"""Explicit optional enterprise capabilities and independent file-key authority."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from uuid import UUID

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.safe_errors import discard_exception_graph, minimize_failure_frames

_VERSION = re.compile(r"[A-Za-z0-9_.-]{1,64}")


class ConfiguredKeyProvider:
    """Keep configured keys in process memory, outside the ciphertext database."""

    @minimize_failure_frames
    def __init__(self, filename, organization_id):
        failure = False
        try:
            path = Path(filename)
            if path.stat().st_size > 65536:
                raise ValueError
            data = json.loads(path.read_text(encoding="utf-8"))
            if set(data) != {"organization_id", "active_version", "keys"}:
                raise ValueError
            if UUID(data["organization_id"]) != organization_id:
                raise ValueError
            active = data["active_version"]
            if not isinstance(active, str) or not _VERSION.fullmatch(active):
                raise ValueError
            rows = data["keys"]
            if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
                raise ValueError
            keys = {}
            for row in rows:
                if not isinstance(row, dict) or set(row) != {"version", "key_hex"}:
                    raise ValueError
                version, encoded = row["version"], row["key_hex"]
                if (
                    not isinstance(version, str)
                    or not _VERSION.fullmatch(version)
                    or version in keys
                    or not isinstance(encoded, str)
                    or re.fullmatch(r"[0-9a-fA-F]{64}", encoded) is None
                ):
                    raise ValueError
                keys[version] = bytes.fromhex(encoded)
            if active not in keys:
                raise ValueError
            self.organization_id, self.active_version, self._keys = organization_id, active, keys
        except Exception as error:
            discard_exception_graph(error)
            failure = True
        if failure:
            filename = organization_id = data = keys = rows = row = encoded = None
            raise GovernanceError("key_configuration_invalid")

    def key_for(self, organization_id, collection_id, version):
        if organization_id != self.organization_id:
            raise GovernanceError("key_scope_invalid")
        key = self._keys.get(version)
        if key is None:
            raise GovernanceError("key_version_unavailable")
        return key


def subject_from_env(settings):
    if not any(name.startswith("AIGUARD_ENTERPRISE_SUBJECT_") for name in os.environ):
        return None
    from app.enterprise.subject_auth import SubjectOIDCSettings

    return SubjectOIDCSettings.from_env(settings)


def managed_keys_from_env(settings):
    filename = os.environ.get("AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE")
    return ConfiguredKeyProvider(filename, settings.organization_id) if filename else None


def consent_gate(store, consent):
    """Bind processing to the exact current activity and reviewed purpose."""

    def check(tx, *, collection, document, action):
        store.lock(tx)
        purpose = tx.execute(
            "SELECT * FROM governance_consent_purposes WHERE purpose_version=%s AND organization_id=%s",
            (collection["purpose_version"], store.organization_id),
        ).fetchone()
        activity = tx.execute(
            "SELECT * FROM governance_activities WHERE activity_id=%s AND organization_id=%s FOR SHARE",
            (collection["activity_id"], store.organization_id),
        ).fetchone()
        if (
            not purpose
            or not activity
            or purpose["activity_id"] != collection["activity_id"]
            or purpose["activity_revision"] != collection["activity_revision"]
            or activity["revision"] != collection["activity_revision"]
            or activity["state"] != "active"
        ):
            raise GovernanceError("consent_scope_required")
        consent.require_processing(
            tx,
            collection["subject_id"],
            collection["purpose_version"],
            activity["data"]["categories"],
        )
        return True

    return check


def managed_services(store, key_provider):
    from app.enterprise.worker import Worker
    from pii_redactor.governance.collections import Collection
    from pii_redactor.governance.consent import Consent
    from pii_redactor.governance.evidence import Evidence
    from pii_redactor.governance.execution import Execution
    from pii_redactor.governance.outbox import Outbox
    from pii_redactor.governance.processing_controls import ProcessingControls

    version = getattr(key_provider, "active_version", "v1")
    processing = ProcessingControls(store)
    collection = Collection(
        store,
        key_provider,
        consent_check=consent_gate(store, Consent(store)),
        key_version=version,
        processing_check=processing.require_activity,
    )
    # New collections use opaque IDs, so startup must prove the configured root key.
    collection.protection.require_key(store.organization_id, None, version)
    evidence = Evidence(store, key_provider, collection=collection)
    execution = Execution(store, collection, evidence)
    from pii_redactor.governance.rights import Rights

    processing.case_checker = rights_case_checker(Rights(store, collection, evidence, execution))
    execution.processing_controls = processing
    return collection, evidence, execution, Worker(execution, Outbox(store))


def rights_case_checker(rights):
    """Bind register evidence to a current case, without granting execution."""
    from pii_redactor.governance.commands import identifier
    from pii_redactor.governance.rights import RIGHTS_ACTION_MAP

    def check(tx, organization_id, department_id, case_id, revision):
        if organization_id != rights.store.organization_id:
            return False
        rights.store.lock(tx)
        row = tx.execute(
            "SELECT * FROM governance_rights_cases WHERE case_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(case_id), organization_id),
        ).fetchone()
        if not row or row["department_id"] != department_id or row["revision"] != revision:
            return False
        try:
            if row["state"] in {"approved", "partial"}:
                rights._authority(tx, row, exact=False)
                return True
            if row["state"] not in {"closed", "refused"} or not row["closure_ref"]:
                return False
            rights._legal(row)
            rights._identity(tx, row)
            for member, version, action in (
                ("verified_by", "verifier_revision", "rights.verify"),
                ("proposed_by", "proposer_revision", "rights.plan"),
                ("approved_by", "approver_revision", "rights.review"),
            ):
                rights._actor(
                    tx, row[member], row[version], RIGHTS_ACTION_MAP[action], department_id
                )
            history = tx.execute(
                "SELECT data FROM governance_rights_history WHERE case_id=%s AND revision=%s AND kind='closure_reviewed'",
                (row["case_id"], row["revision"]),
            ).fetchone()
            return bool(
                history
                and str(history["data"].get("closure_ref")) == str(row["closure_ref"])
                and history["data"].get("closure_proof") == rights._closure_proof(tx, row)
            )
        except GovernanceError:
            return False

    return check

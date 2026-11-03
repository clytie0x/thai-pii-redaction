"""Additive version rotation. Historical ciphertext and keys remain immutable."""

from __future__ import annotations

import json
import os
import re
from contextlib import nullcontext

from pii_redactor.governance.collections import document_context
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.evidence import ProtectedStorage, evidence_context
from pii_redactor.governance.operator_files import create_private, read_private


def verify_keys(store, provider, *, tx=None):
    if tx is None and getattr(store, "production_operations_required", False):
        with store.private_snapshot() as snapshot:
            return verify_keys(snapshot, provider)
    protection = ProtectedStorage(provider)
    protection.require_key(store.organization_id, None, provider.active_version)
    with store.transaction() if tx is None else nullcontext(tx) as tx:
        for row in tx.execute("SELECT collection_id,key_version FROM governance_collections"):
            protection.require_key(store.organization_id, row["collection_id"], row["key_version"])
        with tx.cursor(name="key_document_probe") as cursor:
            cursor.execute(
                "SELECT v.*,d.collection_id FROM governance_document_versions v "
                "JOIN governance_managed_documents d USING(document_id)"
            )
            for row in cursor:
                protection.open(
                    store.organization_id,
                    row["collection_id"],
                    row,
                    document_context(
                        store.organization_id,
                        row["collection_id"],
                        row["document_id"],
                        row["version"],
                        row["content_type"],
                    ),
                )
        with tx.cursor(name="key_evidence_probe") as cursor:
            cursor.execute("SELECT * FROM governance_protected_evidence")
            for row in cursor:
                protection.open(
                    store.organization_id,
                    row["collection_id"],
                    row,
                    evidence_context(store.organization_id, row),
                )
        from pii_redactor.governance.delivery import Delivery

        with tx.cursor(name="key_rights_delivery_probe") as cursor:
            cursor.execute("SELECT * FROM governance_rights_deliveries")
            for row in cursor:
                protection.open(
                    store.organization_id, row["collection_id"], row, Delivery._context(row)
                )
    return True


def prepare_rotation(input_file, output_file, *, version):
    """Create a separate protected candidate; never replace or retire the old file."""
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", version):
        raise GovernanceError("key_configuration_invalid")
    data = read_private(input_file)
    if (
        set(data) != {"organization_id", "active_version", "keys"}
        or not isinstance(data["keys"], list)
        or not 1 <= len(data["keys"]) < 32
        or any(row.get("version") == version for row in data["keys"])
    ):
        raise GovernanceError("key_configuration_invalid")
    from uuid import UUID

    from app.enterprise.capabilities import ConfiguredKeyProvider

    ConfiguredKeyProvider(input_file, UUID(data["organization_id"]))
    candidate = {
        **data,
        "active_version": version,
        "keys": [*data["keys"], {"version": version, "key_hex": os.urandom(32).hex()}],
    }
    with create_private(output_file) as output:
        output.write(json.dumps(candidate, separators=(",", ":")).encode())
        output.flush()
        os.fsync(output.fileno())
    return {"state": "prepared", "retired_keys": 0, "historical_reencryption": "blocked"}


def activate_rotation(store, old_provider, new_provider):
    if new_provider.active_version == old_provider.active_version:
        raise GovernanceError("key_rotation_conflict")
    # Include keys needed by off-DB backups, not just present DB references.
    if any(new_provider._keys.get(v) != k for v, k in old_provider._keys.items()):
        raise GovernanceError("key_history_required")
    with store.transaction() as tx:
        store.lock(tx)
        current = tx.execute(
            "SELECT state,active_key_version FROM governance_operations WHERE singleton FOR UPDATE"
        ).fetchone()
        if not current or (
            current["active_key_version"] != old_provider.active_version
            and not (current["active_key_version"] is None and current["state"] == "quarantined")
        ):
            raise GovernanceError("key_rotation_conflict")
        # Verify the same locked snapshot that the new active version will govern.
        verify_keys(store, old_provider, tx=tx)
        verify_keys(store, new_provider, tx=tx)
        tx.execute(
            "UPDATE governance_operations SET state='quarantined',reconciled_at=NULL,control_digest=NULL,active_key_version=%s "
            "WHERE singleton AND active_key_version IS NOT DISTINCT FROM %s",
            (new_provider.active_version, current["active_key_version"]),
        )
        tx.execute(
            "UPDATE governance_collections SET key_version=%s,revision=revision+1",
            (new_provider.active_version,),
        )
        tx.execute("UPDATE enterprise_staff_sessions SET revoked=true")
        tx.execute("UPDATE enterprise_subject_sessions SET revoked=true")
        tx.execute(
            "UPDATE governance_execution_tasks SET state='unknown',worker_id=NULL,"
            "lease_token=NULL,lease_until=NULL,last_error='key_rotation' "
            "WHERE state IN ('pending','running')"
        )
        tx.execute(
            "UPDATE governance_execution_instructions SET state='unknown',revision=revision+1 "
            "WHERE state IN ('pending','running')"
        )
        store.append_event(
            tx,
            event_code="operations.key_rotated",
            details={
                "from_version": old_provider.active_version,
                "to_version": new_provider.active_version,
            },
        )
    return {"state": "quarantined", "retired_keys": 0, "historical_reencryption": "blocked"}

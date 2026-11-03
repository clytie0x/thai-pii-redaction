"""Production readiness and conservative whole-database recovery barriers."""

from __future__ import annotations

import hashlib
import json
import time
from contextlib import nullcontext
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from pii_redactor.governance.errors import GovernanceError

ROOT = Path(__file__).resolve().parents[2]
MANDATORY_HANDLERS = frozenset(
    {"authority", "registry", "managed", "consent", "holds", "outbox", "rights", "organization"}
)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


def artifact_identity():
    """Bind canonical source or installed wheel bytes, never ambient files."""
    from pii_redactor.artifact_identity import runtime_identity

    try:
        return runtime_identity()
    except ValueError:
        raise GovernanceError("artifact_identity_invalid") from None


def schema_identity():
    return {
        i: hashlib.sha256(p.read_bytes()).hexdigest()
        for i, p in enumerate(
            sorted(
                (
                    p
                    for p in files("pii_redactor.governance").joinpath("migrations").iterdir()
                    if p.name.endswith(".sql")
                ),
                key=lambda p: p.name,
            ),
            1,
        )
    }


@dataclass(frozen=True)
class ProductionProfile:
    artifact: str
    schema: str
    public_origin: str
    evidence: dict
    checkpoint_max_age: int
    checkpoint_max_events: int

    @classmethod
    def parse(cls, value):
        try:
            from urllib.parse import urlsplit

            if set(value) != {
                "profile",
                "artifact",
                "schema",
                "public_origin",
                "evidence",
                "checkpoint_max_age",
                "checkpoint_max_events",
            }:
                raise ValueError
            evidence = value["evidence"]
            required = {
                "tls_proxy",
                "database_runtime_role",
                "storage_acl",
                "secret_custody",
                "key_custody",
                "sink_custody",
                "backup_custody",
                "rpo_rto_drill",
                "capacity",
                "idp",
                "release_scope",
                "image_inventory",
                "rollback",
            }
            origin = urlsplit(value["public_origin"])
            if (
                value["profile"] != "single_organization_production_v1"
                or origin.scheme != "https"
                or not origin.hostname
                or origin.path
                or origin.username
                or origin.password
                or origin.query
                or origin.fragment
                or len(value["artifact"]) != 64
                or len(value["schema"]) != 64
                or set(evidence) != required
                or any(
                    not isinstance(v, str)
                    or not 8 <= len(v) <= 128
                    or v.startswith(("PENDING", "REPLACE"))
                    for v in evidence.values()
                )
                or type(value["checkpoint_max_age"]) is not int
                or not 1 <= value["checkpoint_max_age"] <= 86400
                or type(value["checkpoint_max_events"]) is not int
                or not 0 <= value["checkpoint_max_events"] <= 10000
            ):
                raise ValueError
            return cls(
                value["artifact"],
                value["schema"],
                value["public_origin"],
                evidence,
                value["checkpoint_max_age"],
                value["checkpoint_max_events"],
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise GovernanceError("production_profile_invalid") from None


class Operations:
    def __init__(self, store):
        self.store = store

    def require_reconciled(self):
        with self.store.transaction() as tx:
            row = tx.execute("SELECT state FROM governance_operations").fetchone()
            if not row or row["state"] != "reconciled":
                raise GovernanceError("restore_quarantined")

    def quarantine(self, restore_id, *, manifest=None):
        if manifest is not None:
            from pii_redactor.governance.recovery_controls import record_restore

            if str(restore_id) != manifest.get("archive_id"):
                raise GovernanceError("recovery_lineage_missing")
            record_restore(self.store, manifest)
            return
        with self.store.transaction() as tx:
            self.store.lock(tx)
            tx.execute(
                "UPDATE governance_operations SET state='quarantined',restore_id=%s,"
                "reconciled_at=NULL,control_digest=NULL",
                (restore_id,),
            )
            tx.execute("UPDATE enterprise_staff_sessions SET revoked=true")
            tx.execute("UPDATE enterprise_subject_sessions SET revoked=true")
            # A restored lease or approval is not fresh execution authority.
            tx.execute(
                "UPDATE governance_execution_tasks SET state='unknown',worker_id=NULL,"
                "lease_token=NULL,lease_until=NULL,last_error='restore_quarantined' "
                "WHERE state IN ('pending','running')"
            )
            tx.execute(
                "UPDATE governance_execution_instructions SET state='unknown',revision=revision+1 "
                "WHERE state IN ('pending','running')"
            )
            self.store.append_event(tx, event_code="operations.quarantined")

    def reconcile(
        self,
        source,
        *,
        handlers,
        checkpoint=None,
        runtime_store=None,
        key_provider=None,
        profile=None,
    ):
        from pii_redactor.governance.recovery_controls import reconcile

        return reconcile(
            self.store,
            source,
            handlers=handlers,
            checkpoint=checkpoint,
            runtime_store=runtime_store,
            key_provider=key_provider,
            profile=profile,
        )


def control_handlers():
    from pii_redactor.governance.recovery_controls import control_handlers as build

    return build()


def check_audit_metadata(store, *, tx=None):
    """Reject legacy oversize metadata before transferring historical payloads."""
    if getattr(store, "_verifier_snapshot", False):
        store._require_open()
        if store._metadata_checked:
            return True
    if tx is None and getattr(store, "production_operations_required", False):
        with store.private_snapshot() as snapshot, snapshot.transaction() as readonly:
            return check_audit_metadata(None, tx=readonly)
    with store.transaction() if tx is None else nullcontext(tx) as tx:
        invalid = tx.execute(
            "SELECT EXISTS(SELECT 1 FROM governance_audit "
            "WHERE octet_length(details::text)>4096 OR octet_length(event_code)>128 LIMIT 1) AS oversized"
        ).fetchone()
        if invalid["oversized"]:
            raise GovernanceError("audit_metadata_unbounded")
    if getattr(store, "_verifier_snapshot", False):
        store._metadata_checked = True
    return True


def check_database(store):
    """Read only; do not migrate or enroll during readiness."""
    checks = {}
    with store.transaction() as tx:
        tx.execute("SELECT 1")
        checks["database"] = "ready"
        applied = {
            r["version"]: r["digest"]
            for r in tx.execute("SELECT version,digest FROM governance_schema")
        }
        if applied != schema_identity():
            raise GovernanceError("migration_mismatch")
        checks["schema"] = "ready"
        row = tx.execute("SELECT enrolled_at FROM governance_organization").fetchone()
        if not row or row["enrolled_at"] is None:
            raise GovernanceError("enrollment_required")
        checks["enrollment"] = "ready"
    return checks


def check_runtime_restore(store):
    expected = getattr(store, "runtime_key_version", "")
    with store.transaction() as tx:
        row = tx.execute(
            "SELECT state,active_key_version FROM governance_operations WHERE singleton"
        ).fetchone()
        if (
            not expected
            or not row
            or row["state"] != "reconciled"
            or row["active_key_version"] != expected
        ):
            raise GovernanceError("restore_quarantined")
    return True


def readiness(store, profile, checkpoint, key_check, *, capture=None, checkpoint_history=None):
    checks = {}
    for name, check in (
        (
            "profile",
            lambda: profile is not None
            and profile.artifact == artifact_identity()
            and profile.schema == digest(schema_identity()),
        ),
        ("database_schema_enrollment", lambda: check_database(store)),
        ("runtime_role", lambda: check_runtime_role(store)),
        ("keys", key_check),
        ("audit_metadata", lambda: check_audit_metadata(store)),
        (
            "audit",
            lambda: store.verify_audit() if checks.get("audit_metadata") == "ready" else False,
        ),
        (
            "checkpoint",
            lambda: (
                checkpoint.check(store, history=checkpoint_history)
                if checkpoint_history is not None
                else checkpoint.check(store)
            )
            if checkpoint and checks.get("audit_metadata") == "ready"
            else False,
        ),
        ("restore", lambda: check_runtime_restore(store)),
    ):
        try:
            result = check() if check else False
            if result is False:
                raise GovernanceError("prerequisite_unverified")
            if capture is not None:
                capture[name] = result
            if isinstance(result, dict) and name == "database_schema_enrollment":
                checks.update(result)
            else:
                checks[name] = "ready"
        except Exception:
            checks[name] = "blocked"
    return {
        "status": "ready" if all(v == "ready" for v in checks.values()) else "blocked",
        "checks": checks,
        "observed_at": int(time.time()),
    }


def check_runtime_role(store):
    from pii_redactor.governance.runtime_roles import check_runtime_role as check

    return check(store)

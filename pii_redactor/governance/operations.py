"""Production readiness and conservative whole-database recovery barriers."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from pii_redactor.governance.errors import GovernanceError

ROOT = Path(__file__).resolve().parents[2]
MANDATORY_HANDLERS = frozenset({"managed", "consent", "holds", "outbox", "rights"})


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


def artifact_identity():
    """Bind runtime source, assets, version and dependency locks without PII."""
    names = [
        p
        for base in ("pii_redactor", "app/enterprise")
        for p in (ROOT / base).rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix in {".py", ".sql", ".html", ".js", ".css", ".woff2", ".png"}
    ]
    names += list(ROOT.glob("requirements*.lock")) + [ROOT / "VERSION", ROOT / "pyproject.toml"]
    return digest(
        {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(names)
        }
    )


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

    def quarantine(self, restore_id):
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

    def reconcile(self, source, *, handlers, checkpoint=None):
        """An absent handler/source never certifies recovery. Parent supplies M7.

        A handler receives locked source/target transactions and must either prove
        and replay its complete scope, returning a 64-char evidence digest, or fail.
        No caller-selected import/module name is accepted by the operator CLI.
        """
        if not MANDATORY_HANDLERS.issubset(handlers):
            raise GovernanceError("recovery_handler_missing")
        if (
            source is None
            or source.organization_id != self.store.organization_id
            or checkpoint is None
        ):
            raise GovernanceError("recovery_source_unavailable")
        source_info, target_info = (conninfo_to_dict(s._dsn) for s in (source, self.store))
        if all(source_info.get(k) == target_info.get(k) for k in ("host", "port", "dbname")):
            raise GovernanceError("recovery_source_not_independent")
        self.store.check_ready()
        source.check_ready()
        receipt = checkpoint.check(source)
        with source.transaction() as src, self.store.transaction() as dst:
            source.lock(src)
            self.store.lock(dst)
            tail = src.execute(
                "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            anchor = src.execute(
                "SELECT event_hash FROM governance_audit WHERE sequence=%s", (receipt["sequence"],)
            ).fetchone()
            if not tail or not anchor:
                raise GovernanceError("recovery_source_unavailable")
            checkpoint.verify_chain(
                {receipt["sequence"]: anchor["event_hash"], tail["sequence"]: tail["event_hash"]},
                receipt,
            )
            state = dst.execute("SELECT state FROM governance_operations FOR UPDATE").fetchone()
            if not state or state["state"] != "quarantined":
                raise GovernanceError("restore_state_conflict")
            proofs = {}
            for name in sorted(MANDATORY_HANDLERS):
                proof = handlers[name](src, dst)
                if not isinstance(proof, str) or len(proof) != 64:
                    raise GovernanceError("recovery_scope_unverified")
                proofs[name] = proof
            dst.execute(
                "UPDATE governance_operations SET state='reconciled',"
                "reconciled_at=clock_timestamp(),control_digest=%s",
                (digest(proofs),),
            )
            self.store.append_event(dst, event_code="operations.reconciled")
        return {"state": "reconciled", "control_digest": digest(proofs)}


CONTROL_TABLES = {
    "managed": (
        "governance_managed_documents",
        "governance_document_versions",
        "governance_collection_snapshots",
    ),
    "consent": (
        "governance_subject_links",
        "governance_consent_events",
        "governance_consent_current",
        "governance_consent_propagation",
    ),
    "holds": ("governance_holds", "governance_retention_copies"),
    "outbox": ("governance_execution_outcomes",),
}


def control_handlers():
    """Conservative equality proof. Newer authority requires a refreshed backup.

    Deliberately excludes rights: case/export revocation is not implemented here.
    This never merges stale histories or silently replays old approvals.
    """

    def handler(tables):
        def compare(src, dst):
            proofs = {}
            for table in tables:
                query = sql.SQL(
                    "SELECT to_jsonb(t) AS row FROM {} t ORDER BY to_jsonb(t)::text"
                ).format(sql.Identifier(table))

                def fingerprint(tx, table=table, query=query):
                    h = hashlib.sha256()
                    with tx.cursor(name="controls_" + table) as cursor:
                        cursor.execute(query)
                        for row in cursor:
                            h.update(digest(row["row"]).encode())
                    return h.hexdigest()

                a, b = fingerprint(src), fingerprint(dst)
                if a != b:
                    raise GovernanceError("recovery_controls_changed")
                proofs[table] = a
            return digest(proofs)

        return compare

    return {name: handler(tables) for name, tables in CONTROL_TABLES.items()}


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


def readiness(store, profile, checkpoint, key_check):
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
        ("audit", store.verify_audit),
        ("checkpoint", lambda: checkpoint.check(store) if checkpoint else False),
        ("restore", lambda: Operations(store).require_reconciled()),
    ):
        try:
            result = check() if check else False
            if result is False:
                raise GovernanceError("prerequisite_unverified")
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
    with store.transaction() as tx:
        role = tx.execute(
            "SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        ddl = tx.execute(
            "SELECT has_schema_privilege(current_user,current_schema(),'CREATE') AS allowed"
        ).fetchone()
        owns = tx.execute(
            "SELECT count(*) AS n FROM pg_tables WHERE schemaname=current_schema() "
            "AND pg_has_role(current_user,tableowner,'MEMBER')"
        ).fetchone()
        if not role or any(role.values()) or ddl["allowed"] or owns["n"]:
            raise GovernanceError("runtime_role_overprivileged")
    return True

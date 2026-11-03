"""PostgreSQL authority and atomic audit. No redaction mappings are persisted."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.resources import files
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Enrollment

_ZERO_HASH = "0" * 64


def _event_digest(event: dict) -> str:
    payload = {
        key: str(event[key]) if event[key] is not None else None
        for key in ("event_id", "organization_id", "actor_id", "target_id")
    }
    payload.update(
        {
            key: event[key]
            for key in ("sequence", "event_code", "record_revision", "details", "previous_hash")
        }
    )
    payload["occurred_at"] = event["occurred_at"].astimezone(UTC).isoformat(timespec="microseconds")
    raw = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _audit_rows(tx, organization_id, *, metadata_checked=False):
    from pii_redactor.governance.operations import check_audit_metadata

    if not metadata_checked:
        check_audit_metadata(None, tx=tx)
    previous, count = _ZERO_HASH, 0
    with tx.cursor(name="audit_verifier") as events:
        events.execute("SELECT * FROM governance_audit ORDER BY sequence")
        for event in events:
            count += 1
            if (
                event["sequence"] != count
                or event["organization_id"] != organization_id
                or event["previous_hash"] != previous
                or event["event_hash"] != _event_digest(event)
            ):
                raise GovernanceError("audit_integrity_failure")
            previous = event["event_hash"]
    enrolled = tx.execute("SELECT enrolled_at FROM governance_organization").fetchone()
    if enrolled["enrolled_at"] is not None and count == 0:
        raise GovernanceError("audit_integrity_failure")
    return {"events": count, "tail_hash": previous}


def verifier_identity(tx):
    """Identify the authenticated database boundary without returning a DSN."""
    return dict(
        tx.execute(
            "SELECT current_user AS runtime_role,session_user AS login_role,current_database() AS database_name,"
            "(SELECT oid FROM pg_database WHERE datname=current_database()) AS database_oid,"
            "current_schema() AS schema_name,(SELECT oid FROM pg_namespace WHERE nspname=current_schema()) AS schema_oid,"
            "(SELECT oid FROM pg_roles WHERE rolname=current_user) AS role_oid,"
            "inet_server_addr()::text AS server_address,inet_server_port() AS server_port"
        ).fetchone()
    )


class _VerifierSnapshot:
    """Private verification only. Normal API transactions never receive this view."""

    __slots__ = (
        "_audit",
        "_closed",
        "_connection",
        "_metadata_checked",
        "identity",
        "organization_id",
        "runtime_key_version",
    )
    _verifier_snapshot = True

    def __init__(self, connection, organization_id, key_version):
        self._connection, self.organization_id = connection, organization_id
        self.runtime_key_version, self._audit, self._closed = key_version, None, False
        self._metadata_checked = False
        self.identity = verifier_identity(connection)

    def _require_open(self):
        if self._closed:
            raise GovernanceError("verifier_snapshot_closed")

    @contextmanager
    def transaction(self):
        self._require_open()
        yield self._connection

    def lock(self, _tx):
        raise GovernanceError("verifier_snapshot_only")

    def verify_audit(self):
        from pii_redactor.governance.operations import check_audit_metadata

        self._require_open()
        if self._audit is None:
            check_audit_metadata(self)
            self._audit = _audit_rows(self._connection, self.organization_id, metadata_checked=True)
        return dict(self._audit)


class Store:
    def __init__(self, dsn: str, organization_id: UUID):
        if not isinstance(dsn, str) or not dsn or not isinstance(organization_id, UUID):
            raise GovernanceError("configuration_invalid")
        self._dsn = dsn
        self.organization_id = organization_id
        self.production_operations_required = False
        self.runtime_key_version = ""

    @contextmanager
    def _transaction(self, *, check_organization=True):
        try:
            with psycopg.connect(
                self._dsn, autocommit=True, row_factory=dict_row, connect_timeout=5
            ) as connection:
                with connection.transaction():
                    connection.execute("SET LOCAL statement_timeout = '10s'")
                    connection.execute("SET LOCAL lock_timeout = '5s'")
                    if check_organization:
                        organization = connection.execute(
                            "SELECT organization_id FROM governance_organization"
                        ).fetchone()
                        if (
                            not organization
                            or organization["organization_id"] != self.organization_id
                        ):
                            raise GovernanceError("organization_mismatch")
                    if self.production_operations_required:
                        connection.execute("SET LOCAL aiguard.production_operations = 'on'")
                        connection.execute(
                            "SELECT set_config('aiguard.key_version',%s,true)",
                            (self.runtime_key_version,),
                        )
                        self.lock(connection)
                        # Fence disclosure reads as well as database writes.
                        connection.execute("SELECT governance_runtime_guard()")
                    yield connection
        except psycopg.Error:
            raise GovernanceError("storage_failure") from None

    def transaction(self):
        return self._transaction()

    @contextmanager
    def private_snapshot(self):
        """One repeatable read-only verifier snapshot, without runtime/advisory locks."""
        view = None
        try:
            with psycopg.connect(
                self._dsn, autocommit=True, row_factory=dict_row, connect_timeout=5
            ) as connection:
                with connection.transaction():
                    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                    connection.execute("SET LOCAL statement_timeout='10s'")
                    connection.execute("SET LOCAL lock_timeout='5s'")
                    organization = connection.execute(
                        "SELECT organization_id FROM governance_organization"
                    ).fetchone()
                    if not organization or organization["organization_id"] != self.organization_id:
                        raise GovernanceError("organization_mismatch")
                    view = _VerifierSnapshot(
                        connection, self.organization_id, self.runtime_key_version
                    )
                    yield view
        except psycopg.Error:
            raise GovernanceError("storage_failure") from None
        finally:
            if view is not None:
                view._closed = True

    def check_ready(self):
        """Check schema and enrollment without running privileged DDL."""
        resources = sorted(
            (
                p
                for p in files("pii_redactor.governance").joinpath("migrations").iterdir()
                if p.name.endswith(".sql")
            ),
            key=lambda p: p.name,
        )
        expected = {}
        for version, resource in enumerate(resources, 1):
            if not resource.name.startswith(f"{version:03d}_"):
                raise GovernanceError("migration_mismatch")
            expected[version] = hashlib.sha256(resource.read_bytes()).hexdigest()
        with self.transaction() as tx:
            applied = {
                r["version"]: r["digest"]
                for r in tx.execute("SELECT version,digest FROM governance_schema")
            }
            if not expected or applied != expected:
                raise GovernanceError("migration_mismatch")
            row = tx.execute("SELECT enrolled_at FROM governance_organization").fetchone()
            if row["enrolled_at"] is None:
                raise GovernanceError("enrollment_required")
        self.verify_audit()
        return len(expected)

    def lock(self, tx):
        tx.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            ("aiguard-governance:" + str(self.organization_id),),
        )

    def migrate(self):
        resources = sorted(
            files("pii_redactor.governance").joinpath("migrations").iterdir(), key=lambda p: p.name
        )
        migrations = [p for p in resources if p.name.endswith(".sql")]
        with self._transaction(check_organization=False) as tx:
            tx.execute("SELECT pg_advisory_xact_lock(1786169001)")
            tx.execute("""
                CREATE TABLE IF NOT EXISTS governance_schema (
                    version integer PRIMARY KEY,
                    digest text NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
            """)
            applied = {
                r["version"]: r["digest"]
                for r in tx.execute("SELECT version, digest FROM governance_schema")
            }
            if set(applied) != set(range(1, len(applied) + 1)) or len(applied) > len(migrations):
                raise GovernanceError("migration_mismatch")
            for version, resource in enumerate(migrations, 1):
                if not resource.name.startswith(f"{version:03d}_"):
                    raise GovernanceError("migration_mismatch")
                source = resource.read_bytes()
                digest = hashlib.sha256(source).hexdigest()
                if version in applied:
                    if applied[version] != digest:
                        raise GovernanceError("migration_mismatch")
                else:
                    tx.execute(source.decode("utf-8"), prepare=False)
                    tx.execute(
                        "INSERT INTO governance_schema(version, digest) VALUES (%s, %s)",
                        (version, digest),
                    )
            organization = tx.execute(
                "SELECT organization_id FROM governance_organization"
            ).fetchone()
            if organization is None:
                tx.execute(
                    "INSERT INTO governance_organization(organization_id) VALUES (%s)",
                    (self.organization_id,),
                )
            elif organization["organization_id"] != self.organization_id:
                raise GovernanceError("organization_mismatch")

    def append_event(
        self, tx, *, event_code, actor_id=None, target_id=None, revision=None, details=None
    ):
        self.lock(tx)
        tail = tx.execute(
            "SELECT sequence, event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        event = {
            "sequence": tail["sequence"] + 1 if tail else 1,
            "event_id": uuid4(),
            "organization_id": self.organization_id,
            "actor_id": actor_id,
            "event_code": event_code,
            "target_id": target_id,
            "record_revision": revision,
            "occurred_at": datetime.now(UTC),
            "details": details or {},
            "previous_hash": tail["event_hash"] if tail else _ZERO_HASH,
        }
        event["event_hash"] = _event_digest(event)
        tx.execute(
            """
            INSERT INTO governance_audit(sequence, event_id, organization_id, actor_id,
                event_code, target_id, record_revision, occurred_at, details, previous_hash, event_hash)
            VALUES (%(sequence)s, %(event_id)s, %(organization_id)s, %(actor_id)s,
                %(event_code)s, %(target_id)s, %(record_revision)s, %(occurred_at)s,
                %(details)s, %(previous_hash)s, %(event_hash)s)
        """,
            {**event, "details": Jsonb(event["details"])},
        )
        return event["event_id"]

    def bootstrap(self, members: Sequence[Enrollment]) -> list[UUID]:
        try:
            if not isinstance(members, (list, tuple)) or not 2 <= len(members) <= 16:
                raise GovernanceError("enrollment_invalid")
            members = [Enrollment.model_validate(m.model_dump()) for m in members]
        except (AttributeError, ValidationError):
            raise GovernanceError("enrollment_invalid") from None
        identities = {(m.principal.issuer, m.principal.subject) for m in members}
        administrators = {i for i, m in enumerate(members) if "system_administrator" in m.roles}
        reviewers = {
            i
            for i, m in enumerate(members)
            if "authority_reviewer" in m.roles and "privacy_reviewer" in m.roles
        }
        if len(identities) != len(members) or not any(
            a != r for a in administrators for r in reviewers
        ):
            raise GovernanceError("enrollment_invalid")
        with self.transaction() as tx:
            self.lock(tx)
            organization = tx.execute(
                "SELECT enrolled_at FROM governance_organization FOR UPDATE"
            ).fetchone()
            if organization["enrolled_at"] is not None:
                raise GovernanceError("already_enrolled")
            ids = []
            for member in members:
                member_id = uuid4()
                tx.execute(
                    """
                    INSERT INTO governance_members(member_id, organization_id, issuer, subject, roles, departments)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """,
                    (
                        member_id,
                        self.organization_id,
                        member.principal.issuer,
                        member.principal.subject,
                        Jsonb(member.roles),
                        Jsonb(member.departments),
                    ),
                )
                ids.append(member_id)
            tx.execute("UPDATE governance_organization SET enrolled_at = now()")
            self.append_event(
                tx,
                event_code="organization.enrolled",
                target_id=self.organization_id,
                details={"member_count": len(members)},
            )
            return ids

    def verify_audit(self):
        if self.production_operations_required:
            with self.private_snapshot() as snapshot:
                return snapshot.verify_audit()
        with self.transaction() as tx:
            self.lock(tx)
            return _audit_rows(tx, self.organization_id)

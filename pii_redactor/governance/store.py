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


class Store:
    def __init__(self, dsn: str, organization_id: UUID):
        if not isinstance(dsn, str) or not dsn or not isinstance(organization_id, UUID):
            raise GovernanceError("configuration_invalid")
        self._dsn = dsn
        self.organization_id = organization_id

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
                    yield connection
        except psycopg.Error:
            raise GovernanceError("storage_failure") from None

    def transaction(self):
        return self._transaction()

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

    def _append_enrollment_audit(self, tx, member_count):
        self.lock(tx)
        tail = tx.execute(
            "SELECT sequence, event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        event = {
            "sequence": tail["sequence"] + 1 if tail else 1,
            "event_id": uuid4(),
            "organization_id": self.organization_id,
            "actor_id": None,
            "event_code": "organization.enrolled",
            "target_id": self.organization_id,
            "record_revision": None,
            "occurred_at": datetime.now(UTC),
            "details": {"member_count": member_count},
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
            self._append_enrollment_audit(tx, len(members))
            return ids

    def verify_audit(self):
        with self.transaction() as tx:
            self.lock(tx)
            previous = _ZERO_HASH
            count = 0
            for event in tx.execute("SELECT * FROM governance_audit ORDER BY sequence"):
                count += 1
                if (
                    event["sequence"] != count
                    or event["organization_id"] != self.organization_id
                    or event["previous_hash"] != previous
                    or event["event_hash"] != _event_digest(event)
                ):
                    raise GovernanceError("audit_integrity_failure")
                previous = event["event_hash"]
            enrolled = tx.execute("SELECT enrolled_at FROM governance_organization").fetchone()
            if enrolled["enrolled_at"] is not None and count == 0:
                raise GovernanceError("audit_integrity_failure")
            return {"events": count, "tail_hash": previous}

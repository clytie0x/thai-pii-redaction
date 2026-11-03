"""Reviewed offline first activation. This does not certify human or legal acceptance."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from pydantic import Field, ValidationError, field_validator, model_validator

from pii_redactor.governance.checkpoints import CheckpointClient
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.key_operations import verify_keys
from pii_redactor.governance.models import ClosedModel
from pii_redactor.governance.operations import (
    ProductionProfile,
    artifact_identity,
    digest,
    schema_identity,
)
from pii_redactor.governance.operator_files import file_authority_binding, require_private
from pii_redactor.governance.runtime_roles import TABLES, check_runtime_role
from pii_redactor.governance.store import Store
from pii_redactor.safe_errors import minimize_failure_frames

_INITIAL = {"governance_initial_activations", "governance_initial_journal"}
_AUTHORITY = {"governance_members", "governance_grants", "governance_commands"}
_ALLOWED = (
    _INITIAL
    | _AUTHORITY
    | {"governance_organization", "governance_schema", "governance_operations", "governance_audit"}
)


@minimize_failure_frames
def _file_snapshot(paths, *, protected):
    snapshots, values = {}, {}
    for name, path in paths.items():
        if protected:
            require_private(path)
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)() or not path.is_file():
            raise GovernanceError("initial_file_authority_changed")
        before = path.stat()
        permission = file_authority_binding(path)
        with path.open("rb") as stream:
            raw = stream.read(65537)
        after = path.stat()
        if (
            len(raw) > 65536
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or permission != file_authority_binding(path)
        ):
            raise GovernanceError("initial_file_authority_changed")
        values[name] = json.loads(raw)
        if not isinstance(values[name], dict):
            raise GovernanceError("initial_file_authority_changed")
        snapshots[name] = {
            "path": str(path.resolve()),
            "device": before.st_dev,
            "inode": before.st_ino,
            "size": before.st_size,
            "modified": before.st_mtime_ns,
            "authority": permission,
            "content": hashlib.sha256(raw).hexdigest(),
        }
    return snapshots, values


class InitialFileAuthority:
    """Exactly the selected operator files; no caller-selected validation code."""

    def __init__(
        self,
        *,
        operator_db,
        runtime_db,
        profile_file,
        checkpoint_file,
        managed_keys,
        review_file=None,
    ):
        self._paths = {
            "operator": Path(operator_db),
            "runtime": Path(runtime_db),
            "profile": Path(profile_file),
            "checkpoint": Path(checkpoint_file),
            "managed": Path(managed_keys),
        }
        if review_file is not None:
            self._paths["review"] = Path(review_file)
        self._snapshot, _values = _file_snapshot(self._paths, protected=True)
        self.binding_digest = digest(self._snapshot)
        self.review_binding_digest = digest(
            {k: v for k, v in self._snapshot.items() if k != "review"}
        )

    @minimize_failure_frames
    def validate(self, *, store, runtime_store, profile, key_provider, checkpoint, review=None):
        try:
            observed, values = _file_snapshot(self._paths, protected=False)
            if observed != self._snapshot or (review is not None and "review" not in values):
                raise ValueError
            for name, current in (("operator", store), ("runtime", runtime_store)):
                data = values[name]
                if (
                    set(data) not in ({"dsn"}, {"dsn", "purpose"})
                    or data.get("purpose") not in (None, "synthetic_enterprise_tests")
                    or conninfo_to_dict(data["dsn"]) != conninfo_to_dict(current._dsn)
                ):
                    raise ValueError
            fresh_profile = ProductionProfile.parse(values["profile"])
            if asdict(fresh_profile) != asdict(profile):
                raise ValueError
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

            witness = values["checkpoint"]
            if set(witness) != {"url", "token", "public_key_hex"} or (
                witness["url"].rstrip("/") != checkpoint.url
                or witness["token"] != checkpoint._token
                or bytes.fromhex(witness["public_key_hex"])
                != checkpoint.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
                or checkpoint.organization_id != store.organization_id
                or checkpoint.max_age != profile.checkpoint_max_age
                or checkpoint.max_events != profile.checkpoint_max_events
            ):
                raise ValueError
            configured = values["managed"]
            cached = getattr(key_provider, "_keys", None)
            if set(configured) != {"organization_id", "active_version", "keys"} or (
                UUID(configured["organization_id"]) != store.organization_id
                or getattr(key_provider, "organization_id", None) != store.organization_id
                or configured["active_version"] != key_provider.active_version
                or not isinstance(cached, dict)
                or not 1 <= len(cached) <= 32
                or not all(
                    isinstance(k, str) and type(v) is bytes and len(v) == 32
                    for k, v in cached.items()
                )
                or not isinstance(configured["keys"], list)
                or not 1 <= len(configured["keys"]) <= 32
            ):
                raise ValueError
            fresh_keys = {}
            for row in configured["keys"]:
                if (
                    set(row) != {"version", "key_hex"}
                    or row["version"] in fresh_keys
                    or (
                        not isinstance(row["version"], str)
                        or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", row["version"])
                        or not isinstance(row["key_hex"], str)
                        or not re.fullmatch(r"[0-9a-fA-F]{64}", row["key_hex"])
                    )
                ):
                    raise ValueError
                fresh_keys[row["version"]] = bytes.fromhex(row["key_hex"])
            if fresh_keys != cached or configured["active_version"] not in fresh_keys:
                raise ValueError
            if review is not None and ActivationReview.model_validate(values["review"]).model_dump(
                mode="json", by_alias=True
            ) != review.model_dump(mode="json", by_alias=True):
                raise ValueError
        except Exception:
            raise GovernanceError("initial_file_authority_changed") from None


class SyntheticActivationAuthority:
    """Explicit in-memory synthetic-provider contract; never file/host acceptance."""

    def __init__(self, *, store, runtime_store, key_provider, checkpoint):
        from pii_redactor.governance.evidence import SyntheticKeyProvider

        if type(key_provider) is not SyntheticKeyProvider or not isinstance(
            checkpoint, CheckpointClient
        ):
            raise GovernanceError("initial_authority_unverified")
        for current in (store, runtime_store):
            info = conninfo_to_dict(current._dsn)
            if info.get("host") not in {"127.0.0.1", "localhost", "::1"} or info.get(
                "hostaddr"
            ) not in {None, "127.0.0.1", "localhost", "::1"}:
                raise GovernanceError("initial_authority_unverified")
        if urlsplit(checkpoint.url).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise GovernanceError("initial_authority_unverified")
        self._objects = (store, runtime_store, key_provider, checkpoint)
        self._dsns = (store._dsn, runtime_store._dsn)
        self._keys = self._key_binding(key_provider)
        self._witness = self._witness_binding(checkpoint)
        self.binding_digest = digest(
            {
                "contract": "explicit_synthetic_memory_v1",
                "organization": str(store.organization_id),
                "source": hashlib.sha256(store._dsn.encode()).hexdigest(),
                "runtime": hashlib.sha256(runtime_store._dsn.encode()).hexdigest(),
                "witness": self._witness,
                "keys": self._keys,
            }
        )
        self.review_binding_digest = self.binding_digest

    @staticmethod
    def _key_binding(provider):
        return digest(
            {
                "active": provider.active_version,
                "keys": {str(k): hashlib.sha256(v).hexdigest() for k, v in provider._keys.items()},
            }
        )

    @staticmethod
    def _witness_binding(checkpoint):
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        return digest(
            {
                "url": checkpoint.url,
                "organization": str(checkpoint.organization_id),
                "token": hashlib.sha256(checkpoint._token.encode()).hexdigest(),
                "public_key": checkpoint.public_key.public_bytes(
                    Encoding.Raw, PublicFormat.Raw
                ).hex(),
                "max_age": checkpoint.max_age,
                "max_events": checkpoint.max_events,
            }
        )

    def validate(self, *, store, runtime_store, profile, key_provider, checkpoint, review=None):
        if any(
            actual is not expected
            for actual, expected in zip(
                (store, runtime_store, key_provider, checkpoint), self._objects
            )
        ) or self._dsns != (store._dsn, runtime_store._dsn):
            raise GovernanceError("initial_authority_unverified")
        if self._key_binding(key_provider) != self._keys:
            raise GovernanceError("initial_key_changed")
        if self._witness_binding(checkpoint) != self._witness:
            raise GovernanceError("initial_authority_unverified")


def _authority(authority, **inputs):
    if type(authority) not in {InitialFileAuthority, SyntheticActivationAuthority}:
        raise GovernanceError("initial_authority_unverified")
    authority.validate(**inputs)
    return authority.binding_digest


class ActivationReview(ClosedModel):
    activation_id: UUID = Field(strict=False)
    organization_id: UUID = Field(strict=False)
    artifact: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_digest: str = Field(alias="schema", pattern=r"^[0-9a-f]{64}$")
    profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_origin: str = Field(min_length=1, max_length=2048)
    key_version: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    runtime_role: str = Field(min_length=1, max_length=63)
    database_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_authority: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposer_id: UUID = Field(strict=False)
    proposer_revision: int = Field(ge=1)
    reviewer_id: UUID = Field(strict=False)
    reviewer_revision: int = Field(ge=1)
    proposer_evidence_ref: UUID = Field(strict=False)
    reviewer_evidence_ref: UUID = Field(strict=False)
    decision: str = Field(pattern=r"^approved$")
    reviewed_at: datetime = Field(strict=False)
    expires_at: datetime = Field(strict=False)
    supersedes: UUID | None = Field(default=None, strict=False)

    @field_validator("reviewed_at", "expires_at")
    @classmethod
    def zoned(cls, value):
        if value.tzinfo is None:
            raise ValueError("zoned review time required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def exact_review(self):
        ids = (
            self.activation_id,
            self.organization_id,
            self.proposer_id,
            self.reviewer_id,
            self.proposer_evidence_ref,
            self.reviewer_evidence_ref,
        )
        if any(not value.int for value in ids) or self.proposer_id == self.reviewer_id:
            raise ValueError("distinct reviewed authorities required")
        if "\0" in self.runtime_role or len(self.runtime_role.encode("utf-8")) > 63:
            raise ValueError("runtime role invalid")
        if not self.reviewed_at < self.expires_at <= self.reviewed_at + timedelta(hours=24):
            raise ValueError("bounded review required")
        return self


def _head(tx):
    row = tx.execute(
        "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
    ).fetchone()
    if not row:
        raise GovernanceError("initial_enrollment_required")
    return row


def _operator(tx):
    tx.execute("SET LOCAL timezone='UTC'")
    row = tx.execute(
        "SELECT has_table_privilege(current_user,'governance_operations','UPDATE') AS allowed"
    ).fetchone()
    if not row or not row["allowed"]:
        raise GovernanceError("initial_operator_required")


def _profile(profile, review=None):
    if (
        not isinstance(profile, ProductionProfile)
        or profile.artifact != artifact_identity()
        or profile.schema != digest(schema_identity())
    ):
        raise GovernanceError("production_profile_invalid")
    ProductionProfile.parse({"profile": "single_organization_production_v1", **asdict(profile)})
    value = digest(asdict(profile))
    if review is not None and (
        review.artifact != profile.artifact
        or review.schema_digest != profile.schema
        or review.profile_digest != value
        or review.public_origin != profile.public_origin
    ):
        raise GovernanceError("initial_review_scope_changed")
    return value


def _key_proof(store, provider, activation_id):
    try:
        version = provider.active_version
        key = provider.key_for(store.organization_id, None, version)
        if not isinstance(version, str) or not isinstance(key, bytes) or len(key) != 32:
            raise ValueError
        result = hmac.new(
            key, b"aiguard.initial-activation.v1:" + activation_id.bytes, hashlib.sha256
        ).hexdigest()
    except Exception:
        raise GovernanceError("key_configuration_invalid") from None
    return version, result


def _database_identity(tx):
    value = tx.execute(
        "SELECT system_identifier::text AS system FROM pg_control_system()"
    ).fetchone()
    target = tx.execute(
        "SELECT current_schema() AS schema,"
        "(SELECT oid FROM pg_database WHERE datname=current_database()) AS database_oid"
    ).fetchone()
    return digest({**value, **target})


def _record_identity(tx, record):
    if record["review"].get("database_identity") != _database_identity(tx):
        raise GovernanceError("initial_runtime_target_mismatch")


def _released_receipt(tx, review, record):
    state = tx.execute("SELECT state,restore_id FROM governance_operations FOR UPDATE").fetchone()
    restored = tx.execute(
        "SELECT EXISTS(SELECT 1 FROM governance_restore_sessions) AS present"
    ).fetchone()["present"]
    if not state or state["restore_id"] is not None or restored:
        raise GovernanceError("initial_target_not_fresh")
    _record_identity(tx, record)
    return {
        "state": "already_activated",
        "current_state": state["state"],
        "status": "blocked" if state["state"] != "reconciled" else "recorded",
        "activation_id": str(review.activation_id),
        "current_readiness": "unverified",
    }


def _fresh(tx, store):
    state = tx.execute("SELECT * FROM governance_operations FOR UPDATE").fetchone()
    if not state or state["state"] != "quarantined" or state["restore_id"] is not None:
        raise GovernanceError("initial_target_not_fresh")
    enrolled = tx.execute("SELECT enrolled_at FROM governance_organization").fetchone()
    if not enrolled or enrolled["enrolled_at"] is None:
        raise GovernanceError("initial_enrollment_required")
    for table in sorted(TABLES - _ALLOWED):
        if tx.execute(
            sql.SQL("SELECT EXISTS(SELECT 1 FROM {}) AS present").format(sql.Identifier(table))
        ).fetchone()["present"]:
            raise GovernanceError("initial_target_not_fresh")
    unexpected = tx.execute(
        "SELECT EXISTS(SELECT 1 FROM governance_audit WHERE event_code NOT IN "
        "('organization.enrolled','operations.initial_prepared','operations.key_rotated') "
        "AND event_code NOT LIKE 'membership.%%') AS present"
    ).fetchone()["present"]
    if unexpected:
        raise GovernanceError("initial_target_not_fresh")
    released = tx.execute(
        "SELECT 1 FROM governance_initial_activations WHERE phase='released'"
    ).fetchone()
    if released:
        raise GovernanceError("initial_already_activated")
    return state


def _actors(tx, store, review):
    for member_id, revision, required in (
        (review.proposer_id, review.proposer_revision, "system_administrator"),
        (review.reviewer_id, review.reviewer_revision, "authority_reviewer"),
    ):
        row = tx.execute(
            "SELECT enabled,revision,roles FROM governance_members WHERE member_id=%s "
            "AND organization_id=%s FOR SHARE",
            (member_id, store.organization_id),
        ).fetchone()
        if (
            not row
            or not row["enabled"]
            or row["revision"] != revision
            or required not in row["roles"]
        ):
            raise GovernanceError("initial_authority_changed")
    now = tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    if not review.reviewed_at <= now < review.expires_at:
        raise GovernanceError("initial_review_expired")


def _runtime(tx, store, runtime_store, expected_role=None):
    if (
        not isinstance(runtime_store, Store)
        or runtime_store.organization_id != store.organization_id
    ):
        raise GovernanceError("initial_runtime_target_mismatch")
    # Metadata-only qualification must work while data transactions stay fenced.
    qualifier = Store(runtime_store._dsn, runtime_store.organization_id)
    source = tx.execute(
        "SELECT current_database() AS database,current_schema() AS schema,"
        "(SELECT oid FROM pg_database WHERE datname=current_database()) AS database_oid"
    ).fetchone()
    nonces = (secrets.randbits(63), secrets.randbits(63))
    for nonce in nonces:
        tx.execute("SELECT pg_advisory_xact_lock(%s)", (nonce,))
    with qualifier.transaction() as rt:
        identity = rt.execute(
            "SELECT current_database() AS database,current_schema() AS schema,"
            "(SELECT oid FROM pg_database WHERE datname=current_database()) AS database_oid,"
            "current_user AS role,(SELECT oid FROM pg_roles WHERE rolname=current_user) AS role_oid"
        ).fetchone()
        if any(identity[k] != source[k] for k in source) or (
            expected_role is not None and identity["role"] != expected_role
        ):
            raise GovernanceError("initial_runtime_target_mismatch")
        for nonce in nonces:
            if rt.execute("SELECT pg_try_advisory_xact_lock(%s) AS acquired", (nonce,)).fetchone()[
                "acquired"
            ]:
                raise GovernanceError("initial_runtime_target_mismatch")
        check_runtime_role(qualifier, tx=rt)
    return identity["role"], digest(identity)


def _scope(tx, runtime_fingerprint, key_proof, profile_digest, authority_digest):
    values = {}
    for name in sorted(_AUTHORITY | {"governance_organization", "governance_schema"}):
        value = hashlib.sha256()
        with tx.cursor(name="initial_" + name) as cursor:
            cursor.execute(
                sql.SQL("SELECT to_jsonb(t) AS row FROM {} t ORDER BY to_jsonb(t)::text").format(
                    sql.Identifier(name)
                )
            )
            for row in cursor:
                value.update(digest(row["row"]).encode())
        values[name] = value.hexdigest()
    return digest(
        {
            "authority": values,
            "runtime": runtime_fingerprint,
            "key": key_proof,
            "profile": profile_digest,
            "inputs": authority_digest,
        }
    )


def _journal(tx, activation_id, phase, evidence):
    tx.execute(
        "INSERT INTO governance_initial_journal(activation_id,ordinal,phase,evidence_digest) "
        "SELECT %s,COALESCE(max(ordinal),0)+1,%s,%s FROM governance_initial_journal WHERE activation_id=%s",
        (activation_id, phase, digest(evidence), activation_id),
    )


def review_context(store, *, runtime_store, profile, key_provider, checkpoint=None, authority=None):
    """Return an unapproved metadata template. References require external review."""
    profile_digest = _profile(profile)
    _authority(
        authority,
        store=store,
        runtime_store=runtime_store,
        profile=profile,
        key_provider=key_provider,
        checkpoint=checkpoint,
    )
    store.check_ready()
    with store.transaction() as tx:
        store.lock(tx)
        _operator(tx)
        _fresh(tx, store)
        role, runtime_fingerprint = _runtime(tx, store, runtime_store)
        database_fingerprint = _database_identity(tx)
        version, _proof = _key_proof(store, key_provider, uuid4())
        members = tx.execute(
            "SELECT member_id,revision,roles FROM governance_members WHERE organization_id=%s "
            "AND enabled ORDER BY member_id",
            (store.organization_id,),
        ).fetchall()
        current = tx.execute(
            "SELECT activation_id FROM governance_initial_activations WHERE phase='prepared'"
        ).fetchone()
    return {
        "review_template": {
            "activation_id": str(uuid4()),
            "organization_id": str(store.organization_id),
            "artifact": profile.artifact,
            "schema": profile.schema,
            "profile_digest": profile_digest,
            "public_origin": profile.public_origin,
            "key_version": version,
            "runtime_role": role,
            "database_identity": database_fingerprint,
            "runtime_identity": runtime_fingerprint,
            "input_authority": authority.review_binding_digest,
            "proposer_id": None,
            "proposer_revision": None,
            "reviewer_id": None,
            "reviewer_revision": None,
            "proposer_evidence_ref": None,
            "reviewer_evidence_ref": None,
            "decision": "pending_review",
            "reviewed_at": None,
            "expires_at": None,
            "supersedes": str(current["activation_id"]) if current else None,
        },
        "authority_candidates": [
            {"id": str(m["member_id"]), "revision": m["revision"], "roles": m["roles"]}
            for m in members
        ],
        "owner_acceptance": False,
        "legal_clearance": False,
    }


def activate_initial(
    store, request, *, runtime_store, profile, key_provider, checkpoint, authority=None
):
    """Prepare, witness and release one fresh enrolled organization."""
    try:
        review = ActivationReview.model_validate(request)
    except (ValidationError, TypeError, ValueError):
        raise GovernanceError("initial_review_invalid") from None
    if (
        review.organization_id != store.organization_id
        or not isinstance(checkpoint, CheckpointClient)
        or checkpoint.organization_id != store.organization_id
    ):
        raise GovernanceError("initial_review_scope_changed")
    profile_digest = _profile(profile, review)
    review_data = review.model_dump(mode="json", by_alias=True)
    review_digest = digest(review_data)
    authority_inputs = {
        "store": store,
        "runtime_store": runtime_store,
        "profile": profile,
        "key_provider": key_provider,
        "checkpoint": checkpoint,
        "review": review,
    }
    authority_digest = _authority(authority, **authority_inputs)
    if review.input_authority != authority.review_binding_digest:
        raise GovernanceError("initial_review_scope_changed")
    store.check_ready()
    with store.transaction() as tx:
        store.lock(tx)
        _operator(tx)
        if _database_identity(tx) != review.database_identity:
            raise GovernanceError("initial_review_scope_changed")
        existing = tx.execute(
            "SELECT * FROM governance_initial_activations WHERE activation_id=%s FOR UPDATE",
            (review.activation_id,),
        ).fetchone()
        if existing and existing["review_digest"] != review_digest:
            raise GovernanceError("initial_activation_conflict")
        if existing and existing["phase"] == "released":
            return _released_receipt(tx, review, existing)
        if existing and existing["phase"] != "prepared":
            raise GovernanceError("initial_activation_conflict")
        state = _fresh(tx, store)
        _actors(tx, store, review)
        version, key_proof = _key_proof(store, key_provider, review.activation_id)
        if version != review.key_version:
            raise GovernanceError("initial_key_changed")
        _role, runtime_fingerprint = _runtime(tx, store, runtime_store, review.runtime_role)
        if runtime_fingerprint != review.runtime_identity:
            raise GovernanceError("initial_review_scope_changed")
        verify_keys(store, key_provider, tx=tx)
        _authority(authority, **authority_inputs)
        if existing:
            _record_identity(tx, existing)
            if state["active_key_version"] != version or existing["key_proof"] != key_proof:
                raise GovernanceError("initial_key_changed")
            if existing["prepared_head"] != _head(tx):
                raise GovernanceError("initial_scope_changed")
            expected_scope = _scope(
                tx, runtime_fingerprint, key_proof, profile_digest, authority_digest
            )
            if expected_scope != existing["scope_digest"]:
                raise GovernanceError("initial_scope_changed")
        else:
            previous = tx.execute(
                "SELECT activation_id FROM governance_initial_activations WHERE phase='prepared' FOR UPDATE"
            ).fetchone()
            if (previous is None) != (review.supersedes is None) or (
                previous is not None and previous["activation_id"] != review.supersedes
            ):
                raise GovernanceError("initial_activation_conflict")
            if previous:
                tx.execute(
                    "UPDATE governance_initial_activations SET phase='superseded' WHERE activation_id=%s",
                    (review.supersedes,),
                )
                _journal(
                    tx, review.supersedes, "superseded", {"successor": str(review.activation_id)}
                )
            tx.execute(
                "UPDATE governance_operations SET active_key_version=%s WHERE singleton", (version,)
            )
            expected_scope = _scope(
                tx, runtime_fingerprint, key_proof, profile_digest, authority_digest
            )
            store.append_event(
                tx,
                event_code="operations.initial_prepared",
                actor_id=review.reviewer_id,
                target_id=review.activation_id,
                revision=1,
            )
            prepared_head = _head(tx)
            tx.execute(
                "INSERT INTO governance_initial_activations(activation_id,review,review_digest,key_proof,"
                "scope_digest,prepared_head) VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    review.activation_id,
                    Jsonb({"request": review_data, "database_identity": _database_identity(tx)}),
                    review_digest,
                    key_proof,
                    expected_scope,
                    Jsonb(prepared_head),
                ),
            )
            _journal(
                tx,
                review.activation_id,
                "prepared",
                {"review": review_digest, "head": prepared_head},
            )
    receipt = checkpoint.check(store, publish=True)
    _authority(authority, **authority_inputs)
    with store.transaction() as tx:
        store.lock(tx)
        _operator(tx)
        existing = tx.execute(
            "SELECT * FROM governance_initial_activations WHERE activation_id=%s FOR UPDATE",
            (review.activation_id,),
        ).fetchone()
        if not existing or existing["review_digest"] != review_digest:
            raise GovernanceError("initial_activation_conflict")
        if existing["phase"] == "released":
            return _released_receipt(tx, review, existing)
        if existing["phase"] != "prepared":
            raise GovernanceError("initial_activation_conflict")
        _record_identity(tx, existing)
        if _database_identity(tx) != review.database_identity:
            raise GovernanceError("initial_review_scope_changed")
        state = _fresh(tx, store)
        _actors(tx, store, review)
        _profile(profile, review)
        version, key_proof = _key_proof(store, key_provider, review.activation_id)
        if (
            version != review.key_version
            or state["active_key_version"] != version
            or key_proof != existing["key_proof"]
        ):
            raise GovernanceError("initial_key_changed")
        _role, runtime_fingerprint = _runtime(tx, store, runtime_store, review.runtime_role)
        if runtime_fingerprint != review.runtime_identity:
            raise GovernanceError("initial_review_scope_changed")
        verify_keys(store, key_provider, tx=tx)
        if (
            _scope(tx, runtime_fingerprint, key_proof, profile_digest, authority_digest)
            != existing["scope_digest"]
        ):
            raise GovernanceError("initial_scope_changed")
        head = _head(tx)
        if head != existing["prepared_head"] or any(receipt[k] != head[k] for k in head):
            raise GovernanceError("initial_witness_unverified")
        checkpoint.verify_chain({head["sequence"]: head["event_hash"]}, receipt)
        _authority(authority, **authority_inputs)
        tx.execute(
            "UPDATE governance_operations SET state='reconciled',reconciled_at=clock_timestamp(),control_digest=%s "
            "WHERE singleton AND state='quarantined' AND restore_id IS NULL",
            (digest({"initial": review_digest, "scope": existing["scope_digest"], "head": head}),),
        )
        tx.execute(
            "UPDATE governance_initial_activations SET phase='released',released_at=clock_timestamp() "
            "WHERE activation_id=%s",
            (review.activation_id,),
        )
        _journal(
            tx,
            review.activation_id,
            "released",
            {"receipt": receipt, "scope": existing["scope_digest"]},
        )
    runtime_store.production_operations_required = True
    runtime_store.runtime_key_version = key_provider.active_version
    return {
        "state": "reconciled",
        "activation_id": str(review.activation_id),
        "owner_acceptance": False,
        "legal_clearance": False,
    }

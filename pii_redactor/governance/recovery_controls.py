"""Verified source freeze, complete replay and witnessed single-serving cutover."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.types.json import Jsonb

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.operations import (
    ProductionProfile,
    artifact_identity,
    digest,
    schema_identity,
)
from pii_redactor.governance.runtime_roles import APPEND_ONLY, TABLES, check_runtime_role

MAX_ROWS = 1_000_000
LOCAL = frozenset(
    {
        "governance_schema",
        "governance_operations",
        "governance_restore_sessions",
        "governance_restore_journal",
        "governance_initial_activations",
        "governance_initial_journal",
    }
)
ORDER = (
    "governance_organization",
    "governance_members",
    "governance_grants",
    "governance_commands",
    "governance_activities",
    "governance_notices",
    "governance_subjects",
    "governance_subject_links",
    "enterprise_login_states",
    "enterprise_staff_sessions",
    "enterprise_subject_login_states",
    "enterprise_subject_sessions",
    "governance_consent_purposes",
    "governance_consent_presentations",
    "governance_consent_events",
    "governance_consent_offline_cases",
    "governance_consent_current",
    "governance_subject_commands",
    "governance_consent_propagation",
    "governance_collections",
    "governance_managed_documents",
    "governance_document_versions",
    "governance_protected_evidence",
    "governance_execution_instructions",
    "governance_execution_tasks",
    "governance_execution_outcomes",
    "governance_collection_snapshots",
    "governance_holds",
    "governance_retention_policies",
    "governance_retention_triggers",
    "governance_retention_due",
    "governance_retention_instruction_links",
    "governance_retention_copies",
    "governance_rights_cases",
    "governance_rights_history",
    "governance_rights_manual",
    "governance_rights_subject_commands",
    "governance_rights_instruction_bindings",
    "governance_rights_previews",
    "governance_rights_deliveries",
    "governance_organization_controls",
    "governance_control_history",
    "governance_processing_bindings",
    "governance_processing_history",
    "governance_processing_previews",
    "governance_instruction_controls",
    "governance_outbox",
)
SCOPES = frozenset(
    {"authority", "registry", "managed", "consent", "holds", "outbox", "rights", "organization"}
)
EPHEMERAL = frozenset({"enterprise_login_states", "enterprise_subject_login_states"})
SESSIONS = frozenset({"enterprise_staff_sessions", "enterprise_subject_sessions"})


@dataclass(frozen=True)
class Scope:
    name: str


def control_handlers():
    """Only first-party complete-scope handlers may authorize this operator path."""
    return {name: Scope(name) for name in SCOPES}


def audit_head(tx):
    row = tx.execute(
        "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
    ).fetchone()
    if not row:
        raise GovernanceError("recovery_lineage_missing")
    return row


def database_identity(tx):
    row = tx.execute("SELECT system_identifier::text AS system FROM pg_control_system()").fetchone()
    db = tx.execute(
        "SELECT oid,datname FROM pg_database WHERE datname=current_database()"
    ).fetchone()
    return digest({**row, **db})


def _operator(tx):
    tx.execute("SET LOCAL timezone='UTC'")
    row = tx.execute(
        "SELECT has_table_privilege(current_user,'governance_operations','UPDATE') AS allowed"
    ).fetchone()
    if not row or not row["allowed"]:
        raise GovernanceError("recovery_operator_required")


def _journal(tx, restore_id, phase, evidence):
    tx.execute(
        "INSERT INTO governance_restore_journal(restore_id,ordinal,phase,evidence_digest) "
        "SELECT %s,COALESCE(max(ordinal),0)+1,%s,%s FROM governance_restore_journal WHERE restore_id=%s",
        (restore_id, phase, digest(evidence), restore_id),
    )


def record_restore(store, manifest):
    """Record authenticated provenance without forking the canonical audit."""
    expected = manifest.get("snapshot_head")
    if not isinstance(expected, dict) or set(expected) != {"sequence", "event_hash"}:
        raise GovernanceError("backup_lineage_missing")
    with store.transaction() as tx:
        store.lock(tx)
        _operator(tx)
        if audit_head(tx) != expected:
            raise GovernanceError("recovery_audit_fork")
        restore_id = UUID(manifest["archive_id"])
        tx.execute(
            "INSERT INTO governance_restore_sessions(restore_id,cutover_id,manifest,manifest_digest) VALUES (%s,%s,%s,%s)",
            (restore_id, uuid4(), Jsonb(manifest), digest(manifest)),
        )
        tx.execute(
            "UPDATE governance_operations SET state='quarantined',restore_id=%s,reconciled_at=NULL,control_digest=NULL",
            (restore_id,),
        )
        for name in SESSIONS:
            tx.execute(sql.SQL("UPDATE {} SET revoked=true").format(sql.Identifier(name)))
        for name in EPHEMERAL:
            tx.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(name)))
        _journal(tx, restore_id, "restored", manifest)


def restore_function_acls(tx):
    """A no-ACL archive must not restore PostgreSQL's PUBLIC execute default."""
    schema = tx.execute("SELECT current_schema() AS name").fetchone()["name"]
    for name in (
        "governance_runtime_guard",
        "governance_operations_fence",
        "governance_restore_operator_only",
    ):
        tx.execute(
            sql.SQL("REVOKE ALL ON FUNCTION {}.{}() FROM PUBLIC").format(
                sql.Identifier(schema), sql.Identifier(name)
            )
        )


def _record(tx):
    row = tx.execute(
        "SELECT r.* FROM governance_restore_sessions r JOIN governance_operations o ON o.restore_id=r.restore_id WHERE o.singleton FOR UPDATE OF r,o"
    ).fetchone()
    if not row or row["manifest_digest"] != digest(row["manifest"]):
        raise GovernanceError("recovery_lineage_missing")
    manifest = row["manifest"]
    if manifest.get("artifact") != artifact_identity() or manifest.get("schema") != {
        str(k): v for k, v in schema_identity().items()
    }:
        raise GovernanceError("backup_compatibility_failure")
    return row


def _prefix(src, dst, expected):
    if audit_head(dst) != expected:
        raise GovernanceError("recovery_audit_fork")
    anchor = src.execute(
        "SELECT event_hash FROM governance_audit WHERE sequence=%s", (expected["sequence"],)
    ).fetchone()
    if not anchor or anchor["event_hash"] != expected["event_hash"]:
        raise GovernanceError("recovery_audit_fork")


def _schema(tx):
    names = {
        r["tablename"]
        for r in tx.execute("SELECT tablename FROM pg_tables WHERE schemaname=current_schema()")
    }
    if names != TABLES or set(ORDER) | LOCAL | {"governance_audit"} != names:
        raise GovernanceError("recovery_scope_unqualified")


def _columns(tx, name):
    cols = [
        r["attname"]
        for r in tx.execute(
            "SELECT a.attname FROM pg_index i JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,n) ON true "
            "JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum "
            "WHERE i.indrelid=to_regclass(%s) AND i.indisprimary ORDER BY k.n",
            (name,),
        )
    ]
    if not cols:
        raise GovernanceError("recovery_scope_unqualified")
    return cols


def _where(name, keys):
    return sql.SQL("({})=(SELECT {} FROM jsonb_populate_record(NULL::{},%s))").format(
        sql.SQL(",").join(map(sql.Identifier, keys)),
        sql.SQL(",").join(map(sql.Identifier, keys)),
        sql.Identifier(name),
    )


def _read(tx, name):
    keys = _columns(tx, name)
    with tx.cursor(name="recovery_" + name) as cursor:
        cursor.execute(
            sql.SQL("SELECT to_jsonb(t) AS row FROM {} t ORDER BY {}").format(
                sql.Identifier(name), sql.SQL(",").join(map(sql.Identifier, keys))
            )
        )
        for index, item in enumerate(cursor, 1):
            if index > MAX_ROWS:
                raise GovernanceError("recovery_scope_limit")
            yield item["row"]


def _control_digest(tx):
    result = {}
    for name in ORDER:
        h = hashlib.sha256()
        for row in _read(tx, name):
            h.update(digest(row).encode())
        result[name] = h.hexdigest()
    return digest(result)


def _copy_table(src, dst, name, *, audit=False):
    keys = _columns(src, name)
    condition = _where(name, keys)
    h = hashlib.sha256()
    source_count = 0
    if name in {"governance_processing_bindings", "governance_retention_policies"}:
        # Retire predecessors before UUID order can activate an existing successor.
        for row in _read(src, name):
            if row["state"] != "active":
                dst.execute(
                    sql.SQL("UPDATE {} SET state=%s WHERE ").format(sql.Identifier(name))
                    + condition
                    + sql.SQL(" AND state='active'"),
                    (row["state"], Jsonb(row)),
                )
    # Copy existing mutable rows before inserting missing FK dependants.
    for insert in (False, True):
        for row in _read(src, name):
            if insert:
                h.update(digest(row).encode())
                source_count += 1
            prior = dst.execute(
                sql.SQL("SELECT to_jsonb(t) AS row FROM {} t WHERE ").format(sql.Identifier(name))
                + condition,
                (Jsonb(row),),
            ).fetchone()
            if prior:
                if prior["row"] == row:
                    continue
                if audit or name in APPEND_ONLY or name == "governance_organization":
                    raise GovernanceError("recovery_immutable_conflict")
                if insert:
                    continue
                columns = [c for c in row if c not in keys]
                update = (
                    sql.SQL(
                        "UPDATE {} SET ({})=(SELECT {} FROM jsonb_populate_record(NULL::{},%s)) WHERE "
                    ).format(
                        sql.Identifier(name),
                        sql.SQL(",").join(map(sql.Identifier, columns)),
                        sql.SQL(",").join(map(sql.Identifier, columns)),
                        sql.Identifier(name),
                    )
                    + condition
                )
                if (
                    name == "governance_notices"
                    and row["state"] == "published"
                    and prior["row"]["state"] != "published"
                ):
                    dst.execute(update, (Jsonb({**row, "state": "draft"}), Jsonb(row)))
                dst.execute(update, (Jsonb(row), Jsonb(row)))
            elif insert:
                dst.execute(
                    sql.SQL("INSERT INTO {} SELECT (jsonb_populate_record(NULL::{},%s)).*").format(
                        sql.Identifier(name), sql.Identifier(name)
                    ),
                    (Jsonb(row),),
                )
    target_count = dst.execute(
        sql.SQL("SELECT count(*) AS n FROM {}").format(sql.Identifier(name))
    ).fetchone()["n"]
    if target_count != source_count:
        raise GovernanceError("recovery_unexpected_target_records")
    return h.hexdigest()


def _verify_primary(tx):
    from pii_redactor.governance.execution import instruction_digest

    for row in tx.execute(
        "SELECT i.*,to_jsonb(o) AS outcome FROM governance_execution_instructions i JOIN governance_execution_outcomes o USING(instruction_id)"
    ):
        proof = row["outcome"]
        if (
            instruction_digest(row) != row["instruction_digest"]
            or proof["instruction_digest"] != row["instruction_digest"]
            or proof["document_id"] != str(row["document_id"])
            or proof["result_revision"] != row["target_revision"] + 1
            or proof["result_version"] != row["target_version"] + (row["action"] == "correct")
            or (row["action"] == "suppress" and proof["result_state"] != "suppressed")
            or (
                row["action"] == "restrict"
                and proof["result_state"] not in {"restricted", "suppressed"}
            )
        ):
            raise GovernanceError("recovery_primary_unverified")
        version = tx.execute(
            "SELECT ciphertext_digest FROM governance_document_versions WHERE document_id=%s AND version=%s",
            (row["document_id"], proof["result_version"]),
        ).fetchone()
        if not version or version["ciphertext_digest"] != proof["ciphertext_digest"]:
            raise GovernanceError("recovery_primary_unverified")
    bad = tx.execute(
        "SELECT 1 FROM governance_managed_documents d LEFT JOIN governance_execution_outcomes o ON d.last_instruction_id=o.instruction_id "
        "WHERE d.last_instruction_id IS NOT NULL AND (o.instruction_id IS NULL OR d.revision<>o.result_revision OR d.current_version<>o.result_version OR d.state<>o.result_state) LIMIT 1"
    ).fetchone()
    if bad:
        raise GovernanceError("recovery_primary_unverified")


def _revoke(tx):
    for name in SESSIONS:
        tx.execute(sql.SQL("UPDATE {} SET revoked=true").format(sql.Identifier(name)))
    for name in EPHEMERAL:
        tx.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(name)))
    tx.execute(
        "UPDATE governance_consent_presentations SET consumed_at=COALESCE(consumed_at,clock_timestamp())"
    )
    tx.execute(
        "UPDATE governance_execution_instructions i SET state='failed',revision=revision+1 WHERE state IN ('proposed','pending','running','unknown') AND NOT EXISTS(SELECT 1 FROM governance_execution_outcomes o WHERE o.instruction_id=i.instruction_id)"
    )
    tx.execute(
        "UPDATE governance_execution_instructions i SET state='verified',revision=revision+1 WHERE state<>'verified' AND EXISTS(SELECT 1 FROM governance_execution_outcomes o WHERE o.instruction_id=i.instruction_id)"
    )
    tx.execute(
        "UPDATE governance_execution_tasks t SET state=CASE WHEN EXISTS(SELECT 1 FROM governance_execution_outcomes o WHERE o.instruction_id=t.instruction_id) THEN 'verified' ELSE 'failed' END,worker_id=NULL,lease_token=NULL,lease_until=NULL,last_error='restore_reapproval_required',updated_at=clock_timestamp() WHERE state IN ('pending','running','unknown')"
    )
    tx.execute("UPDATE governance_outbox SET state='failed' WHERE state IN ('pending','claimed')")
    tx.execute(
        "UPDATE governance_rights_deliveries SET state='revoked',revision=revision+1 WHERE state IN ('issued','downloaded')"
    )
    rows = tx.execute(
        "UPDATE governance_rights_cases SET state='verified',revision=revision+1,approved_by=NULL,approver_revision=NULL,approval_expires_at=NULL,review_ref=NULL WHERE state IN ('planned','approved','partial') RETURNING case_id,revision,plan_version"
    ).fetchall()
    for row in rows:
        tx.execute(
            "INSERT INTO governance_rights_history(history_id,case_id,revision,kind,data) VALUES (%s,%s,%s,'recovery_authority_revoked',%s)",
            (
                uuid4(),
                row["case_id"],
                row["revision"],
                Jsonb(
                    {
                        "state": "verified",
                        "plan_version": row["plan_version"],
                        "reason": "restore_reapproval_required",
                    }
                ),
            ),
        )


def _key_check(store, tx, provider, *, historical_version=None):
    from pii_redactor.governance.evidence import ProtectedStorage
    from pii_redactor.governance.key_operations import verify_keys

    version = tx.execute("SELECT active_key_version FROM governance_operations").fetchone()[
        "active_key_version"
    ]
    expected = (
        historical_version
        if historical_version is not None
        else getattr(provider, "active_version", None)
    )
    if provider is None or expected != version:
        raise GovernanceError("recovery_key_version_mismatch")
    if historical_version is not None:
        ProtectedStorage(provider).require_key(store.organization_id, None, historical_version)
    verify_keys(store, provider, tx=tx)
    return version


def _rotation_provenance(store, tx, manifest, provider):
    """Follow only authenticated, ordered version transitions after this archive."""
    import re

    from pii_redactor.governance.evidence import ProtectedStorage

    def version(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value):
            raise GovernanceError("recovery_key_rotation_unverified")
        return value

    current = tx.execute("SELECT active_key_version FROM governance_operations").fetchone()[
        "active_key_version"
    ]
    tracked = version(manifest.get("active_key_version"))
    snapshot = manifest["snapshot_head"]
    anchor = tx.execute(
        "SELECT event_hash FROM governance_audit WHERE sequence=%s", (snapshot["sequence"],)
    ).fetchone()
    if not anchor or anchor["event_hash"] != snapshot["event_hash"]:
        raise GovernanceError("recovery_audit_fork")
    protection = ProtectedStorage(provider)
    protection.require_key(store.organization_id, None, tracked)
    retained_versions = {tracked}
    expected_sequence = snapshot["sequence"] + 1
    with tx.cursor(name="recovery_key_provenance") as cursor:
        cursor.execute(
            "SELECT sequence,event_code,details FROM governance_audit WHERE sequence>%s ORDER BY sequence",
            (snapshot["sequence"],),
        )
        for count, event in enumerate(cursor, 1):
            if count > MAX_ROWS or event["sequence"] != expected_sequence:
                raise GovernanceError("recovery_key_rotation_unverified")
            expected_sequence += 1
            if event["event_code"] != "operations.key_rotated":
                continue
            details = event["details"]
            if not isinstance(details, dict) or set(details) != {"from_version", "to_version"}:
                raise GovernanceError("recovery_key_rotation_unverified")
            before, after = version(details["from_version"]), version(details["to_version"])
            if before != tracked or after == before:
                raise GovernanceError("recovery_key_rotation_unverified")
            retained_versions.add(after)
            tracked = after
    if (
        tracked != current
        or current != getattr(provider, "active_version", None)
        or expected_sequence != audit_head(tx)["sequence"] + 1
    ):
        raise GovernanceError("recovery_key_rotation_unverified")
    for required in retained_versions:
        protection.require_key(store.organization_id, None, required)
    if tx.execute(
        "SELECT 1 FROM governance_collections WHERE key_version<>%s LIMIT 1", (current,)
    ).fetchone():
        raise GovernanceError("recovery_key_rotation_unverified")
    return current


def _target_key_check(target, tx, provider, record):
    historical = (
        record["manifest"].get("active_key_version") if record["phase"] != "released" else None
    )
    return _key_check(target, tx, provider, historical_version=historical)


def _source_unchanged(source, src, record, provider):
    state = src.execute(
        "SELECT state,restore_id,active_key_version FROM governance_operations FOR SHARE"
    ).fetchone()
    freeze = src.execute(
        "SELECT event_hash,event_code,target_id,details FROM governance_audit WHERE sequence=%s",
        (record["source_head"]["sequence"],),
    ).fetchone()
    captured_key = freeze["details"].get("active_key_version") if freeze else None
    if (
        not state
        or state["state"] != "quarantined"
        or state["restore_id"] != record["cutover_id"]
        or not freeze
        or freeze["event_hash"] != record["source_head"]["event_hash"]
        or freeze["event_code"] != "operations.cutover_source_frozen"
        or freeze["target_id"] != record["cutover_id"]
        or captured_key is None
        or state["active_key_version"] != captured_key
        or getattr(provider, "active_version", None) != captured_key
        or audit_head(src) != record["source_head"]
        or database_identity(src) != record["source_fingerprint"]
        or _control_digest(src) != record["source_control_digest"]
    ):
        raise GovernanceError("recovery_source_changed")
    _rotation_provenance(source, src, record["manifest"], provider)


def reconcile(target, source, *, handlers, checkpoint, runtime_store, key_provider, profile):
    if set(handlers) != SCOPES or any(
        not isinstance(handlers[k], Scope) or handlers[k].name != k for k in SCOPES
    ):
        raise GovernanceError("recovery_handler_missing")
    if (
        source is None
        or checkpoint is None
        or source.organization_id != target.organization_id
        or runtime_store is None
    ):
        raise GovernanceError("recovery_source_unavailable")
    if not isinstance(profile, ProductionProfile):
        raise GovernanceError("recovery_profile_required")
    profile = ProductionProfile.parse(
        {"profile": "single_organization_production_v1", **asdict(profile)}
    )
    if profile.artifact != artifact_identity() or profile.schema != digest(schema_identity()):
        raise GovernanceError("production_profile_invalid")
    target.check_ready()
    source.check_ready()
    source.verify_audit()
    target.verify_audit()
    with source.transaction() as src, target.transaction() as dst:
        source.lock(src)
        target.lock(dst)
        _operator(src)
        _operator(dst)
        if database_identity(src) == database_identity(dst):
            raise GovernanceError("recovery_source_not_independent")
        _schema(src)
        _schema(dst)
        record = _record(dst)
        if record["phase"] == "restored":
            _prefix(src, dst, record["manifest"]["snapshot_head"])
        _key_check(source, src, key_provider)
        _rotation_provenance(source, src, record["manifest"], key_provider)
        _target_key_check(target, dst, key_provider, record)
    # Never write the target release before the source fence commits successfully.
    if record["phase"] == "restored":
        checkpoint.check(source)
        with source.transaction() as src:
            source.lock(src)
            _operator(src)
            state = src.execute(
                "SELECT state,restore_id FROM governance_operations FOR UPDATE"
            ).fetchone()
            _key_check(source, src, key_provider)
            frozen_key = _rotation_provenance(source, src, record["manifest"], key_provider)
            if state["restore_id"] == record["cutover_id"]:
                frozen = audit_head(src)
                event = src.execute(
                    "SELECT event_code,target_id,details FROM governance_audit WHERE sequence=%s",
                    (frozen["sequence"],),
                ).fetchone()
                if (
                    event["event_code"] != "operations.cutover_source_frozen"
                    or event["target_id"] != record["cutover_id"]
                    or event["details"].get("active_key_version") != frozen_key
                ):
                    raise GovernanceError("recovery_source_changed")
                source_controls = event["details"].get("control_digest")
                if source_controls != _control_digest(src):
                    raise GovernanceError("recovery_source_changed")
            else:
                src.execute(
                    "UPDATE governance_operations SET state='quarantined',restore_id=%s,reconciled_at=NULL,control_digest=NULL",
                    (record["cutover_id"],),
                )
                source_controls = _control_digest(src)
                source.append_event(
                    src,
                    event_code="operations.cutover_source_frozen",
                    target_id=record["cutover_id"],
                    details={"control_digest": source_controls, "active_key_version": frozen_key},
                )
                frozen = audit_head(src)
            source_id = database_identity(src)
        receipt = checkpoint.check(source, publish=True)
        if (receipt["sequence"], receipt["event_hash"]) != (
            frozen["sequence"],
            frozen["event_hash"],
        ):
            raise GovernanceError("recovery_source_changed")
        with target.transaction() as dst:
            target.lock(dst)
            record = _record(dst)
            dst.execute(
                "UPDATE governance_restore_sessions SET phase='source_frozen',source_fingerprint=%s,source_head=%s,source_control_digest=%s,profile_digest=%s WHERE restore_id=%s",
                (
                    source_id,
                    Jsonb(frozen),
                    source_controls,
                    digest(asdict(profile)),
                    record["restore_id"],
                ),
            )
            _journal(
                dst, record["restore_id"], "source_frozen", {"head": frozen, "source": source_id}
            )
    with target.transaction() as dst:
        record = _record(dst)
    if record["profile_digest"] != digest(asdict(profile)):
        raise GovernanceError("production_profile_invalid")
    if record["phase"] == "source_frozen":
        with source.transaction() as src, target.transaction() as dst:
            source.lock(src)
            target.lock(dst)
            _operator(src)
            _operator(dst)
            _source_unchanged(source, src, record, key_provider)
            _prefix(src, dst, record["manifest"]["snapshot_head"])
            _key_check(source, src, key_provider)
            proofs = {"governance_audit": _copy_table(src, dst, "governance_audit", audit=True)}
            for name in ORDER:
                proofs[name] = (
                    "revoked_without_replay" if name in EPHEMERAL else _copy_table(src, dst, name)
                )
            _verify_primary(dst)
            _target_key_check(target, dst, key_provider, record)
            _revoke(dst)
            actual_controls = _control_digest(dst)
            target.append_event(
                dst,
                event_code="operations.cutover_prepared",
                target_id=record["cutover_id"],
                details={
                    "control_digest": actual_controls,
                    "source_control_digest": digest(proofs),
                },
            )
            prepared = audit_head(dst)
            dst.execute(
                "UPDATE governance_restore_sessions SET phase='replayed',control_digest=%s,target_head=%s WHERE restore_id=%s",
                (actual_controls, Jsonb(prepared), record["restore_id"]),
            )
            _journal(
                dst,
                record["restore_id"],
                "replayed",
                {"controls": actual_controls, "source_controls": digest(proofs), "head": prepared},
            )
    # External publication is complete while the target still cannot serve.
    target.verify_audit()
    receipt = checkpoint.check(target, publish=True)
    with runtime_store.transaction() as runtime_tx:
        if runtime_identity(runtime_tx) != runtime_identity_for(target):
            raise GovernanceError("runtime_role_wrong_database")
        check_runtime_role(runtime_store, tx=runtime_tx)
    with source.transaction() as src, target.transaction() as dst:
        source.lock(src)
        target.lock(dst)
        _operator(src)
        _operator(dst)
        record = _record(dst)
        _source_unchanged(source, src, record, key_provider)
        if record["phase"] == "released":
            anchor = dst.execute(
                "SELECT event_hash FROM governance_audit WHERE sequence=%s",
                (record["target_head"]["sequence"],),
            ).fetchone()
            state = dst.execute("SELECT state,control_digest FROM governance_operations").fetchone()
            if (
                not anchor
                or anchor["event_hash"] != record["target_head"]["event_hash"]
                or state["state"] != "reconciled"
                or state["control_digest"] != record["control_digest"]
            ):
                raise GovernanceError("recovery_checkpoint_changed")
            return {
                "state": "reconciled",
                "source_frozen": True,
                "control_digest": record["control_digest"],
                "cutover_id": str(record["cutover_id"]),
            }
        if record["target_head"] != audit_head(dst) or record["target_head"] != {
            "sequence": receipt["sequence"],
            "event_hash": receipt["event_hash"],
        }:
            raise GovernanceError("recovery_checkpoint_changed")
        if _control_digest(dst) != record["control_digest"]:
            raise GovernanceError("recovery_controls_changed")
        _target_key_check(target, dst, key_provider, record)
        if record["phase"] != "released":
            dst.execute(
                "UPDATE governance_operations SET state='reconciled',reconciled_at=clock_timestamp(),control_digest=%s,active_key_version=%s",
                (record["control_digest"], key_provider.active_version),
            )
            dst.execute(
                "UPDATE governance_restore_sessions SET phase='released' WHERE restore_id=%s",
                (record["restore_id"],),
            )
            _journal(
                dst,
                record["restore_id"],
                "released",
                {"checkpoint": record["target_head"], "controls": record["control_digest"]},
            )
    return {
        "state": "reconciled",
        "source_frozen": True,
        "control_digest": record["control_digest"],
        "cutover_id": str(record["cutover_id"]),
    }


def runtime_identity(tx):
    return tx.execute(
        "SELECT current_database() AS database,inet_server_addr()::text AS host,inet_server_port() AS port"
    ).fetchone()


def runtime_identity_for(store):
    with store.transaction() as tx:
        return runtime_identity(tx)

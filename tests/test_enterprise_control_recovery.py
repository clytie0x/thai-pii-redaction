"""Actual independent databases and witness prove controlled recovery cutover."""

import json
import os
import secrets
from pathlib import Path
from uuid import UUID, uuid4

import pytest

psycopg = pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from psycopg import sql
from psycopg.conninfo import make_conninfo

from pii_redactor.governance.backup import backup_database, restore_database, validate_archive
from pii_redactor.governance.evidence import SyntheticKeyProvider
from pii_redactor.governance.operations import (
    ProductionProfile,
    artifact_identity,
    digest,
    schema_identity,
)
from pii_redactor.governance.store import Store
from tests import governance_helpers
from tests.test_audit_checkpoint import client
from tests.test_audit_checkpoint import witness as independent_witness

witness = independent_witness


@pytest.fixture(autouse=True)
def fixed_artifact_for_subsystem_drill(monkeypatch):
    # Other integration workers can edit assets during this isolated DB drill.
    frozen = artifact_identity()
    monkeypatch.setattr("pii_redactor.governance.backup.artifact_identity", lambda: frozen)
    monkeypatch.setattr(
        "pii_redactor.governance.recovery_controls.artifact_identity", lambda: frozen
    )
    monkeypatch.setitem(globals(), "artifact_identity", lambda: frozen)


@pytest.fixture
def recovery_source():
    config = json.loads(Path(os.environ["AIGUARD_TEST_DB_FILE"]).read_text())
    names, roles = [], []
    name = "aig_restore_" + uuid4().hex
    names.append(name)
    with psycopg.connect(config["dsn"], autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    context = governance_helpers.context.__wrapped__(make_conninfo(config["dsn"], dbname=name))
    context.admin_dsn, context.created_databases, context.created_roles = (
        config["dsn"],
        names,
        roles,
    )
    context.keys = SyntheticKeyProvider({(context.store.organization_id, None, "v1"): b"k" * 32})
    context.keys.active_version = "v1"
    with context.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET state='reconciled',active_key_version='v1'")
    yield context
    with psycopg.connect(config["dsn"], autocommit=True) as admin:
        for database in reversed(names):
            assert database.startswith("aig_restore_") and len(database) == 44
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database))
            )
        for role in roles:
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def profile():
    names = (
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
    )
    return ProductionProfile.parse(
        {
            "profile": "single_organization_production_v1",
            "artifact": artifact_identity(),
            "schema": digest(schema_identity()),
            "public_origin": "https://synthetic.example.test",
            "evidence": dict.fromkeys(names, "synthetic-local-test-only"),
            "checkpoint_max_age": 300,
            "checkpoint_max_events": 100,
        }
    )


def archive(context, checkpoint):
    checkpoint.check(context.store, publish=True)
    filename = Path(os.environ["AIGUARD_OPERATIONS_PRIVATE_DIR"]) / (uuid4().hex + ".aigdb")
    key = os.urandom(32)
    backup_database(
        context.store, os.environ["AIGUARD_OPERATIONS_PG_BIN"], filename, key, checkpoint=checkpoint
    )
    return filename, key


def restored(context, item):
    name = "aig_restore_" + uuid4().hex
    context.created_databases.append(name)
    restore_database(
        context.admin_dsn,
        os.environ["AIGUARD_OPERATIONS_PG_BIN"],
        *item,
        name=name,
        confirmation=name,
    )
    return Store(make_conninfo(context.admin_dsn, dbname=name), context.store.organization_id)


def runtime(context, target):
    from pii_redactor.governance.runtime_roles import grant_statements

    name = "restore_runtime_" + uuid4().hex
    password = secrets.token_urlsafe(32)
    context.created_roles.append(name)
    with target.transaction() as tx:
        tx.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(name), sql.Literal(password)
            )
        )
        tx.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(tx.info.dbname), sql.Identifier(name)
            )
        )
        for statement in grant_statements("public", name):
            tx.execute(statement)
    return Store(make_conninfo(target._dsn, user=name, password=password), target.organization_id)


def reconcile(context, target, checkpoint, **kwargs):
    from pii_redactor.governance.operations import Operations, control_handlers

    return Operations(target).reconcile(
        context.store,
        handlers=control_handlers(),
        checkpoint=checkpoint,
        runtime_store=runtime(context, target),
        key_provider=context.keys,
        profile=profile(),
        **kwargs,
    )


@pytest.mark.parametrize("kind", ["processing", "retention"])
def test_replay_retires_existing_active_predecessor_before_lower_uuid_successor(
    recovery_source, witness, monkeypatch, kind
):
    from tests import test_governance_processing_controls as processing
    from tests.test_governance_retention import policy_input, retention_context

    c = retention_context.__wrapped__(recovery_source)
    old_id = UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
    new_id = UUID("00000000-0000-4000-8000-000000000001")
    if kind == "processing":
        import pii_redactor.governance.processing_controls as module

        with c.store.transaction() as tx:
            c.activity = tx.execute(
                "SELECT * FROM governance_activities WHERE activity_id=%s",
                (c.bucket["activity_id"],),
            ).fetchone()
        rows, _law = processing.controls(c)
        with monkeypatch.context() as patch:
            patch.setattr(module, "uuid4", lambda: old_id)
            service, old = processing.enabled(c, rows)
        with monkeypatch.context() as patch:
            patch.setattr(module, "uuid4", lambda: new_id)
            successor = service.create(c.a, uuid4(), processing.request(c, rows))
        successor = service.submit(c.a, uuid4(), successor["id"], successor["revision"])
        service.preview(c.b, successor["id"], successor["revision"])
        successor = service.review(
            c.b, uuid4(), successor["id"], successor["revision"], "approve", uuid4()
        )
        table, column = "governance_processing_bindings", "binding_id"

        def activate():
            return service.activate(c.b, uuid4(), successor["id"], successor["revision"])
    else:
        import pii_redactor.governance.retention as module

        def propose(identifier):
            with monkeypatch.context() as patch:
                patch.setattr(module, "uuid4", lambda: identifier)
                return c.retention.propose_policy(
                    c.a,
                    uuid4(),
                    policy_input(collection_id=c.bucket["id"], purpose_version=c.purpose),
                )

        old = propose(old_id)
        old = c.retention.review_policy(
            c.b, uuid4(), old["id"], old["revision"], "approve", uuid4()
        )
        successor = propose(new_id)
        table, column = "governance_retention_policies", "policy_id"

        def activate():
            return c.retention.review_policy(
                c.b, uuid4(), successor["id"], successor["revision"], "approve", uuid4()
            )

    checkpoint = client(witness, c.store.organization_id)
    item = archive(c, checkpoint)
    activate()
    target = restored(c, item)
    assert reconcile(c, target, checkpoint)["state"] == "reconciled"
    with target.transaction() as tx:
        rows = tx.execute(
            sql.SQL("SELECT {},state FROM {} ORDER BY {}").format(
                sql.Identifier(column), sql.Identifier(table), sql.Identifier(column)
            )
        ).fetchall()
        assert rows == [
            {column: new_id, "state": "active"},
            {column: old_id, "state": "superseded"},
        ]


def test_archive_binds_actual_snapshot_and_restore_does_not_fork_audit(recovery_source, witness):
    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    before = c.store.verify_audit()
    item = archive(c, checkpoint)
    manifest = validate_archive(*item)
    assert manifest["snapshot_head"] == {
        "sequence": before["events"],
        "event_hash": before["tail_hash"],
    }
    target = restored(c, item)
    assert target.verify_audit() == before


def test_current_authority_replay_and_witnessed_cutover(recovery_source, witness):
    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    item = archive(c, checkpoint)
    with c.store.transaction() as tx:
        c.store.lock(tx)
        tx.execute(
            "UPDATE governance_members SET enabled=false,revision=revision+1 WHERE member_id=%s",
            (c.ids[1],),
        )
        c.store.append_event(tx, event_code="synthetic.authority_revoked", target_id=c.ids[1])
    target = restored(c, item)
    result = reconcile(c, target, checkpoint)
    assert result["state"] == "reconciled" and result["source_frozen"] is True
    with target.transaction() as tx:
        assert (
            tx.execute(
                "SELECT enabled FROM governance_members WHERE member_id=%s", (c.ids[1],)
            ).fetchone()["enabled"]
            is False
        )
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "reconciled"
        )
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )
    assert checkpoint.check(target)["event_hash"] == target.verify_audit()["tail_hash"]


def test_postbackup_consent_registry_and_organization_changes_are_replayed(
    recovery_source, witness
):
    from app.enterprise.capabilities import managed_services
    from pii_redactor.governance.policy_register import Policies
    from pii_redactor.governance.registry import Registry
    from tests import test_governance_consent as consent
    from tests import test_governance_integration as integration
    from tests import test_governance_subjects as subjects
    from tests.test_governance_organization_controls import policy
    from tests.test_governance_registry import activity

    c = consent.consent_context.__wrapped__(subjects.subject_context.__wrapped__(recovery_source))
    consent.command(c, "grant")
    c.collection, c.evidence, c.execution, c.worker = managed_services(c.store, c.keys)
    with c.store.transaction() as tx:
        c.activity = tx.execute(
            "SELECT * FROM governance_activities WHERE activity_id=%s",
            (c.notice["data"]["activity_id"],),
        ).fetchone()
    _bucket, document, instruction = integration.queued_document(c)
    draft = Registry(c.store).create_activity(c.a, uuid4(), activity())
    checkpoint = client(witness, c.store.organization_id)
    item = archive(c, checkpoint)
    consent.command(c, "withdraw", expected=1)
    consent.command(c, "grant", expected=2)
    _other, other_notice = integration.reviewed_activity(c)
    c.consent.present(c.actor, other_notice["id"])
    Registry(c.store).update_activity(
        c.a,
        uuid4(),
        draft["id"],
        draft["revision"],
        activity(purpose="Synthetic changed authority"),
    )
    control = Policies(c.store).create(c.a, uuid4(), policy())
    target = restored(c, item)
    reconcile(c, target, checkpoint)
    with target.transaction() as tx:
        assert (
            tx.execute(
                "SELECT revision FROM governance_consent_current WHERE subject_id=%s AND purpose_version=%s",
                (c.subject["subject_id"], c.notice["id"]),
            ).fetchone()["revision"]
            == 3
        )
        assert (
            tx.execute(
                "SELECT state FROM governance_execution_instructions WHERE instruction_id=%s",
                (instruction["id"],),
            ).fetchone()["state"]
            == "failed"
        )
        assert (
            tx.execute(
                "SELECT state FROM governance_execution_tasks WHERE instruction_id=%s",
                (instruction["id"],),
            ).fetchone()["state"]
            == "failed"
        )
        assert (
            tx.execute(
                "SELECT state FROM governance_activities WHERE activity_id=%s",
                (draft["id"],),
            ).fetchone()["state"]
            == "draft"
        )
        assert (
            tx.execute(
                "SELECT count(*) AS n FROM governance_consent_purposes WHERE purpose_version=%s",
                (other_notice["id"],),
            ).fetchone()["n"]
            == 1
        )
        assert (
            tx.execute(
                "SELECT count(*) AS n FROM governance_control_history WHERE control_id=%s",
                (control["id"],),
            ).fetchone()["n"]
            == 1
        )
        assert not tx.execute(
            "SELECT 1 FROM enterprise_subject_sessions WHERE NOT revoked"
        ).fetchone()
        assert (
            tx.execute(
                "SELECT state FROM governance_managed_documents WHERE document_id=%s",
                (document["id"],),
            ).fetchone()["state"]
            == "active"
        )


def test_postbackup_primary_suppression_hold_and_outcome_are_reconciled(recovery_source, witness):
    from datetime import UTC, datetime, timedelta

    from pii_redactor.governance.execution import InstructionInput
    from pii_redactor.governance.holds import Holds
    from pii_redactor.governance.outbox import Outbox
    from tests.test_governance_holds import hold_input
    from tests.test_governance_rights import rights_context

    c = rights_context.__wrapped__(recovery_source)
    checkpoint = client(witness, c.store.organization_id)
    item = archive(c, checkpoint)
    ins = c.execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_revision=1,
            expected_version=1,
            action="suppress",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    ins = c.execution.approve(c.b, uuid4(), ins["id"], ins["revision"])
    claim = Outbox(c.store).claim("synthetic-recovery")
    assert c.execution.execute("synthetic-recovery", claim)["primary_verified"]
    held = Holds(c.store).request(c.a, uuid4(), hold_input(c.bucket, {**c.document, "revision": 2}))
    target = restored(c, item)
    reconcile(c, target, checkpoint)
    with target.transaction() as tx:
        assert (
            tx.execute(
                "SELECT state FROM governance_managed_documents WHERE document_id=%s",
                (c.document["id"],),
            ).fetchone()["state"]
            == "suppressed"
        )
        assert (
            tx.execute(
                "SELECT count(*) AS n FROM governance_execution_outcomes WHERE instruction_id=%s",
                (ins["id"],),
            ).fetchone()["n"]
            == 1
        )
        assert (
            tx.execute(
                "SELECT state FROM governance_execution_instructions WHERE instruction_id=%s",
                (ins["id"],),
            ).fetchone()["state"]
            == "verified"
        )
        with pytest.raises(Exception, match="hold_effective"):
            Holds(target).fence(
                tx, collection_id=c.bucket["id"], document_id=c.document["id"], action="put"
            )
        assert tx.execute(
            "SELECT state FROM governance_holds WHERE hold_id=%s", (held["id"],)
        ).fetchone()


@pytest.mark.parametrize("action", ["withdraw", "reopen", "revoke"])
def test_current_case_and_export_revocations_keep_receipt_history(recovery_source, witness, action):
    from app.enterprise.subject_auth import SubjectIdentity, SubjectSessions
    from pii_redactor.governance.delivery import Delivery
    from pii_redactor.governance.rights import Rights
    from tests.test_governance_rights import rights_context
    from tests.test_rights_delivery import issued

    c = rights_context.__wrapped__(recovery_source)
    case, delivery = issued(c)
    content = c.delivery.consume(c.actor, delivery["id"])
    c.delivery.acknowledge(c.actor, delivery["id"], content["revision"], content["receipt_token"])
    if action == "reopen":
        case = c.rights.close(c.b, uuid4(), case["id"], case["revision"], uuid4())
    checkpoint = client(witness, c.store.organization_id)
    item = archive(c, checkpoint)
    if action == "revoke":
        c.delivery.revoke(c.a, uuid4(), case["id"], case["revision"], uuid4())
    else:
        c.rights.transition(c.a, uuid4(), case["id"], case["revision"], uuid4(), action=action)
    target = restored(c, item)
    reconcile(c, target, checkpoint)
    sessions = SubjectSessions(target, issuer=c.a.issuer, client_id="aiguard-subject")
    fresh = sessions.issue(SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject"))
    actor = sessions.resolve(fresh.cookie)
    collection = type(c.collection)(target, c.keys)
    evidence = type(c.evidence)(target, c.keys, collection=collection)
    execution = type(c.execution)(target, collection, evidence)
    with pytest.raises(Exception, match="delivery_revoked|case_authority_revoked"):
        Delivery(Rights(target, collection, evidence, execution)).consume(actor, delivery["id"])
    with target.transaction() as tx:
        row = tx.execute(
            "SELECT state,receipt_ref FROM governance_rights_deliveries WHERE delivery_id=%s",
            (delivery["id"],),
        ).fetchone()
        assert row["state"] == "revoked" and row["receipt_ref"] is not None
        assert (
            tx.execute(
                "SELECT count(*) AS n FROM governance_rights_history WHERE case_id=%s",
                (case["id"],),
            ).fetchone()["n"]
            >= 4
        )


def test_audit_fork_is_rejected_without_rewriting_history(recovery_source, witness):
    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))
    with target.transaction() as tx:
        target.append_event(tx, event_code="synthetic.fork")
    before = target.verify_audit()
    with pytest.raises(Exception, match="recovery_audit_fork"):
        reconcile(c, target, checkpoint)
    assert target.verify_audit() == before
    with target.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )


def test_source_commit_failure_cannot_release_destination(recovery_source, witness, monkeypatch):
    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))
    original = c.store.append_event

    def kill(tx, **kwargs):
        result = original(tx, **kwargs)
        if kwargs["event_code"] == "operations.cutover_source_frozen":
            tx.execute("SELECT pg_terminate_backend(pg_backend_pid())")
        return result

    monkeypatch.setattr(c.store, "append_event", kill)
    with pytest.raises(Exception, match="storage_failure"):
        reconcile(c, target, checkpoint)
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "reconciled"
        )
    with target.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )


@pytest.mark.parametrize("stage", ["source", "target"])
def test_checkpoint_failure_retains_quarantine_and_retry_is_safe(recovery_source, witness, stage):
    from pii_redactor.governance.errors import GovernanceError

    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))

    class Failed:
        def check(self, store, *, publish=False):
            if publish and (
                (stage == "source" and store is c.store) or (stage == "target" and store is target)
            ):
                raise GovernanceError("checkpoint_unavailable")
            return checkpoint.check(store, publish=publish)

    with pytest.raises(Exception, match="checkpoint_unavailable"):
        reconcile(c, target, Failed())
    for store in (c.store, target):
        with store.transaction() as tx:
            assert (
                tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
                == "quarantined"
            )
    assert reconcile(c, target, checkpoint)["state"] == "reconciled"


def test_immutable_conflict_remains_quarantined(recovery_source, witness):
    from pii_redactor.governance.registry import Registry
    from tests.test_governance_registry import activity

    c = recovery_source
    Registry(c.store).create_activity(c.a, uuid4(), activity())
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))
    with target.transaction() as tx:
        tx.execute("UPDATE governance_commands SET response='{}'::jsonb")
    with pytest.raises(Exception, match="recovery_immutable_conflict"):
        reconcile(c, target, checkpoint)
    with target.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )


@pytest.mark.parametrize("mismatch", ["key", "provider_version", "source_version"])
def test_wrong_current_key_cannot_release_archive(recovery_source, witness, mismatch):
    from tests.test_governance_rights import rights_context

    c = rights_context.__wrapped__(recovery_source)
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))
    if mismatch == "key":
        c.keys = SyntheticKeyProvider({(c.store.organization_id, None, "v1"): b"z" * 32})
        c.keys.active_version = "v1"
    elif mismatch == "provider_version":
        c.keys.active_version = "v2"
    else:
        with c.store.transaction() as tx:
            tx.execute("UPDATE governance_operations SET active_key_version='v2'")
    code = "protected_content_invalid" if mismatch == "key" else "recovery_key_version_mismatch"
    with pytest.raises(Exception, match=code):
        reconcile(c, target, checkpoint)
    with target.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )


@pytest.mark.parametrize("stage", ["source", "target"])
def test_unlogged_control_change_is_detected_before_release(recovery_source, witness, stage):
    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))

    class Altered:
        def check(self, store, *, publish=False):
            receipt = checkpoint.check(store, publish=publish)
            selected = c.store if stage == "source" else target
            if publish and store is selected:
                with selected.transaction() as tx:
                    tx.execute(
                        "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s",
                        (c.ids[1],),
                    )
            return receipt

    with pytest.raises(Exception, match="recovery_source_changed|recovery_controls_changed"):
        reconcile(c, target, Altered())
    with target.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )


def test_released_cutover_retry_does_not_replay_old_controls(recovery_source, witness):
    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))
    first = reconcile(c, target, checkpoint)
    with target.transaction() as tx:
        target.lock(tx)
        tx.execute(
            "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s", (c.ids[1],)
        )
        target.append_event(tx, event_code="synthetic.target_authority_changed", target_id=c.ids[1])
    second = reconcile(c, target, checkpoint)
    assert first == second
    with target.transaction() as tx:
        assert (
            tx.execute(
                "SELECT revision FROM governance_members WHERE member_id=%s", (c.ids[1],)
            ).fetchone()["revision"]
            == 2
        )


def audited_rotation(context, version):
    from pii_redactor.governance.collections import Collection
    from pii_redactor.governance.key_operations import activate_rotation

    key = {"v2": b"n" * 32, "v3": b"p" * 32}[version]
    newer = SyntheticKeyProvider(
        {**context.keys._keys, (context.store.organization_id, None, version): key}
    )
    newer.active_version = version
    activate_rotation(context.store, context.keys, newer)
    context.keys = newer
    writer = Collection(context.store, newer, key_version=version)
    return writer.put(context.a, uuid4(), context.bucket["id"], "Synthetic current-key document")


@pytest.mark.parametrize("versions", [("v2",), ("v2", "v3")])
def test_historical_archive_recovers_through_actual_audited_key_rotations(
    recovery_source, witness, versions
):
    import hashlib

    from pii_redactor.governance.collections import Collection
    from tests.test_governance_rights import rights_context

    c = rights_context.__wrapped__(recovery_source)
    with c.store.transaction() as tx:
        original = tx.execute(
            "SELECT ciphertext_digest FROM governance_document_versions WHERE document_id=%s AND version=1",
            (c.document["id"],),
        ).fetchone()["ciphertext_digest"]
    before = hashlib.sha256(
        c.collection.read_version(c.a, c.bucket["id"], c.document["id"], 1)["content"].encode()
    ).hexdigest()
    checkpoint = client(witness, c.store.organization_id)
    item = archive(c, checkpoint)
    documents = [audited_rotation(c, version) for version in versions]
    target = restored(c, item)
    assert reconcile(c, target, checkpoint)["state"] == "reconciled"
    reader = Collection(target, c.keys, key_version=versions[-1])
    assert (
        hashlib.sha256(
            reader.read_version(c.a, c.bucket["id"], c.document["id"], 1)["content"].encode()
        ).hexdigest()
        == before
    )
    with target.transaction() as tx:
        assert (
            tx.execute("SELECT active_key_version FROM governance_operations").fetchone()[
                "active_key_version"
            ]
            == versions[-1]
        )
        assert (
            tx.execute(
                "SELECT ciphertext_digest FROM governance_document_versions WHERE document_id=%s AND version=1",
                (c.document["id"],),
            ).fetchone()["ciphertext_digest"]
            == original
        )
        for document, version in zip(documents, versions, strict=True):
            assert (
                tx.execute(
                    "SELECT key_version FROM governance_document_versions WHERE document_id=%s AND version=1",
                    (document["id"],),
                ).fetchone()["key_version"]
                == version
            )
        freeze = tx.execute(
            "SELECT details FROM governance_audit WHERE event_code='operations.cutover_source_frozen' ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        assert freeze["details"]["active_key_version"] == versions[-1]
    assert all((c.store.organization_id, None, v) in c.keys._keys for v in ("v1", *versions))


@pytest.mark.parametrize(
    "invalid", ["missing", "unlabelled", "misordered", "forged_target", "duplicate", "forged_state"]
)
def test_unverifiable_rotation_labels_cannot_qualify_a_historical_archive(
    recovery_source, witness, monkeypatch, invalid
):
    from tests.test_governance_rights import rights_context

    c = rights_context.__wrapped__(recovery_source)
    checkpoint = client(witness, c.store.organization_id)
    item = archive(c, checkpoint)
    original = c.store.append_event

    def emit(tx, **kwargs):
        if kwargs["event_code"] == "operations.key_rotated":
            if invalid == "missing":
                return uuid4()
            if invalid == "unlabelled":
                kwargs["details"] = {}
            elif invalid == "misordered":
                kwargs["details"] = {"from_version": "v0", "to_version": "v2"}
            elif invalid == "forged_target":
                kwargs["details"] = {"from_version": "v1", "to_version": "v3"}
        return original(tx, **kwargs)

    monkeypatch.setattr(c.store, "append_event", emit)
    if invalid == "forged_state":
        c.keys = SyntheticKeyProvider(
            {**c.keys._keys, (c.store.organization_id, None, "v2"): b"n" * 32}
        )
        c.keys.active_version = "v2"
        with c.store.transaction() as tx:
            tx.execute("UPDATE governance_operations SET active_key_version='v2'")
            original(
                tx,
                event_code="operations.key_rotated",
                details={"from_version": "v1", "to_version": "v2"},
            )
    else:
        audited_rotation(c, "v2")
    if invalid == "duplicate":
        with c.store.transaction() as tx:
            original(
                tx,
                event_code="operations.key_rotated",
                details={"from_version": "v1", "to_version": "v2"},
            )
    target = restored(c, item)
    with pytest.raises(Exception, match="recovery_key_rotation_unverified"):
        reconcile(c, target, checkpoint)
    with target.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )


def test_rotation_recovery_requires_retained_historical_key(recovery_source, witness):
    from tests.test_governance_rights import rights_context

    c = rights_context.__wrapped__(recovery_source)
    checkpoint = client(witness, c.store.organization_id)
    item = archive(c, checkpoint)
    audited_rotation(c, "v2")
    target = restored(c, item)
    c.keys = SyntheticKeyProvider({(c.store.organization_id, None, "v2"): b"n" * 32})
    c.keys.active_version = "v2"
    with pytest.raises(Exception, match="key_version_unavailable"):
        reconcile(c, target, checkpoint)


def test_source_key_version_is_rechecked_after_target_witness(recovery_source, witness):
    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))

    class ChangedKey:
        def check(self, store, *, publish=False):
            receipt = checkpoint.check(store, publish=publish)
            if publish and store is target:
                with c.store.transaction() as tx:
                    tx.execute("UPDATE governance_operations SET active_key_version='v2'")
            return receipt

    with pytest.raises(Exception, match="recovery_source_changed"):
        reconcile(c, target, ChangedKey())
    with target.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )


def test_restored_open_plan_needs_fresh_review_before_new_export(recovery_source, witness):
    from datetime import UTC, datetime, timedelta

    from pii_redactor.governance.delivery import Delivery
    from pii_redactor.governance.rights import Rights
    from tests.test_governance_rights import approved, rights_context

    c = rights_context.__wrapped__(recovery_source)
    row = approved(c)
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))
    reconcile(c, target, checkpoint)
    collection = type(c.collection)(target, c.keys)
    evidence = type(c.evidence)(target, c.keys, collection=collection)
    execution = type(c.execution)(target, collection, evidence)
    with target.transaction() as tx:
        restored_case = tx.execute(
            "SELECT revision,state FROM governance_rights_cases WHERE case_id=%s", (row["id"],)
        ).fetchone()
    assert restored_case["state"] == "verified"
    with pytest.raises(Exception, match="case_authority_revoked"):
        Delivery(Rights(target, collection, evidence, execution)).issue(
            c.a,
            uuid4(),
            row["id"],
            restored_case["revision"],
            row["plan_version"],
            datetime.now(UTC) + timedelta(hours=1),
        )


def test_waiting_runtime_source_writer_cannot_commit_after_freeze(
    recovery_source, witness, monkeypatch
):
    import time
    from concurrent.futures import ThreadPoolExecutor

    from pii_redactor.governance.errors import GovernanceError

    c = recovery_source
    checkpoint = client(witness, c.store.organization_id)
    target = restored(c, archive(c, checkpoint))
    writer = runtime(c, c.store)
    label = "synthetic-cutover-writer-" + uuid4().hex
    writer._dsn = make_conninfo(writer._dsn, application_name=label)
    writer.production_operations_required = True
    writer.runtime_key_version = "v1"
    original = c.store.append_event
    future = []

    def pending_write():
        try:
            with writer.transaction() as tx:
                tx.execute(
                    "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s",
                    (c.ids[1],),
                )
        except GovernanceError as error:
            return error.code
        return "unexpected_commit"

    with ThreadPoolExecutor(max_workers=1) as pool:

        def paused(tx, **kwargs):
            result = original(tx, **kwargs)
            if kwargs["event_code"] == "operations.cutover_source_frozen":
                future.append(pool.submit(pending_write))
                deadline = time.monotonic() + 3
                waiting = False
                with psycopg.connect(c.admin_dsn, autocommit=True) as observer:
                    while time.monotonic() < deadline:
                        found = observer.execute(
                            "SELECT 1 FROM pg_stat_activity WHERE application_name=%s AND wait_event_type='Lock'",
                            (label,),
                        ).fetchone()
                        if found:
                            waiting = True
                            break
                        time.sleep(0.01)
                assert waiting, "runtime source writer must actually wait at the held fence"
            return result

        monkeypatch.setattr(c.store, "append_event", paused)
        assert reconcile(c, target, checkpoint)["state"] == "reconciled"
        assert future[0].result(timeout=10) == "storage_failure"
    with c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT revision FROM governance_members WHERE member_id=%s", (c.ids[1],)
            ).fetchone()["revision"]
            == 1
        )

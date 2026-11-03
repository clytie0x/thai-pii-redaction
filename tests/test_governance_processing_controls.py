"""Synthetic exact-control activation on real PostgreSQL, not legal acceptance."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.processing_controls import ProcessingControls, ProcessingInput
from tests import test_governance_integration as production
from tests.test_governance_organization_controls import activate, common
from tests.test_governance_organization_domains import binding, source

database = production.database
context = production.context
subject_context = production.subject_context
consent_context = production.consent_context
integrated = production.integrated


def controls(c):
    from pii_redactor.governance.policy_register import CONTROL_KEYS, LegalControls, Policies

    law = activate(Policies(c.store), c, source())
    rows = [
        activate(
            LegalControls(c.store),
            c,
            common(
                control_key=key,
                applicability="reviewed_not_applicable",
                rationale_ref=str(uuid4()),
                source=binding(law),
                dependencies=[binding(law)],
            ),
        )
        for key in CONTROL_KEYS
    ]
    return rows, law


def request(c, rows):
    return ProcessingInput(
        activity_id=c.activity["activity_id"],
        activity_revision=c.activity["revision"],
        controls=[binding(row) for row in rows],
        evidence_ref=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )


def enabled(c, rows):
    service = ProcessingControls(c.store)
    row = service.create(c.a, uuid4(), request(c, rows))
    row = service.submit(c.a, uuid4(), row["id"], row["revision"])
    service.preview(c.b, row["id"], row["revision"])
    row = service.review(c.b, uuid4(), row["id"], row["revision"], "approve", uuid4())
    return service, service.activate(c.b, uuid4(), row["id"], row["revision"])


def production_mode(c):
    # Synthetic operational prerequisite; this is not M10/real-role acceptance.
    with c.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET state='reconciled',active_key_version='v1'")
    c.store.runtime_key_version = "v1"
    c.store.production_operations_required = True


def test_production_composition_requires_current_reviewed_controls(integrated):
    c = integrated
    production.consent_fixtures.command(c, "grant")
    production_mode(c)
    with pytest.raises(GovernanceError, match="processing_controls_required"):
        production.create_collection(c)


def test_all_eight_reviewed_decisions_allow_actual_collection_and_queue(integrated):
    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, _law = controls(c)
    service, row = enabled(c, rows)
    production_mode(c)
    bucket, document, instruction = production.queued_document(c)
    snapshot = c.execution.get(c.b, instruction["id"])["processing_controls"]
    assert snapshot["id"] == row["id"] and len(snapshot["controls"]) == 8
    assert service.get(c.b, row["id"])["usable"]
    assert c.collection.read_version(c.a, bucket["id"], document["id"], 1)["content"]


def test_missing_decision_and_unpreviewed_or_self_review_fail(integrated):
    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, _law = controls(c)
    service = ProcessingControls(c.store)
    row = service.create(c.a, uuid4(), request(c, rows[:-1]))
    row = service.submit(c.a, uuid4(), row["id"], row["revision"])
    with pytest.raises(GovernanceError, match="processing_controls_incomplete"):
        service.preview(c.b, row["id"], row["revision"])
    complete = service.create(c.a, uuid4(), request(c, rows))
    complete = service.submit(c.a, uuid4(), complete["id"], complete["revision"])
    with pytest.raises(GovernanceError, match="processing_preview_required"):
        service.review(c.b, uuid4(), complete["id"], complete["revision"], "approve", uuid4())
    with pytest.raises(GovernanceError):
        service.review(c.a, uuid4(), complete["id"], complete["revision"], "approve", uuid4())


def test_rebinding_terminally_cancels_old_queue_and_requires_new_instruction(integrated):
    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, _law = controls(c)
    service, row = enabled(c, rows)
    production_mode(c)
    bucket, document, instruction = production.queued_document(c)
    changed = service.replace(c.a, uuid4(), row["id"], row["revision"], request(c, rows))
    state = production.queued_state(c, instruction["id"])
    assert state["state"] == state["task_state"] == "failed" and state["lease_cleared"]
    assert state["last_error"] == "processing_authority_changed"
    changed = service.submit(c.a, uuid4(), changed["id"], changed["revision"])
    service.preview(c.b, changed["id"], changed["revision"])
    changed = service.review(c.b, uuid4(), changed["id"], changed["revision"], "approve", uuid4())
    service.activate(c.b, uuid4(), changed["id"], changed["revision"])
    assert c.worker.run_once("synthetic-old-processing")["state"] == "idle"
    fresh = production.independently_approved(c, bucket, document)
    assert fresh["id"] != instruction["id"]
    assert c.worker.run_once("synthetic-fresh-processing")["primary_verified"]


def test_source_policy_change_cancels_queue_but_preserves_all_immutable_outcomes(integrated):
    from pii_redactor.governance.policy_register import Policies

    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, law = controls(c)
    enabled(c, rows)
    production_mode(c)
    _bucket, _doc, committed = production.queued_document(c)
    assert c.worker.run_once("synthetic-committed-processing")["primary_verified"]
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_execution_instructions SET state='unknown' WHERE instruction_id=%s",
            (committed["id"],),
        )
        tx.execute(
            "UPDATE governance_execution_tasks SET state='unknown' WHERE instruction_id=%s",
            (committed["id"],),
        )
    bucket, doc, pending = production.queued_document(c)
    Policies(c.store).replace(
        c.a, uuid4(), law["id"], law["revision"], source(version="synthetic-revised-source")
    )
    assert production.queued_state(c, pending["id"])["state"] == "failed"
    assert production.queued_state(c, committed["id"])["state"] == "unknown"
    with pytest.raises(GovernanceError):
        c.collection.read_version(c.a, bucket["id"], doc["id"], 1)
    assert c.worker.run_once("synthetic-stale-processing")["state"] == "idle"


def test_control_and_queue_invalidation_roll_back_with_failed_audit(integrated, monkeypatch):
    from pii_redactor.governance.policy_register import Policies

    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, law = controls(c)
    service, row = enabled(c, rows)
    production_mode(c)
    _bucket, _doc, pending = production.queued_document(c)
    original = c.store.append_event

    def refuse(tx, **values):
        if values.get("event_code") == "processing.authority_changed":
            raise RuntimeError("synthetic audit failure")
        return original(tx, **values)

    monkeypatch.setattr(c.store, "append_event", refuse)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        Policies(c.store).replace(c.a, uuid4(), law["id"], law["revision"], source())
    assert production.queued_state(c, pending["id"])["state"] == "pending"
    assert Policies(c.store).get(c.b, law["id"])["revision"] == law["revision"]
    assert service.get(c.b, row["id"])["usable"]


def test_nonconsent_processing_keeps_its_basis_but_requires_current_controls(integrated):
    from pii_redactor.governance.collections import Collection, CollectionInput
    from pii_redactor.governance.policy_register import Policies

    c = integrated
    production.consent_fixtures.command(c, "grant")
    other, _notice = production.reviewed_activity(c, basis="contract")
    c.activity = other
    rows, law = controls(c)
    enabled(c, rows)
    production_mode(c)
    bucket = c.collection.create(
        c.a,
        uuid4(),
        CollectionInput(
            activity_id=other["activity_id"], expected_activity_revision=other["revision"]
        ),
    )
    doc = c.collection.put(c.a, uuid4(), bucket["id"], "Synthetic non-consent document")
    production.consent_fixtures.command(c, "withdraw", expected=1)
    assert not bucket["consent_bound"]
    assert c.collection.read_version(c.a, bucket["id"], doc["id"], 1)["content"]
    direct = Collection(c.store, c.collection.protection.key_provider)
    assert direct.read_version(c.a, bucket["id"], doc["id"], 1)["content"]
    Policies(c.store).replace(c.a, uuid4(), law["id"], law["revision"], source())
    for collection in (c.collection, direct):
        with pytest.raises(GovernanceError):
            collection.read_version(c.a, bucket["id"], doc["id"], 1)


def test_policy_change_serializes_before_claim_and_primary_execution(integrated, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from pii_redactor.governance.policy_register import Policies

    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, law = controls(c)
    enabled(c, rows)
    production_mode(c)
    _bucket, doc, pending = production.queued_document(c)
    entered, release, worker_entered = Event(), Event(), Event()
    original = c.store.append_event

    def pause(tx, **values):
        if values.get("event_code") == "processing.authority_changed":
            entered.set()
            assert release.wait(5)
        return original(tx, **values)

    monkeypatch.setattr(c.store, "append_event", pause)

    def worker():
        worker_entered.set()
        return c.worker.run_once("synthetic-raced-processing")

    with ThreadPoolExecutor(max_workers=2) as pool:
        changing = pool.submit(
            Policies(c.store).replace, c.a, uuid4(), law["id"], law["revision"], source()
        )
        assert entered.wait(5)
        running = pool.submit(worker)
        assert worker_entered.wait(5)
        release.set()
        changing.result()
        assert running.result()["state"] == "idle"
    assert production.queued_state(c, pending["id"])["state"] == "failed"
    assert production.primary(c, doc["id"])["revision"] == 1


def test_completed_action_is_not_relabelled_prevented_by_later_control_change(
    integrated, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from pii_redactor.governance.policy_register import Policies

    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, law = controls(c)
    enabled(c, rows)
    production_mode(c)
    _bucket, doc, pending = production.queued_document(c)
    entered, release, change_entered = Event(), Event(), Event()
    original = c.store.append_event

    def pause(tx, **values):
        if values.get("event_code") == "execution.primary_verified":
            entered.set()
            assert release.wait(5)
        return original(tx, **values)

    monkeypatch.setattr(c.store, "append_event", pause)

    def change():
        change_entered.set()
        return Policies(c.store).replace(c.a, uuid4(), law["id"], law["revision"], source())

    with ThreadPoolExecutor(max_workers=2) as pool:
        running = pool.submit(c.worker.run_once, "synthetic-first-processing")
        assert entered.wait(5)
        changing = pool.submit(change)
        assert change_entered.wait(5)
        release.set()
        assert running.result()["primary_verified"]
        changing.result()
    assert production.queued_state(c, pending["id"])["state"] == "verified"
    assert production.primary(c, doc["id"])["state"] == "suppressed"


def test_proposer_with_both_roles_still_cannot_review_own_binding(integrated):
    from psycopg.types.json import Jsonb

    c = integrated
    production.consent_fixtures.command(c, "grant")
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles=roles||%s::jsonb WHERE member_id=%s",
            (Jsonb(["privacy_reviewer"]), c.ids[0]),
        )
    rows, _law = controls(c)
    service = ProcessingControls(c.store)
    row = service.create(c.a, uuid4(), request(c, rows))
    row = service.submit(c.a, uuid4(), row["id"], row["revision"])
    with pytest.raises(GovernanceError, match="separation_required"):
        service.preview(c.a, row["id"], row["revision"])
    with pytest.raises(GovernanceError, match="separation_required"):
        service.review(c.a, uuid4(), row["id"], row["revision"], "approve", uuid4())


def test_binding_expiry_is_checked_before_queue_execution(integrated):
    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, _law = controls(c)
    service = ProcessingControls(c.store)
    value = request(c, rows).model_copy(
        update={"expires_at": datetime.now(UTC) + timedelta(seconds=5)}
    )
    row = service.create(c.a, uuid4(), value)
    row = service.submit(c.a, uuid4(), row["id"], row["revision"])
    service.preview(c.b, row["id"], row["revision"])
    row = service.review(c.b, uuid4(), row["id"], row["revision"], "approve", uuid4())
    service.activate(c.b, uuid4(), row["id"], row["revision"])
    production_mode(c)
    bucket, doc, pending = production.queued_document(c)
    with c.store.transaction() as tx:
        tx.execute(
            "SELECT pg_sleep(GREATEST(0,EXTRACT(EPOCH FROM %s::timestamptz-clock_timestamp()))+0.1)",
            (value.expires_at,),
        )
    with pytest.raises(GovernanceError, match="processing_controls_expired"):
        c.collection.read_version(c.a, bucket["id"], doc["id"], 1)
    assert not c.worker.run_once("synthetic-expired-processing")["primary_verified"]
    assert production.queued_state(c, pending["id"])["state"] == "failed"


def test_instruction_control_snapshot_is_immutable_and_scoped(integrated):
    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, _law = controls(c)
    service, row = enabled(c, rows)
    production_mode(c)
    _bucket, _doc, instruction = production.queued_document(c)
    with pytest.raises(GovernanceError, match="storage_failure"):
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_instruction_controls SET binding_digest=%s WHERE instruction_id=%s",
                ("0" * 64, instruction["id"]),
            )
    assert c.execution.get(c.b, instruction["id"])["processing_controls"]["id"] == row["id"]
    with pytest.raises(GovernanceError, match="forbidden"):
        service.list(c.a, "other")
    page = service.list(c.a, "operations", limit=1)
    assert len(page["items"]) == 1
    assert service.history(c.b, row["id"])["historical_only"]


def test_new_source_control_supersession_revokes_old_bound_queue(integrated):
    from pii_redactor.governance.policy_register import Policies

    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, law = controls(c)
    enabled(c, rows)
    production_mode(c)
    _bucket, _doc, pending = production.queued_document(c)
    value = source(version="synthetic-successor-source")
    value["supersedes"] = binding(law)
    activate(Policies(c.store), c, value)
    assert production.queued_state(c, pending["id"])["state"] == "failed"
    assert c.worker.run_once("synthetic-superseded-processing")["state"] == "idle"


def test_mutable_source_metadata_must_match_its_immutable_review_history(integrated):
    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, law = controls(c)
    enabled(c, rows)
    production_mode(c)
    bucket, doc, pending = production.queued_document(c)
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_organization_controls SET data=jsonb_set(data,'{instrument,sha256}',%s::jsonb) WHERE control_id=%s",
            ('"' + "f" * 64 + '"', law["id"]),
        )
    with pytest.raises(GovernanceError, match="processing_controls_integrity"):
        c.collection.read_version(c.a, bucket["id"], doc["id"], 1)
    assert not c.worker.run_once("synthetic-source-tamper")["primary_verified"]
    assert production.queued_state(c, pending["id"])["state"] == "failed"

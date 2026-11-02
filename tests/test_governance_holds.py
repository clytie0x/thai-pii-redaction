"""Synthetic preservation fences and exact hold/release authority."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.holds import HoldInput, Holds


@pytest.mark.parametrize("state", ["effective", "release_pending", "post_action_review"])
def test_committed_hold_fence_blocks_every_mutable_action_without_database(state):
    row = {"state": state, "hold_id": uuid4()}
    tx = SimpleNamespace(execute=lambda *_args: SimpleNamespace(fetchone=lambda: row))
    holds = Holds(SimpleNamespace(organization_id=uuid4(), lock=lambda _tx: None))
    for action in [
        "correct",
        "suppress",
        "restrict",
        "put",
        "approve",
        "execute",
        "reconcile",
        "restore_release",
    ]:
        with pytest.raises(GovernanceError, match="^hold_effective$"):
            holds.fence(tx, collection_id=uuid4(), document_id=uuid4(), action=action)


def test_hold_never_infers_expiry_release_and_unknown_actions_fail_closed_without_database():
    holds = Holds(SimpleNamespace(organization_id=uuid4(), lock=lambda _tx: None))
    with pytest.raises(GovernanceError, match="^invalid_request$"):
        holds.fence(None, collection_id=uuid4(), action="physical_erase")


from tests import governance_helpers as fixtures
from tests import test_governance_collection as collection_fixtures

database = fixtures.database
context = fixtures.context


@pytest.fixture
def managed(context):
    return (context, *collection_fixtures.runtime(context))


def hold_input(collection, document):
    from datetime import UTC, datetime, timedelta

    return HoldInput(
        collection_id=collection["id"],
        document_id=document["id"],
        expected_revision=document["revision"],
        expected_version=document["version"],
        reason="legal_preservation",
        evidence_ref=uuid4(),
        review_due_at=datetime.now(UTC) + timedelta(days=7),
    )


def test_database_hold_is_immediate_but_release_needs_distinct_review(managed):
    c, _collection, _evidence, _execution, bucket, document = managed
    holds = Holds(c.store)
    held = holds.request(c.a, uuid4(), hold_input(bucket, document))
    assert held["state"] == "effective" and held["blocks_future_actions"]
    assert held["prior_action_prevented"] is False
    with c.store.transaction() as tx:
        with pytest.raises(GovernanceError, match="^hold_effective$"):
            holds.fence(
                tx, collection_id=bucket["id"], document_id=document["id"], action="suppress"
            )
    pending = holds.propose_release(c.a, uuid4(), held["id"], 1, uuid4())
    with pytest.raises(GovernanceError, match="^separation_required$"):
        holds.release(c.a, uuid4(), held["id"], pending["revision"], uuid4())
    released = holds.release(c.b, uuid4(), held["id"], pending["revision"], uuid4())
    assert released["state"] == "released"
    with c.store.transaction() as tx:
        assert (
            holds.fence(
                tx, collection_id=bucket["id"], document_id=document["id"], action="suppress"
            )["held"]
            is False
        )


def test_database_overdue_hold_stays_effective_and_cross_department_is_denied(managed):
    c, _collection, _evidence, _execution, bucket, document = managed
    holds = Holds(c.store)
    held = holds.request(c.a, uuid4(), hold_input(bucket, document))
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_holds SET review_due_at=clock_timestamp()-interval '1 day' WHERE hold_id=%s",
            (held["id"],),
        )
    assert holds.list(c.a, bucket["id"])["items"][0]["review_overdue"] is True
    with c.store.transaction() as tx:
        with pytest.raises(GovernanceError, match="^hold_effective$"):
            holds.fence(
                tx, collection_id=bucket["id"], document_id=document["id"], action="restore_release"
            )
    with pytest.raises(GovernanceError, match="forbidden|record_unavailable"):
        holds.list(c.c, bucket["id"])


def prepare_action(c, execution, bucket, document):
    from datetime import UTC, datetime, timedelta

    from pii_redactor.governance.execution import InstructionInput
    from pii_redactor.governance.outbox import Outbox

    instruction = execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=bucket["id"],
            document_id=document["id"],
            expected_revision=document["revision"],
            expected_version=document["version"],
            action="suppress",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        ),
    )
    execution.approve(c.b, uuid4(), instruction["id"], 1)
    return Outbox(c.store).claim("synthetic-m6-worker")


def test_database_action_committed_before_hold_is_post_action_review(managed):
    c, _collection, _evidence, execution, bucket, document = managed
    task = prepare_action(c, execution, bucket, document)
    assert execution.execute("synthetic-m6-worker", task)["state"] == "verified"
    held = Holds(c.store).request(c.a, uuid4(), hold_input(bucket, document))
    assert held["state"] == "post_action_review" and held["urgent_post_action_review"]
    assert held["actual_state"] == "suppressed" and held["actual_revision"] == 2
    assert held["prior_action_prevented"] is False


def test_database_hold_arriving_during_mutation_reports_late_serialization(managed, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    c, _collection, _evidence, execution, bucket, document = managed
    task = prepare_action(c, execution, bucket, document)
    applying, allow_commit, hold_waiting = Event(), Event(), Event()
    original_apply, original_lock = execution.connector.apply, c.store.lock

    def paused_apply(*args):
        applying.set()
        assert allow_commit.wait(5)
        return original_apply(*args)

    def observed_lock(tx):
        if current_thread().name.startswith("m6-hold"):
            hold_waiting.set()
        return original_lock(tx)

    monkeypatch.setattr(execution.connector, "apply", paused_apply)
    monkeypatch.setattr(c.store, "lock", observed_lock)
    with (
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="m6-action") as action_pool,
        ThreadPoolExecutor(max_workers=1, thread_name_prefix="m6-hold") as hold_pool,
    ):
        action = action_pool.submit(execution.execute, "synthetic-m6-worker", task)
        assert applying.wait(5)
        hold = hold_pool.submit(Holds(c.store).request, c.a, uuid4(), hold_input(bucket, document))
        assert hold_waiting.wait(5)
        assert not hold.done()
        allow_commit.set()
        assert action.result(timeout=10)["state"] == "verified"
        result = hold.result(timeout=10)
    assert result["state"] == "post_action_review" and result["actual_state"] == "suppressed"
    assert result["received_at"] < result["fenced_at"]


def test_database_hold_committed_before_queued_action_blocks_primary_mutation(managed):
    c, _collection, _evidence, execution, bucket, document = managed
    task = prepare_action(c, execution, bucket, document)
    Holds(c.store).request(c.a, uuid4(), hold_input(bucket, document))
    with pytest.raises(GovernanceError, match="^hold_effective$"):
        execution.execute("synthetic-m6-worker", task)
    with c.store.transaction() as tx:
        row = tx.execute(
            "SELECT state,revision FROM governance_managed_documents WHERE document_id=%s",
            (document["id"],),
        ).fetchone()
    assert row == {"state": "active", "revision": 1}


def test_database_hold_audit_failure_rolls_back_effective_hold(managed):
    c, _collection, _evidence, _execution, bucket, document = managed
    with c.store.transaction() as tx:
        tx.execute("""CREATE FUNCTION refuse_hold_audit() RETURNS trigger LANGUAGE plpgsql AS $$
                   BEGIN RAISE EXCEPTION 'synthetic failure'; END $$;
                   CREATE TRIGGER refuse_hold_audit BEFORE INSERT ON governance_audit
                   FOR EACH ROW EXECUTE FUNCTION refuse_hold_audit();""")
    with pytest.raises(GovernanceError, match="^storage_failure$"):
        Holds(c.store).request(c.a, uuid4(), hold_input(bucket, document))
    with c.store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_holds").fetchone()["n"] == 0

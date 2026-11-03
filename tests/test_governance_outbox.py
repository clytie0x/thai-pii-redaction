"""Bounded worker contracts independent from any real service or shared database."""

import importlib
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from tests import governance_helpers as fixtures

context = fixtures.context
database = fixtures.database


def outbox_module():
    path = "pii_redactor.governance.outbox"
    assert importlib.util.find_spec(path) is not None, "leased outbox is not implemented"
    return importlib.import_module(path)


@pytest.mark.parametrize("worker", ["", "../worker", "https://example.test", "worker\n", "x" * 65])
def test_worker_identifiers_cannot_select_execution_targets(worker):
    module = outbox_module()
    with pytest.raises(Exception, match="^invalid_request$"):
        module.validate_worker(worker)


@pytest.mark.parametrize("lease, attempts", [(0, 3), (301, 3), (30, 0), (30, 11), (True, 3)])
def test_leases_and_retry_attempts_are_bounded(lease, attempts):
    module = outbox_module()
    with pytest.raises(Exception, match="^configuration_invalid$"):
        module.Outbox(None, lease_seconds=lease, max_attempts=attempts)


def test_unknown_outcome_requires_reconciliation_not_retry():
    module = outbox_module()
    assert module.failure_class("outcome_unknown") == "unknown"
    assert module.failure_class("storage_failure") == "retryable"
    assert module.failure_class("key_service_unavailable") == "retryable"
    assert module.failure_class("revision_conflict") == "terminal"
    assert module.failure_class("forbidden") == "terminal"


def test_worker_run_once_reports_verified_only_from_execution_result():
    path = "app.enterprise.worker"
    assert importlib.util.find_spec(path) is not None, "managed worker is not implemented"
    Worker = importlib.import_module(path).Worker

    class Queue:
        def claim(self, worker_id):
            return {"instruction_id": uuid4(), "lease_token": uuid4()}

    class Engine:
        def execute(self, worker_id, task):
            return {"state": "verified", "primary_verified": True}

    result = Worker(Engine(), Queue()).run_once("synthetic-worker")
    assert result == {"state": "verified", "primary_verified": True}


def test_database_duplicate_claim_and_expired_lease_require_reconciliation(context):
    from pii_redactor.governance.outbox import Outbox
    from tests.test_governance_execution import proposed

    _, _, execution, _, _, record = proposed(context)
    execution.approve(context.b, uuid4(), record["id"], 1)
    queue = Outbox(context.store)
    task = queue.claim("first-worker")
    assert task is not None and queue.claim("second-worker") is None
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_execution_tasks SET lease_until=clock_timestamp()-interval '1 second' WHERE instruction_id=%s",
            (task["instruction_id"],),
        )
    assert queue.claim("second-worker") is None
    state = execution.get(context.b, record["id"])
    assert state["state"] == "unknown"
    with pytest.raises(Exception, match="^lease_lost$"):
        execution.execute("first-worker", task)
    reconciled = execution.reconcile(context.b, uuid4(), record["id"], state["revision"])
    assert reconciled["state"] == "pending"
    fresh = queue.claim("second-worker")
    assert fresh["lease_token"] != task["lease_token"]
    assert execution.execute("second-worker", fresh)["state"] == "verified"


def test_database_terminal_and_retryable_failures_are_bounded(context):
    from pii_redactor.governance.outbox import Outbox
    from tests.test_governance_execution import proposed

    _, _, execution, _, _, record = proposed(context)
    execution.approve(context.b, uuid4(), record["id"], 1)
    queue = Outbox(context.store, max_attempts=2)
    first = queue.claim("synthetic-worker")
    assert (
        queue.record_failure("synthetic-worker", first, "key_service_unavailable")["state"]
        == "pending"
    )
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_execution_tasks SET available_at=clock_timestamp() WHERE instruction_id=%s",
            (first["instruction_id"],),
        )
    second = queue.claim("synthetic-worker")
    assert (
        queue.record_failure("synthetic-worker", second, "key_service_unavailable")["state"]
        == "failed"
    )
    assert queue.claim("synthetic-worker") is None


def test_database_commit_ack_failure_never_reports_dispatch_success(context, monkeypatch):
    from app.enterprise.worker import Worker
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.outbox import Outbox
    from tests.test_governance_execution import proposed

    collection, _, execution, bucket, document, record = proposed(context)
    execution.approve(context.b, uuid4(), record["id"], 1)

    def lost_ack(*args):
        raise GovernanceError("storage_failure")

    monkeypatch.setattr(execution, "execute", lost_ack)
    result = Worker(execution, Outbox(context.store)).run_once("synthetic-worker")
    assert result["state"] == "unknown" and not result["primary_verified"]
    assert collection.read_version(context.a, bucket["id"], document["id"], 1)["state"] == "active"


def test_database_crash_after_atomic_commit_does_not_repeat_primary_mutation(context, monkeypatch):
    from app.enterprise.worker import Worker
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.outbox import Outbox
    from tests.test_governance_execution import proposed

    _, _, execution, _, _, record = proposed(context)
    execution.approve(context.b, uuid4(), record["id"], 1)
    actual_execute = execution.execute

    def committed_without_ack(*args):
        actual_execute(*args)
        raise GovernanceError("storage_failure")

    monkeypatch.setattr(execution, "execute", committed_without_ack)
    worker = Worker(execution, Outbox(context.store))
    assert worker.run_once("synthetic-worker")["state"] == "unknown"
    assert execution.get(context.b, record["id"])["state"] == "verified"
    assert worker.run_once("synthetic-worker")["state"] == "idle"
    with context.store.transaction() as tx:
        assert (
            tx.execute("SELECT count(*) AS n FROM governance_execution_outcomes").fetchone()["n"]
            == 1
        )


def test_database_unknown_instruction_blocks_quarantine_before_control_mutation(context):
    from pii_redactor.governance.outbox import Outbox
    from tests.test_governance_execution import proposed

    collection, _, execution, bucket, document, record = proposed(context)
    snapshot = collection.snapshot(context.a, uuid4(), bucket["id"])
    execution.approve(context.b, uuid4(), record["id"], 1)
    queue = Outbox(context.store)
    task = queue.claim("synthetic-worker")
    queue.record_failure("synthetic-worker", task, "outcome_unknown")
    unknown = execution.get(context.b, record["id"])
    assert unknown["state"] == "unknown"
    with pytest.raises(Exception, match="^restore_reconciliation_required$"):
        collection.restore_quarantine(context.a, uuid4(), snapshot["id"], 1)
    assert collection.read_version(context.a, bucket["id"], document["id"], 1)["state"] == "active"
    with context.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT state FROM governance_collection_snapshots WHERE snapshot_id=%s",
                (snapshot["id"],),
            ).fetchone()["state"]
            == "captured"
        )
    assert (
        execution.reconcile(context.b, uuid4(), record["id"], unknown["revision"])["state"]
        == "pending"
    )

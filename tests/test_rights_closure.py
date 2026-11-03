"""Closure requires actual managed outcomes, manual review and recipient evidence."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.rights import FulfilmentPlan, ManualTask, Refusal, Target
from tests import test_governance_rights as fixtures
from tests.test_governance_rights import verified

database = fixtures.database
context = fixtures.context
rights_context = fixtures.rights_context


def mutation_plan(c, right="restriction"):
    from pii_redactor.governance.evidence import EvidenceInput
    from pii_redactor.governance.execution import InstructionInput

    row = verified(c, [right])
    evidence = None
    if right == "rectification":
        evidence = c.evidence.put(
            c.a,
            uuid4(),
            EvidenceInput(
                collection_id=c.bucket["id"],
                document_id=c.document["id"],
                expected_version=1,
                content_type="text/plain",
                content="Synthetic correction",
            ),
        )["id"]
    ins = c.execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_revision=1,
            expected_version=1,
            action={"restriction": "restrict", "erasure": "suppress", "rectification": "correct"}[
                right
            ],
            expires_at=datetime.now(UTC) + timedelta(hours=2),
            evidence_id=evidence,
        ),
    )
    tasks = []
    if right == "erasure":
        tasks = [
            ManualTask(
                right=right,
                kind=k,
                system_ref=uuid4(),
                owner_id=c.ids[0],
                scope_evidence_ref=uuid4(),
            )
            for k in ["derived", "processor", "replica_wal", "backup", "physical_storage"]
        ]
    row = c.rights.plan(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        FulfilmentPlan(
            targets=[
                Target(
                    right=right,
                    collection_id=c.bucket["id"],
                    document_id=c.document["id"],
                    target_revision=1,
                    target_version=1,
                    instruction_id=ins["id"],
                    scope_evidence_ref=uuid4(),
                )
            ],
            manual=tasks,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    row = c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())
    ins = c.execution.approve(c.b, uuid4(), ins["id"], ins["revision"])
    return row, ins


def execute_with_parent_hook(c):
    from pii_redactor.governance.outbox import Outbox

    old = c.execution._recheck

    def checked(tx, instruction, **kwargs):
        c.rights.fence_instruction(tx, instruction)
        return old(tx, instruction, **kwargs)

    c.execution._recheck = checked
    task = Outbox(c.store).claim("synthetic-m7-worker")
    return c.execution.execute("synthetic-m7-worker", task)


def test_case_cannot_close_on_worker_dispatch(rights_context):
    c = rights_context
    row, _ = mutation_plan(c)
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    assert execute_with_parent_hook(c)["primary_verified"]
    assert c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())["state"] == "closed"


def test_backup_or_processor_pending_blocks_full_erasure(rights_context):
    c = rights_context
    row, _ = mutation_plan(c, "erasure")
    execute_with_parent_hook(c)
    with pytest.raises(
        GovernanceError, match="outcome_evidence_required|physical_erasure_unavailable"
    ):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    assert (
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4(), partial=True)["state"]
        == "partial"
    )


def test_partial_delivery_remains_partial(rights_context):
    from pii_redactor.governance.delivery import Delivery
    from tests.test_governance_rights import access_plan

    c = rights_context
    row = access_plan(c)
    row = c.rights.plan(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        FulfilmentPlan(
            targets=row["plan"]["targets"],
            manual=[
                ManualTask(
                    right="access",
                    kind="external",
                    system_ref=uuid4(),
                    owner_id=c.ids[0],
                    scope_evidence_ref=uuid4(),
                )
            ],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    c.rights.preview(c.b, row["id"], row["revision"])
    row = c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())
    delivery = Delivery(c.rights)
    d = delivery.issue(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        row["plan_version"],
        datetime.now(UTC) + timedelta(minutes=20),
    )
    content = delivery.consume(c.actor, d["id"])
    delivery.acknowledge(c.actor, d["id"], content["revision"], content["receipt_token"])
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    assert (
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4(), partial=True)["state"]
        == "partial"
    )


def test_justified_refusal_needs_reviewed_evidence(rights_context):
    c = rights_context
    row = verified(c)
    row = c.rights.plan(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        FulfilmentPlan(
            refusals=[
                Refusal(
                    right="access",
                    reason_ref=uuid4(),
                    source_ref=uuid4(),
                    law_version="synthetic-law-v1",
                    notification_outcome_ref=uuid4(),
                )
            ],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    with pytest.raises(GovernanceError, match="case_authority_revoked"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    row = c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())
    assert c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())["state"] == "refused"


def test_case_withdrawal_fences_previously_approved_instruction(rights_context):
    c = rights_context
    row, _ = mutation_plan(c)
    c.rights.transition(c.a, uuid4(), row["id"], row["revision"], uuid4(), action="withdraw")
    with pytest.raises(GovernanceError, match="case_authority_revoked"):
        execute_with_parent_hook(c)
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_managed_documents").fetchone()["state"]
            == "active"
        )


def test_rectification_uses_actual_m5_primary_outcome(rights_context):
    c = rights_context
    row, _ = mutation_plan(c, "rectification")
    execute_with_parent_hook(c)
    assert c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())["state"] == "closed"


def test_manual_evidence_needs_distinct_review_and_physical_erasure_stays_unavailable(
    rights_context,
):
    c = rights_context
    row, _ = mutation_plan(c, "erasure")
    execute_with_parent_hook(c)
    task = next(t for t in row["manual"] if t["data"]["kind"] == "physical_storage")
    row = c.rights.manual_evidence(c.a, uuid4(), row["id"], row["revision"], task["id"], uuid4())
    with pytest.raises(GovernanceError, match="physical_erasure_unavailable"):
        c.rights.manual_evidence(
            c.b, uuid4(), row["id"], row["revision"], task["id"], uuid4(), review=True
        )
    task = next(t for t in row["manual"] if t["data"]["kind"] == "backup")
    row = c.rights.manual_evidence(c.a, uuid4(), row["id"], row["revision"], task["id"], uuid4())
    row = c.rights.manual_evidence(
        c.b, uuid4(), row["id"], row["revision"], task["id"], uuid4(), review=True
    )
    assert next(t for t in row["manual"] if t["id"] == task["id"])["state"] == "verified"


def test_reopened_case_preserves_history_and_requires_fresh_verification(rights_context):
    c = rights_context
    row, _ = mutation_plan(c)
    execute_with_parent_hook(c)
    row = c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    row = c.rights.transition(c.a, uuid4(), row["id"], row["revision"], uuid4(), action="reopen")
    assert row["state"] == "received" and row["history"][-1]["kind"] == "reopen"
    with pytest.raises(GovernanceError, match="case_authority_revoked"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())

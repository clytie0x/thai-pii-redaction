"""A new reviewed export can retain only this case's completed primary outcome."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.delivery import Delivery
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.evidence import EvidenceInput
from pii_redactor.governance.execution import InstructionInput
from pii_redactor.governance.rights import FulfilmentPlan, ManualTask, Target
from tests import test_governance_rights as fixtures
from tests.test_rights_closure import execute_with_parent_hook

database = fixtures.database
context = fixtures.context
rights_context = fixtures.rights_context


def export_target(c, revision, version):
    export = c.evidence.put(
        c.a,
        uuid4(),
        EvidenceInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_version=version,
            content_type="text/plain",
            content="Synthetic independently reviewed current export",
        ),
    )
    return Target(
        right="access",
        collection_id=c.bucket["id"],
        document_id=c.document["id"],
        target_revision=revision,
        target_version=version,
        scope_evidence_ref=uuid4(),
        export_evidence_id=export["id"],
        third_party_review_ref=uuid4(),
    )


def mixed_plan(c, right="rectification", *, remaining=()):
    row = fixtures.verified(c, ["access", right, *remaining])
    evidence = c.evidence.put(
        c.a,
        uuid4(),
        EvidenceInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_version=1,
            content_type="text/plain",
            content="Synthetic corrected primary content",
        ),
    )
    instruction = c.execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_revision=1,
            expected_version=1,
            action={"rectification": "correct", "restriction": "restrict", "erasure": "suppress"}[
                right
            ],
            expires_at=datetime.now(UTC) + timedelta(hours=2),
            evidence_id=evidence["id"] if right == "rectification" else None,
        ),
    )
    mutation = Target(
        right=right,
        collection_id=c.bucket["id"],
        document_id=c.document["id"],
        target_revision=1,
        target_version=1,
        scope_evidence_ref=uuid4(),
        instruction_id=instruction["id"],
    )
    row = c.rights.plan(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        FulfilmentPlan(
            targets=[export_target(c, 1, 1), mutation],
            manual=(
                [
                    ManualTask(
                        right="erasure",
                        kind=kind,
                        system_ref=uuid4(),
                        owner_id=c.ids[0],
                        scope_evidence_ref=uuid4(),
                    )
                    for kind in [
                        "derived",
                        "processor",
                        "replica_wal",
                        "backup",
                        "physical_storage",
                    ]
                ]
                if right == "erasure"
                else []
            )
            + [
                ManualTask(
                    right=other,
                    kind="external",
                    system_ref=uuid4(),
                    owner_id=c.ids[0],
                    scope_evidence_ref=uuid4(),
                )
                for other in remaining
            ],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    c.rights.preview(c.b, row["id"], row["revision"])
    row = c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())
    c.execution.approve(c.b, uuid4(), instruction["id"], instruction["revision"])
    return row, instruction, mutation


def reviewed_two_mutations(c, *, approve_restriction=True):
    row, corrected, mutation = mixed_plan(c, remaining=("restriction",))
    assert execute_with_parent_hook(c)["primary_verified"]
    restriction = c.execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_revision=2,
            expected_version=2,
            action="restrict",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    target = Target(
        right="restriction",
        collection_id=c.bucket["id"],
        document_id=c.document["id"],
        target_revision=2,
        target_version=2,
        instruction_id=restriction["id"],
        scope_evidence_ref=uuid4(),
    )
    row = c.rights.plan(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        FulfilmentPlan(
            targets=[export_target(c, 2, 2), mutation, target],
            expires_at=datetime.now(UTC) + timedelta(minutes=45),
        ),
    )
    c.rights.preview(c.b, row["id"], row["revision"])
    row = c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())
    delivery = Delivery(c.rights)
    issued = delivery.issue(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        2,
        datetime.now(UTC) + timedelta(minutes=10),
    )
    received = delivery.consume(c.actor, issued["id"])
    delivery.acknowledge(c.actor, issued["id"], received["revision"], received["receipt_token"])
    if approve_restriction:
        c.execution.approve(c.b, uuid4(), restriction["id"], restriction["revision"])
    return row, corrected, restriction


def test_same_case_ordered_correction_and_restriction_close_without_rewriting_proofs(
    rights_context,
):
    from app.enterprise.capabilities import rights_case_checker

    c = rights_context
    row, corrected, restriction = reviewed_two_mutations(c)
    assert execute_with_parent_hook(c)["primary_verified"]
    with c.store.transaction() as tx:
        proofs = tx.execute(
            "SELECT * FROM governance_execution_outcomes ORDER BY result_revision"
        ).fetchall()
        bindings = tx.execute(
            "SELECT * FROM governance_rights_instruction_bindings ORDER BY instruction_id"
        ).fetchall()
    closed = c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    assert closed["state"] == "closed"
    with c.store.transaction() as tx:
        assert rights_case_checker(c.rights)(
            tx, c.store.organization_id, "operations", row["id"], closed["revision"]
        )
        assert (
            tx.execute(
                "SELECT * FROM governance_execution_outcomes ORDER BY result_revision"
            ).fetchall()
            == proofs
        )
        assert (
            tx.execute(
                "SELECT * FROM governance_rights_instruction_bindings ORDER BY instruction_id"
            ).fetchall()
            == bindings
        )
        assert len(proofs) == 2 and [p["result_revision"] for p in proofs] == [2, 3]
        assert {str(p["instruction_id"]) for p in proofs} == {corrected["id"], restriction["id"]}
    with pytest.raises(GovernanceError, match="case_authority_revoked|revision_conflict"):
        Delivery(c.rights).issue(
            c.a, uuid4(), row["id"], closed["revision"], 2, datetime.now(UTC) + timedelta(minutes=5)
        )


def test_outcome_chain_rejects_a_real_other_case_mutation(rights_context):
    c = rights_context
    row, _corrected, _restriction = reviewed_two_mutations(c, approve_restriction=False)
    other = fixtures.verified(c, ["restriction"])
    instruction = c.execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_revision=2,
            expected_version=2,
            action="restrict",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        ),
    )
    other = c.rights.plan(
        c.a,
        uuid4(),
        other["id"],
        other["revision"],
        FulfilmentPlan(
            targets=[
                Target(
                    right="restriction",
                    collection_id=c.bucket["id"],
                    document_id=c.document["id"],
                    target_revision=2,
                    target_version=2,
                    instruction_id=instruction["id"],
                    scope_evidence_ref=uuid4(),
                )
            ],
            expires_at=datetime.now(UTC) + timedelta(minutes=25),
        ),
    )
    c.rights.review(c.b, uuid4(), other["id"], other["revision"], uuid4())
    c.execution.approve(c.b, uuid4(), instruction["id"], instruction["revision"])
    assert execute_with_parent_hook(c)["primary_verified"]
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())


def test_outcome_chain_requires_verified_successor_but_committed_reconciliation_can_recover(
    rights_context,
):
    c = rights_context
    row, _corrected, restriction = reviewed_two_mutations(c)
    execute_with_parent_hook(c)
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_execution_instructions SET state='unknown' WHERE instruction_id=%s",
            (restriction["id"],),
        )
        tx.execute(
            "UPDATE governance_execution_tasks SET state='unknown' WHERE instruction_id=%s",
            (restriction["id"],),
        )
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    current = c.execution.get(c.b, restriction["id"])
    c.execution.reconcile(c.b, uuid4(), current["id"], current["revision"])
    assert c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())["state"] == "closed"


@pytest.mark.parametrize("fault", ["missing", "gap", "cycle", "unapproved"])
def test_outcome_chain_rejects_missing_or_noncontiguous_primary_proofs(rights_context, fault):
    c = rights_context
    row, _corrected, restriction = reviewed_two_mutations(
        c, approve_restriction=fault != "unapproved"
    )
    with c.store.transaction() as tx:
        current = tx.execute(
            "SELECT * FROM governance_execution_instructions WHERE instruction_id=%s",
            (restriction["id"],),
        ).fetchone()
        if fault != "missing":
            ciphertext = tx.execute(
                "SELECT ciphertext_digest FROM governance_document_versions WHERE document_id=%s AND version=2",
                (c.document["id"],),
            ).fetchone()["ciphertext_digest"]
            tx.execute(
                "UPDATE governance_execution_instructions SET state='verified' WHERE instruction_id=%s",
                (restriction["id"],),
            )
            tx.execute(
                "UPDATE governance_execution_tasks SET state='verified' WHERE instruction_id=%s",
                (restriction["id"],),
            )
            tx.execute(
                """INSERT INTO governance_execution_outcomes(instruction_id,instruction_digest,document_id,
                result_version,result_revision,result_state,ciphertext_digest) VALUES (%s,%s,%s,2,%s,'restricted',%s)""",
                (
                    restriction["id"],
                    current["instruction_digest"],
                    c.document["id"],
                    5 if fault == "gap" else 1 if fault == "cycle" else 3,
                    ciphertext,
                ),
            )
        tx.execute(
            "UPDATE governance_managed_documents SET revision=%s,state='restricted',last_instruction_id=%s WHERE document_id=%s",
            (5 if fault == "gap" else 3, restriction["id"], c.document["id"]),
        )
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())


def test_outcome_chain_authenticates_protected_snapshot_bytes(rights_context, monkeypatch):
    import hashlib

    c = rights_context
    row, _corrected, _restriction = reviewed_two_mutations(c)
    execute_with_parent_hook(c)
    original = c.collection.protection.open
    altered = []

    def corrupted_read(organization, collection, envelope, context):
        forged = dict(envelope)
        ciphertext = bytearray(forged["ciphertext"])
        ciphertext[-1] ^= 1
        forged["ciphertext"] = bytes(ciphertext)
        forged["ciphertext_digest"] = hashlib.sha256(ciphertext).hexdigest()
        altered.append(context["version"])
        return original(organization, collection, forged, context)

    monkeypatch.setattr(c.collection.protection, "open", corrupted_read)
    with pytest.raises(GovernanceError, match="protected_content_invalid"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    assert altered == [2]


def test_later_unrelated_primary_mutation_is_not_an_own_case_chain_extension(rights_context):
    c = rights_context
    row, _corrected, _restriction = reviewed_two_mutations(c)
    execute_with_parent_hook(c)
    evidence = c.evidence.put(
        c.a,
        uuid4(),
        EvidenceInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_version=2,
            content_type="text/plain",
            content="Synthetic unrelated later primary",
        ),
    )
    instruction = c.execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_revision=3,
            expected_version=2,
            action="correct",
            expires_at=datetime.now(UTC) + timedelta(minutes=20),
            evidence_id=evidence["id"],
        ),
    )
    c.execution.approve(c.b, uuid4(), instruction["id"], instruction["revision"])
    assert execute_with_parent_hook(c)["primary_verified"]
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())


@pytest.mark.parametrize("right", ["restriction", "erasure"])
def test_received_access_can_close_its_own_later_restriction_without_new_disclosure(
    rights_context, right
):
    c = rights_context
    row, _instruction, _mutation = mixed_plan(c, right)
    delivery = Delivery(c.rights)
    issued = delivery.issue(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        1,
        datetime.now(UTC) + timedelta(minutes=10),
    )
    downloaded = delivery.consume(c.actor, issued["id"])
    delivery.acknowledge(c.actor, issued["id"], downloaded["revision"], downloaded["receipt_token"])
    assert execute_with_parent_hook(c)["primary_verified"]
    with pytest.raises(GovernanceError, match="revision_conflict"):
        delivery.issue(
            c.a, uuid4(), row["id"], row["revision"], 1, datetime.now(UTC) + timedelta(minutes=10)
        )
    result = c.rights.close(
        c.b, uuid4(), row["id"], row["revision"], uuid4(), partial=right == "erasure"
    )
    assert result["state"] == ("partial" if right == "erasure" else "closed")
    if right == "erasure":
        assert result["physical_erasure_available"] is False
        assert len(result["manual"]) == 5


def test_committed_reconciliation_checks_its_own_outcome_without_releasing_stale_export(
    rights_context,
):
    c = rights_context
    row, instruction, _mutation = mixed_plan(c)
    execute_with_parent_hook(c)
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_execution_instructions SET state='unknown' WHERE instruction_id=%s",
            (instruction["id"],),
        )
        tx.execute(
            "UPDATE governance_execution_tasks SET state='unknown' WHERE instruction_id=%s",
            (instruction["id"],),
        )
        unknown = tx.execute(
            "SELECT * FROM governance_execution_instructions WHERE instruction_id=%s",
            (instruction["id"],),
        ).fetchone()
        c.rights.fence_instruction(tx, unknown, allow_committed=True)
    current = c.execution.get(c.b, instruction["id"])
    assert c.execution.reconcile(c.b, uuid4(), current["id"], current["revision"])[
        "primary_verified"
    ]
    with pytest.raises(GovernanceError, match="revision_conflict"):
        Delivery(c.rights).issue(
            c.a, uuid4(), row["id"], row["revision"], 1, datetime.now(UTC) + timedelta(minutes=10)
        )


def renew(c, row, mutation, *, revision=2, version=2):
    return c.rights.plan(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        FulfilmentPlan(
            targets=[export_target(c, revision, version), mutation],
            expires_at=datetime.now(UTC) + timedelta(minutes=45),
        ),
    )


def test_mixed_right_renewal_requires_new_preview_and_preserves_immutable_outcome(rights_context):
    c = rights_context
    row, instruction, mutation = mixed_plan(c)
    delivery = Delivery(c.rights)
    old = delivery.issue(
        c.a, uuid4(), row["id"], row["revision"], 1, datetime.now(UTC) + timedelta(minutes=10)
    )
    assert execute_with_parent_hook(c)["primary_verified"]
    with c.store.transaction() as tx:
        proof = tx.execute("SELECT * FROM governance_execution_outcomes").fetchone()
        bound = tx.execute("SELECT * FROM governance_rights_instruction_bindings").fetchone()
    with pytest.raises(GovernanceError, match="revision_conflict"):
        delivery.consume(c.actor, old["id"])
    with pytest.raises(GovernanceError, match="revision_conflict"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())

    renewed = renew(c, row, mutation)
    assert renewed["plan_version"] == 2 and renewed["state"] == "planned"
    assert renewed["plan"]["completed_outcomes"][instruction["id"]]["source_plan_version"] == 1
    with pytest.raises(GovernanceError, match="case_authority_revoked"):
        delivery.issue(
            c.a,
            uuid4(),
            row["id"],
            renewed["revision"],
            2,
            datetime.now(UTC) + timedelta(minutes=10),
        )
    with pytest.raises(GovernanceError, match="redaction_review_required"):
        c.rights.review(c.b, uuid4(), renewed["id"], renewed["revision"], uuid4())
    c.rights.preview(c.b, renewed["id"], renewed["revision"])
    reviewed = c.rights.review(c.b, uuid4(), renewed["id"], renewed["revision"], uuid4())
    with pytest.raises(GovernanceError, match="delivery_revoked"):
        delivery.consume(c.actor, old["id"])
    fresh = delivery.issue(
        c.a,
        uuid4(),
        reviewed["id"],
        reviewed["revision"],
        2,
        datetime.now(UTC) + timedelta(minutes=10),
    )
    consumed = delivery.consume(c.actor, fresh["id"])
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), reviewed["id"], reviewed["revision"], uuid4())
    assert delivery.acknowledge(
        c.actor, fresh["id"], consumed["revision"], consumed["receipt_token"]
    )["fulfilled"]
    assert (
        c.rights.close(c.b, uuid4(), reviewed["id"], reviewed["revision"], uuid4())["state"]
        == "closed"
    )
    with c.store.transaction() as tx:
        assert tx.execute("SELECT * FROM governance_execution_outcomes").fetchone() == proof
        assert (
            tx.execute("SELECT * FROM governance_rights_instruction_bindings").fetchone() == bound
        )
        assert (
            tx.execute(
                "SELECT state FROM governance_execution_instructions WHERE instruction_id=%s",
                (instruction["id"],),
            ).fetchone()["state"]
            == "verified"
        )


@pytest.mark.parametrize("fault", ["other_case", "unverified", "new_primary"])
def test_completed_outcome_carry_forward_rejects_substitution_and_unverified_state(
    rights_context, fault
):
    c = rights_context
    row, instruction, mutation = mixed_plan(c)
    execute_with_parent_hook(c)
    if fault == "other_case":
        row = fixtures.verified(c, ["access", "rectification"])
    elif fault == "unverified":
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_execution_instructions SET state='unknown' WHERE instruction_id=%s",
                (instruction["id"],),
            )
    else:
        evidence = c.evidence.put(
            c.a,
            uuid4(),
            EvidenceInput(
                collection_id=c.bucket["id"],
                document_id=c.document["id"],
                expected_version=2,
                content_type="text/plain",
                content="Synthetic newer primary",
            ),
        )
        newer = c.execution.propose(
            c.a,
            uuid4(),
            InstructionInput(
                collection_id=c.bucket["id"],
                document_id=c.document["id"],
                expected_revision=2,
                expected_version=2,
                action="correct",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                evidence_id=evidence["id"],
            ),
        )
        c.execution.approve(c.b, uuid4(), newer["id"], newer["revision"])
        execute_with_parent_hook(c)
    with pytest.raises(
        GovernanceError,
        match="instruction_already_bound|outcome_evidence_required|unissued_instruction_required",
    ):
        renew(
            c,
            row,
            mutation,
            revision=3 if fault == "new_primary" else 2,
            version=3 if fault == "new_primary" else 2,
        )

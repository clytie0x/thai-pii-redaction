"""Production composition keeps rights and register fences in the same transaction."""

from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from app.enterprise.capabilities import rights_case_checker
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.rights import Rights
from tests import test_governance_integration as production
from tests import test_governance_rights as fixtures
from tests.test_rights_delivery import issued

database = fixtures.database
context = fixtures.context
rights_context = fixtures.rights_context
subject_context = production.subject_context
consent_context = production.consent_context
integrated = production.integrated


def test_exact_current_case_register_link_does_not_grant_execution(rights_context):
    c = rights_context
    row = fixtures.approved(c)
    check = rights_case_checker(c.rights)
    with c.store.transaction() as tx:
        c.store.lock(tx)
        args = (tx, c.store.organization_id, "operations", row["id"], row["revision"])
        assert check(*args) is True
        assert check(tx, uuid4(), "operations", row["id"], row["revision"]) is False
        assert check(tx, c.store.organization_id, "other", row["id"], row["revision"]) is False
        assert check(tx, c.store.organization_id, "operations", row["id"], 1) is False
    changed = c.rights.transition(
        c.a, uuid4(), row["id"], row["revision"], uuid4(), action="withdraw"
    )
    with c.store.transaction() as tx:
        c.store.lock(tx)
        assert (
            check(tx, c.store.organization_id, "operations", row["id"], changed["revision"])
            is False
        )


def test_closed_case_link_rechecks_receipt_outcome_and_current_identity(rights_context):
    c = rights_context
    row, delivery = issued(c)
    result = c.delivery.consume(c.actor, delivery["id"])
    c.delivery.acknowledge(c.actor, delivery["id"], result["revision"], result["receipt_token"])
    row = c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    check = rights_case_checker(c.rights)
    with c.store.transaction() as tx:
        c.store.lock(tx)
        assert check(tx, c.store.organization_id, "operations", row["id"], row["revision"])
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s", (c.ids[1],)
        )
    with c.store.transaction() as tx:
        c.store.lock(tx)
        assert not check(tx, c.store.organization_id, "operations", row["id"], row["revision"])


def test_actual_managed_factory_calls_rights_fence_before_primary_mutation(integrated, monkeypatch):
    c = integrated
    production.consent_fixtures.command(c, "grant")
    bucket, document, _approved = production.queued_document(c)

    def denied(_self, _tx, _instruction, **_kwargs):
        raise GovernanceError("case_authority_revoked")

    monkeypatch.setattr(Rights, "fence_instruction", denied)
    result = c.worker.run_once("synthetic-rights-composition")
    assert not result["primary_verified"]
    assert production.primary(c, document["id"])["state"] == "active"
    assert c.collection.documents(c.a, bucket["id"])[0]["revision"] == 1


def linked_case_candidate(c, *, close):
    from pii_redactor.governance.policy_register import Policies
    from tests import test_governance_processing_controls as processing
    from tests.test_governance_organization_controls import activate, policy

    with c.store.transaction() as tx:
        c.activity = tx.execute(
            "SELECT a.* FROM governance_activities a JOIN governance_collections c USING(activity_id) WHERE c.collection_id=%s",
            (c.bucket["id"],),
        ).fetchone()
    controls, _law = processing.controls(c)
    service, _binding = processing.enabled(c, controls)
    service.case_checker = rights_case_checker(c.rights)
    c.collection.processing_check = service.require_activity
    processing.production_mode(c)
    case, delivery = issued(c)
    if close:
        received = c.delivery.consume(c.actor, delivery["id"])
        c.delivery.acknowledge(
            c.actor, delivery["id"], received["revision"], received["receipt_token"]
        )
        case = c.rights.close(c.b, uuid4(), case["id"], case["revision"], uuid4())
    control = activate(
        Policies(c.store, case_checker=service.case_checker),
        c,
        policy(
            links=[
                {
                    "kind": "case",
                    "id": case["id"],
                    "revision": case["revision"],
                }
            ]
        ),
    )
    candidate = service.create(c.a, uuid4(), processing.request(c, [*controls, control]))
    candidate = service.submit(c.a, uuid4(), candidate["id"], candidate["revision"])
    service.preview(c.b, candidate["id"], candidate["revision"])
    candidate = service.review(
        c.b, uuid4(), candidate["id"], candidate["revision"], "approve", uuid4()
    )
    return service, candidate


def test_closed_case_evidence_survives_same_activity_binding_renewal_without_disclosure(
    rights_context,
):
    c = rights_context
    service, candidate = linked_case_candidate(c, close=True)
    assert service.activate(c.b, uuid4(), candidate["id"], candidate["revision"])["usable"]


def test_live_case_cannot_authorize_its_own_processing_binding(rights_context):
    c = rights_context
    service, candidate = linked_case_candidate(c, close=False)
    with pytest.raises(GovernanceError, match="processing_controls_stale"):
        service.activate(c.b, uuid4(), candidate["id"], candidate["revision"])


@pytest.mark.parametrize("tamper", [False, True])
def test_historical_closure_checks_immutable_metadata_without_reopening_content(
    rights_context, monkeypatch, tamper
):
    c = rights_context
    row, delivery = issued(c)
    received = c.delivery.consume(c.actor, delivery["id"])
    c.delivery.acknowledge(c.actor, delivery["id"], received["revision"], received["receipt_token"])
    row = c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())

    def no_disclosure(*_args, **_kwargs):
        pytest.fail("Historical metadata validation reopened protected content")

    monkeypatch.setattr(c.collection, "check_consent", no_disclosure)
    monkeypatch.setattr(c.collection.protection, "open", no_disclosure)
    monkeypatch.setattr(c.evidence, "content", no_disclosure)
    if tamper:
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_rights_deliveries SET receipt_ref=%s WHERE delivery_id=%s",
                (uuid4(), delivery["id"]),
            )
    with c.store.transaction() as tx:
        c.store.lock(tx)
        assert rights_case_checker(c.rights)(
            tx, c.store.organization_id, "operations", row["id"], row["revision"]
        ) is (not tamper)


def test_legacy_closure_without_immutable_metadata_proof_is_not_silently_trusted(
    rights_context, monkeypatch
):
    c = rights_context
    row, delivery = issued(c)
    received = c.delivery.consume(c.actor, delivery["id"])
    c.delivery.acknowledge(c.actor, delivery["id"], received["revision"], received["receipt_token"])
    with monkeypatch.context() as patch:
        patch.setattr(c.rights, "_closure_proof", lambda *_args: None)
        row = c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    with c.store.transaction() as tx:
        c.store.lock(tx)
        assert not rights_case_checker(c.rights)(
            tx, c.store.organization_id, "operations", row["id"], row["revision"]
        )


def test_closed_mutation_evidence_never_decrypts_or_reauthorizes_content(
    rights_context, monkeypatch
):
    from tests.test_rights_closure import execute_with_parent_hook, mutation_plan

    c = rights_context
    row, _instruction = mutation_plan(c)
    assert execute_with_parent_hook(c)["primary_verified"]
    row = c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())

    def no_disclosure(*_args, **_kwargs):
        pytest.fail("Historical mutation proof decrypted or reauthorized content")

    monkeypatch.setattr(c.collection, "check_consent", no_disclosure)
    monkeypatch.setattr(c.collection.protection, "open", no_disclosure)
    with c.store.transaction() as tx:
        c.store.lock(tx)
        assert rights_case_checker(c.rights)(
            tx, c.store.organization_id, "operations", row["id"], row["revision"]
        )

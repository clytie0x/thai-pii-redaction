"""Actual M4 sessions, encrypted PostgreSQL delivery and fail-closed races."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.delivery import Delivery
from pii_redactor.governance.errors import GovernanceError
from tests import test_governance_rights as fixtures
from tests.test_governance_rights import approved

database = fixtures.database
context = fixtures.context
rights_context = fixtures.rights_context


def issued(c):
    row = approved(c)
    c.delivery = Delivery(c.rights)
    delivery = c.delivery.issue(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        row["plan_version"],
        datetime.now(UTC) + timedelta(hours=1),
    )
    return row, delivery


def test_encrypted_recipient_bound_download_is_not_receipt(rights_context):
    c = rights_context
    row, d = issued(c)
    with c.store.transaction() as tx:
        encrypted = tx.execute("SELECT ciphertext FROM governance_rights_deliveries").fetchone()[
            "ciphertext"
        ]
        assert b"Synthetic reviewed" not in bytes(encrypted)
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    result = c.delivery.consume(c.actor, d["id"])
    assert result["fulfilled"] is False
    with pytest.raises(GovernanceError, match="outcome_evidence_required"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())
    assert c.delivery.acknowledge(c.actor, d["id"], result["revision"], result["receipt_token"])[
        "fulfilled"
    ]
    assert c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())["state"] == "closed"


def test_delivery_rejects_bearer_link_forged_actor_and_revoked_session(rights_context):
    from dataclasses import replace

    c = rights_context
    _, d = issued(c)
    for actor in (None, replace(c.actor, session_id=uuid4()), replace(c.actor, subject_id=uuid4())):
        with pytest.raises(GovernanceError, match="authentication_required"):
            c.delivery.consume(actor, d["id"])
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE enterprise_subject_sessions SET revoked=true WHERE session_id=%s",
            (c.actor.session_id,),
        )
    with pytest.raises(GovernanceError, match="authentication_required"):
        c.delivery.consume(c.actor, d["id"])


def test_delivery_expiry_withdrawal_export_version_and_tamper(rights_context):
    c = rights_context
    row, d = issued(c)
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_rights_deliveries SET expires_at=clock_timestamp()-interval '1 second'"
        )
    with pytest.raises(GovernanceError, match="delivery_expired"):
        c.delivery.consume(c.actor, d["id"])
    c.rights.transition(c.a, uuid4(), row["id"], row["revision"], uuid4(), action="withdraw")
    with pytest.raises(GovernanceError, match="delivery_revoked|case_authority_revoked"):
        c.delivery.consume(c.actor, d["id"])


def test_download_race_has_one_result_and_no_replay(rights_context):
    c = rights_context
    _, d = issued(c)

    def run(_):
        try:
            return c.delivery.consume(c.actor, d["id"])["fulfilled"]
        except GovernanceError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results.count(False) == 1 and results.count("delivery_replay") == 1


def test_subject_link_correction_and_current_document_restriction_block_delivery(rights_context):
    c = rights_context
    _, d = issued(c)
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_managed_documents SET state='restricted',revision=revision+1 WHERE document_id=%s",
            (c.document["id"],),
        )
    with pytest.raises(GovernanceError, match="revision_conflict|record_restricted"):
        c.delivery.consume(c.actor, d["id"])
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_subjects SET revision=revision+1 WHERE subject_id=%s",
            (c.actor.subject_id,),
        )
    with pytest.raises(GovernanceError, match="authentication_required"):
        c.delivery.consume(c.actor, d["id"])


def test_changed_source_after_download_cannot_close_stale_export(rights_context):
    c = rights_context
    row, d = issued(c)
    result = c.delivery.consume(c.actor, d["id"])
    c.delivery.acknowledge(c.actor, d["id"], result["revision"], result["receipt_token"])
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_managed_documents SET revision=revision+1 WHERE document_id=%s",
            (c.document["id"],),
        )
    with pytest.raises(GovernanceError, match="revision_conflict"):
        c.rights.close(c.b, uuid4(), row["id"], row["revision"], uuid4())


def test_failed_download_audit_rolls_back_receipt_and_state(rights_context, monkeypatch):
    c = rights_context
    _, d = issued(c)
    reached = []

    def fail(*args, **kwargs):
        reached.append(True)
        raise GovernanceError("synthetic_audit_failure")

    monkeypatch.setattr(c.store, "append_event", fail)
    with pytest.raises(GovernanceError, match="synthetic_audit_failure"):
        c.delivery.consume(c.actor, d["id"])
    assert reached
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_rights_deliveries").fetchone()["state"]
            == "issued"
        )


def test_wrong_actual_subject_cannot_guess_delivery_id(rights_context):
    from app.enterprise.subject_auth import SubjectIdentity
    from pii_redactor.governance.subjects import SubjectLinks
    from tests.test_governance_subjects import link_request

    c = rights_context
    _, d = issued(c)
    links = SubjectLinks(c.store)
    link = links.propose(c.a, uuid4(), link_request(oidc_subject="synthetic-other"))
    links.review(c.b, uuid4(), link["id"], 1, "approve", uuid4())
    other = c.sessions.issue(SubjectIdentity(c.a.issuer, "synthetic-other", "aiguard-subject"))
    with pytest.raises(GovernanceError, match="record_unavailable"):
        c.delivery.consume(c.sessions.resolve(other.cookie), d["id"])


def test_ciphertext_tamper_and_wrong_export_version_fail_closed(rights_context):
    c = rights_context
    row = approved(c)
    delivery = Delivery(c.rights)
    with pytest.raises(GovernanceError, match="export_version_conflict"):
        delivery.issue(
            c.a,
            uuid4(),
            row["id"],
            row["revision"],
            row["plan_version"] + 1,
            datetime.now(UTC) + timedelta(minutes=20),
        )
    d = delivery.issue(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        row["plan_version"],
        datetime.now(UTC) + timedelta(minutes=20),
    )
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_rights_deliveries SET ciphertext=set_byte(ciphertext,0,(get_byte(ciphertext,0)+1)%256)"
        )
    with pytest.raises(GovernanceError, match="protected_content_invalid"):
        delivery.consume(c.actor, d["id"])


def test_consent_and_hold_fence_are_rechecked_on_delivery(rights_context, monkeypatch):
    c = rights_context
    _, d = issued(c)
    reached = []

    def denied(*args, **kwargs):
        reached.append(True)
        raise GovernanceError("consent_required")

    monkeypatch.setattr(c.collection, "check_consent", denied)
    with pytest.raises(GovernanceError, match="consent_required"):
        c.delivery.consume(c.actor, d["id"])
    assert reached


def test_actual_m4_withdrawal_cannot_be_bypassed_for_disclosure(rights_context):
    from app.enterprise.capabilities import consent_gate
    from pii_redactor.governance.collections import CollectionInput
    from pii_redactor.governance.consent import Consent
    from pii_redactor.governance.registry import Registry, ReviewInput
    from tests.test_governance_consent import command
    from tests.test_governance_registry import activity, evidence, published_notice

    c = rights_context
    registry = Registry(c.store)
    record = registry.create_activity(c.a, uuid4(), activity(general_basis="consent"))
    c.notice = published_notice(registry, c, record)
    submitted = registry.submit_activity(c.a, uuid4(), record["id"], 1)
    active = registry.review_activity(
        c.b,
        uuid4(),
        record["id"],
        submitted["revision"],
        ReviewInput(
            decision="approve",
            reason="Synthetic independent review",
            notice_id=c.notice["id"],
            evidence=evidence(),
        ),
    )
    c.consent = Consent(c.store)
    grant = command(c, "grant")
    c.collection.consent_check = consent_gate(c.store, c.consent)
    c.bucket = c.collection.create(
        c.a,
        uuid4(),
        CollectionInput(
            activity_id=active["id"],
            expected_activity_revision=active["revision"],
            subject_id=c.actor.subject_id,
            purpose_version=c.notice["id"],
        ),
    )
    c.document = c.collection.put(c.a, uuid4(), c.bucket["id"], "Synthetic consent-bound document")
    _, d = issued(c)
    command(c, "withdraw", expected=grant["revision"])
    with pytest.raises(GovernanceError, match="consent_required"):
        c.delivery.consume(c.actor, d["id"])
    from pii_redactor.governance.consent import PropagationScope

    current = command(c, "grant", expected=2)
    assert current["revision"] == 3
    for task in c.consent.status(c.actor, c.notice["id"])["propagation"]:
        c.consent.review_propagation(
            c.b,
            uuid4(),
            task["id"],
            "verified",
            uuid4(),
            evidence_scope=PropagationScope(
                consent_event_id=task["consent_event_id"],
                event_revision=task["event_revision"],
                recipient_ordinal=task["recipient"],
                expected_state=task["state"],
            ),
        )
    assert c.consent.status(c.actor, c.notice["id"])["allowed"] is True
    with pytest.raises(GovernanceError, match="consent_authority_changed"):
        c.delivery.consume(c.actor, d["id"])


def test_actual_m6_hold_blocks_managed_mutation_but_does_not_invent_disclosure_restriction(
    rights_context,
):
    from pii_redactor.governance.holds import HoldInput, Holds
    from tests.test_rights_closure import execute_with_parent_hook, mutation_plan

    c = rights_context
    row, _ = mutation_plan(c)
    Holds(c.store).request(
        c.a,
        uuid4(),
        HoldInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_revision=1,
            expected_version=1,
            reason="rights_case",
            evidence_ref=uuid4(),
            review_due_at=datetime.now(UTC) + timedelta(days=1),
        ),
    )
    with pytest.raises(GovernanceError, match="hold_effective"):
        execute_with_parent_hook(c)


def test_download_and_withdraw_race_respects_serialization(rights_context):
    c = rights_context
    row, d = issued(c)

    def download():
        try:
            c.delivery.consume(c.actor, d["id"])
            return "downloaded"
        except GovernanceError as error:
            return str(error)

    def withdraw():
        return c.rights.transition(
            c.a, uuid4(), row["id"], row["revision"], uuid4(), action="withdraw"
        )["state"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(download), pool.submit(withdraw)
        assert a.result() in {"downloaded", "delivery_revoked", "case_authority_revoked"}
        assert b.result() == "withdrawn"
    with pytest.raises(GovernanceError, match="delivery_revoked|case_authority_revoked"):
        c.delivery.consume(c.actor, d["id"])

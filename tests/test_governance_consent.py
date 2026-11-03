"""Synthetic consent history, withdrawal fencing and current authority."""

from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from app.enterprise.subject_auth import SubjectIdentity, SubjectSessions
from pii_redactor.governance.consent import Consent, ConsentScope, NoticeProof
from pii_redactor.governance.errors import GovernanceError
from tests import governance_helpers as fixtures
from tests import test_governance_subjects as subject_fixtures

database = fixtures.database
context = fixtures.context
subject_context = subject_fixtures.subject_context


@pytest.fixture
def consent_context(subject_context):
    from pii_redactor.governance.registry import Registry, ReviewInput
    from tests.test_governance_registry import activity, evidence, published_notice

    c = subject_context
    c.subject = subject_fixtures.resolved_subject(c)
    c.sessions = SubjectSessions(c.store, issuer=c.a.issuer, client_id="aiguard-subject")
    grant = c.sessions.issue(SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject"))
    c.actor = c.sessions.resolve(grant.cookie)
    registry = Registry(c.store)
    record = registry.create_activity(c.a, uuid4(), activity(general_basis="consent"))
    c.notice = published_notice(registry, c, record)
    submitted = registry.submit_activity(c.a, uuid4(), record["id"], 1)
    registry.review_activity(
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
    return c


def command(c, action, *, expected=0, key=None, proof=None):
    if proof is None:
        presentation = c.consent.present(c.actor, c.notice["id"])
        proof = NoticeProof.model_validate(presentation["notice_proof"])
    return c.consent.record_subject_event(
        c.actor,
        key or uuid4(),
        proof,
        ConsentScope(
            purpose_version=c.notice["id"], categories=["CONTACT"], expected_revision=expected
        ),
        action,
        affirmative=True,
    )


def test_withdrawal_blocks_affected_processing_without_silent_basis_switch(consent_context):
    c = consent_context
    grant = command(c, "grant")
    withdrawn = command(c, "withdraw", expected=grant["revision"])
    with c.store.transaction() as tx:
        assert (
            c.consent.effective(tx, c.subject["subject_id"], c.notice["id"])["reason"]
            == "withdrawn"
        )
        with pytest.raises(GovernanceError, match="^consent_required$"):
            c.consent.require_processing(tx, c.subject["subject_id"], c.notice["id"], ["CONTACT"])
    assert withdrawn["propagation_complete"] is False


def test_old_grant_retry_cannot_reactivate_after_withdrawal(consent_context):
    c = consent_context
    key = uuid4()
    presentation = c.consent.present(c.actor, c.notice["id"])
    proof = NoticeProof.model_validate(presentation["notice_proof"])
    grant = command(c, "grant", key=key, proof=proof)
    command(c, "withdraw", expected=grant["revision"])
    replay = command(c, "grant", key=key, proof=proof)
    assert replay["replayed"] is True and replay["effective"]["allowed"] is False
    with pytest.raises(GovernanceError, match="^revision_conflict$"):
        command(c, "grant", expected=0)


def test_queued_processing_rechecks_withdrawal(consent_context):
    c = consent_context
    granted = command(c, "grant")
    with c.store.transaction() as tx:
        approved = c.consent.require_processing(
            tx, c.subject["subject_id"], c.notice["id"], ["CONTACT"]
        )
    command(c, "withdraw", expected=granted["revision"])
    with c.store.transaction() as tx:
        with pytest.raises(GovernanceError, match="^consent_required$"):
            c.consent.require_processing(
                tx,
                c.subject["subject_id"],
                c.notice["id"],
                ["CONTACT"],
                expected_revision=approved["revision"],
            )


def test_failed_propagation_cannot_report_complete(consent_context):
    c = consent_context
    grant = command(c, "grant")
    command(c, "withdraw", expected=grant["revision"])
    with c.store.transaction() as tx:
        rows = tx.execute("SELECT propagation_id FROM governance_consent_propagation").fetchall()
    c.consent.review_propagation(c.b, uuid4(), rows[0]["propagation_id"], "failed", uuid4())
    state = c.consent.status(c.actor, c.notice["id"])
    assert state["propagation_complete"] is False
    assert state["propagation"][0]["state"] == "failed"


def test_staff_cannot_forge_subject_grant_and_false_affirmation_is_rejected(consent_context):
    c = consent_context
    proof = NoticeProof.model_validate(c.consent.present(c.actor, c.notice["id"])["notice_proof"])
    scope = ConsentScope(
        purpose_version=c.notice["id"], categories=["CONTACT"], expected_revision=0
    )
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        c.consent.record_subject_event(c.a, uuid4(), proof, scope, "grant", affirmative=True)
    with pytest.raises(GovernanceError, match="^affirmation_required$"):
        c.consent.record_subject_event(c.actor, uuid4(), proof, scope, "grant", affirmative=False)


def test_notice_tampering_missing_receipt_and_scope_widening_are_denied(consent_context):
    c = consent_context
    presentation = c.consent.present(c.actor, c.notice["id"])
    proof = NoticeProof.model_validate(presentation["notice_proof"])
    bad_digest = proof.model_copy(update={"notice_digest": "0" * 64})
    scope = ConsentScope(
        purpose_version=c.notice["id"], categories=["CONTACT"], expected_revision=0
    )
    with pytest.raises(GovernanceError, match="^notice_scope_mismatch$"):
        c.consent.record_subject_event(
            c.actor, uuid4(), bad_digest, scope, "grant", affirmative=True
        )
    absent = proof.model_copy(update={"presentation_id": uuid4()})
    with pytest.raises(GovernanceError, match="^notice_presentation_required$"):
        c.consent.record_subject_event(c.actor, uuid4(), absent, scope, "grant", affirmative=True)
    wider = scope.model_copy(update={"categories": ["CONTACT", "ID"]})
    with pytest.raises(GovernanceError, match="^consent_scope_mismatch$"):
        c.consent.record_subject_event(c.actor, uuid4(), proof, wider, "grant", affirmative=True)


def test_grant_and_withdrawal_race_never_reactivates_old_grant(consent_context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    c = consent_context
    proof = NoticeProof.model_validate(c.consent.present(c.actor, c.notice["id"])["notice_proof"])
    key = uuid4()
    granted = command(c, "grant", key=key, proof=proof)
    withdraw_proof = NoticeProof.model_validate(
        c.consent.present(c.actor, c.notice["id"])["notice_proof"]
    )
    barrier = Barrier(2)

    def run(action):
        barrier.wait(timeout=10)
        return command(
            c,
            action,
            expected=0 if action == "grant" else granted["revision"],
            key=key if action == "grant" else uuid4(),
            proof=proof if action == "grant" else withdraw_proof,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ["grant", "withdraw"]))
    assert any(row["replayed"] for row in results)
    assert c.consent.status(c.actor, c.notice["id"])["reason"] == "withdrawn"
    assert [row["action"] for row in c.consent.history(c.actor, c.notice["id"])] == [
        "grant",
        "withdraw",
    ]


def test_consent_events_are_append_only_and_audit_failure_is_atomic(consent_context):
    c = consent_context
    proof = NoticeProof.model_validate(c.consent.present(c.actor, c.notice["id"])["notice_proof"])
    with c.store.transaction() as tx:
        before = tx.execute("SELECT count(*) AS n FROM governance_outbox").fetchone()["n"]
        tx.execute("""CREATE FUNCTION refuse_consent_audit() RETURNS trigger LANGUAGE plpgsql AS $$
                   BEGIN RAISE EXCEPTION 'synthetic failure'; END $$;
                   CREATE TRIGGER refuse_consent_audit BEFORE INSERT ON governance_audit
                   FOR EACH ROW EXECUTE FUNCTION refuse_consent_audit();""")
    with pytest.raises(GovernanceError, match="^storage_failure$"):
        command(c, "grant", proof=proof)
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT count(*) AS n FROM governance_consent_events").fetchone()["n"] == 0
        )
        assert (
            tx.execute("SELECT count(*) AS n FROM governance_subject_commands").fetchone()["n"] == 0
        )
        assert tx.execute("SELECT count(*) AS n FROM governance_outbox").fetchone()["n"] == before
        assert (
            tx.execute(
                "SELECT consumed_at FROM governance_consent_presentations WHERE presentation_id=%s",
                (proof.presentation_id,),
            ).fetchone()["consumed_at"]
            is None
        )
        tx.execute("DROP TRIGGER refuse_consent_audit ON governance_audit")
    # Reuse the unconsumed proof after the failed transaction.
    command(c, "grant", proof=proof)
    with pytest.raises(GovernanceError, match="^storage_failure$"):
        with c.store.transaction() as tx:
            tx.execute("UPDATE governance_consent_events SET action='withdraw'")


def test_identity_correction_invalidates_dependent_consent(consent_context):
    from pii_redactor.governance.subjects import SubjectLinks

    c = consent_context
    command(c, "grant")
    links = SubjectLinks(c.store)
    corrected = links.propose(
        c.a,
        uuid4(),
        subject_fixtures.link_request(source_version="v2"),
        subject_id=c.subject["subject_id"],
        expected_revision=1,
    )
    links.review(c.b, uuid4(), corrected["id"], 1, "approve", uuid4())
    with c.store.transaction() as tx:
        state = c.consent.effective(tx, c.subject["subject_id"], c.notice["id"])
    assert state["allowed"] is False and state["reason"] == "identity_changed"


def test_retired_purpose_still_allows_withdrawal_but_never_another_grant(consent_context):
    c = consent_context
    grant = command(c, "grant")
    with c.store.transaction() as tx:
        tx.execute("UPDATE governance_activities SET state='rejected',revision=revision+1")
    assert c.consent.available_notices(c.actor)["items"][0]["notice_id"] == c.notice["id"]
    shown = c.consent.present(c.actor, c.notice["id"])
    assert shown["grant_allowed"] is False
    command(c, "withdraw", expected=grant["revision"])
    with pytest.raises(GovernanceError, match="^notice_unavailable$"):
        command(c, "grant", expected=2)


def test_offline_withdrawal_needs_independent_review_and_never_claims_portal_click(consent_context):
    from datetime import UTC, datetime, timedelta

    from pii_redactor.governance.consent import OfflineConsentInput

    c = consent_context
    grant = command(c, "grant")
    request = OfflineConsentInput(
        subject_id=c.subject["subject_id"],
        scope=ConsentScope(
            purpose_version=c.notice["id"],
            categories=["CONTACT"],
            expected_revision=grant["revision"],
        ),
        action="withdraw",
        mode="offline_withdrawal",
        source_evidence_ref=uuid4(),
        source_received_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    case = c.consent.propose_offline(c.a, uuid4(), request)
    assert case["portal_act"] is False
    assert c.consent.status(c.actor, c.notice["id"])["allowed"] is True
    with pytest.raises(GovernanceError, match="forbidden|separation_required"):
        c.consent.review_offline(c.a, uuid4(), case["id"], 1, "approve", uuid4())
    reviewed = c.consent.review_offline(c.b, uuid4(), case["id"], 1, "approve", uuid4())
    assert reviewed["portal_act"] is False
    assert reviewed["channel"] == "reviewed_offline_withdrawal"
    assert (
        c.consent.history(c.actor, c.notice["id"])[-1]["channel"] == "reviewed_offline_withdrawal"
    )
    assert c.consent.status(c.actor, c.notice["id"])["reason"] == "withdrawn"


def test_representative_authority_is_required_and_not_inferred_from_staff_role():
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from pii_redactor.governance.consent import OfflineConsentInput

    with pytest.raises(ValidationError):
        OfflineConsentInput(
            subject_id=uuid4(),
            scope=ConsentScope(
                purpose_version=uuid4(), categories=["CONTACT"], expected_revision=0
            ),
            action="grant",
            mode="representative",
            source_evidence_ref=uuid4(),
            source_received_at=datetime.now(UTC),
        )


@pytest.mark.parametrize("pending_state", ["pending", "failed"])
def test_old_withdrawal_propagation_blocks_new_grant_without_database(pending_state):
    from types import SimpleNamespace

    from pii_redactor.governance.commands import digest

    purpose_id, subject_id = uuid4(), uuid4()
    activity = {"purpose": "Synthetic processing"}
    purpose = {
        "purpose_version": purpose_id,
        "activity_revision": 3,
        "activity_digest": digest(activity),
    }
    queries = iter(
        [
            SimpleNamespace(
                fetchone=lambda: {"subject_id": subject_id, "state": "resolved", "revision": 1}
            ),
            SimpleNamespace(
                fetchone=lambda: {
                    "action": "grant",
                    "link_revision": 1,
                    "revision": 3,
                    "consent_event_id": uuid4(),
                    "categories": ["CONTACT"],
                }
            ),
            SimpleNamespace(
                fetchone=lambda: {"data": activity, "review": {"notice_id": str(purpose_id)}}
            ),
            SimpleNamespace(
                fetchall=lambda: [
                    {
                        "propagation_id": uuid4(),
                        "recipient_ordinal": 1,
                        "state": pending_state,
                        "revision": 2,
                        "consent_event_id": uuid4(),
                    }
                ]
            ),
        ]
    )
    tx = SimpleNamespace(execute=lambda *args: next(queries))
    consent = Consent(SimpleNamespace(organization_id=uuid4(), lock=lambda _tx: None))
    consent._purpose = lambda *_args: purpose
    state = consent.effective(tx, subject_id, purpose_id)
    assert state["allowed"] is False
    assert state["reason"] == "propagation_" + pending_state
    assert state["revision"] == 3  # The genuine new grant remains in history.
    assert state["propagation_complete"] is False


def test_new_grant_waits_for_exact_recipient_evidence_and_scope_cannot_be_replayed(consent_context):
    from pii_redactor.governance.consent import PropagationScope

    c = consent_context
    command(c, "grant")
    command(c, "withdraw", expected=1)
    current = command(c, "grant", expected=2)
    assert current["effective"]["reason"] == "propagation_pending"
    assert c.consent.history(c.actor, c.notice["id"])[-1]["action"] == "grant"
    task = c.consent.status(c.actor, c.notice["id"])["propagation"][0]
    with pytest.raises(GovernanceError, match="^evidence_scope_required$"):
        c.consent.review_propagation(c.b, uuid4(), task["id"], "verified", uuid4())
    scope = PropagationScope(
        consent_event_id=task["consent_event_id"],
        event_revision=task["event_revision"],
        recipient_ordinal=task["recipient"],
        expected_state=task["state"],
    )
    with pytest.raises(GovernanceError, match="^revision_conflict$"):
        c.consent.review_propagation(
            c.b,
            uuid4(),
            task["id"],
            "verified",
            uuid4(),
            evidence_scope=scope.model_copy(update={"event_revision": 1}),
        )
    c.consent.review_propagation(c.b, uuid4(), task["id"], "failed", uuid4(), evidence_scope=scope)
    assert c.consent.status(c.actor, c.notice["id"])["reason"] == "propagation_failed"
    with pytest.raises(GovernanceError, match="^revision_conflict$"):
        c.consent.review_propagation(
            c.b, uuid4(), task["id"], "verified", uuid4(), evidence_scope=scope
        )
    c.consent.review_propagation(
        c.b,
        uuid4(),
        task["id"],
        "verified",
        uuid4(),
        evidence_scope=scope.model_copy(update={"expected_state": "failed"}),
    )
    assert c.consent.status(c.actor, c.notice["id"])["allowed"] is True


def test_more_than_one_hundred_eligible_notices_are_reachable_with_scoped_stable_cursor(
    consent_context,
):
    from psycopg.types.json import Jsonb

    from pii_redactor.governance.commands import digest

    c = consent_context
    with c.store.transaction() as tx:
        activity = tx.execute("SELECT * FROM governance_activities LIMIT 1").fetchone()
        for _ in range(104):
            aid, nid = uuid4(), uuid4()
            tx.execute(
                """INSERT INTO governance_activities(activity_id,organization_id,department_id,state,revision,data,
                       created_by,last_editor,submitted_by,review,reviewed_by,reviewed_at)
                       VALUES (%s,%s,'operations','active',3,%s,%s,%s,%s,%s,%s,clock_timestamp())""",
                (
                    aid,
                    c.store.organization_id,
                    Jsonb(activity["data"]),
                    c.ids[0],
                    c.ids[0],
                    c.ids[0],
                    Jsonb({"notice_id": str(nid)}),
                    c.ids[1],
                ),
            )
            notice_data = {
                "activity_id": str(aid),
                "title": "Synthetic paged notice",
                "body": "Synthetic immutable notice for pagination.",
                "language": "en",
            }
            tx.execute(
                """INSERT INTO governance_notices(notice_id,organization_id,activity_id,payload_digest,content_digest,
                       state,revision,data,created_by,published_by,published_at)
                       VALUES (%s,%s,%s,%s,%s,'published',2,%s,%s,%s,clock_timestamp())""",
                (
                    nid,
                    c.store.organization_id,
                    aid,
                    digest(activity["data"]),
                    digest(notice_data),
                    Jsonb(notice_data),
                    c.ids[0],
                    c.ids[1],
                ),
            )
    first = c.consent.available_notices(c.actor, limit=100)
    second = c.consent.available_notices(c.actor, limit=100, cursor=first["next_cursor"])
    ids = [r["notice_id"] for r in first["items"] + second["items"]]
    assert len(first["items"]) == 100 and len(second["items"]) == 5
    assert len(ids) == len(set(ids)) == 105 and second["next_cursor"] is None
    with pytest.raises(GovernanceError, match="^invalid_request$"):
        c.consent.available_notices(c.actor, cursor=uuid4())
    with pytest.raises(GovernanceError, match="^invalid_request$"):
        c.consent.available_notices(c.actor, limit=101)

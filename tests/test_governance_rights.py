"""Synthetic rights authority on a real isolated PostgreSQL database."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from pii_redactor.governance.errors import GovernanceError
from tests import governance_helpers as fixtures

database = fixtures.database
context = fixtures.context


@pytest.fixture
def rights_context(context):
    from psycopg.types.json import Jsonb

    from app.enterprise.subject_auth import SubjectIdentity, SubjectSessions
    from pii_redactor.governance.rights import Rights
    from tests.test_governance_collection import runtime
    from tests.test_governance_subjects import resolved_subject

    c = context
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles=%s WHERE member_id=%s",
            (
                Jsonb(["system_administrator", "data_steward", "case_manager", "custodian"]),
                c.ids[0],
            ),
        )
        tx.execute(
            "UPDATE governance_members SET roles=%s WHERE member_id=%s",
            (
                Jsonb(["authority_reviewer", "privacy_reviewer", "identity_steward", "custodian"]),
                c.ids[1],
            ),
        )
    c.link = resolved_subject(c)
    c.collection, c.evidence, c.execution, c.bucket, c.document = runtime(c)
    c.rights = Rights(c.store, c.collection, c.evidence, c.execution)
    c.sessions = SubjectSessions(c.store, issuer=c.a.issuer, client_id="aiguard-subject")
    c.grant = c.sessions.issue(SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject"))
    c.actor = c.sessions.resolve(c.grant.cookie)
    return c


def intake(c, rights=None):
    from pii_redactor.governance.rights import Intake

    return Intake(
        department_id="operations",
        subject_id=c.link["subject_id"],
        received_at=datetime.now(UTC) - timedelta(days=2),
        channel="offline",
        original_receipt_ref=uuid4(),
        rights=rights or ["access"],
        requester="subject",
    )


def verification(c, rights=None, **changes):
    from pii_redactor.governance.rights import ClockReview, Verification

    return Verification(
        **{
            "subject_id": c.link["subject_id"],
            "link_revision": 1,
            "complete": True,
            "completeness_ref": uuid4(),
            "identity_ref": uuid4(),
            "capacity_ref": uuid4(),
            "clocks": [
                ClockReview(
                    right=r,
                    applicability="applicable",
                    law_version="synthetic-law-v1",
                    source_ref=uuid4(),
                    rationale_ref=uuid4(),
                    anchor="original_receipt",
                    due_at=datetime.now(UTC) + timedelta(days=10),
                )
                for r in (rights or ["access"])
            ],
            **changes,
        }
    )


def verified(c, rights=None):
    row = c.rights.receive(c.a, uuid4(), intake(c, rights))
    return c.rights.verify(c.b, uuid4(), row["id"], row["revision"], verification(c, rights))


def access_plan(c, row=None, **changes):
    from pii_redactor.governance.evidence import EvidenceInput
    from pii_redactor.governance.rights import FulfilmentPlan, Target

    row = row or verified(c)
    export = c.evidence.put(
        c.a,
        uuid4(),
        EvidenceInput(
            collection_id=c.bucket["id"],
            document_id=c.document["id"],
            expected_version=1,
            content_type="text/plain",
            content="Synthetic reviewed subject-only export",
        ),
    )
    plan = FulfilmentPlan(
        targets=[
            Target(
                right="access",
                collection_id=c.bucket["id"],
                document_id=c.document["id"],
                target_revision=1,
                target_version=1,
                scope_evidence_ref=uuid4(),
                export_evidence_id=export["id"],
                third_party_review_ref=uuid4(),
            )
        ],
        manual=[],
        expires_at=datetime.now(UTC) + timedelta(hours=2),
        **changes,
    )
    return c.rights.plan(c.a, uuid4(), row["id"], row["revision"], plan)


def approved(c):
    row = access_plan(c)
    c.rights.preview(c.b, row["id"], row["revision"])
    return c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())


def test_subject_pages_reach_a_delivery_beyond_one_hundred_cases(rights_context):
    from pii_redactor.governance.delivery import Delivery

    c = rights_context
    cases = [c.rights.receive(c.a, uuid4(), intake(c)) for _ in range(105)]
    last = max(cases, key=lambda row: row["id"])
    row = c.rights.verify(c.b, uuid4(), last["id"], last["revision"], verification(c))
    row = access_plan(c, row)
    c.rights.preview(c.b, row["id"], row["revision"])
    row = c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())
    delivery = Delivery(c.rights)
    issued = delivery.issue(
        c.a,
        uuid4(),
        row["id"],
        row["revision"],
        row["plan_version"],
        datetime.now(UTC) + timedelta(minutes=10),
    )
    pages, cursor = [], None
    while True:
        page = c.rights.subject_cases(c.actor, limit=50, cursor=cursor)
        pages.append(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert list(map(len, pages)) == [50, 50, 5]
    ids = [row["id"] for page in pages for row in page]
    assert ids == sorted(set(ids)) and len(ids) == 105
    assert pages[-1][-1]["deliveries"][0]["id"] == issued["id"]
    downloaded = delivery.consume(c.actor, issued["id"])
    assert delivery.acknowledge(
        c.actor, issued["id"], downloaded["revision"], downloaded["receipt_token"]
    )["fulfilled"]


def test_subject_cursor_is_bound_to_current_session_and_link_scope(rights_context):
    from psycopg.types.json import Jsonb

    from app.enterprise.subject_auth import SubjectIdentity
    from pii_redactor.governance.subjects import SubjectLinks
    from tests.test_governance_subjects import link_request

    c = rights_context
    for _ in range(3):
        c.rights.receive(c.a, uuid4(), intake(c))
    cursor = c.rights.subject_cases(c.actor, limit=1)["next_cursor"]
    other = c.sessions.issue(SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject"))
    actor = c.sessions.resolve(other.cookie)
    with pytest.raises(GovernanceError, match="invalid_request"):
        c.rights.subject_cases(actor, limit=1, cursor=cursor)
    with pytest.raises(GovernanceError, match="invalid_request"):
        c.rights.subject_cases(c.actor, cursor=cursor[:-1] + ("0" if cursor[-1] != "0" else "1"))
    with pytest.raises(GovernanceError, match="invalid_request"):
        c.rights.subject_cases(c.actor, limit=101)
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET departments=%s WHERE member_id=ANY(%s)",
            (Jsonb(["operations", "finance"]), c.ids[:2]),
        )
    links = SubjectLinks(c.store)
    proposal = links.propose(
        c.a,
        uuid4(),
        link_request(source_version="v2", departments=["finance"]),
        subject_id=c.actor.subject_id,
        expected_revision=1,
    )
    links.review(c.b, uuid4(), proposal["id"], 1, "approve", uuid4())
    new = c.sessions.issue(SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject"))
    current = c.sessions.resolve(new.cookie)
    assert c.rights.subject_cases(current)["items"] == []
    with pytest.raises(GovernanceError, match="invalid_request"):
        c.rights.subject_cases(current, cursor=cursor)
    with pytest.raises(GovernanceError, match="authentication_required"):
        c.rights.subject_cases(c.actor)


def test_original_receipt_and_right_specific_clocks_persist_across_connections(rights_context):
    c = rights_context
    req = intake(c, ["access", "erasure"])
    row = c.rights.receive(c.a, uuid4(), req)
    v = verification(c, ["access", "erasure"])
    clocks = [
        v.clocks[0],
        v.clocks[1].model_copy(update={"due_at": None, "anchor": "reviewed_event"}),
    ]
    row = c.rights.verify(c.b, uuid4(), row["id"], 1, v.model_copy(update={"clocks": clocks}))
    assert row["intake"]["original_receipt_ref"] == str(req.original_receipt_ref)
    assert row["verification"]["clocks"][0]["due_at"] is not None
    assert row["verification"]["clocks"][1]["due_at"] is None
    assert len(row["history"]) == 2


def test_unknown_applicability_and_incompleteness_block_plan(rights_context):
    c = rights_context
    row = c.rights.receive(c.a, uuid4(), intake(c))
    v = verification(c)
    v = v.model_copy(
        update={"clocks": [v.clocks[0].model_copy(update={"applicability": "unknown"})]}
    )
    row = c.rights.verify(c.b, uuid4(), row["id"], 1, v)
    with pytest.raises(GovernanceError, match="legal_review_required"):
        access_plan(c, row)


def test_replay_scope_and_independent_review(rights_context):
    c = rights_context
    key, req = uuid4(), intake(c)
    row = c.rights.receive(c.a, key, req)
    assert c.rights.receive(c.a, key, req)["id"] == row["id"]
    with pytest.raises(GovernanceError, match="idempotency_conflict"):
        c.rights.receive(c.a, key, intake(c))
    with pytest.raises(GovernanceError, match="forbidden|record_unavailable"):
        c.rights.get(c.c, row["id"])
    with pytest.raises(GovernanceError, match="separation_required|forbidden"):
        c.rights.verify(c.a, uuid4(), row["id"], 1, verification(c))


def test_mixed_person_export_requires_actual_reviewer_preview(rights_context):
    c = rights_context
    row = access_plan(c)
    with pytest.raises(GovernanceError, match="redaction_review_required"):
        c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())
    preview = c.rights.preview(c.b, row["id"], row["revision"])
    assert "Synthetic reviewed" in preview["content"]
    assert c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())["state"] == "approved"


def test_audit_failure_rolls_back_intake(rights_context, monkeypatch):
    c = rights_context
    called = []

    def fail(*args, **kwargs):
        called.append(True)
        raise GovernanceError("synthetic_audit_failure")

    monkeypatch.setattr(c.store, "append_event", fail)
    with pytest.raises(GovernanceError, match="synthetic_audit_failure"):
        c.rights.receive(c.a, uuid4(), intake(c))
    assert called
    with c.store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_rights_cases").fetchone()["n"] == 0


def test_representative_requires_reviewed_authority_and_recipient_link(rights_context):
    c = rights_context
    req = intake(c).model_copy(update={"requester": "representative"})
    row = c.rights.receive(c.a, uuid4(), req)
    with pytest.raises(GovernanceError, match="representative_review_required"):
        c.rights.verify(c.b, uuid4(), row["id"], 1, verification(c))
    v = verification(
        c,
        representative_ref=uuid4(),
        recipient_subject_id=c.actor.subject_id,
        recipient_link_revision=1,
    )
    assert c.rights.verify(c.b, uuid4(), row["id"], 1, v)["state"] == "verified"


def test_incomplete_and_mismatched_clock_scope_are_blocked(rights_context):
    c = rights_context
    row = c.rights.receive(c.a, uuid4(), intake(c))
    with pytest.raises(GovernanceError, match="clock_scope_mismatch"):
        c.rights.verify(c.b, uuid4(), row["id"], 1, verification(c, ["erasure"]))
    row = c.rights.verify(c.b, uuid4(), row["id"], 1, verification(c, complete=False))
    with pytest.raises(GovernanceError, match="legal_review_required"):
        access_plan(c, row)


def test_stale_plan_and_changed_approver_authority_are_blocked(rights_context):
    c = rights_context
    row = access_plan(c)
    c.rights.preview(c.b, row["id"], row["revision"])
    with pytest.raises(GovernanceError, match="revision_conflict"):
        c.rights.review(c.b, uuid4(), row["id"], row["revision"] - 1, uuid4())
    row = c.rights.review(c.b, uuid4(), row["id"], row["revision"], uuid4())
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET enabled=false,revision=revision+1 WHERE member_id=%s",
            (c.ids[1],),
        )
    from pii_redactor.governance.delivery import Delivery

    with pytest.raises(GovernanceError, match="approval_authority_changed"):
        Delivery(c.rights).issue(
            c.a,
            uuid4(),
            row["id"],
            row["revision"],
            row["plan_version"],
            datetime.now(UTC) + timedelta(minutes=10),
        )


def test_portal_intake_uses_actual_actor_receipt_and_idempotency(rights_context):
    c = rights_context
    key = uuid4()
    result = c.rights.subject_receive(c.actor, key, "operations", ["access"])
    assert c.rights.subject_receive(c.actor, key, "operations", ["access"])["replayed"]
    row = c.rights.get(c.b, result["id"])
    assert row["intake"]["channel"] == "portal" and row["subject_id"] == str(c.actor.subject_id)
    with pytest.raises(GovernanceError, match="forbidden"):
        c.rights.subject_receive(c.actor, uuid4(), "finance", ["access"])
    with pytest.raises(GovernanceError, match="idempotency_conflict"):
        c.rights.subject_receive(c.actor, key, "operations", ["erasure"])


def test_unknown_or_unreviewed_extension_is_not_a_default_deadline():
    from pydantic import ValidationError

    from pii_redactor.governance.rights import ClockReview

    fields = {
        "right": "erasure",
        "applicability": "unknown",
        "law_version": "synthetic",
        "source_ref": uuid4(),
        "rationale_ref": uuid4(),
        "anchor": "reviewed_event",
    }
    assert ClockReview(**fields).due_at is None
    with pytest.raises(ValidationError):
        ClockReview(**fields, extension_until=datetime.now(UTC) + timedelta(days=30))


def test_discovery_is_scoped_advice_not_identity_or_deadline_authority(rights_context):
    c = rights_context
    row = verified(c)
    result = c.rights.advice(c.a, row["id"], c.bucket["id"])
    assert result["advice_only"] and result["dsar_match_executed"] is False
    assert result["candidates"][0]["identity_authority"] is False
    assert c.rights.get(c.a, row["id"])["revision"] == row["revision"]
    with pytest.raises(GovernanceError, match="forbidden|record_unavailable"):
        c.rights.advice(c.c, row["id"], c.bucket["id"])

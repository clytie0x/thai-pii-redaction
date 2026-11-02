"""Authoritative source identity linkage against real PostgreSQL."""

from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.subjects import SubjectLinkInput, SubjectLinks
from tests import governance_helpers as fixtures

database = fixtures.database
context = fixtures.context


@pytest.fixture
def subject_context(context):
    from psycopg.types.json import Jsonb

    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles=%s WHERE member_id=%s",
            (Jsonb(["system_administrator", "data_steward", "case_manager"]), context.ids[0]),
        )
        tx.execute(
            "UPDATE governance_members SET roles=%s WHERE member_id=%s",
            (Jsonb(["authority_reviewer", "privacy_reviewer", "identity_steward"]), context.ids[1]),
        )
    return context


def link_request(**changes):
    return SubjectLinkInput(
        **{
            "issuer": "https://idp.example.test/realms/staff",
            "oidc_subject": "synthetic-customer",
            "source_system": "synthetic-crm",
            "source_record_id": uuid4(),
            "source_version": "v1",
            "departments": ["operations"],
            "identity_evidence_ref": uuid4(),
            "capacity_evidence_ref": uuid4(),
            **changes,
        }
    )


def resolved_subject(context):
    links = SubjectLinks(context.store)
    result = links.propose(context.a, uuid4(), link_request())
    return links.review(context.b, uuid4(), result["id"], 1, "approve", uuid4())


def test_link_requires_distinct_current_identity_review_and_exact_source(subject_context):
    c = subject_context
    links = SubjectLinks(c.store)
    proposal = links.propose(c.a, uuid4(), link_request())
    with pytest.raises(GovernanceError, match="forbidden|separation_required"):
        links.review(c.a, uuid4(), proposal["id"], 1, "approve", uuid4())
    reviewed = links.review(c.b, uuid4(), proposal["id"], 1, "approve", uuid4())
    assert reviewed["state"] == "active"
    assert links.get(c.b, reviewed["id"])["subject_id"] == reviewed["subject_id"]
    with pytest.raises(GovernanceError, match="forbidden|record_unavailable"):
        links.get(c.c, reviewed["id"])


def test_conflicting_source_and_oidc_identity_cannot_merge_subjects(subject_context):
    c = subject_context
    links = SubjectLinks(c.store)
    request = link_request()
    proposal = links.propose(c.a, uuid4(), request)
    links.review(c.b, uuid4(), proposal["id"], 1, "approve", uuid4())
    with pytest.raises(GovernanceError, match="^identity_conflict$"):
        links.propose(
            c.a,
            uuid4(),
            link_request(
                source_record_id=request.source_record_id, oidc_subject="other-synthetic-customer"
            ),
        )


def test_no_name_or_phone_similarity_inputs_can_authorize_a_link():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        link_request(name="synthetic-name", phone="synthetic-phone")


def test_corrected_link_revokes_old_session_and_never_reuses_old_consent(subject_context):
    from app.enterprise.subject_auth import SubjectIdentity, SubjectSessions

    c = subject_context
    old = resolved_subject(c)
    sessions = SubjectSessions(c.store, issuer=c.a.issuer, client_id="aiguard-subject")
    grant = sessions.issue(SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject"))
    assert sessions.resolve(grant.cookie).link_revision == 1
    links = SubjectLinks(c.store)
    correction = links.propose(
        c.a,
        uuid4(),
        link_request(source_version="v2"),
        subject_id=old["subject_id"],
        expected_revision=1,
    )
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        sessions.resolve(grant.cookie)
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        sessions.issue(SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject"))
    assert links.review(c.b, uuid4(), correction["id"], 1, "approve", uuid4())["link_revision"] == 2
    assert (
        sessions.resolve(
            sessions.issue(
                SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject")
            ).cookie
        ).link_revision
        == 2
    )


def test_cross_department_link_requires_distinct_privacy_review(subject_context):
    from psycopg.types.json import Jsonb

    c = subject_context
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET departments=%s WHERE member_id=ANY(%s)",
            (Jsonb(["operations", "finance"]), [c.ids[0], c.ids[1]]),
        )
        tx.execute(
            "UPDATE governance_members SET roles=%s,departments=%s WHERE member_id=%s",
            (Jsonb(["privacy_reviewer"]), Jsonb(["operations", "finance"]), c.ids[2]),
        )
    links = SubjectLinks(c.store)
    proposal = links.propose(c.a, uuid4(), link_request(departments=["operations", "finance"]))
    reviewed = links.review(c.b, uuid4(), proposal["id"], 1, "approve", uuid4())
    assert reviewed["state"] == "awaiting_privacy"
    with pytest.raises(GovernanceError, match="^separation_required$"):
        links.review(
            c.b, uuid4(), proposal["id"], reviewed["revision"], "approve", uuid4(), privacy=True
        )
    assert (
        links.review(
            c.c, uuid4(), proposal["id"], reviewed["revision"], "approve", uuid4(), privacy=True
        )["state"]
        == "active"
    )


def test_revoked_proposer_and_in_place_identity_change_are_denied(subject_context):
    c = subject_context
    links = SubjectLinks(c.store)
    proposal = links.propose(c.a, uuid4(), link_request())
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s", (c.ids[0],)
        )
    with pytest.raises(GovernanceError, match="^proposal_authority_expired$"):
        links.review(c.b, uuid4(), proposal["id"], 1, "approve", uuid4())
    with pytest.raises(GovernanceError, match="^storage_failure$"):
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_subject_links SET oidc_subject='other-synthetic' WHERE link_id=%s",
                (proposal["id"],),
            )


def test_scoped_link_retry_is_idempotent_and_changed_identity_conflicts(subject_context):
    c = subject_context
    links, key, request = SubjectLinks(c.store), uuid4(), link_request()
    first = links.propose(c.a, key, request)
    assert links.propose(c.a, key, request) == first
    changed = request.model_copy(update={"oidc_subject": "changed-synthetic"})
    with pytest.raises(GovernanceError, match="^idempotency_conflict$"):
        links.propose(c.a, key, changed)

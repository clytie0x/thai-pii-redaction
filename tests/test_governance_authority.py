from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
from tests import governance_helpers as fixtures

context = fixtures.context
database = fixtures.database


def test_department_scope_and_current_membership_are_authoritative(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError

    authority = Authority(context.store)
    with context.store.transaction() as tx:
        assert (
            authority.require(tx, context.a, "activity.create", "operations")["member_id"]
            == context.ids[0]
        )
        with pytest.raises(GovernanceError, match="forbidden"):
            authority.require(tx, context.a, "activity.create", "finance")
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET enabled=false WHERE member_id=%s", (context.ids[0],)
        )
    with (
        context.store.transaction() as tx,
        pytest.raises(GovernanceError, match="authentication_required"),
    ):
        authority.require(tx, context.a, "activity.create", "operations")


def test_privileged_grant_needs_distinct_authorized_approver(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError

    authority = Authority(context.store)
    proposal = authority.propose_grant(
        context.a, uuid4(), context.ids[1], ["auditor"], ["operations"]
    )
    for forbidden_approver in [context.a, context.b]:
        with pytest.raises(GovernanceError, match="separation_required"):
            authority.approve_grant(forbidden_approver, uuid4(), proposal["id"], 1)
    result = authority.approve_grant(context.d, uuid4(), proposal["id"], 1)
    assert result["state"] == "applied"
    with context.store.transaction() as tx:
        member = tx.execute(
            "SELECT roles, revision FROM governance_members WHERE member_id=%s", (context.ids[1],)
        ).fetchone()
    assert member["roles"] == ["auditor"] and member["revision"] == 2


def test_grant_cannot_be_approved_after_target_revision_changes(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError

    authority = Authority(context.store)
    proposal = authority.propose_grant(
        context.a, uuid4(), context.ids[1], ["auditor"], ["operations"]
    )
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s",
            (context.ids[1],),
        )
    with pytest.raises(GovernanceError, match="revision_conflict"):
        authority.approve_grant(context.d, uuid4(), proposal["id"], 1)


def test_new_staff_stays_disabled_until_independent_enrollment_approval(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.models import Enrollment, Principal

    authority = Authority(context.store)
    new = Enrollment(
        principal=Principal(issuer=context.a.issuer, subject="new-staff"),
        roles=["data_steward"],
        departments=["operations"],
    )
    proposal = authority.propose_enrollment(context.a, uuid4(), new)
    with (
        context.store.transaction() as tx,
        pytest.raises(GovernanceError, match="authentication_required"),
    ):
        authority.require(tx, new.principal, "activity.create", "operations")
    authority.approve_grant(context.b, uuid4(), proposal["id"], 1)
    with context.store.transaction() as tx:
        assert (
            authority.require(tx, new.principal, "activity.create", "operations")["enabled"] is True
        )


def test_admin_role_alone_does_not_allow_processing_review(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError

    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles='[\"system_administrator\"]'::jsonb WHERE member_id=%s",
            (context.ids[0],),
        )
    with context.store.transaction() as tx, pytest.raises(GovernanceError, match="forbidden"):
        Authority(context.store).require(tx, context.a, "activity.review", "operations")


def test_suspension_is_immediate_but_reactivation_requires_review(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError

    authority = Authority(context.store)
    authority.suspend_member(context.a, uuid4(), context.ids[1], 1)
    with (
        context.store.transaction() as tx,
        pytest.raises(GovernanceError, match="authentication_required"),
    ):
        authority.require(tx, context.b, "activity.review", "operations")
    proposal = authority.propose_grant(
        context.a,
        uuid4(),
        context.ids[1],
        ["authority_reviewer", "privacy_reviewer", "auditor"],
        ["operations"],
        enabled=True,
    )
    with (
        context.store.transaction() as tx,
        pytest.raises(GovernanceError, match="authentication_required"),
    ):
        authority.require(tx, context.b, "activity.review", "operations")
    authority.approve_grant(context.d, uuid4(), proposal["id"], 1)
    with context.store.transaction() as tx:
        assert authority.require(tx, context.b, "activity.review", "operations")["enabled"]


def test_last_administrator_cannot_be_removed_by_a_role_change(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError

    authority = Authority(context.store)
    proposal = authority.propose_grant(
        context.a, uuid4(), context.ids[0], ["auditor"], ["operations"]
    )
    with pytest.raises(GovernanceError, match="authority_unavailable"):
        authority.approve_grant(context.b, uuid4(), proposal["id"], 1)
    with context.store.transaction() as tx:
        roles = tx.execute(
            "SELECT roles FROM governance_members WHERE member_id=%s", (context.ids[0],)
        ).fetchone()["roles"]
        assert "system_administrator" in roles


def test_enrollment_retry_rechecks_current_department_scope(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.models import Enrollment, Principal

    authority = Authority(context.store)
    request = Enrollment(
        principal=Principal(issuer=context.a.issuer, subject="another-new-staff"),
        roles=["auditor"],
        departments=["operations"],
    )
    key = uuid4()
    authority.propose_enrollment(context.a, key, request)
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET departments='[\"finance\"]'::jsonb WHERE member_id=%s",
            (context.ids[0],),
        )
    with pytest.raises(GovernanceError, match="forbidden"):
        authority.propose_enrollment(context.a, key, request)


def test_membership_and_grant_views_are_scoped_to_the_reviewer(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError

    authority = Authority(context.store)
    members = authority.list_members(context.a)
    assert {m["id"] for m in members} == {str(context.ids[i]) for i in [0, 1, 3]}
    proposal = authority.propose_grant(
        context.a, uuid4(), context.ids[1], ["auditor"], ["operations"]
    )
    visible = authority.get_grant(context.d, proposal["id"])
    assert visible["roles"] == ["auditor"] and visible["target_id"] == str(context.ids[1])
    assert [g["id"] for g in authority.list_grants(context.d)] == [proposal["id"]]
    with pytest.raises(GovernanceError, match="forbidden"):
        authority.list_members(context.c)


def test_revoked_proposer_authority_invalidates_a_pending_grant(context):
    from pii_redactor.governance.authority import Authority
    from pii_redactor.governance.errors import GovernanceError

    authority = Authority(context.store)
    proposal = authority.propose_grant(
        context.a,
        uuid4(),
        context.ids[1],
        ["authority_reviewer", "privacy_reviewer", "auditor", "case_manager"],
        ["operations"],
    )
    with context.store.transaction() as tx:
        tx.execute(
            'UPDATE governance_members SET roles=\'["system_administrator","data_steward"]\'::jsonb WHERE member_id=%s',
            (context.ids[2],),
        )
        tx.execute(
            "UPDATE governance_members SET enabled=false,revision=revision+1 WHERE member_id=%s",
            (context.ids[0],),
        )
    with pytest.raises(GovernanceError, match="proposal_authority_expired"):
        authority.approve_grant(context.d, uuid4(), proposal["id"], 1)

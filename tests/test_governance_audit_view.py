"""Audit readers receive minimized events only inside their authorized scope."""

from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.audit_view import AuditView
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.registry import Registry
from tests import governance_helpers
from tests.test_governance_registry import activity

context = governance_helpers.context
database = governance_helpers.database


def test_department_auditor_cannot_enumerate_other_department_events(context):
    registry = Registry(context.store)
    own = registry.create_activity(context.a, uuid4(), activity())
    foreign = registry.create_activity(context.c, uuid4(), activity(department_id="finance"))
    events = AuditView(context.store).list_events(context.b)
    assert {e["target_id"] for e in events} == {own["id"]}
    assert foreign["id"] not in str(events) and own["data"]["title"] not in str(events)
    assert all("details" not in e and "subject" not in e for e in events)


def test_admin_has_no_implicit_audit_permission(context):
    with pytest.raises(GovernanceError, match="^forbidden$"):
        AuditView(context.store).list_events(context.a)


def test_global_auditor_can_read_integrity_fields_without_values(context):
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET departments='[\"*\"]'::jsonb WHERE member_id=%s",
            (context.ids[1],),
        )
    events = AuditView(context.store).list_events(context.b)
    assert len(events) == 1 and events[0]["event_code"] == "organization.enrolled"
    assert len(events[0]["event_hash"]) == 64 and len(events[0]["previous_hash"]) == 64


@pytest.mark.parametrize(
    "options",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": True}],
    ids=["zero", "large", "negative", "boolean"],
)
def test_audit_pagination_is_bounded(context, options):
    with pytest.raises(GovernanceError, match="^invalid_request$"):
        AuditView(context.store).list_events(context.b, **options)

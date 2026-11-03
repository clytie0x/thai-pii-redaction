"""Minimized audit views; department scope covers activity and notice events."""

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.permissions import require_member


class AuditView:
    def __init__(self, store):
        self.store = store

    def list_events(self, principal, *, limit=100, offset=0):
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(offset) is not int
            or not 0 <= offset <= 10000
        ):
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "audit.read")
            rows = tx.execute(
                """SELECT a.sequence,a.event_id,a.event_code,a.actor_id,a.target_id,
                    a.record_revision,a.occurred_at,a.event_hash,a.previous_hash
                FROM governance_audit a WHERE a.organization_id=%s AND (
                    %s OR EXISTS(SELECT 1 FROM governance_activities r
                        WHERE r.activity_id=a.target_id AND r.organization_id=a.organization_id
                        AND r.department_id=ANY(%s))
                    OR EXISTS(SELECT 1 FROM governance_notices n
                        JOIN governance_activities r ON r.activity_id=n.activity_id
                        WHERE n.notice_id=a.target_id AND r.organization_id=a.organization_id
                        AND r.department_id=ANY(%s)))
                ORDER BY a.sequence DESC LIMIT %s OFFSET %s""",
                (
                    self.store.organization_id,
                    "*" in member["departments"],
                    member["departments"],
                    member["departments"],
                    limit,
                    offset,
                ),
            ).fetchall()
            return [
                {
                    key: value.isoformat()
                    if key == "occurred_at"
                    else str(value)
                    if key in {"event_id", "actor_id", "target_id"} and value is not None
                    else value
                    for key, value in row.items()
                }
                for row in rows
            ]

"""Current membership, explicit permissions and department scope."""

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Principal

PERMISSIONS = {
    "activity.create": {"data_steward"},
    "activity.update": {"data_steward"},
    "activity.submit": {"data_steward"},
    "activity.review": {"privacy_reviewer"},
    "activity.read": {"data_steward", "privacy_reviewer", "case_manager", "custodian"},
    "notice.create": {"data_steward"},
    "notice.publish": {"privacy_reviewer"},
    "membership.propose": {"system_administrator"},
    "membership.approve": {"authority_reviewer"},
    "membership.suspend": {"system_administrator"},
    "membership.read": {"system_administrator", "authority_reviewer"},
    "audit.read": {"auditor"},
}


def require_member(tx, organization_id, principal: Principal, permission, department_id=None):
    if permission not in PERMISSIONS or not isinstance(principal, Principal):
        raise GovernanceError("forbidden")
    member = tx.execute(
        """
        SELECT * FROM governance_members
        WHERE organization_id=%s AND issuer=%s AND subject=%s AND enabled
        FOR SHARE
    """,
        (organization_id, principal.issuer, principal.subject),
    ).fetchone()
    if not member:
        raise GovernanceError("authentication_required")
    if not PERMISSIONS[permission].intersection(member["roles"]):
        raise GovernanceError("forbidden")
    if department_id is not None and not in_scope(member, department_id):
        raise GovernanceError("forbidden")
    return member


def in_scope(member, department_id):
    return "*" in member["departments"] or department_id in member["departments"]

"""Closed enrollment input must not invent roles or normalize identity."""

import pytest
from pydantic import ValidationError


def test_identity_is_exact_and_unknown_identity_fields_are_rejected():
    from pii_redactor.governance.models import Principal

    principal = Principal(issuer="https://idp.example.test/staff/", subject="Staff-A")
    assert principal.issuer.endswith("/") and principal.subject == "Staff-A"
    with pytest.raises(ValidationError):
        Principal(issuer=principal.issuer, subject=principal.subject, role="privacy_reviewer")


@pytest.mark.parametrize(
    "issuer,subject",
    [
        ("http://outside.example.test", "person"),
        ("https://user:pass@idp.example.test", "person"),
        ("https://idp.example.test?redirect=elsewhere", "person"),
        ("https://idp.example.test", "person\nforged"),
        ("https://idp.example.test", ""),
    ],
)
def test_invalid_principal_does_not_enter_authority_store(issuer, subject):
    from pii_redactor.governance.models import Principal

    with pytest.raises(ValidationError):
        Principal(issuer=issuer, subject=subject)


@pytest.mark.parametrize(
    "roles,departments",
    [
        (["root"], ["operations"]),
        (["auditor", "auditor"], ["operations"]),
        (["auditor"], []),
        (["auditor"], ["*", "operations"]),
        (["auditor"], ["operations", "operations"]),
        ([], ["operations"]),
    ],
)
def test_enrollment_requires_explicit_unique_roles_and_scope(roles, departments):
    from pii_redactor.governance.models import Enrollment, Principal

    with pytest.raises(ValidationError):
        Enrollment(
            principal=Principal(issuer="https://idp.example.test/staff", subject="staff-a"),
            roles=roles,
            departments=departments,
        )

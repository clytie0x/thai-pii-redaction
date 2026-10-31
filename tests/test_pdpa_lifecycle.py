import pytest


def test_closed_context_rejects_unknown_fields_and_boolean_strings():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    with pytest.raises(ValueError):
        plan_lifecycle({"private_name": "synthetic-person"})
    with pytest.raises(ValueError):
        plan_lifecycle({"basis_reviewed": "false"})


def test_contract_is_not_mistaken_for_missing_consent():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle(
        {"purpose_specified": True, "basis": "contract", "basis_reviewed": True}
    )
    assert "obtain_consent" not in result["actions"]
    assert result["execution"] == "none"
    assert result["legal_clearance"] is False


def test_sensitive_condition_is_separate_from_general_contract_basis():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle(
        {"purpose_specified": True, "basis": "contract", "basis_reviewed": True}, sensitive=True
    )
    assert "review_section26_condition" in result["actions"]


def test_withdrawal_does_not_silently_switch_basis_or_delete_held_records():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle(
        {"basis": "consent", "consent": "withdrawn", "legal_hold": True, "hold_reviewed": True}
    )
    assert "stop_consent_processing" in result["actions"]
    assert "retain_restricted_hold" in result["actions"]
    assert "delete_now" not in result["actions"]


def test_access_and_erasure_use_different_clock_origins():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    common = {"received_on": "2026-10-01", "complete_on": "2026-10-10", "identity_verified": True}
    access = plan_lifecycle({**common, "right": "access"})
    erasure = plan_lifecycle({**common, "right": "erasure", "right_qualified": True})
    assert any(
        d["event"] == "access_fulfilment" and d["calendar_anchor"] == "2026-11-09"
        for d in access["deadlines"]
    )
    assert any(
        d["event"] == "erasure_response" and d["calendar_anchor"] == "2026-12-30"
        for d in erasure["deadlines"]
    )


def test_unlawful_erasure_cannot_substitute_anonymization():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle(
        {
            "right": "erasure",
            "identity_verified": True,
            "right_qualified": True,
            "unlawful_processing": True,
        }
    )
    assert "propose_delete_or_destroy" in result["actions"]
    assert "propose_anonymization" not in result["actions"]


def test_other_rights_get_no_invented_thirty_day_deadline():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle(
        {"right": "portability", "identity_verified": True, "received_on": "2026-10-01"}
    )
    assert not any(d["days"] == 30 for d in result["deadlines"])
    assert "review_right_scope_and_deadline" in result["actions"]


def test_expired_retention_requires_disposal_review_including_copies():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle({"as_of": "2026-10-31", "retention_until": "2026-10-01"})
    assert {"propose_retention_disposal", "cover_processors_and_backups"} <= set(result["actions"])


def test_verified_qualified_portability_and_rectification_have_specific_plans():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    portable = plan_lifecycle(
        {"right": "portability", "identity_verified": True, "right_qualified": True}
    )
    rectify = plan_lifecycle({"right": "rectification", "identity_verified": True})
    assert "propose_machine_readable_portability_export" in portable["actions"]
    assert "propose_verify_and_correct_records" in rectify["actions"]
    assert portable["execution"] == rectify["execution"] == "none"


def test_sensitive_consent_withdrawal_is_separate_from_contract_basis():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle(
        {
            "basis": "contract",
            "basis_reviewed": True,
            "s26_condition": "explicit_consent",
            "s26_reviewed": True,
            "consent": "withdrawn",
        },
        sensitive=True,
    )
    assert "stop_sensitive_consent_processing" in result["actions"]


def test_unqualified_erasure_keeps_the_conditional_receipt_clock_visible():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle({"right": "erasure", "received_on": "2026-10-01"})
    assert any(
        d["event"] == "erasure_response" and d["calendar_anchor"] == "2026-12-30"
        for d in result["deadlines"]
    )


def test_overdue_hold_review_does_not_silently_authorize_disposal():
    from pii_redactor.pdpa_lifecycle import plan_lifecycle

    result = plan_lifecycle(
        {
            "legal_hold": True,
            "hold_reviewed": True,
            "hold_review_on": "2026-10-01",
            "as_of": "2026-10-31",
        }
    )
    assert "review_hold_ground_and_expiry" in result["actions"]
    assert "propose_retention_disposal" not in result["actions"]

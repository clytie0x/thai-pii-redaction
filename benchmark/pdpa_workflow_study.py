"""Visible hand-authored policy scenarios, not independent legal accuracy."""

import argparse
import json
from pathlib import Path

from pii_redactor.pdpa_catalog import LAW_VERSION, SOURCES
from pii_redactor.pdpa_lifecycle import plan_lifecycle


def scenarios():
    return [
        (
            "unspecified",
            {},
            False,
            {"specify_and_minimize_purpose", "review_general_legal_basis"},
            set(),
        ),
        (
            "contract_no_consent",
            {"purpose_specified": True, "basis": "contract", "basis_reviewed": True},
            False,
            set(),
            {"obtain_consent"},
        ),
        (
            "consent_missing",
            {"basis": "consent"},
            False,
            {"obtain_consent", "verify_scoped_consent_evidence_and_version"},
            set(),
        ),
        (
            "withdrawn",
            {"basis": "consent", "consent": "withdrawn"},
            False,
            {"stop_consent_processing", "propagate_withdrawal_by_purpose"},
            {"assume_processing_allowed"},
        ),
        (
            "refused",
            {"basis": "consent", "consent": "refused"},
            False,
            {"stop_consent_processing"},
            {"assume_processing_allowed"},
        ),
        (
            "capacity_unknown",
            {"basis": "consent", "consent": "active"},
            False,
            {"review_capacity_and_representative"},
            {"assume_processing_allowed"},
        ),
        (
            "sensitive_contract",
            {"basis": "contract", "basis_reviewed": True},
            True,
            {"review_section26_condition"},
            {"assume_processing_allowed"},
        ),
        (
            "sensitive_exception",
            {
                "basis": "legal_obligation",
                "basis_reviewed": True,
                "s26_condition": "legal_claims",
                "s26_reviewed": True,
            },
            True,
            set(),
            {"obtain_consent", "review_section26_condition"},
        ),
        (
            "expired",
            {"as_of": "2026-10-31", "retention_until": "2026-10-01"},
            False,
            {"propose_retention_disposal", "cover_processors_and_backups"},
            set(),
        ),
        (
            "future",
            {"as_of": "2026-10-31", "retention_until": "2027-10-01"},
            False,
            set(),
            {"propose_retention_disposal"},
        ),
        (
            "expired_hold",
            {"as_of": "2026-10-31", "retention_until": "2026-10-01", "legal_hold": True},
            False,
            {"retain_restricted_hold", "review_hold_ground_and_expiry"},
            {"propose_retention_disposal"},
        ),
        (
            "access_identity",
            {"right": "access", "received_on": "2026-10-01"},
            False,
            {"verify_subject_or_authority", "retain_access_evidence_at_least_2_years"},
            set(),
        ),
        (
            "access_extension_review",
            {"right": "access", "access_extension": True},
            False,
            {"review_extension_reason_and_notice"},
            set(),
        ),
        (
            "erasure_identity",
            {"right": "erasure", "right_qualified": True},
            False,
            {"verify_subject_or_authority"},
            {"propose_delete_or_destroy"},
        ),
        (
            "unlawful_erasure",
            {
                "right": "erasure",
                "identity_verified": True,
                "right_qualified": True,
                "unlawful_processing": True,
            },
            False,
            {"propose_delete_or_destroy", "cover_processors_and_backups"},
            {"propose_anonymization"},
        ),
        (
            "erasure_hold",
            {
                "right": "erasure",
                "identity_verified": True,
                "right_qualified": True,
                "legal_hold": True,
            },
            False,
            {"review_erasure_hold_conflict", "retain_restricted_hold"},
            {"propose_delete_or_destroy"},
        ),
        (
            "portability",
            {"right": "portability", "identity_verified": True, "right_qualified": True},
            False,
            {"propose_machine_readable_portability_export"},
            set(),
        ),
        (
            "rectification",
            {"right": "rectification", "identity_verified": True},
            False,
            {
                "propose_verify_and_correct_records",
                "propagate_correction_to_processors_and_restores",
            },
            set(),
        ),
        (
            "objection",
            {"right": "objection"},
            False,
            {"propose_segregation_pending_objection_review", "review_right_scope_and_deadline"},
            set(),
        ),
        (
            "restriction",
            {"right": "restriction"},
            False,
            {"propose_restriction_pending_review"},
            set(),
        ),
    ]


def evaluate_workflows():
    methods = {
        name: {"passed": 0, "missing_required": 0, "forbidden_suggestions": 0}
        for name in ("uniform_consent", "manual_only", "basis_lifecycle")
    }
    cases = scenarios()
    for _, context, sensitive, required, forbidden in cases:
        proposals = {
            "uniform_consent": {"assume_processing_allowed"}
            if context.get("consent") == "active"
            else {"obtain_consent"},
            "manual_only": {"manual_review"},
            "basis_lifecycle": set(plan_lifecycle(context, sensitive=sensitive)["actions"]),
        }
        for name, actions in proposals.items():
            missing = len(required - actions)
            bad = len(forbidden & actions)
            methods[name]["missing_required"] += missing
            methods[name]["forbidden_suggestions"] += bad
            methods[name]["passed"] += int(missing == 0 and bad == 0)
    return {
        "schema": "pdpa-workflow-scenarios/1",
        "rule_version": LAW_VERSION,
        "cases": len(cases),
        "methods": methods,
        "execution": "none",
        "sources": SOURCES,
        "limits": "Hand-authored functional requirements, not independent legal outcome accuracy. Weak policies are experimental comparisons only.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate_workflows()
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result["methods"], indent=2))


if __name__ == "__main__":
    main()

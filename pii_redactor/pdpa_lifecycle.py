"""Pure lifecycle proposals. Caller declarations are not verified legal evidence."""

from datetime import date, timedelta

from pii_redactor.pdpa_catalog import LAW_VERSION, SOURCES

_ENUMS = {
    "basis": {
        "consent",
        "contract",
        "legal_obligation",
        "vital_interests",
        "public_task",
        "legitimate_interests",
        "research_archiving",
    },
    "consent": {"active", "withdrawn", "refused", "unknown"},
    "capacity": {"reviewed", "needs_review", "unknown"},
    "s26_condition": {
        "explicit_consent",
        "vital_interests",
        "nonprofit_internal",
        "manifestly_public",
        "legal_claims",
        "medical",
        "public_health",
        "employment_social_protection",
        "research_statistics",
        "substantial_public_interest",
    },
    "right": {
        "access",
        "erasure",
        "portability",
        "objection",
        "restriction",
        "rectification",
        "withdrawal",
    },
}
_BOOLS = {
    "sensitive_data",
    "purpose_specified",
    "basis_reviewed",
    "s26_reviewed",
    "notice_recorded",
    "legal_hold",
    "hold_reviewed",
    "identity_verified",
    "right_qualified",
    "unlawful_processing",
    "access_extension",
    "extension_reviewed",
    "extension_notice_recorded",
}
_DATES = {"as_of", "received_on", "complete_on", "retention_until", "hold_review_on"}


def validate_context(context: dict | None) -> dict:
    if context is None:
        return {}
    if not isinstance(context, dict) or set(context) - set(_ENUMS) - _BOOLS - _DATES:
        raise ValueError("invalid lifecycle context")
    result = dict(context)
    for key, value in result.items():
        if key in _BOOLS and type(value) is not bool:
            raise ValueError("invalid lifecycle boolean")
        if key in _ENUMS and (not isinstance(value, str) or value not in _ENUMS[key]):
            raise ValueError("invalid lifecycle choice")
        if key in _DATES:
            try:
                parsed = date.fromisoformat(value) if isinstance(value, str) else None
            except ValueError:
                raise ValueError("invalid lifecycle date") from None
            if parsed is None or parsed.isoformat() != value:
                raise ValueError("invalid lifecycle date")
    if (
        result.get("complete_on")
        and result.get("received_on")
        and result["complete_on"] < result["received_on"]
    ):
        raise ValueError("invalid lifecycle chronology")
    return result


def plan_lifecycle(
    context: dict | None = None, *, sensitive: bool = False, unsupported: bool = False
) -> dict:
    c = validate_context(context)
    sensitive = bool(sensitive or c.get("sensitive_data") or c.get("s26_condition"))
    actions = set()
    deadlines = []

    def deadline(event, days, origin):
        value = c.get(origin)
        anchor = (date.fromisoformat(value) + timedelta(days=days)).isoformat() if value else None
        deadlines.append(
            {
                "event": event,
                "days": days,
                "origin": origin,
                "calendar_anchor": anchor,
                "status": "indicative_requires_controller_review",
            }
        )

    if not c.get("purpose_specified"):
        actions.add("specify_and_minimize_purpose")
    if not c.get("basis") or not c.get("basis_reviewed"):
        actions.add("review_general_legal_basis")
    if not c.get("notice_recorded"):
        actions.add("review_notice_and_recipients")
    if c.get("basis") == "consent":
        if c.get("consent") in {"withdrawn", "refused"}:
            actions.update({"stop_consent_processing", "propagate_withdrawal_by_purpose"})
        elif c.get("consent") != "active":
            actions.add("obtain_consent")
        if c.get("capacity") != "reviewed":
            actions.add("review_capacity_and_representative")
        actions.add("verify_scoped_consent_evidence_and_version")
    if sensitive and (not c.get("s26_condition") or not c.get("s26_reviewed")):
        actions.add("review_section26_condition")
    if sensitive and c.get("s26_condition") == "explicit_consent":
        actions.add("verify_sensitive_scoped_consent_evidence")
        if c.get("consent") != "active":
            actions.add("stop_sensitive_consent_processing")
        if c.get("capacity") != "reviewed":
            actions.add("review_capacity_and_representative")
    if unsupported:
        actions.add("review_unsupported_data_modality")
    if c.get("legal_hold"):
        actions.add("retain_restricted_hold")
        if (
            not c.get("hold_reviewed")
            or not c.get("hold_review_on")
            or (c.get("as_of") and c.get("hold_review_on") and c["as_of"] >= c["hold_review_on"])
        ):
            actions.add("review_hold_ground_and_expiry")
    if not c.get("retention_until"):
        actions.add("define_purpose_specific_retention")
    elif c.get("as_of") and c["as_of"] >= c["retention_until"] and not c.get("legal_hold"):
        actions.update(
            {
                "propose_retention_disposal",
                "cover_processors_and_backups",
                "prevent_restoration_of_disposed_records",
            }
        )
    elif not c.get("as_of"):
        actions.add("review_retention_clock")
    right = c.get("right")
    if right:
        actions.update(
            {"record_rights_request_and_evidence", "review_third_party_and_statutory_exceptions"}
        )
        if not c.get("identity_verified"):
            actions.add("verify_subject_or_authority")
        if right == "access":
            deadline("access_initial_check", 15, "received_on")
            origin = "complete_on" if c.get("complete_on") else "received_on"
            deadline("access_fulfilment", 30, origin)
            actions.update(
                {
                    "provide_correction_window_at_least_10_days_if_needed",
                    "retain_access_evidence_at_least_2_years",
                    "review_access_clock_completeness_and_channels",
                }
            )
            if c.get("access_extension"):
                if c.get("extension_reviewed") and c.get("extension_notice_recorded"):
                    deadline("access_extended_fulfilment_maximum", 60, origin)
                else:
                    actions.add("review_extension_reason_and_notice")
            if c.get("identity_verified"):
                actions.add("propose_scoped_access_and_secure_delivery")
        elif right == "erasure":
            deadline("erasure_response", 90, "received_on")
            if not c.get("right_qualified"):
                actions.add("review_erasure_qualification_and_deadline")
            if c.get("legal_hold"):
                actions.add("review_erasure_hold_conflict")
            elif c.get("identity_verified") and c.get("right_qualified"):
                actions.update(
                    {"cover_processors_and_backups", "prevent_restoration_of_disposed_records"}
                )
                actions.add(
                    "propose_delete_or_destroy"
                    if c.get("unlawful_processing")
                    else "review_delete_destroy_or_anonymize_options"
                )
        elif right == "withdrawal":
            actions.add("review_withdrawal_scope_and_remaining_purposes")
            if c.get("identity_verified"):
                actions.add("propose_record_scoped_withdrawal")
                if c.get("basis") == "consent":
                    actions.add("stop_consent_processing")
                if sensitive and c.get("s26_condition") == "explicit_consent":
                    actions.add("stop_sensitive_consent_processing")
        else:
            actions.add("review_right_scope_and_deadline")
            if right == "portability":
                actions.add("review_automated_processing_and_portable_data_scope")
                if c.get("identity_verified") and c.get("right_qualified"):
                    actions.add("propose_machine_readable_portability_export")
            if right == "rectification" and c.get("identity_verified"):
                actions.update(
                    {
                        "propose_verify_and_correct_records",
                        "propagate_correction_to_processors_and_restores",
                    }
                )
            if right == "objection":
                actions.add("propose_segregation_pending_objection_review")
            if right == "restriction":
                actions.add("propose_restriction_pending_review")
    return {
        "schema": "aiguard.pdpa-lifecycle/1",
        "mode": "planning_only",
        "legal_clearance": False,
        "execution": "none",
        "human_approval_required": True,
        "assumptions": "caller_declarations_not_verified",
        "rule_version": LAW_VERSION,
        "actions": sorted(actions),
        "deadlines": deadlines,
        "sources": SOURCES,
        "clock_limits": "Calendar anchors only; applicable scope, nonworking days and actual receipt require review.",
    }

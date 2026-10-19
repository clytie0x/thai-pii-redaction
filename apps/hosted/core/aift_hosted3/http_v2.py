"""Additive HTTP-contract-2 metadata owned by the Hosted 3.0 overlay."""

from __future__ import annotations

from dataclasses import dataclass

SERVER_TIME_HEADER = b"x-aiguard-server-time-ms"
SESSION_EXPIRES_HEADER = b"x-aiguard-session-expires-at-ms"
SERVICE_CLASS_HEADER = b"x-aiguard-service-class"
CONTRACT_VERSION = 2


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    status: int
    category: str
    retryable: bool


ERROR_SPECS = {
    "contract_version_required": ErrorSpec(426, "contract", False),
    "authentication_required": ErrorSpec(401, "authentication", False),
    "method_not_allowed": ErrorSpec(405, "request", False),
    "request_schema_invalid": ErrorSpec(422, "request", False),
    "payload_too_large": ErrorSpec(413, "request", False),
    "rate_limited": ErrorSpec(429, "rate_limit", True),
    "provider_payload_too_large": ErrorSpec(422, "provider", False),
    "document_unsupported": ErrorSpec(422, "document", False),
    "pdf_text_layer_required": ErrorSpec(422, "document", False),
    "pdf_visual_content_unsupported": ErrorSpec(422, "document", False),
    "document_too_complex": ErrorSpec(422, "document", False),
    "document_busy": ErrorSpec(429, "service", True),
    "document_parser_unavailable": ErrorSpec(503, "dependency", True),
    "session_review_window": ErrorSpec(409, "session", False),
    "approval_invalid": ErrorSpec(403, "session", False),
    "approval_consumed": ErrorSpec(409, "session", False),
    "approval_expired": ErrorSpec(410, "session", False),
    "approval_registry_full": ErrorSpec(503, "service", True),
    "queue_invalid": ErrorSpec(403, "queue", False),
    "queue_already_active": ErrorSpec(409, "queue", False),
    "queue_full": ErrorSpec(429, "queue", True),
    "queue_rate_limited": ErrorSpec(429, "queue", True),
    "queue_expired": ErrorSpec(410, "queue", False),
    "queue_not_ready": ErrorSpec(409, "queue", False),
    "provider_already_running": ErrorSpec(409, "provider", False),
    "residual_pii": ErrorSpec(422, "privacy", False),
    "document_integrity_failed": ErrorSpec(422, "document", False),
    "document_structure_invalid": ErrorSpec(502, "provider", False),
    "provider_configuration": ErrorSpec(503, "dependency", True),
    "provider_unavailable": ErrorSpec(502, "provider", True),
    "provider_rejected": ErrorSpec(502, "provider", False),
    "provider_response_invalid": ErrorSpec(502, "provider", False),
    "provider_timeout": ErrorSpec(504, "provider", True),
    "provider_failed": ErrorSpec(502, "provider", True),
    "restore_failed": ErrorSpec(500, "restore", False),
    "internal_error": ErrorSpec(500, "internal", False),
}


def error_payload(code: str) -> dict[str, dict[str, object]]:
    """Return one value-free strict v2 envelope for an approved additive row."""

    spec = ERROR_SPECS[code]
    return {
        "error": {
            "code": code,
            "category": spec.category,
            "count": 0,
            "retryable": spec.retryable,
            "status": spec.status,
        }
    }

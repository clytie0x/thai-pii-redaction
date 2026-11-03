"""Sanitize an OpenAI chat-completions payload and restore replies.

Every message's text is masked through the public facade in token mode with
one shared salt and an accumulated ``prior_mapping``, so the same value keeps
the same token across the whole history. The forwarded request is rebuilt from
an explicit v1 schema: free-form strings exist only in sanitized content, while
model/role/type strings are tightly validated identifiers or closed enums.
Anything else is rejected before an upstream request can be made.
"""

from __future__ import annotations

import copy
import math
import re
import warnings

from pii_redactor.config import CoreConfig
from pii_redactor.leak_guard import (
    OutboundGuardContext,
    OutboundPolicyError,
    enforce_outbound_policy,
)
from pii_redactor.pdpa_categories import SECTION26_CATEGORIES
from pii_redactor.safe_errors import discard_exception_graph, minimize_failure_frames

import amphrang
from amphrang._core_config import sdk_core_config


class ProxyRequestError(ValueError):
    """The request shape is outside what the proxy can sanitize (v1 scope)."""


_MODEL_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_MESSAGE_ROLES = frozenset({"developer", "system", "user", "assistant"})
_MESSAGE_FIELDS = frozenset({"role", "content"})
_CONTENT_PART_FIELDS = frozenset({"type", "text"})
_BOOLEAN_CONTROLS = frozenset({"stream", "logprobs"})
_NUMBER_CONTROLS = {
    "temperature": (0.0, 2.0),
    "top_p": (0.0, 1.0),
    "presence_penalty": (-2.0, 2.0),
    "frequency_penalty": (-2.0, 2.0),
}
_INTEGER_CONTROLS = {
    "max_tokens": (1, 2_000_000),
    "max_completion_tokens": (1, 2_000_000),
    "n": (1, 128),
    "seed": (-(2**63), 2**63 - 1),
    "top_logprobs": (0, 20),
}
_TOP_LEVEL_FIELDS = frozenset(
    {
        "model",
        "messages",
        *_BOOLEAN_CONTROLS,
        *_NUMBER_CONTROLS,
        *_INTEGER_CONTROLS,
        "stream_options",
        "response_format",
    }
)
_EMPTY_GUARD_CONTEXT = OutboundGuardContext()
_SECTION26_WARNINGS = {f"section26:{category}" for category in SECTION26_CATEGORIES}


def _is_model_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and _MODEL_IDENTIFIER_RE.fullmatch(value) is not None
        and any(character.isascii() and character.isalpha() for character in value)
    )


def validate_allowed_models(models: object) -> frozenset[str]:
    """Validate and return the immutable operator-configured model allowlist."""
    if (
        not isinstance(models, frozenset)
        or not models
        or any(not _is_model_identifier(model) for model in models)
    ):
        raise ValueError("allowed_models must be a non-empty frozenset of model identifiers")
    return models


def _validate_control_scalar(value: bool | int | float, *, config: CoreConfig) -> None:
    try:
        enforce_outbound_policy(str(value), guard_context=_EMPTY_GUARD_CONTEXT, config=config)
    except OutboundPolicyError as error:
        discard_exception_graph(error)
        raise ProxyRequestError("invalid request control for sanitizing proxy (v1)") from None


def _validate_controls(payload: dict, *, config: CoreConfig) -> None:
    for field in _BOOLEAN_CONTROLS:
        if field in payload and type(payload[field]) is not bool:
            raise ProxyRequestError("invalid request control for sanitizing proxy (v1)")
        if field in payload:
            _validate_control_scalar(payload[field], config=config)

    for field, (minimum, maximum) in _NUMBER_CONTROLS.items():
        if field not in payload:
            continue
        value = payload[field]
        if type(value) not in (int, float):
            raise ProxyRequestError("invalid request control for sanitizing proxy (v1)")
        if type(value) is float and not math.isfinite(value):
            raise ProxyRequestError("invalid request control for sanitizing proxy (v1)")
        if value < minimum or value > maximum:
            raise ProxyRequestError("invalid request control for sanitizing proxy (v1)")
        _validate_control_scalar(value, config=config)

    for field, (minimum, maximum) in _INTEGER_CONTROLS.items():
        if field not in payload:
            continue
        value = payload[field]
        if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
            raise ProxyRequestError("invalid request control for sanitizing proxy (v1)")
        _validate_control_scalar(value, config=config)

    if "stream_options" in payload:
        stream_options = payload["stream_options"]
        if (
            not isinstance(stream_options, dict)
            or not set(stream_options) <= {"include_usage"}
            or any(type(value) is not bool for value in stream_options.values())
            or payload.get("stream") is not True
        ):
            raise ProxyRequestError("invalid request control for sanitizing proxy (v1)")
        for value in stream_options.values():
            _validate_control_scalar(value, config=config)

    if "response_format" in payload:
        response_format = payload["response_format"]
        if (
            not isinstance(response_format, dict)
            or set(response_format) != {"type"}
            or not isinstance(response_format["type"], str)
            or response_format["type"] not in {"text", "json_object"}
        ):
            raise ProxyRequestError("invalid request control for sanitizing proxy (v1)")

    if "top_logprobs" in payload and payload.get("logprobs") is not True:
        raise ProxyRequestError("invalid request control for sanitizing proxy (v1)")


def _validate_messages(messages: object) -> None:
    if not isinstance(messages, list) or not messages:
        raise ProxyRequestError("request has no messages list")
    for message in messages:
        role = message.get("role") if isinstance(message, dict) else None
        if (
            not isinstance(message, dict)
            or set(message) != _MESSAGE_FIELDS
            or not isinstance(role, str)
            or role not in _MESSAGE_ROLES
        ):
            raise ProxyRequestError("unsupported message shape for sanitizing proxy (v1)")

        content = message["content"]
        if content is None or isinstance(content, str):
            continue
        if not isinstance(content, list):
            raise ProxyRequestError("unsupported message content shape")
        # Multiple parts form one logical message, but sanitizing them separately
        # misses PII split across boundaries. V1 therefore supports one text part.
        if len(content) != 1:
            raise ProxyRequestError("unsupported content part shape for sanitizing proxy (v1)")
        for part in content:
            if (
                not isinstance(part, dict)
                or set(part) != _CONTENT_PART_FIELDS
                or part.get("type") != "text"
                or not isinstance(part.get("text"), str)
            ):
                raise ProxyRequestError("unsupported content part shape for sanitizing proxy (v1)")


def _validate_payload(
    payload: object, allowed_models: frozenset[str] | None, *, config: CoreConfig
) -> None:
    if not isinstance(payload, dict) or not set(payload) <= _TOP_LEVEL_FIELDS:
        raise ProxyRequestError("unsupported request shape for sanitizing proxy (v1)")

    if "model" not in payload:
        if allowed_models is not None:
            raise ProxyRequestError("invalid model identifier for sanitizing proxy (v1)")
    else:
        model = payload["model"]
        if not _is_model_identifier(model):
            raise ProxyRequestError("invalid model identifier for sanitizing proxy (v1)")
        if allowed_models is not None:
            if model not in allowed_models:
                raise ProxyRequestError("invalid model identifier for sanitizing proxy (v1)")
        elif amphrang._detect_with_config(model, config=config):
            # Direct core callers have no trusted configured model identity.
            # Reject anything detector-visible rather than infer version syntax.
            raise ProxyRequestError("invalid model identifier for sanitizing proxy (v1)")

    _validate_messages(payload.get("messages"))
    _validate_controls(payload, config=config)


def _message_content_text(message: dict) -> str | None:
    content = message["content"]
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return content[0]["text"]
    return None


def _enforce_whole_history(sanitized: dict, mapping: dict[str, str], *, config: CoreConfig) -> None:
    pieces = [
        text
        for message in sanitized["messages"]
        if (text := _message_content_text(message)) is not None
    ]
    if len(pieces) < 2:
        return
    joined = "".join(pieces)
    context = OutboundGuardContext(frozenset(mapping))
    try:
        enforce_outbound_policy(joined, guard_context=context, config=config)
    except OutboundPolicyError as error:
        failure = (list(error.leak_types), list(error.policy_categories))
        discard_exception_graph(error)
        joined = ""
        pieces.clear()
        context = None
        leak_types, policy_categories = failure
        raise amphrang.LeakBlockedError(
            leak_types,
            policy_categories=policy_categories,
        ) from None


@minimize_failure_frames
def sanitize_chat_request(
    payload: dict,
    *,
    salt: str,
    allowed_models: frozenset[str] | None = None,
) -> tuple[dict, dict[str, str]]:
    """Return (masked copy of the payload, token→original mapping).

    ``allowed_models`` is the immutable operator-configured trust boundary for
    HTTP forwarding. Direct core callers may omit ``model``; if they provide it
    without an allowlist, detector-visible values fail closed.

    Raises ``ProxyRequestError`` for shapes outside the v1 scope and
    ``amphrang.LeakBlockedError`` when a mask would still leak (the caller
    must not forward anything in either case).
    """
    return _sanitize_chat_request_with_config(
        payload, salt=salt, allowed_models=allowed_models, config=sdk_core_config()
    )


@minimize_failure_frames
def _sanitize_chat_request_with_config(
    payload: dict,
    *,
    salt: str,
    allowed_models: frozenset[str] | None = None,
    config: CoreConfig,
) -> tuple[dict, dict[str, str]]:
    amphrang._require_local_config(config)
    if allowed_models is not None:
        allowed_models = validate_allowed_models(allowed_models)
    _validate_payload(payload, allowed_models, config=config)
    sanitized = {
        field: copy.deepcopy(value)
        for field, value in payload.items()
        if field in _TOP_LEVEL_FIELDS
    }
    mapping: dict[str, str] = {}
    for message in sanitized["messages"]:
        content = message["content"]
        if content is None or content == "":
            continue
        if isinstance(content, str):
            message["content"] = _sanitize_text(content, salt, mapping, config=config)
            continue
        if isinstance(content, list):
            for part in content:
                part["text"] = _sanitize_text(part["text"], salt, mapping, config=config)
            continue
    _enforce_whole_history(sanitized, mapping, config=config)
    return sanitized, mapping


def _sanitize_text(text: str, salt: str, mapping: dict[str, str], *, config: CoreConfig) -> str:
    if not text.strip():
        return text
    result = amphrang._anonymize_with_config(
        text, mode="token", salt=salt, prior_mapping=mapping, config=config
    )
    for code in result.warnings:
        if code in _SECTION26_WARNINGS:
            warnings.warn(code, UserWarning, stacklevel=2)
    mapping.update(result.mapping)
    return result.text


@minimize_failure_frames
def restore_text(text: str, mapping: dict[str, str]) -> str:
    """Restore originals into a complete (non-streamed) reply text."""
    return _restore_text_with_config(text, mapping, config=sdk_core_config())


@minimize_failure_frames
def _restore_text_with_config(text: str, mapping: dict[str, str], *, config: CoreConfig) -> str:
    restored = amphrang._restore_with_config(text, mapping, config=config)
    return restored.text

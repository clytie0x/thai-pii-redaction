"""Sanitize an OpenAI chat-completions payload and restore replies.

Every message's text is masked through the public facade in token mode with
one shared salt and an accumulated ``prior_mapping``, so the same value keeps
the same token across the whole history. Anything the v1 proxy cannot mask
end-to-end (tools, tool calls, non-text content parts) is rejected outright —
forwarding it unmasked would be a silent leak path.
"""

from __future__ import annotations

import copy

import amphrang


class ProxyRequestError(ValueError):
    """The request shape is outside what the proxy can sanitize (v1 scope)."""


def _sanitize_text(text: str, salt: str, mapping: dict[str, str]) -> str:
    if not text.strip():
        return text
    result = amphrang.anonymize(text, mode="token", salt=salt, prior_mapping=mapping)
    mapping.update(result.mapping)
    return result.text


def sanitize_chat_request(payload: dict, *, salt: str) -> tuple[dict, dict[str, str]]:
    """Return (masked copy of the payload, token→original mapping).

    Raises ``ProxyRequestError`` for shapes outside the v1 scope and
    ``amphrang.LeakBlockedError`` when a mask would still leak (the caller
    must not forward anything in either case).
    """
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ProxyRequestError("request has no messages list")
    if payload.get("tools") or payload.get("functions"):
        raise ProxyRequestError(
            "tools are not supported by the sanitizing proxy (v1); "
            "tool arguments would bypass masking"
        )

    sanitized = copy.deepcopy(payload)
    mapping: dict[str, str] = {}
    for message in sanitized["messages"]:
        if not isinstance(message, dict):
            raise ProxyRequestError("malformed message entry")
        if message.get("tool_calls") or message.get("role") == "tool":
            raise ProxyRequestError("tool calls are not supported by the sanitizing proxy (v1)")
        content = message.get("content")
        if content is None or content == "":
            continue
        if isinstance(content, str):
            message["content"] = _sanitize_text(content, salt, mapping)
            continue
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "text":
                    raise ProxyRequestError(
                        "only text content parts are supported by the sanitizing proxy (v1)"
                    )
                part["text"] = _sanitize_text(part.get("text", ""), salt, mapping)
            continue
        raise ProxyRequestError("unsupported message content shape")
    return sanitized, mapping


def restore_text(text: str, mapping: dict[str, str]) -> str:
    """Restore originals into a complete (non-streamed) reply text."""
    restored = amphrang.restore(text, mapping)
    return restored.text

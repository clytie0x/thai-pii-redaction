"""Proxy request sanitization: OpenAI chat payload in, masked payload + mapping out."""

import pytest

from amphrang.proxy.core import ProxyRequestError, restore_text, sanitize_chat_request

PII_TEXT = "ผมชื่อ นายสมชาย ใจดี โทร 081-234-5678"


def _payload(messages, **extra):
    return {"model": "gpt-test", "messages": messages, **extra}


def test_masks_pii_in_every_message():
    payload = _payload(
        [
            {"role": "system", "content": "คุณเป็นผู้ช่วยงานเอกสาร"},
            {"role": "user", "content": PII_TEXT},
        ]
    )
    sanitized, mapping = sanitize_chat_request(payload, salt="s")
    assert "081-234-5678" not in str(sanitized)
    assert "สมชาย" not in str(sanitized)
    assert any("081-234-5678" == original for original in mapping.values())


def test_same_value_gets_the_same_token_across_messages():
    payload = _payload(
        [
            {"role": "user", "content": "เบอร์ผม 081-234-5678"},
            {"role": "assistant", "content": "รับทราบ"},
            {"role": "user", "content": "ย้ำอีกครั้ง 081-234-5678 นะ"},
        ]
    )
    sanitized, mapping = sanitize_chat_request(payload, salt="s")
    phone_tokens = [t for t, original in mapping.items() if original == "081-234-5678"]
    assert len(phone_tokens) == 1
    token = phone_tokens[0]
    assert token in sanitized["messages"][0]["content"]
    assert token in sanitized["messages"][2]["content"]


def test_non_message_fields_and_input_are_untouched():
    payload = _payload([{"role": "user", "content": PII_TEXT}], temperature=0.2, stream=True)
    sanitized, _ = sanitize_chat_request(payload, salt="s")
    assert sanitized["model"] == "gpt-test"
    assert sanitized["temperature"] == 0.2
    assert sanitized["stream"] is True
    # the caller's payload is not mutated
    assert payload["messages"][0]["content"] == PII_TEXT


def test_text_content_parts_are_sanitized():
    payload = _payload([{"role": "user", "content": [{"type": "text", "text": PII_TEXT}]}])
    sanitized, mapping = sanitize_chat_request(payload, salt="s")
    part = sanitized["messages"][0]["content"][0]
    assert part["type"] == "text"
    assert "081-234-5678" not in part["text"]
    assert mapping


def test_empty_or_null_content_passes_through():
    payload = _payload(
        [{"role": "assistant", "content": None}, {"role": "user", "content": PII_TEXT}]
    )
    sanitized, _ = sanitize_chat_request(payload, salt="s")
    assert sanitized["messages"][0]["content"] is None


def test_tools_are_rejected_fail_closed():
    payload = _payload([{"role": "user", "content": "หวัดดี"}], tools=[{"type": "function"}])
    with pytest.raises(ProxyRequestError):
        sanitize_chat_request(payload, salt="s")


def test_tool_calls_are_rejected_fail_closed():
    payload = _payload([{"role": "assistant", "content": None, "tool_calls": [{}]}])
    with pytest.raises(ProxyRequestError):
        sanitize_chat_request(payload, salt="s")


def test_non_text_content_parts_are_rejected():
    payload = _payload(
        [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}]
    )
    with pytest.raises(ProxyRequestError):
        sanitize_chat_request(payload, salt="s")


def test_missing_messages_rejected():
    with pytest.raises(ProxyRequestError):
        sanitize_chat_request({"model": "gpt-test"}, salt="s")


def test_leak_block_propagates():
    import amphrang

    # Undetected 7-digit run -> ORPHAN_DIGITS residual -> deterministic block.
    payload = _payload([{"role": "user", "content": "ค่าที่เหลือ 6801234"}])
    with pytest.raises(amphrang.LeakBlockedError):
        sanitize_chat_request(payload, salt="s")


def test_restore_text_round_trip():
    payload = _payload([{"role": "user", "content": PII_TEXT}])
    sanitized, mapping = sanitize_chat_request(payload, salt="s")
    masked = sanitized["messages"][0]["content"]
    assert restore_text(masked, mapping) == PII_TEXT

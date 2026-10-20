"""Proxy request sanitization: OpenAI chat payload in, masked payload + mapping out."""

import copy

import pytest

import amphrang
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
    payload = _payload(
        [{"role": "user", "content": PII_TEXT}],
        temperature=0.2,
        top_p=0.8,
        max_completion_tokens=200,
        n=2,
        presence_penalty=-0.5,
        frequency_penalty=0.5,
        seed=42,
        stream=True,
        logprobs=True,
        top_logprobs=3,
        stream_options={"include_usage": True},
        response_format={"type": "json_object"},
    )
    original = copy.deepcopy(payload)
    sanitized, _ = sanitize_chat_request(payload, salt="s")
    assert sanitized["model"] == "gpt-test"
    assert sanitized["temperature"] == 0.2
    assert sanitized["top_p"] == 0.8
    assert sanitized["max_completion_tokens"] == 200
    assert sanitized["n"] == 2
    assert sanitized["presence_penalty"] == -0.5
    assert sanitized["frequency_penalty"] == 0.5
    assert sanitized["seed"] == 42
    assert sanitized["stream"] is True
    assert sanitized["logprobs"] is True
    assert sanitized["top_logprobs"] == 3
    assert sanitized["stream_options"] == {"include_usage": True}
    assert sanitized["response_format"] == {"type": "json_object"}
    # the caller's payload is not mutated
    assert payload == original


def test_text_content_parts_are_sanitized():
    payload = _payload([{"role": "user", "content": [{"type": "text", "text": PII_TEXT}]}])
    sanitized, mapping = sanitize_chat_request(payload, salt="s")
    part = sanitized["messages"][0]["content"][0]
    assert part["type"] == "text"
    assert "081-234-5678" not in part["text"]
    assert mapping


def test_pii_split_across_text_parts_is_rejected():
    payload = _payload(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "โทร 081-"},
                    {"type": "text", "text": "234-5678"},
                ],
            }
        ]
    )
    with pytest.raises(ProxyRequestError, match="unsupported content part shape"):
        sanitize_chat_request(payload, salt="s")


def test_plain_and_part_content_share_one_mapping():
    payload = _payload(
        [
            {"role": "user", "content": PII_TEXT},
            {"role": "user", "content": [{"type": "text", "text": PII_TEXT}]},
        ]
    )
    sanitized, mapping = sanitize_chat_request(payload, salt="s")
    phone_tokens = [token for token, original in mapping.items() if original == "081-234-5678"]
    assert len(phone_tokens) == 1
    token = phone_tokens[0]
    assert token in sanitized["messages"][0]["content"]
    assert token in sanitized["messages"][1]["content"][0]["text"]


@pytest.mark.parametrize(
    "messages",
    [
        [
            {"role": "user", "content": "phone 08123"},
            {"role": "assistant", "content": "45678"},
        ],
        [
            {"role": "user", "content": "โทร 081"},
            {"role": "assistant", "content": [{"type": "text", "text": "23"}]},
            {"role": "user", "content": "45678"},
        ],
    ],
)
def test_pii_reconstructed_across_message_boundaries_is_blocked(messages):
    with pytest.raises(amphrang.LeakBlockedError):
        sanitize_chat_request(_payload(messages), salt="s")


def test_normal_mixed_multi_turn_history_is_not_rejected():
    payload = _payload(
        [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "ช่วยสรุปหัวข้อนี้"},
            {"role": "assistant", "content": [{"type": "text", "text": "ได้เลยครับ"}]},
            {"role": "user", "content": "ขอบคุณ"},
        ]
    )
    sanitized, _ = sanitize_chat_request(payload, salt="s")
    assert len(sanitized["messages"]) == 4


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


@pytest.mark.parametrize(
    "extra",
    [
        {"metadata": {"contact": PII_TEXT}},
        {"user": PII_TEXT},
        {"stop": PII_TEXT},
        {"tools": []},
        {"functions": []},
    ],
)
def test_unknown_or_uninspected_top_level_fields_are_rejected(extra):
    payload = _payload([{"role": "user", "content": "หวัดดี"}], **extra)
    with pytest.raises(ProxyRequestError, match="unsupported request shape"):
        sanitize_chat_request(payload, salt="s")


@pytest.mark.parametrize(
    "message",
    [
        {"role": "user", "content": "หวัดดี", "name": PII_TEXT},
        {"role": "assistant", "content": None, "tool_calls": []},
        {"role": "tool", "content": PII_TEXT},
        {"role": "intruder", "content": PII_TEXT},
        {"role": [], "content": PII_TEXT},
        {"content": PII_TEXT},
        {"role": "user"},
    ],
)
def test_unknown_or_invalid_message_fields_are_rejected(message):
    with pytest.raises(ProxyRequestError, match="unsupported message shape"):
        sanitize_chat_request(_payload([message]), salt="s")


@pytest.mark.parametrize(
    "part",
    [
        {"type": "text", "text": "หวัดดี", "metadata": PII_TEXT},
        {"type": "text", "text": 123},
        {"type": "text"},
        {"text": PII_TEXT},
    ],
)
def test_unknown_or_invalid_text_content_part_fields_are_rejected(part):
    payload = _payload([{"role": "user", "content": [part]}])
    with pytest.raises(ProxyRequestError, match="unsupported content part shape"):
        sanitize_chat_request(payload, salt="s")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("temperature", True),
        ("temperature", 2.1),
        ("temperature", float("nan")),
        ("temperature", float("inf")),
        ("temperature", 10**400),
        ("temperature", 0.0812345678),
        ("top_p", -0.1),
        ("n", 0),
        ("max_tokens", 0),
        ("max_tokens", 1234567),
        ("max_tokens", 1101700207030),
        ("seed", 2**63),
        ("seed", 6801234),
        ("seed", 1101700207030),
        ("stream", 1),
        ("top_logprobs", 21),
        ("stream_options", {"include_usage": True, "contact": PII_TEXT}),
        ("stream_options", None),
        ("response_format", {"type": PII_TEXT}),
        ("response_format", {"type": []}),
        ("response_format", None),
    ],
)
def test_invalid_controls_are_rejected(field, value):
    payload = _payload([{"role": "user", "content": "หวัดดี"}], **{field: value})
    with pytest.raises(ProxyRequestError, match="invalid request control"):
        sanitize_chat_request(payload, salt="s")


def test_model_may_be_omitted_for_direct_core_callers():
    payload = {"messages": [{"role": "user", "content": PII_TEXT}]}
    sanitized, mapping = sanitize_chat_request(payload, salt="s")
    assert "model" not in sanitized
    assert "081-234-5678" not in sanitized["messages"][0]["content"]
    assert mapping


def test_model_is_tightly_validated_when_present():
    messages = [{"role": "user", "content": "หวัดดี"}]
    for payload in (
        _payload(messages, model="นายสมชาย ใจดี"),
        _payload(messages, model=""),
        _payload(messages, model=123),
        _payload(messages, model="081-234-5678"),
        _payload(messages, model="AB123456"),
        _payload(messages, model="gpt-1101700207030"),
        _payload(messages, model="id-12345678"),
        _payload(messages, model="birthdate-1990-01-01"),
        _payload(messages, model="appointment-2026-08-29"),
    ):
        with pytest.raises(ProxyRequestError, match="invalid model identifier"):
            sanitize_chat_request(payload, salt="s")


def test_model_identifier_supports_openai_compatible_vendor_syntax():
    messages = [{"role": "user", "content": "hi"}]
    for model in (
        "hf.co/org/model:latest",
        "gpt-4.1-2025-04-14",
        "claude-3-5-sonnet-20241022",
        "o3",
    ):
        sanitized, _ = sanitize_chat_request(
            {"model": model, "messages": messages},
            salt="s",
            allowed_models=frozenset({model}),
        )
        assert sanitized["model"] == model


def test_configured_model_must_match_exactly_and_http_mode_requires_it():
    messages = [{"role": "user", "content": "hi"}]
    allowed_models = frozenset({"gpt-test"})
    for payload in (
        {"messages": messages},
        {"model": "gpt-test-copy", "messages": messages},
    ):
        with pytest.raises(ProxyRequestError, match="invalid model identifier"):
            sanitize_chat_request(payload, salt="s", allowed_models=allowed_models)


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

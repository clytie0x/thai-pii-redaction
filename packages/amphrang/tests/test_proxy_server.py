"""The sanitizing proxy's HTTP surface (/v1/chat/completions).

The fake upstream is an httpx.MockTransport that records exactly what the
proxy forwarded — the core promise under test is that raw PII never reaches
it, while the client gets plaintext back.
"""

from __future__ import annotations

import json
import re

import pytest

httpx = pytest.importorskip("httpx")
fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from amphrang.proxy.server import create_app

PII_TEXT = "ผมชื่อ นายสมชาย ใจดี โทร 081-234-5678"
LEAKY_TEXT = "ค่าที่เหลือ 6801234"
TOKEN_RE = re.compile(r"\[[^\[\]\r\n]+\]")
PHONE_TOKEN_RE = re.compile(r"\[โทรศัพท์_[^\[\]\r\n]+\]")


class FakeUpstream:
    """Records forwarded requests and answers like an OpenAI server."""

    def __init__(self, *, status=200, stream_events=None, body=None):
        self.requests: list[httpx.Request] = []
        self.status = status
        self.stream_events = stream_events
        self.body = body

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.stream_events is not None:
            content = "".join(self.stream_events).encode("utf-8")
            return httpx.Response(
                self.status, content=content, headers={"content-type": "text/event-stream"}
            )
        if self.body is not None:
            return httpx.Response(self.status, json=self.body)
        # Echo the phone token back inside a completion.
        payload = json.loads(request.content)
        text = payload["messages"][-1]["content"]
        token = PHONE_TOKEN_RE.search(text)
        reply = f"ติดต่อกลับที่ {token.group(0)} แล้วกัน" if token else "รับทราบ"
        return httpx.Response(
            self.status,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": payload["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop",
                    }
                ],
            },
        )


def _client(upstream: FakeUpstream, **kwargs) -> TestClient:
    allowed_models = kwargs.pop("allowed_models", frozenset({"gpt-test"}))
    app = create_app(
        upstream_base_url="https://upstream.example",
        allowed_models=allowed_models,
        transport=httpx.MockTransport(upstream),
        **kwargs,
    )
    return TestClient(app, base_url="http://localhost")


def _chat(messages, **extra):
    return {"model": "gpt-test", "messages": messages, **extra}


@pytest.mark.parametrize(
    "allowed_models",
    [{"gpt-test"}, frozenset(), frozenset({""}), frozenset({"081-234-5678"})],
)
def test_create_app_requires_nonempty_immutable_valid_model_allowlist(allowed_models):
    with pytest.raises(ValueError, match="non-empty frozenset"):
        create_app(
            upstream_base_url="https://upstream.example",
            allowed_models=allowed_models,
        )


def test_upstream_never_sees_raw_pii_and_client_gets_plaintext_back():
    upstream = FakeUpstream()
    response = _client(upstream).post(
        "/v1/chat/completions", json=_chat([{"role": "user", "content": PII_TEXT}])
    )
    assert response.status_code == 200
    forwarded = upstream.requests[0].content.decode("utf-8")
    assert "081-234-5678" not in forwarded
    assert "สมชาย" not in forwarded
    body = response.json()
    assert body["choices"][0]["message"]["content"] == "ติดต่อกลับที่ 081-234-5678 แล้วกัน"
    assert not TOKEN_RE.search(body["choices"][0]["message"]["content"])


def test_upstream_gets_the_configured_key_never_the_clients():
    upstream = FakeUpstream()
    client = _client(upstream, upstream_api_key="sk-upstream")
    client.post(
        "/v1/chat/completions",
        json=_chat([{"role": "user", "content": "หวัดดี ทดสอบ"}]),
        headers={"Authorization": "Bearer sk-client-secret"},
    )
    sent = upstream.requests[0].headers
    assert sent["authorization"] == "Bearer sk-upstream"


def test_leak_blocked_input_is_never_forwarded():
    upstream = FakeUpstream()
    response = _client(upstream).post(
        "/v1/chat/completions", json=_chat([{"role": "user", "content": LEAKY_TEXT}])
    )
    assert response.status_code == 422
    assert response.json()["error"]["type"] == "leak_blocked"
    assert "6801234" not in response.text
    assert upstream.requests == []


def test_tools_are_rejected_without_forwarding():
    upstream = FakeUpstream()
    response = _client(upstream).post(
        "/v1/chat/completions",
        json=_chat([{"role": "user", "content": "หวัดดี"}], tools=[{"type": "function"}]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["type"] == "invalid_request_error"
    assert upstream.requests == []


@pytest.mark.parametrize(
    "messages, extra",
    [
        ([{"role": "user", "content": "หวัดดี"}], {"metadata": {"contact": PII_TEXT}}),
        ([{"role": "user", "content": "หวัดดี", "name": PII_TEXT}], {}),
        (
            [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "หวัดดี", "contact": PII_TEXT}],
                }
            ],
            {},
        ),
        (
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "โทร 081-"},
                        {"type": "text", "text": "234-5678"},
                    ],
                }
            ],
            {},
        ),
        ([{"role": "user", "content": "หวัดดี"}], {"model": "081-234-5678"}),
        ([{"role": "user", "content": "หวัดดี"}], {"model": "id-12345678"}),
        ([{"role": "user", "content": "หวัดดี"}], {"model": "birthdate-1990-01-01"}),
        ([{"role": "user", "content": "หวัดดี"}], {"model": "appointment-2026-08-29"}),
        ([{"role": "user", "content": "หวัดดี"}], {"seed": 1101700207030}),
        ([{"role": "user", "content": "หวัดดี"}], {"seed": 6801234}),
        ([{"role": "user", "content": "หวัดดี"}], {"max_tokens": 1234567}),
        ([{"role": "user", "content": "หวัดดี"}], {"temperature": 0.0812345678}),
        (
            [
                {"role": "user", "content": "phone 08123"},
                {"role": "assistant", "content": "45678"},
            ],
            {},
        ),
        (
            [
                {"role": "user", "content": "โทร 081"},
                {"role": "assistant", "content": [{"type": "text", "text": "23"}]},
                {"role": "user", "content": "45678"},
            ],
            {},
        ),
    ],
)
def test_pii_in_uninspected_fields_is_rejected_before_upstream(messages, extra):
    upstream = FakeUpstream()
    response = _client(upstream).post(
        "/v1/chat/completions",
        json=_chat(messages, **extra),
    )
    assert response.status_code == 422
    expected_type = "leak_blocked" if len(messages) > 1 else "invalid_request_error"
    assert response.json()["error"]["type"] == expected_type
    assert "สมชาย" not in response.text
    assert "081-234-5678" not in response.text
    assert upstream.requests == []


def test_configured_dated_model_is_forwarded_only_on_exact_match():
    model = "gpt-4.1-2025-04-14"
    upstream = FakeUpstream()
    response = _client(upstream, allowed_models=frozenset({model})).post(
        "/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": "หวัดดี"}]},
    )
    assert response.status_code == 200
    assert json.loads(upstream.requests[0].content)["model"] == model


def test_http_request_requires_a_configured_model():
    upstream = FakeUpstream()
    response = _client(upstream).post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "หวัดดี"}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["type"] == "invalid_request_error"
    assert upstream.requests == []


def test_single_text_part_is_sanitized_before_recording_upstream():
    upstream = FakeUpstream(
        body={
            "id": "chatcmpl-1",
            "choices": [{"message": {"role": "assistant", "content": "รับทราบ"}}],
        }
    )
    response = _client(upstream).post(
        "/v1/chat/completions",
        json=_chat([{"role": "user", "content": [{"type": "text", "text": PII_TEXT}]}]),
    )
    assert response.status_code == 200
    forwarded = json.loads(upstream.requests[0].content)
    text = forwarded["messages"][0]["content"][0]["text"]
    assert "สมชาย" not in text
    assert "081-234-5678" not in text
    assert PHONE_TOKEN_RE.search(text)


def test_invalid_json_body_is_400():
    upstream = FakeUpstream()
    response = _client(upstream).post(
        "/v1/chat/completions",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert upstream.requests == []


def test_upstream_error_status_passes_through():
    upstream = FakeUpstream(status=429, body={"error": {"message": "rate limited"}})
    response = _client(upstream).post(
        "/v1/chat/completions", json=_chat([{"role": "user", "content": "หวัดดี ทดสอบ"}])
    )
    assert response.status_code == 429
    assert response.json()["error"]["message"] == "rate limited"


def test_tokens_in_upstream_json_error_values_are_restored_recursively():
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        payload = json.loads(request.content)
        token = PHONE_TOKEN_RE.search(payload["messages"][-1]["content"]).group(0)
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": f"retry for {token}",
                    "details": [token, {"echo": token}],
                    "code": 429,
                }
            },
        )

    app = create_app(
        upstream_base_url="https://upstream.example",
        allowed_models=frozenset({"gpt-test"}),
        transport=httpx.MockTransport(handler),
    )
    response = TestClient(app, base_url="http://localhost").post(
        "/v1/chat/completions",
        json=_chat([{"role": "user", "content": PII_TEXT}]),
    )
    assert response.status_code == 429
    assert "081-234-5678" not in recorded[0].content.decode("utf-8")
    assert response.json() == {
        "error": {
            "message": "retry for 081-234-5678",
            "details": ["081-234-5678", {"echo": "081-234-5678"}],
            "code": 429,
        }
    }


def test_streaming_reply_is_restored_across_split_tokens():
    upstream_probe = FakeUpstream()
    client = _client(upstream_probe)
    # First, learn the token the proxy will mint for this phone number is
    # per-request; so the streaming upstream builds its events from the
    # forwarded request instead.

    events_built: dict[str, list[str]] = {}

    def streaming_handler(request: httpx.Request) -> httpx.Response:
        upstream_probe.requests.append(request)
        payload = json.loads(request.content)
        token = PHONE_TOKEN_RE.search(payload["messages"][-1]["content"]).group(0)
        cut = len(token) // 2

        def chunk(content):
            return (
                "data: "
                + json.dumps(
                    {
                        "id": "chatcmpl-1",
                        "object": "chat.completion.chunk",
                        "model": payload["model"],
                        "choices": [
                            {"index": 0, "delta": {"content": content}, "finish_reason": None}
                        ],
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )

        events = [
            chunk("เบอร์ "),
            chunk(token[:cut]),
            chunk(token[cut:]),
            chunk(" ครับ"),
            "data: [DONE]\n\n",
        ]
        events_built["events"] = events
        return httpx.Response(
            200,
            content="".join(events).encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )

    app = create_app(
        upstream_base_url="https://upstream.example",
        allowed_models=frozenset({"gpt-test"}),
        transport=httpx.MockTransport(streaming_handler),
    )
    client = TestClient(app, base_url="http://localhost")
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json=_chat([{"role": "user", "content": PII_TEXT}], stream=True),
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    contents = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            parsed = json.loads(line[len("data: ") :])
            for choice in parsed["choices"]:
                piece = choice.get("delta", {}).get("content")
                if piece:
                    contents.append(piece)
    joined = "".join(contents)
    assert joined == "เบอร์ 081-234-5678 ครับ"
    assert "data: [DONE]" in raw
    assert not TOKEN_RE.search(joined.replace("081-234-5678", ""))

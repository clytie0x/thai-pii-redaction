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
    app = create_app(
        upstream_base_url="https://upstream.example",
        transport=httpx.MockTransport(upstream),
        **kwargs,
    )
    return TestClient(app, base_url="http://localhost")


def _chat(messages, **extra):
    return {"model": "gpt-test", "messages": messages, **extra}


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

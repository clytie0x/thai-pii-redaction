"""Only synthetic canaries; provider failures never become restored output."""

import asyncio
import json
import re

import pytest

httpx = pytest.importorskip("httpx")
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from amphrang.proxy.server import create_app

PHONE = "081-234-5678"
CANARY = "synthetic-provider-private-canary"
ERROR = {"error": {"message": "upstream request failed", "type": "upstream_error"}}


def app_for(handler, *, transport=None):
    return create_app(
        "https://upstream.example",
        frozenset({"gpt-test"}),
        transport=transport or httpx.MockTransport(handler),
    )


def client(handler, *, transport=None):
    return TestClient(app_for(handler, transport=transport), base_url="http://localhost")


def post(client, *, stream=False):
    return client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-test",
            "messages": [{"role": "user", "content": "Synthetic contact: " + PHONE}],
            "stream": stream,
        },
    )


def token(request):
    text = json.loads(request.content)["messages"][0]["content"]
    assert PHONE not in text
    return re.search(r"\[โทรศัพท์_[^\[\]\r\n]+\]", text).group(0)


def test_proxy_requires_its_declared_anyio_api_without_retaining_credentials(monkeypatch):
    import anyio

    key = "synthetic-startup-provider-key"
    monkeypatch.setattr(anyio.TaskInfo, "has_pending_cancellation", None)
    with pytest.raises(RuntimeError, match=r"amphrang\[proxy\].*AnyIO") as caught:
        create_app("https://upstream.example", frozenset({"gpt-test"}), upstream_api_key=key)
    frames = []
    traceback = caught.value.__traceback__
    while traceback:
        if traceback.tb_frame.f_code is create_app.__code__:
            frames.append(traceback.tb_frame.f_locals)
        traceback = traceback.tb_next
    assert frames and all(key not in frame.values() for frame in frames)


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
@pytest.mark.parametrize("stream", [False, True])
def test_http_errors_return_only_fixed_metadata_without_reading_body(status, stream):
    class PrivateErrorBody(httpx.AsyncByteStream):
        read = False
        closed = False

        async def __aiter__(self):
            self.read = True
            yield (CANARY + PHONE).encode()

        async def aclose(self):
            self.closed = True

    body = PrivateErrorBody()
    response = post(
        client(
            lambda request: httpx.Response(
                status,
                stream=body,
                headers={"content-type": "text/plain", "x-provider-detail": CANARY},
            )
        ),
        stream=stream,
    )
    assert response.status_code == status
    assert response.json() == ERROR
    assert CANARY not in response.text and PHONE not in response.text
    assert "x-provider-detail" not in response.headers
    assert not body.read and body.closed


@pytest.mark.parametrize(
    "body",
    [
        {"error": {"message": CANARY}},
        {"choices": []},
        {"choices": [CANARY]},
        {"choices": [{"message": {"role": "assistant", "content": None, "refusal": CANARY}}]},
        {"choices": [{"message": {"content": "text"}, "finish_reason": "error"}]},
        {"choices": [{"message": {"content": "text"}}], "error": CANARY},
        {"id": "\ud800", "choices": [{"message": {"content": "text"}}]},
        [CANARY],
        CANARY,
    ],
)
def test_http_200_error_or_unsupported_success_is_fixed_failure(body):
    response = post(client(lambda request: httpx.Response(200, json=body)))
    assert response.status_code == 502
    assert response.json() == ERROR
    assert CANARY not in response.text and PHONE not in response.text


def test_non_json_success_is_not_restored_or_passed_through():
    response = post(
        client(
            lambda request: httpx.Response(
                200,
                text=CANARY + token(request),
                headers={"content-type": "text/plain"},
            )
        )
    )
    assert response.status_code == 502 and response.json() == ERROR


def test_escaped_invalid_unicode_in_json_is_a_fixed_failure():
    body = {"id": "\ud800", "choices": [{"message": {"content": "Safe text"}}]}
    response = post(
        client(
            lambda request: httpx.Response(
                200,
                content=json.dumps(body).encode(),
                headers={"content-type": "application/json"},
            )
        )
    )
    assert response.status_code == 502 and response.json() == ERROR


def test_stream_request_rejects_json_error_at_http_200():
    response = post(
        client(
            lambda request: httpx.Response(
                200,
                json={"error": {"message": CANARY + token(request)}},
            )
        ),
        stream=True,
    )
    assert response.status_code == 502 and response.json() == ERROR


@pytest.mark.parametrize(
    "event",
    [
        "data: " + json.dumps({"error": {"message": CANARY + PHONE}}) + "\n\n",
        "data: " + CANARY + "\n\n",
        "event: error\ndata: " + json.dumps({"message": CANARY}) + "\n\n",
        CANARY + "\n\n",
        "data: " + json.dumps({"choices": [CANARY]}) + "\n\n",
    ],
)
def test_sse_failure_has_a_fixed_error_event_and_no_done(event):
    response = post(
        client(
            lambda request: httpx.Response(
                200,
                content=event,
                headers={"content-type": "text/event-stream"},
            )
        ),
        stream=True,
    )
    assert response.status_code == 200
    assert response.text == "data: " + json.dumps(ERROR, ensure_ascii=False) + "\n\n"
    assert CANARY not in response.text and PHONE not in response.text
    assert "[DONE]" not in response.text


def chunk(content):
    return (
        "data: " + json.dumps({"choices": [{"index": 0, "delta": {"content": content}}]}) + "\n\n"
    )


def test_late_stream_failure_discards_held_token_tail():
    def handler(request):
        partial = token(request)[:18]
        events = chunk(partial) + "data: " + json.dumps({"error": {"message": CANARY}}) + "\n\n"
        return httpx.Response(200, content=events, headers={"content-type": "text/event-stream"})

    response = post(client(handler), stream=True)
    assert response.status_code == 200
    assert "[โทรศัพท์_" not in response.text and PHONE not in response.text
    assert CANARY not in response.text and "[DONE]" not in response.text
    assert ERROR["error"] == json.loads(response.text.split("data: ")[-1])["error"]


def test_transport_failure_after_headers_is_fixed_and_exception_is_scrubbed():
    failure = httpx.ReadError(CANARY + PHONE)

    class BrokenStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield chunk("Safe prefix").encode()
            raise failure

        async def aclose(self):
            self.closed = True

    body = BrokenStream()
    response = post(
        client(
            lambda request: httpx.Response(
                200,
                stream=body,
                headers={"content-type": "text/event-stream"},
            )
        ),
        stream=True,
    )
    assert response.status_code == 200
    assert CANARY not in response.text and PHONE not in response.text
    assert "[DONE]" not in response.text and '"upstream_error"' in response.text
    assert body.closed
    assert not failure.args and not failure.__dict__
    assert failure.__traceback__ is None and failure.__context__ is None


def test_eof_without_done_is_failure_and_does_not_flush_pending_data():
    response = post(
        client(
            lambda request: httpx.Response(
                200,
                content=chunk("[โทรศัพท์_"),
                headers={"content-type": "text/event-stream"},
            )
        ),
        stream=True,
    )
    assert "[โทรศัพท์_" not in response.text
    assert '"upstream_error"' in response.text and "[DONE]" not in response.text


def test_sse_comments_are_dropped_and_multiline_data_remains_supported():
    event = json.dumps({"choices": [{"index": 0, "delta": {"content": "Safe text"}}]}, indent=2)
    wire = ": " + CANARY + "\n\n" + "\n".join("data: " + line for line in event.splitlines())
    wire += "\n\ndata: [DONE]\n\n"
    response = post(
        client(
            lambda request: httpx.Response(
                200,
                content=wire,
                headers={"content-type": "text/event-stream"},
            )
        ),
        stream=True,
    )
    assert response.status_code == 200 and "Safe text" in response.text
    assert CANARY not in response.text and "data: [DONE]" in response.text


def test_invalid_unicode_in_a_held_sse_tail_is_a_fixed_failure():
    response = post(
        client(
            lambda request: httpx.Response(
                200,
                content=(chunk("[" + "\ud800") + "data: [DONE]\n\n").encode(),
                headers={"content-type": "text/event-stream"},
            )
        ),
        stream=True,
    )
    assert response.status_code == 200 and '"upstream_error"' in response.text
    assert "[DONE]" not in response.text


@pytest.mark.parametrize("stream", [False, True])
def test_body_and_transport_close_failures_are_value_free(stream):
    failure = RuntimeError(CANARY + PHONE)

    class Body(httpx.AsyncByteStream):
        close_attempted = False

        async def __aiter__(self):
            if stream:
                yield (chunk("[โทรศัพท์_") + "data: [DONE]\n\n").encode()
            else:
                yield json.dumps({"choices": [{"message": {"content": "Safe text"}}]}).encode()

        async def aclose(self):
            self.close_attempted = True
            raise failure

    class Transport(httpx.MockTransport):
        close_attempted = False

        async def aclose(self):
            self.close_attempted = True

    body = Body()
    transport = Transport(
        lambda request: httpx.Response(
            200,
            stream=body,
            headers={"content-type": "text/event-stream" if stream else "application/json"},
        )
    )
    response = post(client(None, transport=transport), stream=stream)
    assert CANARY not in response.text and PHONE not in response.text
    if stream:
        assert response.status_code == 200 and '"upstream_error"' in response.text
        assert "[โทรศัพท์_" not in response.text and "[DONE]" not in response.text
    else:
        assert response.status_code == 502 and response.json() == ERROR
    assert body.close_attempted and transport.close_attempted
    assert not failure.args and failure.__traceback__ is None


def asgi_request():
    return {
        "type": "http.request",
        "body": json.dumps(
            {
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "Synthetic contact: " + PHONE}],
                "stream": True,
            }
        ).encode(),
        "more_body": False,
    }


SCOPE = {
    "type": "http",
    "method": "POST",
    "scheme": "http",
    "path": "/v1/chat/completions",
    "raw_path": b"/v1/chat/completions",
    "root_path": "",
    "query_string": b"",
    "headers": [(b"content-type", b"application/json")],
    "http_version": "1.1",
    "server": ("localhost", 80),
    "client": ("127.0.0.1", 1234),
    "asgi": {"version": "3.0", "spec_version": "2.4"},
}


@pytest.mark.parametrize("stream", [False, True])
def test_cancellation_while_opening_upstream_closes_transport_and_drops_mapping(
    monkeypatch, stream
):
    import amphrang.proxy.server as module

    mappings = []
    original = module.sanitize_chat_request

    def capture(*args, **kwargs):
        sanitized, mapping = original(*args, **kwargs)
        mappings.append(mapping)
        return sanitized, mapping

    monkeypatch.setattr(module, "sanitize_chat_request", capture)

    async def exercise():
        entered = asyncio.Event()

        async def handler(request):
            entered.set()
            await asyncio.Event().wait()

        class Transport(httpx.MockTransport):
            closed = False

            async def aclose(self):
                self.closed = True

        transport = Transport(handler)
        app = app_for(None, transport=transport)
        sent = []
        request = asgi_request()
        payload = json.loads(request["body"])
        payload["stream"] = stream
        request["body"] = json.dumps(payload).encode()

        async def receive():
            return request

        async def send(message):
            sent.append(message)

        task = asyncio.create_task(app(SCOPE.copy(), receive, send))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport.closed and mappings == [{}]
        assert not sent

    asyncio.run(exercise())


@pytest.mark.parametrize("stream", [False, True])
def test_cancellation_during_response_cleanup_finishes_all_owned_cleanup(monkeypatch, stream):
    import amphrang.proxy.server as module

    mappings = []
    original = module.sanitize_chat_request

    def capture(*args, **kwargs):
        sanitized, mapping = original(*args, **kwargs)
        mappings.append(mapping)
        return sanitized, mapping

    monkeypatch.setattr(module, "sanitize_chat_request", capture)

    async def exercise():
        closing, release = asyncio.Event(), asyncio.Event()

        class Body(httpx.AsyncByteStream):
            closed = False

            async def __aiter__(self):
                pytest.fail("HTTP error body must not be read")
                yield b""

            async def aclose(self):
                closing.set()
                await release.wait()
                self.closed = True

        class Transport(httpx.MockTransport):
            closed = False

            async def aclose(self):
                self.closed = True

        body = Body()
        transport = Transport(lambda request: httpx.Response(503, stream=body))
        app = app_for(None, transport=transport)
        request = asgi_request()
        payload = json.loads(request["body"])
        payload["stream"] = stream
        request["body"] = json.dumps(payload).encode()

        async def receive():
            return request

        async def send(message):
            pytest.fail("Canceled request must not send a response")

        task = asyncio.create_task(app(SCOPE.copy(), receive, send))
        await asyncio.wait_for(closing.wait(), 2)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert body.closed and transport.closed and mappings == [{}]
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(exercise())


def test_provider_cancellation_drops_original_graph_and_credentials():
    failure = asyncio.CancelledError(CANARY)
    synthetic_key = "synthetic-proxy-provider-key"

    async def handler(request):
        raise failure

    async def exercise():
        app = create_app(
            "https://upstream.example",
            frozenset({"gpt-test"}),
            upstream_api_key=synthetic_key,
            transport=httpx.MockTransport(handler),
        )

        async def receive():
            return asgi_request()

        async def send(message):
            pytest.fail("Canceled request must not send a response")

        with pytest.raises(asyncio.CancelledError) as captured:
            await app(SCOPE.copy(), receive, send)
        error = captured.value
        assert error is not failure
        assert not failure.args and failure.__traceback__ is None
        assert CANARY not in str(error) and synthetic_key not in str(error)
        traceback = error.__traceback__
        product_frames = 0
        while traceback is not None:
            if "/amphrang/proxy/" in traceback.tb_frame.f_code.co_filename.replace("\\", "/"):
                product_frames += 1
                values = list(traceback.tb_frame.f_locals.values())
                assert CANARY not in values and synthetic_key not in values
                for value in values:
                    if isinstance(value, dict):
                        assert "Bearer " + synthetic_key not in value.values()
            traceback = traceback.tb_next
        assert product_frames

    asyncio.run(exercise())


def test_anyio_scope_cancellation_remains_owned_by_the_original_scope():
    import anyio

    async def exercise():
        with anyio.CancelScope() as scope:

            async def handler(request):
                scope.cancel()
                await anyio.lowlevel.checkpoint()

            app = app_for(handler)

            async def receive():
                return asgi_request()

            async def send(message):
                pytest.fail("Canceled scope must not send a response")

            await app(SCOPE.copy(), receive, send)
        assert scope.cancelled_caught

    anyio.run(exercise)


@pytest.mark.parametrize(
    "spec,mode",
    [
        ("2.4", "cancel"),
        ("2.3", "cancel"),
        ("2.4", "provider_cancel"),
        ("2.3", "provider_cancel"),
        ("2.4", "send_error"),
        ("2.3", "disconnect"),
    ],
)
def test_after_headers_failure_closes_resources_without_private_tail(monkeypatch, spec, mode):
    import amphrang.proxy.server as module

    mappings = []
    original = module.sanitize_chat_request

    def capture(*args, **kwargs):
        sanitized, mapping = original(*args, **kwargs)
        mappings.append(mapping)
        return sanitized, mapping

    monkeypatch.setattr(module, "sanitize_chat_request", capture)

    async def exercise():
        started, disconnected = asyncio.Event(), asyncio.Event()
        failure = asyncio.CancelledError(CANARY)

        class Body(httpx.AsyncByteStream):
            closed = False

            async def __aiter__(self):
                yield chunk("[โทรศัพท์_").encode()
                if mode == "provider_cancel":
                    raise failure
                await asyncio.Event().wait()

            async def aclose(self):
                self.closed = True

        class Transport(httpx.MockTransport):
            closed = False

            async def aclose(self):
                self.closed = True

        body = Body()
        transport = Transport(
            lambda request: httpx.Response(
                200,
                stream=body,
                headers={"content-type": "text/event-stream"},
            )
        )
        app = app_for(None, transport=transport)
        delivered = False
        sent = []

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return asgi_request()
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body":
                started.set()
                if mode == "send_error":
                    raise OSError(CANARY)

        scope = {**SCOPE, "asgi": {"version": "3.0", "spec_version": spec}}
        task = asyncio.create_task(app(scope, receive, send))
        await asyncio.wait_for(started.wait(), 2)
        if mode == "cancel":
            task.cancel()
        elif mode == "disconnect":
            disconnected.set()
        try:
            if mode in {"cancel", "provider_cancel"}:
                with pytest.raises(asyncio.CancelledError) as caught:
                    await asyncio.wait_for(task, 2)
                assert CANARY not in str(caught.value)
            elif mode == "send_error":
                with pytest.raises(RuntimeError, match="proxy stream delivery failed") as caught:
                    await asyncio.wait_for(task, 2)
                assert CANARY not in str(caught.value)
            else:
                await asyncio.wait_for(task, 2)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        assert body.closed and transport.closed and mappings == [{}]
        wire = b"".join(m.get("body", b"") for m in sent).decode()
        assert CANARY not in wire and PHONE not in wire and "[โทรศัพท์_" not in wire
        assert "[DONE]" not in wire
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(exercise())

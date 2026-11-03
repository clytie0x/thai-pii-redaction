"""OpenAI text proxy with request-owned mappings and value-free upstream errors."""

from __future__ import annotations

import json
import math
import secrets

import anyio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pii_redactor.config import CoreConfig
from pii_redactor.safe_errors import discard_exception_graph

import amphrang
from amphrang._core_config import sdk_core_config
from amphrang.proxy.core import (
    ProxyRequestError,
    validate_allowed_models,
)
from amphrang.proxy.core import _restore_text_with_config as restore_text
from amphrang.proxy.core import _sanitize_chat_request_with_config as sanitize_chat_request
from amphrang.proxy.stream_restore import StreamRestorer

_ENVELOPE_FIELDS = frozenset(
    {"id", "object", "created", "model", "choices", "usage", "system_fingerprint", "service_tier"}
)
_CHOICE_FIELDS = frozenset({"index", "message", "delta", "finish_reason", "logprobs"})
_FINISH_REASONS = (None, "stop", "length", "content_filter")


def _error(status: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"message": message, "type": error_type}}
    )


def _upstream_error_body() -> dict:
    return {"error": {"message": "upstream request failed", "type": "upstream_error"}}


def _upstream_error(status: int = 502) -> JSONResponse:
    return JSONResponse(status_code=status, content=_upstream_error_body())


class _UpstreamProtocolError(ValueError):
    def __init__(self):
        super().__init__("unsupported upstream response")


def _wire_json(value) -> str:
    text = json.dumps(value, ensure_ascii=False, allow_nan=False)
    text.encode("utf-8")
    return text


def _valid_usage(value) -> bool:
    if value is None:
        return True
    fields = {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_tokens_details",
        "completion_tokens_details",
        "cached_tokens",
        "audio_tokens",
        "reasoning_tokens",
        "accepted_prediction_tokens",
        "rejected_prediction_tokens",
    }
    if not isinstance(value, dict) or not set(value) <= fields:
        return False
    return all(
        _valid_usage(item) if isinstance(item, dict) else type(item) is int and item >= 0
        for item in value.values()
    )


def _valid_logprobs(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict) or not set(value) <= {"content", "refusal"}:
        return False
    for records in value.values():
        if records is None:
            continue
        if not isinstance(records, list):
            return False
        for record in records:
            if not isinstance(record, dict) or not set(record) <= {
                "token",
                "logprob",
                "bytes",
                "top_logprobs",
            }:
                return False
            if not isinstance(record.get("token"), str):
                return False
            score = record.get("logprob")
            if type(score) not in (int, float) or not math.isfinite(score):
                return False
            data = record.get("bytes")
            if data is not None and (
                not isinstance(data, list)
                or any(type(v) is not int or not 0 <= v <= 255 for v in data)
            ):
                return False
            top = record.get("top_logprobs")
            if top is not None and (
                not isinstance(top, list)
                or any(not isinstance(v, dict) or "top_logprobs" in v for v in top)
                or not _valid_logprobs({"content": top})
            ):
                return False
    return True


def _validate_completion(body, *, streaming: bool) -> None:
    if not isinstance(body, dict) or not set(body) <= _ENVELOPE_FIELDS:
        raise _UpstreamProtocolError()
    for key in ("id", "model", "system_fingerprint", "service_tier"):
        if key in body and body[key] is not None and not isinstance(body[key], str):
            raise _UpstreamProtocolError()
    if "created" in body and (type(body["created"]) is not int or body["created"] < 0):
        raise _UpstreamProtocolError()
    if "object" in body and body["object"] != (
        "chat.completion.chunk" if streaming else "chat.completion"
    ):
        raise _UpstreamProtocolError()
    if not _valid_usage(body.get("usage")):
        raise _UpstreamProtocolError()
    choices = body.get("choices")
    if not isinstance(choices, list) or (not choices and not (streaming and body.get("usage"))):
        raise _UpstreamProtocolError()
    indexes = set()
    for position, choice in enumerate(choices):
        if not isinstance(choice, dict) or not set(choice) <= _CHOICE_FIELDS:
            raise _UpstreamProtocolError()
        index = choice.get("index", position)
        if type(index) is not int or index < 0 or index in indexes:
            raise _UpstreamProtocolError()
        indexes.add(index)
        if choice.get("finish_reason") not in _FINISH_REASONS or not _valid_logprobs(
            choice.get("logprobs")
        ):
            raise _UpstreamProtocolError()
        field = "delta" if streaming else "message"
        if ("message" if streaming else "delta") in choice:
            raise _UpstreamProtocolError()
        message = choice.get(field)
        if not isinstance(message, dict) or not set(message) <= {"role", "content", "refusal"}:
            raise _UpstreamProtocolError()
        if message.get("role", "assistant") != "assistant" or message.get("refusal") is not None:
            raise _UpstreamProtocolError()
        content = message.get("content")
        if not isinstance(content, str) and not (streaming and content is None):
            raise _UpstreamProtocolError()
    _wire_json(body)


def _restore_completion(body: dict, mapping: dict[str, str], *, config: CoreConfig) -> dict:
    _validate_completion(body, streaming=False)
    for choice in body["choices"]:
        message = choice["message"]
        message["content"] = restore_text(message["content"], mapping, config=config)
    return body


class _SSEProcessor:
    """Validate complete SSE events before restoring supported text deltas."""

    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping
        self._restorers: dict[int, StreamRestorer] = {}
        self._template: dict | None = None
        self._data: list[str] = []
        self.done = False

    def process_line(self, line: str) -> list[str]:
        if line.startswith(":"):
            return []
        if line:
            field, separator, value = line.partition(":")
            if not separator:
                raise _UpstreamProtocolError()
            value = value.removeprefix(" ")
            if field == "data":
                self._data.append(value)
            elif field != "event" or value != "message":
                raise _UpstreamProtocolError()
            return []
        if not self._data:
            return []
        data = "\n".join(self._data)
        self._data.clear()
        if data == "[DONE]":
            self.done = True
            return []
        parsed = json.loads(data)
        _validate_completion(parsed, streaming=True)
        self._template = {key: value for key, value in parsed.items() if key != "choices"}
        for position, choice in enumerate(parsed["choices"]):
            delta = choice["delta"]
            if isinstance(delta.get("content"), str):
                index = choice.get("index", position)
                restorer = self._restorers.setdefault(index, StreamRestorer(self._mapping))
                delta["content"] = restorer.feed(delta["content"])
        return ["data: " + _wire_json(parsed) + "\n\n"]

    def finish(self) -> list[str]:
        out = []
        for index, restorer in self._restorers.items():
            leftover = restorer.flush()
            if leftover and self._template is not None:
                synthetic = dict(self._template)
                synthetic["choices"] = [
                    {"index": index, "delta": {"content": leftover}, "finish_reason": None}
                ]
                out.append("data: " + _wire_json(synthetic) + "\n\n")
        out.append("data: [DONE]\n\n")
        return out

    def discard(self) -> None:
        for restorer in self._restorers.values():
            restorer.discard()
        self._restorers.clear()
        self._data.clear()
        self._template = None


async def _close_resources(upstream, client) -> bool:
    success = True

    async def close_all():
        nonlocal success
        with anyio.CancelScope(shield=True):
            for resource in (upstream, client):
                if resource is not None:
                    try:
                        await resource.aclose()
                    except (Exception, anyio.get_cancelled_exc_class()) as error:
                        discard_exception_graph(error)
                        success = False

    # A child task also survives direct asyncio cancellation of the request task.
    with anyio.CancelScope(shield=True):
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(close_all)
    return success


class _CancelledResponse(Response):
    """Re-raise cancellation after the sensitive handler frames have returned."""

    async def __call__(self, scope, receive, send):
        del self, scope, receive, send
        await anyio.lowlevel.checkpoint_if_cancelled()
        cancelled = None
        with anyio.CancelScope() as cancel_scope:
            cancel_scope.cancel()
            try:
                await anyio.lowlevel.checkpoint()
            except anyio.get_cancelled_exc_class() as error:
                discard_exception_graph(error)
                cancelled = error
        if cancelled is None:
            raise RuntimeError("proxy cancellation failed")
        raise cancelled from None


class _StreamCancellation(Exception):
    """Carry cancellation across an ASGI 2.3 stream task group without payload."""


def _contains_stream_cancellation(error: BaseException) -> bool:
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, _StreamCancellation):
            return True
        if isinstance(current, BaseExceptionGroup):
            pending.extend(BaseExceptionGroup.exceptions.__get__(current))
    return False


class _ClosingStreamingResponse(StreamingResponse):
    def __init__(self, content, *, cleanup):
        super().__init__(content, media_type="text/event-stream")
        self._cleanup = cleanup

    async def __call__(self, scope, receive, send):
        cancelled = False
        failed = False
        try:
            await super().__call__(scope, receive, send)
        except anyio.get_cancelled_exc_class() as error:
            discard_exception_graph(error)
            cancelled = True
        except Exception as error:
            cancelled = _contains_stream_cancellation(error)
            discard_exception_graph(error)
            failed = not cancelled
        finally:
            try:
                await self._cleanup()
            except anyio.get_cancelled_exc_class() as error:
                discard_exception_graph(error)
                cancelled = True
        if cancelled or failed:
            self = scope = receive = send = None
            if cancelled:
                await _CancelledResponse()(None, None, None)
            raise RuntimeError("proxy stream delivery failed") from None


def create_app(
    upstream_base_url: str,
    allowed_models: frozenset[str],
    upstream_api_key: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout_s: float = 120.0,
) -> FastAPI:
    core_config = sdk_core_config()
    configured_models = validate_allowed_models(allowed_models)
    if not callable(getattr(anyio.TaskInfo, "has_pending_cancellation", None)):
        upstream_api_key = None
        upstream_base_url = ""
        transport = allowed_models = configured_models = None
        raise RuntimeError("proxy requires amphrang[proxy] with AnyIO >=4.4.0")
    app = FastAPI(title="amphrang sanitizing proxy", docs_url=None, redoc_url=None)

    async def _open(sanitized):
        client = None
        try:
            client = httpx.AsyncClient(
                base_url=upstream_base_url, transport=transport, timeout=timeout_s
            )
            headers = {"content-type": "application/json"}
            if upstream_api_key:
                headers["authorization"] = f"Bearer {upstream_api_key}"
            request = client.build_request(
                "POST", "/v1/chat/completions", json=sanitized, headers=headers
            )
            upstream = await client.send(request, stream=True)
            return client, upstream
        except BaseException as error:
            if not isinstance(error, Exception):
                await _close_resources(None, client)
                raise
            discard_exception_graph(error)
        await _close_resources(None, client)
        return None, None

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        try:
            return await _handle_chat(request)
        except anyio.get_cancelled_exc_class() as error:
            discard_exception_graph(error)
            return _CancelledResponse()

    async def _handle_chat(request: Request):
        try:
            payload = json.loads(await request.body())
            if not isinstance(payload, dict):
                raise ValueError("body is not an object")
        except ValueError as error:
            discard_exception_graph(error)
            return _error(400, "request body is not a JSON object", "invalid_request_error")
        try:
            sanitized, mapping = sanitize_chat_request(
                payload,
                salt=secrets.token_hex(16),
                allowed_models=configured_models,
                config=core_config,
            )
        except ProxyRequestError as error:
            return _error(422, str(error), "invalid_request_error")
        except amphrang.LeakBlockedError as error:
            leak_types = ", ".join(error.leak_types)
            discard_exception_graph(error)
            return _error(
                422, f"mask would still leak ({leak_types}); nothing was forwarded", "leak_blocked"
            )
        if sanitized.get("stream") is True:
            return await _forward_stream(sanitized, mapping)
        return await _forward(sanitized, mapping)

    async def _forward(sanitized, mapping) -> Response:
        client, upstream = None, None
        body = None
        response = None
        status = 502
        try:
            client, upstream = await _open(sanitized)
            if upstream is not None:
                if 400 <= upstream.status_code < 600:
                    status = upstream.status_code
                elif 200 <= upstream.status_code < 300:
                    await upstream.aread()
                    body = _restore_completion(upstream.json(), mapping, config=core_config)
                    status = upstream.status_code
                    response = JSONResponse(status_code=status, content=body)
        except Exception as error:
            discard_exception_graph(error)
            body = None
            response = None
            status = 502
        finally:
            try:
                closed = await _close_resources(upstream, client)
            finally:
                mapping.clear()
        if not closed:
            body = None
            response = None
            status = 502
        return response if response is not None else _upstream_error(status)

    async def _forward_stream(sanitized, mapping) -> Response:
        try:
            client, upstream = await _open(sanitized)
        except BaseException:
            mapping.clear()
            raise
        if upstream is None:
            mapping.clear()
            return _upstream_error()
        if (
            not 200 <= upstream.status_code < 300
            or upstream.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "text/event-stream"
        ):
            status = upstream.status_code if 400 <= upstream.status_code < 600 else 502
            try:
                closed = await _close_resources(upstream, client)
            finally:
                mapping.clear()
            return _upstream_error(status if closed else 502)
        upstream.encoding = "utf-8"
        processor = _SSEProcessor(mapping)

        async def cleanup():
            try:
                await _close_resources(upstream, client)
            finally:
                processor.discard()
                mapping.clear()

        async def stream_body():
            failed = False
            provider_cancelled = False
            try:
                try:
                    async for line in upstream.aiter_lines():
                        for out in processor.process_line(line):
                            yield out
                        if processor.done:
                            break
                    failed = not processor.done
                except anyio.get_cancelled_exc_class() as error:
                    if anyio.get_current_task().has_pending_cancellation():
                        raise
                    discard_exception_graph(error)
                    provider_cancelled = True
                except Exception as error:
                    discard_exception_graph(error)
                    failed = True
                closed = await _close_resources(upstream, client)
                if provider_cancelled:
                    raise _StreamCancellation() from None
                if failed or not closed:
                    processor.discard()
                    yield "data: " + json.dumps(_upstream_error_body(), ensure_ascii=False) + "\n\n"
                else:
                    try:
                        terminal = processor.finish()
                    except Exception as error:
                        discard_exception_graph(error)
                        terminal = ["data: " + _wire_json(_upstream_error_body()) + "\n\n"]
                    for out in terminal:
                        yield out
            finally:
                await cleanup()

        return _ClosingStreamingResponse(stream_body(), cleanup=cleanup)

    return app

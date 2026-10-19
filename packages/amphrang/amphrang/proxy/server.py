"""OpenAI-compatible sanitizing proxy.

An existing app points its ``base_url`` here; the proxy masks Thai PII on the
way to the configured upstream and restores it on the way back — streaming
included. The token→original mapping lives only in request-scoped memory and
is dropped when the request ends. Fail-closed: a request whose mask would
still leak is answered 422 and never forwarded.

Errors reuse the OpenAI wire shape (``{"error": {"message", "type"}}``) so
stock clients surface them normally; proxy-side failures are value-free.
"""

from __future__ import annotations

import json
import secrets

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

import amphrang
from amphrang.engine.safe_errors import discard_exception_graph
from amphrang.proxy.core import (
    ProxyRequestError,
    restore_text,
    sanitize_chat_request,
    validate_allowed_models,
)
from amphrang.proxy.stream_restore import StreamRestorer

_HOP_HEADERS = {"host", "content-length", "authorization", "connection", "accept-encoding"}


def _error(status: int, message: str, error_type: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": error_type}},
    )


def _restore_completion(body: dict, mapping: dict[str, str]) -> dict:
    for choice in body.get("choices", []):
        message = choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            message["content"] = restore_text(message["content"], mapping)
    return body


def _restore_json_strings(value, mapping: dict[str, str]):
    """Recursively restore JSON string values while preserving keys and shape."""
    if isinstance(value, str):
        return restore_text(value, mapping)
    if isinstance(value, list):
        return [_restore_json_strings(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: _restore_json_strings(item, mapping) for key, item in value.items()}
    return value


class _SSEProcessor:
    """Re-emit upstream SSE line by line, restoring delta content per choice.

    Any tail a restorer still holds at [DONE] is emitted as one synthetic
    chunk first, so no held-back text is ever dropped — and nothing beyond
    one line plus one token-length of holdback is ever buffered.
    """

    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping
        self._restorers: dict[int, StreamRestorer] = {}
        self._template: dict | None = None

    def process_line(self, line: str) -> list[str]:
        if not line.startswith("data: "):
            # aiter_lines yields the blank event separators too; we re-add
            # our own, so only non-blank non-data lines pass through.
            return [line + "\n\n"] if line.strip() else []
        data = line[len("data: ") :]
        if data.strip() == "[DONE]":
            out: list[str] = []
            for index, restorer in self._restorers.items():
                leftover = restorer.flush()
                if leftover and self._template is not None:
                    synthetic = dict(self._template)
                    synthetic["choices"] = [
                        {"index": index, "delta": {"content": leftover}, "finish_reason": None}
                    ]
                    out.append("data: " + json.dumps(synthetic, ensure_ascii=False) + "\n\n")
            out.append("data: [DONE]\n\n")
            return out
        try:
            parsed = json.loads(data)
        except ValueError:
            return [line + "\n\n"]
        self._template = {key: value for key, value in parsed.items() if key != "choices"}
        for choice in parsed.get("choices", []):
            delta = choice.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                index = choice.get("index", 0)
                restorer = self._restorers.setdefault(index, StreamRestorer(self._mapping))
                delta["content"] = restorer.feed(delta["content"])
        return ["data: " + json.dumps(parsed, ensure_ascii=False) + "\n\n"]


def create_app(
    upstream_base_url: str,
    allowed_models: frozenset[str],
    upstream_api_key: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout_s: float = 120.0,
) -> FastAPI:
    configured_models = validate_allowed_models(allowed_models)
    app = FastAPI(title="amphrang sanitizing proxy", docs_url=None, redoc_url=None)

    def _upstream_headers() -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if upstream_api_key:
            headers["authorization"] = f"Bearer {upstream_api_key}"
        return headers

    def _client() -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=upstream_base_url, transport=transport, timeout=timeout_s)

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
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
            )
        except ProxyRequestError as error:
            return _error(422, str(error), "invalid_request_error")
        except amphrang.LeakBlockedError as error:
            leak_types = ", ".join(error.leak_types)
            discard_exception_graph(error)
            return _error(
                422,
                f"mask would still leak ({leak_types}); nothing was forwarded",
                "leak_blocked",
            )

        if sanitized.get("stream") is True:
            return await _forward_stream(sanitized, mapping)
        return await _forward(sanitized, mapping)

    async def _forward(sanitized: dict, mapping: dict[str, str]) -> Response:
        async with _client() as client:
            try:
                upstream = await client.post(
                    "/v1/chat/completions", json=sanitized, headers=_upstream_headers()
                )
            except httpx.HTTPError as error:
                discard_exception_graph(error)
                return _error(502, "upstream request failed", "upstream_error")
        try:
            body = upstream.json()
        except ValueError:
            return Response(
                content=restore_text(upstream.text, mapping),
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "text/plain"),
            )
        if upstream.status_code < 400:
            body = _restore_completion(body, mapping)
        else:
            body = _restore_json_strings(body, mapping)
        return JSONResponse(status_code=upstream.status_code, content=body)

    async def _forward_stream(sanitized: dict, mapping: dict[str, str]) -> Response:
        client = _client()
        try:
            upstream_request = client.build_request(
                "POST", "/v1/chat/completions", json=sanitized, headers=_upstream_headers()
            )
            upstream = await client.send(upstream_request, stream=True)
        except httpx.HTTPError as error:
            discard_exception_graph(error)
            await client.aclose()
            return _error(502, "upstream request failed", "upstream_error")

        if upstream.status_code >= 400:
            body = await upstream.aread()
            await upstream.aclose()
            await client.aclose()
            return Response(
                content=restore_text(body.decode("utf-8", "replace"), mapping),
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )

        async def stream_body():
            processor = _SSEProcessor(mapping)
            try:
                async for line in upstream.aiter_lines():
                    for out in processor.process_line(line):
                        yield out
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(stream_body(), media_type="text/event-stream")

    return app

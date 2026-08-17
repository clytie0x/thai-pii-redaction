"""Internal ASGI routes for staged Hosted 3.0 implementation."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from pii_redactor.safe_errors import discard_exception_graph

from .approval import ApprovalEngine, ApprovalError, derive_approval_key
from .authority import AuthorityContext
from .document_preview import DocumentPreviewService
from .execution import ExecuteError, ExecuteService
from .http_v2 import (
    CONTRACT_VERSION,
    SERVER_TIME_HEADER,
    SERVICE_CLASS_HEADER,
    SESSION_EXPIRES_HEADER,
    error_payload,
)
from .legacy_roundtrip import LEGACY_ROUNDTRIP_PATH, legacy_roundtrip_authority
from .preview import (
    CUSTOM_INITIAL_REMAINING_SECONDS,
    PreviewError,
    PreviewService,
    default_bindings,
    document_bindings,
)
from .provider_queue import (
    CLAIM_LONG_POLL_SECONDS,
    CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS,
    ProviderQueue,
    ProviderQueueError,
    derive_provider_queue_key,
)

PROTECTION_PREVIEW_PATH = "/api/protection-preview"
GUEST_PREVIEW_PATH = "/api/guest/preview"
DOCUMENT_PREVIEW_PATH = "/api/document-preview"
HOSTED3_PREVIEW_PATHS = frozenset(
    {PROTECTION_PREVIEW_PATH, GUEST_PREVIEW_PATH, DOCUMENT_PREVIEW_PATH}
)
QUEUE_JOIN_PATH = "/api/provider-queue/join"
QUEUE_STATUS_PATH = "/api/provider-queue/status"
QUEUE_CLAIM_PATH = "/api/provider-queue/claim"
QUEUE_CANCEL_PATH = "/api/provider-queue/cancel"
HOSTED3_QUEUE_PATHS = frozenset(
    {QUEUE_JOIN_PATH, QUEUE_STATUS_PATH, QUEUE_CLAIM_PATH, QUEUE_CANCEL_PATH}
)
GUEST_EXECUTE_PATH = "/api/guest/execute"
PROTECTION_EXECUTE_PATH = "/api/protection-execute"
DOCUMENT_EXECUTE_PATH = "/api/document-execute"
HOSTED3_EXECUTE_PATHS = frozenset(
    {GUEST_EXECUTE_PATH, PROTECTION_EXECUTE_PATH, DOCUMENT_EXECUTE_PATH}
)
HOSTED3_INTERNAL_PATHS = (
    HOSTED3_PREVIEW_PATHS | HOSTED3_QUEUE_PATHS | HOSTED3_EXECUTE_PATHS
)
MAX_PREVIEW_BODY_BYTES = 96 * 1024
MAX_DOCUMENT_BODY_BYTES = 5 * 1024 * 1024
MAX_QUEUE_BODY_BYTES = 12 * 1024
MAX_EXECUTE_BODY_BYTES = 96 * 1024


class _RequestDisconnected(Exception):
    """Internal ASGI outcome that must never be serialized after disconnect."""


class _ResponseUnavailable(Exception):
    """Internal send failure that must escape HTTP error serialization."""


def _run_synthetic_document_execute(
    service: ExecuteService,
    request: object,
    authority: AuthorityContext,
) -> dict[str, object]:
    """Run parser plus blocking provider work outside the ASGI event loop."""
    return asyncio.run(
        service.execute_synthetic_document(
            request,
            authority=authority,
        )
    )


def _read_version() -> str:
    try:
        return (Path(__file__).resolve().parent.parent / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return "3.0.1"


def _strict_json(body: bytes) -> object:
    duplicate = False

    def pairs(rows):
        nonlocal duplicate
        output = {}
        for key, value in rows:
            if key in output:
                duplicate = True
            output[key] = value
        return output

    try:
        value = json.loads(body, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PreviewError("request_schema_invalid", status=422) from None
    if duplicate:
        raise PreviewError("request_schema_invalid", status=422)
    return value


class Hosted3Overlay:
    """Handle unexposed Hosted 3.0 routes before the vendored FastAPI app."""

    def __init__(
        self,
        app,
        *,
        environ: Mapping[str, str] | None = None,
        service: PreviewService | None = None,
        document_service: DocumentPreviewService | None = None,
        queue: ProviderQueue | None = None,
        execute_service: ExecuteService | None = None,
        now: Callable[[], float] | None = None,
    ):
        config = os.environ if environ is None else environ
        self._app = app
        self._now = time.time if now is None else now
        api_key = config.get("AIGUARD_API_KEY", "")
        self._api_key = api_key.encode("utf-8")
        approval: ApprovalEngine | None = None
        if service is None:
            signing = config.get("AIFT_COOKIE_SIGNING_KEY", "").encode("utf-8")
            approval = ApprovalEngine(
                derive_approval_key(signing),
                default_bindings(),
                document_bindings=document_bindings(),
                now=self._now,
            )
            service = PreviewService(
                approval,
                hosted_version=_read_version(),
                now=self._now,
            )
            if queue is None:
                queue = ProviderQueue(
                    derive_provider_queue_key(signing),
                    approval,
                    now=self._now,
                )
        self._service = service
        self._queue = queue
        self._document_service = (
            DocumentPreviewService(
                approval,
                hosted_version=_read_version(),
                now=self._now,
            )
            if document_service is None and approval is not None
            else document_service
        )
        self._execute_service = (
            ExecuteService(queue, hosted_version=_read_version())
            if (
                execute_service is None
                and approval is not None
                and isinstance(queue, ProviderQueue)
            )
            else execute_service
        )

    @property
    def provider_queue(self) -> ProviderQueue:
        """Return the one process-local scheduler shared by all provider paths."""

        if not isinstance(self._queue, ProviderQueue):
            raise RuntimeError("Hosted 3 provider queue is unavailable")
        return self._queue

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == LEGACY_ROUNDTRIP_PATH:
            authority = (scope.get("state") or {}).get("aiguard_authority")
            with legacy_roundtrip_authority(
                authority if isinstance(authority, AuthorityContext) else None
            ):
                await self._app(scope, receive, send)
            return
        if scope.get("type") != "http" or scope.get("path") not in HOSTED3_INTERNAL_PATHS:
            await self._app(scope, receive, send)
            return
        path = scope.get("path")
        authority = (scope.get("state") or {}).get("aiguard_authority")
        if not isinstance(authority, AuthorityContext):
            await self._error(send, 401, "authentication_required", authority=None)
            return
        expected_method = "GET" if path == QUEUE_STATUS_PATH else "POST"
        if scope.get("method") != expected_method:
            await self._error(send, 405, "method_not_allowed", authority=authority)
            return
        if scope.get("query_string", b""):
            await self._error(send, 422, "request_schema_invalid", authority=authority)
            return
        if self._headers(scope, b"x-aiguard-contract-version") != [
            str(CONTRACT_VERSION).encode("ascii")
        ]:
            await self._error(send, 426, "contract_version_required", authority=authority)
            return
        supplied_keys = self._headers(scope, b"x-aiguard-key")
        if (
            len(supplied_keys) != 1
            or not self._api_key
            or not hmac.compare_digest(supplied_keys[0], self._api_key)
        ):
            await self._error(send, 401, "authentication_required", authority=authority)
            return
        if path in HOSTED3_QUEUE_PATHS:
            await self._queue_http(scope, receive, send, authority=authority)
            return
        if path in HOSTED3_EXECUTE_PATHS:
            await self._execute_http(scope, receive, send, authority=authority)
            return
        if authority.expires_at_unix - int(self._now()) < CUSTOM_INITIAL_REMAINING_SECONDS:
            await self._error(send, 409, "session_review_window", authority=authority)
            return
        if path == DOCUMENT_PREVIEW_PATH:
            if self._document_service is None:
                await self._error(
                    send,
                    503,
                    "document_parser_unavailable",
                    authority=authority,
                )
                return
            await self._document_preview(scope, receive, send, authority=authority)
            return
        content_types = self._headers(scope, b"content-type")
        if len(content_types) != 1 or content_types[0].split(b";", 1)[0].strip().lower() != b"application/json":
            await self._error(send, 422, "request_schema_invalid", authority=authority)
            return
        lengths = self._headers(scope, b"content-length")
        if len(lengths) > 1:
            await self._error(send, 422, "request_schema_invalid", authority=authority)
            return
        if lengths:
            try:
                declared = int(lengths[0])
            except ValueError:
                declared = -1
            if declared < 0:
                await self._error(send, 422, "request_schema_invalid", authority=authority)
                return
            if declared > MAX_PREVIEW_BODY_BYTES:
                await self._error(send, 413, "payload_too_large", authority=authority)
                return
        body = await self._read_body(receive)
        if body is None:
            await self._error(send, 413, "payload_too_large", authority=authority)
            return
        try:
            request = _strict_json(body)
            body = b""
            if path == GUEST_PREVIEW_PATH:
                if self._document_service is None:
                    raise PreviewError("document_parser_unavailable", status=503)
                response = await self._document_service.preview_scenario(
                    request,
                    authority=authority,
                )
            else:
                response = self._service.preview_custom(request, authority=authority)
        except PreviewError as error:
            await self._error(send, error.status, error.code, authority=authority)
            return
        except Exception:
            await self._error(send, 500, "internal_error", authority=authority)
            return
        await self._json(send, 200, response, authority=authority)

    async def _execute_http(
        self,
        scope,
        receive,
        send,
        *,
        authority: AuthorityContext,
    ) -> None:
        if self._execute_service is None:
            await self._error(send, 500, "internal_error", authority=authority)
            return
        request: dict[str, object] | None = None
        try:
            request = await self._execute_json_request(scope, receive)
            path = scope.get("path")
            if path == GUEST_EXECUTE_PATH:
                response = await asyncio.to_thread(
                    _run_synthetic_document_execute,
                    self._execute_service,
                    request,
                    authority,
                )
            elif path == PROTECTION_EXECUTE_PATH:
                response = await asyncio.to_thread(
                    self._execute_service.execute_custom,
                    request,
                    authority=authority,
                )
            elif path == DOCUMENT_EXECUTE_PATH:
                response = await asyncio.to_thread(
                    self._execute_service.execute_uploaded_document,
                    request,
                    authority=authority,
                )
            else:  # pragma: no cover - exact dispatch set above
                raise PreviewError("request_schema_invalid", status=422)
            await self._queue_json_response(
                send,
                200,
                response,
                authority=authority,
            )
        except _RequestDisconnected:
            return
        except _ResponseUnavailable:
            raise
        except ExecuteError as error:
            code = error.code
            discard_exception_graph(error)
            error = None
            await self._error(
                send,
                error_payload(code)["error"]["status"],
                code,
                authority=authority,
            )
        except ApprovalError as error:
            code = error.code
            discard_exception_graph(error)
            error = None
            await self._error(
                send,
                error_payload(code)["error"]["status"],
                code,
                authority=authority,
            )
        except ProviderQueueError as error:
            code = error.code
            discard_exception_graph(error)
            error = None
            await self._error(
                send,
                error_payload(code)["error"]["status"],
                code,
                authority=authority,
            )
        except PreviewError as error:
            await self._error(send, error.status, error.code, authority=authority)
        except Exception:
            await self._error(send, 500, "internal_error", authority=authority)
        finally:
            if request is not None:
                request.clear()

    async def _queue_http(
        self,
        scope,
        receive,
        send,
        *,
        authority: AuthorityContext,
    ) -> None:
        if self._queue is None:
            await self._error(send, 500, "internal_error", authority=authority)
            return
        path = scope.get("path")
        request: dict[str, object] | None = None
        try:
            if path == QUEUE_STATUS_PATH:
                if not await self._empty_request(scope, receive):
                    raise PreviewError("request_schema_invalid", status=422)
                response = self._queue.status(authority=authority)
                await self._queue_json_response(
                    send,
                    200,
                    response,
                    authority=authority,
                )
                return

            request = await self._queue_json_request(scope, receive)
            if path == QUEUE_JOIN_PATH:
                if set(request) != {"ticket"} or not isinstance(
                    request.get("ticket"), str
                ):
                    raise PreviewError("request_schema_invalid", status=422)
                response = self._queue.join(
                    str(request["ticket"]),
                    authority=authority,
                )
                await self._queue_json_response(
                    send,
                    201,
                    response,
                    authority=authority,
                )
                return
            if path == QUEUE_CLAIM_PATH:
                if set(request) != {"queue_capability", "last_revision"}:
                    raise PreviewError("request_schema_invalid", status=422)
                capability = request.get("queue_capability")
                revision = request.get("last_revision")
                if not isinstance(capability, str) or type(revision) is not int:
                    raise PreviewError("request_schema_invalid", status=422)
                await self._queue_claim(
                    receive,
                    send,
                    authority=authority,
                    queue_capability=capability,
                    last_revision=revision,
                )
                return
            if path == QUEUE_CANCEL_PATH:
                if request:
                    raise PreviewError("request_schema_invalid", status=422)
                self._queue.cancel(authority=authority)
                await self._queue_empty_response(send, authority=authority)
                return
            raise PreviewError("request_schema_invalid", status=422)
        except _RequestDisconnected:
            return
        except _ResponseUnavailable:
            raise
        except PreviewError as error:
            await self._error(send, error.status, error.code, authority=authority)
        except ApprovalError as error:
            await self._error(
                send,
                error_payload(error.code)["error"]["status"],
                error.code,
                authority=authority,
            )
        except ProviderQueueError as error:
            if error.code == "queue_poll_cancelled":
                return
            await self._error(
                send,
                error_payload(error.code)["error"]["status"],
                error.code,
                authority=authority,
            )
        except Exception:
            await self._error(send, 500, "internal_error", authority=authority)
        finally:
            if request is not None:
                request.clear()

    async def _queue_json_response(
        self,
        send,
        status: int,
        payload: dict[str, object],
        *,
        authority: AuthorityContext,
    ) -> None:
        try:
            await self._json(send, status, payload, authority=authority)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise _ResponseUnavailable(str(error)) from error

    async def _queue_empty_response(
        self,
        send,
        *,
        authority: AuthorityContext,
    ) -> None:
        try:
            await self._empty(send, 204, authority=authority)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise _ResponseUnavailable(str(error)) from error

    async def _queue_claim(
        self,
        receive,
        send,
        *,
        authority: AuthorityContext,
        queue_capability: str,
        last_revision: int,
    ) -> None:
        cancelled = threading.Event()
        disconnect_task = asyncio.create_task(self._wait_for_disconnect(receive))
        claim_task = asyncio.create_task(
            asyncio.to_thread(
                self._queue.claim,
                queue_capability,
                last_revision=last_revision,
                authority=authority,
                wait_seconds=CLAIM_LONG_POLL_SECONDS,
                cancelled=cancelled.is_set,
                execute_ack_pending=True,
            )
        )
        response: dict[str, object] | None = None
        try:
            done, _ = await asyncio.wait(
                {claim_task, disconnect_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if claim_task in done and disconnect_task not in done:
                await asyncio.sleep(0)
            if disconnect_task.done() and disconnect_task.result():
                cancelled.set()
                self._queue.wake_claims()
                try:
                    response = await asyncio.shield(claim_task)
                except Exception:
                    response = None
                self._abandon_response_claim(
                    response,
                    authority=authority,
                    queue_capability=queue_capability,
                )
                return
            response = await claim_task

            # ASGI cannot distinguish a browser that received the response
            # from Uvicorn's normal post-response ``http.disconnect`` sentinel.
            # Stop reading before the response; the browser's execute request
            # is the only reliable acknowledgement of a returned claim.
            if not disconnect_task.done():
                disconnect_task.cancel()
            try:
                await disconnect_task
            except BaseException:
                pass

            send_task = asyncio.create_task(
                self._json(send, 200, response, authority=authority)
            )

            async def stop_send() -> None:
                if not send_task.done():
                    send_task.cancel()
                try:
                    await send_task
                except BaseException:
                    pass

            try:
                await asyncio.wait_for(
                    send_task,
                    timeout=CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS,
                )
            except asyncio.CancelledError:
                await stop_send()
                self._abandon_response_claim(
                    response,
                    authority=authority,
                    queue_capability=queue_capability,
                )
                raise
            except asyncio.TimeoutError as error:
                self._abandon_response_claim(
                    response,
                    authority=authority,
                    queue_capability=queue_capability,
                )
                raise _ResponseUnavailable("claim response send timed out") from error
            except Exception as error:
                self._abandon_response_claim(
                    response,
                    authority=authority,
                    queue_capability=queue_capability,
                )
                raise _ResponseUnavailable(str(error)) from error
            if response.get("state") != "claim_ready":
                return
            if not isinstance(response.get("claim_token"), str):
                raise _ResponseUnavailable("claim response omitted its token")
        except asyncio.CancelledError:
            cancelled.set()
            self._queue.wake_claims()
            try:
                response = await asyncio.shield(claim_task)
            except Exception:
                response = None
            self._abandon_response_claim(
                response,
                authority=authority,
                queue_capability=queue_capability,
            )
            raise
        finally:
            if not disconnect_task.done():
                disconnect_task.cancel()
            try:
                await disconnect_task
            except BaseException:
                pass

    def _abandon_response_claim(
        self,
        response: dict[str, object] | None,
        *,
        authority: AuthorityContext,
        queue_capability: str,
    ) -> None:
        if (
            not isinstance(response, dict)
            or response.get("state") != "claim_ready"
            or not isinstance(response.get("claim_token"), str)
        ):
            return
        try:
            self._queue.abandon_undelivered_claim(
                queue_capability,
                str(response["claim_token"]),
                authority=authority,
            )
        except ProviderQueueError:
            pass

    async def _queue_json_request(self, scope, receive) -> dict[str, object]:
        content_types = self._headers(scope, b"content-type")
        if (
            len(content_types) != 1
            or content_types[0].split(b";", 1)[0].strip().lower()
            != b"application/json"
            or self._headers(scope, b"content-encoding")
            or self._headers(scope, b"transfer-encoding")
        ):
            raise PreviewError("request_schema_invalid", status=422)
        lengths = self._headers(scope, b"content-length")
        if len(lengths) != 1:
            raise PreviewError("request_schema_invalid", status=422)
        try:
            declared = int(lengths[0])
        except ValueError:
            declared = -1
        if declared < 2:
            raise PreviewError("request_schema_invalid", status=422)
        if declared > MAX_QUEUE_BODY_BYTES:
            raise PreviewError("payload_too_large", status=413)
        body = await self._read_queue_body(receive, max_bytes=MAX_QUEUE_BODY_BYTES)
        if len(body) != declared:
            raise PreviewError("request_schema_invalid", status=422)
        value = _strict_json(body)
        body = b""
        if not isinstance(value, dict):
            raise PreviewError("request_schema_invalid", status=422)
        return value

    async def _execute_json_request(self, scope, receive) -> dict[str, object]:
        content_types = self._headers(scope, b"content-type")
        if (
            len(content_types) != 1
            or content_types[0].split(b";", 1)[0].strip().lower()
            != b"application/json"
            or self._headers(scope, b"content-encoding")
            or self._headers(scope, b"transfer-encoding")
        ):
            raise PreviewError("request_schema_invalid", status=422)
        lengths = self._headers(scope, b"content-length")
        if len(lengths) != 1:
            raise PreviewError("request_schema_invalid", status=422)
        try:
            declared = int(lengths[0])
        except ValueError:
            declared = -1
        if declared < 2:
            raise PreviewError("request_schema_invalid", status=422)
        if declared > MAX_EXECUTE_BODY_BYTES:
            raise PreviewError("payload_too_large", status=413)
        body = await self._read_queue_body(
            receive,
            max_bytes=MAX_EXECUTE_BODY_BYTES,
        )
        if len(body) != declared:
            raise PreviewError("request_schema_invalid", status=422)
        value = _strict_json(body)
        body = b""
        if not isinstance(value, dict):
            raise PreviewError("request_schema_invalid", status=422)
        return value

    async def _empty_request(self, scope, receive) -> bool:
        if (
            self._headers(scope, b"content-type")
            or self._headers(scope, b"content-encoding")
            or self._headers(scope, b"transfer-encoding")
        ):
            return False
        lengths = self._headers(scope, b"content-length")
        if len(lengths) > 1 or (lengths and lengths != [b"0"]):
            return False
        body = await self._read_queue_body(receive, max_bytes=0)
        return body == b""

    @staticmethod
    async def _read_queue_body(receive, *, max_bytes: int) -> bytes:
        body = bytearray()
        while True:
            message = await receive()
            if message.get("type") == "http.disconnect":
                raise _RequestDisconnected()
            if message.get("type") != "http.request":
                raise PreviewError("request_schema_invalid", status=422)
            body.extend(message.get("body", b""))
            if len(body) > max_bytes:
                raise PreviewError("payload_too_large", status=413)
            if not message.get("more_body", False):
                return bytes(body)

    @staticmethod
    async def _wait_for_disconnect(receive) -> bool:
        while True:
            message = await receive()
            if message.get("type") == "http.disconnect":
                return True

    async def _document_preview(
        self,
        scope,
        receive,
        send,
        *,
        authority: AuthorityContext,
    ) -> None:
        content_types = self._headers(scope, b"content-type")
        if len(content_types) != 1 or content_types[0].strip().lower() != b"application/pdf":
            await self._error(send, 422, "request_schema_invalid", authority=authority)
            return
        if self._headers(scope, b"content-encoding") or self._headers(
            scope, b"transfer-encoding"
        ):
            await self._error(send, 422, "request_schema_invalid", authority=authority)
            return
        lengths = self._headers(scope, b"content-length")
        if len(lengths) != 1:
            await self._error(send, 422, "request_schema_invalid", authority=authority)
            return
        try:
            declared = int(lengths[0])
        except ValueError:
            declared = -1
        if declared < 1:
            await self._error(send, 422, "request_schema_invalid", authority=authority)
            return
        if declared > MAX_DOCUMENT_BODY_BYTES:
            await self._error(send, 413, "payload_too_large", authority=authority)
            return
        try:
            response = await self._document_service.preview_upload(
                receive,
                body_bytes=declared,
                authority=authority,
            )
        except PreviewError as error:
            await self._error(send, error.status, error.code, authority=authority)
            return
        except Exception:
            await self._error(send, 500, "internal_error", authority=authority)
            return
        await self._json(send, 200, response, authority=authority)

    async def _read_body(self, receive, *, max_bytes: int = MAX_PREVIEW_BODY_BYTES) -> bytes | None:
        body = bytearray()
        while True:
            message = await receive()
            if message.get("type") != "http.request":
                return None
            body.extend(message.get("body", b""))
            if len(body) > max_bytes:
                return None
            if not message.get("more_body", False):
                return bytes(body)

    async def _error(
        self,
        send,
        status: int,
        code: str,
        *,
        authority: AuthorityContext | None,
    ) -> None:
        try:
            payload = error_payload(code)
        except KeyError:
            payload = error_payload("internal_error")
            status = 500
        await self._json(send, status, payload, authority=authority)

    async def _json(
        self,
        send,
        status: int,
        payload: dict,
        *,
        authority: AuthorityContext | None,
    ) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = [
            (b"cache-control", b"no-store"),
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"x-content-type-options", b"nosniff"),
            (b"x-aiguard-contract-version", str(CONTRACT_VERSION).encode("ascii")),
            (SERVER_TIME_HEADER, str(int(self._now() * 1000)).encode("ascii")),
        ]
        if authority is not None:
            headers.extend(
                [
                    (
                        SESSION_EXPIRES_HEADER,
                        str(authority.expires_at_unix * 1000).encode("ascii"),
                    ),
                    (SERVICE_CLASS_HEADER, authority.service_class.encode("ascii")),
                ]
            )
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def _empty(
        self,
        send,
        status: int,
        *,
        authority: AuthorityContext,
    ) -> None:
        headers = [
            (b"cache-control", b"no-store"),
            (b"content-length", b"0"),
            (b"x-content-type-options", b"nosniff"),
            (b"x-aiguard-contract-version", str(CONTRACT_VERSION).encode("ascii")),
            (SERVER_TIME_HEADER, str(int(self._now() * 1000)).encode("ascii")),
            (
                SESSION_EXPIRES_HEADER,
                str(authority.expires_at_unix * 1000).encode("ascii"),
            ),
            (SERVICE_CLASS_HEADER, authority.service_class.encode("ascii")),
        ]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": b""})

    @staticmethod
    def _headers(scope, name: bytes) -> list[bytes]:
        return [value for key, value in scope.get("headers", []) if key.lower() == name]

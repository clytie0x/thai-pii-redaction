"""Port-owned, stateless caller authentication for the AIFT HTTP shell."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from collections.abc import Callable, Mapping
from http.cookies import CookieError, SimpleCookie

from aift_hosted3.authority import (
    AuthorityContext,
    AuthorityRegistryError,
    InviteRegistry,
    SessionRecord,
)
from aift_hosted3.http_v2 import (
    CONTRACT_VERSION,
    SERVER_TIME_HEADER,
    SERVICE_CLASS_HEADER,
    SESSION_EXPIRES_HEADER,
    error_payload,
)
from aift_hosted3.rate_limit import AuthorityRateLimiter

COOKIE_NAME = "__Host-aift_session"
STANDARD_COOKIE_NAME = "__Host-aift_guest"
LOGIN_PATH = "/aift/auth/login"
LOGOUT_PATH = "/aift/auth/logout"
SESSION_PATH = "/aift/auth/session"
STANDARD_START_PATH = "/aift/auth/guest"
STANDARD_END_PATH = "/aift/auth/guest/end"
SHARED_PROTECTED_PATHS = frozenset(
    {
        "/api/detect",
        "/api/guard",
        "/api/analyze-report",
        "/api/guest/preview",
        "/api/guest/execute",
        "/api/protection-preview",
        "/api/protection-execute",
        "/api/document-preview",
        "/api/document-execute",
        "/api/provider-queue/join",
        "/api/provider-queue/status",
        "/api/provider-queue/claim",
        "/api/provider-queue/cancel",
    }
)
PRIORITY_PROTECTED_PATHS = frozenset({"/api/roundtrip", "/api/redact-pdf"})
PROTECTED_PATHS = SHARED_PROTECTED_PATHS | PRIORITY_PROTECTED_PATHS

_MAX_LOGIN_BODY_BYTES = 4096
_MIN_ACCESS_CODE_BYTES = 16
_MIN_SIGNING_KEY_BYTES = 32
_MIN_CORE_API_KEY_BYTES = 16
_MIN_TTL_SECONDS = 300
_MAX_TTL_SECONDS = 1800
_MAX_ACTIVE_SESSIONS = 256
_MAX_STANDARD_SESSIONS = 512
_STANDARD_TTL_SECONDS = 1800
_STANDARD_CAPABILITIES = [
    "analyze_report",
    "detect",
    "document_execute",
    "document_preview",
    "guard",
    "protection_execute",
    "protection_preview",
    "synthetic_scenarios",
]
_TOKEN_PATTERN = re.compile(
    r"^v1\.(?P<expiry>[0-9]{1,12})\."
    r"(?P<nonce>[A-Za-z0-9_-]{22})\."
    r"(?P<signature>[A-Za-z0-9_-]{43})$"
)
_ORIGIN_PATTERN = re.compile(r"^https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?$")


class AuthConfigurationError(RuntimeError):
    """The deployment auth boundary cannot start safely."""


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _secret_bytes(
    environ: Mapping[str, str],
    name: str,
    *,
    minimum: int,
) -> bytes:
    value = environ.get(name)
    if not isinstance(value, str):
        raise AuthConfigurationError(f"{name} is required")
    encoded = value.encode("utf-8")
    if (
        len(encoded) < minimum
        or len(encoded) > 256
        or value != value.strip()
        or any(ord(char) < 0x21 or ord(char) == 0x7F for char in value)
    ):
        raise AuthConfigurationError(f"{name} has an invalid format")
    return encoded


def _allowed_origins(environ: Mapping[str, str]) -> frozenset[str]:
    raw = environ.get("AIFT_ALLOWED_ORIGINS", "")
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values or any(_ORIGIN_PATTERN.fullmatch(item) is None for item in values):
        raise AuthConfigurationError("AIFT_ALLOWED_ORIGINS must contain exact HTTPS origins")
    return frozenset(values)


def _ttl_seconds(environ: Mapping[str, str]) -> int:
    raw = environ.get("AIFT_SESSION_TTL_SECONDS", "1800")
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise AuthConfigurationError("AIFT_SESSION_TTL_SECONDS is invalid") from error
    if not _MIN_TTL_SECONDS <= value <= _MAX_TTL_SECONDS:
        raise AuthConfigurationError("AIFT_SESSION_TTL_SECONDS is outside the allowed range")
    return value


class AuthGateway:
    """ASGI wrapper that keeps caller auth separate from the shared core."""

    def __init__(
        self,
        app,
        *,
        environ: Mapping[str, str] | None = None,
        now: Callable[[], float] | None = None,
        nonce_bytes: Callable[[int], bytes] | None = None,
    ):
        config = os.environ if environ is None else environ
        self._app = app
        access_code = _secret_bytes(
            config,
            "AIFT_ACCESS_CODE",
            minimum=_MIN_ACCESS_CODE_BYTES,
        )
        self._signing_key = _secret_bytes(
            config,
            "AIFT_COOKIE_SIGNING_KEY",
            minimum=_MIN_SIGNING_KEY_BYTES,
        )
        core_api_key = _secret_bytes(
            config,
            "AIGUARD_API_KEY",
            minimum=_MIN_CORE_API_KEY_BYTES,
        )
        configured_secrets = [
            access_code,
            self._signing_key,
            core_api_key,
        ]
        provider_api_key = config.get("TOKENMIND_API_KEY")
        if provider_api_key:
            try:
                configured_secrets.append(provider_api_key.encode("utf-8"))
            except UnicodeEncodeError as error:
                raise AuthConfigurationError("TOKENMIND_API_KEY has an invalid format") from error
        for index, secret in enumerate(configured_secrets):
            if any(hmac.compare_digest(secret, other) for other in configured_secrets[index + 1 :]):
                raise AuthConfigurationError("deployment secrets must be different")
        self._origins = _allowed_origins(config)
        self._ttl = _ttl_seconds(config)
        self._now = time.time if now is None else now
        self._nonce_bytes = secrets.token_bytes if nonce_bytes is None else nonce_bytes
        self._priority_session_key = hmac.new(
            self._signing_key,
            b"aift-priority-session-v2",
            hashlib.sha256,
        ).digest()
        self._standard_session_key = hmac.new(
            self._signing_key,
            b"aift-standard-session-v1",
            hashlib.sha256,
        ).digest()
        try:
            self._priority_invites = InviteRegistry.from_json(
                config.get("AIFT_PRIORITY_INVITES_JSON"),
                legacy_code=access_code,
                subject_key=self._signing_key,
            )
        except AuthorityRegistryError as error:
            raise AuthConfigurationError(str(error)) from error
        access_code = b""
        core_api_key = b""
        configured_secrets = []
        # Hosted sessions are intentionally process-local.  Keeping only a
        # SHA-256 fingerprint makes logout revoke a captured cookie without
        # persisting session authority or introducing a user database.  A
        # process restart invalidates every prior session, which is the safe
        # recovery behavior for this single-worker invite beta.
        self._active_sessions: dict[bytes, SessionRecord | int] = {}
        self._standard_sessions: dict[bytes, SessionRecord | int] = {}
        self._authority_rates = AuthorityRateLimiter(now=self._now)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path") or "/"
        if path == LOGIN_PATH:
            await self._login(scope, receive, send)
            return
        if path == LOGOUT_PATH:
            await self._logout(scope, send)
            return
        if path == SESSION_PATH:
            await self._session(scope, send)
            return
        if path == STANDARD_START_PATH:
            await self._standard_start(scope, receive, send)
            return
        if path == STANDARD_END_PATH:
            await self._standard_end(scope, receive, send)
            return

        if path in PROTECTED_PATHS:
            if not self._browser_context_allowed(scope):
                await self._error(send, 403, "cross_site_forbidden")
                return
            authority, headers, conflict = self._request_authority(scope)
            if conflict:
                await self._error(
                    send,
                    409,
                    "authority_conflict",
                    extra_headers=headers,
                )
                return
            if authority is None:
                await self._error(
                    send,
                    401,
                    "authentication_required",
                    extra_headers=headers,
                )
                return
            if path in PRIORITY_PROTECTED_PATHS and authority.scope != "priority_invite":
                await self._error(send, 403, "control_forbidden")
                return
            lane = {
                "/api/detect": "work",
                "/api/guard": "work",
                "/api/analyze-report": "work",
                "/api/guest/preview": "work",
                "/api/protection-preview": "work",
                "/api/document-preview": "document",
                "/api/provider-queue/status": "status",
                "/api/provider-queue/claim": "claim",
                "/api/provider-queue/cancel": "cancel",
                "/api/guest/execute": "execute",
                "/api/protection-execute": "execute",
                "/api/document-execute": "execute",
            }.get(path)
            if lane is not None and not self._authority_rates.consume(lane, authority):
                # Keep existing canonical operations byte-compatible with their
                # historic edge response while the additive Core paths retain
                # their v2 response metadata below.
                if path in {"/api/detect", "/api/guard", "/api/analyze-report"}:
                    await self._error(send, 429, "rate_limited")
                else:
                    await self._v2_rate_error(send, lane, authority)
                return
            scope = dict(scope)
            state = dict(scope.get("state") or {})
            state["aiguard_authority"] = authority
            scope["state"] = state

        await self._app(scope, receive, send)

    async def _login(self, scope, receive, send) -> None:
        if scope.get("method") != "POST":
            await self._error(send, 405, "method_not_allowed")
            return
        if not self._browser_context_allowed(scope):
            await self._error(send, 403, "cross_site_forbidden")
            return
        if scope.get("query_string", b""):
            await self._error(send, 400, "request_schema_invalid")
            return
        content_types = self._header_values(scope, b"content-type")
        if len(content_types) != 1 or content_types[0].split(b";", 1)[0].strip().lower() != (
            b"application/json"
        ):
            await self._error(send, 400, "request_schema_invalid")
            return
        content_lengths = self._header_values(scope, b"content-length")
        if len(content_lengths) > 1:
            await self._error(send, 400, "request_schema_invalid")
            return
        if content_lengths:
            try:
                declared_size = int(content_lengths[0])
            except ValueError:
                await self._error(send, 400, "request_schema_invalid")
                return
            if declared_size > _MAX_LOGIN_BODY_BYTES:
                await self._error(send, 413, "request_too_large")
                return

        body = await self._read_body(receive)
        if body is None:
            await self._error(send, 413, "request_too_large")
            return
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        schema_valid = (
            isinstance(payload, dict)
            and set(payload) == {"access_code"}
            and isinstance(payload.get("access_code"), str)
        )
        if not schema_valid:
            body = b""
            payload = None
            await self._error(send, 400, "request_schema_invalid")
            return
        supplied = payload["access_code"]
        try:
            supplied_bytes = supplied.encode("utf-8")
        except UnicodeEncodeError:
            body = b""
            payload = None
            supplied = None
            await self._error(send, 400, "request_schema_invalid")
            return
        subject_id = self._priority_invites.verify(supplied_bytes)
        body = b""
        payload = None
        supplied = None
        supplied_bytes = b""
        if subject_id is None:
            await self._error(send, 401, "authentication_required")
            return

        token = self._mint_authority_token("priority", subject_id=subject_id)
        if token is None:
            await self._error(send, 429, "rate_limited")
            return
        extra_headers = [self._session_cookie(token)]
        standard_token = self._cookie_token(scope, STANDARD_COOKIE_NAME)
        if standard_token is not None:
            self._standard_sessions.pop(self._token_fingerprint(standard_token), None)
            extra_headers.append(self._clear_cookie(STANDARD_COOKIE_NAME))
        await self._response(
            send,
            204,
            b"",
            extra_headers=extra_headers,
        )

    async def _logout(self, scope, send) -> None:
        if scope.get("method") != "POST":
            await self._error(send, 405, "method_not_allowed")
            return
        if not self._browser_context_allowed(scope):
            await self._error(send, 403, "cross_site_forbidden")
            return
        _authority, headers, conflict = self._request_authority(scope)
        if conflict:
            await self._error(
                send,
                409,
                "authority_conflict",
                extra_headers=headers,
            )
            return
        token = self._cookie_token(scope, COOKIE_NAME)
        if token is not None:
            self._active_sessions.pop(self._token_fingerprint(token), None)
        response_headers = list(headers)
        if self._clear_cookie() not in response_headers:
            response_headers.append(self._clear_cookie())
        await self._response(send, 204, b"", extra_headers=response_headers)

    async def _session(self, scope, send) -> None:
        if scope.get("method") != "GET":
            await self._error(send, 405, "method_not_allowed")
            return
        if not self._browser_context_allowed(scope):
            await self._error(send, 403, "cross_site_forbidden")
            return
        authority, headers, conflict = self._request_authority(scope)
        if conflict:
            await self._error(
                send,
                409,
                "authority_conflict",
                extra_headers=headers,
            )
            return
        if authority is None:
            await self._error(
                send,
                401,
                "authentication_required",
                extra_headers=headers,
            )
            return
        expiry = authority.expires_at_unix
        expires_in = max(0, expiry - int(self._now()))
        await self._json_response(
            send,
            200,
            {"authenticated": True, "expires_in": expires_in},
            extra_headers=self._authority_headers(authority),
        )

    async def _standard_start(self, scope, receive, send) -> None:
        if scope.get("method") != "POST":
            await self._error(send, 405, "method_not_allowed")
            return
        if not self._browser_context_allowed(scope):
            await self._error(send, 403, "cross_site_forbidden")
            return
        existing, headers, conflict = self._request_authority(scope)
        if conflict:
            await self._error(
                send,
                409,
                "authority_conflict",
                extra_headers=headers,
            )
            return
        if existing is not None and existing.scope == "priority_invite":
            await self._error(send, 409, "authority_conflict", extra_headers=headers)
            return
        error = await self._empty_json_error(scope, receive)
        if error is not None:
            await self._error(
                send,
                413 if error == "request_too_large" else 400,
                error,
                extra_headers=headers,
            )
            return
        authority = existing
        status = 200
        extra_headers: list[tuple[bytes, bytes]] = list(headers)
        if authority is None:
            token = self._mint_authority_token("standard", subject_id=None)
            if token is None:
                await self._error(
                    send,
                    429,
                    "standard_capacity",
                    extra_headers=headers,
                )
                return
            authority = self._verify_authority(token, "standard")
            if authority is None:  # pragma: no cover - defensive invariant
                raise RuntimeError("new Standard authority did not verify")
            status = 201
            extra_headers.append(self._standard_cookie(token))
        extra_headers.extend(self._authority_headers(authority))
        await self._json_response(
            send,
            status,
            {
                "scope": "public_guest",
                "expires_at_unix": authority.expires_at_unix,
                "service_class": "standard",
                "capabilities": _STANDARD_CAPABILITIES,
            },
            extra_headers=extra_headers,
        )

    async def _standard_end(self, scope, receive, send) -> None:
        if scope.get("method") != "POST":
            await self._error(send, 405, "method_not_allowed")
            return
        if not self._browser_context_allowed(scope):
            await self._error(send, 403, "cross_site_forbidden")
            return
        _authority, headers, conflict = self._request_authority(scope)
        if conflict:
            await self._error(
                send,
                409,
                "authority_conflict",
                extra_headers=headers,
            )
            return
        error = await self._empty_json_error(scope, receive)
        if error is not None:
            await self._error(
                send,
                413 if error == "request_too_large" else 400,
                error,
                extra_headers=headers,
            )
            return
        token = self._cookie_token(scope, STANDARD_COOKIE_NAME)
        if token is not None:
            authority = self._verify_authority(token, "standard")
            if authority is not None:
                self._authority_rates.clear_standard(authority)
            self._standard_sessions.pop(self._token_fingerprint(token), None)
        response_headers = list(headers)
        if self._clear_cookie(STANDARD_COOKIE_NAME) not in response_headers:
            response_headers.append(self._clear_cookie(STANDARD_COOKIE_NAME))
        await self._response(
            send,
            204,
            b"",
            extra_headers=response_headers,
        )

    async def _empty_json_error(self, scope, receive) -> str | None:
        if scope.get("query_string", b""):
            return "request_schema_invalid"
        content_types = self._header_values(scope, b"content-type")
        if len(content_types) != 1 or content_types[0].split(b";", 1)[0].strip().lower() != (
            b"application/json"
        ):
            return "request_schema_invalid"
        content_lengths = self._header_values(scope, b"content-length")
        if len(content_lengths) > 1:
            return "request_schema_invalid"
        if content_lengths:
            try:
                declared_size = int(content_lengths[0])
            except ValueError:
                return "request_schema_invalid"
            if declared_size > _MAX_LOGIN_BODY_BYTES:
                return "request_too_large"
        body = await self._read_body(receive)
        if body is None:
            return "request_too_large"
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "request_schema_invalid"
        return None if isinstance(payload, dict) and not payload else "request_schema_invalid"

    def _mint_authority_token(
        self,
        kind: str,
        *,
        subject_id: str | None,
    ) -> str | None:
        self._prune_sessions()
        sessions = self._active_sessions if kind == "priority" else self._standard_sessions
        capacity = _MAX_ACTIVE_SESSIONS if kind == "priority" else _MAX_STANDARD_SESSIONS
        if len(sessions) >= capacity:
            return None
        ttl = self._ttl if kind == "priority" else _STANDARD_TTL_SECONDS
        expiry = int(self._now()) + ttl
        nonce = self._nonce_bytes(16)
        if not isinstance(nonce, bytes) or len(nonce) != 16:
            raise RuntimeError("nonce source returned an invalid value")
        payload = f"v1.{expiry}.{_b64url(nonce)}"
        signature = hmac.new(
            self._authority_signing_key(kind, subject_id),
            payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        token = f"{payload}.{_b64url(signature)}"
        context = AuthorityContext(
            scope="priority_invite" if kind == "priority" else "public_guest",
            service_class="priority" if kind == "priority" else "standard",
            session_nonce=_b64url(nonce),
            subject_id=subject_id,
            expires_at_unix=expiry,
        )
        sessions[self._token_fingerprint(token)] = SessionRecord(context)
        return token

    def _authority_signing_key(self, kind: str, subject_id: str | None) -> bytes:
        base = self._priority_session_key if kind == "priority" else self._standard_session_key
        binding = (subject_id or "standard").encode("ascii")
        return hmac.new(base, binding, hashlib.sha256).digest()

    def _verify_authority(
        self,
        token: str | None,
        kind: str,
    ) -> AuthorityContext | None:
        if token is None or len(token) > 160:
            return None
        match = _TOKEN_PATTERN.fullmatch(token)
        if match is None:
            return None
        try:
            expiry = int(match.group("expiry"))
            nonce = _b64url_decode(match.group("nonce"))
            signature = _b64url_decode(match.group("signature"))
        except (ValueError, TypeError):
            return None
        if _b64url(nonce) != match.group("nonce") or _b64url(signature) != match.group("signature"):
            return None
        if len(nonce) != 16 or len(signature) != hashlib.sha256().digest_size:
            return None
        sessions = self._active_sessions if kind == "priority" else self._standard_sessions
        record = sessions.get(self._token_fingerprint(token))
        if not isinstance(record, SessionRecord):
            return None
        context = record.context
        expected_scope = "priority_invite" if kind == "priority" else "public_guest"
        if context.scope != expected_scope or context.session_nonce != match.group("nonce"):
            return None
        payload = token.rsplit(".", 1)[0]
        expected = hmac.new(
            self._authority_signing_key(kind, context.subject_id),
            payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        now = int(self._now())
        ttl = self._ttl if kind == "priority" else _STANDARD_TTL_SECONDS
        if expiry <= now or expiry > now + ttl:
            return None
        self._prune_sessions(now)
        if context.expires_at_unix != expiry or sessions.get(
            self._token_fingerprint(token)
        ) is not record:
            return None
        return context

    def _verify_token(self, token: str | None) -> int | None:
        """Compatibility helper retained for the deployed invite contract tests."""

        authority = self._verify_authority(token, "priority")
        return authority.expires_at_unix if authority is not None else None

    def _request_authority(
        self,
        scope,
    ) -> tuple[AuthorityContext | None, list[tuple[bytes, bytes]], bool]:
        if self._has_duplicate_cookie(scope, COOKIE_NAME) or self._has_duplicate_cookie(
            scope, STANDARD_COOKIE_NAME
        ):
            return None, [self._clear_cookie(), self._clear_cookie(STANDARD_COOKIE_NAME)], True
        priority_token = self._cookie_token(scope, COOKIE_NAME)
        standard_token = self._cookie_token(scope, STANDARD_COOKIE_NAME)
        priority = self._verify_authority(priority_token, "priority")
        standard = self._verify_authority(standard_token, "standard")
        headers: list[tuple[bytes, bytes]] = []
        if priority_token is not None and priority is None:
            headers.append(self._clear_cookie(COOKIE_NAME))
        if standard_token is not None and standard is None:
            headers.append(self._clear_cookie(STANDARD_COOKIE_NAME))
        if priority is not None and standard is not None:
            self._active_sessions.pop(self._token_fingerprint(priority_token or ""), None)
            self._standard_sessions.pop(self._token_fingerprint(standard_token or ""), None)
            return None, [self._clear_cookie(), self._clear_cookie(STANDARD_COOKIE_NAME)], True
        return priority or standard, headers, False

    @staticmethod
    def _token_fingerprint(token: str) -> bytes:
        # Cookie parsing tolerates arbitrary client bytes.  A malformed cookie
        # must fail authentication, never turn logout into a server error.
        return hashlib.sha256(token.encode("utf-8", "surrogatepass")).digest()

    def _prune_sessions(self, now: int | None = None) -> None:
        current = int(self._now()) if now is None else now
        for sessions in (self._active_sessions, self._standard_sessions):
            expired = [
                fingerprint
                for fingerprint, record in sessions.items()
                if self._record_expiry(record) <= current
            ]
            for fingerprint in expired:
                sessions.pop(fingerprint, None)

    @staticmethod
    def _record_expiry(record: SessionRecord | int) -> int:
        return record if isinstance(record, int) else record.context.expires_at_unix

    def _browser_context_allowed(self, scope) -> bool:
        fetch_sites = self._header_values(scope, b"sec-fetch-site")
        if len(fetch_sites) > 1 or (
            fetch_sites and fetch_sites[0].decode("latin-1").lower() == "cross-site"
        ):
            return False
        origins = self._header_values(scope, b"origin")
        if len(origins) > 1:
            return False
        if origins:
            try:
                origin = origins[0].decode("ascii")
            except UnicodeDecodeError:
                return False
            if origin not in self._origins:
                return False
        return True

    def _cookie_token(self, scope, cookie_name: str = COOKIE_NAME) -> str | None:
        rows = self._header_values(scope, b"cookie")
        if len(rows) != 1:
            return None
        try:
            parsed = SimpleCookie()
            parsed.load(rows[0].decode("latin-1"))
        except (CookieError, UnicodeDecodeError):
            return None
        morsel = parsed.get(cookie_name)
        return morsel.value if morsel is not None else None

    @staticmethod
    def _has_duplicate_cookie(scope, cookie_name: str) -> bool:
        rows = AuthGateway._header_values(scope, b"cookie")
        if not rows:
            return False
        if len(rows) != 1:
            return True
        try:
            values = [
                part.split(b"=", 1)[0].strip()
                for part in rows[0].split(b";")
                if b"=" in part
            ]
        except Exception:
            return True
        return values.count(cookie_name.encode("ascii")) > 1

    async def _v2_rate_error(
        self,
        send,
        lane: str,
        authority: AuthorityContext,
    ) -> None:
        """Emit the additive Core rate row with Core-owned timing metadata."""

        code = "queue_rate_limited" if lane in {"status", "claim", "cancel", "execute"} else "rate_limited"
        body = json.dumps(error_payload(code), separators=(",", ":")).encode("utf-8")
        await self._response(
            send,
            429,
            body,
            content_type=b"application/json; charset=utf-8",
            extra_headers=[
                (b"x-aiguard-contract-version", str(CONTRACT_VERSION).encode("ascii")),
                (SERVER_TIME_HEADER, str(int(self._now() * 1000)).encode("ascii")),
                (SESSION_EXPIRES_HEADER, str(authority.expires_at_unix * 1000).encode("ascii")),
                (SERVICE_CLASS_HEADER, authority.service_class.encode("ascii")),
            ],
        )

    @staticmethod
    def _header_values(scope, target: bytes) -> list[bytes]:
        return [value for key, value in scope.get("headers", []) if key.lower() == target]

    @staticmethod
    async def _read_body(receive) -> bytes | None:
        body = bytearray()
        while True:
            message = await receive()
            if message.get("type") != "http.request":
                return None
            body.extend(message.get("body", b""))
            if len(body) > _MAX_LOGIN_BODY_BYTES:
                return None
            if not message.get("more_body", False):
                return bytes(body)

    def _session_cookie(self, token: str) -> tuple[bytes, bytes]:
        value = (
            f"{COOKIE_NAME}={token}; Max-Age={self._ttl}; Path=/; Secure; HttpOnly; SameSite=Strict"
        )
        return b"set-cookie", value.encode("ascii")

    @staticmethod
    def _standard_cookie(token: str) -> tuple[bytes, bytes]:
        value = (
            f"{STANDARD_COOKIE_NAME}={token}; Max-Age={_STANDARD_TTL_SECONDS}; "
            "Path=/; Secure; HttpOnly; SameSite=Strict"
        )
        return b"set-cookie", value.encode("ascii")

    @staticmethod
    def _clear_cookie(cookie_name: str = COOKIE_NAME) -> tuple[bytes, bytes]:
        value = f"{cookie_name}=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Strict"
        return b"set-cookie", value.encode("ascii")

    def _authority_headers(
        self,
        authority: AuthorityContext,
    ) -> list[tuple[bytes, bytes]]:
        sampled_ms = int(self._now() * 1000)
        return [
            (SERVER_TIME_HEADER, str(sampled_ms).encode("ascii")),
            (
                SESSION_EXPIRES_HEADER,
                str(authority.expires_at_unix * 1000).encode("ascii"),
            ),
            (SERVICE_CLASS_HEADER, authority.service_class.encode("ascii")),
        ]

    async def _error(
        self,
        send,
        status: int,
        code: str,
        *,
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        await self._json_response(
            send,
            status,
            {"error": {"code": code}},
            extra_headers=extra_headers,
        )

    async def _json_response(
        self,
        send,
        status: int,
        payload: dict,
        *,
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        await self._response(
            send,
            status,
            body,
            content_type=b"application/json; charset=utf-8",
            extra_headers=extra_headers,
        )

    @staticmethod
    async def _response(
        send,
        status: int,
        body: bytes,
        *,
        content_type: bytes | None = None,
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        headers = [
            (b"cache-control", b"no-store"),
            (b"x-content-type-options", b"nosniff"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        if content_type is not None:
            headers.append((b"content-type", content_type))
        if extra_headers:
            headers.extend(extra_headers)
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": body})

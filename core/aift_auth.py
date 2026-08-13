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

COOKIE_NAME = "__Host-aift_session"
LOGIN_PATH = "/aift/auth/login"
LOGOUT_PATH = "/aift/auth/logout"
SESSION_PATH = "/aift/auth/session"
PROTECTED_PATHS = frozenset(
    {
        "/api/detect",
        "/api/guard",
        "/api/roundtrip",
        "/api/redact-pdf",
        "/api/analyze-report",
    }
)

_MAX_LOGIN_BODY_BYTES = 4096
_MIN_ACCESS_CODE_BYTES = 16
_MIN_SIGNING_KEY_BYTES = 32
_MIN_CORE_API_KEY_BYTES = 16
_MIN_TTL_SECONDS = 300
_MAX_TTL_SECONDS = 3600
_MAX_ACTIVE_SESSIONS = 256
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
        self._access_code = _secret_bytes(
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
            self._access_code,
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
        self._session_key = hmac.new(
            self._signing_key,
            b"aift-session-v1\x00" + self._access_code,
            hashlib.sha256,
        ).digest()
        # Hosted sessions are intentionally process-local.  Keeping only a
        # SHA-256 fingerprint makes logout revoke a captured cookie without
        # persisting session authority or introducing a user database.  A
        # process restart invalidates every prior session, which is the safe
        # recovery behavior for this single-worker invite beta.
        self._active_sessions: dict[bytes, int] = {}

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

        if path in PROTECTED_PATHS:
            if not self._browser_context_allowed(scope):
                await self._error(send, 403, "cross_site_forbidden")
                return
            token = self._cookie_token(scope)
            expiry = self._verify_token(token)
            if expiry is None:
                headers = [self._clear_cookie()] if token is not None else []
                await self._error(
                    send,
                    401,
                    "authentication_required",
                    extra_headers=headers,
                )
                return

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
        valid = hmac.compare_digest(supplied_bytes, self._access_code)
        body = b""
        payload = None
        supplied = None
        supplied_bytes = b""
        if not valid:
            await self._error(send, 401, "authentication_required")
            return

        token = self._mint_token()
        if token is None:
            await self._error(send, 429, "rate_limited")
            return
        await self._response(
            send,
            204,
            b"",
            extra_headers=[self._session_cookie(token)],
        )

    async def _logout(self, scope, send) -> None:
        if scope.get("method") != "POST":
            await self._error(send, 405, "method_not_allowed")
            return
        if not self._browser_context_allowed(scope):
            await self._error(send, 403, "cross_site_forbidden")
            return
        token = self._cookie_token(scope)
        if token is not None:
            self._active_sessions.pop(self._token_fingerprint(token), None)
        await self._response(send, 204, b"", extra_headers=[self._clear_cookie()])

    async def _session(self, scope, send) -> None:
        if scope.get("method") != "GET":
            await self._error(send, 405, "method_not_allowed")
            return
        if not self._browser_context_allowed(scope):
            await self._error(send, 403, "cross_site_forbidden")
            return
        token = self._cookie_token(scope)
        expiry = self._verify_token(token)
        if expiry is None:
            headers = [self._clear_cookie()] if token is not None else []
            await self._error(
                send,
                401,
                "authentication_required",
                extra_headers=headers,
            )
            return
        expires_in = max(0, expiry - int(self._now()))
        await self._json_response(
            send,
            200,
            {"authenticated": True, "expires_in": expires_in},
        )

    def _mint_token(self) -> str | None:
        self._prune_sessions()
        if len(self._active_sessions) >= _MAX_ACTIVE_SESSIONS:
            return None
        expiry = int(self._now()) + self._ttl
        nonce = self._nonce_bytes(16)
        if not isinstance(nonce, bytes) or len(nonce) != 16:
            raise RuntimeError("nonce source returned an invalid value")
        payload = f"v1.{expiry}.{_b64url(nonce)}"
        signature = hmac.new(
            self._session_key,
            payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        token = f"{payload}.{_b64url(signature)}"
        self._active_sessions[self._token_fingerprint(token)] = expiry
        return token

    def _verify_token(self, token: str | None) -> int | None:
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
        payload = token.rsplit(".", 1)[0]
        expected = hmac.new(
            self._session_key,
            payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        now = int(self._now())
        if expiry <= now or expiry > now + self._ttl:
            return None
        self._prune_sessions(now)
        if self._active_sessions.get(self._token_fingerprint(token)) != expiry:
            return None
        return expiry

    @staticmethod
    def _token_fingerprint(token: str) -> bytes:
        # Cookie parsing tolerates arbitrary client bytes.  A malformed cookie
        # must fail authentication, never turn logout into a server error.
        return hashlib.sha256(token.encode("utf-8", "surrogatepass")).digest()

    def _prune_sessions(self, now: int | None = None) -> None:
        current = int(self._now()) if now is None else now
        expired = [
            fingerprint
            for fingerprint, expiry in self._active_sessions.items()
            if expiry <= current
        ]
        for fingerprint in expired:
            self._active_sessions.pop(fingerprint, None)

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

    def _cookie_token(self, scope) -> str | None:
        rows = self._header_values(scope, b"cookie")
        if len(rows) != 1:
            return None
        try:
            parsed = SimpleCookie()
            parsed.load(rows[0].decode("latin-1"))
        except (CookieError, UnicodeDecodeError):
            return None
        morsel = parsed.get(COOKIE_NAME)
        return morsel.value if morsel is not None else None

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
    def _clear_cookie() -> tuple[bytes, bytes]:
        value = f"{COOKIE_NAME}=; Max-Age=0; Path=/; Secure; HttpOnly; SameSite=Strict"
        return b"set-cookie", value.encode("ascii")

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

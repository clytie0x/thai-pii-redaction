"""Configured OIDC transport; browser state remains owned by PostgreSQL."""

from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

import httpx
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.enterprise.identity import verify_identity
from app.enterprise.settings import _url
from pii_redactor.governance.errors import GovernanceError

_MAX_BYTES = 65536


class _LimitedBody(httpx.AsyncByteStream):
    def __init__(self, stream):
        self.stream = stream

    async def __aiter__(self):
        size = 0
        async for chunk in self.stream:
            size += len(chunk)
            if size > _MAX_BYTES:
                raise ValueError("identity_response_invalid")
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


class _BoundedTransport(httpx.AsyncBaseTransport):
    def __init__(self, transport=None):
        self.transport = transport or httpx.AsyncHTTPTransport(retries=0, trust_env=False)

    async def handle_async_request(self, request):
        response = await self.transport.handle_async_request(request)
        try:
            if response.headers.get("content-encoding", "identity").lower() != "identity":
                raise ValueError("identity_response_invalid")
            length = response.headers.get("content-length")
            if length is not None and not 0 <= int(length) <= _MAX_BYTES:
                raise ValueError("identity_response_invalid")
        except (ValueError, TypeError):
            await response.aclose()
            raise
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            request=request,
            stream=_LimitedBody(response.stream),
            extensions=response.extensions,
        )

    async def aclose(self):
        await self.transport.aclose()


def _origin(url):
    parsed = urlsplit(url)
    return parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


class OIDCClient:
    def __init__(self, settings, *, transport=None):
        self.settings = settings
        self.transport = transport
        self._metadata = None

    def _options(self):
        return {
            "timeout": httpx.Timeout(10),
            "trust_env": False,
            "follow_redirects": False,
            "headers": {"Accept": "application/json", "Accept-Encoding": "identity"},
            "transport": _BoundedTransport(self.transport),
        }

    async def _json(self, url):
        async with httpx.AsyncClient(**self._options()) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("identity_response_invalid")
            return data

    async def metadata(self, *, refresh=False):
        if self._metadata is not None and not refresh:
            return self._metadata
        data = await self._json(
            self.settings.issuer.rstrip("/") + "/.well-known/openid-configuration"
        )
        if data.get("issuer") != self.settings.issuer:
            raise ValueError("identity_response_invalid")
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            _url(data.get(key))
            if _origin(data[key]) != _origin(self.settings.issuer):
                raise ValueError("identity_response_invalid")
        self._metadata = data
        return data

    async def check_ready(self, *, refresh=False):
        try:
            async with asyncio.timeout(20):
                await self.metadata(refresh=refresh)
                return
        except (httpx.HTTPError, AuthlibBaseError, ValueError, TypeError, TimeoutError):
            pass
        raise GovernanceError("identity_unavailable") from None

    def _oauth(self):
        return AsyncOAuth2Client(
            client_id=self.settings.client_id,
            client_secret=self.settings.client_secret,
            redirect_uri=self.settings.redirect_uri,
            scope="openid",
            code_challenge_method="S256",
            **self._options(),
        )

    async def authorization_url(self, attempt):
        try:
            async with asyncio.timeout(20):
                metadata = await self.metadata()
                async with self._oauth() as client:
                    url, _state = client.create_authorization_url(
                        metadata["authorization_endpoint"],
                        state=attempt.state,
                        nonce=attempt.nonce,
                        code_verifier=attempt.code_verifier,
                    )
                    return url
        except (httpx.HTTPError, AuthlibBaseError, ValueError, TypeError, TimeoutError):
            pass
        raise GovernanceError("identity_unavailable") from None

    async def complete_login(self, code, attempt):
        error_code = "identity_unavailable"
        try:
            if not isinstance(code, str) or not 1 <= len(code) <= 4096:
                raise GovernanceError("authentication_failed")
            async with asyncio.timeout(20):
                metadata = await self.metadata()
                async with self._oauth() as client:
                    token = await client.fetch_token(
                        metadata["token_endpoint"],
                        grant_type="authorization_code",
                        code=code,
                        code_verifier=attempt.code_verifier,
                    )
                if not isinstance(token.get("id_token"), str) or not isinstance(
                    token.get("access_token"), str
                ):
                    raise GovernanceError("authentication_failed")
                keys = await self._json(metadata["jwks_uri"])
                return verify_identity(
                    token["id_token"],
                    jwks=keys,
                    issuer=self.settings.issuer,
                    client_id=self.settings.client_id,
                    nonce=attempt.nonce,
                    access_token=token["access_token"],
                )
        except GovernanceError:
            error_code = "authentication_failed"
        except AuthlibBaseError:
            error_code = "authentication_failed"
        except (httpx.HTTPError, ValueError, TypeError, TimeoutError):
            pass
        raise GovernanceError(error_code) from None

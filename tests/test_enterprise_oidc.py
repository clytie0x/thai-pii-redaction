"""Bounded OIDC transport with explicit issuer and PKCE binding."""

import asyncio
import secrets
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

pytest.importorskip("authlib", reason="optional enterprise identity dependency")
pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

import httpx
from joserfc import jwt
from joserfc.jwk import RSAKey

from app.enterprise.auth import OIDCClient
from app.enterprise.sessions import LoginAttempt
from app.enterprise.settings import Settings
from pii_redactor.governance.errors import GovernanceError

ISSUER = "https://staff.example.test/realms/staff"


@pytest.fixture
def setup():
    settings = Settings(
        organization_id=uuid4(),
        database_dsn="dbname=synthetic user=synthetic",
        issuer=ISSUER,
        client_id="aiguard-staff",
        client_secret="synthetic-client-secret",
        public_origin="https://guard.example.test",
    )
    attempt = LoginAttempt(*(secrets.token_urlsafe(32) for _ in range(3)))
    key = RSAKey.generate_key(2048, parameters={"kid": "synthetic"})
    return settings, attempt, key


def provider(
    settings, attempt, key, *, metadata_changes=None, claim_changes=None, token_status=200
):
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": settings.issuer,
                    "authorization_endpoint": settings.issuer + "/authorize",
                    "token_endpoint": settings.issuer + "/token",
                    "jwks_uri": settings.issuer + "/certs",
                    **(metadata_changes or {}),
                },
            )
        if request.url.path.endswith("/certs"):
            return httpx.Response(200, json={"keys": [key.as_dict(private=False)]})
        assert request.url.path.endswith("/token") and request.method == "POST"
        fields = parse_qs(request.content.decode())
        assert fields["code_verifier"] == [attempt.code_verifier]
        assert fields["redirect_uri"] == [settings.redirect_uri]
        assert request.headers["authorization"].startswith("Basic ")
        if token_status != 200:
            return httpx.Response(token_status, json={"error": "sensitive-provider-error"})
        now = int(time.time())
        claims = {
            "iss": settings.issuer,
            "sub": "staff-a",
            "aud": settings.client_id,
            "azp": settings.client_id,
            "iat": now,
            "exp": now + 120,
            "nonce": attempt.nonce,
            **(claim_changes or {}),
        }
        return httpx.Response(
            200,
            json={
                "access_token": "synthetic-access-token",
                "token_type": "Bearer",
                "id_token": jwt.encode({"alg": "RS256", "kid": key.kid}, claims, key),
            },
        )

    return httpx.MockTransport(handle), calls


def test_authorization_uses_explicit_redirect_state_nonce_and_pkce(setup):
    settings, attempt, key = setup
    transport, calls = provider(settings, attempt, key)
    client = OIDCClient(settings, transport=transport)
    url = asyncio.run(client.authorization_url(attempt))
    query = parse_qs(urlsplit(url).query)
    assert query["state"] == [attempt.state] and query["nonce"] == [attempt.nonce]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == [settings.redirect_uri]
    assert attempt.code_verifier not in url and settings.client_secret not in url
    assert len(calls) == 1


def test_complete_login_uses_signed_issuer_identity(setup):
    settings, attempt, key = setup
    transport, calls = provider(settings, attempt, key)
    principal = asyncio.run(
        OIDCClient(settings, transport=transport).complete_login("code", attempt)
    )
    assert principal.model_dump() == {"issuer": ISSUER, "subject": "staff-a"}
    assert len(calls) == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"issuer": "https://foreign.example.test"},
        {"jwks_uri": "https://foreign.example.test/keys"},
        {"token_endpoint": "http://127.0.0.1/private"},
        {"authorization_endpoint": "https://user:secret@staff.example.test/auth"},
    ],
    ids=["issuer", "foreign-jwks", "private-token-url", "userinfo"],
)
def test_discovery_cannot_redirect_backend_authority(setup, changes):
    settings, attempt, key = setup
    transport, calls = provider(settings, attempt, key, metadata_changes=changes)
    with pytest.raises(GovernanceError, match="^identity_unavailable$") as caught:
        asyncio.run(OIDCClient(settings, transport=transport).authorization_url(attempt))
    assert caught.value.__context__ is None and len(calls) == 1


def test_wrong_nonce_never_returns_a_principal(setup):
    settings, attempt, key = setup
    transport, _ = provider(settings, attempt, key, claim_changes={"nonce": "wrong"})
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        asyncio.run(OIDCClient(settings, transport=transport).complete_login("code", attempt))


def test_provider_error_has_no_response_body_in_error(setup):
    settings, attempt, key = setup
    transport, _ = provider(settings, attempt, key, token_status=503)
    with pytest.raises(GovernanceError) as caught:
        asyncio.run(OIDCClient(settings, transport=transport).complete_login("code", attempt))
    assert str(caught.value) in {"authentication_failed", "identity_unavailable"}
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "headers,content",
    [
        ({}, b"x" * 65537),
        ({"content-encoding": "gzip"}, b"encoded-response"),
    ],
    ids=["oversize", "unexpected-compression"],
)
def test_upstream_payload_is_bounded_before_json_parsing(setup, headers, content):
    settings, attempt, _ = setup
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=content, headers=headers)
    )
    with pytest.raises(GovernanceError, match="^identity_unavailable$"):
        asyncio.run(OIDCClient(settings, transport=transport).authorization_url(attempt))

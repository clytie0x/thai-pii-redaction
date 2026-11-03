"""Synthetic BFF auth scope with real PostgreSQL and a controlled signed OIDC provider.

Production operations and restricted-role readiness use separate mandatory suites.
"""

import base64
import hashlib
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

pytest.importorskip("authlib", reason="optional enterprise identity dependency")
pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

import httpx
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import RSAKey

from app.enterprise.server import create_app
from app.enterprise.settings import Settings
from tests import governance_helpers
from tests.test_governance_registry import activity

context = governance_helpers.context
database = governance_helpers.database


@pytest.fixture
def web(context, monkeypatch):
    # These contracts isolate BFF auth. Real operations gates have dedicated suites.
    async def ready(_settings, store, *_args):
        from pii_redactor.governance.errors import GovernanceError

        try:
            store.check_ready()
        except GovernanceError as error:
            return {
                "status": "blocked",
                "checks": {"schema_audit": "blocked"},
                "error": {"code": error.code},
            }
        return {"status": "ready", "checks": {"synthetic_auth_scope": "ready"}}

    monkeypatch.setattr("app.enterprise.server._production_readiness", ready)
    with context.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET state='reconciled'")
    settings = Settings(
        organization_id=context.store.organization_id,
        database_dsn=context.store._dsn,
        issuer=context.a.issuer,
        client_id="aiguard-staff",
        client_secret="synthetic-secret",
        public_origin="https://guard.example.test",
    )
    key = RSAKey.generate_key(2048, parameters={"kid": "synthetic"})
    flow = {"subject": context.a.subject, "nonce": None, "challenge": None, "token_calls": 0}

    def provider(request):
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": settings.issuer,
                    "authorization_endpoint": settings.issuer + "/authorize",
                    "token_endpoint": settings.issuer + "/token",
                    "jwks_uri": settings.issuer + "/certs",
                },
            )
        if request.url.path.endswith("/certs"):
            return httpx.Response(200, json={"keys": [key.as_dict(private=False)]})
        assert request.url.path.endswith("/token")
        flow["token_calls"] += 1
        verifier = parse_qs(request.content.decode())["code_verifier"][0]
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        assert challenge == flow["challenge"]
        now = int(time.time())
        return httpx.Response(
            200,
            json={
                "access_token": "synthetic-access-token",
                "token_type": "Bearer",
                "id_token": jwt.encode(
                    {"alg": "RS256", "kid": key.kid},
                    {
                        "iss": settings.issuer,
                        "sub": flow["subject"],
                        "aud": settings.client_id,
                        "azp": settings.client_id,
                        "iat": now,
                        "exp": now + 120,
                        "nonce": flow["nonce"],
                    },
                    key,
                ),
            },
        )

    app = create_app(settings, store=context.store, oidc_transport=httpx.MockTransport(provider))
    # Keep the operator-backed fixture in the schema/audit scope mocked above.
    # Production settings still exercise secure cookies, origin and BFF auth.
    monkeypatch.setattr(context.store, "production_operations_required", False)
    with TestClient(
        app, base_url=settings.public_origin, follow_redirects=False, raise_server_exceptions=False
    ) as client:
        yield client, settings, flow


def login(web):
    client, settings, flow = web
    response = client.get("/auth/login")
    assert response.status_code == 303
    values = parse_qs(urlsplit(response.headers["location"]).query)
    flow["nonce"] = values["nonce"][0]
    flow["challenge"] = values["code_challenge"][0]
    callback = "/auth/callback?code=synthetic-code&state=" + values["state"][0]
    response = client.get(callback)
    assert response.status_code == 303
    return callback


def mutation_headers(web):
    client, settings, _flow = web
    return {
        "Origin": settings.public_origin,
        "X-CSRF-Token": client.cookies.get(settings.cookie_prefix + "csrf"),
    }


def test_unauthenticated_and_forged_identity_headers_are_denied(web):
    client, _settings, _flow = web
    response = client.get(
        "/api/enterprise/v1/me", headers={"X-User": "staff-a", "X-Role": "system_administrator"}
    )
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "correlation_id"}


def test_code_flow_publishes_only_browser_session_and_scoped_me(web):
    callback = login(web)
    client, settings, _flow = web
    response = client.get("/api/enterprise/v1/me")
    assert response.status_code == 200
    assert response.json()["departments"] == ["operations"]
    assert "session_id" not in response.text and "access_token" not in response.text
    cookies = [str(c) for c in client.cookies.jar]
    assert any(settings.cookie_prefix + "session" in c for c in cookies)
    assert client.get(callback).status_code == 401
    assert web[2]["token_calls"] == 1


def test_callback_duplicate_parameters_fail_before_exchange(web):
    client, _settings, flow = web
    response = client.get("/auth/callback?state=x&state=y&code=z")
    assert response.status_code == 401 and flow["token_calls"] == 0


def test_callback_without_browser_binding_never_exchanges_code(web):
    client, _settings, flow = web
    response = client.get("/auth/callback?state=" + "a" * 43 + "&code=synthetic")
    assert response.status_code == 401 and flow["token_calls"] == 0


def test_no_startup_ddl_and_readiness_checks_current_schema(web, context, monkeypatch):
    client, _settings, _flow = web
    monkeypatch.setattr(
        context.store, "migrate", lambda: pytest.fail("Web startup must not run DDL")
    )
    assert client.get("/health/ready").status_code == 200
    with context.store.transaction() as tx:
        tx.execute("UPDATE governance_schema SET digest=repeat('0',64) WHERE version=3")
    assert client.get("/health/ready").status_code == 503


def test_csrf_and_origin_are_required_for_writes(web):
    login(web)
    client, _settings, _flow = web
    body = {"command_key": str(uuid4()), "data": activity().model_dump(mode="json")}
    assert client.post("/api/enterprise/v1/activities", json=body).status_code == 403
    headers = mutation_headers(web)
    headers["Origin"] = "https://foreign.example.test"
    assert (
        client.post("/api/enterprise/v1/activities", json=body, headers=headers).status_code == 403
    )


def test_create_read_and_idempotency_use_shared_registry(web):
    login(web)
    client, _settings, _flow = web
    body = {"command_key": str(uuid4()), "data": activity().model_dump(mode="json")}
    headers = mutation_headers(web)
    response = client.post("/api/enterprise/v1/activities", json=body, headers=headers)
    assert response.status_code == 200
    record = response.json()
    replay = client.post("/api/enterprise/v1/activities", json=body, headers=headers)
    assert replay.json() == record
    assert client.get("/api/enterprise/v1/activities").json() == [record]
    assert client.get("/api/enterprise/v1/activities/" + record["id"]).json() == record


def test_rejected_values_do_not_appear_in_validation_errors(web):
    login(web)
    client, _settings, _flow = web
    response = client.post(
        "/api/enterprise/v1/activities",
        json={
            "command_key": str(uuid4()),
            "data": {},
            "forged_role": "private-rejected-marker",
        },
        headers=mutation_headers(web),
    )
    assert response.status_code == 422
    assert "private-rejected-marker" not in response.text


def test_membership_revocation_invalidates_existing_browser(web, context):
    login(web)
    client, _settings, _flow = web
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET enabled=false,revision=revision+1 WHERE member_id=%s",
            (context.ids[0],),
        )
    assert client.get("/api/enterprise/v1/me").status_code == 401


def test_logout_revokes_server_authority(web):
    login(web)
    client, _settings, _flow = web
    assert client.post("/auth/logout", headers=mutation_headers(web)).status_code == 204
    assert client.get("/api/enterprise/v1/me").status_code == 401


def test_browser_errors_and_auth_responses_are_not_cacheable(web):
    client, _settings, _flow = web
    response = client.get("/api/enterprise/v1/me")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_oversized_body_cannot_reach_domain(web):
    login(web)
    client, _settings, _flow = web
    response = client.post(
        "/api/enterprise/v1/activities",
        content=b"x" * 65537,
        headers={**mutation_headers(web), "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert client.get("/api/enterprise/v1/activities").json() == []


def test_unexpected_errors_are_value_free_and_not_cacheable(web, monkeypatch, caplog):
    from pii_redactor.governance.registry import Registry

    login(web)
    client, _settings, _flow = web

    def fail(*_args, **_kwargs):
        raise RuntimeError("private-internal-error-marker")

    monkeypatch.setattr(Registry, "list_activities", fail)
    response = client.get("/api/enterprise/v1/activities")
    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert "private-internal-error-marker" not in response.text + caplog.text


def test_self_view_works_for_a_scoped_identity_steward(web, context):
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles='[\"identity_steward\"]'::jsonb WHERE member_id=%s",
            (context.ids[0],),
        )
    login(web)
    response = web[0].get("/api/enterprise/v1/me")
    assert response.status_code == 200
    assert response.json()["roles"] == ["identity_steward"]


def test_oidc_response_issuer_and_session_marker_are_accepted_only_when_bound(web):
    from urllib.parse import urlencode

    client, settings, flow = web
    response = client.get("/auth/login")
    values = parse_qs(urlsplit(response.headers["location"]).query)
    flow["nonce"], flow["challenge"] = values["nonce"][0], values["code_challenge"][0]
    params = {
        "state": values["state"][0],
        "code": "synthetic-code",
        "iss": "https://foreign.example.test",
        "session_state": "synthetic-session",
    }
    assert client.get("/auth/callback?" + urlencode(params)).status_code == 401
    assert flow["token_calls"] == 0
    params["iss"] = settings.issuer
    assert client.get("/auth/callback?" + urlencode(params)).status_code == 303


def test_uvicorn_callback_log_never_contains_code_or_state(web):
    import logging

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "synthetic",
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", "/auth/callback?code=private-code&state=private-state", "1.1", 303),
        None,
    )
    assert logging.getLogger("uvicorn.access").filter(record)
    assert "private-code" not in record.getMessage() and "private-state" not in record.getMessage()
    assert "/auth/callback" in record.getMessage()


def test_accepted_ipv6_development_origin_passes_host_boundary(context):
    settings = Settings(
        organization_id=context.store.organization_id,
        database_dsn=context.store._dsn,
        issuer="http://[::1]:8080/realms/staff",
        client_id="synthetic",
        client_secret="synthetic",
        public_origin="http://[::1]:8765",
        development=True,
    )
    app = create_app(settings, store=context.store)
    # The sync TestClient has its own IPv6 parsing limitation; use direct ASGI.
    import asyncio

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=settings.public_origin
        ) as client:
            assert (await client.get("/health/live")).status_code == 200
            assert (
                await client.get("/health/live", headers={"Host": "[::1]:9999"})
            ).status_code == 400

    asyncio.run(check())


def test_self_view_has_non_authorizing_deadlines_for_browser_cleanup(web):
    login(web)
    value = web[0].get("/api/enterprise/v1/me").json()
    assert len(value["id"]) == 36
    assert value["session"]["idle_seconds"] == 1800
    assert 0 < value["session"]["absolute_remaining_seconds"] <= 28800
    assert "cookie" not in value["session"] and "session_id" not in value["session"]


def test_form_options_come_from_shared_core_catalog(web):
    login(web)
    response = web[0].get("/api/enterprise/v1/catalog")
    assert response.status_code == 200
    data = response.json()
    assert {c["code"] for c in data["categories"]} >= {"CONTACT", "HEALTH", "OTHER_PERSONAL"}
    assert "contract" in data["bases"] and "explicit_consent" in data["sensitive_conditions"]
    assert "system_administrator" in data["roles"]


def test_browser_callback_error_returns_safe_login_recovery(web):
    response = web[0].get(
        "/auth/callback?code=private-code&state=invalid", headers={"Accept": "text/html"}
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/?login=failed"
    assert "private-code" not in response.text + response.headers["location"]


def test_membership_review_can_load_exact_target_only_inside_scope(web, context):
    login(web)
    response = web[0].get("/api/enterprise/v1/members/" + str(context.ids[1]))
    assert response.status_code == 200 and response.json()["subject"] == context.b.subject
    assert web[0].get("/api/enterprise/v1/members/" + str(context.ids[2])).status_code == 404


def test_corrupted_local_audit_chain_stops_readiness(web, context):
    from psycopg.types.json import Jsonb

    with context.store.transaction() as tx:
        tx.execute(
            """INSERT INTO governance_audit(sequence,event_id,organization_id,event_code,
                   occurred_at,details,previous_hash,event_hash)
                   VALUES (2,%s,%s,'synthetic_corruption',clock_timestamp(),%s,%s,%s)""",
            (uuid4(), context.store.organization_id, Jsonb({}), "0" * 64, "0" * 64),
        )
    response = web[0].get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "audit_integrity_failure"


def test_production_cookie_attributes_do_not_expose_session_to_javascript(web):
    login(web)
    client, settings, _flow = web
    cookies = {c.name: c for c in client.cookies.jar}
    session = cookies[settings.cookie_prefix + "session"]
    csrf = cookies[settings.cookie_prefix + "csrf"]
    assert session.secure and "HttpOnly" in session._rest and session._rest["SameSite"] == "strict"
    assert csrf.secure and "HttpOnly" not in csrf._rest and csrf._rest["SameSite"] == "strict"

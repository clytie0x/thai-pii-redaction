"""Separate subject identity and caller boundary, using synthetic claims only."""

import time
from uuid import uuid4

import pytest

pytest.importorskip("authlib", reason="optional enterprise identity dependency")
pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from joserfc import jwt
from joserfc.jwk import RSAKey

from app.enterprise.subject_auth import (
    SubjectIdentity,
    SubjectOIDCSettings,
    verify_subject_identity,
)
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Principal
from pii_redactor.governance.subjects import SubjectActor, require_subject_actor


def subject_settings(**changes):
    return SubjectOIDCSettings(
        **{
            "issuer": "https://idp.example.test/realms/staff",
            "client_id": "aiguard-subject",
            "client_secret": "synthetic-subject-secret",
            "staff_client_id": "aiguard-staff",
            "public_origin": "https://guard.example.test",
            **changes,
        }
    )


def test_subject_configuration_allows_same_approved_issuer_but_never_staff_client():
    settings = subject_settings()
    assert settings.redirect_uri.endswith("/subject/auth/callback")
    assert settings.cookie_prefix == "__Host-aiguard_subject_"
    assert "synthetic-subject-secret" not in repr(settings)
    with pytest.raises(GovernanceError, match="^configuration_invalid$"):
        subject_settings(client_id="aiguard-staff")


@pytest.mark.parametrize("audience", ["aiguard-staff", ["aiguard-subject", "aiguard-staff"]])
def test_staff_token_cannot_become_subject_token_even_with_shared_issuer(audience):
    settings = subject_settings()
    key = RSAKey.generate_key(2048, parameters={"kid": "synthetic"})
    now = int(time.time())
    token = jwt.encode(
        {"alg": "RS256", "kid": key.kid},
        {
            "iss": settings.issuer,
            "sub": "synthetic-customer",
            "aud": audience,
            "azp": "aiguard-staff",
            "iat": now,
            "exp": now + 120,
            "nonce": "synthetic-nonce",
        },
        key,
    )
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify_subject_identity(
            token,
            jwks={"keys": [key.as_dict(private=False)]},
            settings=settings,
            nonce="synthetic-nonce",
        )


def test_verified_subject_identity_is_not_a_staff_principal():
    settings = subject_settings()
    key = RSAKey.generate_key(2048, parameters={"kid": "synthetic"})
    now = int(time.time())
    token = jwt.encode(
        {"alg": "RS256", "kid": key.kid},
        {
            "iss": settings.issuer,
            "sub": "synthetic-customer",
            "aud": settings.client_id,
            "azp": settings.client_id,
            "iat": now,
            "exp": now + 120,
            "nonce": "synthetic-nonce",
        },
        key,
    )
    identity = verify_subject_identity(
        token,
        jwks={"keys": [key.as_dict(private=False)]},
        settings=settings,
        nonce="synthetic-nonce",
    )
    assert isinstance(identity, SubjectIdentity)
    assert not isinstance(identity, Principal)
    assert "synthetic-customer" not in repr(identity)


def test_staff_principal_and_browser_declared_identity_are_rejected_before_database_access():
    for actor in [
        Principal(issuer=subject_settings().issuer, subject="staff-a"),
        {"subject_id": str(uuid4())},
        None,
    ]:
        with pytest.raises(GovernanceError, match="^authentication_required$"):
            require_subject_actor(None, uuid4(), actor)
    actor = SubjectActor(subject_id=uuid4(), link_revision=1, session_id=uuid4())
    assert not isinstance(actor, Principal)


def test_malformed_subject_actor_is_denied_before_database_access():
    actor = SubjectActor(subject_id=uuid4(), link_revision=True, session_id=uuid4())
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        require_subject_actor(None, uuid4(), actor)


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://foreign.example.test"},
        {"iat": 1},
        {"exp": 1},
        {"nonce": "other-synthetic-nonce"},
    ],
)
def test_subject_tokens_reject_foreign_issuer_expiry_and_stale_nonce(changes):
    settings = subject_settings()
    key = RSAKey.generate_key(2048, parameters={"kid": "synthetic"})
    now = int(time.time())
    payload = {
        "iss": settings.issuer,
        "sub": "synthetic-customer",
        "aud": settings.client_id,
        "azp": settings.client_id,
        "iat": now,
        "exp": now + 120,
        "nonce": "synthetic-nonce",
        **changes,
    }
    token = jwt.encode({"alg": "RS256", "kid": key.kid}, payload, key)
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        verify_subject_identity(
            token,
            jwks={"keys": [key.as_dict(private=False)]},
            settings=settings,
            nonce="synthetic-nonce",
        )


def test_subject_router_rejects_staff_cookie_forged_headers_and_foreign_origin_without_storage():
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from app.enterprise.subject_routes import create_subject_router

    app = FastAPI()

    @app.exception_handler(GovernanceError)
    async def rejected(_request, error):
        return JSONResponse(
            {"error": {"code": error.code}},
            status_code=401 if error.code == "authentication_required" else 403,
        )

    def staff_identity(_request, **_kwargs):
        raise GovernanceError("authentication_required")

    app.include_router(
        create_subject_router(subject_settings(), object(), staff_identity=staff_identity)
    )
    with TestClient(app, base_url=subject_settings().public_origin) as client:
        client.cookies.set("__Host-aiguard_session", "a" * 43)
        response = client.get(
            "/api/subject/v1/me", headers={"X-Subject-ID": str(uuid4()), "X-Role": "subject"}
        )
        assert response.status_code == 401
        response = client.post(
            "/api/subject/v1/notices/" + str(uuid4()) + "/presentation",
            headers={"Origin": "https://foreign.example.test"},
        )
        assert response.status_code == 403
        assert "foreign.example.test" not in response.text


from tests import governance_helpers as fixtures
from tests import test_governance_consent as consent_fixtures

database = fixtures.database
context = fixtures.context
subject_context = consent_fixtures.subject_context
consent_context = consent_fixtures.consent_context


@pytest.fixture
def subject_web(consent_context):
    import base64
    import hashlib
    from urllib.parse import parse_qs

    import httpx
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from app.enterprise.server import _RequestBoundary
    from app.enterprise.subject_routes import create_subject_router

    c = consent_context
    settings = subject_settings()
    key = RSAKey.generate_key(2048, parameters={"kid": "synthetic-subject"})
    flow = {
        "subject": "synthetic-customer",
        "audience": settings.client_id,
        "nonce": None,
        "challenge": None,
    }

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
        body = parse_qs(request.content.decode())
        client_auth = request.headers.get("authorization", "").removeprefix("Basic ")
        assert base64.b64decode(client_auth).decode().split(":", 1)[0] == settings.client_id
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(body["code_verifier"][0].encode()).digest())
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
                        "aud": flow["audience"],
                        "azp": flow["audience"],
                        "iat": now,
                        "exp": now + 120,
                        "nonce": flow["nonce"],
                    },
                    key,
                ),
            },
        )

    app = FastAPI()
    app.add_middleware(_RequestBoundary, origin=settings.public_origin)

    @app.exception_handler(GovernanceError)
    async def rejected(_request, error):
        status = 401 if error.code in {"authentication_required", "authentication_failed"} else 409
        return JSONResponse({"error": {"code": error.code}}, status_code=status)

    def staff_identity(_request, **_kwargs):
        raise GovernanceError("authentication_required")

    app.include_router(
        create_subject_router(
            settings,
            c.store,
            staff_identity=staff_identity,
            oidc_transport=httpx.MockTransport(provider),
        )
    )
    with TestClient(
        app, base_url=settings.public_origin, follow_redirects=False, raise_server_exceptions=False
    ) as client:
        yield client, settings, flow, c


def subject_login(web):
    from urllib.parse import parse_qs, urlsplit

    client, _settings, flow, _c = web
    started = client.get("/subject/auth/login")
    assert started.status_code == 303
    params = parse_qs(urlsplit(started.headers["location"]).query)
    flow["nonce"], flow["challenge"] = params["nonce"][0], params["code_challenge"][0]
    callback = "/subject/auth/callback?code=synthetic-code&state=" + params["state"][0]
    return callback, client.get(callback)


def test_subject_database_login_binds_reviewed_source_and_state_is_one_time(subject_web):
    client, settings, _flow, c = subject_web
    callback, response = subject_login(subject_web)
    assert response.status_code == 303
    assert client.cookies.get(settings.cookie_prefix + "session")
    assert client.get("/api/subject/v1/me").json()["subject_id"] == c.subject["subject_id"]
    assert client.get(callback).status_code == 401
    # Staff authority never appears in the separate subject session.
    assert client.cookies.get("__Host-aiguard_session") is None


@pytest.mark.parametrize("wrong", ["staff_audience", "unreviewed_subject"])
def test_subject_database_login_rejects_staff_token_and_unreviewed_identity(subject_web, wrong):
    client, _settings, flow, _c = subject_web
    flow["audience" if wrong == "staff_audience" else "subject"] = (
        "aiguard-staff" if wrong == "staff_audience" else "unlinked-synthetic-customer"
    )
    _callback, response = subject_login(subject_web)
    assert response.status_code == 401
    assert client.get("/api/subject/v1/me").status_code == 401


def test_subject_database_session_expiry_logout_and_csrf_are_effective(subject_web):
    client, settings, _flow, c = subject_web
    _callback, response = subject_login(subject_web)
    assert response.status_code == 303
    path = "/api/subject/v1/notices/" + c.notice["id"] + "/presentation"
    assert client.post(path, headers={"Origin": settings.public_origin}).status_code == 409
    headers = {
        "Origin": settings.public_origin,
        "X-CSRF-Token": client.cookies.get(settings.cookie_prefix + "csrf"),
    }
    assert client.post(path, headers=headers).status_code == 200
    assert client.post("/subject/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/subject/v1/me").status_code == 401
    _callback, response = subject_login(subject_web)
    assert response.status_code == 303
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE enterprise_subject_sessions SET absolute_until=clock_timestamp()-interval '1 second'"
        )
    assert client.get("/api/subject/v1/me").status_code == 401


def test_subject_database_custodian_gets_scoped_tasks_without_identity_link_read(consent_context):
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient
    from psycopg.types.json import Jsonb

    from app.enterprise.subject_routes import create_subject_router

    c = consent_context
    consent_fixtures.command(c, "grant")
    consent_fixtures.command(c, "withdraw", expected=1)
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles=%s,departments=%s WHERE member_id=%s",
            (Jsonb(["custodian"]), Jsonb(["operations"]), c.ids[2]),
        )
    app = FastAPI()

    @app.exception_handler(GovernanceError)
    async def rejected(_request, error):
        return JSONResponse(
            {"error": {"code": error.code}}, status_code=403 if error.code == "forbidden" else 404
        )

    app.include_router(
        create_subject_router(
            subject_settings(), c.store, staff_identity=lambda _request, **_kwargs: c.c
        )
    )
    with TestClient(app, base_url=subject_settings().public_origin) as client:
        setup = client.get("/api/enterprise/v1/subjects/setup")
        assert setup.status_code == 200 and setup.json() == {
            "issuer": None,
            "can_read_subjects": False,
        }
        path = (
            "/api/enterprise/v1/consent/subjects/"
            + c.subject["subject_id"]
            + "/purposes/"
            + c.notice["id"]
            + "/propagation"
        )
        tasks = client.get(path)
        assert tasks.status_code == 200
        assert set(tasks.json()) == {"propagation", "propagation_complete"}
        assert tasks.json()["propagation"][0]["state"] == "pending"
        assert "oidc_subject" not in tasks.text and "source_record_id" not in tasks.text
        assert client.get("/api/enterprise/v1/subjects/links/" + c.subject["id"]).status_code == 403
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_members SET departments=%s WHERE member_id=%s",
                (Jsonb(["finance"]), c.ids[2]),
            )
        assert client.get(path).status_code == 404


def test_custodian_ui_uses_scoped_propagation_and_exact_evidence_tuple():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = r"""
      const fs = require('node:fs');
      const assert = require('node:assert/strict');
      const { JSDOM } = require('jsdom');
      const { randomUUID } = require('node:crypto');
      const dom = new JSDOM(fs.readFileSync('app/enterprise/static/subject_staff.html','utf8'),
        { url:'https://guard.example.test', runScripts:'outside-only' });
      const w=dom.window, calls=[];
      w.crypto.randomUUID=randomUUID;
      const task={id:randomUUID(),recipient:1,event_revision:2,consent_event_id:randomUUID(),state:'pending'};
      w.fetch=async(path,options={})=>{
        calls.push({path,options});
        let data;
        if(path.endsWith('/me'))data={roles:['custodian'],departments:['operations'],csrf_cookie_name:'synthetic_csrf'};
        else if(path.endsWith('/subjects/setup'))data={issuer:null,can_read_subjects:false};
        else if(path.endsWith('/propagation'))data={propagation:[task],propagation_complete:false};
        else if(path.endsWith('/review'))data={id:task.id,revision:1,state:'verified'};
        else throw Error('unexpected_route');
        return {ok:true,status:200,json:async()=>data};
      };
      w.document.cookie='synthetic_csrf=synthetic-value';
      w.eval(fs.readFileSync('app/enterprise/static/subject_staff.js','utf8'));
      const tick=async()=>{for(let i=0;i<15;i++)await Promise.resolve();};
      (async()=>{
        await tick();
        assert.equal(w.document.getElementById('workspace').hidden,false);
        assert.equal(w.document.getElementById('link-panel').hidden,true);
        assert.equal(w.document.getElementById('offline-panel').hidden,true);
        assert.equal(w.document.getElementById('propagation-panel').hidden,false);
        const form=w.document.getElementById('status-form');
        form.elements.subject_id.value=randomUUID();form.elements.purpose_version.value=randomUUID();
        form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
        assert(calls.some(c=>c.path.includes('/consent/subjects/')&&c.path.endsWith('/propagation')));
        assert(!calls.some(c=>c.path.includes('/subjects/links')));
        const review=w.document.getElementById('propagation-form');
        review.elements.record_id.value=task.id;review.elements.state.value='verified';review.elements.evidence_ref.value=randomUUID();
        review.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
        const posted=calls.find(c=>c.options.method==='POST');
        assert.deepEqual(JSON.parse(posted.options.body).evidence_scope,
          {consent_event_id:task.consent_event_id,event_revision:2,recipient_ordinal:1,expected_state:'pending'});
        dom.window.close();
      })().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});
    """
    result = subprocess.run(
        ["node", "-e", script], cwd=root, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


def test_subject_ui_pages_beyond_one_hundred_notices():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = r"""
      const fs=require('node:fs'),assert=require('node:assert/strict');
      const {JSDOM}=require('jsdom'),{randomUUID}=require('node:crypto');
      const dom=new JSDOM(fs.readFileSync('app/enterprise/static/subject_index.html','utf8'),
        {url:'https://guard.example.test',runScripts:'outside-only'});
      const w=dom.window, notices=Array.from({length:105},()=>({notice_id:randomUUID(),title:'Synthetic notice'}));
      const calls=[];
      w.fetch=async(path)=>{
        calls.push(path);let data;
        if(path.endsWith('/me'))data={csrf_cookie_name:'synthetic_csrf'};
        else {
          const parsed=new URL(path,'https://guard.example.test');
          const cursor=parsed.searchParams.get('cursor');
          const from=cursor?notices.findIndex(n=>n.notice_id===cursor)+1:0;
          const items=notices.slice(from,from+50);
          data={items,next_cursor:from+50<notices.length?items.at(-1).notice_id:null};
        }
        return {ok:true,status:200,json:async()=>data};
      };
      w.eval(fs.readFileSync('app/enterprise/static/subject_app.js','utf8'));
      const tick=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
      (async()=>{
        await tick();const more=w.document.getElementById('load-more');
        assert.equal(w.document.getElementById('notice-list').children.length,50);
        assert.equal(more.hidden,false);more.click();await tick();
        assert.equal(w.document.getElementById('notice-list').children.length,100);
        more.click();await tick();
        assert.equal(w.document.getElementById('notice-list').children.length,105);
        assert.equal(more.hidden,true);assert(calls.at(-1).includes(notices[99].notice_id));
        dom.window.close();
      })().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});
    """
    result = subprocess.run(
        ["node", "-e", script], cwd=root, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr

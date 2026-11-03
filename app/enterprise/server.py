"""Staff BFF and registry adapter over the shared governance commands."""

from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import get_args
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from app.access_logging import install_uvicorn_access_log_filter
from app.enterprise.auth import OIDCClient
from app.enterprise.schemas import (
    ActivityCreate,
    ActivityReview,
    ActivityUpdate,
    EnrollmentProposal,
    GrantProposal,
    NoticeCreate,
    Transition,
)
from app.enterprise.sessions import StaffSessions
from app.enterprise.settings import Settings
from pii_redactor.governance.audit_view import AuditView
from pii_redactor.governance.authority import Authority
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Enrollment, Principal, Role
from pii_redactor.governance.permissions import current_member
from pii_redactor.governance.registry import Registry
from pii_redactor.governance.store import Store
from pii_redactor.pdpa_catalog import SENSITIVE, coverage_catalog
from pii_redactor.pdpa_lifecycle import _ENUMS


def _error(code, status):
    return JSONResponse(
        {"error": {"code": code, "correlation_id": str(uuid4())}}, status_code=status
    )


class _RequestBoundary:
    def __init__(self, app, origin, secure=True):
        self.app, self.secure = app, secure
        self.origin = urlsplit(origin)

    def _host_valid(self, scope):
        try:
            values = [v.decode("ascii") for k, v in scope["headers"] if k.lower() == b"host"]
            if len(values) != 1 or any(ord(c) < 33 or ord(c) == 127 for c in values[0]):
                return False
            parsed = urlsplit(self.origin.scheme + "://" + values[0])
            default_port = 443 if self.origin.scheme == "https" else 80
            return (
                parsed.hostname == self.origin.hostname
                and (parsed.port or default_port) == (self.origin.port or default_port)
                and parsed.username is None
                and parsed.password is None
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )
        except (UnicodeError, ValueError):
            return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def protected_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {b"cache-control", b"referrer-policy"}
                ]
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                        (
                            b"content-security-policy",
                            b"default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
                        ),
                    ]
                )
                if self.secure:
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                message = {**message, "headers": headers}
            await send(message)

        if not self._host_valid(scope):
            return await _error("invalid_request", 400)(scope, receive, protected_send)
        if len(scope.get("query_string", b"")) > 8192:
            return await _error("request_too_large", 414)(scope, receive, protected_send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > 65536:
                return await _error("request_too_large", 413)(scope, receive, protected_send)
            chunks.append(message)
            if not message.get("more_body", False):
                break

        async def bounded_receive():
            return chunks.pop(0) if chunks else await receive()

        try:
            await self.app(scope, bounded_receive, protected_send)
        except Exception:
            if started:
                raise RuntimeError("enterprise_response_failed") from None
            await _error("internal_error", 500)(scope, bounded_receive, protected_send)


_FROM_ENV = object()


class _IdentityFlight:
    def __init__(self):
        self.pending = None

    async def check(self, operation):
        if self.pending is None or self.pending.done():
            self.pending = asyncio.create_task(operation())
        await asyncio.shield(self.pending)


async def _production_readiness(
    settings, store, key_provider, oidc, subject_router, runtime_gate=None, identity_flight=None
):
    from app.enterprise.operations import runtime_request_report

    report = (
        await run_in_threadpool(runtime_gate.request_report)
        if runtime_gate
        else await run_in_threadpool(runtime_request_report, settings, store, key_provider)
    )
    if report["status"] != "ready":
        report["checks"]["idp"] = "unverified_prerequisites"
        return report

    async def identities():
        await oidc.check_ready(refresh=True)
        if subject_router is None:
            raise GovernanceError("identity_unavailable")
        await subject_router.subject_oidc.check_ready(refresh=True)

    try:
        if identity_flight is None:
            await identities()
        else:
            await identity_flight.check(identities)
        if runtime_gate is not None:
            # Identity I/O may outlive the local proof or a quarantine transition.
            report = await run_in_threadpool(runtime_gate.request_report)
        report["checks"]["idp"] = "ready"
    except Exception:
        report["checks"]["idp"] = "blocked"
    report["status"] = (
        "ready" if all(v == "ready" for v in report["checks"].values()) else "blocked"
    )
    return report


def create_app(
    settings: Settings,
    *,
    store=None,
    oidc_transport=None,
    subject_settings=_FROM_ENV,
    subject_oidc_transport=None,
    managed_key_provider=_FROM_ENV,
):
    if not isinstance(settings, Settings):
        raise GovernanceError("configuration_invalid")
    install_uvicorn_access_log_filter()
    store = store or Store(settings.database_dsn, settings.organization_id)
    if store.organization_id != settings.organization_id:
        raise GovernanceError("configuration_invalid")
    store.production_operations_required = not settings.development
    if settings.development:
        store.check_ready()
    sessions, registry, authority = StaffSessions(store), Registry(store), Authority(store)
    oidc = OIDCClient(settings, transport=oidc_transport)
    from app.enterprise.capabilities import managed_keys_from_env, subject_from_env

    if subject_settings is _FROM_ENV:
        subject_settings = subject_from_env(settings)
    if managed_key_provider is _FROM_ENV:
        try:
            managed_key_provider = managed_keys_from_env(settings)
        except GovernanceError:
            if settings.development:
                raise
            managed_key_provider = None
    store.runtime_key_version = getattr(managed_key_provider, "active_version", "")
    subject_router = None
    managed_collection = None
    managed_rights = None
    from app.enterprise.operations import RuntimeGate

    runtime_gate = (
        RuntimeGate(settings, store, managed_key_provider) if not settings.development else None
    )
    identity_flight = _IdentityFlight()

    @asynccontextmanager
    async def lifespan(_app):
        if settings.development:
            await oidc.check_ready()
            if subject_router is not None:
                await subject_router.subject_oidc.check_ready()
        task = asyncio.create_task(runtime_gate.run()) if runtime_gate else None
        try:
            yield
        finally:
            if runtime_gate:
                runtime_gate.close()
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.production_gate = runtime_gate
    prefix = settings.cookie_prefix

    async def production_readiness():
        return await _production_readiness(
            settings,
            store,
            managed_key_provider,
            oidc,
            subject_router,
            runtime_gate,
            identity_flight,
        )

    @app.middleware("http")
    async def production_barrier(request, call_next):
        if not settings.development and request.url.path != "/health/live":
            report = await production_readiness()
            if request.url.path == "/health/ready":
                return JSONResponse(report, status_code=200 if report["status"] == "ready" else 503)
            if report["status"] != "ready":
                return _error("production_prerequisites_unverified", 503)
        return await call_next(request)

    app.add_middleware(
        _RequestBoundary, origin=settings.public_origin, secure=not settings.development
    )

    @app.exception_handler(GovernanceError)
    async def governance_error(_request, error):
        if _request.url.path == "/auth/callback" and "text/html" in _request.headers.get(
            "accept", ""
        ):
            return RedirectResponse("/?login=failed", status_code=303)
        status = 409
        if error.code in {"authentication_required", "authentication_failed"}:
            status = 401
        elif error.code in {"forbidden", "independent_review_required"}:
            status = 403
        elif error.code == "record_unavailable":
            status = 404
        elif error.code in {
            "storage_failure",
            "identity_unavailable",
            "migration_mismatch",
            "enrollment_required",
            "audit_integrity_failure",
        }:
            status = 503
        elif error.code == "invalid_request":
            status = 422
        return _error(error.code, status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error_value):
        return _error("invalid_request", 422)

    @app.exception_handler(HTTPException)
    async def framework_error(_request, error):
        return _error("invalid_request", error.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(_request, _error_value):
        return _error("internal_error", 500)

    def identity(request, *, mutation=False):
        origins = request.headers.getlist("origin")
        if (origins and origins != [settings.public_origin]) or (
            mutation and origins != [settings.public_origin]
        ):
            raise GovernanceError("forbidden")
        cookie = request.cookies.get(prefix + "session", "")
        principal = sessions.resolve(cookie)
        if mutation:
            values = request.headers.getlist("x-csrf-token")
            if len(values) != 1:
                raise GovernanceError("forbidden")
            sessions.check_csrf(cookie, values[0])
        return principal

    def set_cookie(response, name, value, *, httponly, samesite, max_age):
        response.set_cookie(
            prefix + name,
            value,
            path="/",
            secure=not settings.development,
            httponly=httponly,
            samesite=samesite,
            max_age=max_age,
        )

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready():
        version = await run_in_threadpool(store.check_ready)
        await oidc.check_ready(refresh=True)
        if subject_router is not None:
            await subject_router.subject_oidc.check_ready(refresh=True)
        if managed_collection is not None:
            await run_in_threadpool(managed_collection.check_ready)
        return {"status": "ready", "schema_version": version}

    @app.get("/auth/login")
    async def login():
        binding = secrets.token_urlsafe(32)
        attempt = await run_in_threadpool(sessions.begin_login, binding)
        response = RedirectResponse(await oidc.authorization_url(attempt), status_code=303)
        set_cookie(response, "login", binding, httponly=True, samesite="lax", max_age=300)
        return response

    @app.get("/auth/callback")
    async def callback(request: Request):
        params = request.query_params
        if (
            not {"code", "state"}.issubset(params)
            or set(params) - {"code", "state", "iss", "session_state"}
            or any(len(params.getlist(k)) != 1 for k in params)
            or ("iss" in params and params["iss"] != settings.issuer)
            or len(params.get("session_state", "")) > 1024
        ):
            raise GovernanceError("authentication_failed")
        metadata = await oidc.metadata()
        if (
            metadata.get("authorization_response_iss_parameter_supported") is True
            and params.get("iss") != settings.issuer
        ):
            raise GovernanceError("authentication_failed")
        attempt = await run_in_threadpool(
            sessions.consume_login, params["state"], request.cookies.get(prefix + "login", "")
        )
        principal = await oidc.complete_login(params["code"], attempt)
        grant = await run_in_threadpool(sessions.issue, principal)
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(
            prefix + "login",
            path="/",
            secure=not settings.development,
            httponly=True,
            samesite="lax",
        )
        set_cookie(
            response, "session", grant.cookie, httponly=True, samesite="strict", max_age=28800
        )
        set_cookie(response, "csrf", grant.csrf, httponly=False, samesite="strict", max_age=28800)
        return response

    @app.post("/auth/logout")
    def logout(request: Request):
        identity(request, mutation=True)
        sessions.logout(
            request.cookies.get(prefix + "session", ""), request.headers.get("x-csrf-token", "")
        )
        response = Response(status_code=204)
        for name, httponly in (("session", True), ("csrf", False)):
            response.delete_cookie(
                prefix + name,
                path="/",
                secure=not settings.development,
                httponly=httponly,
                samesite="strict",
            )
        return response

    @app.get("/api/enterprise/v1/me")
    def me(request: Request):
        principal = identity(request)
        with store.transaction() as tx:
            member = current_member(tx, store.organization_id, principal)
            row = tx.execute(
                """SELECT ceil(extract(epoch FROM (absolute_until-clock_timestamp())))::integer AS remaining
                FROM enterprise_staff_sessions WHERE session_id=%s""",
                (principal.session_id,),
            ).fetchone()
            return {
                "id": str(member["member_id"]),
                "roles": member["roles"],
                "departments": member["departments"],
                "csrf_cookie_name": prefix + "csrf",
                "session": {
                    "idle_seconds": sessions.idle_seconds,
                    "absolute_remaining_seconds": max(0, row["remaining"]),
                },
            }

    base = "/api/enterprise/v1"

    @app.get(base + "/catalog")
    def catalog(request: Request):
        principal = identity(request)
        with store.transaction() as tx:
            current_member(tx, store.organization_id, principal)
        return {
            "categories": [
                {
                    "code": r["category"],
                    "sensitive": r["category"] in SENSITIVE
                    or r["category"] == "OTHER_DECLARED_SENSITIVE",
                }
                for r in coverage_catalog()
            ],
            "bases": sorted(_ENUMS["basis"]),
            "sensitive_conditions": sorted(_ENUMS["s26_condition"]),
            "roles": list(get_args(Role)),
        }

    @app.get(base + "/audit")
    def audit(request: Request, limit: int = 100, offset: int = 0):
        return AuditView(store).list_events(identity(request), limit=limit, offset=offset)

    @app.get(base + "/activities")
    def activities(request: Request, limit: int = 100, offset: int = 0):
        return registry.list_activities(identity(request), limit=limit, offset=offset)

    @app.get(base + "/activities/{record_id}")
    def activity(request: Request, record_id: str):
        return registry.get_activity(identity(request), record_id)

    @app.post(base + "/activities")
    def create_activity(request: Request, body: ActivityCreate):
        return registry.create_activity(
            identity(request, mutation=True), body.command_key, body.data
        )

    @app.put(base + "/activities/{record_id}")
    def update_activity(request: Request, record_id: str, body: ActivityUpdate):
        return registry.update_activity(
            identity(request, mutation=True),
            body.command_key,
            record_id,
            body.expected_revision,
            body.data,
        )

    @app.post(base + "/activities/{record_id}/submit")
    def submit_activity(request: Request, record_id: str, body: Transition):
        return registry.submit_activity(
            identity(request, mutation=True), body.command_key, record_id, body.expected_revision
        )

    @app.post(base + "/activities/{record_id}/review")
    def review_activity(request: Request, record_id: str, body: ActivityReview):
        return registry.review_activity(
            identity(request, mutation=True),
            body.command_key,
            record_id,
            body.expected_revision,
            body.data,
        )

    @app.get(base + "/activities/{record_id}/notices")
    def notices(request: Request, record_id: str, limit: int = 100, offset: int = 0):
        return registry.list_notices(identity(request), record_id, limit=limit, offset=offset)

    @app.post(base + "/notices")
    def create_notice(request: Request, body: NoticeCreate):
        return registry.create_notice(
            identity(request, mutation=True),
            body.command_key,
            body.data,
            expected_activity_revision=body.expected_activity_revision,
        )

    @app.get(base + "/notices/{record_id}")
    def get_notice(request: Request, record_id: str):
        return registry.get_notice(identity(request), record_id)

    @app.post(base + "/notices/{record_id}/publish")
    def publish_notice(request: Request, record_id: str, body: Transition):
        return registry.publish_notice(
            identity(request, mutation=True), body.command_key, record_id, body.expected_revision
        )

    @app.get(base + "/members")
    def members(request: Request, limit: int = 100, offset: int = 0):
        return authority.list_members(identity(request), limit=limit, offset=offset)

    @app.get(base + "/members/{record_id}")
    def member(request: Request, record_id: str):
        return authority.get_member(identity(request), record_id)

    @app.get(base + "/grants")
    def grants(request: Request, limit: int = 100, offset: int = 0):
        return authority.list_grants(identity(request), limit=limit, offset=offset)

    @app.get(base + "/grants/{record_id}")
    def grant(request: Request, record_id: str):
        return authority.get_grant(identity(request), record_id)

    @app.post(base + "/members")
    def enroll_member(request: Request, body: EnrollmentProposal):
        principal = identity(request, mutation=True)
        try:
            target = Enrollment(
                principal=Principal(issuer=settings.issuer, subject=body.data.subject),
                roles=body.data.roles,
                departments=body.data.departments,
            )
        except ValidationError:
            raise GovernanceError("invalid_request") from None
        return authority.propose_enrollment(principal, body.command_key, target)

    @app.post(base + "/members/{record_id}/grants")
    def propose_grant(request: Request, record_id: str, body: GrantProposal):
        return authority.propose_grant(
            identity(request, mutation=True),
            body.command_key,
            record_id,
            body.roles,
            body.departments,
            enabled=body.enabled,
        )

    @app.post(base + "/members/{record_id}/suspend")
    def suspend_member(request: Request, record_id: str, body: Transition):
        return authority.suspend_member(
            identity(request, mutation=True), body.command_key, record_id, body.expected_revision
        )

    @app.post(base + "/grants/{record_id}/approve")
    def approve_grant(request: Request, record_id: str, body: Transition):
        return authority.approve_grant(
            identity(request, mutation=True), body.command_key, record_id, body.expected_revision
        )

    app.state.subjects_enabled = subject_settings is not None
    app.state.managed_enabled = managed_key_provider is not None
    if subject_settings is not None:
        from app.enterprise.subject_auth import SubjectOIDCSettings
        from app.enterprise.subject_routes import create_subject_router

        if (
            not isinstance(subject_settings, SubjectOIDCSettings)
            or subject_settings.public_origin != settings.public_origin
            or subject_settings.staff_client_id != settings.client_id
        ):
            raise GovernanceError("configuration_invalid")
        subject_router = create_subject_router(
            subject_settings,
            store,
            staff_identity=identity,
            oidc_transport=subject_oidc_transport,
        )
        if runtime_gate is not None:
            runtime_gate.subject_settings = subject_router.subject_oidc.settings
        app.include_router(subject_router)
    if managed_key_provider is not None:
        from app.enterprise.capabilities import managed_services
        from app.enterprise.managed_routes import build_managed_router

        managed_collection, managed_evidence, managed_execution, managed_worker = managed_services(
            store,
            managed_key_provider,
        )
        app.state.managed_collection = managed_collection
        app.state.managed_execution = managed_execution
        app.state.managed_worker = managed_worker
        app.include_router(
            build_managed_router(
                managed_collection,
                managed_execution,
                managed_evidence,
                identity,
            )
        )
        from app.enterprise.processing_control_routes import build_processing_router

        app.include_router(build_processing_router(managed_execution.processing_controls, identity))
        app.state.processing_controls = managed_execution.processing_controls
        from app.enterprise.retention_routes import build_retention_router
        from pii_redactor.governance.holds import Holds
        from pii_redactor.governance.retention import Retention

        app.include_router(
            build_retention_router(
                Retention(store, execution=managed_execution),
                Holds(store),
                identity,
            )
        )

        if subject_router is not None:
            from app.enterprise.rights_routes import build_rights_router
            from pii_redactor.governance.rights import Rights

            managed_rights = Rights(store, managed_collection, managed_evidence, managed_execution)
            app.include_router(
                build_rights_router(
                    managed_rights,
                    staff_identity=identity,
                    subject_identity=subject_router.subject_identity,
                )
            )
            subject_router.rights_enabled = True
            app.state.managed_rights = managed_rights

    from app.enterprise.capabilities import rights_case_checker
    from app.enterprise.governance_routes import build_governance_router

    app.include_router(
        build_governance_router(
            store,
            identity,
            case_checker=rights_case_checker(managed_rights) if managed_rights else None,
        )
    )
    app.state.governance_enabled = True
    app.state.rights_enabled = managed_rights is not None

    static = Path(__file__).with_name("static")
    if static.is_dir():
        app.mount("/static", StaticFiles(directory=static), name="static")

        @app.get("/")
        def home():
            links = ['<a class="secondary" href="/governance">ทะเบียนและข้อควบคุมขององค์กร</a>']
            if managed_rights is not None:
                links.append('<a class="secondary" href="/rights">คำขอใช้สิทธิและการส่งมอบ</a>')
            if subject_settings is not None:
                links.append('<a class="secondary" href="/subject/staff">ตัวตนและความยินยอม</a>')
            if managed_collection is not None:
                links.extend(
                    [
                        '<a class="secondary" href="/managed">เอกสารและคำสั่งที่อนุมัติ</a>',
                        '<a class="secondary" href="/processing-controls">อนุมัติข้อควบคุมก่อนประมวลผล</a>',
                        '<a class="secondary" href="/retention">การเก็บรักษาและระงับการดำเนินการ</a>',
                    ]
                )
            if links:
                content = (static / "index.html").read_text(encoding="utf-8")
                navigation = (
                    '<nav class="toolbar" aria-label="งานข้อมูลส่วนบุคคล">' + " ".join(links) + "</nav>"
                )
                return HTMLResponse(
                    content.replace("<!-- enterprise-feature-links -->", navigation)
                )
            return FileResponse(static / "index.html")

    return app

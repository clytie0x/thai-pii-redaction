"""Callable subject portal router; staff mutations retain staff BFF authority."""

import secrets
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from app.enterprise.subject_auth import SubjectOIDCClient, SubjectOIDCSettings, SubjectSessions
from pii_redactor.governance.consent import (
    Consent,
    ConsentScope,
    NoticeProof,
    OfflineConsentInput,
    PropagationScope,
)
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel
from pii_redactor.governance.registry import RecordID
from pii_redactor.governance.subjects import SubjectLinkInput, SubjectLinks


class SubjectEvent(ClosedModel):
    command_key: RecordID
    notice_version: NoticeProof
    purpose_scope: ConsentScope
    action: Literal["grant", "refuse", "withdraw"]
    affirmative: bool


class LinkProposal(ClosedModel):
    command_key: RecordID
    data: SubjectLinkInput
    subject_id: RecordID | None = None
    expected_revision: int | None = None


class EvidencedReview(ClosedModel):
    command_key: RecordID
    expected_revision: int
    decision: Literal["approve", "reject"]
    evidence_ref: RecordID


class OfflineProposal(ClosedModel):
    command_key: RecordID
    data: OfflineConsentInput


class PropagationReview(ClosedModel):
    command_key: RecordID
    state: Literal["failed", "verified"]
    evidence_ref: RecordID
    evidence_scope: PropagationScope


def create_subject_router(
    settings: SubjectOIDCSettings, store, *, staff_identity, oidc_transport=None
):
    """Mount in the enterprise app with its bounded request/error middleware."""
    if not isinstance(settings, SubjectOIDCSettings) or not callable(staff_identity):
        raise GovernanceError("configuration_invalid")
    router = APIRouter()
    sessions = SubjectSessions(store, issuer=settings.issuer, client_id=settings.client_id)
    oidc = SubjectOIDCClient(settings, transport=oidc_transport)
    consent, links = Consent(store), SubjectLinks(store)
    prefix = settings.cookie_prefix

    # Parent readiness/lifespan can check the same approved provider boundary.
    router.subject_oidc = oidc

    def identity(request, *, mutation=False):
        origins = request.headers.getlist("origin")
        if (origins and origins != [settings.public_origin]) or (
            mutation and origins != [settings.public_origin]
        ):
            raise GovernanceError("forbidden")
        cookie = request.cookies.get(prefix + "session", "")
        actor = sessions.resolve(cookie)
        if mutation:
            values = request.headers.getlist("x-csrf-token")
            if len(values) != 1:
                raise GovernanceError("forbidden")
            sessions.check_csrf(cookie, values[0])
        return actor

    router.subject_identity = identity
    router.rights_enabled = False

    def cookie(response, name, value, *, httponly, samesite="strict", max_age=28800):
        response.set_cookie(
            prefix + name,
            value,
            path="/",
            secure=not settings.development,
            httponly=httponly,
            samesite=samesite,
            max_age=max_age,
        )

    @router.get("/subject")
    @router.get("/subject/")
    def home():
        path = Path(__file__).with_name("static") / "subject_index.html"
        if router.rights_enabled:
            return HTMLResponse(
                path.read_text(encoding="utf-8").replace(
                    "<!-- enterprise-rights-link -->",
                    '<a class="secondary" href="/subject/rights">คำขอและการส่งมอบของฉัน</a>',
                )
            )
        return FileResponse(path)

    @router.get("/subject/staff")
    def staff_home():
        return FileResponse(Path(__file__).with_name("static") / "subject_staff.html")

    @router.get("/subject/auth/login")
    async def login():
        binding = secrets.token_urlsafe(32)
        attempt = await run_in_threadpool(sessions.begin_login, binding)
        response = RedirectResponse(await oidc.authorization_url(attempt), status_code=303)
        cookie(response, "login", binding, httponly=True, samesite="lax", max_age=300)
        return response

    @router.get("/subject/auth/callback")
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
        verified = await oidc.complete_login(params["code"], attempt)
        grant = await run_in_threadpool(sessions.issue, verified)
        response = RedirectResponse("/subject", status_code=303)
        response.delete_cookie(
            prefix + "login",
            path="/",
            secure=not settings.development,
            httponly=True,
            samesite="lax",
        )
        cookie(response, "session", grant.cookie, httponly=True)
        cookie(response, "csrf", grant.csrf, httponly=False)
        return response

    @router.post("/subject/auth/logout")
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

    base = "/api/subject/v1"

    @router.get(base + "/me")
    def me(request: Request):
        actor = identity(request)
        return {
            "subject_id": str(actor.subject_id),
            "link_revision": actor.link_revision,
            "csrf_cookie_name": prefix + "csrf",
            "authority": "verified_subject_session",
        }

    @router.get(base + "/notices")
    def notices(request: Request, limit: int = 50, cursor: str | None = None):
        return consent.available_notices(identity(request), limit=limit, cursor=cursor)

    @router.post(base + "/notices/{notice_id}/presentation")
    def presentation(request: Request, notice_id: str):
        return consent.present(identity(request, mutation=True), notice_id)

    @router.post(base + "/events")
    def record_event(request: Request, body: SubjectEvent):
        return consent.record_subject_event(
            identity(request, mutation=True),
            body.command_key,
            body.notice_version,
            body.purpose_scope,
            body.action,
            affirmative=body.affirmative,
        )

    @router.get(base + "/purposes/{purpose_version}")
    def status(request: Request, purpose_version: str):
        return consent.status(identity(request), purpose_version)

    @router.get(base + "/purposes/{purpose_version}/history")
    def history(request: Request, purpose_version: str):
        return consent.history(identity(request), purpose_version)

    staff_base = "/api/enterprise/v1"

    @router.get(staff_base + "/subjects/setup")
    def subject_setup(request: Request):
        from pii_redactor.governance.permissions import require_member

        with store.transaction() as tx:
            principal = staff_identity(request)
            try:
                require_member(tx, store.organization_id, principal, "subject.read")
                can_read_subjects = True
            except GovernanceError as error:
                if error.code != "forbidden":
                    raise
                require_member(tx, store.organization_id, principal, "consent.propagation.read")
                can_read_subjects = False
        return {
            "issuer": settings.issuer if can_read_subjects else None,
            "can_read_subjects": can_read_subjects,
        }

    @router.post(staff_base + "/subjects/links")
    def propose_link(request: Request, body: LinkProposal):
        if body.data.issuer != settings.issuer:
            raise GovernanceError("identity_issuer_mismatch")
        return links.propose(
            staff_identity(request, mutation=True),
            body.command_key,
            body.data,
            subject_id=body.subject_id,
            expected_revision=body.expected_revision,
        )

    @router.get(staff_base + "/subjects/links/{link_id}")
    def get_link(request: Request, link_id: str):
        return links.get(staff_identity(request), link_id)

    @router.post(staff_base + "/subjects/links/{link_id}/review")
    def review_link(request: Request, link_id: str, body: EvidencedReview):
        return links.review(
            staff_identity(request, mutation=True),
            body.command_key,
            link_id,
            body.expected_revision,
            body.decision,
            body.evidence_ref,
        )

    @router.post(staff_base + "/subjects/links/{link_id}/privacy-review")
    def privacy_review_link(request: Request, link_id: str, body: EvidencedReview):
        return links.review(
            staff_identity(request, mutation=True),
            body.command_key,
            link_id,
            body.expected_revision,
            body.decision,
            body.evidence_ref,
            privacy=True,
        )

    @router.post(staff_base + "/consent/offline")
    def propose_offline(request: Request, body: OfflineProposal):
        return consent.propose_offline(
            staff_identity(request, mutation=True), body.command_key, body.data
        )

    @router.get(staff_base + "/consent/offline/{case_id}")
    def get_offline(request: Request, case_id: str):
        return consent.get_offline(staff_identity(request), case_id)

    @router.get(staff_base + "/subjects/{subject_id}/purposes/{purpose_version}")
    def staff_consent_status(request: Request, subject_id: str, purpose_version: str):
        return consent.staff_status(staff_identity(request), subject_id, purpose_version)

    @router.get(
        staff_base + "/consent/subjects/{subject_id}/purposes/{purpose_version}/propagation"
    )
    def scoped_propagation(request: Request, subject_id: str, purpose_version: str):
        return consent.propagation_tasks(staff_identity(request), subject_id, purpose_version)

    @router.post(staff_base + "/consent/offline/{case_id}/review")
    def review_offline(request: Request, case_id: str, body: EvidencedReview):
        return consent.review_offline(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.decision,
            body.evidence_ref,
        )

    @router.post(staff_base + "/consent/propagation/{propagation_id}/review")
    def propagation(request: Request, propagation_id: str, body: PropagationReview):
        return consent.review_propagation(
            staff_identity(request, mutation=True),
            body.command_key,
            propagation_id,
            body.state,
            body.evidence_ref,
            evidence_scope=body.evidence_scope,
        )

    return router

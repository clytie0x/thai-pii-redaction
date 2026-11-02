"""Mountable M7 BFF. Parent supplies real staff/subject session and CSRF hooks."""

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from pydantic import Field

from app.enterprise.schemas import Command, Transition
from pii_redactor.governance.delivery import Delivery
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Department
from pii_redactor.governance.registry import RecordID
from pii_redactor.governance.rights import FulfilmentPlan, Intake, Right, Verification

PRIVATE_HEADERS = {
    "Cache-Control": "no-store, private, max-age=0",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
}


class PrivateRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def private(request):
            try:
                response = await handler(request)
            except RequestValidationError:
                response = JSONResponse({"error": {"code": "validation_error"}}, status_code=422)
            except GovernanceError as error:
                code = str(error)
                if not re.fullmatch(r"[a-z_]{1,64}", code):
                    code = "request_failed"
                status = (
                    401
                    if code == "authentication_required"
                    else 403
                    if code in {"forbidden", "record_unavailable"}
                    else 409
                )
                response = JSONResponse({"error": {"code": code}}, status_code=status)
            response.headers.update(PRIVATE_HEADERS)
            return response

        return private


class IntakeCommand(Command):
    data: Intake


class VerifyCommand(Transition):
    data: Verification


class PlanCommand(Transition):
    data: FulfilmentPlan


class EvidenceCommand(Transition):
    evidence_ref: RecordID


class CloseCommand(EvidenceCommand):
    partial: bool = False


class ManualCommand(EvidenceCommand):
    obligation_id: RecordID
    review: bool = False
    decision: Literal["verified", "failed"] = "verified"


class IssueCommand(Transition):
    approved_export_version: int
    expires_at: datetime = Field(strict=False)


class ReceiptCommand(Transition):
    receipt_token: RecordID


class SubjectIntake(Command):
    department_id: Department
    rights: list[Right]


def build_rights_router(rights, *, staff_identity, subject_identity):
    if not callable(staff_identity) or not callable(subject_identity):
        raise GovernanceError("configuration_invalid")
    delivery = Delivery(rights)
    router = APIRouter(route_class=PrivateRoute)
    base = "/api/enterprise/v1/rights"
    subject = "/api/subject/v1/rights"

    @router.get("/rights")
    def staff_page():
        return FileResponse(Path(__file__).with_name("static") / "rights_staff.html")

    @router.get("/subject/rights")
    def subject_page():
        return FileResponse(Path(__file__).with_name("static") / "rights_subject.html")

    @router.get(base)
    def cases(request: Request, limit: int = 50, cursor: str | None = None):
        return rights.list(staff_identity(request), limit=limit, cursor=cursor)

    @router.post(base)
    def receive(request: Request, body: IntakeCommand):
        return rights.receive(staff_identity(request, mutation=True), body.command_key, body.data)

    @router.get(base + "/{case_id}")
    def detail(request: Request, case_id: RecordID):
        return rights.get(staff_identity(request), case_id)

    @router.get(base + "/{case_id}/advice/{collection_id}")
    def advice(request: Request, case_id: RecordID, collection_id: RecordID):
        return rights.advice(staff_identity(request), case_id, collection_id)

    @router.post(base + "/{case_id}/verify")
    def verify(request: Request, case_id: RecordID, body: VerifyCommand):
        return rights.verify(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.data,
        )

    @router.post(base + "/{case_id}/plan")
    def plan(request: Request, case_id: RecordID, body: PlanCommand):
        return rights.plan(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.data,
        )

    @router.post(base + "/{case_id}/preview")
    def preview(request: Request, case_id: RecordID, body: Transition):
        return rights.preview(
            staff_identity(request, mutation=True), case_id, body.expected_revision
        )

    @router.post(base + "/{case_id}/review")
    def review(request: Request, case_id: RecordID, body: EvidenceCommand):
        return rights.review(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.evidence_ref,
        )

    @router.post(base + "/{case_id}/manual")
    def manual(request: Request, case_id: RecordID, body: ManualCommand):
        return rights.manual_evidence(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.obligation_id,
            body.evidence_ref,
            review=body.review,
            decision=body.decision,
        )

    @router.post(base + "/{case_id}/close")
    def close(request: Request, case_id: RecordID, body: CloseCommand):
        return rights.close(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.evidence_ref,
            partial=body.partial,
        )

    @router.post(base + "/{case_id}/reopen")
    def reopen(request: Request, case_id: RecordID, body: EvidenceCommand):
        return rights.transition(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.evidence_ref,
            action="reopen",
        )

    @router.post(base + "/{case_id}/withdraw")
    def withdraw(request: Request, case_id: RecordID, body: EvidenceCommand):
        return rights.transition(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.evidence_ref,
            action="withdraw",
        )

    @router.post(base + "/{case_id}/delivery")
    def issue(request: Request, case_id: RecordID, body: IssueCommand):
        return delivery.issue(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.approved_export_version,
            body.expires_at,
        )

    @router.post(base + "/{case_id}/revoke")
    def revoke(request: Request, case_id: RecordID, body: EvidenceCommand):
        return delivery.revoke(
            staff_identity(request, mutation=True),
            body.command_key,
            case_id,
            body.expected_revision,
            body.evidence_ref,
        )

    @router.get(subject)
    def subject_cases(request: Request):
        return {"items": rights.subject_cases(subject_identity(request))}

    @router.post(subject)
    def subject_receive(request: Request, body: SubjectIntake):
        return rights.subject_receive(
            subject_identity(request, mutation=True),
            body.command_key,
            body.department_id,
            body.rights,
        )

    @router.post(subject + "/deliveries/{delivery_id}/consume")
    def consume(request: Request, delivery_id: RecordID, body: Command):
        return delivery.consume(subject_identity(request, mutation=True), delivery_id)

    @router.post(subject + "/deliveries/{delivery_id}/receipt")
    def receipt(request: Request, delivery_id: RecordID, body: ReceiptCommand):
        return delivery.acknowledge(
            subject_identity(request, mutation=True),
            delivery_id,
            body.expected_revision,
            body.receipt_token,
        )

    return router

"""Staff adapter for exact reviewed processing controls; parent supplies BFF identity."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import Field

from app.enterprise.rights_routes import PrivateRoute
from app.enterprise.schemas import Command, Transition
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel, Department
from pii_redactor.governance.processing_controls import ProcessingInput
from pii_redactor.governance.registry import RecordID


class ProcessingCreate(Command):
    data: ProcessingInput


class ProcessingReplace(ProcessingCreate):
    expected_revision: int = Field(ge=1)


class ProcessingReview(Transition):
    decision: Literal["approve", "reject"]
    evidence_ref: RecordID


class ProcessingPreview(ClosedModel):
    expected_revision: int = Field(ge=1)


def build_processing_router(service, identity):
    if not callable(identity):
        raise GovernanceError("configuration_invalid")
    router = APIRouter(route_class=PrivateRoute)
    base = "/api/enterprise/v1/processing"

    @router.get("/processing-controls")
    def page(request: Request):
        identity(request)
        return FileResponse(Path(__file__).with_name("static") / "processing_controls_index.html")

    @router.get(base)
    def listing(
        request: Request, department_id: Department, limit: int = 50, cursor: str | None = None
    ):
        return service.list(identity(request), department_id, limit=limit, cursor=cursor)

    @router.get(base + "/activities")
    def activities(
        request: Request, department_id: Department, limit: int = 50, cursor: str | None = None
    ):
        return service.activities(identity(request), department_id, limit=limit, cursor=cursor)

    @router.get(base + "/controls")
    def controls(
        request: Request, department_id: Department, limit: int = 50, cursor: str | None = None
    ):
        return service.catalog(identity(request), department_id, limit=limit, cursor=cursor)

    @router.post(base)
    def create(request: Request, body: ProcessingCreate):
        return service.create(identity(request, mutation=True), body.command_key, body.data)

    @router.get(base + "/{binding_id}")
    def detail(request: Request, binding_id: RecordID):
        return service.get(identity(request), binding_id)

    @router.get(base + "/{binding_id}/history")
    def history(request: Request, binding_id: RecordID, after: int = 0, limit: int = 50):
        return service.history(identity(request), binding_id, after=after, limit=limit)

    @router.post(base + "/{binding_id}/replace")
    def replace(request: Request, binding_id: RecordID, body: ProcessingReplace):
        return service.replace(
            identity(request, mutation=True),
            body.command_key,
            binding_id,
            body.expected_revision,
            body.data,
        )

    @router.post(base + "/{binding_id}/preview")
    def preview(request: Request, binding_id: RecordID, body: ProcessingPreview):
        return service.preview(identity(request, mutation=True), binding_id, body.expected_revision)

    @router.post(base + "/{binding_id}/submit")
    def submit(request: Request, binding_id: RecordID, body: Transition):
        return service.submit(
            identity(request, mutation=True), body.command_key, binding_id, body.expected_revision
        )

    @router.post(base + "/{binding_id}/review")
    def review(request: Request, binding_id: RecordID, body: ProcessingReview):
        return service.review(
            identity(request, mutation=True),
            body.command_key,
            binding_id,
            body.expected_revision,
            body.decision,
            body.evidence_ref,
        )

    @router.post(base + "/{binding_id}/activate")
    def activate(request: Request, binding_id: RecordID, body: Transition):
        return service.activate(
            identity(request, mutation=True), body.command_key, binding_id, body.expected_revision
        )

    return router

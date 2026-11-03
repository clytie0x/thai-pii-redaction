"""Organization register adapter. Parent BFF owns session/origin/CSRF checks."""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.enterprise.schemas import Command, Transition
from pii_redactor.governance.assessments import Assessments
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.incidents import Incidents
from pii_redactor.governance.permissions import require_member
from pii_redactor.governance.policy_register import LegalControls, Policies
from pii_redactor.governance.processors import Processors
from pii_redactor.governance.registry import RecordID
from pii_redactor.governance.responsibilities import Responsibilities
from pii_redactor.governance.transfers import Transfers


class ControlCreate(Command):
    data: dict


class ControlReplace(ControlCreate):
    expected_revision: int


class ControlReview(Transition):
    decision: Literal["approve", "reject"]
    evidence_ref: RecordID


def build_governance_router(store, identity, *, case_checker=None):
    router = APIRouter()
    prefix = "/api/enterprise/v1/governance"
    registers = {
        cls.kind: cls(store, case_checker=case_checker)
        for cls in (
            Processors,
            Transfers,
            Incidents,
            Assessments,
            Responsibilities,
            Policies,
            LegalControls,
        )
    }

    def register(kind):
        if kind not in registers:
            raise GovernanceError("record_unavailable")
        return registers[kind]

    @router.get("/governance")
    def home(request: Request):
        identity(request)
        return FileResponse(Path(__file__).with_name("static") / "governance_index.html")

    @router.get(prefix + "/schemas")
    def schemas(request: Request):
        with store.transaction() as tx:
            require_member(tx, store.organization_id, identity(request), "retention.read")
        return {key: value.input_model.model_json_schema() for key, value in registers.items()}

    @router.get(prefix + "/release-findings")
    def findings(request: Request, department_id: str):
        return registers["legal"].release_findings(
            identity(request), {"department_id": department_id}
        )

    @router.get(prefix + "/{kind}")
    def listing(
        request: Request, kind: str, department_id: str, limit: int = 50, cursor: str | None = None
    ):
        return register(kind).list(identity(request), department_id, limit=limit, cursor=cursor)

    @router.post(prefix + "/{kind}")
    def create(request: Request, kind: str, body: ControlCreate):
        return register(kind).create(identity(request, mutation=True), body.command_key, body.data)

    @router.get(prefix + "/{kind}/{record_id}")
    def detail(request: Request, kind: str, record_id: RecordID):
        return register(kind).get(identity(request), record_id)

    @router.post(prefix + "/{kind}/{record_id}/replace")
    def replace(request: Request, kind: str, record_id: RecordID, body: ControlReplace):
        return register(kind).replace(
            identity(request, mutation=True),
            body.command_key,
            record_id,
            body.expected_revision,
            body.data,
        )

    @router.get(prefix + "/{kind}/{record_id}/history")
    def history(request: Request, kind: str, record_id: RecordID, after: int = 0, limit: int = 50):
        return register(kind).history(identity(request), record_id, after=after, limit=limit)

    @router.post(prefix + "/{kind}/{record_id}/submit")
    def submit(request: Request, kind: str, record_id: RecordID, body: Transition):
        return register(kind).submit(
            identity(request, mutation=True), body.command_key, record_id, body.expected_revision
        )

    @router.post(prefix + "/{kind}/{record_id}/review")
    def review(request: Request, kind: str, record_id: RecordID, body: ControlReview):
        return register(kind).review(
            identity(request, mutation=True),
            body.command_key,
            record_id,
            body.expected_revision,
            body.decision,
            body.evidence_ref,
        )

    @router.post(prefix + "/{kind}/{record_id}/activate")
    def activate(request: Request, kind: str, record_id: RecordID, body: Transition):
        return register(kind).activate(
            identity(request, mutation=True), body.command_key, record_id, body.expected_revision
        )

    return router

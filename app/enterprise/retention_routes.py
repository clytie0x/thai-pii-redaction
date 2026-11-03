"""Staff BFF adapter for reviewed retention and preservation holds."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import Field

from app.enterprise.schemas import Command, Transition
from pii_redactor.governance.holds import HoldInput
from pii_redactor.governance.registry import RecordID
from pii_redactor.governance.retention import PolicyInput, TriggerInput


class PolicyCreate(Command):
    data: PolicyInput


class TriggerCreate(Command):
    data: TriggerInput


class HoldCreate(Command):
    data: HoldInput


class EvidenceTransition(Transition):
    evidence_ref: RecordID


class PolicyReview(EvidenceTransition):
    decision: Literal["approve", "reject"]


class CopyReview(EvidenceTransition):
    state: Literal["failed", "verified"]


class DueScan(Command):
    as_of: datetime | None = Field(default=None, strict=False)
    limit: int = Field(ge=1, le=100, default=100)


def build_retention_router(retention, holds, identity):
    router = APIRouter()
    base = "/api/enterprise/v1/retention"

    @router.get("/retention")
    def home():
        return FileResponse(Path(__file__).with_name("static") / "retention_index.html")

    @router.get(base + "/collections/{collection_id}/policies")
    def policies(
        request: Request, collection_id: RecordID, limit: int = 50, cursor: str | None = None
    ):
        return retention.list_policies(identity(request), collection_id, limit=limit, cursor=cursor)

    @router.post(base + "/policies")
    def propose_policy(request: Request, body: PolicyCreate):
        return retention.propose_policy(
            identity(request, mutation=True), body.command_key, body.data
        )

    @router.post(base + "/policies/{policy_id}/review")
    def review_policy(request: Request, policy_id: RecordID, body: PolicyReview):
        return retention.review_policy(
            identity(request, mutation=True),
            body.command_key,
            policy_id,
            body.expected_revision,
            body.decision,
            body.evidence_ref,
        )

    @router.post(base + "/triggers")
    def trigger(request: Request, body: TriggerCreate):
        return retention.record_trigger(
            identity(request, mutation=True), body.command_key, body.data
        )

    @router.get(base + "/triggers/{trigger_id}")
    def get_trigger(request: Request, trigger_id: RecordID):
        return retention.get_trigger(identity(request), trigger_id)

    @router.post(base + "/triggers/{trigger_id}/review")
    def review_trigger(request: Request, trigger_id: RecordID, body: EvidenceTransition):
        return retention.review_trigger(
            identity(request, mutation=True),
            body.command_key,
            trigger_id,
            body.expected_revision,
            body.evidence_ref,
        )

    @router.post(base + "/collections/{collection_id}/due-scan")
    def scan(request: Request, collection_id: RecordID, body: DueScan):
        return {
            "items": retention.propose_due(
                body.as_of or datetime.now(UTC),
                limit=body.limit,
                principal=identity(request, mutation=True),
                collection_id=collection_id,
            )
        }

    @router.get(base + "/collections/{collection_id}/due")
    def due(request: Request, collection_id: RecordID, limit: int = 50, cursor: str | None = None):
        return retention.list_due(identity(request), collection_id, limit=limit, cursor=cursor)

    @router.post(base + "/due/{due_id}/approve")
    def approve_due(request: Request, due_id: RecordID, body: EvidenceTransition):
        return retention.approve_due(
            identity(request, mutation=True),
            body.command_key,
            due_id,
            body.expected_revision,
            body.evidence_ref,
        )

    @router.get(base + "/due/{due_id}")
    def due_detail(request: Request, due_id: RecordID):
        return retention.get_due(identity(request), due_id)

    @router.post(base + "/due/{due_id}/issue")
    def issue(request: Request, due_id: RecordID, body: Transition):
        return retention.issue_instruction(
            identity(request, mutation=True), body.command_key, due_id, body.expected_revision
        )

    @router.get(base + "/due/{due_id}/disposition")
    def disposition(request: Request, due_id: RecordID):
        return retention.disposition(identity(request), due_id)

    @router.post(base + "/copies/{obligation_id}/review")
    def copy_review(request: Request, obligation_id: RecordID, body: CopyReview):
        return retention.review_copy(
            identity(request, mutation=True),
            body.command_key,
            obligation_id,
            body.expected_revision,
            body.state,
            body.evidence_ref,
        )

    @router.get(base + "/collections/{collection_id}/holds")
    def list_holds(
        request: Request, collection_id: RecordID, limit: int = 50, cursor: str | None = None
    ):
        return holds.list(identity(request), collection_id, limit=limit, cursor=cursor)

    @router.post(base + "/holds")
    def impose_hold(request: Request, body: HoldCreate):
        return holds.request(identity(request, mutation=True), body.command_key, body.data)

    @router.post(base + "/holds/{hold_id}/review")
    def review_hold(request: Request, hold_id: RecordID, body: EvidenceTransition):
        return holds.review(
            identity(request, mutation=True),
            body.command_key,
            hold_id,
            body.expected_revision,
            body.evidence_ref,
        )

    @router.post(base + "/holds/{hold_id}/release-proposal")
    def propose_release(request: Request, hold_id: RecordID, body: EvidenceTransition):
        return holds.propose_release(
            identity(request, mutation=True),
            body.command_key,
            hold_id,
            body.expected_revision,
            body.evidence_ref,
        )

    @router.post(base + "/holds/{hold_id}/release")
    def release(request: Request, hold_id: RecordID, body: EvidenceTransition):
        return holds.release(
            identity(request, mutation=True),
            body.command_key,
            hold_id,
            body.expected_revision,
            body.evidence_ref,
        )

    return router

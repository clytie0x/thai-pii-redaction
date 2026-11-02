"""Staff-session adapter for protected collection and exact managed instructions."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pydantic import Field

from app.enterprise.schemas import Command, Transition
from pii_redactor.governance.collections import CollectionInput
from pii_redactor.governance.evidence import ContentType, EvidenceInput
from pii_redactor.governance.execution import InstructionInput
from pii_redactor.governance.registry import RecordID


class CollectionCreate(Command):
    data: CollectionInput


class DocumentPut(Command):
    content: str = Field(min_length=1, max_length=32768)
    content_type: ContentType = "text/plain"


class EvidenceCreate(Command):
    data: EvidenceInput


class InstructionCreate(Command):
    data: InstructionInput


def build_managed_router(collection, execution, evidence, identity):
    """The existing BFF owns session, origin and CSRF checks through identity."""
    router = APIRouter()
    prefix = "/api/enterprise/v1/managed"

    @router.get("/managed")
    def managed_page(request: Request):
        identity(request)
        return FileResponse(Path(__file__).with_name("static") / "managed_index.html")

    @router.get(prefix + "/collections")
    def collections(request: Request):
        return {"items": collection.list(identity(request))}

    @router.get(prefix + "/recovery/collections")
    def recovery_collections(request: Request):
        return {"items": collection.recovery_collections(identity(request))}

    @router.post(prefix + "/collections")
    def create_collection(request: Request, body: CollectionCreate):
        return collection.create(identity(request, mutation=True), body.command_key, body.data)

    @router.get(prefix + "/collections/{collection_id}/documents")
    def documents(request: Request, collection_id: RecordID):
        return {"items": collection.documents(identity(request), collection_id)}

    @router.post(prefix + "/collections/{collection_id}/documents")
    def put_document(request: Request, collection_id: RecordID, body: DocumentPut):
        return collection.put(
            identity(request, mutation=True),
            body.command_key,
            collection_id,
            body.content,
            content_type=body.content_type,
        )

    @router.get(prefix + "/collections/{collection_id}/documents/{document_id}/versions/{version}")
    def read_document(
        request: Request, collection_id: RecordID, document_id: RecordID, version: int
    ):
        return collection.read_version(identity(request), collection_id, document_id, version)

    @router.post(prefix + "/evidence")
    def put_evidence(request: Request, body: EvidenceCreate):
        return evidence.put(identity(request, mutation=True), body.command_key, body.data)

    @router.get(prefix + "/evidence/{evidence_id}")
    def read_evidence(request: Request, evidence_id: RecordID):
        return evidence.read(identity(request), evidence_id)

    @router.get(prefix + "/instructions")
    def instructions(request: Request):
        return {"items": execution.list(identity(request))}

    @router.get(prefix + "/instructions/{instruction_id}")
    def get_instruction(request: Request, instruction_id: RecordID):
        return execution.get(identity(request), instruction_id)

    @router.get(prefix + "/instructions/{instruction_id}/evidence")
    def preview_evidence(request: Request, instruction_id: RecordID, expected_revision: int):
        return execution.preview_evidence(identity(request), instruction_id, expected_revision)

    @router.post(prefix + "/instructions")
    def propose(request: Request, body: InstructionCreate):
        return execution.propose(identity(request, mutation=True), body.command_key, body.data)

    @router.post(prefix + "/instructions/{instruction_id}/approve")
    def approve(request: Request, instruction_id: RecordID, body: Transition):
        return execution.approve(
            identity(request, mutation=True),
            body.command_key,
            instruction_id,
            body.expected_revision,
        )

    @router.post(prefix + "/instructions/{instruction_id}/reconcile")
    def reconcile(request: Request, instruction_id: RecordID, body: Transition):
        return execution.reconcile(
            identity(request, mutation=True),
            body.command_key,
            instruction_id,
            body.expected_revision,
        )

    @router.post(prefix + "/collections/{collection_id}/snapshots")
    def snapshot(request: Request, collection_id: RecordID, body: Command):
        return collection.snapshot(
            identity(request, mutation=True), body.command_key, collection_id
        )

    @router.post(prefix + "/snapshots/{snapshot_id}/quarantine")
    def restore(request: Request, snapshot_id: RecordID, body: Transition):
        return collection.restore_quarantine(
            identity(request, mutation=True), body.command_key, snapshot_id, body.expected_revision
        )

    @router.post(prefix + "/snapshots/{snapshot_id}/reconcile")
    def reconcile_restore(request: Request, snapshot_id: RecordID, body: Transition):
        return collection.reconcile_restore(
            identity(request, mutation=True), body.command_key, snapshot_id, body.expected_revision
        )

    return router

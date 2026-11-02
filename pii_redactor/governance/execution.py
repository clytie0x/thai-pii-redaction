"""Two-person exact instructions and atomic managed-primary outcome evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, ValidationError, field_validator, model_validator

from pii_redactor.governance.commands import check_revision, digest, identifier, run_command
from pii_redactor.governance.connectors.managed_documents import ManagedDocuments
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel, Principal
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.registry import RecordID


class InstructionInput(ClosedModel):
    collection_id: RecordID
    document_id: RecordID
    expected_revision: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    action: Literal["restrict", "suppress", "correct"]
    expires_at: datetime = Field(strict=False)
    evidence_id: RecordID | None = None

    @field_validator("expires_at")
    @classmethod
    def bounded_expiry(cls, value):
        now = datetime.now(UTC)
        if value.tzinfo is None or not now < value <= now + timedelta(hours=24):
            raise ValueError("invalid approval expiry")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def correction_evidence(self):
        if (self.action == "correct") != (self.evidence_id is not None):
            raise ValueError("invalid action evidence")
        return self


def instruction_digest(source):
    if isinstance(source, InstructionInput):
        return digest(source.model_dump(mode="json"))
    return digest(
        {
            "collection_id": str(source["collection_id"]),
            "document_id": str(source["document_id"]),
            "expected_revision": source["target_revision"],
            "expected_version": source["target_version"],
            "action": source["action"],
            "expires_at": source["expires_at"].astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "evidence_id": str(source["evidence_id"]) if source["evidence_id"] else None,
        }
    )


def instruction_view(row):
    return {
        "id": str(row["instruction_id"]),
        "collection_id": str(row["collection_id"]),
        "document_id": str(row["document_id"]),
        "target_revision": row["target_revision"],
        "target_version": row["target_version"],
        "action": row["action"],
        "evidence_id": str(row["evidence_id"]) if row["evidence_id"] else None,
        "proposed_by": str(row["proposed_by"]),
        "approved_by": str(row["approved_by"]) if row["approved_by"] else None,
        "expires_at": row["expires_at"].astimezone(UTC).isoformat(),
        "state": row["state"],
        "revision": row["revision"],
        "primary_verified": row["state"] == "verified",
        "overall_erasure_verified": False,
    }


def emit(store, tx, event_code, instruction, actor_id=None):
    event_id = store.append_event(
        tx,
        event_code=event_code,
        actor_id=actor_id,
        target_id=instruction["instruction_id"],
        revision=instruction["revision"],
    )
    tx.execute(
        "INSERT INTO governance_outbox(event_id,event_code,payload) VALUES (%s,%s,%s)",
        (
            event_id,
            event_code,
            Jsonb(
                {
                    "record_id": str(instruction["instruction_id"]),
                    "revision": instruction["revision"],
                }
            ),
        ),
    )


class Execution:
    def __init__(self, store, collection, evidence):
        self.store, self.collection, self.evidence = store, collection, evidence
        self.connector = ManagedDocuments(collection, evidence)

    def _instruction(self, tx, member, instruction_id, *, allow_quarantine=False):
        row = tx.execute(
            "SELECT * FROM governance_execution_instructions WHERE instruction_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(instruction_id), self.store.organization_id),
        ).fetchone()
        if not row:
            raise GovernanceError("record_unavailable")
        self.collection._scope(tx, member, row["collection_id"], allow_quarantine=allow_quarantine)
        if instruction_digest(row) != row["instruction_digest"]:
            raise GovernanceError("instruction_integrity_failure")
        return row

    def _current_actor(self, tx, member_id, revision, permission, department):
        row = tx.execute(
            "SELECT * FROM governance_members WHERE member_id=%s AND organization_id=%s FOR SHARE",
            (member_id, self.store.organization_id),
        ).fetchone()
        if not row or row["revision"] != revision:
            raise GovernanceError("approval_authority_changed")
        try:
            member = require_member(
                tx,
                self.store.organization_id,
                Principal(issuer=row["issuer"], subject=row["subject"]),
                permission,
                department,
            )
        except GovernanceError:
            raise GovernanceError("approval_authority_changed") from None
        return member

    def _recheck(self, tx, instruction, *, approved, read_only=False):
        from pii_redactor.governance.retention import Retention

        Retention(self.store).fence_instruction(tx, instruction)
        now = tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if instruction["expires_at"] <= now:
            raise GovernanceError("approval_expired")
        if instruction_digest(instruction) != instruction["instruction_digest"]:
            raise GovernanceError("instruction_integrity_failure")
        collection = tx.execute(
            "SELECT * FROM governance_collections WHERE collection_id=%s AND organization_id=%s FOR UPDATE",
            (instruction["collection_id"], self.store.organization_id),
        ).fetchone()
        if not collection:
            raise GovernanceError("record_unavailable")
        proposer = self._current_actor(
            tx,
            instruction["proposed_by"],
            instruction["proposer_revision"],
            "execution.propose",
            collection["department_id"],
        )
        collection = self.collection._scope(tx, proposer, instruction["collection_id"])
        document = self.collection._document(
            tx, instruction["collection_id"], instruction["document_id"]
        )
        if (
            document["revision"] != instruction["target_revision"]
            or document["current_version"] != instruction["target_version"]
        ):
            raise GovernanceError("revision_conflict")
        self.collection.check_consent(
            tx,
            collection,
            document,
            "preview" if read_only else instruction["action"],
        )
        if approved:
            if (
                not instruction["approved_by"]
                or instruction["approved_by"] == instruction["proposed_by"]
            ):
                raise GovernanceError("separation_required")
            self._current_actor(
                tx,
                instruction["approved_by"],
                instruction["approver_revision"],
                "execution.approve",
                collection["department_id"],
            )
        if instruction["action"] == "correct":
            evidence = self.evidence.resolve(
                tx,
                proposer,
                instruction["evidence_id"],
                collection_id=collection["collection_id"],
                document_id=document["document_id"],
                version=document["current_version"],
            )
            self.evidence.content(tx, evidence)
        return collection, document, proposer

    def propose(self, principal, command_key, request):
        try:
            data = InstructionInput.model_validate(request.model_dump())
        except (AttributeError, ValidationError):
            raise GovernanceError("invalid_request") from None

        def scope(tx, member):
            collection = self.collection._scope(tx, member, data.collection_id)
            document = self.collection._document(tx, data.collection_id, data.document_id)
            check_revision(document, data.expected_revision)
            if document["current_version"] != data.expected_version:
                raise GovernanceError("revision_conflict")
            self.collection.check_consent(tx, collection, document, data.action)
            if data.evidence_id:
                evidence = self.evidence.resolve(
                    tx,
                    member,
                    data.evidence_id,
                    collection_id=data.collection_id,
                    document_id=data.document_id,
                    version=data.expected_version,
                )
                self.evidence.content(tx, evidence)
            return document

        def effect(tx, member, document):
            row = tx.execute(
                """INSERT INTO governance_execution_instructions(instruction_id,organization_id,
                collection_id,document_id,target_revision,target_version,action,evidence_id,expires_at,
                instruction_digest,proposed_by,proposer_revision)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    data.collection_id,
                    data.document_id,
                    data.expected_revision,
                    data.expected_version,
                    data.action,
                    data.evidence_id,
                    data.expires_at,
                    instruction_digest(data),
                    member["member_id"],
                    member["revision"],
                ),
            ).fetchone()
            return instruction_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "execution.propose",
            "execution.proposed",
            data.model_dump(mode="json"),
            effect,
            scope=scope,
        )

    def approve(self, principal, command_key, instruction_id, expected_revision):
        instruction_id = identifier(instruction_id)

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            if row["state"] != "proposed":
                raise GovernanceError("invalid_transition")
            if member["member_id"] == row["proposed_by"]:
                raise GovernanceError("separation_required")
            self._recheck(tx, row, approved=False)
            updated = tx.execute(
                """UPDATE governance_execution_instructions SET state='pending',approved_by=%s,
                approver_revision=%s,revision=revision+1 WHERE instruction_id=%s RETURNING *""",
                (member["member_id"], member["revision"], instruction_id),
            ).fetchone()
            tx.execute(
                "INSERT INTO governance_execution_tasks(instruction_id) VALUES (%s)",
                (instruction_id,),
            )
            return instruction_view(updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "execution.approve",
            "execution.approved",
            {"id": str(instruction_id), "revision": expected_revision},
            effect,
            scope=lambda tx, member: self._instruction(tx, member, instruction_id),
        )

    def list(self, principal):
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "execution.read")
            rows = tx.execute(
                """SELECT i.*,c.department_id FROM governance_execution_instructions i
                JOIN governance_collections c USING(collection_id) WHERE i.organization_id=%s
                ORDER BY i.created_at DESC,i.instruction_id LIMIT 100""",
                (self.store.organization_id,),
            ).fetchall()
            return [instruction_view(row) for row in rows if in_scope(member, row["department_id"])]

    def get(self, principal, instruction_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "execution.read")
            return instruction_view(
                self._instruction(tx, member, instruction_id, allow_quarantine=True)
            )

    def preview_evidence(self, principal, instruction_id, expected_revision):
        """An independent reviewer sees only the exact live correction's replacement."""
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "execution.approve")
            instruction = self._instruction(tx, member, instruction_id)
            check_revision(instruction, expected_revision)
            if instruction["state"] != "proposed" or instruction["action"] != "correct":
                raise GovernanceError("invalid_transition")
            if instruction["proposed_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            collection, document, _proposer = self._recheck(
                tx,
                instruction,
                approved=False,
                read_only=True,
            )
            row = self.evidence.resolve(
                tx,
                member,
                instruction["evidence_id"],
                collection_id=collection["collection_id"],
                document_id=document["document_id"],
                version=instruction["target_version"],
            )
            content = self.evidence.content(tx, row)
            self.store.append_event(
                tx,
                event_code="execution.correction_previewed",
                actor_id=member["member_id"],
                target_id=instruction["instruction_id"],
                revision=instruction["revision"],
            )
            return {
                "id": str(row["evidence_id"]),
                "instruction_id": str(instruction["instruction_id"]),
                "content_type": row["content_type"],
                "content": content.decode("utf-8"),
            }

    def execute(self, worker_id, task):
        from pii_redactor.governance.outbox import validate_worker

        worker_id = validate_worker(worker_id)
        instruction_id, lease_token = (
            identifier(task["instruction_id"]),
            identifier(task["lease_token"]),
        )
        with self.store.transaction() as tx:
            self.store.lock(tx)
            lease = tx.execute(
                """SELECT * FROM governance_execution_tasks WHERE instruction_id=%s AND state='running'
                AND worker_id=%s AND lease_token=%s FOR UPDATE""",
                (instruction_id, worker_id, lease_token),
            ).fetchone()
            now = tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if not lease or lease["lease_until"] <= now:
                raise GovernanceError("lease_lost")
            row = tx.execute(
                "SELECT * FROM governance_execution_instructions WHERE instruction_id=%s AND organization_id=%s FOR UPDATE",
                (instruction_id, self.store.organization_id),
            ).fetchone()
            if not row or row["state"] != "running":
                raise GovernanceError("invalid_transition")
            if tx.execute(
                "SELECT 1 FROM governance_execution_outcomes WHERE instruction_id=%s",
                (instruction_id,),
            ).fetchone():
                raise GovernanceError("outcome_reconciliation_required")
            collection, document, proposer = self._recheck(tx, row, approved=True)
            proof = self.connector.apply(tx, collection, document, row, proposer)
            now = tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if min(lease["lease_until"], row["expires_at"]) <= now:
                raise GovernanceError("lease_lost")
            tx.execute(
                """INSERT INTO governance_execution_outcomes(instruction_id,instruction_digest,document_id,
                result_version,result_revision,result_state,ciphertext_digest) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    instruction_id,
                    row["instruction_digest"],
                    row["document_id"],
                    proof["result_version"],
                    proof["result_revision"],
                    proof["result_state"],
                    proof["ciphertext_digest"],
                ),
            )
            updated = tx.execute(
                "UPDATE governance_execution_instructions SET state='verified',revision=revision+1 WHERE instruction_id=%s RETURNING *",
                (instruction_id,),
            ).fetchone()
            tx.execute(
                """UPDATE governance_execution_tasks SET state='verified',worker_id=NULL,lease_token=NULL,
                lease_until=NULL,last_error=NULL,updated_at=clock_timestamp() WHERE instruction_id=%s""",
                (instruction_id,),
            )
            emit(self.store, tx, "execution.primary_verified", updated)
            return instruction_view(updated)

    def reconcile(self, principal, command_key, instruction_id, expected_revision):
        instruction_id = identifier(instruction_id)

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            if row["state"] != "unknown":
                raise GovernanceError("invalid_transition")
            if member["member_id"] != row["approved_by"]:
                raise GovernanceError("independent_review_required")
            task = tx.execute(
                "SELECT * FROM governance_execution_tasks WHERE instruction_id=%s FOR UPDATE",
                (instruction_id,),
            ).fetchone()
            proof = tx.execute(
                "SELECT * FROM governance_execution_outcomes WHERE instruction_id=%s",
                (instruction_id,),
            ).fetchone()
            from pii_redactor.governance.retention import Retention

            Retention(self.store).fence_instruction(tx, row, allow_committed=bool(proof))
            if proof:
                collection = self.collection._scope(tx, member, row["collection_id"])
                self._current_actor(
                    tx,
                    row["proposed_by"],
                    row["proposer_revision"],
                    "execution.propose",
                    collection["department_id"],
                )
                self._current_actor(
                    tx,
                    row["approved_by"],
                    row["approver_revision"],
                    "execution.approve",
                    collection["department_id"],
                )
                if proof["instruction_digest"] != row["instruction_digest"]:
                    raise GovernanceError("instruction_integrity_failure")
                doc = self.collection._document(tx, row["collection_id"], row["document_id"])
                if (
                    doc["last_instruction_id"] != instruction_id
                    or doc["revision"] != proof["result_revision"]
                    or doc["current_version"] != proof["result_version"]
                    or doc["state"] != proof["result_state"]
                ):
                    raise GovernanceError("outcome_reconciliation_required")
                self.collection.check_consent(tx, collection, doc, row["action"])
                actual = tx.execute(
                    "SELECT * FROM governance_document_versions WHERE document_id=%s AND version=%s",
                    (row["document_id"], proof["result_version"]),
                ).fetchone()
                if not actual or actual["ciphertext_digest"] != proof["ciphertext_digest"]:
                    raise GovernanceError("primary_verification_failed")
                from pii_redactor.governance.collections import document_context

                self.collection.protection.open(
                    self.store.organization_id,
                    row["collection_id"],
                    actual,
                    document_context(
                        self.store.organization_id,
                        row["collection_id"],
                        row["document_id"],
                        proof["result_version"],
                        actual["content_type"],
                    ),
                )
                state = "verified"
            else:
                self._recheck(tx, row, approved=True)
                if not task or task["attempts"] >= task["max_attempts"]:
                    raise GovernanceError("attempt_limit_reached")
                state = "pending"
            tx.execute(
                """UPDATE governance_execution_tasks SET state=%s,worker_id=NULL,lease_token=NULL,lease_until=NULL,
                available_at=clock_timestamp(),last_error=NULL,updated_at=clock_timestamp() WHERE instruction_id=%s""",
                (state, instruction_id),
            )
            updated = tx.execute(
                "UPDATE governance_execution_instructions SET state=%s,revision=revision+1 WHERE instruction_id=%s RETURNING *",
                (state, instruction_id),
            ).fetchone()
            return instruction_view(updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "execution.reconcile",
            "execution.reconciled",
            {"id": str(instruction_id), "revision": expected_revision},
            effect,
            scope=lambda tx, member: self._instruction(tx, member, instruction_id),
        )

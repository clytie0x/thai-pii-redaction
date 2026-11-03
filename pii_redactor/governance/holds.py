"""Preservation holds share the managed mutation transaction and lock."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator

from pii_redactor.governance.commands import check_revision, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel, Principal
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.registry import RecordID, _validated

# New evidence records do not change a held primary document/version.
_READ_ONLY = {"read", "list", "snapshot", "get", "preview", "evidence"}
_MUTATIONS = {
    "create",
    "put",
    "correct",
    "suppress",
    "restrict",
    "propose",
    "approve",
    "execute",
    "reconcile",
    "quarantine",
    "restore_quarantine",
    "restore_release",
    "restore_reconcile",
    "release",
}


class HoldInput(ClosedModel):
    collection_id: RecordID
    document_id: RecordID
    expected_revision: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    reason: Literal["legal_preservation", "rights_case", "incident", "review_required"]
    evidence_ref: RecordID
    review_due_at: datetime = Field(strict=False)

    @field_validator("review_due_at")
    @classmethod
    def bounded_review(cls, value):
        if value.tzinfo is None or not datetime.now(UTC) < value <= datetime.now(UTC) + timedelta(
            days=366
        ):
            raise ValueError("review date required")
        return value.astimezone(UTC)


def collection_scope(tx, organization_id, member, collection_id):
    row = tx.execute(
        "SELECT * FROM governance_collections WHERE collection_id=%s AND organization_id=%s FOR UPDATE",
        (identifier(collection_id), organization_id),
    ).fetchone()
    if not row or not in_scope(member, row["department_id"]):
        raise GovernanceError("record_unavailable")
    return row


def target_document(tx, organization_id, collection_id, document_id):
    row = tx.execute(
        "SELECT * FROM governance_managed_documents WHERE document_id=%s AND collection_id=%s AND organization_id=%s FOR UPDATE",
        (identifier(document_id), identifier(collection_id), organization_id),
    ).fetchone()
    if not row:
        raise GovernanceError("record_unavailable")
    return row


def hold_view(row):
    return {
        "id": str(row["hold_id"]),
        "collection_id": str(row["collection_id"]),
        "document_id": str(row["document_id"]),
        "revision": row["revision"],
        "state": row["state"],
        "requested_revision": row["target_revision"],
        "requested_version": row["target_version"],
        "actual_revision": row["actual_revision"],
        "actual_version": row["actual_version"],
        "actual_state": row["actual_state"],
        "reason": row["reason"],
        "evidence_ref": str(row["evidence_ref"]),
        "review_due_at": row["review_due_at"].isoformat(),
        "received_at": row["received_at"].isoformat(),
        "fenced_at": row["fenced_at"].isoformat(),
        "review_status": "reviewed" if row["reviewed_by"] else "pending",
        "review_overdue": row["review_due_at"] <= datetime.now(UTC),
        "urgent_post_action_review": row["post_action"],
        "prior_action_prevented": False,
        "blocks_future_actions": row["state"] != "released",
        "expiry_releases_hold": False,
    }


class Holds:
    def __init__(self, store):
        self.store = store

    def fence(self, tx, *, collection_id, document_id=None, action):
        """Call in every managed transaction, before its first primary mutation."""
        if action not in _READ_ONLY | _MUTATIONS:
            raise GovernanceError("invalid_request")
        self.store.lock(tx)
        row = tx.execute(
            """SELECT hold_id,state FROM governance_holds WHERE organization_id=%s AND collection_id=%s
                         AND (%s::uuid IS NULL OR document_id=%s::uuid)
                         AND state IN ('effective','release_pending','post_action_review') LIMIT 1 FOR SHARE""",
            (
                self.store.organization_id,
                identifier(collection_id),
                identifier(document_id) if document_id else None,
                identifier(document_id) if document_id else None,
            ),
        ).fetchone()
        if row and action in _MUTATIONS:
            raise GovernanceError("hold_effective")
        return {"held": row is not None, "state": row["state"] if row else None}

    def _scope(self, tx, member, hold_id):
        row = tx.execute(
            "SELECT * FROM governance_holds WHERE hold_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(hold_id), self.store.organization_id),
        ).fetchone()
        if not row:
            raise GovernanceError("record_unavailable")
        collection_scope(tx, self.store.organization_id, member, row["collection_id"])
        return row

    def request(self, principal, command_key, request):
        data, received_at = _validated(HoldInput, request), datetime.now(UTC)

        def scope(tx, member):
            collection_scope(tx, self.store.organization_id, member, data.collection_id)
            return target_document(
                tx, self.store.organization_id, data.collection_id, data.document_id
            )

        def effect(tx, member, doc):
            post_action = (
                doc["revision"] != data.expected_revision
                or doc["current_version"] != data.expected_version
                or doc["last_instruction_id"] is not None
            )
            row = tx.execute(
                """INSERT INTO governance_holds(hold_id,organization_id,collection_id,document_id,
                             target_revision,target_version,actual_revision,actual_version,actual_state,state,reason,
                             evidence_ref,review_due_at,received_at,imposed_by,imposer_revision,post_action)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    data.collection_id,
                    data.document_id,
                    data.expected_revision,
                    data.expected_version,
                    doc["revision"],
                    doc["current_version"],
                    doc["state"],
                    "post_action_review" if post_action else "effective",
                    data.reason,
                    data.evidence_ref,
                    data.review_due_at,
                    received_at,
                    member["member_id"],
                    member["revision"],
                    post_action,
                ),
            ).fetchone()
            return hold_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "hold.request",
            "hold.imposed",
            data.model_dump(mode="json"),
            effect,
            scope=scope,
        )

    def review(self, principal, command_key, hold_id, expected_revision, evidence_ref):
        hold_id, evidence_ref = identifier(hold_id), identifier(evidence_ref)

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            if row["state"] not in {"effective", "post_action_review"} or row["reviewed_by"]:
                raise GovernanceError("invalid_transition")
            if row["imposed_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            updated = tx.execute(
                "UPDATE governance_holds SET reviewed_by=%s,review_evidence_ref=%s,revision=revision+1 WHERE hold_id=%s RETURNING *",
                (member["member_id"], evidence_ref, hold_id),
            ).fetchone()
            return hold_view(updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "hold.review",
            "hold.reviewed",
            {"id": str(hold_id), "revision": expected_revision, "evidence_ref": str(evidence_ref)},
            effect,
            scope=lambda tx, m: self._scope(tx, m, hold_id),
        )

    def propose_release(self, principal, command_key, hold_id, expected_revision, evidence_ref):
        hold_id, evidence_ref = identifier(hold_id), identifier(evidence_ref)

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            if row["state"] not in {"effective", "post_action_review"}:
                raise GovernanceError("invalid_transition")
            updated = tx.execute(
                """UPDATE governance_holds SET state='release_pending',release_proposed_by=%s,
                                 release_proposer_revision=%s,release_evidence_ref=%s,revision=revision+1 WHERE hold_id=%s RETURNING *""",
                (member["member_id"], member["revision"], evidence_ref, hold_id),
            ).fetchone()
            return hold_view(updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "hold.release.propose",
            "hold.release_proposed",
            {"id": str(hold_id), "revision": expected_revision, "evidence_ref": str(evidence_ref)},
            effect,
            scope=lambda tx, m: self._scope(tx, m, hold_id),
        )

    def release(self, principal, command_key, hold_id, expected_revision, evidence_ref):
        hold_id, evidence_ref = identifier(hold_id), identifier(evidence_ref)

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            if row["state"] != "release_pending":
                raise GovernanceError("invalid_transition")
            if row["release_proposed_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            proposer = tx.execute(
                "SELECT * FROM governance_members WHERE member_id=%s AND organization_id=%s FOR SHARE",
                (row["release_proposed_by"], self.store.organization_id),
            ).fetchone()
            if not proposer or proposer["revision"] != row["release_proposer_revision"]:
                raise GovernanceError("proposal_authority_expired")
            bucket = collection_scope(tx, self.store.organization_id, member, row["collection_id"])
            require_member(
                tx,
                self.store.organization_id,
                Principal(issuer=proposer["issuer"], subject=proposer["subject"]),
                "hold.release.propose",
                bucket["department_id"],
            )
            updated = tx.execute(
                "UPDATE governance_holds SET state='released',released_by=%s,release_review_ref=%s,released_at=clock_timestamp(),revision=revision+1 WHERE hold_id=%s RETURNING *",
                (member["member_id"], evidence_ref, hold_id),
            ).fetchone()
            return hold_view(updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "hold.release.review",
            "hold.released",
            {"id": str(hold_id), "revision": expected_revision, "evidence_ref": str(evidence_ref)},
            effect,
            scope=lambda tx, m: self._scope(tx, m, hold_id),
        )

    def list(self, principal, collection_id, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "hold.read")
            collection_scope(tx, self.store.organization_id, member, collection_id)
            rows = tx.execute(
                """SELECT * FROM governance_holds WHERE organization_id=%s AND collection_id=%s
                              AND (%s::uuid IS NULL OR hold_id>%s::uuid) ORDER BY hold_id LIMIT %s""",
                (
                    self.store.organization_id,
                    identifier(collection_id),
                    identifier(cursor) if cursor else None,
                    identifier(cursor) if cursor else None,
                    limit + 1,
                ),
            ).fetchall()
            items = [hold_view(r) for r in rows[:limit]]
            return {"items": items, "next_cursor": items[-1]["id"] if len(rows) > limit else None}

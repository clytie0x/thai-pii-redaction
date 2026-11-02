"""Reviewed due policies and reversible disposition, with copy obligations."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, field_validator, model_validator

from pii_redactor.governance.commands import check_revision, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.holds import Holds, collection_scope, target_document
from pii_redactor.governance.models import ClosedModel, Principal
from pii_redactor.governance.permissions import require_member
from pii_redactor.governance.registry import RecordID, _validated

CopyKind = Literal["derived", "processor", "replica_wal", "backup", "physical_storage"]
_COPY_KINDS = {"derived", "processor", "replica_wal", "backup", "physical_storage"}


class CopyRule(ClosedModel):
    kind: CopyKind
    recipient_ref: RecordID
    applicability: Literal["required", "not_applicable"]
    evidence_ref: RecordID | None = None

    @model_validator(mode="after")
    def applicability_evidence(self):
        if self.applicability == "not_applicable" and self.evidence_ref is None:
            raise ValueError("applicability evidence required")
        return self


class PolicyInput(ClosedModel):
    collection_id: RecordID
    purpose_version: RecordID
    trigger_kind: Literal["record_closed", "received", "reviewed_event"]
    delay_days: int = Field(ge=0, le=36500)
    action: Literal["restrict", "suppress"]
    policy_evidence_ref: RecordID
    restriction_evidence_ref: RecordID
    copies: list[CopyRule] = Field(min_length=5, max_length=64)

    @model_validator(mode="after")
    def complete_inventory(self):
        keys = [(r.kind, r.recipient_ref) for r in self.copies]
        if {r.kind for r in self.copies} != _COPY_KINDS or len(keys) != len(set(keys)):
            raise ValueError("complete distinct copy inventory required")
        return self


class TriggerInput(ClosedModel):
    policy_id: RecordID
    document_id: RecordID
    expected_revision: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    occurred_at: datetime = Field(strict=False)
    evidence_ref: RecordID

    @field_validator("occurred_at")
    @classmethod
    def actual_receipt(cls, value):
        if value.tzinfo is None or value > datetime.now(UTC):
            raise ValueError("actual trigger time required")
        return value.astimezone(UTC)


def _policy_view(row):
    return {
        "id": str(row["policy_id"]),
        "collection_id": str(row["collection_id"]),
        "purpose_version": str(row["purpose_version"]),
        "revision": row["revision"],
        "state": row["state"],
        "data": row["data"],
        "evidence_mode": "reviewer_attested_external",
        "physical_erasure_supported": False,
    }


def _due_view(row):
    return {
        "id": str(row["due_id"]),
        "policy_id": str(row["policy_id"]),
        "policy_revision": row["policy_revision"],
        "collection_id": str(row["collection_id"]),
        "document_id": str(row["document_id"]),
        "target_revision": row["target_revision"],
        "target_version": row["target_version"],
        "revision": row["revision"],
        "state": row["state"],
        "due_at": row["due_at"].isoformat(),
        "instruction_id": str(row["instruction_id"]) if row["instruction_id"] else None,
        "primary_erased": False,
        "all_copies_erased": False,
    }


class Retention:
    def __init__(self, store, *, execution=None):
        self.store, self.execution = store, execution

    def _policy(self, tx, member, policy_id):
        row = tx.execute(
            "SELECT * FROM governance_retention_policies WHERE policy_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(policy_id), self.store.organization_id),
        ).fetchone()
        if not row:
            raise GovernanceError("record_unavailable")
        bucket = collection_scope(tx, self.store.organization_id, member, row["collection_id"])
        return row, bucket

    def _active_policy(self, tx, row, bucket):
        activity = tx.execute(
            "SELECT * FROM governance_activities WHERE activity_id=%s AND organization_id=%s FOR SHARE",
            (bucket["activity_id"], self.store.organization_id),
        ).fetchone()
        if (
            row["state"] != "active"
            or not activity
            or activity["state"] != "active"
            or activity["revision"] != row["activity_revision"]
            or bucket["activity_revision"] != row["activity_revision"]
            or activity["review"].get("notice_id") != str(row["purpose_version"])
        ):
            raise GovernanceError("retention_authority_changed")
        return activity

    def _actor(self, tx, member_id, revision, permission, department):
        actor = tx.execute(
            "SELECT * FROM governance_members WHERE member_id=%s AND organization_id=%s FOR SHARE",
            (member_id, self.store.organization_id),
        ).fetchone()
        if not actor or actor["revision"] != revision:
            raise GovernanceError("approval_authority_changed")
        return require_member(
            tx,
            self.store.organization_id,
            Principal(issuer=actor["issuer"], subject=actor["subject"]),
            permission,
            department,
        )

    def propose_policy(self, principal, command_key, request):
        data = _validated(PolicyInput, request)

        def scope(tx, member):
            bucket = collection_scope(tx, self.store.organization_id, member, data.collection_id)
            activity = tx.execute(
                "SELECT * FROM governance_activities WHERE activity_id=%s FOR SHARE",
                (bucket["activity_id"],),
            ).fetchone()
            if (
                not activity
                or activity["state"] != "active"
                or activity["revision"] != bucket["activity_revision"]
                or activity["review"].get("notice_id") != str(data.purpose_version)
            ):
                raise GovernanceError("retention_authority_changed")
            return bucket, activity["data"]["purpose"]

        def effect(tx, member, scoped):
            bucket, purpose_snapshot = scoped
            row = tx.execute(
                """INSERT INTO governance_retention_policies(policy_id,organization_id,collection_id,purpose_version,
                              activity_revision,data,proposed_by,proposer_revision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    data.collection_id,
                    data.purpose_version,
                    bucket["activity_revision"],
                    Jsonb({**data.model_dump(mode="json"), "purpose_snapshot": purpose_snapshot}),
                    member["member_id"],
                    member["revision"],
                ),
            ).fetchone()
            return _policy_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "retention.propose",
            "retention.policy_proposed",
            data.model_dump(mode="json"),
            effect,
            scope=scope,
        )

    def review_policy(
        self, principal, command_key, policy_id, expected_revision, decision, evidence_ref
    ):
        policy_id, evidence_ref = identifier(policy_id), identifier(evidence_ref)
        if decision not in {"approve", "reject"}:
            raise GovernanceError("invalid_request")

        def effect(tx, member, scoped):
            row, bucket = scoped
            check_revision(row, expected_revision)
            if row["state"] != "proposed":
                raise GovernanceError("invalid_transition")
            if row["proposed_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            self._actor(
                tx,
                row["proposed_by"],
                row["proposer_revision"],
                "retention.propose",
                bucket["department_id"],
            )
            if decision == "approve":
                self._active_policy(tx, {**row, "state": "active"}, bucket)
                tx.execute(
                    "UPDATE governance_retention_policies SET state='superseded',revision=revision+1 WHERE collection_id=%s AND state='active'",
                    (bucket["collection_id"],),
                )
            updated = tx.execute(
                """UPDATE governance_retention_policies SET state=%s,reviewed_by=%s,reviewer_revision=%s,
                                  review_evidence_ref=%s,revision=revision+1 WHERE policy_id=%s RETURNING *""",
                (
                    "active" if decision == "approve" else "rejected",
                    member["member_id"],
                    member["revision"],
                    evidence_ref,
                    policy_id,
                ),
            ).fetchone()
            return _policy_view(updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "retention.review",
            "retention.policy_reviewed",
            {
                "id": str(policy_id),
                "revision": expected_revision,
                "decision": decision,
                "evidence_ref": str(evidence_ref),
            },
            effect,
            scope=lambda tx, m: self._policy(tx, m, policy_id),
        )

    def record_trigger(self, principal, command_key, request):
        data = _validated(TriggerInput, request)

        def scope(tx, member):
            policy, bucket = self._policy(tx, member, data.policy_id)
            self._active_policy(tx, policy, bucket)
            doc = target_document(
                tx, self.store.organization_id, bucket["collection_id"], data.document_id
            )
            check_revision(doc, data.expected_revision)
            if doc["current_version"] != data.expected_version:
                raise GovernanceError("revision_conflict")
            return policy

        def effect(tx, member, _policy):
            row = tx.execute(
                """INSERT INTO governance_retention_triggers(trigger_id,policy_id,document_id,target_revision,target_version,
                              occurred_at,evidence_ref,proposed_by,proposer_revision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    data.policy_id,
                    data.document_id,
                    data.expected_revision,
                    data.expected_version,
                    data.occurred_at,
                    data.evidence_ref,
                    member["member_id"],
                    member["revision"],
                ),
            ).fetchone()
            return {"id": str(row["trigger_id"]), "revision": 1, "state": "proposed"}

        return run_command(
            self.store,
            principal,
            command_key,
            "retention.trigger",
            "retention.trigger_proposed",
            data.model_dump(mode="json"),
            effect,
            scope=scope,
        )

    def review_trigger(self, principal, command_key, trigger_id, expected_revision, evidence_ref):
        trigger_id, evidence_ref = identifier(trigger_id), identifier(evidence_ref)

        def scope(tx, member):
            row = tx.execute(
                "SELECT * FROM governance_retention_triggers WHERE trigger_id=%s FOR UPDATE",
                (trigger_id,),
            ).fetchone()
            if not row:
                raise GovernanceError("record_unavailable")
            policy, bucket = self._policy(tx, member, row["policy_id"])
            self._active_policy(tx, policy, bucket)
            return row, bucket

        def effect(tx, member, scoped):
            row, bucket = scoped
            check_revision(row, expected_revision)
            if row["state"] != "proposed":
                raise GovernanceError("invalid_transition")
            if row["proposed_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            self._actor(
                tx,
                row["proposed_by"],
                row["proposer_revision"],
                "retention.trigger",
                bucket["department_id"],
            )
            doc = target_document(
                tx, self.store.organization_id, bucket["collection_id"], row["document_id"]
            )
            if (
                doc["revision"] != row["target_revision"]
                or doc["current_version"] != row["target_version"]
            ):
                raise GovernanceError("revision_conflict")
            tx.execute(
                "UPDATE governance_retention_triggers SET state='active',reviewed_by=%s,reviewer_revision=%s,review_evidence_ref=%s,revision=revision+1 WHERE trigger_id=%s",
                (member["member_id"], member["revision"], evidence_ref, trigger_id),
            )
            return {"id": str(trigger_id), "revision": expected_revision + 1, "state": "active"}

        return run_command(
            self.store,
            principal,
            command_key,
            "retention.trigger.review",
            "retention.trigger_reviewed",
            {
                "id": str(trigger_id),
                "revision": expected_revision,
                "evidence_ref": str(evidence_ref),
            },
            effect,
            scope=scope,
        )

    def propose_due(self, as_of, *, limit=100, principal=None, collection_id=None):
        if (
            not isinstance(as_of, datetime)
            or as_of.tzinfo is None
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            if principal is not None:
                if collection_id is None:
                    raise GovernanceError("forbidden")
                member = require_member(
                    tx, self.store.organization_id, principal, "retention.trigger"
                )
                collection_scope(tx, self.store.organization_id, member, collection_id)
            now = tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if as_of > now:
                raise GovernanceError("invalid_request")
            rows = tx.execute(
                """SELECT t.*,p.collection_id,p.revision AS policy_revision,p.data FROM governance_retention_triggers t
                              JOIN governance_retention_policies p ON p.policy_id=t.policy_id
                              JOIN governance_managed_documents d ON d.document_id=t.document_id
                              WHERE p.organization_id=%s AND (%s::uuid IS NULL OR p.collection_id=%s::uuid)
                              AND p.state='active' AND t.state='active'
                              AND d.revision=t.target_revision AND d.current_version=t.target_version
                              AND t.occurred_at+(p.data->>'delay_days')::integer*interval '1 day'<=%s
                              AND NOT EXISTS(SELECT 1 FROM governance_retention_due due WHERE due.trigger_id=t.trigger_id)
                              ORDER BY t.occurred_at,t.trigger_id LIMIT %s FOR UPDATE OF t,p,d""",
                (
                    self.store.organization_id,
                    identifier(collection_id) if collection_id else None,
                    identifier(collection_id) if collection_id else None,
                    as_of,
                    limit,
                ),
            ).fetchall()
            results = []
            for row in rows:
                due = tx.execute(
                    """INSERT INTO governance_retention_due(due_id,policy_id,policy_revision,trigger_id,trigger_revision,
                                  collection_id,document_id,target_revision,target_version,due_at)
                                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (
                        uuid4(),
                        row["policy_id"],
                        row["policy_revision"],
                        row["trigger_id"],
                        row["revision"],
                        row["collection_id"],
                        row["document_id"],
                        row["target_revision"],
                        row["target_version"],
                        row["occurred_at"] + timedelta(days=row["data"]["delay_days"]),
                    ),
                ).fetchone()
                for copy in row["data"]["copies"]:
                    tx.execute(
                        """INSERT INTO governance_retention_copies(obligation_id,due_id,kind,recipient_ref,state,evidence_ref)
                                  VALUES (%s,%s,%s,%s,%s,%s)""",
                        (
                            uuid4(),
                            due["due_id"],
                            copy["kind"],
                            identifier(copy["recipient_ref"]),
                            "not_applicable"
                            if copy["applicability"] == "not_applicable"
                            else "pending",
                            identifier(copy["evidence_ref"]) if copy.get("evidence_ref") else None,
                        ),
                    )
                eid = self.store.append_event(
                    tx, event_code="retention.due_proposed", target_id=due["due_id"], revision=1
                )
                tx.execute(
                    "INSERT INTO governance_outbox(event_id,event_code,payload) VALUES (%s,%s,%s)",
                    (
                        eid,
                        "retention.due_proposed",
                        Jsonb({"record_id": str(due["due_id"]), "revision": 1}),
                    ),
                )
                results.append(_due_view(due))
            return results

    def get_trigger(self, principal, trigger_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            row = tx.execute(
                "SELECT * FROM governance_retention_triggers WHERE trigger_id=%s",
                (identifier(trigger_id),),
            ).fetchone()
            if not row:
                raise GovernanceError("record_unavailable")
            self._policy(tx, member, row["policy_id"])
            return {
                "id": str(row["trigger_id"]),
                "revision": row["revision"],
                "state": row["state"],
                "policy_id": str(row["policy_id"]),
                "document_id": str(row["document_id"]),
                "target_revision": row["target_revision"],
                "target_version": row["target_version"],
                "occurred_at": row["occurred_at"].isoformat(),
                "evidence_ref": str(row["evidence_ref"]),
            }

    def _due(self, tx, member, due_id):
        row = tx.execute(
            "SELECT * FROM governance_retention_due WHERE due_id=%s FOR UPDATE",
            (identifier(due_id),),
        ).fetchone()
        if not row:
            raise GovernanceError("record_unavailable")
        policy, bucket = self._policy(tx, member, row["policy_id"])
        return row, policy, bucket

    def _current_due(self, tx, row, policy, bucket, *, check_target=True, approved=False):
        self._active_policy(tx, policy, bucket)
        trigger = tx.execute(
            "SELECT * FROM governance_retention_triggers WHERE trigger_id=%s FOR SHARE",
            (row["trigger_id"],),
        ).fetchone()
        if (
            policy["revision"] != row["policy_revision"]
            or not trigger
            or trigger["state"] != "active"
            or trigger["revision"] != row["trigger_revision"]
        ):
            raise GovernanceError("retention_authority_changed")
        self._actor(
            tx,
            policy["reviewed_by"],
            policy["reviewer_revision"],
            "retention.review",
            bucket["department_id"],
        )
        self._actor(
            tx,
            trigger["reviewed_by"],
            trigger["reviewer_revision"],
            "retention.trigger.review",
            bucket["department_id"],
        )
        doc = target_document(
            tx, self.store.organization_id, bucket["collection_id"], row["document_id"]
        )
        if check_target and (
            doc["revision"] != row["target_revision"]
            or doc["current_version"] != row["target_version"]
        ):
            raise GovernanceError("revision_conflict")
        if approved:
            now = tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if (
                row["state"] not in {"approved", "issued"}
                or not row["approval_expires_at"]
                or row["approval_expires_at"] <= now
            ):
                raise GovernanceError("approval_expired")
            self._actor(
                tx,
                row["reviewed_by"],
                row["reviewer_revision"],
                "retention.review",
                bucket["department_id"],
            )
        return trigger, doc

    def approve_due(self, principal, command_key, due_id, expected_revision, evidence_ref):
        due_id, evidence_ref = identifier(due_id), identifier(evidence_ref)

        def effect(tx, member, scoped):
            row, policy, bucket = scoped
            check_revision(row, expected_revision)
            if row["state"] != "proposed":
                raise GovernanceError("invalid_transition")
            trigger, _doc = self._current_due(tx, row, policy, bucket)
            if member["member_id"] in {policy["proposed_by"], trigger["proposed_by"]}:
                raise GovernanceError("separation_required")
            Holds(self.store).fence(
                tx,
                collection_id=bucket["collection_id"],
                document_id=row["document_id"],
                action="approve",
            )
            updated = tx.execute(
                """UPDATE governance_retention_due SET state='approved',reviewed_by=%s,reviewer_revision=%s,
                                review_evidence_ref=%s,approval_expires_at=clock_timestamp()+interval '24 hours',revision=revision+1
                                WHERE due_id=%s RETURNING *""",
                (member["member_id"], member["revision"], evidence_ref, due_id),
            ).fetchone()
            return _due_view(updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "retention.review",
            "retention.due_approved",
            {"id": str(due_id), "revision": expected_revision, "evidence_ref": str(evidence_ref)},
            effect,
            scope=lambda tx, m: self._due(tx, m, due_id),
        )

    def issue_instruction(self, principal, command_key, due_id, expected_revision):
        from pii_redactor.governance.execution import InstructionInput, instruction_digest

        due_id = identifier(due_id)

        def effect(tx, member, scoped):
            row, policy, bucket = scoped
            check_revision(row, expected_revision)
            if row["state"] != "approved":
                raise GovernanceError("invalid_transition")
            _trigger, doc = self._current_due(tx, row, policy, bucket, approved=True)
            if member["member_id"] == row["reviewed_by"]:
                raise GovernanceError("separation_required")
            require_member(
                tx,
                self.store.organization_id,
                principal,
                "execution.propose",
                bucket["department_id"],
            )
            self._actor(
                tx,
                row["reviewed_by"],
                row["reviewer_revision"],
                "execution.approve",
                bucket["department_id"],
            )
            Holds(self.store).fence(
                tx,
                collection_id=bucket["collection_id"],
                document_id=row["document_id"],
                action="propose",
            )
            if self.execution is None:
                raise GovernanceError("execution_unavailable")
            self.execution.collection._scope(tx, member, bucket["collection_id"])
            self.execution.collection.check_consent(tx, bucket, doc, policy["data"]["action"])
            data = InstructionInput(
                collection_id=bucket["collection_id"],
                document_id=row["document_id"],
                expected_revision=row["target_revision"],
                expected_version=row["target_version"],
                action=policy["data"]["action"],
                expires_at=row["approval_expires_at"],
            )
            iid = uuid4()
            tx.execute(
                """INSERT INTO governance_execution_instructions(instruction_id,organization_id,collection_id,document_id,
                          target_revision,target_version,action,expires_at,instruction_digest,proposed_by,proposer_revision,
                          approved_by,approver_revision,state,revision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',2)""",
                (
                    iid,
                    self.store.organization_id,
                    bucket["collection_id"],
                    row["document_id"],
                    row["target_revision"],
                    row["target_version"],
                    data.action,
                    data.expires_at,
                    instruction_digest(data),
                    member["member_id"],
                    member["revision"],
                    row["reviewed_by"],
                    row["reviewer_revision"],
                ),
            )
            tx.execute("INSERT INTO governance_execution_tasks(instruction_id) VALUES (%s)", (iid,))
            tx.execute(
                "INSERT INTO governance_retention_instruction_links(instruction_id,due_id) VALUES (%s,%s)",
                (iid, due_id),
            )
            tx.execute(
                "UPDATE governance_retention_due SET state='issued',instruction_id=%s,revision=revision+1 WHERE due_id=%s",
                (iid, due_id),
            )
            return {
                "id": str(iid),
                "revision": 2,
                "state": "pending",
                "due_id": str(due_id),
                "physical_erasure_supported": False,
            }

        return run_command(
            self.store,
            principal,
            command_key,
            "retention.issue",
            "retention.instruction_issued",
            {"id": str(due_id), "revision": expected_revision},
            effect,
            scope=lambda tx, m: self._due(tx, m, due_id),
        )

    def fence_instruction(self, tx, instruction, *, allow_committed=False):
        if type(allow_committed) is not bool:
            raise GovernanceError("invalid_request")
        self.store.lock(tx)
        link = tx.execute(
            "SELECT due_id FROM governance_retention_instruction_links WHERE instruction_id=%s",
            (instruction["instruction_id"],),
        ).fetchone()
        if not link:
            return
        row = tx.execute(
            "SELECT * FROM governance_retention_due WHERE due_id=%s FOR SHARE", (link["due_id"],)
        ).fetchone()
        policy = tx.execute(
            "SELECT * FROM governance_retention_policies WHERE policy_id=%s FOR SHARE",
            (row["policy_id"],),
        ).fetchone()
        bucket = tx.execute(
            "SELECT * FROM governance_collections WHERE collection_id=%s AND organization_id=%s FOR UPDATE",
            (row["collection_id"], self.store.organization_id),
        ).fetchone()
        if (
            not bucket
            or row["state"] != "issued"
            or row["instruction_id"] != instruction["instruction_id"]
            or instruction["document_id"] != row["document_id"]
            or instruction["target_revision"] != row["target_revision"]
            or instruction["target_version"] != row["target_version"]
            or instruction["action"] != policy["data"]["action"]
            or instruction["approved_by"] != row["reviewed_by"]
            or instruction["approver_revision"] != row["reviewer_revision"]
            or instruction["expires_at"] != row["approval_expires_at"]
        ):
            raise GovernanceError("retention_authority_changed")
        self._current_due(tx, row, policy, bucket, check_target=not allow_committed, approved=True)
        if allow_committed:
            outcome = tx.execute(
                "SELECT * FROM governance_execution_outcomes WHERE instruction_id=%s",
                (instruction["instruction_id"],),
            ).fetchone()
            if (
                not outcome
                or outcome["document_id"] != row["document_id"]
                or outcome["result_version"] != row["target_version"]
            ):
                raise GovernanceError("retention_outcome_unverified")

    def list_policies(self, principal, collection_id, *, limit=50, cursor=None):
        return self._list(principal, collection_id, "policies", limit, cursor)

    def list_due(self, principal, collection_id, *, limit=50, cursor=None):
        return self._list(principal, collection_id, "due", limit, cursor)

    def get_due(self, principal, due_id):
        """Return the exact action and reviewed sources before a staff decision."""
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            row, policy, bucket = self._due(tx, member, due_id)
            trigger = tx.execute(
                "SELECT * FROM governance_retention_triggers WHERE trigger_id=%s AND policy_id=%s",
                (row["trigger_id"], policy["policy_id"]),
            ).fetchone()
            activity = tx.execute(
                "SELECT data,revision FROM governance_activities WHERE activity_id=%s AND organization_id=%s",
                (bucket["activity_id"], self.store.organization_id),
            ).fetchone()
            if not trigger or not activity:
                raise GovernanceError("record_unavailable")
            purpose = policy["data"].get("purpose_snapshot")
            if purpose is None and activity["revision"] == policy["activity_revision"]:
                purpose = activity["data"]["purpose"]
            blocked_reason = None
            try:
                self._current_due(tx, row, policy, bucket, approved=row["state"] == "approved")
                held = Holds(self.store).fence(
                    tx,
                    collection_id=bucket["collection_id"],
                    document_id=row["document_id"],
                    action="preview",
                )
                if held["held"]:
                    blocked_reason = "hold_effective"
            except GovernanceError as error:
                blocked_reason = error.code
            if purpose is None:
                blocked_reason = "retention_authority_changed"

            def allowed(permission):
                try:
                    require_member(
                        tx,
                        self.store.organization_id,
                        principal,
                        permission,
                        bucket["department_id"],
                    )
                    return True
                except GovernanceError as error:
                    if error.code != "forbidden":
                        raise
                    return False

            can_approve = (
                blocked_reason is None
                and row["state"] == "proposed"
                and allowed("retention.review")
                and member["member_id"] not in {policy["proposed_by"], trigger["proposed_by"]}
            )
            can_issue = (
                blocked_reason is None
                and row["state"] == "approved"
                and allowed("retention.issue")
                and allowed("execution.propose")
                and member["member_id"] != row["reviewed_by"]
            )
            return {
                **_due_view(row),
                "action": policy["data"]["action"],
                "purpose_version": str(policy["purpose_version"]),
                "purpose": purpose or "",
                "activity_id": str(bucket["activity_id"]),
                "activity_revision": policy["activity_revision"],
                "policy": {
                    "id": str(policy["policy_id"]),
                    "bound_revision": row["policy_revision"],
                    "current_revision": policy["revision"],
                    "state": policy["state"],
                    "source_evidence_ref": policy["data"]["policy_evidence_ref"],
                    "restriction_evidence_ref": policy["data"]["restriction_evidence_ref"],
                    "review_evidence_ref": str(policy["review_evidence_ref"])
                    if policy["review_evidence_ref"]
                    else None,
                },
                "trigger": {
                    "id": str(trigger["trigger_id"]),
                    "bound_revision": row["trigger_revision"],
                    "current_revision": trigger["revision"],
                    "state": trigger["state"],
                    "kind": policy["data"]["trigger_kind"],
                    "occurred_at": trigger["occurred_at"].isoformat(),
                    "source_evidence_ref": str(trigger["evidence_ref"]),
                    "review_evidence_ref": str(trigger["review_evidence_ref"])
                    if trigger["review_evidence_ref"]
                    else None,
                },
                "approval_expires_at": row["approval_expires_at"].isoformat()
                if row["approval_expires_at"]
                else None,
                "approval_window_hours": 24,
                "can_approve": can_approve,
                "can_issue": can_issue,
                "blocked_reason": blocked_reason,
            }

    def _list(self, principal, collection_id, kind, limit, cursor):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GovernanceError("invalid_request")
        table, column, view = (
            ("governance_retention_policies", "policy_id", _policy_view)
            if kind == "policies"
            else ("governance_retention_due", "due_id", _due_view)
        )
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            collection_scope(tx, self.store.organization_id, member, collection_id)
            rows = tx.execute(
                f"SELECT * FROM {table} WHERE collection_id=%s AND (%s::uuid IS NULL OR {column}>%s::uuid) ORDER BY {column} LIMIT %s",
                (
                    identifier(collection_id),
                    identifier(cursor) if cursor else None,
                    identifier(cursor) if cursor else None,
                    limit + 1,
                ),
            ).fetchall()
            items = [view(r) for r in rows[:limit]]
            return {"items": items, "next_cursor": items[-1]["id"] if len(rows) > limit else None}

    def disposition(self, principal, due_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            row, _policy, _bucket = self._due(tx, member, due_id)
            outcome = (
                tx.execute(
                    "SELECT result_state,result_version,result_revision,verified_at FROM governance_execution_outcomes WHERE instruction_id=%s",
                    (row["instruction_id"],),
                ).fetchone()
                if row["instruction_id"]
                else None
            )
            current = target_document(
                tx, self.store.organization_id, row["collection_id"], row["document_id"]
            )
            current_matches = bool(
                outcome
                and current["last_instruction_id"] == row["instruction_id"]
                and current["revision"] == outcome["result_revision"]
                and current["current_version"] == outcome["result_version"]
                and current["state"] == outcome["result_state"]
            )
            copies = tx.execute(
                "SELECT * FROM governance_retention_copies WHERE due_id=%s ORDER BY kind,obligation_id",
                (row["due_id"],),
            ).fetchall()
            return {
                **_due_view(row),
                "primary": {
                    "state": outcome["result_state"]
                    if current_matches
                    else "changed_after_action"
                    if outcome
                    else "pending",
                    "verification": "managed_primary_logical_only"
                    if current_matches
                    else "unverified_after_target_change"
                    if outcome
                    else "unverified",
                    "physical_erasure": False,
                },
                "copies": [
                    {
                        "id": str(c["obligation_id"]),
                        "kind": c["kind"],
                        "recipient_ref": str(c["recipient_ref"]),
                        "revision": c["revision"],
                        "state": c["state"],
                        "evidence_mode": "reviewer_attested_external"
                        if c["state"] in {"verified", "not_applicable"}
                        else "pending_evidence",
                    }
                    for c in copies
                ],
                "overall_state": "partial_logical_disposition"
                if current_matches
                else "unresolved_target_change"
                if outcome
                else "pending",
                "all_copies_erased": False,
                "immutable_versions_retained": True,
            }

    def review_copy(
        self, principal, command_key, obligation_id, expected_revision, state, evidence_ref
    ):
        obligation_id, evidence_ref = identifier(obligation_id), identifier(evidence_ref)
        if state not in {"failed", "verified"}:
            raise GovernanceError("invalid_request")

        def scope(tx, member):
            row = tx.execute(
                "SELECT * FROM governance_retention_copies WHERE obligation_id=%s FOR UPDATE",
                (obligation_id,),
            ).fetchone()
            if not row:
                raise GovernanceError("record_unavailable")
            self._due(tx, member, row["due_id"])
            return row

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            if row["state"] in {"verified", "not_applicable"}:
                raise GovernanceError("invalid_transition")
            tx.execute(
                "UPDATE governance_retention_copies SET state=%s,evidence_ref=%s,reviewed_by=%s,reviewed_at=clock_timestamp(),revision=revision+1 WHERE obligation_id=%s",
                (state, evidence_ref, member["member_id"], obligation_id),
            )
            return {
                "id": str(obligation_id),
                "revision": expected_revision + 1,
                "state": state,
                "evidence_mode": "reviewer_attested_external",
            }

        return run_command(
            self.store,
            principal,
            command_key,
            "retention.obligation.review",
            "retention.copy_reviewed",
            {
                "id": str(obligation_id),
                "revision": expected_revision,
                "state": state,
                "evidence_ref": str(evidence_ref),
            },
            effect,
            scope=scope,
        )

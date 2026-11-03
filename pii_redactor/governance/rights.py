"""Reviewed rights cases. Advice, dispatch and primary removal are not fulfilment."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from psycopg import sql
from psycopg.types.json import Jsonb
from pydantic import Field, model_validator

from pii_redactor.governance.commands import check_revision, digest, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel, Department, Principal
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.registry import RecordID, _validated
from pii_redactor.governance.subjects import require_subject_actor

Right = Literal[
    "access", "rectification", "restriction", "erasure", "portability", "objection", "withdrawal"
]
# Parent wiring can expose these action names without broadening existing roles.
RIGHTS_ACTION_MAP = {
    "rights.receive": "subject.propose",
    "rights.plan": "subject.propose",
    "rights.read": "subject.read",
    "rights.verify": "consent.offline.review",
    "rights.review": "consent.offline.review",
    "rights.close": "consent.offline.review",
    "rights.manual.submit": "subject.propose",
    "rights.manual.review": "consent.offline.review",
    "rights.reopen": "subject.propose",
    "rights.withdraw": "subject.propose",
    "delivery.issue": "subject.propose",
    "delivery.revoke": "subject.propose",
}
RIGHTS_ROLES = {
    action: {"privacy_reviewer"}
    if action in {"rights.verify", "rights.review", "rights.close", "rights.manual.review"}
    else {"case_manager", "privacy_reviewer"}
    if action == "rights.read"
    else {"case_manager"}
    for action in RIGHTS_ACTION_MAP
}


def require_rights_role(member, action):
    if not RIGHTS_ROLES[action].intersection(member["roles"]):
        raise GovernanceError("forbidden")


def aware(value):
    if value.tzinfo is None:
        raise GovernanceError("invalid_request")
    return value.astimezone(UTC)


class Intake(ClosedModel):
    department_id: Department
    subject_id: RecordID | None = None
    received_at: datetime = Field(strict=False)
    channel: Literal["offline", "email", "post", "in_person", "portal"]
    original_receipt_ref: RecordID
    requester: Literal["subject", "representative"]
    rights: list[Right] = Field(min_length=1, max_length=7)

    @model_validator(mode="after")
    def original(self):
        if self.department_id == "*" or len(set(self.rights)) != len(self.rights):
            raise ValueError("concrete scope required")
        if self.received_at.tzinfo is None or self.received_at > datetime.now(UTC):
            raise ValueError("original receipt required")
        return self


class ClockReview(ClosedModel):
    right: Right
    applicability: Literal["applicable", "not_applicable", "unknown"]
    law_version: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}$")
    source_ref: RecordID
    rationale_ref: RecordID
    anchor: Literal["original_receipt", "complete_receipt", "reviewed_event"]
    due_at: datetime | None = Field(default=None, strict=False)
    extension_until: datetime | None = Field(default=None, strict=False)
    extension_ref: RecordID | None = None
    extension_notice_ref: RecordID | None = None

    @model_validator(mode="after")
    def chronology(self):
        for value in (self.due_at, self.extension_until):
            if value is not None and value.tzinfo is None:
                raise ValueError("timezone required")
        if self.extension_until is not None and (
            self.due_at is None
            or self.extension_until <= self.due_at
            or not self.extension_ref
            or not self.extension_notice_ref
        ):
            raise ValueError("reviewed extension and notice required")
        return self


class Verification(ClosedModel):
    subject_id: RecordID
    link_revision: int = Field(ge=1)
    complete: bool
    completeness_ref: RecordID
    complete_at: datetime | None = Field(default=None, strict=False)
    identity_ref: RecordID
    capacity_ref: RecordID
    representative_ref: RecordID | None = None
    recipient_subject_id: RecordID | None = None
    recipient_link_revision: int | None = Field(default=None, ge=1)
    clocks: list[ClockReview] = Field(min_length=1, max_length=7)


class Target(ClosedModel):
    right: Right
    collection_id: RecordID
    document_id: RecordID
    target_revision: int = Field(ge=1)
    target_version: int = Field(ge=1)
    scope_evidence_ref: RecordID
    export_evidence_id: RecordID | None = None
    third_party_review_ref: RecordID | None = None
    instruction_id: RecordID | None = None

    @model_validator(mode="after")
    def supported(self):
        if self.right in {"access", "portability"}:
            if (
                not self.export_evidence_id
                or not self.third_party_review_ref
                or self.instruction_id
            ):
                raise ValueError("reviewed redacted export required")
        elif self.right in {"rectification", "restriction", "erasure"}:
            if not self.instruction_id or self.export_evidence_id:
                raise ValueError("bounded execution required")
        else:
            raise ValueError("manual obligation required")
        return self


class ManualTask(ClosedModel):
    right: Right
    kind: Literal[
        "external", "derived", "processor", "replica_wal", "backup", "physical_storage", "notice"
    ]
    system_ref: RecordID
    owner_id: RecordID
    scope_evidence_ref: RecordID


class Refusal(ClosedModel):
    right: Right
    reason_ref: RecordID
    source_ref: RecordID
    law_version: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}$")
    notification_outcome_ref: RecordID


class FulfilmentPlan(ClosedModel):
    targets: list[Target] = Field(default_factory=list, max_length=50)
    manual: list[ManualTask] = Field(default_factory=list, max_length=100)
    refusals: list[Refusal] = Field(default_factory=list, max_length=7)
    expires_at: datetime = Field(strict=False)

    @model_validator(mode="after")
    def bounded(self):
        if self.expires_at.tzinfo is None or not datetime.now(
            UTC
        ) < self.expires_at <= datetime.now(UTC) + timedelta(hours=24):
            raise ValueError("bounded authority required")
        keys = [(t.right, str(t.document_id)) for t in self.targets]
        if len(set(keys)) != len(keys) or not (self.targets or self.manual or self.refusals):
            raise ValueError("distinct obligations required")
        refused = [r.right for r in self.refusals]
        active = {r.right for r in [*self.targets, *self.manual]}
        if len(set(refused)) != len(refused) or set(refused) & active:
            raise ValueError("refusal scope conflict")
        return self


class Rights:
    def __init__(self, store, collection, evidence, execution):
        self.store, self.collection, self.evidence, self.execution = (
            store,
            collection,
            evidence,
            execution,
        )

    def _case(self, tx, member, case_id):
        row = tx.execute(
            "SELECT * FROM governance_rights_cases WHERE case_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(case_id), self.store.organization_id),
        ).fetchone()
        if not row or not in_scope(member, row["department_id"]):
            raise GovernanceError("record_unavailable")
        return row

    def _view(self, tx, row):
        result = {
            k: row[k]
            for k in ("revision", "state", "intake", "verification", "plan", "plan_version")
        }
        result.update(
            id=str(row["case_id"]),
            subject_id=str(row["subject_id"]) if row["subject_id"] else None,
            link_revision=row["link_revision"],
            physical_erasure_available=False,
        )
        result["manual"] = [
            {
                "id": str(r["obligation_id"]),
                "revision": r["revision"],
                "state": r["state"],
                "data": r["data"],
                "evidence_ref": str(r["evidence_ref"]) if r["evidence_ref"] else None,
            }
            for r in tx.execute(
                "SELECT * FROM governance_rights_manual WHERE case_id=%s AND plan_version=%s ORDER BY obligation_id",
                (row["case_id"], row["plan_version"]),
            )
        ]
        result["history"] = [
            {
                "revision": r["revision"],
                "kind": r["kind"],
                "data": {k: v for k, v in r["data"].items() if k != "closure_proof"},
            }
            for r in tx.execute(
                "SELECT * FROM governance_rights_history WHERE case_id=%s ORDER BY revision",
                (row["case_id"],),
            )
        ]
        return result

    def _save(self, tx, row, member, kind, **changes):
        # Column names originate only from this module, never browser input.
        json_columns = {"verification", "plan"}
        updated = tx.execute(
            sql.SQL(
                "UPDATE governance_rights_cases SET {},revision=revision+1 WHERE case_id=%s RETURNING *"
            ).format(
                sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in changes)
            ),
            tuple(
                Jsonb(v) if k in json_columns and v is not None else v for k, v in changes.items()
            )
            + (row["case_id"],),
        ).fetchone()
        history_data = {
            k: str(v) if k.endswith("_ref") and v else v
            for k, v in changes.items()
            if k in {"state", "verification", "plan", "closure_ref", "review_ref"}
        }
        if kind == "closure_reviewed" and updated["state"] in {"closed", "refused"}:
            history_data["closure_proof"] = self._closure_proof(tx, updated)
        tx.execute(
            "INSERT INTO governance_rights_history(history_id,case_id,revision,kind,data,actor_id) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                uuid4(),
                row["case_id"],
                updated["revision"],
                kind,
                Jsonb(history_data),
                member["member_id"],
            ),
        )
        return self._view(tx, updated)

    @staticmethod
    def _closure_fact(value):
        """Hash protected bytes; historical evidence never decrypts or discloses them."""
        if isinstance(value, dict):
            if "ciphertext" in value and hashlib.sha256(
                bytes(value["ciphertext"])
            ).hexdigest() != value.get("ciphertext_digest"):
                raise GovernanceError("protected_content_invalid")
            return {k: Rights._closure_fact(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [Rights._closure_fact(v) for v in value]
        if isinstance(value, (bytes, bytearray, memoryview)):
            return {"sha256": hashlib.sha256(bytes(value)).hexdigest(), "bytes": len(value)}
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        return str(value) if isinstance(value, UUID) else value

    def _closure_proof(self, tx, row):
        plan = row["plan"]
        if not plan or len(plan["targets"]) > 50 or len(plan["manual"]) > 100:
            raise GovernanceError("outcome_evidence_required")
        facts = {"case": self._closure_fact(row), "targets": [], "deliveries": []}
        for target in plan["targets"]:
            collection = tx.execute(
                "SELECT collection_id,organization_id,department_id,activity_id,activity_revision,subject_id,purpose_version,consent_bound FROM governance_collections WHERE collection_id=%s AND organization_id=%s",
                (identifier(target["collection_id"]), self.store.organization_id),
            ).fetchone()
            document = tx.execute(
                "SELECT document_id,collection_id,organization_id FROM governance_managed_documents WHERE document_id=%s AND collection_id=%s AND organization_id=%s",
                (
                    identifier(target["document_id"]),
                    identifier(target["collection_id"]),
                    self.store.organization_id,
                ),
            ).fetchone()
            if not collection or not document:
                raise GovernanceError("outcome_evidence_required")
            fact = {"target": target, "collection": collection, "document": document}
            versions = {target["target_version"]}
            if target.get("instruction_id"):
                instruction_id = identifier(target["instruction_id"])
                instruction = tx.execute(
                    "SELECT * FROM governance_execution_instructions WHERE instruction_id=%s AND organization_id=%s",
                    (instruction_id, self.store.organization_id),
                ).fetchone()
                outcome = tx.execute(
                    "SELECT * FROM governance_execution_outcomes WHERE instruction_id=%s",
                    (instruction_id,),
                ).fetchone()
                if not instruction or not outcome:
                    raise GovernanceError("outcome_evidence_required")
                versions.add(outcome["result_version"])
                fact.update(
                    instruction=instruction,
                    outcome=outcome,
                    controls=tx.execute(
                        "SELECT * FROM governance_instruction_controls WHERE instruction_id=%s",
                        (instruction_id,),
                    ).fetchone(),
                )
            if target.get("export_evidence_id"):
                evidence = tx.execute(
                    "SELECT * FROM governance_protected_evidence WHERE evidence_id=%s AND organization_id=%s",
                    (identifier(target["export_evidence_id"]), self.store.organization_id),
                ).fetchone()
                if not evidence:
                    raise GovernanceError("outcome_evidence_required")
                fact["evidence"] = evidence
            version_rows = tx.execute(
                "SELECT * FROM governance_document_versions WHERE document_id=%s AND version=ANY(%s) ORDER BY version",
                (identifier(target["document_id"]), sorted(versions)),
            ).fetchall()
            if len(version_rows) != len(versions):
                raise GovernanceError("outcome_evidence_required")
            fact["versions"] = version_rows
            facts["targets"].append(self._closure_fact(fact))
        for delivery in tx.execute(
            "SELECT * FROM governance_rights_deliveries WHERE case_id=%s AND plan_version=%s AND state='received' ORDER BY delivery_id",
            (row["case_id"], row["plan_version"]),
        ).fetchall():
            if not delivery["receipt_ref"] or not delivery["downloaded_session"]:
                raise GovernanceError("outcome_evidence_required")
            facts["deliveries"].append(self._closure_fact(delivery))
        facts["manual"] = self._closure_fact(
            tx.execute(
                "SELECT * FROM governance_rights_manual WHERE case_id=%s AND plan_version=%s ORDER BY obligation_id",
                (row["case_id"], row["plan_version"]),
            ).fetchall()
        )
        return {"version": 1, "digest": digest(facts)}

    def _run(self, principal, key, case_id, revision, action, data, effect):
        def scoped(tx, member):
            require_rights_role(member, action)
            return self._case(tx, member, case_id)

        def apply(tx, member, row):
            check_revision(row, revision)
            return effect(tx, member, row)

        return run_command(
            self.store,
            principal,
            key,
            RIGHTS_ACTION_MAP[action],
            action,
            {"id": str(identifier(case_id)), "revision": revision, "data": data},
            apply,
            scope=scoped,
        )

    def _link(self, tx, subject_id, revision, department):
        row = tx.execute(
            """SELECT s.subject_id FROM governance_subjects s
            JOIN governance_subject_links l ON l.subject_id=s.subject_id AND l.subject_revision=s.revision
            WHERE s.subject_id=%s AND s.organization_id=%s AND s.state='resolved'
            AND s.revision=%s AND l.state='active' AND l.departments ? %s FOR SHARE OF s,l""",
            (identifier(subject_id), self.store.organization_id, revision, department),
        ).fetchone()
        if not row:
            raise GovernanceError("identity_authority_changed")

    def _identity(self, tx, row):
        self._link(tx, row["subject_id"], row["link_revision"], row["department_id"])
        v = row["verification"]
        self._link(
            tx,
            v.get("recipient_subject_id") or row["subject_id"],
            v.get("recipient_link_revision") or row["link_revision"],
            row["department_id"],
        )

    def _legal(self, row):
        v = row["verification"]
        if not v or not v["complete"] or any(c["applicability"] == "unknown" for c in v["clocks"]):
            raise GovernanceError("legal_review_required")

    def _actor(self, tx, member_id, revision, permission, department):
        row = tx.execute(
            "SELECT * FROM governance_members WHERE member_id=%s AND organization_id=%s FOR SHARE",
            (member_id, self.store.organization_id),
        ).fetchone()
        if not row or row["revision"] != revision:
            raise GovernanceError("approval_authority_changed")
        if permission == RIGHTS_ACTION_MAP["rights.plan"] and "case_manager" not in row["roles"]:
            raise GovernanceError("approval_authority_changed")
        return require_member(
            tx,
            self.store.organization_id,
            Principal(issuer=row["issuer"], subject=row["subject"]),
            permission,
            department,
        )

    def receive(self, principal, command_key, request):
        data = _validated(Intake, request)

        def effect(tx, member, _):
            if data.channel == "portal":
                raise GovernanceError("subject_intake_required")
            row = tx.execute(
                """INSERT INTO governance_rights_cases(case_id,organization_id,department_id,intake,received_by,subject_id)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    data.department_id,
                    Jsonb(data.model_dump(mode="json")),
                    member["member_id"],
                    data.subject_id,
                ),
            ).fetchone()
            tx.execute(
                "INSERT INTO governance_rights_history(history_id,case_id,revision,kind,data,actor_id) VALUES (%s,%s,1,%s,%s,%s)",
                (
                    uuid4(),
                    row["case_id"],
                    "received",
                    Jsonb(data.model_dump(mode="json")),
                    member["member_id"],
                ),
            )
            return self._view(tx, row)

        return run_command(
            self.store,
            principal,
            command_key,
            RIGHTS_ACTION_MAP["rights.receive"],
            "rights.received",
            data.model_dump(mode="json"),
            effect,
            department_id=data.department_id,
            scope=lambda tx, member: require_rights_role(member, "rights.receive"),
        )

    def verify(self, principal, key, case_id, revision, request):
        data = _validated(Verification, request)

        def effect(tx, member, row):
            if row["state"] not in {"received", "verified"}:
                raise GovernanceError("invalid_transition")
            if member["member_id"] == row["received_by"]:
                raise GovernanceError("separation_required")
            if row["subject_id"] and row["subject_id"] != data.subject_id:
                raise GovernanceError("identity_mismatch")
            if {c.right for c in data.clocks} != set(row["intake"]["rights"]) or len(
                data.clocks
            ) != len(row["intake"]["rights"]):
                raise GovernanceError("clock_scope_mismatch")
            recipient = data.recipient_subject_id or data.subject_id
            if row["intake"]["requester"] == "representative":
                if (
                    not data.representative_ref
                    or not data.recipient_subject_id
                    or not data.recipient_link_revision
                ):
                    raise GovernanceError("representative_review_required")
            elif recipient != data.subject_id:
                raise GovernanceError("identity_mismatch")
            receipt = datetime.fromisoformat(row["intake"]["received_at"].replace("Z", "+00:00"))
            if data.complete_at and not receipt <= aware(data.complete_at) <= datetime.now(UTC):
                raise GovernanceError("invalid_request")
            if any(c.anchor == "complete_receipt" for c in data.clocks) and not data.complete_at:
                raise GovernanceError("completeness_review_required")
            self._link(tx, data.subject_id, data.link_revision, row["department_id"])
            self._link(
                tx,
                recipient,
                data.recipient_link_revision or data.link_revision,
                row["department_id"],
            )
            return self._save(
                tx,
                row,
                member,
                "verified",
                state="verified",
                subject_id=data.subject_id,
                link_revision=data.link_revision,
                verification=data.model_dump(mode="json"),
                verified_by=member["member_id"],
                verifier_revision=member["revision"],
            )

        return self._run(
            principal, key, case_id, revision, "rights.verify", data.model_dump(mode="json"), effect
        )

    def get(self, principal, case_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(
                tx, self.store.organization_id, principal, RIGHTS_ACTION_MAP["rights.read"]
            )
            require_rights_role(member, "rights.read")
            return self._view(tx, self._case(tx, member, case_id))

    def advice(self, principal, case_id, collection_id):
        """Bounded candidates and existing planner advice never grant authority."""
        from pii_redactor.dsar import _METHOD_STATEMENT
        from pii_redactor.pdpa_lifecycle import plan_lifecycle

        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(
                tx, self.store.organization_id, principal, RIGHTS_ACTION_MAP["rights.read"]
            )
            require_rights_role(member, "rights.read")
            row = self._case(tx, member, case_id)
            if not row["verification"]:
                raise GovernanceError("identity_review_required")
            self._identity(tx, row)
            bucket = self.collection._scope(tx, member, collection_id)
            if bucket["department_id"] != row["department_id"] or (
                bucket["subject_id"] and bucket["subject_id"] != row["subject_id"]
            ):
                raise GovernanceError("record_unavailable")
            self.collection.check_consent(tx, bucket, None, "list")
            candidates = [
                {
                    "document_id": str(d["document_id"]),
                    "target_revision": d["revision"],
                    "target_version": d["current_version"],
                    "identity_authority": False,
                }
                for d in tx.execute(
                    "SELECT * FROM governance_managed_documents WHERE collection_id=%s ORDER BY document_id LIMIT 100",
                    (bucket["collection_id"],),
                )
            ]
            return {
                "id": str(row["case_id"]),
                "revision": row["revision"],
                "candidates": candidates,
                "advice_only": True,
                "dsar_method": _METHOD_STATEMENT,
                "dsar_match_executed": False,
                "planner": [
                    plan_lifecycle({"right": r, "received_on": row["intake"]["received_at"][:10]})
                    for r in row["intake"]["rights"]
                ],
            }

    def list(self, principal, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            member = require_member(
                tx, self.store.organization_id, principal, RIGHTS_ACTION_MAP["rights.read"]
            )
            require_rights_role(member, "rights.read")
            rows = tx.execute(
                """SELECT * FROM governance_rights_cases WHERE organization_id=%s
                AND (%s OR department_id=ANY(%s)) AND (%s::uuid IS NULL OR case_id>%s::uuid)
                ORDER BY case_id LIMIT %s""",
                (
                    self.store.organization_id,
                    "*" in member["departments"],
                    member["departments"],
                    identifier(cursor) if cursor else None,
                    identifier(cursor) if cursor else None,
                    limit + 1,
                ),
            ).fetchall()
            return {
                "items": [
                    {"id": str(r["case_id"]), "revision": r["revision"], "state": r["state"]}
                    for r in rows[:limit]
                ],
                "next_cursor": str(rows[limit - 1]["case_id"]) if len(rows) > limit else None,
            }

    def _outcome_step(self, tx, row, target, instruction, document, *, committed=False):
        """Check one immutable outcome against its original approved case plan."""
        from pii_redactor.governance.execution import instruction_digest

        action = {"rectification": "correct", "restriction": "restrict", "erasure": "suppress"}.get(
            target["right"]
        )
        if (
            not action
            or instruction_digest(instruction) != instruction["instruction_digest"]
            or not instruction["approved_by"]
            or instruction["approved_by"] == instruction["proposed_by"]
            or not instruction["approver_revision"]
            or instruction["organization_id"] != self.store.organization_id
            or instruction["collection_id"] != identifier(target["collection_id"])
            or instruction["document_id"] != identifier(target["document_id"])
            or instruction["document_id"] != document["document_id"]
            or instruction["target_revision"] != target["target_revision"]
            or instruction["target_version"] != target["target_version"]
            or instruction["action"] != action
        ):
            raise GovernanceError("outcome_evidence_required")
        binding = tx.execute(
            "SELECT * FROM governance_rights_instruction_bindings WHERE instruction_id=%s",
            (instruction["instruction_id"],),
        ).fetchone()
        if (
            not binding
            or binding["case_id"] != row["case_id"]
            or not 1 <= binding["plan_version"] <= row["plan_version"]
        ):
            raise GovernanceError("instruction_already_bound")
        source = tx.execute(
            """SELECT revision,data,actor_id FROM governance_rights_history
            WHERE case_id=%s AND kind='planned' ORDER BY revision OFFSET %s LIMIT 1""",
            (row["case_id"], binding["plan_version"] - 1),
        ).fetchone()
        if not source:
            raise GovernanceError("outcome_evidence_required")
        reviewed = tx.execute(
            """SELECT created_at FROM governance_rights_history WHERE case_id=%s AND kind='approved'
            AND revision>%s AND actor_id<>%s AND revision<COALESCE(
                (SELECT min(revision) FROM governance_rights_history
                 WHERE case_id=%s AND kind='planned' AND revision>%s),%s)""",
            (
                row["case_id"],
                source["revision"],
                source["actor_id"],
                row["case_id"],
                source["revision"],
                row["revision"] + 1,
            ),
        ).fetchone()
        fields = (
            "right",
            "collection_id",
            "document_id",
            "target_revision",
            "target_version",
            "instruction_id",
        )
        if not reviewed or not any(
            all(original[key] == target[key] for key in fields)
            for original in source["data"]["plan"]["targets"]
        ):
            raise GovernanceError("outcome_evidence_required")
        proof = tx.execute(
            "SELECT * FROM governance_execution_outcomes WHERE instruction_id=%s",
            (instruction["instruction_id"],),
        ).fetchone()
        task = tx.execute(
            "SELECT state FROM governance_execution_tasks WHERE instruction_id=%s",
            (instruction["instruction_id"],),
        ).fetchone()
        states = {"verified", "unknown"} if committed else {"verified"}
        source_expiry = datetime.fromisoformat(
            source["data"]["plan"]["expires_at"].replace("Z", "+00:00")
        )
        if (
            instruction["state"] not in states
            or not task
            or task["state"] not in states
            or not proof
            or proof["verified_at"] < reviewed["created_at"]
            or proof["verified_at"] > min(source_expiry, instruction["expires_at"])
            or proof["instruction_digest"] != instruction["instruction_digest"]
            or proof["document_id"] != document["document_id"]
            or proof["result_revision"] != instruction["target_revision"] + 1
            or proof["result_version"] != instruction["target_version"] + (action == "correct")
            or (action == "restrict" and proof["result_state"] not in {"restricted", "suppressed"})
            or (action == "suppress" and proof["result_state"] != "suppressed")
        ):
            raise GovernanceError("outcome_evidence_required")
        stored = tx.execute(
            "SELECT * FROM governance_document_versions WHERE document_id=%s AND version=%s",
            (document["document_id"], proof["result_version"]),
        ).fetchone()
        if not stored or stored["ciphertext_digest"] != proof["ciphertext_digest"]:
            raise GovernanceError("outcome_evidence_required")
        from pii_redactor.governance.collections import document_context

        self.collection.protection.open(
            self.store.organization_id,
            instruction["collection_id"],
            stored,
            document_context(
                self.store.organization_id,
                instruction["collection_id"],
                document["document_id"],
                proof["result_version"],
                stored["content_type"],
            ),
        )
        return proof, {
            "source_plan_version": binding["plan_version"],
            **{
                key: proof[key]
                for key in (
                    "instruction_digest",
                    "result_revision",
                    "result_version",
                    "result_state",
                    "ciphertext_digest",
                )
            },
        }

    def _completed_outcome(self, tx, row, target, instruction, document, *, committed=False):
        """Trace only approved same-case outcomes to the exact current primary."""
        seen, original, previous = set(), None, None
        while True:
            if instruction["instruction_id"] in seen or len(seen) >= 50:
                raise GovernanceError("outcome_evidence_required")
            seen.add(instruction["instruction_id"])
            proof, metadata = self._outcome_step(
                tx, row, target, instruction, document, committed=committed and original is None
            )
            if original is None:
                original = metadata
            if previous is not None:
                expected_state = (
                    "suppressed"
                    if instruction["action"] == "suppress"
                    or previous["result_state"] == "suppressed"
                    else "restricted"
                    if instruction["action"] == "restrict"
                    else previous["result_state"]
                )
                if (
                    instruction["target_revision"] != previous["result_revision"]
                    or instruction["target_version"] != previous["result_version"]
                    or proof["result_state"] != expected_state
                    or proof["verified_at"] < previous["verified_at"]
                ):
                    raise GovernanceError("outcome_evidence_required")
            if document["last_instruction_id"] == instruction["instruction_id"]:
                if (
                    document["revision"] != proof["result_revision"]
                    or document["current_version"] != proof["result_version"]
                    or document["state"] != proof["result_state"]
                ):
                    raise GovernanceError("outcome_evidence_required")
                return original
            if proof["result_revision"] >= document["revision"]:
                raise GovernanceError("outcome_evidence_required")
            successors = tx.execute(
                """SELECT i.* FROM governance_execution_instructions i
                JOIN governance_execution_outcomes o USING(instruction_id)
                JOIN governance_rights_instruction_bindings b USING(instruction_id)
                WHERE i.organization_id=%s AND i.collection_id=%s AND i.document_id=%s
                AND i.target_revision=%s AND i.target_version=%s AND i.state='verified'
                AND b.case_id=%s LIMIT 2""",
                (
                    self.store.organization_id,
                    instruction["collection_id"],
                    document["document_id"],
                    proof["result_revision"],
                    proof["result_version"],
                    row["case_id"],
                ),
            ).fetchall()
            if len(successors) != 1:
                raise GovernanceError("outcome_evidence_required")
            previous, instruction = proof, successors[0]
            target = next(
                (
                    candidate
                    for candidate in row["plan"]["targets"]
                    if candidate["instruction_id"] == str(instruction["instruction_id"])
                ),
                None,
            )
            if target is None:
                raise GovernanceError("outcome_evidence_required")

    def _received_before_own_outcome(self, tx, row, target, member, document):
        received = tx.execute(
            "SELECT 1 FROM governance_rights_deliveries WHERE case_id=%s AND plan_version=%s AND state='received'",
            (row["case_id"], row["plan_version"]),
        ).fetchone()
        if not received:
            return False
        for mutation in row["plan"]["targets"]:
            if (
                mutation["instruction_id"]
                and mutation["document_id"] == target["document_id"]
                and mutation["target_revision"] == target["target_revision"]
                and mutation["target_version"] == target["target_version"]
            ):
                instruction = self.execution._instruction(tx, member, mutation["instruction_id"])
                self._completed_outcome(tx, row, mutation, instruction, document)
                return True
        return False

    def _targets(self, tx, row, member, *, exact=True, only_instruction=None):
        for target in row["plan"]["targets"]:
            if only_instruction is not None and target["instruction_id"] != only_instruction:
                continue
            collection = self.collection._scope(tx, member, target["collection_id"])
            if collection["consent_bound"]:
                from pii_redactor.governance.consent import Consent

                current = Consent(self.store).effective(
                    tx, collection["subject_id"], collection["purpose_version"]
                )
                if not current["allowed"]:
                    raise GovernanceError("consent_required")
                if (
                    row["plan"].get("consent_bindings", {}).get(str(collection["collection_id"]))
                    != current["revision"]
                ):
                    raise GovernanceError("consent_authority_changed")
            if collection["department_id"] != row["department_id"] or (
                collection["subject_id"] and collection["subject_id"] != row["subject_id"]
            ):
                raise GovernanceError("identity_mismatch")
            doc = self.collection._document(tx, collection["collection_id"], target["document_id"])
            carried = row["plan"].get("completed_outcomes", {}).get(target["instruction_id"])
            if (
                (exact or target["right"] in {"access", "portability"})
                and not carried
                and (
                    doc["revision"] != target["target_revision"]
                    or doc["current_version"] != target["target_version"]
                )
            ):
                if (
                    not exact
                    and target["right"] in {"access", "portability"}
                    and self._received_before_own_outcome(tx, row, target, member, doc)
                ):
                    self.collection.check_consent(tx, collection, doc, "preview")
                    continue
                raise GovernanceError("revision_conflict")
            if target["right"] in {"access", "portability"}:
                self.collection.check_consent(tx, collection, doc, "read")
                if doc["state"] != "active":
                    raise GovernanceError("record_restricted")
                ev = self.evidence.resolve(
                    tx,
                    member,
                    target["export_evidence_id"],
                    collection_id=collection["collection_id"],
                    document_id=doc["document_id"],
                    version=target["target_version"],
                )
                self.evidence.content(tx, ev)
            else:
                ins = self.execution._instruction(tx, member, target["instruction_id"])
                expected = {
                    "rectification": "correct",
                    "restriction": "restrict",
                    "erasure": "suppress",
                }[target["right"]]
                if (
                    ins["document_id"] != doc["document_id"]
                    or ins["collection_id"] != collection["collection_id"]
                    or ins["target_version"] != target["target_version"]
                    or ins["target_revision"] != target["target_revision"]
                    or ins["action"] != expected
                ):
                    raise GovernanceError("instruction_scope_mismatch")
                # The worker's outcome may legitimately change the primary document.
                if carried:
                    if carried != self._completed_outcome(
                        tx, row, target, ins, doc, committed=only_instruction is not None
                    ):
                        raise GovernanceError("outcome_evidence_required")
                    self.collection.check_consent(tx, collection, doc, "preview")
                elif exact:
                    self.collection.check_consent(tx, collection, doc, expected)
                    if ins["state"] not in {"proposed", "pending"}:
                        raise GovernanceError("invalid_transition")

    def plan(self, principal, key, case_id, revision, request):
        data = _validated(FulfilmentPlan, request)

        def effect(tx, member, row):
            if row["state"] not in {"verified", "planned", "approved", "partial"}:
                raise GovernanceError("invalid_transition")
            self._legal(row)
            self._identity(tx, row)
            covered = {t.right for t in [*data.targets, *data.manual, *data.refusals]}
            if covered != set(row["intake"]["rights"]):
                raise GovernanceError("plan_scope_mismatch")
            for clock in row["verification"]["clocks"]:
                if clock["applicability"] == "not_applicable" and clock["right"] not in {
                    r.right for r in data.refusals
                }:
                    raise GovernanceError("legal_review_required")
            for task in data.manual:
                owner = tx.execute(
                    "SELECT * FROM governance_members WHERE member_id=%s AND organization_id=%s AND enabled FOR SHARE",
                    (task.owner_id, self.store.organization_id),
                ).fetchone()
                if not owner or not in_scope(owner, row["department_id"]):
                    raise GovernanceError("manual_owner_required")
            if "erasure" in covered and not any(r.right == "erasure" for r in data.refusals):
                if not {
                    "derived",
                    "processor",
                    "replica_wal",
                    "backup",
                    "physical_storage",
                }.issubset({t.kind for t in data.manual if t.right == "erasure"}):
                    raise GovernanceError("erasure_obligations_required")
            bindings = {}
            for target in data.targets:
                collection = self.collection._scope(tx, member, target.collection_id)
                if collection["consent_bound"]:
                    from pii_redactor.governance.consent import Consent

                    current = Consent(self.store).effective(
                        tx, collection["subject_id"], collection["purpose_version"]
                    )
                    if not current["allowed"]:
                        raise GovernanceError("consent_required")
                    bindings[str(collection["collection_id"])] = current["revision"]
            completed = {}
            for target in data.targets:
                if target.instruction_id:
                    instruction = self.execution._instruction(tx, member, target.instruction_id)
                    if instruction["state"] == "verified":
                        document = self.collection._document(
                            tx, target.collection_id, target.document_id
                        )
                        completed[str(target.instruction_id)] = self._completed_outcome(
                            tx, row, target.model_dump(mode="json"), instruction, document
                        )
                    elif instruction["state"] != "proposed":
                        raise GovernanceError("unissued_instruction_required")
            bound_plan = {
                **data.model_dump(mode="json"),
                "consent_bindings": bindings,
                "completed_outcomes": completed,
            }
            candidate = {**row, "plan": bound_plan}
            self._targets(tx, candidate, member)
            version = row["plan_version"] + 1
            for target in data.targets:
                if target.instruction_id:
                    if str(target.instruction_id) in completed:
                        continue
                    instruction = self.execution._instruction(tx, member, target.instruction_id)
                    if instruction["state"] != "proposed":
                        raise GovernanceError("unissued_instruction_required")
                    prior = tx.execute(
                        "SELECT * FROM governance_rights_instruction_bindings WHERE instruction_id=%s",
                        (target.instruction_id,),
                    ).fetchone()
                    if prior:
                        raise GovernanceError("instruction_already_bound")
                    tx.execute(
                        "INSERT INTO governance_rights_instruction_bindings VALUES (%s,%s,%s)",
                        (target.instruction_id, row["case_id"], version),
                    )
            tx.execute(
                "UPDATE governance_rights_deliveries SET state='revoked',revision=revision+1 WHERE case_id=%s AND state<>'revoked'",
                (row["case_id"],),
            )
            for task in data.manual:
                tx.execute(
                    "INSERT INTO governance_rights_manual(obligation_id,case_id,plan_version,data) VALUES (%s,%s,%s,%s)",
                    (uuid4(), row["case_id"], version, Jsonb(task.model_dump(mode="json"))),
                )
            return self._save(
                tx,
                row,
                member,
                "planned",
                state="planned",
                plan=bound_plan,
                plan_version=version,
                proposed_by=member["member_id"],
                proposer_revision=member["revision"],
                approved_by=None,
                approver_revision=None,
                approval_expires_at=None,
                review_ref=None,
            )

        return self._run(
            principal, key, case_id, revision, "rights.plan", data.model_dump(mode="json"), effect
        )

    def _export(self, tx, row, member):
        parts = []
        for target in row["plan"]["targets"]:
            if target["right"] in {"access", "portability"}:
                ev = self.evidence.resolve(
                    tx,
                    member,
                    target["export_evidence_id"],
                    collection_id=target["collection_id"],
                    document_id=target["document_id"],
                    version=target["target_version"],
                )
                parts.append(self.evidence.content(tx, ev).decode("utf-8"))
        return "\n\n".join(parts)

    def preview(self, principal, case_id, revision):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(
                tx, self.store.organization_id, principal, RIGHTS_ACTION_MAP["rights.review"]
            )
            row = self._case(tx, member, case_id)
            check_revision(row, revision)
            if row["state"] != "planned" or member["member_id"] == row["proposed_by"]:
                raise GovernanceError("separation_required")
            if (
                datetime.fromisoformat(row["plan"]["expires_at"].replace("Z", "+00:00"))
                <= tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            ):
                raise GovernanceError("approval_expired")
            self._identity(tx, row)
            self._targets(tx, row, member)
            content = self._export(tx, row, member)
            tx.execute(
                """INSERT INTO governance_rights_previews VALUES (%s,%s,%s,%s)
                ON CONFLICT(case_id,plan_version,reviewer_id) DO UPDATE SET plan_digest=EXCLUDED.plan_digest""",
                (row["case_id"], row["plan_version"], member["member_id"], digest(row["plan"])),
            )
            self.store.append_event(
                tx,
                event_code="rights.export_previewed",
                actor_id=member["member_id"],
                target_id=row["case_id"],
                revision=row["revision"],
            )
            return {"id": str(row["case_id"]), "revision": revision, "content": content}

    def review(self, principal, key, case_id, revision, evidence_ref):
        evidence_ref = identifier(evidence_ref)

        def effect(tx, member, row):
            if row["state"] != "planned":
                raise GovernanceError("invalid_transition")
            if member["member_id"] == row["proposed_by"]:
                raise GovernanceError("separation_required")
            self._legal(row)
            self._identity(tx, row)
            self._actor(
                tx,
                row["proposed_by"],
                row["proposer_revision"],
                RIGHTS_ACTION_MAP["rights.plan"],
                row["department_id"],
            )
            self._targets(tx, row, member)
            expires = datetime.fromisoformat(row["plan"]["expires_at"].replace("Z", "+00:00"))
            if expires <= datetime.now(UTC):
                raise GovernanceError("approval_expired")
            if any(t["right"] in {"access", "portability"} for t in row["plan"]["targets"]):
                preview = tx.execute(
                    "SELECT plan_digest FROM governance_rights_previews WHERE case_id=%s AND plan_version=%s AND reviewer_id=%s",
                    (row["case_id"], row["plan_version"], member["member_id"]),
                ).fetchone()
                if not preview or preview["plan_digest"] != digest(row["plan"]):
                    raise GovernanceError("redaction_review_required")
            return self._save(
                tx,
                row,
                member,
                "approved",
                state="approved",
                approved_by=member["member_id"],
                approver_revision=member["revision"],
                approval_expires_at=expires,
                review_ref=evidence_ref,
            )

        return self._run(
            principal, key, case_id, revision, "rights.review", str(evidence_ref), effect
        )

    def _authority(self, tx, row, *, exact=True, only_instruction=None):
        if row["state"] not in {"approved", "partial"}:
            raise GovernanceError("case_authority_revoked")
        self._legal(row)
        self._identity(tx, row)
        self._actor(
            tx,
            row["verified_by"],
            row["verifier_revision"],
            RIGHTS_ACTION_MAP["rights.verify"],
            row["department_id"],
        )
        proposer = self._actor(
            tx,
            row["proposed_by"],
            row["proposer_revision"],
            RIGHTS_ACTION_MAP["rights.plan"],
            row["department_id"],
        )
        self._actor(
            tx,
            row["approved_by"],
            row["approver_revision"],
            RIGHTS_ACTION_MAP["rights.review"],
            row["department_id"],
        )
        self._targets(tx, row, proposer, exact=exact, only_instruction=only_instruction)
        # Check wall time after all potentially blocking locks.
        if (
            row["approval_expires_at"]
            <= tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        ):
            raise GovernanceError("approval_expired")
        return proposer

    def fence_instruction(self, tx, instruction, *, allow_committed=False):
        """Required parent Execution._recheck hook, inside its managed transaction."""
        binding = tx.execute(
            "SELECT * FROM governance_rights_instruction_bindings WHERE instruction_id=%s",
            (instruction["instruction_id"],),
        ).fetchone()
        if not binding:
            return
        row = tx.execute(
            "SELECT * FROM governance_rights_cases WHERE case_id=%s AND organization_id=%s FOR UPDATE",
            (binding["case_id"], self.store.organization_id),
        ).fetchone()
        if not row:
            raise GovernanceError("case_authority_revoked")
        target = next(
            (
                t
                for t in row["plan"]["targets"]
                if t["instruction_id"] == str(instruction["instruction_id"])
            ),
            None,
        )
        if not target:
            raise GovernanceError("instruction_scope_mismatch")
        if binding["plan_version"] != row["plan_version"] and not (
            allow_committed
            and str(instruction["instruction_id"]) in row["plan"].get("completed_outcomes", {})
        ):
            raise GovernanceError("case_authority_revoked")
        if allow_committed:
            document = self.collection._document(
                tx, instruction["collection_id"], instruction["document_id"]
            )
            self._completed_outcome(tx, row, target, instruction, document, committed=True)
        # Reconciliation verifies one committed primary outcome, never an export or replay.
        self._authority(
            tx,
            row,
            exact=False,
            only_instruction=str(instruction["instruction_id"]) if allow_committed else None,
        )

    def manual_evidence(
        self,
        principal,
        key,
        case_id,
        revision,
        obligation_id,
        evidence_ref,
        *,
        review=False,
        decision="verified",
    ):
        obligation_id, evidence_ref = identifier(obligation_id), identifier(evidence_ref)
        if type(review) is not bool or decision not in {"verified", "failed"}:
            raise GovernanceError("invalid_request")

        def effect(tx, member, row):
            self._authority(tx, row, exact=False)
            task = tx.execute(
                "SELECT * FROM governance_rights_manual WHERE obligation_id=%s AND case_id=%s AND plan_version=%s FOR UPDATE",
                (obligation_id, row["case_id"], row["plan_version"]),
            ).fetchone()
            if not task:
                raise GovernanceError("record_unavailable")
            if review:
                if task["state"] != "submitted" or member["member_id"] == task["submitted_by"]:
                    raise GovernanceError("independent_review_required")
                if (
                    task["data"]["right"] == "erasure"
                    and task["data"]["kind"] == "physical_storage"
                    and decision == "verified"
                ):
                    raise GovernanceError("physical_erasure_unavailable")
                tx.execute(
                    "UPDATE governance_rights_manual SET state=%s,revision=revision+1,reviewed_by=%s,review_ref=%s WHERE obligation_id=%s",
                    (decision, member["member_id"], evidence_ref, obligation_id),
                )
            else:
                if (
                    task["data"]["owner_id"] != str(member["member_id"])
                    or task["state"] == "verified"
                ):
                    raise GovernanceError("forbidden")
                tx.execute(
                    "UPDATE governance_rights_manual SET state='submitted',revision=revision+1,evidence_ref=%s,submitted_by=%s WHERE obligation_id=%s",
                    (evidence_ref, member["member_id"], obligation_id),
                )
            return self._save(
                tx,
                row,
                member,
                "manual_reviewed" if review else "manual_submitted",
                state=row["state"],
            )

        return self._run(
            principal,
            key,
            case_id,
            revision,
            "rights.manual.review" if review else "rights.manual.submit",
            {
                "obligation_id": str(obligation_id),
                "evidence_ref": str(evidence_ref),
                "decision": decision,
            },
            effect,
        )

    def outcome(self, tx, row):
        verified = 0
        pending = 0
        for target in row["plan"]["targets"]:
            if target["right"] in {"access", "portability"}:
                delivery = tx.execute(
                    "SELECT 1 FROM governance_rights_deliveries WHERE case_id=%s AND plan_version=%s AND state='received'",
                    (row["case_id"], row["plan_version"]),
                ).fetchone()
                verified += bool(delivery)
                pending += not bool(delivery)
            else:
                instruction = tx.execute(
                    "SELECT * FROM governance_execution_instructions WHERE instruction_id=%s AND organization_id=%s",
                    (identifier(target["instruction_id"]), self.store.organization_id),
                ).fetchone()
                completed = bool(instruction and instruction["state"] == "verified")
                if completed:
                    document = self.collection._document(
                        tx, target["collection_id"], target["document_id"]
                    )
                    self._completed_outcome(tx, row, target, instruction, document)
                verified += completed
                pending += not completed
        for task in tx.execute(
            "SELECT state FROM governance_rights_manual WHERE case_id=%s AND plan_version=%s",
            (row["case_id"], row["plan_version"]),
        ):
            verified += task["state"] == "verified"
            pending += task["state"] != "verified"
        verified += len(row["plan"]["refusals"])
        return {"verified": verified, "pending": pending, "physical_erasure_verified": False}

    def close(self, principal, key, case_id, revision, evidence_ref, *, partial=False):
        evidence_ref = identifier(evidence_ref)
        if type(partial) is not bool:
            raise GovernanceError("invalid_request")

        def effect(tx, member, row):
            self._authority(tx, row, exact=False)
            result = self.outcome(tx, row)
            if not result["verified"] or (result["pending"] and not partial):
                raise GovernanceError("outcome_evidence_required")
            erasure = "erasure" in row["intake"]["rights"] and not any(
                r["right"] == "erasure" for r in row["plan"]["refusals"]
            )
            if erasure and not partial:
                raise GovernanceError("physical_erasure_unavailable")
            state = (
                "partial"
                if result["pending"] or erasure
                else (
                    "refused"
                    if len(row["plan"]["refusals"]) == len(row["intake"]["rights"])
                    else "closed"
                )
            )
            return self._save(
                tx, row, member, "closure_reviewed", state=state, closure_ref=evidence_ref
            )

        return self._run(
            principal,
            key,
            case_id,
            revision,
            "rights.close",
            {"evidence_ref": str(evidence_ref), "partial": partial},
            effect,
        )

    def transition(self, principal, key, case_id, revision, evidence_ref, *, action):
        evidence_ref = identifier(evidence_ref)
        if action not in {"reopen", "withdraw"}:
            raise GovernanceError("invalid_request")

        def effect(tx, member, row):
            if action == "reopen" and row["state"] not in {
                "partial",
                "closed",
                "refused",
                "withdrawn",
            }:
                raise GovernanceError("invalid_transition")
            if action == "withdraw" and row["state"] in {"closed", "refused", "withdrawn"}:
                raise GovernanceError("invalid_transition")
            tx.execute(
                "UPDATE governance_rights_deliveries SET state='revoked',revision=revision+1 WHERE case_id=%s AND state<>'revoked'",
                (row["case_id"],),
            )
            return self._save(
                tx,
                row,
                member,
                action,
                state="received" if action == "reopen" else "withdrawn",
                approved_by=None,
                approver_revision=None,
                approval_expires_at=None,
                closure_ref=evidence_ref,
            )

        return self._run(
            principal, key, case_id, revision, "rights." + action, str(evidence_ref), effect
        )

    def subject_cases(self, actor, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            subject = require_subject_actor(tx, self.store.organization_id, actor)
            session = tx.execute(
                "SELECT csrf_hash FROM enterprise_subject_sessions WHERE session_id=%s AND organization_id=%s",
                (actor.session_id, self.store.organization_id),
            ).fetchone()
            scope = digest(
                {
                    "purpose": "rights.subject_cases.v1",
                    "organization_id": str(self.store.organization_id),
                    "subject_id": str(actor.subject_id),
                    "session_id": str(actor.session_id),
                    "link_revision": actor.link_revision,
                    "departments": sorted(subject["departments"]),
                }
            )

            def signature(last):
                return hmac.new(
                    session["csrf_hash"].encode("ascii"),
                    (scope + ":" + str(last)).encode("ascii"),
                    hashlib.sha256,
                ).hexdigest()

            last = None
            if cursor is not None:
                if not isinstance(cursor, str) or len(cursor) != 101 or cursor.count(".") != 1:
                    raise GovernanceError("invalid_request")
                value, supplied = cursor.split(".")
                last = identifier(value)
                if any(
                    char not in "0123456789abcdef" for char in supplied
                ) or not hmac.compare_digest(supplied, signature(last)):
                    raise GovernanceError("invalid_request")
            rows = tx.execute(
                """SELECT case_id,state,revision,plan_version FROM governance_rights_cases
                WHERE organization_id=%s AND department_id=ANY(%s)
                AND (verification->>'recipient_subject_id'=%s OR
                     (subject_id=%s AND intake->>'requester'='subject'))
                AND (%s::uuid IS NULL OR case_id>%s::uuid)
                ORDER BY case_id LIMIT %s""",
                (
                    self.store.organization_id,
                    subject["departments"],
                    str(subject["subject_id"]),
                    subject["subject_id"],
                    last,
                    last,
                    limit + 1,
                ),
            ).fetchall()
            items = [
                {
                    "id": str(r["case_id"]),
                    "state": r["state"],
                    "revision": r["revision"],
                    "deliveries": [
                        {
                            "id": str(d["delivery_id"]),
                            "revision": d["revision"],
                            "state": d["state"],
                            "expires_at": d["expires_at"].isoformat(),
                        }
                        for d in tx.execute(
                            "SELECT * FROM governance_rights_deliveries WHERE case_id=%s AND plan_version=%s",
                            (r["case_id"], r["plan_version"]),
                        )
                    ],
                }
                for r in rows[:limit]
            ]
            return {
                "items": items,
                "next_cursor": (
                    str(rows[limit - 1]["case_id"]) + "." + signature(rows[limit - 1]["case_id"])
                    if len(rows) > limit
                    else None
                ),
            }

    def subject_receive(self, actor, key, department_id, rights):
        # The portal never supplies its own actor, receipt time or channel.
        key = identifier(key)
        with self.store.transaction() as tx:
            self.store.lock(tx)
            subject = require_subject_actor(tx, self.store.organization_id, actor)
            data = _validated(
                Intake,
                {
                    "department_id": department_id,
                    "subject_id": actor.subject_id,
                    "received_at": datetime.now(UTC),
                    "channel": "portal",
                    "original_receipt_ref": uuid4(),
                    "requester": "subject",
                    "rights": rights,
                },
            )
            fingerprint = digest({"department_id": department_id, "rights": data.rights})
            if department_id not in subject["departments"]:
                raise GovernanceError("forbidden")
            previous = tx.execute(
                "SELECT * FROM governance_rights_subject_commands WHERE subject_id=%s AND command_key=%s",
                (actor.subject_id, key),
            ).fetchone()
            if previous:
                if previous["request_digest"] != fingerprint:
                    raise GovernanceError("idempotency_conflict")
                return {"id": str(previous["case_id"]), "replayed": True}
            row = tx.execute(
                """INSERT INTO governance_rights_cases(case_id,organization_id,department_id,intake,subject_id,received_session)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    department_id,
                    Jsonb(data.model_dump(mode="json")),
                    actor.subject_id,
                    actor.session_id,
                ),
            ).fetchone()
            tx.execute(
                "INSERT INTO governance_rights_history(history_id,case_id,revision,kind,data) VALUES (%s,%s,1,%s,%s)",
                (uuid4(), row["case_id"], "received", Jsonb(data.model_dump(mode="json"))),
            )
            event = self.store.append_event(
                tx, event_code="rights.subject_received", target_id=row["case_id"], revision=1
            )
            tx.execute(
                "INSERT INTO governance_outbox(event_id,event_code,payload) VALUES (%s,%s,%s)",
                (
                    event,
                    "rights.subject_received",
                    Jsonb({"record_id": str(row["case_id"]), "revision": 1}),
                ),
            )
            tx.execute(
                "INSERT INTO governance_rights_subject_commands VALUES (%s,%s,%s,%s)",
                (actor.subject_id, key, fingerprint, row["case_id"]),
            )
            return {
                "id": str(row["case_id"]),
                "revision": 1,
                "state": "received",
                "replayed": False,
            }

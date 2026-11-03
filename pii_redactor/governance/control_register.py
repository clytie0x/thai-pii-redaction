"""Shared exact-revision lifecycle for the seven organization registers.

Only opaque evidence references enter these records. The shared transaction
keeps authority, dependency fencing, history, audit and receipts consistent.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, field_validator

from pii_redactor.governance.commands import check_revision, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel, Department, Principal
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.registry import RecordID, _validated


class Binding(ClosedModel):
    id: RecordID
    revision: int = Field(ge=1)


class WorkflowLink(Binding):
    kind: Literal["activity", "notice", "consent", "retention", "case"]


class ControlInput(ClosedModel):
    department_id: Department
    owner_ref: RecordID
    evidence_ref: RecordID
    expires_at: datetime = Field(strict=False)
    links: list[WorkflowLink] = Field(default_factory=list, max_length=64)
    dependencies: list[Binding] = Field(default_factory=list, max_length=64)
    supersedes: Binding | None = None

    @field_validator("department_id")
    @classmethod
    def concrete_department(cls, value):
        if value == "*":
            raise ValueError("concrete department required")
        return value

    @field_validator("expires_at")
    @classmethod
    def zoned(cls, value):
        if value.tzinfo is None:
            raise ValueError("timezone required")
        return value.astimezone(UTC)


class Register:
    kind = ""
    input_model = ControlInput

    def __init__(self, store, *, case_checker=None):
        self.store = store
        self.case_checker = case_checker

    def _row(self, tx, member, record_id, *, kind=True):
        row = tx.execute(
            "SELECT * FROM governance_organization_controls WHERE control_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(record_id), self.store.organization_id),
        ).fetchone()
        if (
            not row
            or not in_scope(member, row["department_id"])
            or (kind and row["kind"] != self.kind)
        ):
            raise GovernanceError("record_unavailable")
        return row

    def _actor(self, tx, member_id, revision, permission, department):
        actor = tx.execute(
            "SELECT * FROM governance_members WHERE member_id=%s AND organization_id=%s FOR SHARE",
            (member_id, self.store.organization_id),
        ).fetchone()
        if not actor or actor["revision"] != revision:
            raise GovernanceError("authority_changed")
        try:
            require_member(
                tx,
                self.store.organization_id,
                Principal(issuer=actor["issuer"], subject=actor["subject"]),
                permission,
                department,
            )
        except GovernanceError:
            raise GovernanceError("authority_changed") from None

    def _links_current(self, tx, row):
        for link in row["data"]["links"]:
            params = (link["id"], self.store.organization_id)
            if link["kind"] == "activity":
                target = tx.execute(
                    "SELECT revision,state,department_id FROM governance_activities WHERE activity_id=%s AND organization_id=%s FOR SHARE",
                    params,
                ).fetchone()
                allowed = {"active"}
            elif link["kind"] == "notice":
                target = tx.execute(
                    "SELECT n.revision,n.state,a.department_id FROM governance_notices n JOIN governance_activities a USING(activity_id) WHERE n.notice_id=%s AND n.organization_id=%s FOR SHARE OF n,a",
                    params,
                ).fetchone()
                allowed = {"published"}
            elif link["kind"] == "consent":
                target = tx.execute(
                    "SELECT p.notice_revision AS revision,a.state,p.department_id FROM governance_consent_purposes p JOIN governance_activities a USING(activity_id) WHERE p.purpose_version=%s AND p.organization_id=%s AND p.activity_revision=a.revision FOR SHARE OF a",
                    params,
                ).fetchone()
                allowed = {"active"}
            elif link["kind"] == "retention":
                target = tx.execute(
                    "SELECT p.revision,p.state,c.department_id FROM governance_retention_policies p JOIN governance_collections c USING(collection_id) WHERE p.policy_id=%s AND p.organization_id=%s FOR SHARE OF p,c",
                    params,
                ).fetchone()
                allowed = {"active"}
            else:
                # M7 is not installed here. An opaque case reference never proves fulfilment.
                if (
                    self.case_checker is None
                    or self.case_checker(
                        tx,
                        self.store.organization_id,
                        row["department_id"],
                        identifier(link["id"]),
                        link["revision"],
                    )
                    is not True
                ):
                    raise GovernanceError("linked_case_unverified")
                continue
            if (
                not target
                or target["revision"] != link["revision"]
                or target["department_id"] != row["department_id"]
                or target["state"] not in allowed
            ):
                raise GovernanceError("control_stale")

    def _current(self, tx, row, *, seen=None, checked=None, require_active=True):
        seen = set() if seen is None else set(seen)
        checked = set() if checked is None else checked
        if row["control_id"] in seen or len(seen) >= 32:
            raise GovernanceError("control_stale")
        if row["control_id"] in checked:
            return
        if len(checked) >= 256:
            raise GovernanceError("control_stale")
        seen.add(row["control_id"])
        if require_active and row["state"] != "active":
            raise GovernanceError("control_stale")
        if datetime.fromisoformat(row["data"]["expires_at"]) <= datetime.now(UTC):
            raise GovernanceError("control_stale")
        self._actor(
            tx,
            row["proposed_by"],
            row["proposer_revision"],
            "activity.create",
            row["department_id"],
        )
        self._actor(
            tx,
            row["reviewed_by"],
            row["reviewer_revision"],
            "activity.review",
            row["department_id"],
        )
        self._links_current(tx, row)
        for binding in row["data"]["dependencies"]:
            dep = tx.execute(
                "SELECT * FROM governance_organization_controls WHERE control_id=%s AND organization_id=%s FOR SHARE",
                (identifier(binding["id"]), self.store.organization_id),
            ).fetchone()
            if (
                not dep
                or dep["revision"] != binding["revision"]
                or dep["department_id"] != row["department_id"]
            ):
                raise GovernanceError("control_stale")
            self._current(tx, dep, seen=seen, checked=checked)
        checked.add(row["control_id"])

    def _view(self, tx, row):
        usable = False
        reason = None
        if row["state"] == "active":
            try:
                self._current(tx, row)
                usable = True
            except GovernanceError as exc:
                reason = str(exc)
        return {
            "id": str(row["control_id"]),
            "kind": row["kind"],
            "department_id": row["department_id"],
            "revision": row["revision"],
            "state": row["state"],
            "data": row["data"],
            "proposed_by": str(row["proposed_by"]),
            "reviewed_by": str(row["reviewed_by"]) if row["reviewed_by"] else None,
            "proposer_revision": row["proposer_revision"],
            "reviewer_revision": row["reviewer_revision"],
            "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
            "activated_at": row["activated_at"].isoformat() if row["activated_at"] else None,
            "review_evidence_ref": str(row["review_evidence_ref"])
            if row["review_evidence_ref"]
            else None,
            "usable": usable,
            "unresolved_reason": reason,
            "evidence_mode": "organization_reviewer_attestation",
            "legal_clearance": False,
        }

    def _save(self, tx, row):
        view = self._view(tx, row)
        tx.execute(
            "INSERT INTO governance_control_history(control_id,revision,snapshot) VALUES (%s,%s,%s)",
            (row["control_id"], row["revision"], Jsonb(view)),
        )
        from pii_redactor.governance.processing_controls import ProcessingControls

        ProcessingControls(self.store).invalidate_control(tx, row["control_id"])
        return view

    def create(self, principal, command_key, request):
        data = _validated(self.input_model, request)
        payload = data.model_dump(mode="json")

        def effect(tx, member, _):
            for binding in data.dependencies:
                dep = self._row(tx, member, binding.id, kind=False)
                if (
                    dep["department_id"] != data.department_id
                    or dep["revision"] != binding.revision
                ):
                    raise GovernanceError("control_stale")
            if data.supersedes:
                previous = self._row(tx, member, data.supersedes.id)
                check_revision(previous, data.supersedes.revision)
                if previous["department_id"] != data.department_id or previous["state"] != "active":
                    raise GovernanceError("invalid_transition")
            row = tx.execute(
                """INSERT INTO governance_organization_controls(control_id,organization_id,department_id,kind,data,proposed_by,proposer_revision)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    data.department_id,
                    self.kind,
                    Jsonb(payload),
                    member["member_id"],
                    member["revision"],
                ),
            ).fetchone()
            return self._save(tx, row)

        return run_command(
            self.store,
            principal,
            command_key,
            "activity.create",
            "control.created",
            {"kind": self.kind, "data": payload},
            effect,
            department_id=data.department_id,
        )

    def replace(self, principal, command_key, record_id, expected_revision, request):
        data = _validated(self.input_model, request)
        payload = data.model_dump(mode="json")

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            if row["state"] == "superseded" or data.department_id != row["department_id"]:
                raise GovernanceError("invalid_transition")
            updated = tx.execute(
                """UPDATE governance_organization_controls SET data=%s,state='draft',revision=revision+1,
                proposed_by=%s,proposer_revision=%s,reviewed_by=NULL,reviewer_revision=NULL,review_evidence_ref=NULL,reviewed_at=NULL,activated_at=NULL
                WHERE control_id=%s RETURNING *""",
                (Jsonb(payload), member["member_id"], member["revision"], row["control_id"]),
            ).fetchone()
            return self._save(tx, updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "activity.update",
            "control.replaced",
            {"id": str(identifier(record_id)), "revision": expected_revision, "data": payload},
            effect,
            scope=lambda tx, m: self._row(tx, m, record_id),
        )

    def _transition(
        self,
        principal,
        command_key,
        record_id,
        expected_revision,
        action,
        decision=None,
        evidence_ref=None,
    ):
        permission = "activity.submit" if action == "submit" else "activity.review"

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            needed = {"submit": "draft", "review": "submitted", "activate": "reviewed"}[action]
            if row["state"] != needed:
                raise GovernanceError("invalid_transition")
            self._actor(
                tx,
                row["proposed_by"],
                row["proposer_revision"],
                "activity.create",
                row["department_id"],
            )
            if action != "submit" and row["proposed_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            if action == "submit" and row["proposed_by"] != member["member_id"]:
                raise GovernanceError("separation_required")
            state = "submitted"
            if action == "review":
                state = "reviewed" if decision == "approve" else "rejected"
                row = {
                    **row,
                    "reviewed_by": member["member_id"],
                    "reviewer_revision": member["revision"],
                    "review_evidence_ref": identifier(evidence_ref),
                }
            if action == "activate" or (action == "review" and decision == "approve"):
                self._current(tx, row, require_active=False)
                self.validate_activation(tx, row)
            if action == "activate":
                state = "active"
                if row["data"]["supersedes"]:
                    previous = row["data"]["supersedes"]
                    old = self._row(tx, member, previous["id"])
                    check_revision(old, previous["revision"])
                    if old["state"] != "active" or old["department_id"] != row["department_id"]:
                        raise GovernanceError("control_stale")
                    old = tx.execute(
                        "UPDATE governance_organization_controls SET state='superseded',revision=revision+1 WHERE control_id=%s RETURNING *",
                        (old["control_id"],),
                    ).fetchone()
                    self._save(tx, old)
            updated = tx.execute(
                """UPDATE governance_organization_controls SET state=%s,revision=revision+1,reviewed_by=%s,
                reviewer_revision=%s,review_evidence_ref=%s,
                reviewed_at=CASE WHEN %s='review' THEN clock_timestamp() ELSE reviewed_at END,
                activated_at=CASE WHEN %s='activate' THEN clock_timestamp() ELSE activated_at END
                WHERE control_id=%s RETURNING *""",
                (
                    state,
                    row["reviewed_by"],
                    row["reviewer_revision"],
                    row["review_evidence_ref"],
                    action,
                    action,
                    row["control_id"],
                ),
            ).fetchone()
            return self._save(tx, updated)

        return run_command(
            self.store,
            principal,
            command_key,
            permission,
            "control." + action,
            {
                "id": str(identifier(record_id)),
                "revision": expected_revision,
                "decision": decision,
                "evidence_ref": str(identifier(evidence_ref)) if evidence_ref else None,
            },
            effect,
            scope=lambda tx, m: self._row(tx, m, record_id),
        )

    def validate_activation(self, tx, row):
        """Subclasses add obligations beyond the shared lifecycle checks."""

    def submit(self, principal, command_key, record_id, expected_revision):
        return self._transition(principal, command_key, record_id, expected_revision, "submit")

    def review(self, principal, command_key, record_id, expected_revision, decision, evidence_ref):
        if decision not in {"approve", "reject"}:
            raise GovernanceError("invalid_request")
        identifier(evidence_ref)
        return self._transition(
            principal, command_key, record_id, expected_revision, "review", decision, evidence_ref
        )

    def activate(self, principal, command_key, record_id, expected_revision):
        return self._transition(principal, command_key, record_id, expected_revision, "activate")

    def get(self, principal, record_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            return self._view(tx, self._row(tx, member, record_id))

    def list(self, principal, department_id, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            require_member(
                tx, self.store.organization_id, principal, "retention.read", department_id
            )
            rows = tx.execute(
                """SELECT * FROM governance_organization_controls WHERE organization_id=%s AND department_id=%s AND kind=%s
                AND (%s::uuid IS NULL OR control_id>%s::uuid) ORDER BY control_id LIMIT %s""",
                (
                    self.store.organization_id,
                    department_id,
                    self.kind,
                    identifier(cursor) if cursor else None,
                    identifier(cursor) if cursor else None,
                    limit + 1,
                ),
            ).fetchall()
            return {
                "items": [self._view(tx, r) for r in rows[:limit]],
                "next_cursor": str(rows[limit - 1]["control_id"]) if len(rows) > limit else None,
            }

    def require_active(self, principal, record_id, expected_revision):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            row = self._row(tx, member, record_id)
            check_revision(row, expected_revision)
            self._current(tx, row)
            return self._view(tx, row)

    def history(self, principal, record_id, *, after=0, limit=50):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            row = self._row(tx, member, record_id)
            entries = tx.execute(
                "SELECT snapshot FROM governance_control_history WHERE control_id=%s AND revision>%s ORDER BY revision LIMIT %s",
                (row["control_id"], after, limit + 1),
            ).fetchall()
            return {
                "items": [e["snapshot"] for e in entries[:limit]],
                "next_cursor": entries[limit - 1]["snapshot"]["revision"]
                if len(entries) > limit
                else None,
                "historical_only": True,
            }

    def assert_active(self, tx, record_id, expected_revision, department_id):
        """Fence a parent-owned processing action inside its existing transaction.

        Caller must hold Store.lock(tx) and check the action's own permission.
        This method neither grants processing authority nor commits anything.
        """
        row = tx.execute(
            "SELECT * FROM governance_organization_controls WHERE control_id=%s AND organization_id=%s FOR SHARE",
            (identifier(record_id), self.store.organization_id),
        ).fetchone()
        if not row or row["kind"] != self.kind or row["department_id"] != department_id:
            raise GovernanceError("record_unavailable")
        check_revision(row, expected_revision)
        self._current(tx, row)
        return self._view(tx, row)

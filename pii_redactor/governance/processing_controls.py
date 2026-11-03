"""Reviewed activity controls and immutable execution snapshots, never legal verdicts."""

from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, field_validator, model_validator

from pii_redactor.governance.commands import check_revision, digest, identifier, run_command
from pii_redactor.governance.control_register import Binding, Register
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.policy_register import CONTROL_KEYS, LegalControls
from pii_redactor.governance.registry import RecordID, _validated

_CHECKING = ContextVar("processing_control_fences", default=frozenset())


class ProcessingInput(ClosedModel):
    activity_id: RecordID
    activity_revision: int = Field(ge=1)
    controls: list[Binding] = Field(min_length=1, max_length=64)
    evidence_ref: RecordID
    expires_at: datetime = Field(strict=False)

    @field_validator("expires_at")
    @classmethod
    def expiry(cls, value):
        now = datetime.now(UTC)
        if value.tzinfo is None or not now < value <= now + timedelta(days=366):
            raise ValueError("bounded zoned expiry required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def distinct(self):
        if len({c.id for c in self.controls}) != len(self.controls):
            raise ValueError("duplicate control")
        return self


class ProcessingControls:
    def __init__(self, store, *, case_checker=None):
        self.store, self.case_checker = store, case_checker

    def _activity(self, tx, activity_id, revision):
        row = tx.execute(
            "SELECT * FROM governance_activities WHERE activity_id=%s AND organization_id=%s FOR SHARE",
            (identifier(activity_id), self.store.organization_id),
        ).fetchone()
        if not row or row["state"] != "active" or row["revision"] != revision:
            raise GovernanceError("activity_authority_changed")
        return row

    def _row(self, tx, member, binding_id):
        row = tx.execute(
            "SELECT * FROM governance_processing_bindings WHERE binding_id=%s AND organization_id=%s FOR UPDATE",
            (identifier(binding_id), self.store.organization_id),
        ).fetchone()
        if not row or not in_scope(member, row["department_id"]):
            raise GovernanceError("record_unavailable")
        return row

    def _actor(self, tx, row, *, reviewer=False):
        prefix = "reviewer" if reviewer else "proposer"
        member = row["reviewed_by"] if reviewer else row["proposed_by"]
        Register(self.store)._actor(
            tx,
            member,
            row[prefix + "_revision"],
            "activity.review" if reviewer else "activity.create",
            row["department_id"],
        )

    def _registers(self):
        from pii_redactor.governance.assessments import Assessments
        from pii_redactor.governance.incidents import Incidents
        from pii_redactor.governance.policy_register import Policies
        from pii_redactor.governance.processors import Processors
        from pii_redactor.governance.responsibilities import Responsibilities
        from pii_redactor.governance.transfers import Transfers

        return {
            cls.kind: cls(self.store, case_checker=self.case_checker)
            for cls in (
                Assessments,
                Incidents,
                Policies,
                Processors,
                Responsibilities,
                Transfers,
                LegalControls,
            )
        }

    def _controls(self, tx, bindings, department):
        registers = self._registers()
        legal = registers["legal"]
        views, versions, materials, keys, visiting = [], {}, {}, set(), set()

        def collect(control_id, revision):
            key = str(identifier(control_id))
            if key in visiting or len(versions) >= 256:
                raise GovernanceError("processing_controls_stale")
            if key in versions:
                if versions[key] != revision:
                    raise GovernanceError("processing_controls_stale")
                return
            visiting.add(key)
            row = tx.execute(
                "SELECT * FROM governance_organization_controls WHERE control_id=%s AND organization_id=%s",
                (identifier(control_id), self.store.organization_id),
            ).fetchone()
            if not row or row["kind"] not in registers:
                raise GovernanceError("record_unavailable")
            reg = registers[row["kind"]]
            view = reg.assert_active(tx, control_id, revision, department)
            history = tx.execute(
                "SELECT snapshot FROM governance_control_history WHERE control_id=%s AND revision=%s",
                (row["control_id"], revision),
            ).fetchone()
            fields = (
                "data",
                "state",
                "revision",
                "kind",
                "department_id",
                "proposed_by",
                "proposer_revision",
                "reviewed_by",
                "reviewer_revision",
                "review_evidence_ref",
            )
            if not history or any(history["snapshot"].get(name) != view[name] for name in fields):
                raise GovernanceError("processing_controls_integrity")
            reg.validate_activation(tx, row)
            if legal._pending_obligations(tx, row):
                raise GovernanceError("operational_obligations_unresolved")
            versions[key] = revision
            materials[key] = view
            for dependency in row["data"]["dependencies"]:
                collect(dependency["id"], dependency["revision"])
            visiting.remove(key)
            return view

        for reference in bindings:
            view = collect(reference["id"], reference["revision"])
            if view is None:
                row = tx.execute(
                    "SELECT * FROM governance_organization_controls WHERE control_id=%s",
                    (identifier(reference["id"]),),
                ).fetchone()
                view = registers[row["kind"]]._view(tx, row)
            if view["kind"] == "legal":
                key = view["data"]["control_key"]
                if key in keys:
                    raise GovernanceError("processing_controls_incomplete")
                keys.add(key)
            views.append(view)
        if keys != set(CONTROL_KEYS):
            raise GovernanceError("processing_controls_incomplete")
        # An omitted live incident is still an unresolved organization obligation.
        incidents = tx.execute(
            "SELECT * FROM governance_organization_controls WHERE organization_id=%s AND department_id=%s AND kind='incident' AND state NOT IN ('superseded','rejected')",
            (self.store.organization_id, department),
        ).fetchall()
        if any(legal._pending_obligations(tx, row) for row in incidents):
            raise GovernanceError("operational_obligations_unresolved")
        selected = {str(identifier(item["id"])) for item in bindings}
        return views, versions, [materials[key] for key in sorted(materials) if key not in selected]

    @staticmethod
    def _record(row):
        return {
            "id": str(row["binding_id"]),
            "revision": row["revision"],
            "state": row["state"],
            "activity_id": str(row["activity_id"]),
            "activity_revision": row["activity_revision"],
            "department_id": row["department_id"],
            "data": row["data"],
            "data_digest": row["data_digest"],
            "proposed_by": str(row["proposed_by"]),
            "proposer_revision": row["proposer_revision"],
            "reviewed_by": str(row["reviewed_by"]) if row["reviewed_by"] else None,
            "reviewer_revision": row["reviewer_revision"],
            "review_digest": row["review_digest"],
            "review_evidence_ref": str(row["review_evidence_ref"])
            if row["review_evidence_ref"]
            else None,
        }

    def _material(self, tx, row):
        if (
            digest(row["data"]) != row["data_digest"]
            or str(row["activity_id"]) != row["data"]["activity_id"]
            or row["activity_revision"] != row["data"]["activity_revision"]
        ):
            raise GovernanceError("processing_controls_integrity")
        activity = self._activity(tx, row["activity_id"], row["activity_revision"])
        if activity["department_id"] != row["department_id"]:
            raise GovernanceError("processing_controls_stale")
        self._actor(tx, row)
        controls, versions, dependencies = self._controls(
            tx, row["data"]["controls"], row["department_id"]
        )
        if (
            datetime.fromisoformat(row["data"]["expires_at"])
            <= tx.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        ):
            raise GovernanceError("processing_controls_expired")
        return {
            "id": str(row["binding_id"]),
            "activity_id": str(row["activity_id"]),
            "activity_revision": row["activity_revision"],
            "department_id": row["department_id"],
            "data_digest": row["data_digest"],
            "controls": controls,
            "dependencies": dependencies,
            "control_versions": versions,
            "expires_at": row["data"]["expires_at"],
        }

    def _current(self, tx, row):
        if row["state"] != "active":
            raise GovernanceError("processing_controls_stale")
        checking = _CHECKING.get()
        if row["binding_id"] in checking or len(checking) >= 32:
            raise GovernanceError("processing_controls_cycle")
        token = _CHECKING.set(checking | {row["binding_id"]})
        try:
            return self._current_material(tx, row)
        finally:
            _CHECKING.reset(token)

    def _current_material(self, tx, row):
        material = self._material(tx, row)
        self._actor(tx, row, reviewer=True)
        history = tx.execute(
            "SELECT snapshot FROM governance_processing_history WHERE binding_id=%s AND revision=%s",
            (row["binding_id"], row["revision"]),
        ).fetchone()
        if (
            not history
            or history["snapshot"] != self._record(row)
            or digest(material) != row["review_digest"]
        ):
            raise GovernanceError("processing_controls_integrity")
        return {
            **material,
            "revision": row["revision"],
            "digest": digest(material),
            "reviewed_by": str(row["reviewed_by"]),
            "reviewer_revision": row["reviewer_revision"],
            "review_evidence_ref": str(row["review_evidence_ref"]),
        }

    def _view(self, tx, row):
        view = self._record(row)
        view.update(usable=False, unresolved_reason=None, legal_clearance=False)
        if row["state"] == "active":
            try:
                self._current(tx, row)
                view["usable"] = True
            except GovernanceError as error:
                view["unresolved_reason"] = error.code
        return view

    def _save(self, tx, row):
        tx.execute(
            "INSERT INTO governance_processing_history(binding_id,revision,snapshot) VALUES (%s,%s,%s)",
            (row["binding_id"], row["revision"], Jsonb(self._record(row))),
        )
        return self._view(tx, row)

    def create(self, principal, command_key, request):
        data = _validated(ProcessingInput, request)

        def scope(tx, member):
            activity = self._activity(tx, data.activity_id, data.activity_revision)
            if not in_scope(member, activity["department_id"]):
                raise GovernanceError("record_unavailable")
            return activity

        def effect(tx, member, activity):
            row = tx.execute(
                """INSERT INTO governance_processing_bindings(binding_id,organization_id,
                activity_id,activity_revision,department_id,data,data_digest,proposed_by,proposer_revision)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    data.activity_id,
                    data.activity_revision,
                    activity["department_id"],
                    Jsonb(data.model_dump(mode="json")),
                    digest(data.model_dump(mode="json")),
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
            "processing.created",
            data.model_dump(mode="json"),
            effect,
            scope=scope,
        )

    def replace(self, principal, command_key, binding_id, revision, request):
        data = _validated(ProcessingInput, request)

        def effect(tx, member, row):
            check_revision(row, revision)
            activity = self._activity(tx, data.activity_id, data.activity_revision)
            if (
                row["activity_id"] != identifier(data.activity_id)
                or activity["department_id"] != row["department_id"]
            ):
                raise GovernanceError("processing_controls_stale")
            self._cancel(tx, binding_id=row["binding_id"])
            updated = tx.execute(
                """UPDATE governance_processing_bindings SET revision=revision+1,
                state='draft',activity_revision=%s,data=%s,data_digest=%s,proposed_by=%s,proposer_revision=%s,
                reviewed_by=NULL,reviewer_revision=NULL,review_evidence_ref=NULL,review_digest=NULL
                WHERE binding_id=%s RETURNING *""",
                (
                    data.activity_revision,
                    Jsonb(data.model_dump(mode="json")),
                    digest(data.model_dump(mode="json")),
                    member["member_id"],
                    member["revision"],
                    row["binding_id"],
                ),
            ).fetchone()
            return self._save(tx, updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "activity.create",
            "processing.replaced",
            {
                "id": str(identifier(binding_id)),
                "revision": revision,
                "data": data.model_dump(mode="json"),
            },
            effect,
            scope=lambda tx, member: self._row(tx, member, binding_id),
        )

    def preview(self, principal, binding_id, revision):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "activity.review")
            row = self._row(tx, member, binding_id)
            check_revision(row, revision)
            if row["state"] != "submitted" or row["proposed_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            material = self._material(tx, row)
            tx.execute(
                """INSERT INTO governance_processing_previews(binding_id,revision,reviewer_id,
                reviewer_revision,snapshot_digest) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (
                    row["binding_id"],
                    revision,
                    member["member_id"],
                    member["revision"],
                    digest(material),
                ),
            )
            return {
                **material,
                "revision": revision,
                "digest": digest(material),
                "legal_clearance": False,
            }

    def _transition(
        self, principal, key, binding_id, revision, action, decision=None, evidence_ref=None
    ):
        permission = "activity.submit" if action == "submit" else "activity.review"

        def effect(tx, member, row):
            check_revision(row, revision)
            expected = {"submit": "draft", "review": "submitted", "activate": "reviewed"}[action]
            if row["state"] != expected:
                raise GovernanceError("invalid_transition")
            self._actor(tx, row)
            if (action == "submit") != (row["proposed_by"] == member["member_id"]):
                raise GovernanceError("separation_required")
            state, reviewer, reviewer_version, review_digest, reference = (
                "submitted",
                None,
                None,
                None,
                None,
            )
            if action == "review":
                state = "reviewed" if decision == "approve" else "rejected"
                reviewer, reviewer_version, reference = (
                    member["member_id"],
                    member["revision"],
                    identifier(evidence_ref),
                )
                if decision == "approve":
                    material = self._material(tx, row)
                    review_digest = digest(material)
                    preview = tx.execute(
                        """SELECT reviewer_revision FROM governance_processing_previews
                        WHERE binding_id=%s AND revision=%s AND reviewer_id=%s AND snapshot_digest=%s""",
                        (row["binding_id"], row["revision"], member["member_id"], review_digest),
                    ).fetchone()
                    if not preview or preview["reviewer_revision"] != member["revision"]:
                        raise GovernanceError("processing_preview_required")
            if action == "activate":
                state = "active"
                self._actor(tx, row, reviewer=True)
                if digest(self._material(tx, row)) != row["review_digest"]:
                    raise GovernanceError("processing_controls_stale")
                previous = tx.execute(
                    """SELECT * FROM governance_processing_bindings WHERE organization_id=%s
                    AND activity_id=%s AND activity_revision=%s AND state='active' AND binding_id<>%s FOR UPDATE""",
                    (
                        self.store.organization_id,
                        row["activity_id"],
                        row["activity_revision"],
                        row["binding_id"],
                    ),
                ).fetchall()
                for old in previous:
                    self._cancel(tx, binding_id=old["binding_id"])
                    old = tx.execute(
                        "UPDATE governance_processing_bindings SET state='superseded',revision=revision+1 WHERE binding_id=%s RETURNING *",
                        (old["binding_id"],),
                    ).fetchone()
                    self._save(tx, old)
                reviewer, reviewer_version, reference, review_digest = (
                    row["reviewed_by"],
                    row["reviewer_revision"],
                    row["review_evidence_ref"],
                    row["review_digest"],
                )
            updated = tx.execute(
                """UPDATE governance_processing_bindings SET state=%s,revision=revision+1,
                reviewed_by=%s,reviewer_revision=%s,review_evidence_ref=%s,review_digest=%s
                WHERE binding_id=%s RETURNING *""",
                (state, reviewer, reviewer_version, reference, review_digest, row["binding_id"]),
            ).fetchone()
            view = self._save(tx, updated)
            if state == "active" and not view["usable"]:
                raise GovernanceError("processing_controls_stale")
            return view

        return run_command(
            self.store,
            principal,
            key,
            permission,
            "processing." + action,
            {
                "id": str(identifier(binding_id)),
                "revision": revision,
                "decision": decision,
                "evidence_ref": str(identifier(evidence_ref)) if evidence_ref else None,
            },
            effect,
            scope=lambda tx, member: self._row(tx, member, binding_id),
        )

    def submit(self, principal, key, binding_id, revision):
        return self._transition(principal, key, binding_id, revision, "submit")

    def review(self, principal, key, binding_id, revision, decision, evidence_ref):
        if decision not in {"approve", "reject"}:
            raise GovernanceError("invalid_request")
        return self._transition(
            principal, key, binding_id, revision, "review", decision, evidence_ref
        )

    def activate(self, principal, key, binding_id, revision):
        return self._transition(principal, key, binding_id, revision, "activate")

    def get(self, principal, binding_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            return self._view(tx, self._row(tx, member, binding_id))

    def history(self, principal, binding_id, *, after=0, limit=50):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "retention.read")
            row = self._row(tx, member, binding_id)
            entries = tx.execute(
                """SELECT revision,snapshot FROM governance_processing_history
                WHERE binding_id=%s AND revision>%s ORDER BY revision LIMIT %s""",
                (row["binding_id"], after, limit + 1),
            ).fetchall()
            return {
                "items": [entry["snapshot"] for entry in entries[:limit]],
                "next_cursor": entries[limit - 1]["revision"] if len(entries) > limit else None,
                "historical_only": True,
            }

    def list(self, principal, department_id, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100 or department_id == "*":
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            require_member(
                tx, self.store.organization_id, principal, "retention.read", department_id
            )
            rows = tx.execute(
                """SELECT * FROM governance_processing_bindings WHERE organization_id=%s AND department_id=%s
                AND (%s::uuid IS NULL OR binding_id>%s::uuid) ORDER BY binding_id LIMIT %s""",
                (
                    self.store.organization_id,
                    department_id,
                    identifier(cursor) if cursor else None,
                    identifier(cursor) if cursor else None,
                    limit + 1,
                ),
            ).fetchall()
            return {
                "items": [self._view(tx, row) for row in rows[:limit]],
                "next_cursor": str(rows[limit - 1]["binding_id"]) if len(rows) > limit else None,
            }

    def require_activity(self, tx, collection, *, required=None):
        self.store.lock(tx)
        if not collection or collection["organization_id"] != self.store.organization_id:
            raise GovernanceError("record_unavailable")
        row = tx.execute(
            """SELECT * FROM governance_processing_bindings WHERE organization_id=%s
            AND activity_id=%s AND activity_revision=%s AND state='active' FOR SHARE""",
            (
                self.store.organization_id,
                collection["activity_id"],
                collection["activity_revision"],
            ),
        ).fetchone()
        required = self.store.production_operations_required if required is None else required
        if not row:
            if required:
                raise GovernanceError("processing_controls_required")
            return None
        if row["department_id"] != collection["department_id"]:
            raise GovernanceError("processing_controls_stale")
        return self._current(tx, row)

    def activities(self, principal, department_id, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100 or department_id == "*":
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            require_member(
                tx, self.store.organization_id, principal, "activity.read", department_id
            )
            rows = tx.execute(
                """SELECT activity_id,revision,data FROM governance_activities WHERE organization_id=%s
                AND department_id=%s AND state='active' AND (%s::uuid IS NULL OR activity_id>%s::uuid)
                ORDER BY activity_id LIMIT %s""",
                (
                    self.store.organization_id,
                    department_id,
                    identifier(cursor) if cursor else None,
                    identifier(cursor) if cursor else None,
                    limit + 1,
                ),
            ).fetchall()
            return {
                "items": [
                    {
                        "id": str(row["activity_id"]),
                        "revision": row["revision"],
                        "purpose": row["data"]["purpose"],
                    }
                    for row in rows[:limit]
                ],
                "next_cursor": str(rows[limit - 1]["activity_id"]) if len(rows) > limit else None,
            }

    def catalog(self, principal, department_id, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100 or department_id == "*":
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            require_member(
                tx, self.store.organization_id, principal, "retention.read", department_id
            )
            legal = tx.execute(
                """SELECT * FROM governance_organization_controls WHERE organization_id=%s
                AND department_id=%s AND kind='legal' AND state='active' ORDER BY control_id""",
                (self.store.organization_id, department_id),
            ).fetchall()
            if len(legal) > len(CONTROL_KEYS):
                raise GovernanceError("processing_controls_stale")
            optional = tx.execute(
                """SELECT * FROM governance_organization_controls WHERE organization_id=%s
                AND department_id=%s AND kind<>'legal' AND state='active'
                AND (%s::uuid IS NULL OR control_id>%s::uuid) ORDER BY control_id LIMIT %s""",
                (
                    self.store.organization_id,
                    department_id,
                    identifier(cursor) if cursor else None,
                    identifier(cursor) if cursor else None,
                    limit + 1,
                ),
            ).fetchall()
            registers = self._registers()
            return {
                "legal": [registers[row["kind"]]._view(tx, row) for row in legal],
                "items": [registers[row["kind"]]._view(tx, row) for row in optional[:limit]],
                "required_keys": list(CONTROL_KEYS),
                "next_cursor": str(optional[limit - 1]["control_id"])
                if len(optional) > limit
                else None,
                "legal_clearance": False,
            }

    def attach_instruction(self, tx, instruction):
        collection = tx.execute(
            "SELECT * FROM governance_collections WHERE collection_id=%s AND organization_id=%s",
            (instruction["collection_id"], self.store.organization_id),
        ).fetchone()
        snapshot = self.require_activity(tx, collection)
        if snapshot:
            tx.execute(
                """INSERT INTO governance_instruction_controls(instruction_id,organization_id,binding_id,
                binding_revision,binding_digest,snapshot) VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    instruction["instruction_id"],
                    self.store.organization_id,
                    snapshot["id"],
                    snapshot["revision"],
                    snapshot["digest"],
                    Jsonb(snapshot),
                ),
            )
        return snapshot

    def instruction_snapshot(self, tx, instruction_id):
        row = tx.execute(
            "SELECT * FROM governance_instruction_controls WHERE instruction_id=%s AND organization_id=%s",
            (instruction_id, self.store.organization_id),
        ).fetchone()
        if not row:
            return None
        snapshot = row["snapshot"]
        if not isinstance(snapshot, dict):
            raise GovernanceError("processing_controls_integrity")
        metadata = {"revision", "digest", "reviewed_by", "reviewer_revision", "review_evidence_ref"}
        material = {key: value for key, value in snapshot.items() if key not in metadata}
        if (
            snapshot.get("id") != str(row["binding_id"])
            or snapshot.get("revision") != row["binding_revision"]
            or snapshot.get("digest") != row["binding_digest"]
            or digest(material) != row["binding_digest"]
        ):
            raise GovernanceError("processing_controls_integrity")
        return snapshot

    def fence_instruction(self, tx, instruction, *, allow_committed=False):
        snapshot = self.instruction_snapshot(tx, instruction["instruction_id"])
        if not snapshot:
            if self.store.production_operations_required and not allow_committed:
                raise GovernanceError("processing_controls_required")
            return
        if allow_committed:
            # Reconciliation proves an immutable outcome elsewhere; this grants no new work.
            return
        collection = tx.execute(
            "SELECT * FROM governance_collections WHERE collection_id=%s AND organization_id=%s",
            (instruction["collection_id"], self.store.organization_id),
        ).fetchone()
        current = self.require_activity(tx, collection, required=True)
        if any(current[name] != snapshot[name] for name in ("id", "revision", "digest")):
            raise GovernanceError("processing_controls_stale")

    def _cancel(self, tx, *, binding_id=None, control_id=None):
        rows = tx.execute(
            """SELECT i.instruction_id FROM governance_execution_instructions i
            JOIN governance_instruction_controls b USING(instruction_id) WHERE i.organization_id=%s
            AND i.state IN ('proposed','pending','running','unknown')
            AND NOT EXISTS(SELECT 1 FROM governance_execution_outcomes o WHERE o.instruction_id=i.instruction_id)
            AND (%s::uuid IS NULL OR b.binding_id=%s::uuid)
            AND (%s::text IS NULL OR (b.snapshot->'control_versions') ? %s::text) FOR UPDATE OF i""",
            (
                self.store.organization_id,
                binding_id,
                binding_id,
                str(control_id) if control_id else None,
                str(control_id) if control_id else None,
            ),
        ).fetchall()
        for item in rows:
            instruction_id = item["instruction_id"]
            updated = tx.execute(
                "UPDATE governance_execution_instructions SET state='failed',revision=revision+1 WHERE instruction_id=%s RETURNING revision",
                (instruction_id,),
            ).fetchone()
            tx.execute(
                """UPDATE governance_execution_tasks SET state='failed',worker_id=NULL,lease_token=NULL,
                lease_until=NULL,last_error='processing_authority_changed',updated_at=clock_timestamp() WHERE instruction_id=%s""",
                (instruction_id,),
            )
            event = self.store.append_event(
                tx,
                event_code="processing.authority_changed",
                target_id=instruction_id,
                revision=updated["revision"],
            )
            tx.execute(
                "INSERT INTO governance_outbox(event_id,event_code,payload) VALUES (%s,%s,%s)",
                (
                    event,
                    "processing.authority_changed",
                    Jsonb({"record_id": str(instruction_id), "revision": updated["revision"]}),
                ),
            )

    def invalidate_control(self, tx, control_id):
        self.store.lock(tx)
        self._cancel(tx, control_id=control_id)

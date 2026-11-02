"""Append-only, exact-version consent and current processing authority."""

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, model_validator

from pii_redactor.governance.commands import check_revision, digest, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.registry import RecordID, _validated
from pii_redactor.governance.subjects import require_subject_actor


class NoticeProof(ClosedModel):
    notice_id: RecordID
    notice_revision: int = Field(ge=1)
    notice_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    presentation_id: RecordID


class ConsentScope(ClosedModel):
    purpose_version: RecordID
    categories: list[str] = Field(min_length=1, max_length=24)
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def distinct_choices(self):
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("distinct categories required")
        return self


class OfflineConsentInput(ClosedModel):
    subject_id: RecordID
    scope: ConsentScope
    action: Literal["grant", "refuse", "withdraw"]
    mode: Literal["offline_withdrawal", "representative"]
    source_evidence_ref: RecordID
    capacity_evidence_ref: RecordID | None = None
    representative_authority_ref: RecordID | None = None
    source_received_at: Annotated[datetime, Field(strict=False)]

    @model_validator(mode="after")
    def evidenced_mode(self):
        if self.source_received_at.tzinfo is None or self.source_received_at > datetime.now(UTC):
            raise ValueError("valid receipt time required")
        if self.mode == "offline_withdrawal" and self.action != "withdraw":
            raise ValueError("withdrawal only")
        if self.mode == "representative" and (
            not self.capacity_evidence_ref or not self.representative_authority_ref
        ):
            raise ValueError("representative authority required")
        return self


class PropagationScope(ClosedModel):
    consent_event_id: RecordID
    event_revision: int = Field(ge=1)
    recipient_ordinal: int = Field(ge=1)
    expected_state: Literal["pending", "failed"]


class Consent:
    def __init__(self, store):
        self.store = store

    def _snapshot(self, tx, notice_id):
        notice_id = identifier(notice_id)
        row = tx.execute(
            """SELECT n.*,a.state AS activity_state,a.revision AS activity_revision,
            a.department_id,a.data AS activity_data,a.review AS activity_review
            FROM governance_notices n JOIN governance_activities a ON a.activity_id=n.activity_id
            WHERE n.notice_id=%s AND n.organization_id=%s AND a.organization_id=%s FOR SHARE OF n,a""",
            (notice_id, self.store.organization_id, self.store.organization_id),
        ).fetchone()
        if not row or row["state"] != "published" or row["activity_state"] != "active":
            raise GovernanceError("notice_unavailable")
        if (
            digest(row["data"]) != row["content_digest"]
            or digest(row["activity_data"]) != row["payload_digest"]
            or not row["activity_review"]
            or row["activity_review"].get("notice_id") != str(notice_id)
            or (
                row["activity_data"].get("general_basis") != "consent"
                and row["activity_data"].get("sensitive_condition") != "explicit_consent"
            )
        ):
            raise GovernanceError("notice_scope_mismatch")
        tx.execute(
            """INSERT INTO governance_consent_purposes(purpose_version,organization_id,activity_id,
            activity_revision,department_id,notice_revision,notice_digest,activity_digest,purpose,categories,recipients)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(purpose_version) DO NOTHING""",
            (
                notice_id,
                self.store.organization_id,
                row["activity_id"],
                row["activity_revision"],
                row["department_id"],
                row["revision"],
                row["content_digest"],
                row["payload_digest"],
                row["activity_data"]["purpose"],
                Jsonb(row["activity_data"]["categories"]),
                Jsonb(row["activity_data"]["recipient_refs"]),
            ),
        )
        purpose = self._purpose(tx, notice_id)
        if purpose["activity_revision"] != row["activity_revision"]:
            raise GovernanceError("notice_scope_mismatch")
        return purpose, row

    def _purpose(self, tx, purpose_version):
        row = tx.execute(
            "SELECT * FROM governance_consent_purposes WHERE purpose_version=%s AND organization_id=%s",
            (identifier(purpose_version), self.store.organization_id),
        ).fetchone()
        if not row:
            raise GovernanceError("notice_unavailable")
        return row

    @staticmethod
    def _check_categories(purpose, categories):
        if not set(categories).issubset(purpose["categories"]):
            raise GovernanceError("consent_scope_mismatch")

    def available_notices(self, actor, *, limit=50, cursor=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GovernanceError("invalid_request")
        cursor_id = identifier(cursor) if cursor is not None else None
        with self.store.transaction() as tx:
            member = require_subject_actor(tx, self.store.organization_id, actor)
            eligible = """FROM governance_notices n JOIN governance_activities a ON a.activity_id=n.activity_id
                WHERE n.organization_id=%s AND a.organization_id=%s AND a.department_id=ANY(%s)
                AND n.state='published' AND ((a.state='active' AND (a.data->>'general_basis'='consent'
                OR a.data->>'sensitive_condition'='explicit_consent') AND a.review->>'notice_id'=n.notice_id::text)
                OR EXISTS(SELECT 1 FROM governance_consent_events e WHERE e.subject_id=%s AND e.purpose_version=n.notice_id))"""
            values = (
                self.store.organization_id,
                self.store.organization_id,
                member["departments"],
                actor.subject_id,
            )
            after = None
            if cursor_id:
                after = tx.execute(
                    "SELECT n.created_at,n.notice_id " + eligible + " AND n.notice_id=%s",
                    (*values, cursor_id),
                ).fetchone()
                if not after:
                    raise GovernanceError("invalid_request")
            page_filter = " AND (n.created_at,n.notice_id)>(%s,%s)" if after else ""
            page_values = (*values, after["created_at"], after["notice_id"]) if after else values
            rows = tx.execute(
                "SELECT n.notice_id,n.data,n.content_digest,n.revision "
                + eligible
                + page_filter
                + " ORDER BY n.created_at,n.notice_id LIMIT %s",
                (*page_values, limit + 1),
            ).fetchall()
            items = [
                {
                    "notice_id": str(r["notice_id"]),
                    "title": r["data"]["title"],
                    "notice_revision": r["revision"],
                    "notice_digest": r["content_digest"],
                }
                for r in rows[:limit]
            ]
            return {
                "items": items,
                "next_cursor": items[-1]["notice_id"] if len(rows) > limit else None,
            }

    def present(self, actor, notice_id):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            subject = require_subject_actor(tx, self.store.organization_id, actor)
            grant_allowed = True
            try:
                purpose, notice = self._snapshot(tx, notice_id)
            except GovernanceError as error:
                if error.code not in {"notice_unavailable", "notice_scope_mismatch"}:
                    raise
                # A retired purpose must remain available for withdrawal.
                purpose = self._purpose(tx, notice_id)
                notice = tx.execute(
                    """SELECT n.* FROM governance_notices n WHERE n.notice_id=%s
                                    AND n.organization_id=%s AND n.state='published' AND EXISTS(
                                    SELECT 1 FROM governance_consent_events e WHERE e.subject_id=%s
                                    AND e.purpose_version=n.notice_id)""",
                    (identifier(notice_id), self.store.organization_id, actor.subject_id),
                ).fetchone()
                if not notice or digest(notice["data"]) != purpose["notice_digest"]:
                    raise GovernanceError("notice_unavailable") from None
                grant_allowed = False
            if purpose["department_id"] not in subject["departments"]:
                raise GovernanceError("record_unavailable")
            presentation_id = uuid4()
            tx.execute(
                """INSERT INTO governance_consent_presentations(presentation_id,organization_id,subject_id,
                       session_id,link_revision,purpose_version,notice_digest,expires_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,clock_timestamp()+interval '15 minutes')""",
                (
                    presentation_id,
                    self.store.organization_id,
                    actor.subject_id,
                    actor.session_id,
                    actor.link_revision,
                    purpose["purpose_version"],
                    purpose["notice_digest"],
                ),
            )
            self.store.append_event(
                tx,
                event_code="consent.notice_presented",
                actor_id=actor.subject_id,
                target_id=presentation_id,
                revision=purpose["notice_revision"],
            )
            return {
                "notice_proof": {
                    "notice_id": str(purpose["purpose_version"]),
                    "notice_revision": purpose["notice_revision"],
                    "notice_digest": purpose["notice_digest"],
                    "presentation_id": str(presentation_id),
                },
                "title": notice["data"]["title"],
                "body": notice["data"]["body"],
                "language": notice["data"]["language"],
                "purpose": purpose["purpose"],
                "purpose_version": str(purpose["purpose_version"]),
                "grant_allowed": grant_allowed,
                "categories": purpose["categories"],
                "effective": self.effective(tx, actor.subject_id, purpose["purpose_version"]),
            }

    def effective(self, tx, subject_id, purpose_version):
        """Call in the same transaction as processing; this method takes its guard."""
        self.store.lock(tx)
        subject_id, purpose_version = identifier(subject_id), identifier(purpose_version)
        subject = tx.execute(
            "SELECT * FROM governance_subjects WHERE subject_id=%s AND organization_id=%s FOR SHARE",
            (subject_id, self.store.organization_id),
        ).fetchone()
        purpose = self._purpose(tx, purpose_version)
        current = tx.execute(
            """SELECT e.* FROM governance_consent_current c JOIN governance_consent_events e
                             ON e.consent_event_id=c.consent_event_id WHERE c.subject_id=%s AND c.purpose_version=%s""",
            (subject_id, purpose_version),
        ).fetchone()
        reason = "no_consent"
        if not subject or subject["state"] != "resolved":
            reason = "identity_unresolved"
        elif current:
            if current["action"] != "grant":
                reason = "withdrawn" if current["action"] == "withdraw" else "refused"
            elif current["link_revision"] != subject["revision"]:
                reason = "identity_changed"
            else:
                active = tx.execute(
                    """SELECT a.* FROM governance_activities a JOIN governance_notices n ON n.activity_id=a.activity_id
                                    WHERE n.notice_id=%s AND n.organization_id=%s AND a.organization_id=%s
                                    AND n.state='published' AND a.state='active' AND a.revision=%s FOR SHARE OF a,n""",
                    (
                        purpose_version,
                        self.store.organization_id,
                        self.store.organization_id,
                        purpose["activity_revision"],
                    ),
                ).fetchone()
                if (
                    active
                    and digest(active["data"]) == purpose["activity_digest"]
                    and active["review"].get("notice_id") == str(purpose_version)
                ):
                    reason = "granted"
                else:
                    reason = "purpose_changed"
        propagation = []
        if current:
            rows = tx.execute(
                """SELECT p.propagation_id,p.recipient_ordinal,p.state,e.revision,e.consent_event_id FROM governance_consent_propagation p
                JOIN governance_consent_events e ON e.consent_event_id=p.consent_event_id
                WHERE e.subject_id=%s AND e.purpose_version=%s ORDER BY e.revision,p.recipient_ordinal""",
                (subject_id, purpose_version),
            ).fetchall()
            propagation = [
                {
                    "id": str(r["propagation_id"]),
                    "recipient": r["recipient_ordinal"],
                    "event_revision": r["revision"],
                    "consent_event_id": str(r["consent_event_id"]),
                    "state": r["state"],
                    "verification_mode": "reviewer_attested_external"
                    if r["state"] == "verified"
                    else None,
                }
                for r in rows
            ]
        if reason == "granted" and any(r["state"] != "verified" for r in propagation):
            reason = (
                "propagation_failed"
                if any(r["state"] == "failed" for r in propagation)
                else "propagation_pending"
            )
        return {
            "allowed": reason == "granted",
            "reason": reason,
            "purpose_version": str(purpose_version),
            "revision": current["revision"] if current else 0,
            "link_revision": subject["revision"] if subject else None,
            "event_id": str(current["consent_event_id"]) if current else None,
            "consent_action": current["action"] if current else None,
            "categories": current["categories"] if current and reason == "granted" else [],
            "propagation": propagation,
            "propagation_complete": all(r["state"] == "verified" for r in propagation),
            "retention_authority": "requires_separate_review",
        }

    def require_processing(
        self, tx, subject_id, purpose_version, categories, *, expected_revision=None
    ):
        state = self.effective(tx, subject_id, purpose_version)
        if (
            not state["allowed"]
            or not isinstance(categories, list)
            or not categories
            or not set(categories).issubset(state["categories"])
        ):
            raise GovernanceError("consent_required")
        if expected_revision is not None and (
            type(expected_revision) is not int or expected_revision != state["revision"]
        ):
            raise GovernanceError("revision_conflict")
        return state

    def _invalidate_queued_authority(self, tx, subject_id, purpose_version, actor_id):
        """Revoke unexecuted authority, while preserving any committed primary proof."""
        self.store.lock(tx)
        instructions = tx.execute(
            """SELECT i.instruction_id FROM governance_execution_instructions i
            JOIN governance_collections c ON c.collection_id=i.collection_id
            WHERE i.organization_id=%s AND c.organization_id=%s AND c.consent_bound
            AND c.subject_id=%s AND c.purpose_version=%s
            AND i.state IN ('proposed','pending','running','unknown')
            AND NOT EXISTS(SELECT 1 FROM governance_execution_outcomes o
                           WHERE o.instruction_id=i.instruction_id)
            ORDER BY i.instruction_id FOR UPDATE OF i""",
            (self.store.organization_id, self.store.organization_id, subject_id, purpose_version),
        ).fetchall()
        if not instructions:
            return
        from pii_redactor.governance.execution import emit

        for instruction in instructions:
            row = tx.execute(
                """UPDATE governance_execution_instructions i SET state='failed',revision=revision+1
                WHERE instruction_id=%s AND organization_id=%s
                AND state IN ('proposed','pending','running','unknown')
                AND NOT EXISTS(SELECT 1 FROM governance_execution_outcomes o
                               WHERE o.instruction_id=i.instruction_id) RETURNING i.*""",
                (instruction["instruction_id"], self.store.organization_id),
            ).fetchone()
            if not row:
                continue
            tx.execute(
                """UPDATE governance_execution_tasks SET state='failed',worker_id=NULL,
                lease_token=NULL,lease_until=NULL,last_error='consent_authority_changed',
                updated_at=clock_timestamp() WHERE instruction_id=%s""",
                (row["instruction_id"],),
            )
            emit(self.store, tx, "execution.consent_invalidated", row, actor_id=actor_id)

    def _append(
        self,
        tx,
        subject_id,
        link_revision,
        purpose,
        scope,
        action,
        *,
        session_id=None,
        staff_actor_id=None,
        offline_case_id=None,
        channel="subject_portal",
        source_received_at=None,
    ):
        previous = tx.execute(
            "SELECT revision FROM governance_consent_current WHERE subject_id=%s AND purpose_version=%s",
            (subject_id, purpose["purpose_version"]),
        ).fetchone()
        revision = previous["revision"] if previous else 0
        if revision != scope.expected_revision:
            raise GovernanceError("revision_conflict")
        eid, revision = uuid4(), revision + 1
        tx.execute(
            """INSERT INTO governance_consent_events(consent_event_id,organization_id,subject_id,purpose_version,
                   revision,link_revision,action,categories,notice_revision,notice_digest,channel,session_id,
                   staff_actor_id,offline_case_id,source_received_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                eid,
                self.store.organization_id,
                subject_id,
                purpose["purpose_version"],
                revision,
                link_revision,
                action,
                Jsonb(scope.categories),
                purpose["notice_revision"],
                purpose["notice_digest"],
                channel,
                session_id,
                staff_actor_id,
                offline_case_id,
                source_received_at,
            ),
        )
        tx.execute(
            """INSERT INTO governance_consent_current(subject_id,purpose_version,consent_event_id,revision)
                   VALUES (%s,%s,%s,%s) ON CONFLICT(subject_id,purpose_version) DO UPDATE
                   SET consent_event_id=EXCLUDED.consent_event_id,revision=EXCLUDED.revision""",
            (subject_id, purpose["purpose_version"], eid, revision),
        )
        self._invalidate_queued_authority(
            tx, subject_id, purpose["purpose_version"], staff_actor_id or subject_id
        )
        if action != "grant":
            for ordinal in range(1, len(purpose["recipients"]) + 1):
                tx.execute(
                    "INSERT INTO governance_consent_propagation(propagation_id,consent_event_id,recipient_ordinal) VALUES (%s,%s,%s)",
                    (uuid4(), eid, ordinal),
                )
        audit_id = self.store.append_event(
            tx,
            event_code="consent." + action,
            actor_id=staff_actor_id or subject_id,
            target_id=eid,
            revision=revision,
        )
        tx.execute(
            "INSERT INTO governance_outbox(event_id,event_code,payload) VALUES (%s,%s,%s)",
            (audit_id, "consent." + action, Jsonb({"record_id": str(eid), "revision": revision})),
        )
        return eid, revision

    def record_subject_event(
        self,
        subject_actor,
        command_key,
        notice_version,
        purpose_scope,
        action,
        *,
        affirmative=False,
    ):
        if action not in {"grant", "refuse", "withdraw"}:
            raise GovernanceError("invalid_request")
        if affirmative is not True:
            raise GovernanceError("affirmation_required")
        proof, scope = (
            _validated(NoticeProof, notice_version),
            _validated(ConsentScope, purpose_scope),
        )
        key = identifier(command_key)
        fingerprint = digest(
            {
                "notice": proof.model_dump(mode="json"),
                "scope": scope.model_dump(mode="json"),
                "action": action,
                "affirmative": True,
            }
        )
        with self.store.transaction() as tx:
            self.store.lock(tx)
            subject = require_subject_actor(tx, self.store.organization_id, subject_actor)
            previous = tx.execute(
                "SELECT request_digest,consent_event_id FROM governance_subject_commands WHERE subject_id=%s AND command_key=%s",
                (subject_actor.subject_id, key),
            ).fetchone()
            if previous:
                if previous["request_digest"] != fingerprint:
                    raise GovernanceError("idempotency_conflict")
                state = self.effective(tx, subject_actor.subject_id, scope.purpose_version)
                return {
                    "id": str(previous["consent_event_id"]),
                    "revision": state["revision"],
                    "replayed": True,
                    "effective": state,
                    "propagation_complete": state["propagation_complete"],
                }
            purpose = self._purpose(tx, scope.purpose_version)
            if action != "withdraw":
                self._snapshot(tx, scope.purpose_version)
            if (
                proof.notice_id != scope.purpose_version
                or proof.notice_digest != purpose["notice_digest"]
                or proof.notice_revision != purpose["notice_revision"]
            ):
                raise GovernanceError("notice_scope_mismatch")
            if purpose["department_id"] not in subject["departments"]:
                raise GovernanceError("record_unavailable")
            self._check_categories(purpose, scope.categories)
            receipt = tx.execute(
                """SELECT presentation_id FROM governance_consent_presentations WHERE presentation_id=%s
                                 AND organization_id=%s AND subject_id=%s AND session_id=%s AND link_revision=%s
                                 AND purpose_version=%s AND notice_digest=%s AND consumed_at IS NULL AND expires_at>clock_timestamp()
                                 FOR UPDATE""",
                (
                    proof.presentation_id,
                    self.store.organization_id,
                    subject_actor.subject_id,
                    subject_actor.session_id,
                    subject_actor.link_revision,
                    scope.purpose_version,
                    purpose["notice_digest"],
                ),
            ).fetchone()
            if not receipt:
                raise GovernanceError("notice_presentation_required")
            eid, revision = self._append(
                tx,
                subject_actor.subject_id,
                subject_actor.link_revision,
                purpose,
                scope,
                action,
                session_id=subject_actor.session_id,
            )
            tx.execute(
                "UPDATE governance_consent_presentations SET consumed_at=clock_timestamp() WHERE presentation_id=%s",
                (proof.presentation_id,),
            )
            tx.execute(
                "INSERT INTO governance_subject_commands(subject_id,command_key,request_digest,consent_event_id) VALUES (%s,%s,%s,%s)",
                (subject_actor.subject_id, key, fingerprint, eid),
            )
            state = self.effective(tx, subject_actor.subject_id, scope.purpose_version)
            return {
                "id": str(eid),
                "revision": revision,
                "replayed": False,
                "effective": state,
                "propagation_complete": state["propagation_complete"],
            }

    def status(self, actor, purpose_version):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            subject = require_subject_actor(tx, self.store.organization_id, actor)
            purpose = self._purpose(tx, purpose_version)
            if purpose["department_id"] not in subject["departments"]:
                raise GovernanceError("record_unavailable")
            return self.effective(tx, actor.subject_id, purpose_version)

    def history(self, actor, purpose_version):
        with self.store.transaction() as tx:
            subject = require_subject_actor(tx, self.store.organization_id, actor)
            purpose = self._purpose(tx, purpose_version)
            if purpose["department_id"] not in subject["departments"]:
                raise GovernanceError("record_unavailable")
            rows = tx.execute(
                "SELECT consent_event_id,revision,action,channel,notice_revision,notice_digest,received_at,categories FROM governance_consent_events WHERE subject_id=%s AND purpose_version=%s ORDER BY revision",
                (actor.subject_id, identifier(purpose_version)),
            ).fetchall()
            return [
                {
                    "id": str(r["consent_event_id"]),
                    "revision": r["revision"],
                    "action": r["action"],
                    "channel": r["channel"],
                    "notice_revision": r["notice_revision"],
                    "notice_digest": r["notice_digest"],
                    "received_at": r["received_at"].isoformat(),
                    "categories": r["categories"],
                }
                for r in rows
            ]

    def _staff_subject(self, tx, member, subject_id):
        row = tx.execute(
            """SELECT s.*,l.departments FROM governance_subjects s JOIN governance_subject_links l
                         ON l.subject_id=s.subject_id AND l.subject_revision=s.revision
                         WHERE s.subject_id=%s AND s.organization_id=%s""",
            (identifier(subject_id), self.store.organization_id),
        ).fetchone()
        if not row or any(not in_scope(member, d) for d in row["departments"]):
            raise GovernanceError("record_unavailable")
        if row["state"] != "resolved":
            raise GovernanceError("identity_unresolved")
        return row

    def propose_offline(self, principal, command_key, request):
        data = _validated(OfflineConsentInput, request)

        def scoped(tx, member):
            subject = self._staff_subject(tx, member, data.subject_id)
            if data.action == "withdraw":
                purpose = self._purpose(tx, data.scope.purpose_version)
            else:
                purpose, _ = self._snapshot(tx, data.scope.purpose_version)
            if purpose["department_id"] not in subject["departments"] or not in_scope(
                member, purpose["department_id"]
            ):
                raise GovernanceError("record_unavailable")
            self._check_categories(purpose, data.scope.categories)
            return subject

        def effect(tx, member, subject):
            cid = uuid4()
            tx.execute(
                """INSERT INTO governance_consent_offline_cases(case_id,organization_id,subject_id,link_revision,
                       purpose_version,categories,expected_consent_revision,action,mode,source_evidence_ref,
                       capacity_evidence_ref,representative_authority_ref,source_received_at,proposed_by,proposer_revision)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    cid,
                    self.store.organization_id,
                    data.subject_id,
                    subject["revision"],
                    data.scope.purpose_version,
                    Jsonb(data.scope.categories),
                    data.scope.expected_revision,
                    data.action,
                    data.mode,
                    data.source_evidence_ref,
                    data.capacity_evidence_ref,
                    data.representative_authority_ref,
                    data.source_received_at,
                    member["member_id"],
                    member["revision"],
                ),
            )
            return {
                "id": str(cid),
                "revision": 1,
                "state": "proposed",
                "channel": "reviewed_" + data.mode,
                "evidence_mode": "pending_independent_review",
                "portal_act": False,
            }

        return run_command(
            self.store,
            principal,
            command_key,
            "consent.offline.propose",
            "consent.offline_proposed",
            data.model_dump(mode="json"),
            effect,
            scope=scoped,
        )

    def get_offline(self, principal, case_id):
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "subject.read")
            row = tx.execute(
                "SELECT * FROM governance_consent_offline_cases WHERE case_id=%s AND organization_id=%s",
                (identifier(case_id), self.store.organization_id),
            ).fetchone()
            if not row:
                raise GovernanceError("record_unavailable")
            self._staff_subject(tx, member, row["subject_id"])
            purpose = self._purpose(tx, row["purpose_version"])
            if not in_scope(member, purpose["department_id"]):
                raise GovernanceError("record_unavailable")
            result = {
                key: str(row[key]) if row[key] is not None else None
                for key in (
                    "subject_id",
                    "purpose_version",
                    "source_evidence_ref",
                    "capacity_evidence_ref",
                    "representative_authority_ref",
                    "proposed_by",
                    "review_evidence_ref",
                )
            }
            return {
                "id": str(row["case_id"]),
                **result,
                "revision": row["revision"],
                "state": row["state"],
                "mode": row["mode"],
                "action": row["action"],
                "categories": row["categories"],
                "link_revision": row["link_revision"],
                "expected_consent_revision": row["expected_consent_revision"],
                "source_received_at": row["source_received_at"].isoformat(),
                "portal_act": False,
            }

    def staff_status(self, principal, subject_id, purpose_version):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(tx, self.store.organization_id, principal, "subject.read")
            subject = self._staff_subject(tx, member, subject_id)
            purpose = self._purpose(tx, purpose_version)
            if purpose["department_id"] not in subject["departments"] or not in_scope(
                member, purpose["department_id"]
            ):
                raise GovernanceError("record_unavailable")
            return self.effective(tx, subject_id, purpose_version)

    def propagation_tasks(self, principal, subject_id, purpose_version):
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = require_member(
                tx, self.store.organization_id, principal, "consent.propagation.read"
            )
            subject = self._staff_subject(tx, member, subject_id)
            purpose = self._purpose(tx, purpose_version)
            if purpose["department_id"] not in subject["departments"] or not in_scope(
                member, purpose["department_id"]
            ):
                raise GovernanceError("record_unavailable")
            state = self.effective(tx, subject_id, purpose_version)
            return {
                "propagation": state["propagation"],
                "propagation_complete": state["propagation_complete"],
            }

    def review_offline(
        self, principal, command_key, case_id, expected_revision, decision, evidence_ref
    ):
        case_id, evidence_ref = identifier(case_id), identifier(evidence_ref)
        if decision not in {"approve", "reject"}:
            raise GovernanceError("invalid_request")

        def scoped(tx, member):
            row = tx.execute(
                "SELECT * FROM governance_consent_offline_cases WHERE case_id=%s AND organization_id=%s",
                (case_id, self.store.organization_id),
            ).fetchone()
            if not row:
                raise GovernanceError("record_unavailable")
            subject = self._staff_subject(tx, member, row["subject_id"])
            return row, subject

        def effect(tx, member, scoped):
            row, subject = scoped
            check_revision(row, expected_revision)
            if row["state"] != "proposed":
                raise GovernanceError("invalid_transition")
            if row["proposed_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            proposer = tx.execute(
                "SELECT * FROM governance_members WHERE member_id=%s AND enabled FOR SHARE",
                (row["proposed_by"],),
            ).fetchone()
            if (
                not proposer
                or proposer["revision"] != row["proposer_revision"]
                or "case_manager" not in proposer["roles"]
                or any(not in_scope(proposer, d) for d in subject["departments"])
            ):
                raise GovernanceError("proposal_authority_expired")
            if subject["revision"] != row["link_revision"]:
                raise GovernanceError("revision_conflict")
            state = "rejected"
            if decision == "approve":
                purpose = self._purpose(tx, row["purpose_version"])
                if row["action"] != "withdraw":
                    self._snapshot(tx, row["purpose_version"])
                if not in_scope(member, purpose["department_id"]):
                    raise GovernanceError("record_unavailable")
                scope = ConsentScope(
                    purpose_version=row["purpose_version"],
                    categories=row["categories"],
                    expected_revision=row["expected_consent_revision"],
                )
                self._append(
                    tx,
                    row["subject_id"],
                    row["link_revision"],
                    purpose,
                    scope,
                    row["action"],
                    staff_actor_id=member["member_id"],
                    offline_case_id=case_id,
                    channel="reviewed_" + row["mode"],
                    source_received_at=row["source_received_at"],
                )
                state = "applied"
            tx.execute(
                "UPDATE governance_consent_offline_cases SET state=%s,revision=revision+1,reviewed_by=%s,review_evidence_ref=%s WHERE case_id=%s",
                (state, member["member_id"], evidence_ref, case_id),
            )
            return {
                "id": str(case_id),
                "revision": expected_revision + 1,
                "state": state,
                "channel": "reviewed_" + row["mode"],
                "evidence_mode": "reviewer_attested_external",
                "portal_act": False,
            }

        return run_command(
            self.store,
            principal,
            command_key,
            "consent.offline.review",
            "consent.offline_reviewed",
            {
                "id": str(case_id),
                "revision": expected_revision,
                "decision": decision,
                "evidence_ref": str(evidence_ref),
            },
            effect,
            scope=scoped,
        )

    def review_propagation(
        self, principal, command_key, propagation_id, state, evidence_ref, *, evidence_scope=None
    ):
        propagation_id, evidence_ref = identifier(propagation_id), identifier(evidence_ref)
        if state not in {"failed", "verified"}:
            raise GovernanceError("invalid_request")
        if state == "verified" and evidence_scope is None:
            raise GovernanceError("evidence_scope_required")
        evidence_scope = (
            _validated(PropagationScope, evidence_scope) if evidence_scope is not None else None
        )

        def scoped(tx, member):
            row = tx.execute(
                """SELECT p.*,e.subject_id,e.purpose_version,e.revision AS event_revision FROM governance_consent_propagation p
                             JOIN governance_consent_events e ON e.consent_event_id=p.consent_event_id
                             WHERE p.propagation_id=%s AND e.organization_id=%s""",
                (propagation_id, self.store.organization_id),
            ).fetchone()
            if not row:
                raise GovernanceError("record_unavailable")
            self._staff_subject(tx, member, row["subject_id"])
            purpose = self._purpose(tx, row["purpose_version"])
            if not in_scope(member, purpose["department_id"]):
                raise GovernanceError("record_unavailable")
            return row

        def effect(tx, member, row):
            if row["state"] == "verified":
                raise GovernanceError("invalid_transition")
            if evidence_scope is not None and (
                evidence_scope.consent_event_id != row["consent_event_id"]
                or evidence_scope.event_revision != row["event_revision"]
                or evidence_scope.recipient_ordinal != row["recipient_ordinal"]
                or evidence_scope.expected_state != row["state"]
            ):
                raise GovernanceError("revision_conflict")
            tx.execute(
                "UPDATE governance_consent_propagation SET state=%s,evidence_ref=%s,reviewed_by=%s,reviewed_at=clock_timestamp() WHERE propagation_id=%s",
                (state, evidence_ref, member["member_id"], propagation_id),
            )
            return {
                "id": str(propagation_id),
                "revision": 1,
                "state": state,
                "verification_mode": "reviewer_attested_external",
            }

        return run_command(
            self.store,
            principal,
            command_key,
            "consent.propagation.review",
            "consent.propagation_reviewed",
            {
                "id": str(propagation_id),
                "state": state,
                "evidence_ref": str(evidence_ref),
                "evidence_scope": evidence_scope.model_dump(mode="json")
                if evidence_scope
                else None,
            },
            effect,
            scope=scoped,
        )

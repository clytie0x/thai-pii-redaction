"""Reviewed source identity links. Similarity never supplies identity authority."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import Field, field_validator, model_validator

from pii_redactor.governance.commands import check_revision, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel, Department, Principal
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.governance.registry import RecordID, _validated


@dataclass(frozen=True)
class SubjectActor:
    """Backend-only authority; every use checks the persistent session again."""

    subject_id: UUID
    link_revision: int
    session_id: UUID


def require_subject_actor(tx, organization_id, actor):
    if (
        type(actor) is not SubjectActor
        or not isinstance(actor.subject_id, UUID)
        or not isinstance(actor.session_id, UUID)
        or type(actor.link_revision) is not int
        or actor.link_revision < 1
    ):
        raise GovernanceError("authentication_required")
    row = tx.execute(
        """SELECT s.*,l.departments FROM governance_subjects s
        JOIN governance_subject_links l ON l.subject_id=s.subject_id AND l.subject_revision=s.revision
        JOIN enterprise_subject_sessions e ON e.subject_id=s.subject_id
        WHERE s.subject_id=%s AND s.organization_id=%s AND l.organization_id=%s
        AND s.state='resolved' AND l.state='active' AND s.revision=%s
        AND e.session_id=%s AND e.organization_id=%s AND e.link_revision=s.revision
        AND NOT e.revoked AND e.idle_until>clock_timestamp() AND e.absolute_until>clock_timestamp()
        FOR SHARE OF s,l,e""",
        (
            actor.subject_id,
            organization_id,
            organization_id,
            actor.link_revision,
            actor.session_id,
            organization_id,
        ),
    ).fetchone()
    if not row:
        raise GovernanceError("authentication_required")
    # Recheck the wall clock after a lock wait.
    active = tx.execute(
        """SELECT session_id FROM enterprise_subject_sessions WHERE session_id=%s
        AND NOT revoked AND idle_until>clock_timestamp() AND absolute_until>clock_timestamp()""",
        (actor.session_id,),
    ).fetchone()
    if not active:
        raise GovernanceError("authentication_required")
    return row


class SubjectLinkInput(ClosedModel):
    issuer: str
    oidc_subject: str = Field(min_length=1, max_length=255, repr=False)
    source_system: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    source_record_id: RecordID
    source_version: str = Field(min_length=1, max_length=128)
    departments: list[Department] = Field(min_length=1, max_length=32)
    identity_evidence_ref: RecordID
    capacity_evidence_ref: RecordID

    @model_validator(mode="after")
    def exact_identity(self):
        Principal(issuer=self.issuer, subject=self.oidc_subject)
        if len(set(self.departments)) != len(self.departments) or "*" in self.departments:
            raise ValueError("concrete scope required")
        if not self.source_version.strip() or any(ord(c) < 32 for c in self.source_version):
            raise ValueError("source version required")
        return self

    @field_validator("issuer")
    @classmethod
    def approved_issuer_shape(cls, value):
        return Principal(issuer=value, subject="validation").issuer


def _view(row):
    return {
        "id": str(row["link_id"]),
        "subject_id": str(row["subject_id"]),
        "revision": row["revision"],
        "link_revision": row["subject_revision"],
        "state": row["state"],
        "departments": row["departments"],
        "source_system": row["source_system"],
        "source_version": row["source_version"],
        "source_record_id": str(row["source_record_id"]),
        "issuer": row["issuer"],
        "oidc_subject": row["oidc_subject"],
        "identity_evidence_ref": str(row["identity_evidence_ref"]),
        "capacity_evidence_ref": str(row["capacity_evidence_ref"]),
        "identity_reviewed": row["identity_reviewed_by"] is not None,
        "privacy_reviewed": row["privacy_reviewed_by"] is not None,
        "evidence_mode": "reviewer_attested_external"
        if row["identity_reviewed_by"]
        else "pending_review",
    }


class SubjectLinks:
    def __init__(self, store):
        self.store = store

    def _scoped(self, tx, member, link_id):
        row = tx.execute(
            "SELECT * FROM governance_subject_links WHERE link_id=%s AND organization_id=%s",
            (identifier(link_id), self.store.organization_id),
        ).fetchone()
        if not row or any(not in_scope(member, d) for d in row["departments"]):
            raise GovernanceError("record_unavailable")
        return row

    def get(self, principal, link_id):
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "subject.read")
            return _view(self._scoped(tx, member, link_id))

    def propose(self, principal, command_key, request, *, subject_id=None, expected_revision=None):
        data = _validated(SubjectLinkInput, request)
        target = identifier(subject_id) if subject_id else None

        def scope(tx, member):
            if any(not in_scope(member, d) for d in data.departments):
                raise GovernanceError("forbidden")
            if target:
                current = tx.execute(
                    """SELECT s.*,l.departments,l.state AS link_state FROM governance_subjects s JOIN governance_subject_links l
                    ON l.subject_id=s.subject_id AND l.subject_revision=s.revision
                    WHERE s.subject_id=%s AND s.organization_id=%s""",
                    (target, self.store.organization_id),
                ).fetchone()
                if not current or any(not in_scope(member, d) for d in current["departments"]):
                    raise GovernanceError("record_unavailable")
                return current

        def effect(tx, member, current):
            conflict = tx.execute(
                """SELECT subject_id FROM governance_subject_links WHERE organization_id=%s
                AND state IN ('proposed','awaiting_privacy','active') AND
                ((issuer=%s AND oidc_subject=%s) OR (source_system=%s AND source_record_id=%s))
                AND (%s::uuid IS NULL OR subject_id<>%s::uuid) LIMIT 1""",
                (
                    self.store.organization_id,
                    data.issuer,
                    data.oidc_subject,
                    data.source_system,
                    data.source_record_id,
                    target,
                    target,
                ),
            ).fetchone()
            if conflict:
                raise GovernanceError("identity_conflict")
            sid = target or uuid4()
            revision = 1
            if current:
                check_revision(current, expected_revision)
                if current["state"] != "resolved" and current["link_state"] != "rejected":
                    raise GovernanceError("identity_unresolved")
                revision = current["revision"] + 1
                tx.execute(
                    "UPDATE governance_subjects SET revision=%s,state='unresolved' WHERE subject_id=%s",
                    (revision, sid),
                )
                tx.execute(
                    "UPDATE governance_subject_links SET state='superseded',revision=revision+1 WHERE subject_id=%s AND state='active'",
                    (sid,),
                )
                tx.execute(
                    "UPDATE enterprise_subject_sessions SET revoked=true WHERE subject_id=%s",
                    (sid,),
                )
            else:
                if expected_revision is not None:
                    raise GovernanceError("invalid_request")
                tx.execute(
                    "INSERT INTO governance_subjects(subject_id,organization_id,state) VALUES (%s,%s,'unresolved')",
                    (sid, self.store.organization_id),
                )
            row = tx.execute(
                """INSERT INTO governance_subject_links(link_id,subject_id,organization_id,subject_revision,
                issuer,oidc_subject,source_system,source_record_id,source_version,departments,
                identity_evidence_ref,capacity_evidence_ref,proposed_by,proposer_revision,state)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'proposed') RETURNING *""",
                (
                    uuid4(),
                    sid,
                    self.store.organization_id,
                    revision,
                    data.issuer,
                    data.oidc_subject,
                    data.source_system,
                    data.source_record_id,
                    data.source_version,
                    Jsonb(data.departments),
                    data.identity_evidence_ref,
                    data.capacity_evidence_ref,
                    member["member_id"],
                    member["revision"],
                ),
            ).fetchone()
            return _view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "subject.propose",
            "subject.link_proposed",
            {
                "data": data.model_dump(mode="json"),
                "subject_id": str(target) if target else None,
                "expected_revision": expected_revision,
            },
            effect,
            scope=scope,
        )

    def review(
        self,
        principal,
        command_key,
        link_id,
        expected_revision,
        decision,
        evidence_ref,
        *,
        privacy=False,
    ):
        target, evidence_ref = identifier(link_id), identifier(evidence_ref)
        if decision not in {"approve", "reject"} or type(privacy) is not bool:
            raise GovernanceError("invalid_request")

        def effect(tx, member, row):
            check_revision(row, expected_revision)
            required_state = "awaiting_privacy" if privacy else "proposed"
            if row["state"] != required_state:
                raise GovernanceError("invalid_transition")
            if member["member_id"] in {row["proposed_by"], row["identity_reviewed_by"]}:
                raise GovernanceError("separation_required")
            proposer = tx.execute(
                "SELECT * FROM governance_members WHERE member_id=%s AND enabled FOR SHARE",
                (row["proposed_by"],),
            ).fetchone()
            if (
                not proposer
                or proposer["revision"] != row["proposer_revision"]
                or not {"identity_steward", "case_manager"}.intersection(proposer["roles"])
                or any(not in_scope(proposer, d) for d in row["departments"])
            ):
                raise GovernanceError("proposal_authority_expired")
            if privacy:
                reviewer = tx.execute(
                    "SELECT * FROM governance_members WHERE member_id=%s AND enabled FOR SHARE",
                    (row["identity_reviewed_by"],),
                ).fetchone()
                if (
                    not reviewer
                    or reviewer["revision"] != row["identity_reviewer_revision"]
                    or "identity_steward" not in reviewer["roles"]
                    or any(not in_scope(reviewer, d) for d in row["departments"])
                ):
                    raise GovernanceError("proposal_authority_expired")
            state = (
                "rejected"
                if decision == "reject"
                else ("active" if privacy or len(row["departments"]) == 1 else "awaiting_privacy")
            )
            if privacy:
                updated = tx.execute(
                    "UPDATE governance_subject_links SET state=%s,revision=revision+1,privacy_reviewed_by=%s,privacy_review_ref=%s WHERE link_id=%s RETURNING *",
                    (state, member["member_id"], evidence_ref, target),
                ).fetchone()
            else:
                updated = tx.execute(
                    "UPDATE governance_subject_links SET state=%s,revision=revision+1,identity_reviewed_by=%s,identity_reviewer_revision=%s,identity_review_ref=%s WHERE link_id=%s RETURNING *",
                    (state, member["member_id"], member["revision"], evidence_ref, target),
                ).fetchone()
            if state == "active":
                tx.execute(
                    "UPDATE governance_subjects SET state='resolved' WHERE subject_id=%s AND revision=%s",
                    (row["subject_id"], row["subject_revision"]),
                )
            return _view(updated)

        return run_command(
            self.store,
            principal,
            command_key,
            "subject.privacy_review" if privacy else "subject.review",
            "subject.link_reviewed",
            {
                "id": str(target),
                "expected_revision": expected_revision,
                "decision": decision,
                "evidence_ref": str(evidence_ref),
                "privacy": privacy,
            },
            effect,
            scope=lambda tx, m: self._scoped(tx, m, target),
        )

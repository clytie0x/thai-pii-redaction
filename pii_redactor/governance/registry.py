"""Scoped processing inventory and immutable notices with recorded human review."""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from pydantic import AfterValidator, Field, ValidationError, field_validator

from pii_redactor.governance.commands import check_revision, digest, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel, Department
from pii_redactor.governance.permissions import in_scope, require_member
from pii_redactor.pdpa_catalog import GENERAL, SENSITIVE
from pii_redactor.pdpa_lifecycle import validate_context


def _nonblank(value):
    if not value.strip():
        raise ValueError("a nonblank value is required")
    return value


Reference = Annotated[str, Field(min_length=1, max_length=256), AfterValidator(_nonblank)]
RecordID = Annotated[UUID, Field(strict=False)]


class ActivityInput(ClosedModel):
    department_id: Department
    title: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=2000)
    necessity: str = Field(default="", max_length=2000)
    categories: list[str] = Field(min_length=1, max_length=24)
    general_basis: str | None = None
    sensitive_condition: str | None = None
    retention_rule: str = Field(default="", max_length=2000)
    destination: str = Field(default="", max_length=2000)
    source_refs: list[Reference] = Field(default_factory=list, max_length=64)
    subject_groups: list[Reference] = Field(default_factory=list, max_length=64)
    recipient_refs: list[Reference] = Field(default_factory=list, max_length=64)

    @field_validator("title", "purpose")
    @classmethod
    def required_text(cls, value):
        return _nonblank(value)

    @field_validator("department_id")
    @classmethod
    def concrete_department(cls, value):
        if value == "*":
            raise ValueError("activity requires a department")
        return value

    @field_validator("categories")
    @classmethod
    def category_inventory(cls, value):
        known = {*GENERAL, *SENSITIVE, "OTHER_PERSONAL", "OTHER_DECLARED_SENSITIVE"}
        if len(set(value)) != len(value) or set(value) - known:
            raise ValueError("invalid category inventory")
        return value

    @field_validator("general_basis", "sensitive_condition")
    @classmethod
    def legal_route(cls, value, info):
        if value is not None:
            validate_context(
                {"basis" if info.field_name == "general_basis" else "s26_condition": value}
            )
        return value


class NoticeInput(ClosedModel):
    activity_id: RecordID
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=20, max_length=20000)
    language: Literal["th", "en"]

    @field_validator("title", "body")
    @classmethod
    def required_text(cls, value):
        return _nonblank(value)


class ReviewInput(ClosedModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=10, max_length=2000)
    notice_id: RecordID | None = None
    evidence: dict[
        Literal["inventory", "basis", "retention", "destination", "sensitive"], Reference
    ] = Field(default_factory=dict, max_length=5)

    @field_validator("reason")
    @classmethod
    def required_text(cls, value):
        return _nonblank(value)


def _validated(model, value):
    try:
        return model.model_validate(value.model_dump() if isinstance(value, model) else value)
    except ValidationError:
        raise GovernanceError("invalid_request") from None


def _activity_view(row):
    return {
        "id": str(row["activity_id"]),
        "state": row["state"],
        "revision": row["revision"],
        "data": row["data"],
        "review": row["review"],
        "created_by": str(row["created_by"]),
        "last_editor": str(row["last_editor"]),
        "submitted_by": str(row["submitted_by"]) if row["submitted_by"] else None,
        "reviewed_by": str(row["reviewed_by"]) if row["reviewed_by"] else None,
        "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
        "review_evidence_mode": "reviewer_attested_external" if row["review"] else None,
        "legal_clearance": False,
    }


def _notice_view(row):
    return {
        "id": str(row["notice_id"]),
        "state": row["state"],
        "revision": row["revision"],
        "data": row["data"],
        "content_digest": row["content_digest"],
        "created_by": str(row["created_by"]),
        "published_by": str(row["published_by"]) if row["published_by"] else None,
        "published_at": row["published_at"].isoformat() if row["published_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }


class Registry:
    def __init__(self, store):
        self.store = store

    def _activity(self, tx, member, record_id):
        row = tx.execute(
            "SELECT * FROM governance_activities WHERE activity_id=%s AND organization_id=%s",
            (identifier(record_id), self.store.organization_id),
        ).fetchone()
        if not row or not in_scope(member, row["department_id"]):
            raise GovernanceError("record_unavailable")
        return row

    def get_activity(self, principal, record_id):
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "activity.read")
            return _activity_view(self._activity(tx, member, record_id))

    def list_activities(self, principal, *, limit=100, offset=0):
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(offset) is not int
            or not 0 <= offset <= 10000
        ):
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "activity.read")
            rows = tx.execute(
                """SELECT * FROM governance_activities WHERE organization_id=%s
                AND (department_id=ANY(%s) OR %s) ORDER BY created_at,activity_id LIMIT %s OFFSET %s""",
                (
                    self.store.organization_id,
                    member["departments"],
                    "*" in member["departments"],
                    limit,
                    offset,
                ),
            ).fetchall()
            return [_activity_view(row) for row in rows]

    def create_activity(self, principal, command_key, request):
        data = _validated(ActivityInput, request).model_dump(mode="json")

        def effect(tx, member, _):
            row = tx.execute(
                """INSERT INTO governance_activities(activity_id,organization_id,department_id,state,revision,data,created_by,last_editor)
                VALUES (%s,%s,%s,'draft',1,%s,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    data["department_id"],
                    Jsonb(data),
                    member["member_id"],
                    member["member_id"],
                ),
            ).fetchone()
            return _activity_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "activity.create",
            "activity.created",
            data,
            effect,
            department_id=data["department_id"],
        )

    def update_activity(self, principal, command_key, record_id, expected_revision, request):
        record_id = identifier(record_id)
        data = _validated(ActivityInput, request).model_dump(mode="json")

        def effect(tx, member, record):
            check_revision(record, expected_revision)
            if record["state"] not in {"draft", "rejected"}:
                raise GovernanceError("invalid_transition")
            if data["department_id"] != record["department_id"]:
                raise GovernanceError("department_change_forbidden")
            row = tx.execute(
                """UPDATE governance_activities SET data=%s,revision=revision+1,last_editor=%s,
                state='draft',review=NULL,reviewed_by=NULL,reviewed_at=NULL WHERE activity_id=%s RETURNING *""",
                (Jsonb(data), member["member_id"], record_id),
            ).fetchone()
            return _activity_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "activity.update",
            "activity.updated",
            {"id": str(record_id), "revision": expected_revision, "data": data},
            effect,
            scope=lambda tx, m: self._activity(tx, m, record_id),
        )

    def submit_activity(self, principal, command_key, record_id, expected_revision):
        record_id = identifier(record_id)

        def effect(tx, member, record):
            check_revision(record, expected_revision)
            if record["state"] != "draft":
                raise GovernanceError("invalid_transition")
            row = tx.execute(
                """UPDATE governance_activities SET state='submitted',revision=revision+1,
                submitted_by=%s WHERE activity_id=%s RETURNING *""",
                (member["member_id"], record_id),
            ).fetchone()
            return _activity_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "activity.submit",
            "activity.submitted",
            {"id": str(record_id), "revision": expected_revision},
            effect,
            scope=lambda tx, m: self._activity(tx, m, record_id),
        )

    def create_notice(self, principal, command_key, request, *, expected_activity_revision=None):
        notice = _validated(NoticeInput, request)
        data = notice.model_dump(mode="json")

        def effect(tx, member, record):
            if expected_activity_revision is not None:
                check_revision(record, expected_activity_revision)
            row = tx.execute(
                """INSERT INTO governance_notices(notice_id,organization_id,activity_id,
                payload_digest,content_digest,state,revision,data,created_by)
                VALUES (%s,%s,%s,%s,%s,'draft',1,%s,%s) RETURNING *""",
                (
                    uuid4(),
                    self.store.organization_id,
                    notice.activity_id,
                    digest(record["data"]),
                    digest(data),
                    Jsonb(data),
                    member["member_id"],
                ),
            ).fetchone()
            return _notice_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "notice.create",
            "notice.created",
            data
            if expected_activity_revision is None
            else {"notice": data, "activity_revision": expected_activity_revision},
            effect,
            scope=lambda tx, m: self._activity(tx, m, notice.activity_id),
        )

    def _notice(self, tx, member, notice_id):
        row = tx.execute(
            "SELECT * FROM governance_notices WHERE notice_id=%s AND organization_id=%s",
            (identifier(notice_id), self.store.organization_id),
        ).fetchone()
        if not row:
            raise GovernanceError("record_unavailable")
        self._activity(tx, member, row["activity_id"])
        return row

    def get_notice(self, principal, notice_id):
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "activity.read")
            return _notice_view(self._notice(tx, member, notice_id))

    def list_notices(self, principal, activity_id, *, limit=100, offset=0):
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(offset) is not int
            or not 0 <= offset <= 10000
        ):
            raise GovernanceError("invalid_request")
        with self.store.transaction() as tx:
            member = require_member(tx, self.store.organization_id, principal, "activity.read")
            record = self._activity(tx, member, activity_id)
            rows = tx.execute(
                "SELECT * FROM governance_notices WHERE activity_id=%s AND organization_id=%s ORDER BY created_at,notice_id LIMIT %s OFFSET %s",
                (record["activity_id"], self.store.organization_id, limit, offset),
            ).fetchall()
            return [_notice_view(row) for row in rows]

    def publish_notice(self, principal, command_key, notice_id, expected_revision):
        record_id = identifier(notice_id)

        def effect(tx, member, notice):
            check_revision(notice, expected_revision)
            if notice["state"] != "draft":
                raise GovernanceError("invalid_transition")
            if notice["created_by"] == member["member_id"]:
                raise GovernanceError("separation_required")
            activity = self._activity(tx, member, notice["activity_id"])
            if digest(activity["data"]) != notice["payload_digest"]:
                raise GovernanceError("notice_scope_mismatch")
            row = tx.execute(
                """UPDATE governance_notices SET state='published',revision=revision+1,
                published_by=%s,published_at=now() WHERE notice_id=%s RETURNING *""",
                (member["member_id"], record_id),
            ).fetchone()
            return _notice_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "notice.publish",
            "notice.published",
            {"id": str(record_id), "revision": expected_revision},
            effect,
            scope=lambda tx, m: self._notice(tx, m, record_id),
        )

    def review_activity(self, principal, command_key, record_id, expected_revision, request):
        record_id = identifier(record_id)
        review = _validated(ReviewInput, request)
        data = review.model_dump(mode="json")

        def effect(tx, member, record):
            check_revision(record, expected_revision)
            if record["state"] != "submitted":
                raise GovernanceError("invalid_transition")
            if member["member_id"] in {
                record["created_by"],
                record["last_editor"],
                record["submitted_by"],
            }:
                raise GovernanceError("separation_required")
            if review.decision == "approve":
                self._complete_review(tx, member, record, review)
            state = "active" if review.decision == "approve" else "rejected"
            row = tx.execute(
                """UPDATE governance_activities SET state=%s,revision=revision+1,
                reviewed_by=%s,review=%s,reviewed_at=now() WHERE activity_id=%s RETURNING *""",
                (state, member["member_id"], Jsonb(data), record_id),
            ).fetchone()
            return _activity_view(row)

        return run_command(
            self.store,
            principal,
            command_key,
            "activity.review",
            "activity.reviewed",
            {"id": str(record_id), "revision": expected_revision, "review": data},
            effect,
            scope=lambda tx, m: self._activity(tx, m, record_id),
        )

    def _complete_review(self, tx, member, record, review):
        activity = record["data"]
        required = {"inventory", "basis", "retention", "destination"}
        if set(activity["categories"]) & set(SENSITIVE):
            required.add("sensitive")
            if not activity["sensitive_condition"]:
                raise GovernanceError("review_incomplete")
        if (
            required - review.evidence.keys()
            or not review.notice_id
            or not all(
                activity[k]
                for k in (
                    "necessity",
                    "general_basis",
                    "retention_rule",
                    "destination",
                    "source_refs",
                    "subject_groups",
                    "recipient_refs",
                )
            )
            or set(activity["categories"]) & {"OTHER_PERSONAL", "OTHER_DECLARED_SENSITIVE"}
        ):
            raise GovernanceError("review_incomplete")
        notice = self._notice(tx, member, review.notice_id)
        if (
            notice["state"] != "published"
            or notice["activity_id"] != record["activity_id"]
            or notice["payload_digest"] != digest(activity)
        ):
            raise GovernanceError("notice_scope_mismatch")

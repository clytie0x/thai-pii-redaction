"""Membership changes require an independent, currently authorized reviewer."""

from uuid import uuid4

from psycopg.types.json import Jsonb
from pydantic import ValidationError

from pii_redactor.governance.commands import check_revision, identifier, run_command
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Enrollment, Principal
from pii_redactor.governance.permissions import in_scope, require_member


class Authority:
    def __init__(self, store):
        self.store = store

    def require(self, tx, principal, permission, department_id=None):
        return require_member(tx, self.store.organization_id, principal, permission, department_id)

    @staticmethod
    def _target(tx, member, target_id, *, for_update=True):
        statement = "SELECT * FROM governance_members WHERE member_id=%s AND organization_id=%s"
        if for_update:
            statement += " FOR UPDATE"
        target = tx.execute(
            statement,
            (identifier(target_id), member["organization_id"]),
        ).fetchone()
        if (
            not target
            or ("*" in target["departments"] and "*" not in member["departments"])
            or any(not in_scope(member, department) for department in target["departments"])
        ):
            raise GovernanceError("record_unavailable")
        return target

    def propose_grant(self, principal, command_key, member_id, roles, departments, *, enabled=None):
        target_id = identifier(member_id)
        if enabled is not None and type(enabled) is not bool:
            raise GovernanceError("invalid_request")

        def scope(tx, member):
            target = self._target(tx, member, target_id)
            try:
                enrollment = Enrollment(
                    principal=Principal(issuer=target["issuer"], subject=target["subject"]),
                    roles=roles,
                    departments=departments,
                )
            except ValidationError:
                raise GovernanceError("invalid_request") from None
            if any(not in_scope(member, d) for d in enrollment.departments):
                raise GovernanceError("forbidden")
            return target

        def effect(tx, member, target):
            record_id = uuid4()
            tx.execute(
                """INSERT INTO governance_grants(grant_id,organization_id,target_id,target_revision,proposed_by,proposer_revision,state,roles,departments,enabled_change)
                        VALUES (%s,%s,%s,%s,%s,%s,'proposed',%s,%s,%s)""",
                (
                    record_id,
                    self.store.organization_id,
                    target_id,
                    target["revision"],
                    member["member_id"],
                    member["revision"],
                    Jsonb(roles),
                    Jsonb(departments),
                    enabled,
                ),
            )
            return {"id": str(record_id), "state": "proposed", "revision": 1}

        return run_command(
            self.store,
            principal,
            command_key,
            "membership.propose",
            "membership.proposed",
            {
                "member_id": str(target_id),
                "roles": roles,
                "departments": departments,
                "enabled": enabled,
            },
            effect,
            scope=scope,
        )

    def propose_enrollment(self, principal, command_key, request):
        try:
            enrollment = Enrollment.model_validate(request.model_dump())
        except (AttributeError, ValidationError):
            raise GovernanceError("invalid_request") from None

        def scope(tx, member):
            if enrollment.principal.issuer != member["issuer"]:
                raise GovernanceError("identity_issuer_mismatch")
            if any(not in_scope(member, d) for d in enrollment.departments):
                raise GovernanceError("forbidden")

        def effect(tx, member, _):
            existing = tx.execute(
                "SELECT member_id FROM governance_members WHERE organization_id=%s AND issuer=%s AND subject=%s",
                (
                    self.store.organization_id,
                    enrollment.principal.issuer,
                    enrollment.principal.subject,
                ),
            ).fetchone()
            if existing:
                raise GovernanceError("already_enrolled")
            member_id, grant_id = uuid4(), uuid4()
            tx.execute(
                """INSERT INTO governance_members(member_id,organization_id,issuer,subject,roles,departments,enabled)
                VALUES (%s,%s,%s,%s,%s,%s,false)""",
                (
                    member_id,
                    self.store.organization_id,
                    enrollment.principal.issuer,
                    enrollment.principal.subject,
                    Jsonb(enrollment.roles),
                    Jsonb(enrollment.departments),
                ),
            )
            tx.execute(
                """INSERT INTO governance_grants(grant_id,organization_id,target_id,target_revision,proposed_by,proposer_revision,state,roles,departments,enabled_change)
                VALUES (%s,%s,%s,1,%s,%s,'proposed',%s,%s,true)""",
                (
                    grant_id,
                    self.store.organization_id,
                    member_id,
                    member["member_id"],
                    member["revision"],
                    Jsonb(enrollment.roles),
                    Jsonb(enrollment.departments),
                ),
            )
            return {"id": str(grant_id), "state": "proposed", "revision": 1}

        return run_command(
            self.store,
            principal,
            command_key,
            "membership.propose",
            "membership.enrollment_proposed",
            enrollment.model_dump(mode="json"),
            effect,
            scope=scope,
        )

    def _ensure_available(self, tx):
        members = tx.execute(
            "SELECT member_id,roles FROM governance_members WHERE organization_id=%s AND enabled",
            (self.store.organization_id,),
        ).fetchall()
        administrators = {m["member_id"] for m in members if "system_administrator" in m["roles"]}
        reviewers = {m["member_id"] for m in members if "authority_reviewer" in m["roles"]}
        if not any(a != r for a in administrators for r in reviewers) or not any(
            "privacy_reviewer" in m["roles"] for m in members
        ):
            raise GovernanceError("authority_unavailable")

    def suspend_member(self, principal, command_key, member_id, expected_revision):
        target_id = identifier(member_id)

        def effect(tx, member, target):
            check_revision(target, expected_revision)
            if not target["enabled"]:
                raise GovernanceError("invalid_transition")
            tx.execute(
                "UPDATE governance_members SET enabled=false,revision=revision+1 WHERE member_id=%s",
                (target_id,),
            )
            self._ensure_available(tx)
            return {"id": str(target_id), "state": "suspended", "revision": expected_revision + 1}

        return run_command(
            self.store,
            principal,
            command_key,
            "membership.suspend",
            "membership.suspended",
            {"member_id": str(target_id), "revision": expected_revision},
            effect,
            scope=lambda tx, m: self._target(tx, m, target_id),
        )

    def approve_grant(self, principal, command_key, grant_id, expected_revision):
        record_id = identifier(grant_id)

        def scope(tx, member):
            grant = tx.execute(
                "SELECT * FROM governance_grants WHERE grant_id=%s AND organization_id=%s FOR UPDATE",
                (record_id, self.store.organization_id),
            ).fetchone()
            if not grant:
                raise GovernanceError("record_unavailable")
            target = self._target(tx, member, grant["target_id"])
            if any(not in_scope(member, d) for d in grant["departments"]):
                raise GovernanceError("forbidden")
            return grant, target

        def effect(tx, member, scoped):
            grant, target = scoped
            check_revision(grant, expected_revision)
            if member["member_id"] in {grant["proposed_by"], grant["target_id"]}:
                raise GovernanceError("separation_required")
            if grant["state"] != "proposed":
                raise GovernanceError("invalid_transition")
            proposer = tx.execute(
                "SELECT * FROM governance_members WHERE member_id=%s AND organization_id=%s FOR SHARE",
                (grant["proposed_by"], self.store.organization_id),
            ).fetchone()
            if (
                not proposer
                or not proposer["enabled"]
                or proposer["revision"] != grant["proposer_revision"]
                or "system_administrator" not in proposer["roles"]
            ):
                raise GovernanceError("proposal_authority_expired")
            if target["revision"] != grant["target_revision"]:
                raise GovernanceError("revision_conflict")
            tx.execute(
                "UPDATE governance_members SET roles=%s,departments=%s,enabled=COALESCE(%s,enabled),revision=revision+1 WHERE member_id=%s",
                (
                    Jsonb(grant["roles"]),
                    Jsonb(grant["departments"]),
                    grant["enabled_change"],
                    target["member_id"],
                ),
            )
            tx.execute(
                "UPDATE governance_grants SET state='applied',approved_by=%s,revision=revision+1 WHERE grant_id=%s",
                (member["member_id"], record_id),
            )
            self._ensure_available(tx)
            return {"id": str(record_id), "state": "applied", "revision": expected_revision + 1}

        return run_command(
            self.store,
            principal,
            command_key,
            "membership.approve",
            "membership.applied",
            {"grant_id": str(record_id), "expected_revision": expected_revision},
            effect,
            scope=scope,
        )

    def list_members(self, principal, *, limit=100, offset=0):
        self._pagination(limit, offset)
        with self.store.transaction() as tx:
            member = self.require(tx, principal, "membership.read")
            rows = tx.execute(
                """SELECT member_id,issuer,subject,roles,departments,enabled,revision FROM governance_members
                WHERE organization_id=%s AND (departments <@ %s::jsonb OR %s)
                ORDER BY created_at,member_id LIMIT %s OFFSET %s""",
                (
                    self.store.organization_id,
                    Jsonb(member["departments"]),
                    "*" in member["departments"],
                    limit,
                    offset,
                ),
            ).fetchall()
            return [{"id": str(r.pop("member_id")), **r} for r in rows]

    @staticmethod
    def _pagination(limit, offset):
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(offset) is not int
            or not 0 <= offset <= 10000
        ):
            raise GovernanceError("invalid_request")

    @staticmethod
    def _grant_view(row):
        return {
            "id": str(row["grant_id"]),
            "target_id": str(row["target_id"]),
            "proposed_by": str(row["proposed_by"]),
            "approved_by": str(row["approved_by"]) if row["approved_by"] else None,
            "roles": row["roles"],
            "departments": row["departments"],
            "enabled_change": row["enabled_change"],
            "state": row["state"],
            "revision": row["revision"],
            "target_revision": row["target_revision"],
        }

    def get_grant(self, principal, grant_id):
        with self.store.transaction() as tx:
            member = self.require(tx, principal, "membership.read")
            row = tx.execute(
                "SELECT * FROM governance_grants WHERE grant_id=%s AND organization_id=%s",
                (identifier(grant_id), self.store.organization_id),
            ).fetchone()
            if not row:
                raise GovernanceError("record_unavailable")
            self._target(tx, member, row["target_id"], for_update=False)
            if any(not in_scope(member, d) for d in row["departments"]):
                raise GovernanceError("record_unavailable")
            return self._grant_view(row)

    def list_grants(self, principal, *, limit=100, offset=0):
        self._pagination(limit, offset)
        with self.store.transaction() as tx:
            member = self.require(tx, principal, "membership.read")
            rows = tx.execute(
                """SELECT g.* FROM governance_grants g JOIN governance_members m ON m.member_id=g.target_id
                WHERE g.organization_id=%s AND m.organization_id=%s AND ((g.departments <@ %s::jsonb
                AND m.departments <@ %s::jsonb) OR %s) ORDER BY g.created_at,g.grant_id LIMIT %s OFFSET %s""",
                (
                    self.store.organization_id,
                    self.store.organization_id,
                    Jsonb(member["departments"]),
                    Jsonb(member["departments"]),
                    "*" in member["departments"],
                    limit,
                    offset,
                ),
            ).fetchall()
            return [self._grant_view(row) for row in rows]

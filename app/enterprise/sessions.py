"""Browser-bound login attempts and revision-bound PostgreSQL staff sessions."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass, field
from uuid import uuid4

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import Principal, StaffPrincipal

_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


def _hash(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def _valid(value):
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


@dataclass(frozen=True)
class LoginAttempt:
    state: str = field(repr=False)
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)


@dataclass(frozen=True)
class SessionGrant:
    cookie: str = field(repr=False)
    csrf: str = field(repr=False)


class StaffSessions:
    def __init__(self, store, *, login_seconds=300, idle_seconds=1800, absolute_seconds=28800):
        for value, maximum in (
            (login_seconds, 600),
            (idle_seconds, 86400),
            (absolute_seconds, 604800),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise GovernanceError("configuration_invalid")
        if idle_seconds > absolute_seconds:
            raise GovernanceError("configuration_invalid")
        self.store = store
        self.login_seconds = login_seconds
        self.idle_seconds = idle_seconds
        self.absolute_seconds = absolute_seconds

    def begin_login(self, binding: str) -> LoginAttempt:
        if not _valid(binding):
            raise GovernanceError("authentication_failed")
        attempt = LoginAttempt(*(secrets.token_urlsafe(32) for _ in range(3)))
        with self.store.transaction() as tx:
            self.store.lock(tx)
            tx.execute("DELETE FROM enterprise_login_states WHERE expires_at<=clock_timestamp()")
            tx.execute(
                """INSERT INTO enterprise_login_states
                (state_hash,organization_id,binding_hash,nonce,code_verifier,expires_at)
                VALUES (%s,%s,%s,%s,%s,clock_timestamp()+%s*interval '1 second')""",
                (
                    _hash(attempt.state),
                    self.store.organization_id,
                    _hash(binding),
                    attempt.nonce,
                    attempt.code_verifier,
                    self.login_seconds,
                ),
            )
            self.store.append_event(tx, event_code="staff_login_started", target_id=uuid4())
        return attempt

    def consume_login(self, state: str, binding: str) -> LoginAttempt:
        if not _valid(state) or not _valid(binding):
            raise GovernanceError("authentication_failed")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row = tx.execute(
                """DELETE FROM enterprise_login_states
                WHERE state_hash=%s AND binding_hash=%s AND organization_id=%s
                AND expires_at>clock_timestamp() RETURNING nonce,code_verifier""",
                (_hash(state), _hash(binding), self.store.organization_id),
            ).fetchone()
            if not row:
                raise GovernanceError("authentication_failed")
            self.store.append_event(tx, event_code="staff_login_consumed", target_id=uuid4())
        return LoginAttempt(state, row["nonce"], row["code_verifier"])

    def issue(self, principal: Principal) -> SessionGrant:
        if not isinstance(principal, Principal):
            raise GovernanceError("authentication_required")
        grant = SessionGrant(secrets.token_urlsafe(32), secrets.token_urlsafe(32))
        with self.store.transaction() as tx:
            self.store.lock(tx)
            member = tx.execute(
                """SELECT member_id,revision FROM governance_members
                WHERE issuer=%s AND subject=%s AND organization_id=%s AND enabled FOR SHARE""",
                (principal.issuer, principal.subject, self.store.organization_id),
            ).fetchone()
            if not member:
                raise GovernanceError("authentication_required")
            session_id = uuid4()
            tx.execute(
                """INSERT INTO enterprise_staff_sessions
                (session_id,organization_id,member_id,member_revision,cookie_hash,csrf_hash,
                 idle_until,absolute_until)
                VALUES (%s,%s,%s,%s,%s,%s,clock_timestamp()+%s*interval '1 second',
                        clock_timestamp()+%s*interval '1 second')""",
                (
                    session_id,
                    self.store.organization_id,
                    member["member_id"],
                    member["revision"],
                    _hash(grant.cookie),
                    _hash(grant.csrf),
                    self.idle_seconds,
                    self.absolute_seconds,
                ),
            )
            self.store.append_event(
                tx,
                event_code="staff_session_issued",
                actor_id=member["member_id"],
                target_id=session_id,
            )
        return grant

    def resolve(self, cookie: str) -> StaffPrincipal:
        if not _valid(cookie):
            raise GovernanceError("authentication_required")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row = tx.execute(
                """SELECT s.session_id,s.member_revision,m.issuer,m.subject
                FROM enterprise_staff_sessions s JOIN governance_members m ON m.member_id=s.member_id
                WHERE s.cookie_hash=%s AND s.organization_id=%s AND m.organization_id=%s
                AND NOT s.revoked AND m.enabled AND s.member_revision=m.revision
                AND s.idle_until>clock_timestamp() AND s.absolute_until>clock_timestamp()
                FOR SHARE OF m FOR UPDATE OF s""",
                (_hash(cookie), self.store.organization_id, self.store.organization_id),
            ).fetchone()
            if not row:
                raise GovernanceError("authentication_required")
            renewed = tx.execute(
                """UPDATE enterprise_staff_sessions
                SET idle_until=LEAST(absolute_until,clock_timestamp()+%s*interval '1 second')
                WHERE session_id=%s AND NOT revoked
                AND idle_until>clock_timestamp() AND absolute_until>clock_timestamp()
                RETURNING session_id""",
                (self.idle_seconds, row["session_id"]),
            ).fetchone()
            if not renewed:
                raise GovernanceError("authentication_required")
        return StaffPrincipal(**row)

    def check_csrf(self, cookie: str, csrf: str) -> None:
        if not _valid(cookie) or not _valid(csrf):
            raise GovernanceError("forbidden")
        with self.store.transaction() as tx:
            row = tx.execute(
                """SELECT csrf_hash FROM enterprise_staff_sessions
                WHERE cookie_hash=%s AND organization_id=%s AND NOT revoked
                AND idle_until>clock_timestamp() AND absolute_until>clock_timestamp() FOR SHARE""",
                (_hash(cookie), self.store.organization_id),
            ).fetchone()
            if not row or not hmac.compare_digest(row["csrf_hash"], _hash(csrf)):
                raise GovernanceError("forbidden")

    def logout(self, cookie: str, csrf: str) -> None:
        if not _valid(cookie) or not _valid(csrf):
            raise GovernanceError("forbidden")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row = tx.execute(
                """SELECT session_id,member_id,csrf_hash,revoked FROM enterprise_staff_sessions
                WHERE cookie_hash=%s AND organization_id=%s FOR UPDATE""",
                (_hash(cookie), self.store.organization_id),
            ).fetchone()
            if not row or not hmac.compare_digest(row["csrf_hash"], _hash(csrf)):
                raise GovernanceError("forbidden")
            if row["revoked"]:
                return
            tx.execute(
                "UPDATE enterprise_staff_sessions SET revoked=true WHERE session_id=%s",
                (row["session_id"],),
            )
            self.store.append_event(
                tx,
                event_code="staff_session_revoked",
                actor_id=row["member_id"],
                target_id=row["session_id"],
            )

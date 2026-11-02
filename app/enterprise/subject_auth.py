"""Subject OIDC and PostgreSQL sessions, isolated from staff authority."""

from __future__ import annotations

import asyncio
import hmac
import os
import secrets
from dataclasses import dataclass, field
from uuid import uuid4

import httpx
from authlib.common.errors import AuthlibBaseError
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from app.enterprise.auth import OIDCClient
from app.enterprise.identity import verify_identity
from app.enterprise.sessions import LoginAttempt, SessionGrant, _hash, _valid
from app.enterprise.settings import _secret_file, _url
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.subjects import SubjectActor, require_subject_actor


@dataclass(frozen=True)
class SubjectOIDCSettings:
    issuer: str
    client_id: str
    client_secret: str = field(repr=False)
    public_origin: str
    staff_client_id: str
    development: bool = False

    def __post_init__(self):
        try:
            issuer, origin = _url(self.issuer), _url(self.public_origin)
            if (
                type(self.development) is not bool
                or origin.path
                or self.client_id == self.staff_client_id
            ):
                raise ValueError
            for value, limit in (
                (self.client_id, 255),
                (self.staff_client_id, 255),
                (self.client_secret, 4096),
            ):
                if (
                    not isinstance(value, str)
                    or not 1 <= len(value) <= limit
                    or any(ord(c) < 32 or ord(c) == 127 for c in value)
                ):
                    raise ValueError
            if self.development:
                if any(
                    p.hostname not in {"127.0.0.1", "localhost", "::1"} for p in (issuer, origin)
                ):
                    raise ValueError
            elif issuer.scheme != "https" or origin.scheme != "https":
                raise ValueError
            return
        except (ValueError, TypeError, AttributeError):
            pass
        raise GovernanceError("configuration_invalid") from None

    @property
    def redirect_uri(self):
        return self.public_origin + "/subject/auth/callback"

    @property
    def cookie_prefix(self):
        return "aiguard_dev_subject_" if self.development else "__Host-aiguard_subject_"

    @classmethod
    def from_env(cls, staff_settings, environment=None):
        env = os.environ if environment is None else environment
        try:
            return cls(
                issuer=env["AIGUARD_ENTERPRISE_SUBJECT_ISSUER"],
                client_id=env["AIGUARD_ENTERPRISE_SUBJECT_CLIENT_ID"],
                client_secret=_secret_file(
                    env["AIGUARD_ENTERPRISE_SUBJECT_OIDC_SECRET_FILE"], "client_secret"
                ),
                public_origin=staff_settings.public_origin,
                staff_client_id=staff_settings.client_id,
                development=staff_settings.development,
            )
        except (KeyError, ValueError, TypeError, OSError):
            pass
        raise GovernanceError("configuration_invalid") from None


@dataclass(frozen=True)
class SubjectIdentity:
    issuer: str
    subject: str = field(repr=False)
    client_id: str


def verify_subject_identity(id_token, *, jwks, settings, nonce, access_token=None):
    principal = verify_identity(
        id_token,
        jwks=jwks,
        issuer=settings.issuer,
        client_id=settings.client_id,
        nonce=nonce,
        access_token=access_token,
    )
    try:
        claims = jwt.decode(id_token, KeySet.import_key_set(jwks), algorithms=["RS256"]).claims
        audiences = [claims["aud"]] if isinstance(claims["aud"], str) else claims["aud"]
        if audiences != [settings.client_id] or settings.staff_client_id in audiences:
            raise ValueError
    except (JoseError, ValueError, KeyError, TypeError):
        raise GovernanceError("authentication_failed") from None
    return SubjectIdentity(principal.issuer, principal.subject, settings.client_id)


class SubjectOIDCClient(OIDCClient):
    async def complete_login(self, code, attempt):
        error_code = "identity_unavailable"
        try:
            if not isinstance(code, str) or not 1 <= len(code) <= 4096:
                raise GovernanceError("authentication_failed")
            async with asyncio.timeout(20):
                metadata = await self.metadata()
                async with self._oauth() as client:
                    token = await client.fetch_token(
                        metadata["token_endpoint"],
                        grant_type="authorization_code",
                        code=code,
                        code_verifier=attempt.code_verifier,
                    )
                if not isinstance(token.get("id_token"), str) or not isinstance(
                    token.get("access_token"), str
                ):
                    raise GovernanceError("authentication_failed")
                keys = await self._json(metadata["jwks_uri"])
                return verify_subject_identity(
                    token["id_token"],
                    jwks=keys,
                    settings=self.settings,
                    nonce=attempt.nonce,
                    access_token=token["access_token"],
                )
        except (GovernanceError, AuthlibBaseError):
            error_code = "authentication_failed"
        except (httpx.HTTPError, ValueError, TypeError, TimeoutError):
            pass
        raise GovernanceError(error_code) from None


class SubjectSessions:
    def __init__(
        self,
        store,
        *,
        issuer,
        client_id,
        login_seconds=300,
        idle_seconds=1800,
        absolute_seconds=28800,
    ):
        if (
            not issuer
            or not client_id
            or any(
                type(v) is not int or not 1 <= v <= maximum
                for v, maximum in (
                    (login_seconds, 600),
                    (idle_seconds, 86400),
                    (absolute_seconds, 604800),
                )
            )
            or idle_seconds > absolute_seconds
        ):
            raise GovernanceError("configuration_invalid")
        self.store, self.issuer, self.client_id = store, issuer, client_id
        self.login_seconds, self.idle_seconds, self.absolute_seconds = (
            login_seconds,
            idle_seconds,
            absolute_seconds,
        )

    def begin_login(self, binding):
        if not _valid(binding):
            raise GovernanceError("authentication_failed")
        attempt = LoginAttempt(*(secrets.token_urlsafe(32) for _ in range(3)))
        with self.store.transaction() as tx:
            self.store.lock(tx)
            tx.execute(
                "DELETE FROM enterprise_subject_login_states WHERE expires_at<=clock_timestamp()"
            )
            tx.execute(
                """INSERT INTO enterprise_subject_login_states(state_hash,organization_id,binding_hash,nonce,code_verifier,expires_at)
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
            self.store.append_event(tx, event_code="subject_login_started", target_id=uuid4())
        return attempt

    def consume_login(self, state, binding):
        if not _valid(state) or not _valid(binding):
            raise GovernanceError("authentication_failed")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row = tx.execute(
                """DELETE FROM enterprise_subject_login_states WHERE state_hash=%s AND binding_hash=%s
                             AND organization_id=%s AND expires_at>clock_timestamp() RETURNING nonce,code_verifier""",
                (_hash(state), _hash(binding), self.store.organization_id),
            ).fetchone()
            if not row:
                raise GovernanceError("authentication_failed")
            self.store.append_event(tx, event_code="subject_login_consumed", target_id=uuid4())
        return LoginAttempt(state, row["nonce"], row["code_verifier"])

    def issue(self, identity):
        if (
            type(identity) is not SubjectIdentity
            or identity.issuer != self.issuer
            or identity.client_id != self.client_id
        ):
            raise GovernanceError("authentication_required")
        grant = SessionGrant(secrets.token_urlsafe(32), secrets.token_urlsafe(32))
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row = tx.execute(
                """SELECT s.subject_id,s.revision FROM governance_subjects s JOIN governance_subject_links l
                             ON l.subject_id=s.subject_id AND l.subject_revision=s.revision
                             WHERE l.organization_id=%s AND s.organization_id=%s AND l.issuer=%s AND l.oidc_subject=%s
                             AND s.state='resolved' AND l.state='active' FOR SHARE OF s,l""",
                (
                    self.store.organization_id,
                    self.store.organization_id,
                    identity.issuer,
                    identity.subject,
                ),
            ).fetchone()
            if not row:
                raise GovernanceError("authentication_required")
            sid = uuid4()
            tx.execute(
                """INSERT INTO enterprise_subject_sessions(session_id,organization_id,subject_id,link_revision,issuer,client_id,
                       cookie_hash,csrf_hash,idle_until,absolute_until) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,
                       clock_timestamp()+%s*interval '1 second',clock_timestamp()+%s*interval '1 second')""",
                (
                    sid,
                    self.store.organization_id,
                    row["subject_id"],
                    row["revision"],
                    self.issuer,
                    self.client_id,
                    _hash(grant.cookie),
                    _hash(grant.csrf),
                    self.idle_seconds,
                    self.absolute_seconds,
                ),
            )
            self.store.append_event(tx, event_code="subject_session_issued", target_id=sid)
        return grant

    def resolve(self, cookie):
        if not _valid(cookie):
            raise GovernanceError("authentication_required")
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row = tx.execute(
                """SELECT session_id,subject_id,link_revision FROM enterprise_subject_sessions
                             WHERE cookie_hash=%s AND organization_id=%s AND issuer=%s AND client_id=%s
                             AND NOT revoked AND idle_until>clock_timestamp() AND absolute_until>clock_timestamp() FOR UPDATE""",
                (_hash(cookie), self.store.organization_id, self.issuer, self.client_id),
            ).fetchone()
            if not row:
                raise GovernanceError("authentication_required")
            actor = SubjectActor(**row)
            require_subject_actor(tx, self.store.organization_id, actor)
            tx.execute(
                "UPDATE enterprise_subject_sessions SET idle_until=LEAST(absolute_until,clock_timestamp()+%s*interval '1 second') WHERE session_id=%s",
                (self.idle_seconds, actor.session_id),
            )
        return actor

    def check_csrf(self, cookie, csrf):
        if not _valid(cookie) or not _valid(csrf):
            raise GovernanceError("forbidden")
        with self.store.transaction() as tx:
            row = tx.execute(
                """SELECT csrf_hash FROM enterprise_subject_sessions WHERE cookie_hash=%s AND organization_id=%s
                             AND issuer=%s AND client_id=%s AND NOT revoked AND idle_until>clock_timestamp()
                             AND absolute_until>clock_timestamp() FOR SHARE""",
                (_hash(cookie), self.store.organization_id, self.issuer, self.client_id),
            ).fetchone()
            if not row or not hmac.compare_digest(row["csrf_hash"], _hash(csrf)):
                raise GovernanceError("forbidden")

    def logout(self, cookie, csrf):
        self.check_csrf(cookie, csrf)
        with self.store.transaction() as tx:
            self.store.lock(tx)
            row = tx.execute(
                "UPDATE enterprise_subject_sessions SET revoked=true WHERE cookie_hash=%s AND organization_id=%s AND issuer=%s AND client_id=%s RETURNING session_id",
                (_hash(cookie), self.store.organization_id, self.issuer, self.client_id),
            ).fetchone()
            if not row:
                raise GovernanceError("authentication_required")
            self.store.append_event(
                tx, event_code="subject_session_revoked", target_id=row["session_id"]
            )

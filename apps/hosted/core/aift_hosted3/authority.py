"""Opaque authority records for the Hosted 3.0 port overlay."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass

MAX_PRIORITY_INVITES = 32
_SUBJECT_PATTERN = re.compile(r"^sub_[A-Za-z0-9_-]{22}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_INVITE_CODE_PATTERN = re.compile(rb"^[A-Za-z0-9_-]{22,128}$")


class AuthorityRegistryError(ValueError):
    """The masked Priority Invite registry is not safe to load."""


@dataclass(frozen=True, slots=True)
class AuthorityContext:
    """The only caller authority supplied to Hosted business handlers."""

    scope: str
    service_class: str
    session_nonce: str
    subject_id: str | None
    expires_at_unix: int


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Process-local session metadata; never contains a raw credential."""

    context: AuthorityContext


@dataclass(frozen=True, slots=True)
class _InviteRecord:
    subject_id: str
    enabled: bool
    code_digest: bytes
    canonical_code_required: bool


class InviteRegistry:
    """Bounded digest-to-opaque-subject Priority Invite registry."""

    def __init__(self, records: tuple[_InviteRecord, ...]):
        self._records = records

    @classmethod
    def from_json(
        cls,
        raw: str | None,
        *,
        legacy_code: bytes,
        subject_key: bytes,
    ) -> "InviteRegistry":
        if raw in (None, ""):
            values = []
        else:
            try:
                values = json.loads(raw)
            except (TypeError, json.JSONDecodeError) as error:
                raise AuthorityRegistryError(
                    "AIFT_PRIORITY_INVITES_JSON is invalid"
                ) from error
        if not isinstance(values, list) or len(values) > MAX_PRIORITY_INVITES:
            raise AuthorityRegistryError("Priority Invite registry is not a bounded list")

        records: list[_InviteRecord] = []
        subjects: set[str] = set()
        digests: set[bytes] = set()
        for value in values:
            if not isinstance(value, dict) or set(value) != {
                "subject_id",
                "role",
                "enabled",
                "code_sha256",
            }:
                raise AuthorityRegistryError("Priority Invite registry row is invalid")
            subject_id = value.get("subject_id")
            role = value.get("role")
            enabled = value.get("enabled")
            digest_text = value.get("code_sha256")
            if (
                not isinstance(subject_id, str)
                or _SUBJECT_PATTERN.fullmatch(subject_id) is None
                or role != "priority_invite"
                or type(enabled) is not bool
                or not isinstance(digest_text, str)
                or _DIGEST_PATTERN.fullmatch(digest_text) is None
            ):
                raise AuthorityRegistryError("Priority Invite registry value is invalid")
            digest = bytes.fromhex(digest_text)
            if subject_id in subjects or digest in digests:
                raise AuthorityRegistryError("Priority Invite registry contains a duplicate")
            subjects.add(subject_id)
            digests.add(digest)
            records.append(_InviteRecord(subject_id, enabled, digest, True))

        legacy_digest = hashlib.sha256(legacy_code).digest()
        if legacy_digest in digests:
            raise AuthorityRegistryError("legacy and masked invite credentials overlap")
        legacy_subject_bytes = hmac.new(
            subject_key,
            b"aift-legacy-priority-subject-v1",
            hashlib.sha256,
        ).digest()[:16]
        legacy_subject = "sub_" + base64.urlsafe_b64encode(
            legacy_subject_bytes
        ).decode("ascii").rstrip("=")
        records.append(_InviteRecord(legacy_subject, True, legacy_digest, False))
        return cls(tuple(records))

    def verify(self, supplied: bytes) -> str | None:
        """Compare fixed-size digests across every row before returning authority."""

        candidate = hashlib.sha256(supplied).digest()
        canonical = _INVITE_CODE_PATTERN.fullmatch(supplied) is not None
        subject: str | None = None
        for record in self._records:
            matches = hmac.compare_digest(candidate, record.code_digest)
            format_allowed = canonical or not record.canonical_code_required
            if matches and record.enabled and format_allowed:
                subject = record.subject_id
        candidate = b""
        return subject

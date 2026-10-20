"""Content-stateless Hosted 3.0 approval capabilities.

Tickets authenticate only bounded reconstruction facts.  Caller content and
original-to-replacement mappings never enter the encrypted envelope or replay
registry.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .authority import AuthorityContext

APPROVAL_CONTEXT = b"aiguard-hosted3-approval-v1"
TICKET_SCHEMA = "aiguard-approval-v1"
HTTP_CONTRACT_VERSION = 2
PROTECTION_GENERATION_REVISION = "pg-v1"
CUSTOM_TEXT_TTL_SECONDS = 300
STANDARD_DOCUMENT_TTL_SECONDS = 900
INVITE_DOCUMENT_TTL_SECONDS = 900
SYNTHETIC_DOCUMENT_TTL_SECONDS = 600
DEFAULT_REPLAY_CAPACITY = 4096

_TICKET_KINDS = frozenset(
    {
        "custom_text_v1",
        "standard_document_v1",
        "invite_document_v1",
        "synthetic_document_v1",
    }
)
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_B64_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_SOURCE_KINDS = {
    "custom_text_v1": frozenset({"custom_standard", "custom_invite"}),
    "standard_document_v1": frozenset({"document_standard"}),
    "invite_document_v1": frozenset({"document_invite"}),
    "synthetic_document_v1": frozenset({"synthetic_document"}),
}
_KIND_TTLS = {
    "custom_text_v1": CUSTOM_TEXT_TTL_SECONDS,
    "standard_document_v1": STANDARD_DOCUMENT_TTL_SECONDS,
    "invite_document_v1": INVITE_DOCUMENT_TTL_SECONDS,
    "synthetic_document_v1": SYNTHETIC_DOCUMENT_TTL_SECONDS,
}
_COMMON_KEYS = frozenset(
    {
        "schema",
        "kind",
        "jti",
        "boot_nonce",
        "issued_at_unix",
        "expires_at_unix",
        "scope",
        "session_nonce",
        "mode",
        "provider_id",
        "provider_model",
        "prompt_revision",
        "http_contract_version",
        "detector_code_sha256",
        "detector_model_sha256",
        "protected_sha256",
        "salt",
        "source_kind",
    }
)
_TOKEN_KEYS = frozenset(
    {"protection_generation_seed", "protection_generation_revision"}
)
_CUSTOM_KEYS = frozenset({"source_sha256"})
_DOCUMENT_KEYS = frozenset(
    {
        "source_pdf_sha256",
        "parser_revision",
        "extraction_revision",
        "segmentation_revision",
        "page_count",
        "character_count",
        "segment_count",
        "omitted_visual_page_numbers",
        "source_receipt_id",
        "segment_manifest_sha256",
    }
)
_SYNTHETIC_KEYS = frozenset(
    {"scenario_id", "scenario_registry_sha256"}
)


class ApprovalError(ValueError):
    """A value-free approval rejection safe for fixed error translation."""

    def __init__(self, code: str = "approval_invalid"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ApprovalBindings:
    provider_id: str
    provider_model: str
    prompt_revision: str
    detector_code_sha256: str
    detector_model_sha256: str


@dataclass(frozen=True, slots=True)
class DocumentFacts:
    source_pdf_sha256: str = field(repr=False)
    parser_revision: str
    extraction_revision: str
    segmentation_revision: str
    page_count: int
    character_count: int
    segment_count: int
    omitted_visual_page_numbers: tuple[int, ...]
    source_receipt_id: str = field(repr=False)
    segment_manifest_sha256: str = field(repr=False)
    scenario_id: str | None = None
    scenario_registry_sha256: str | None = None


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_b64url(value: str) -> bytes:
    if not isinstance(value, str) or not 1 <= len(value) <= 4096:
        raise ApprovalError()
    if _B64_PATTERN.fullmatch(value) is None:
        raise ApprovalError()
    try:
        decoded = base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, TypeError):
        raise ApprovalError() from None
    if _b64url(decoded) != value:
        raise ApprovalError()
    return decoded


def derive_approval_key(cookie_signing_key: bytes) -> bytes:
    """Derive the dedicated AES-256 key without adding another deployed secret."""

    if not isinstance(cookie_signing_key, bytes) or len(cookie_signing_key) < 32:
        raise ValueError("approval key source is invalid")
    return hmac.new(cookie_signing_key, APPROVAL_CONTEXT, hashlib.sha256).digest()


def decode_generation_seed(value: object) -> bytes:
    """Decode the strict encrypted pg-v1 seed after ticket authentication."""

    if not isinstance(value, str):
        raise ApprovalError()
    decoded = _decode_b64url(value)
    if len(decoded) != 32:
        raise ApprovalError()
    return decoded


class ConsumedJTIRegistry:
    """Bounded value-free one-use registry keyed only by JTI digests."""

    def __init__(
        self,
        *,
        capacity: int = DEFAULT_REPLAY_CAPACITY,
        now: Callable[[], float] | None = None,
    ):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("replay capacity is invalid")
        self._capacity = capacity
        self._now = time.time if now is None else now
        self._rows: dict[bytes, int] = {}
        self._lock = threading.Lock()

    def consume(self, jti: str, expires_at_unix: int) -> None:
        digest = hashlib.sha256(jti.encode("ascii")).digest()
        now = int(self._now())
        with self._lock:
            for key, expiry in tuple(self._rows.items()):
                if expiry <= now:
                    self._rows.pop(key, None)
            if digest in self._rows:
                raise ApprovalError("approval_consumed")
            if len(self._rows) >= self._capacity:
                raise ApprovalError("approval_registry_full")
            self._rows[digest] = expires_at_unix

    def snapshot(self) -> tuple[tuple[bytes, int], ...]:
        """Expose value-free rows for contract tests and operational metrics."""

        with self._lock:
            return tuple(self._rows.items())


class ApprovalEngine:
    """Mint and validate strict AES-GCM approval tickets."""

    def __init__(
        self,
        key: bytes,
        bindings: ApprovalBindings,
        *,
        document_bindings: ApprovalBindings | None = None,
        now: Callable[[], float] | None = None,
        random_bytes: Callable[[int], bytes] | None = None,
        boot_nonce: bytes | None = None,
        replay_capacity: int = DEFAULT_REPLAY_CAPACITY,
    ):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("approval key must contain 32 bytes")
        _validate_bindings(bindings)
        if document_bindings is not None:
            _validate_bindings(document_bindings)
        self._aead = AESGCM(key)
        self._bindings = bindings
        self._document_bindings = (
            bindings if document_bindings is None else document_bindings
        )
        self._now = time.time if now is None else now
        self._random_bytes = secrets.token_bytes if random_bytes is None else random_bytes
        raw_boot = self._random_bytes(16) if boot_nonce is None else boot_nonce
        if not isinstance(raw_boot, bytes) or len(raw_boot) != 16:
            raise ValueError("boot nonce must contain 16 bytes")
        self._boot_nonce = _b64url(raw_boot)
        self._consumed = ConsumedJTIRegistry(capacity=replay_capacity, now=self._now)

    @property
    def consumed_registry(self) -> ConsumedJTIRegistry:
        return self._consumed

    def mint_custom(
        self,
        *,
        authority: AuthorityContext,
        mode: str,
        source_sha256: str,
        protected_sha256: str,
        salt: str,
        generation_seed: bytes | None,
    ) -> tuple[str, int]:
        source_kind = (
            "custom_standard"
            if authority.scope == "public_guest"
            else "custom_invite"
        )
        payload = self._common_payload(
            kind="custom_text_v1",
            source_kind=source_kind,
            authority=authority,
            mode=mode,
            protected_sha256=protected_sha256,
            salt=salt,
            generation_seed=generation_seed,
        )
        payload["source_sha256"] = source_sha256
        _validate_ticket_payload(payload)
        return self._encrypt(payload), payload["expires_at_unix"]

    def mint_document(
        self,
        *,
        kind: str,
        authority: AuthorityContext,
        protected_sha256: str,
        salt: str,
        generation_seed: bytes,
        facts: DocumentFacts,
    ) -> tuple[str, int]:
        if kind not in _DOCUMENT_KEYS_BY_KIND:
            raise ApprovalError()
        source_kind = _source_kind_for_authority(kind, authority)
        payload = self._common_payload(
            kind=kind,
            source_kind=source_kind,
            authority=authority,
            mode="token",
            protected_sha256=protected_sha256,
            salt=salt,
            generation_seed=generation_seed,
        )
        payload.update(_document_payload(facts, synthetic=kind == "synthetic_document_v1"))
        _validate_ticket_payload(payload)
        return self._encrypt(payload), payload["expires_at_unix"]

    def inspect(
        self,
        ticket: str,
        *,
        authority: AuthorityContext,
        expected_kind: str,
    ) -> dict[str, object]:
        payload = self._decrypt(ticket)
        self._validate_runtime(payload, authority=authority, expected_kind=expected_kind)
        return payload

    def inspect_supported(
        self,
        ticket: str,
        *,
        authority: AuthorityContext,
        expected_kinds: frozenset[str],
    ) -> dict[str, object]:
        """Authenticate one ticket whose exact branch is selected by its ciphertext."""

        if (
            not isinstance(expected_kinds, frozenset)
            or not expected_kinds
            or not expected_kinds.issubset(_TICKET_KINDS)
        ):
            raise ApprovalError()
        payload = self._decrypt(ticket)
        kind = payload.get("kind")
        if kind not in expected_kinds:
            raise ApprovalError()
        self._validate_runtime(
            payload,
            authority=authority,
            expected_kind=str(kind),
        )
        return payload

    def consume(
        self,
        ticket: str,
        *,
        authority: AuthorityContext,
        expected_kind: str,
    ) -> dict[str, object]:
        payload = self.inspect(
            ticket,
            authority=authority,
            expected_kind=expected_kind,
        )
        self._consumed.consume(str(payload["jti"]), int(payload["expires_at_unix"]))
        return payload

    def consume_supported(
        self,
        ticket: str,
        *,
        authority: AuthorityContext,
        expected_kinds: frozenset[str],
    ) -> dict[str, object]:
        """Atomically consume one authenticated ticket from an exact branch set."""

        payload = self.inspect_supported(
            ticket,
            authority=authority,
            expected_kinds=expected_kinds,
        )
        self._consumed.consume(str(payload["jti"]), int(payload["expires_at_unix"]))
        return payload

    def _common_payload(
        self,
        *,
        kind: str,
        source_kind: str,
        authority: AuthorityContext,
        mode: str,
        protected_sha256: str,
        salt: str,
        generation_seed: bytes | None,
    ) -> dict[str, object]:
        if (
            kind not in _TICKET_KINDS
            or mode not in {"token", "surrogate"}
            or (kind != "custom_text_v1" and mode != "token")
        ):
            raise ApprovalError()
        _validate_authority(authority)
        issued = int(self._now())
        ttl = _KIND_TTLS[kind]
        bindings = self._bindings_for_kind(kind)
        payload: dict[str, object] = {
            "schema": TICKET_SCHEMA,
            "kind": kind,
            "jti": _b64url(self._fresh_bytes(16)),
            "boot_nonce": self._boot_nonce,
            "issued_at_unix": issued,
            "expires_at_unix": min(issued + ttl, authority.expires_at_unix),
            "scope": authority.scope,
            "session_nonce": authority.session_nonce,
            "mode": mode,
            "provider_id": bindings.provider_id,
            "provider_model": bindings.provider_model,
            "prompt_revision": bindings.prompt_revision,
            "http_contract_version": HTTP_CONTRACT_VERSION,
            "detector_code_sha256": bindings.detector_code_sha256,
            "detector_model_sha256": bindings.detector_model_sha256,
            "protected_sha256": protected_sha256,
            "salt": salt,
            "source_kind": source_kind,
        }
        if mode == "token":
            if not isinstance(generation_seed, bytes) or len(generation_seed) != 32:
                raise ApprovalError()
            payload["protection_generation_seed"] = _b64url(generation_seed)
            payload["protection_generation_revision"] = PROTECTION_GENERATION_REVISION
        elif generation_seed is not None:
            raise ApprovalError()
        return payload

    def _fresh_bytes(self, size: int) -> bytes:
        value = self._random_bytes(size)
        if not isinstance(value, bytes) or len(value) != size:
            raise RuntimeError("approval random source returned an invalid value")
        return value

    def _bindings_for_kind(self, kind: str) -> ApprovalBindings:
        return self._bindings if kind == "custom_text_v1" else self._document_bindings

    def _encrypt(self, payload: Mapping[str, object]) -> str:
        nonce = self._fresh_bytes(12)
        plaintext = json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return _b64url(nonce + self._aead.encrypt(nonce, plaintext, APPROVAL_CONTEXT))

    def _decrypt(self, ticket: str) -> dict[str, object]:
        packed = _decode_b64url(ticket)
        if len(packed) < 12 + 16:
            raise ApprovalError()
        nonce, ciphertext = packed[:12], packed[12:]
        try:
            plaintext = self._aead.decrypt(nonce, ciphertext, APPROVAL_CONTEXT)
            payload = json.loads(plaintext)
        except Exception:
            raise ApprovalError() from None
        if type(payload) is not dict:
            raise ApprovalError()
        _validate_ticket_payload(payload)
        return payload

    def _validate_runtime(
        self,
        payload: Mapping[str, object],
        *,
        authority: AuthorityContext,
        expected_kind: str,
    ) -> None:
        _validate_authority(authority)
        if expected_kind not in _TICKET_KINDS or payload.get("kind") != expected_kind:
            raise ApprovalError()
        now = int(self._now())
        if int(payload["expires_at_unix"]) <= now:
            raise ApprovalError("approval_expired")
        expected_source_kind = _source_kind_for_authority(expected_kind, authority)
        bindings = self._bindings_for_kind(expected_kind)
        checks = (
            payload.get("boot_nonce") == self._boot_nonce,
            payload.get("scope") == authority.scope,
            payload.get("session_nonce") == authority.session_nonce,
            payload.get("source_kind") == expected_source_kind,
            payload.get("provider_id") == bindings.provider_id,
            payload.get("provider_model") == bindings.provider_model,
            payload.get("prompt_revision") == bindings.prompt_revision,
            payload.get("http_contract_version") == HTTP_CONTRACT_VERSION,
            payload.get("detector_code_sha256") == bindings.detector_code_sha256,
            payload.get("detector_model_sha256") == bindings.detector_model_sha256,
        )
        if not all(checks):
            raise ApprovalError()


_DOCUMENT_KEYS_BY_KIND = {
    "standard_document_v1": _DOCUMENT_KEYS,
    "invite_document_v1": _DOCUMENT_KEYS,
    "synthetic_document_v1": _DOCUMENT_KEYS | _SYNTHETIC_KEYS,
}


def _validate_bindings(bindings: ApprovalBindings) -> None:
    values = (bindings.provider_id, bindings.provider_model, bindings.prompt_revision)
    if any(not isinstance(value, str) or not 1 <= len(value) <= 128 for value in values):
        raise ValueError("approval binding is invalid")
    if any(
        _HASH_PATTERN.fullmatch(value) is None
        for value in (bindings.detector_code_sha256, bindings.detector_model_sha256)
    ):
        raise ValueError("approval hash binding is invalid")


def _source_kind_for_authority(kind: str, authority: AuthorityContext) -> str:
    if kind == "custom_text_v1":
        return "custom_standard" if authority.scope == "public_guest" else "custom_invite"
    if kind == "standard_document_v1" and authority.scope == "public_guest":
        return "document_standard"
    if kind == "invite_document_v1" and authority.scope == "priority_invite":
        return "document_invite"
    if kind == "synthetic_document_v1":
        return "synthetic_document"
    raise ApprovalError()


def _validate_authority(authority: AuthorityContext) -> None:
    if not isinstance(authority, AuthorityContext):
        raise ApprovalError()
    if authority.scope == "public_guest":
        valid = authority.service_class == "standard" and authority.subject_id is None
    elif authority.scope == "priority_invite":
        valid = authority.service_class == "priority" and isinstance(authority.subject_id, str)
    else:
        valid = False
    if (
        not valid
        or not isinstance(authority.session_nonce, str)
        or _B64_PATTERN.fullmatch(authority.session_nonce) is None
        or type(authority.expires_at_unix) is not int
    ):
        raise ApprovalError()


def _validate_ticket_payload(payload: Mapping[str, object]) -> None:
    kind = payload.get("kind")
    mode = payload.get("mode")
    if kind not in _TICKET_KINDS or mode not in {"token", "surrogate"}:
        raise ApprovalError()
    if kind != "custom_text_v1" and mode != "token":
        raise ApprovalError()
    expected = _COMMON_KEYS | (_TOKEN_KEYS if mode == "token" else frozenset())
    if kind == "custom_text_v1":
        expected |= _CUSTOM_KEYS
    else:
        expected |= _DOCUMENT_KEYS_BY_KIND[str(kind)]
    if set(payload) != expected:
        raise ApprovalError()
    if payload.get("schema") != TICKET_SCHEMA:
        raise ApprovalError()
    source_kind = payload.get("source_kind")
    if source_kind not in _SOURCE_KINDS[str(kind)]:
        raise ApprovalError()
    if payload.get("scope") not in {"public_guest", "priority_invite"}:
        raise ApprovalError()
    if not isinstance(payload.get("session_nonce"), str):
        raise ApprovalError()
    for key in ("jti", "boot_nonce", "session_nonce", "salt"):
        value = payload.get(key)
        if not isinstance(value, str) or _B64_PATTERN.fullmatch(value) is None:
            raise ApprovalError()
    for key in ("issued_at_unix", "expires_at_unix"):
        if type(payload.get(key)) is not int or int(payload[key]) < 1:
            raise ApprovalError()
    if int(payload["expires_at_unix"]) <= int(payload["issued_at_unix"]):
        raise ApprovalError()
    for key in (
        "provider_id",
        "provider_model",
        "prompt_revision",
    ):
        value = payload.get(key)
        if not isinstance(value, str) or not 1 <= len(value) <= 128:
            raise ApprovalError()
    if payload.get("http_contract_version") != HTTP_CONTRACT_VERSION:
        raise ApprovalError()
    for key in (
        "detector_code_sha256",
        "detector_model_sha256",
        "protected_sha256",
    ):
        if not isinstance(payload.get(key), str) or _HASH_PATTERN.fullmatch(str(payload[key])) is None:
            raise ApprovalError()
    if mode == "token":
        if payload.get("protection_generation_revision") != PROTECTION_GENERATION_REVISION:
            raise ApprovalError()
        if len(_decode_b64url(str(payload["protection_generation_seed"]))) != 32:
            raise ApprovalError()
    if kind == "custom_text_v1":
        if _HASH_PATTERN.fullmatch(str(payload.get("source_sha256", ""))) is None:
            raise ApprovalError()
    else:
        _validate_document_payload(payload, synthetic=kind == "synthetic_document_v1")


def _document_payload(facts: DocumentFacts, *, synthetic: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_pdf_sha256": facts.source_pdf_sha256,
        "parser_revision": facts.parser_revision,
        "extraction_revision": facts.extraction_revision,
        "segmentation_revision": facts.segmentation_revision,
        "page_count": facts.page_count,
        "character_count": facts.character_count,
        "segment_count": facts.segment_count,
        "omitted_visual_page_numbers": list(facts.omitted_visual_page_numbers),
        "source_receipt_id": facts.source_receipt_id,
        "segment_manifest_sha256": facts.segment_manifest_sha256,
    }
    if synthetic:
        payload["scenario_id"] = facts.scenario_id
        payload["scenario_registry_sha256"] = facts.scenario_registry_sha256
    elif facts.scenario_id is not None or facts.scenario_registry_sha256 is not None:
        raise ApprovalError()
    return payload


def _validate_document_payload(payload: Mapping[str, object], *, synthetic: bool) -> None:
    for key in ("source_pdf_sha256", "segment_manifest_sha256"):
        if _HASH_PATTERN.fullmatch(str(payload.get(key, ""))) is None:
            raise ApprovalError()
    for key in ("parser_revision", "extraction_revision", "segmentation_revision"):
        value = payload.get(key)
        if not isinstance(value, str) or not 1 <= len(value) <= 64:
            raise ApprovalError()
    numeric_bounds = {
        "page_count": (1, 10),
        "character_count": (1, 8_000),
        "segment_count": (1, 80),
    }
    for key, (minimum, maximum) in numeric_bounds.items():
        value = payload.get(key)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ApprovalError()
    pages = payload.get("omitted_visual_page_numbers")
    if (
        type(pages) is not list
        or any(type(page) is not int or page < 1 for page in pages)
        or pages != sorted(set(pages))
        or any(page > int(payload["page_count"]) for page in pages)
    ):
        raise ApprovalError()
    receipt = payload.get("source_receipt_id")
    if not isinstance(receipt, str) or len(_decode_b64url(receipt)) != 16:
        raise ApprovalError()
    if synthetic:
        scenario = payload.get("scenario_id")
        if not isinstance(scenario, str) or not 1 <= len(scenario) <= 64 or not scenario.isascii():
            raise ApprovalError()
        if _HASH_PATTERN.fullmatch(str(payload.get("scenario_registry_sha256", ""))) is None:
            raise ApprovalError()

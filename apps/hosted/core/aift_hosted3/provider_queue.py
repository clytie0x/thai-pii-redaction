"""Content-free, single-process provider queue for Hosted 3.0."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import secrets
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .approval import ApprovalEngine, ApprovalError
from .authority import AuthorityContext


QUEUE_KEY_CONTEXT = b"aiguard-hosted3-provider-queue-key-v1"
QUEUE_CAPABILITY_CONTEXT = b"aiguard-hosted3-provider-queue-capability-v1"
CLAIM_TOKEN_CONTEXT = b"aiguard-hosted3-provider-claim-v1"
QUEUE_CAPABILITY_SCHEMA = "aiguard-provider-queue-v1"
CLAIM_TOKEN_SCHEMA = "aiguard-provider-claim-v1"

PROVIDER_SLOTS = 2
TOTAL_ACTIVE_CAPACITY = 12
STANDARD_ACTIVE_CAPACITY = 8
PRIORITY_ACTIVE_CAPACITY = 4
QUEUE_CAPABILITY_TTL_SECONDS = 900
QUEUE_WAIT_CAP_SECONDS = 600
PROVIDER_MARGIN_SECONDS = 210
QUEUE_JOIN_MINIMUM_REMAINING_SECONDS = 900
CLAIM_TTL_SECONDS = 15
CLAIM_LONG_POLL_SECONDS = 25
CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS = 5
CLAIM_HTTP_ACK_TTL_SECONDS = (
    CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS + CLAIM_TTL_SECONDS
)
CLAIM_MAX_ENCODED_TTL_SECONDS = CLAIM_HTTP_ACK_TTL_SECONDS + 1
STATUS_POLL_AFTER_MS = 10_000
TERMINAL_RETENTION_SECONDS = 300
MAX_RECORDS = 64
LEGACY_ROUNDTRIP_WAIT_SECONDS = 5.0
STANDARD_QUEUE_JOIN_PER_MINUTE = 1
STANDARD_QUEUE_JOIN_BURST = 1
PRIORITY_QUEUE_JOIN_PER_MINUTE = 6
PRIORITY_QUEUE_JOIN_BURST = 2
STANDARD_IDLE_BORROW_SECONDS = 10

CLAIM_GRANT_SEQUENCE = ("priority", "priority", "priority", "standard")
SUPPORTED_APPROVAL_KINDS = frozenset(
    {
        "custom_text_v1",
        "standard_document_v1",
        "invite_document_v1",
        "synthetic_document_v1",
    }
)

_B64_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_SUBJECT_PATTERN = re.compile(r"^sub_[A-Za-z0-9_-]{22}$")
_ACTIVE_STATES = frozenset({"queued", "claim_ready", "running"})
_TERMINAL_STATES = frozenset({"complete", "failed", "cancelled", "expired"})
_FAILURE_REASONS = frozenset(
    {
        "provider_failed",
        "approval_invalid",
        "document_integrity_failed",
        "document_parser_unavailable",
        "residual_pii",
        "restore_failed",
        "internal_error",
    }
)
class ProviderQueueError(ValueError):
    """A fixed value-free scheduler rejection safe for HTTP translation."""

    def __init__(self, code: str = "queue_invalid"):
        self.code = code
        super().__init__(code)


@dataclass(slots=True, repr=False)
class QueueExecution:
    """Authenticated execute facts released only after claim-ready admission."""

    queue_id: str
    slot: int
    revision: int
    service_class: str
    approval: dict[str, object] = field(repr=False)

    def clear(self) -> None:
        self.approval.clear()


@dataclass(slots=True, repr=False)
class LegacyQueueExecution:
    """Internal lease for the byte-compatible Priority `/roundtrip` adapter."""

    queue_id: str
    slot: int
    revision: int


@dataclass(slots=True, repr=False)
class _QueueRecord:
    queue_id: str
    binding_digest: bytes
    owner_digest: bytes
    service_class: str
    approval_jti_digest: bytes
    capability_jti_digest: bytes
    capability_active: bool
    enqueued_at_unix: int
    queue_expires_at_unix: int
    capability_expires_at_unix: int
    fairness_age: int
    state: str = "queued"
    revision: int = 1
    reason: str | None = None
    claim_miss_count: int = 0
    claim_jti_digest: bytes | None = None
    claim_expires_at_unix: int | None = None
    claim_acknowledgement_pending: bool = False
    slot: int | None = None
    claim_poll_seen: bool = False
    poll_active: bool = False
    provider_attempt_count: int = 0
    retain_until_unix: int | None = None
    legacy_internal: bool = False


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_b64url(value: object) -> bytes:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 4096
        or _B64_PATTERN.fullmatch(value) is None
    ):
        raise ProviderQueueError()
    try:
        decoded = base64.b64decode(
            value + "=" * (-len(value) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (TypeError, ValueError):
        raise ProviderQueueError() from None
    if _b64url(decoded) != value:
        raise ProviderQueueError()
    return decoded


def derive_provider_queue_key(cookie_signing_key: bytes) -> bytes:
    """Derive one queue root key without introducing another deployed secret."""

    if not isinstance(cookie_signing_key, bytes) or len(cookie_signing_key) < 32:
        raise ValueError("provider queue key source is invalid")
    return hmac.new(
        cookie_signing_key,
        QUEUE_KEY_CONTEXT,
        hashlib.sha256,
    ).digest()


class ProviderQueue:
    """Atomic two-slot scheduler whose records never contain caller content."""

    def __init__(
        self,
        key: bytes,
        approval: ApprovalEngine,
        *,
        now: Callable[[], float] | None = None,
        monotonic: Callable[[], float] | None = None,
        random_bytes: Callable[[int], bytes] | None = None,
        boot_nonce: bytes | None = None,
    ):
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("provider queue key must contain 32 bytes")
        if not isinstance(approval, ApprovalEngine):
            raise ValueError("provider queue approval engine is invalid")
        self._capability_aead = AESGCM(
            hmac.new(key, QUEUE_CAPABILITY_CONTEXT, hashlib.sha256).digest()
        )
        self._claim_aead = AESGCM(
            hmac.new(key, CLAIM_TOKEN_CONTEXT, hashlib.sha256).digest()
        )
        self._approval = approval
        self._now = time.time if now is None else now
        self._monotonic = time.monotonic if monotonic is None else monotonic
        self._random_bytes = secrets.token_bytes if random_bytes is None else random_bytes
        raw_boot = self._fresh_bytes(16) if boot_nonce is None else boot_nonce
        if not isinstance(raw_boot, bytes) or len(raw_boot) != 16:
            raise ValueError("provider queue boot nonce must contain 16 bytes")
        self._boot_nonce = _b64url(raw_boot)
        self._records: dict[str, _QueueRecord] = {}
        self._binding_index: dict[bytes, str] = {}
        self._owner_index: dict[bytes, str] = {}
        self._eligible: set[str] = set()
        self._active_polls: set[bytes] = set()
        self._poll_capabilities: dict[str, dict[str, object]] = {}
        self._legacy_waiters: set[str] = set()
        self._claim_deliveries: dict[str, str] = {}
        self._free_slots: set[int] = set(range(PROVIDER_SLOTS))
        self._grant_cursor = 0
        self._fairness_counter = 0
        # Verified-authority queue admission is owned here, rather than by a
        # cookie parser in Nginx, because only this process can apply the
        # reviewed Standard idle-borrow exception without weakening it under
        # contention. Values are token counts and monotonic wall timestamps;
        # no raw authority, cookie, ticket, or content is retained.
        self._join_buckets: dict[bytes, tuple[float, float]] = {}
        self._standard_last_provider_admission: dict[bytes, int] = {}
        self._condition = threading.Condition(threading.Lock())

    def admit_legacy_roundtrip(
        self,
        *,
        authority: AuthorityContext,
        wait_seconds: float = LEGACY_ROUNDTRIP_WAIT_SECONDS,
        cancelled: Callable[[], bool] | None = None,
    ) -> LegacyQueueExecution | None:
        """Admit one Priority legacy call through the shared provider slots.

        This compatibility adapter creates no caller capability and retains no
        request body.  Selection and the `queued -> running` transition happen
        atomically inside the same blocking request.  Returning ``None`` means
        the caller must render the legacy fixed ``429 rate_limited`` response.
        """

        _validate_authority(authority)
        if (
            authority.service_class != "priority"
            or authority.scope != "priority_invite"
            or not isinstance(wait_seconds, (int, float))
            or not 0 <= float(wait_seconds) <= LEGACY_ROUNDTRIP_WAIT_SECONDS
            or (cancelled is not None and not callable(cancelled))
        ):
            raise ProviderQueueError()
        started = self._monotonic()
        wall_now = float(self._now())
        now = math.floor(wall_now)
        binding = _binding_digest(authority)
        owner = _owner_digest(authority)
        queue_id: str | None = None
        with self._condition:
            self._advance_locked(now)
            self._prune_locked(now)
            if authority.expires_at_unix - now < PROVIDER_MARGIN_SECONDS:
                return None
            try:
                self._ensure_record_capacity_locked()
            except ProviderQueueError:
                return None
            if self._active_record_for_owner_locked(owner) is not None:
                return None
            active = self._active_records_locked()
            if len(active) >= TOTAL_ACTIVE_CAPACITY:
                return None
            if (
                sum(row.service_class == "priority" for row in active)
                >= PRIORITY_ACTIVE_CAPACITY
            ):
                return None
            queue_expires = min(
                max(now + 1, math.ceil(wall_now + float(wait_seconds))),
                authority.expires_at_unix - PROVIDER_MARGIN_SECONDS,
            )
            if queue_expires <= now:
                return None
            queue_id = _b64url(self._fresh_bytes(16))
            internal_jti = _b64url(self._fresh_bytes(16))
            self._fairness_counter += 1
            record = _QueueRecord(
                queue_id=queue_id,
                binding_digest=binding,
                owner_digest=owner,
                service_class="priority",
                approval_jti_digest=_digest_ascii(internal_jti),
                capability_jti_digest=_digest_ascii(internal_jti),
                capability_active=False,
                enqueued_at_unix=now,
                queue_expires_at_unix=queue_expires,
                capability_expires_at_unix=queue_expires,
                fairness_age=self._fairness_counter,
                claim_poll_seen=True,
                poll_active=True,
                legacy_internal=True,
            )
            self._records[queue_id] = record
            self._binding_index[binding] = queue_id
            self._owner_index[owner] = queue_id
            self._eligible.add(queue_id)
            self._legacy_waiters.add(queue_id)
            self._condition.notify_all()
            try:
                while True:
                    if cancelled is not None and cancelled():
                        self._terminal_locked(
                            record,
                            "cancelled",
                            "cancelled",
                            int(self._now()),
                        )
                        return None
                    current_now = int(self._now())
                    self._advance_locked(current_now)
                    self._dispatch_locked(current_now)
                    if record.state == "running" and record.slot is not None:
                        return LegacyQueueExecution(
                            queue_id=record.queue_id,
                            slot=record.slot,
                            revision=record.revision,
                        )
                    if record.state in _TERMINAL_STATES:
                        return None
                    remaining = float(wait_seconds) - (
                        self._monotonic() - started
                    )
                    if remaining <= 0:
                        self._terminal_locked(
                            record,
                            "expired",
                            "deadline_expired",
                            int(self._now()),
                        )
                        return None
                    self._condition.wait(timeout=min(remaining, 0.1))
            finally:
                self._legacy_waiters.discard(queue_id)
                if record.state != "running":
                    self._eligible.discard(queue_id)
                    record.poll_active = False
                self._condition.notify_all()

    def finish_legacy_roundtrip(
        self,
        execution: LegacyQueueExecution,
        *,
        succeeded: bool,
    ) -> None:
        """Release a legacy slot without inventing unavailable attempt facts."""

        if not isinstance(execution, LegacyQueueExecution) or type(succeeded) is not bool:
            raise ProviderQueueError()
        now = int(self._now())
        with self._condition:
            record = self._records.get(execution.queue_id)
            if (
                record is None
                or not record.legacy_internal
                or record.state != "running"
                or record.slot != execution.slot
                or record.revision != execution.revision
            ):
                raise ProviderQueueError("queue_not_ready")
            self._release_slot_locked(record)
            record.state = "complete" if succeeded else "failed"
            record.reason = None if succeeded else "provider_failed"
            record.provider_attempt_count = 0
            record.revision += 1
            record.retain_until_unix = now + TERMINAL_RETENTION_SECONDS
            record.poll_active = False
            self._eligible.discard(record.queue_id)
            self._legacy_waiters.discard(record.queue_id)
            self._condition.notify_all()

    def join(self, ticket: str, *, authority: AuthorityContext) -> dict[str, object]:
        """Consume one preview approval and replace it with a queue capability."""

        _validate_authority(authority)
        inspected = self._approval.inspect_supported(
            ticket,
            authority=authority,
            expected_kinds=SUPPORTED_APPROVAL_KINDS,
        )
        now = int(self._now())
        if authority.expires_at_unix - now < QUEUE_JOIN_MINIMUM_REMAINING_SECONDS:
            raise ProviderQueueError("queue_expired")
        binding = _binding_digest(authority)
        owner = _owner_digest(authority)
        with self._condition:
            self._advance_locked(now)
            self._prune_locked(now)
            self._ensure_record_capacity_locked()
            active = self._active_record_for_owner_locked(owner)
            if active is not None:
                raise ProviderQueueError("queue_already_active")
            self._consume_join_rate_locked(authority, owner, now)
            if len(self._active_records_locked()) >= TOTAL_ACTIVE_CAPACITY:
                raise ProviderQueueError("queue_full")
            class_capacity = (
                STANDARD_ACTIVE_CAPACITY
                if authority.service_class == "standard"
                else PRIORITY_ACTIVE_CAPACITY
            )
            if (
                sum(
                    row.service_class == authority.service_class
                    for row in self._active_records_locked()
                )
                >= class_capacity
            ):
                raise ProviderQueueError("queue_full")
            capability_expires = min(
                now + QUEUE_CAPABILITY_TTL_SECONDS,
                authority.expires_at_unix,
            )
            queue_expires = min(
                now + QUEUE_WAIT_CAP_SECONDS,
                authority.expires_at_unix - PROVIDER_MARGIN_SECONDS,
                capability_expires - PROVIDER_MARGIN_SECONDS,
            )
            if queue_expires <= now:
                raise ProviderQueueError("queue_expired")
            queue_id = _b64url(self._fresh_bytes(16))
            capability_jti = _b64url(self._fresh_bytes(16))
            capability_payload = {
                "schema": QUEUE_CAPABILITY_SCHEMA,
                "kind": "provider_queue_v1",
                "jti": capability_jti,
                "boot_nonce": self._boot_nonce,
                "queue_id": queue_id,
                "approval_jti": inspected["jti"],
                "approval": inspected,
                "scope": authority.scope,
                "service_class": authority.service_class,
                "session_nonce": authority.session_nonce,
                "subject_id": authority.subject_id,
                "issued_at_unix": now,
                "expires_at_unix": capability_expires,
                "queue_expires_at_unix": queue_expires,
            }
            capability = self._encrypt(
                capability_payload,
                aead=self._capability_aead,
                context=QUEUE_CAPABILITY_CONTEXT,
            )
            consumed = self._approval.consume_supported(
                ticket,
                authority=authority,
                expected_kinds=SUPPORTED_APPROVAL_KINDS,
            )
            if consumed != inspected:
                raise ProviderQueueError()
            self._fairness_counter += 1
            record = _QueueRecord(
                queue_id=queue_id,
                binding_digest=binding,
                owner_digest=owner,
                service_class=authority.service_class,
                approval_jti_digest=_digest_ascii(str(inspected["jti"])),
                capability_jti_digest=_digest_ascii(capability_jti),
                capability_active=True,
                enqueued_at_unix=now,
                queue_expires_at_unix=queue_expires,
                capability_expires_at_unix=capability_expires,
                fairness_age=self._fairness_counter,
            )
            self._records[queue_id] = record
            self._binding_index[binding] = queue_id
            self._owner_index[owner] = queue_id
            self._condition.notify_all()
            return {
                "state": "queued",
                "position": self._position_locked(record),
                "queue_expires_at_unix": queue_expires,
                "poll_after_ms": STATUS_POLL_AFTER_MS,
                "queue_capability": capability,
            }

    def status(self, *, authority: AuthorityContext) -> dict[str, object]:
        """Return a value-free read-only view without pruning or fairness mutation."""

        _validate_authority(authority)
        now = int(self._now())
        binding = _binding_digest(authority)
        with self._condition:
            record = self._record_for_binding_locked(binding)
            if record is None:
                return _status_absent()
            state, reason = self._derived_status_locked(record, now)
            return {
                "state": state,
                "position": (
                    self._position_locked(record)
                    if state in {"queued", "paused"}
                    else None
                ),
                "reason": reason,
                "enqueued_at_unix": record.enqueued_at_unix,
                "queue_expires_at_unix": record.queue_expires_at_unix,
                "poll_after_ms": STATUS_POLL_AFTER_MS,
                "automatic_execute_possible": state
                in {"queued", "paused", "claim_ready", "running"},
            }

    def claim(
        self,
        queue_capability: str,
        *,
        last_revision: int,
        authority: AuthorityContext,
        wait_seconds: float = CLAIM_LONG_POLL_SECONDS,
        cancelled: Callable[[], bool] | None = None,
        execute_ack_pending: bool = False,
    ) -> dict[str, object]:
        """Hold one authenticated eligibility request and return at most one claim."""

        _validate_authority(authority)
        if (
            type(last_revision) is not int
            or last_revision < 0
            or not isinstance(wait_seconds, (int, float))
            or not 0 <= float(wait_seconds) <= CLAIM_LONG_POLL_SECONDS
            or (cancelled is not None and not callable(cancelled))
            or type(execute_ack_pending) is not bool
        ):
            raise ProviderQueueError()
        capability = self._validated_capability(
            queue_capability,
            authority=authority,
        )
        queue_id = str(capability["queue_id"])
        capability_jti = str(capability["jti"])
        poll_binding = {
            "jti": capability_jti,
            "scope": str(capability["scope"]),
            "session_nonce": str(capability["session_nonce"]),
            "subject_id": capability["subject_id"],
        }
        binding = _binding_digest(authority)
        started = self._monotonic()
        with self._condition:
            self._advance_locked(int(self._now()))
            record = self._matching_record_locked(
                queue_id,
                binding=binding,
                capability_jti=capability_jti,
            )
            if last_revision > record.revision:
                raise ProviderQueueError()
            if record.state == "claim_ready":
                raise ProviderQueueError("queue_already_active")
            if record.state != "queued":
                return self._claim_state_locked(record)
            if binding in self._active_polls:
                raise ProviderQueueError("queue_already_active")

            self._active_polls.add(binding)
            self._eligible.add(queue_id)
            self._poll_capabilities[queue_id] = poll_binding
            capability.clear()
            record.claim_poll_seen = True
            record.poll_active = True
            record.claim_acknowledgement_pending = execute_ack_pending
            try:
                while True:
                    if cancelled is not None and cancelled():
                        raise ProviderQueueError("queue_poll_cancelled")
                    now = int(self._now())
                    self._advance_locked(now)
                    self._dispatch_locked(now)
                    current = self._records.get(queue_id)
                    if (
                        current is not None
                        and current.binding_digest == binding
                        and current.capability_jti_digest
                        == _digest_ascii(capability_jti)
                        and current.state == "expired"
                        and current.reason == "deadline_expired"
                    ):
                        raise ProviderQueueError("queue_expired")
                    record = self._matching_record_locked(
                        queue_id,
                        binding=binding,
                        capability_jti=capability_jti,
                    )
                    delivery = self._claim_deliveries.pop(queue_id, None)
                    if record.state == "claim_ready" and delivery is not None:
                        return {
                            "state": "claim_ready",
                            "revision": record.revision,
                            "claim_token": delivery,
                            "claim_expires_at_unix": record.claim_expires_at_unix,
                            "claim_window_seconds": (
                                CLAIM_HTTP_ACK_TTL_SECONDS
                                if record.claim_acknowledgement_pending
                                else CLAIM_TTL_SECONDS
                            ),
                            "queue_expires_at_unix": record.queue_expires_at_unix,
                        }
                    if record.state != "queued":
                        return self._claim_state_locked(record)
                    remaining = float(wait_seconds) - (self._monotonic() - started)
                    if remaining <= 0:
                        return self._claim_state_locked(record)
                    self._condition.wait(timeout=min(remaining, 1.0))
            finally:
                self._active_polls.discard(binding)
                self._eligible.discard(queue_id)
                self._poll_capabilities.pop(queue_id, None)
                current = self._records.get(queue_id)
                if current is not None:
                    current.poll_active = False
                    if current.state == "queued":
                        current.claim_acknowledgement_pending = False
                self._condition.notify_all()

    def wake_claims(self) -> None:
        """Wake claim waiters so an external disconnect signal is observed."""

        with self._condition:
            self._condition.notify_all()

    def abandon_undelivered_claim(
        self,
        queue_capability: str,
        claim_token: str,
        *,
        authority: AuthorityContext,
    ) -> bool:
        """Release a claim that the HTTP transport proved it did not deliver."""

        _validate_authority(authority)
        capability = self._validated_capability(
            queue_capability,
            authority=authority,
            allow_expired=True,
        )
        claim = self._validated_claim(
            claim_token,
            authority=authority,
            allow_expired=True,
        )
        binding = _binding_digest(authority)
        try:
            with self._condition:
                record = self._matching_record_locked(
                    str(capability["queue_id"]),
                    binding=binding,
                    capability_jti=str(capability["jti"]),
                )
                checks = (
                    record.state == "claim_ready",
                    record.claim_acknowledgement_pending is True,
                    claim.get("queue_id") == record.queue_id == capability.get("queue_id"),
                    claim.get("capability_jti") == capability.get("jti"),
                    claim.get("revision") == record.revision,
                    claim.get("slot") == record.slot,
                    _digest_ascii(str(claim.get("jti"))) == record.claim_jti_digest,
                )
                if not all(checks):
                    return False
                self._release_slot_locked(record)
                self._claim_deliveries.pop(record.queue_id, None)
                record.state = "queued"
                record.reason = None
                record.revision += 1
                record.claim_jti_digest = None
                record.claim_expires_at_unix = None
                record.claim_acknowledgement_pending = False
                self._condition.notify_all()
                return True
        finally:
            capability.clear()
            claim.clear()

    def begin_execute(
        self,
        queue_capability: str,
        claim_token: str,
        *,
        authority: AuthorityContext,
    ) -> QueueExecution:
        """Atomically consume one matching claim-ready transition before I/O."""

        _validate_authority(authority)
        capability = self._validated_capability(
            queue_capability,
            authority=authority,
        )
        claim = self._validated_claim(claim_token, authority=authority)
        now = int(self._now())
        binding = _binding_digest(authority)
        try:
            with self._condition:
                self._advance_locked(now)
                record = self._records.get(str(capability["queue_id"]))
                if (
                    record is None
                    or record.binding_digest != binding
                    or record.capability_jti_digest
                    != _digest_ascii(str(capability["jti"]))
                ):
                    raise ProviderQueueError()
                # A valid, correctly bound capability can become terminal while
                # this request races cancellation.  It is not a forged
                # capability; the exact claim is simply no longer executable.
                if not record.capability_active:
                    raise ProviderQueueError("queue_not_ready")
                checks = (
                    record.state == "claim_ready",
                    claim.get("queue_id") == record.queue_id == capability.get("queue_id"),
                    claim.get("capability_jti") == capability.get("jti"),
                    claim.get("revision") == record.revision,
                    claim.get("slot") == record.slot,
                    _digest_ascii(str(claim.get("jti"))) == record.claim_jti_digest,
                    record.claim_expires_at_unix is not None,
                    int(record.claim_expires_at_unix or 0) > now,
                    record.queue_expires_at_unix > now,
                )
                if not all(checks):
                    raise ProviderQueueError("queue_not_ready")
                record.state = "running"
                record.reason = None
                record.revision += 1
                if record.service_class == "standard":
                    self._standard_last_provider_admission[record.owner_digest] = now
                record.claim_acknowledgement_pending = False
                self._claim_deliveries.pop(record.queue_id, None)
                self._eligible.discard(record.queue_id)
                self._condition.notify_all()
                return QueueExecution(
                    queue_id=record.queue_id,
                    slot=int(record.slot),
                    revision=record.revision,
                    service_class=record.service_class,
                    approval=dict(capability["approval"]),
                )
        finally:
            capability.clear()
            claim.clear()

    def finish(
        self,
        execution: QueueExecution,
        *,
        succeeded: bool,
        attempt_count: int = 0,
        failure_reason: str | None = None,
    ) -> None:
        """Release one running slot after verified result or value-free failure."""

        if (
            not isinstance(execution, QueueExecution)
            or type(succeeded) is not bool
            or type(attempt_count) is not int
            or not 0 <= attempt_count <= 3
            or (succeeded and attempt_count < 1)
            or (succeeded and failure_reason is not None)
            or (
                not succeeded
                and failure_reason is not None
                and failure_reason not in _FAILURE_REASONS
            )
        ):
            raise ProviderQueueError()
        now = int(self._now())
        with self._condition:
            record = self._records.get(execution.queue_id)
            if (
                record is None
                or record.state != "running"
                or record.slot != execution.slot
                or record.revision != execution.revision
            ):
                raise ProviderQueueError("queue_not_ready")
            self._release_slot_locked(record)
            record.state = "complete" if succeeded else "failed"
            record.reason = (
                None
                if succeeded
                else failure_reason
                if failure_reason is not None
                else "provider_failed"
            )
            record.capability_active = False
            record.provider_attempt_count = attempt_count
            record.revision += 1
            record.retain_until_unix = now + TERMINAL_RETENTION_SECONDS
            self._condition.notify_all()

    def cancel(self, *, authority: AuthorityContext) -> None:
        """Cancel a non-running queue entry; absence and terminal states are idempotent."""

        _validate_authority(authority)
        now = int(self._now())
        binding = _binding_digest(authority)
        with self._condition:
            self._advance_locked(now)
            record = self._record_for_binding_locked(binding)
            if record is None:
                return
            if record.state == "running":
                raise ProviderQueueError("provider_already_running")
            if record.state in _TERMINAL_STATES:
                return
            self._release_slot_locked(record)
            self._eligible.discard(record.queue_id)
            self._claim_deliveries.pop(record.queue_id, None)
            record.state = "cancelled"
            record.reason = "cancelled"
            record.capability_active = False
            record.revision += 1
            record.retain_until_unix = now + TERMINAL_RETENTION_SECONDS
            self._condition.notify_all()

    def tick(self) -> None:
        """Advance deadlines/missed claims and dispatch eligible waiters."""

        now = int(self._now())
        with self._condition:
            self._advance_locked(now)
            self._prune_locked(now)
            self._dispatch_locked(now)
            self._condition.notify_all()

    def snapshot(self) -> tuple[dict[str, object], ...]:
        """Expose only value-free scheduler facts for metrics and contract tests."""

        with self._condition:
            return tuple(
                {
                    "queue_id_sha256": hashlib.sha256(
                        row.queue_id.encode("ascii")
                    ).hexdigest(),
                    "binding_sha256": row.binding_digest.hex(),
                    "owner_sha256": row.owner_digest.hex(),
                    "service_class": row.service_class,
                    "state": row.state,
                    "reason": row.reason,
                    "revision": row.revision,
                    "claim_miss_count": row.claim_miss_count,
                    "provider_attempt_count": row.provider_attempt_count,
                    "enqueued_at_unix": row.enqueued_at_unix,
                    "queue_expires_at_unix": row.queue_expires_at_unix,
                    "slot": row.slot,
                }
                for row in sorted(
                    self._records.values(),
                    key=lambda value: value.fairness_age,
                )
            )

    def _validated_capability(
        self,
        value: str,
        *,
        authority: AuthorityContext,
        allow_expired: bool = False,
    ) -> dict[str, object]:
        payload = self._decrypt(
            value,
            aead=self._capability_aead,
            context=QUEUE_CAPABILITY_CONTEXT,
        )
        expected = {
            "schema",
            "kind",
            "jti",
            "boot_nonce",
            "queue_id",
            "approval_jti",
            "approval",
            "scope",
            "service_class",
            "session_nonce",
            "subject_id",
            "issued_at_unix",
            "expires_at_unix",
            "queue_expires_at_unix",
        }
        if set(payload) != expected:
            raise ProviderQueueError()
        if (
            payload.get("schema") != QUEUE_CAPABILITY_SCHEMA
            or payload.get("kind") != "provider_queue_v1"
            or payload.get("boot_nonce") != self._boot_nonce
            or payload.get("scope") != authority.scope
            or payload.get("service_class") != authority.service_class
            or payload.get("session_nonce") != authority.session_nonce
            or payload.get("subject_id") != authority.subject_id
        ):
            raise ProviderQueueError()
        for key in ("jti", "queue_id", "approval_jti", "boot_nonce", "session_nonce"):
            _require_b64(payload.get(key), decoded_bytes=None)
        if len(_decode_b64url(payload["jti"])) != 16:
            raise ProviderQueueError()
        if len(_decode_b64url(payload["queue_id"])) != 16:
            raise ProviderQueueError()
        approval = payload.get("approval")
        if not isinstance(approval, dict) or approval.get("jti") != payload.get(
            "approval_jti"
        ):
            raise ProviderQueueError()
        for key in ("issued_at_unix", "expires_at_unix", "queue_expires_at_unix"):
            if type(payload.get(key)) is not int:
                raise ProviderQueueError()
        now = int(self._now())
        if type(allow_expired) is not bool:
            raise ProviderQueueError()
        if (
            int(payload["issued_at_unix"]) > now
            or (
                not allow_expired
                and (
                    int(payload["expires_at_unix"]) <= now
                    or int(payload["queue_expires_at_unix"]) <= now
                )
            )
            or int(payload["queue_expires_at_unix"])
            > int(payload["expires_at_unix"]) - PROVIDER_MARGIN_SECONDS
        ):
            raise ProviderQueueError("queue_expired")
        return payload

    def _validated_claim(
        self,
        value: str,
        *,
        authority: AuthorityContext,
        allow_expired: bool = False,
    ) -> dict[str, object]:
        payload = self._decrypt(
            value,
            aead=self._claim_aead,
            context=CLAIM_TOKEN_CONTEXT,
        )
        expected = {
            "schema",
            "kind",
            "jti",
            "boot_nonce",
            "queue_id",
            "capability_jti",
            "scope",
            "service_class",
            "session_nonce",
            "subject_id",
            "slot",
            "revision",
            "issued_at_unix",
            "expires_at_unix",
        }
        if set(payload) != expected:
            raise ProviderQueueError()
        if (
            payload.get("schema") != CLAIM_TOKEN_SCHEMA
            or payload.get("kind") != "provider_claim_v1"
            or payload.get("boot_nonce") != self._boot_nonce
            or payload.get("scope") != authority.scope
            or payload.get("service_class") != authority.service_class
            or payload.get("session_nonce") != authority.session_nonce
            or payload.get("subject_id") != authority.subject_id
        ):
            raise ProviderQueueError()
        for key in ("jti", "queue_id", "capability_jti", "boot_nonce", "session_nonce"):
            _require_b64(payload.get(key), decoded_bytes=None)
        if len(_decode_b64url(payload["jti"])) != 16:
            raise ProviderQueueError()
        if type(payload.get("slot")) is not int or payload["slot"] not in range(
            PROVIDER_SLOTS
        ):
            raise ProviderQueueError()
        if type(payload.get("revision")) is not int or int(payload["revision"]) < 1:
            raise ProviderQueueError()
        for key in ("issued_at_unix", "expires_at_unix"):
            if type(payload.get(key)) is not int:
                raise ProviderQueueError()
        now = int(self._now())
        if type(allow_expired) is not bool:
            raise ProviderQueueError()
        if (
            int(payload["issued_at_unix"]) > now
            or (not allow_expired and int(payload["expires_at_unix"]) <= now)
            or int(payload["expires_at_unix"])
            < int(payload["issued_at_unix"]) + CLAIM_TTL_SECONDS
            or int(payload["expires_at_unix"])
            > int(payload["issued_at_unix"]) + CLAIM_MAX_ENCODED_TTL_SECONDS
        ):
            raise ProviderQueueError("queue_not_ready")
        return payload

    def _encrypt(
        self,
        payload: Mapping[str, object],
        *,
        aead: AESGCM,
        context: bytes,
    ) -> str:
        nonce = self._fresh_bytes(12)
        plaintext = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return _b64url(nonce + aead.encrypt(nonce, plaintext, context))

    def _decrypt(
        self,
        value: str,
        *,
        aead: AESGCM,
        context: bytes,
    ) -> dict[str, object]:
        packed = _decode_b64url(value)
        if len(packed) < 28:
            raise ProviderQueueError()
        nonce, ciphertext = packed[:12], packed[12:]
        try:
            plaintext = aead.decrypt(nonce, ciphertext, context)
            payload = json.loads(plaintext)
        except Exception:
            raise ProviderQueueError() from None
        if not isinstance(payload, dict):
            raise ProviderQueueError()
        return payload

    def _matching_record_locked(
        self,
        queue_id: str,
        *,
        binding: bytes,
        capability_jti: str,
    ) -> _QueueRecord:
        record = self._records.get(queue_id)
        if (
            record is None
            or record.binding_digest != binding
            or not record.capability_active
            or record.capability_jti_digest != _digest_ascii(capability_jti)
        ):
            raise ProviderQueueError()
        return record

    def _record_for_binding_locked(self, binding: bytes) -> _QueueRecord | None:
        queue_id = self._binding_index.get(binding)
        return None if queue_id is None else self._records.get(queue_id)

    def _active_record_for_owner_locked(
        self,
        owner: bytes,
    ) -> _QueueRecord | None:
        queue_id = self._owner_index.get(owner)
        record = None if queue_id is None else self._records.get(queue_id)
        return record if record is not None and record.state in _ACTIVE_STATES else None

    def _active_records_locked(self) -> tuple[_QueueRecord, ...]:
        return tuple(row for row in self._records.values() if row.state in _ACTIVE_STATES)

    def _derived_status_locked(
        self,
        record: _QueueRecord,
        now: int,
    ) -> tuple[str, str | None]:
        if record.state == "queued" and now >= record.queue_expires_at_unix:
            return "expired", "deadline_expired"
        if record.state == "claim_ready" and (
            record.claim_expires_at_unix is None
            or now >= record.claim_expires_at_unix
        ):
            reason = (
                "claim_missed_expired"
                if record.claim_miss_count >= 1
                else "claim_missed_requeued"
            )
            return "expired" if record.claim_miss_count >= 1 else "queued", reason
        if record.state == "queued" and record.claim_poll_seen and not record.poll_active:
            return "paused", record.reason
        return record.state, record.reason

    def _position_locked(self, record: _QueueRecord) -> int | None:
        if record.state != "queued":
            return None
        waiting = sorted(
            (row for row in self._records.values() if row.state == "queued"),
            key=lambda value: (value.fairness_age, value.enqueued_at_unix),
        )
        try:
            return waiting.index(record) + 1
        except ValueError:
            return None

    def _claim_state_locked(self, record: _QueueRecord) -> dict[str, object]:
        return {
            "state": record.state,
            "revision": record.revision,
            "claim_token": None,
            "claim_expires_at_unix": None,
            "queue_expires_at_unix": record.queue_expires_at_unix,
        }

    def _advance_locked(self, now: int) -> None:
        for record in tuple(self._records.values()):
            if record.state == "queued" and now >= record.queue_expires_at_unix:
                self._terminal_locked(record, "expired", "deadline_expired", now)
            elif record.state == "claim_ready" and (
                record.claim_expires_at_unix is None
                or now >= record.claim_expires_at_unix
                or now >= record.queue_expires_at_unix
            ):
                self._release_slot_locked(record)
                self._claim_deliveries.pop(record.queue_id, None)
                record.claim_miss_count += 1
                record.revision += 1
                record.claim_jti_digest = None
                record.claim_expires_at_unix = None
                record.claim_acknowledgement_pending = False
                if now >= record.queue_expires_at_unix:
                    self._terminal_locked(record, "expired", "deadline_expired", now)
                elif record.claim_miss_count >= 2:
                    self._terminal_locked(
                        record,
                        "expired",
                        "claim_missed_expired",
                        now,
                    )
                else:
                    self._fairness_counter += 1
                    record.fairness_age = self._fairness_counter
                    record.state = "queued"
                    record.reason = "claim_missed_requeued"
        self._condition.notify_all()

    def _terminal_locked(
        self,
        record: _QueueRecord,
        state: str,
        reason: str | None,
        now: int,
    ) -> None:
        self._release_slot_locked(record)
        self._eligible.discard(record.queue_id)
        self._legacy_waiters.discard(record.queue_id)
        self._claim_deliveries.pop(record.queue_id, None)
        record.state = state
        record.reason = reason
        record.capability_active = False
        record.retain_until_unix = now + TERMINAL_RETENTION_SECONDS

    def _prune_locked(self, now: int) -> None:
        for queue_id, record in tuple(self._records.items()):
            if (
                record.state in _TERMINAL_STATES
                and record.retain_until_unix is not None
                and record.retain_until_unix <= now
            ):
                self._drop_record_locked(record)

    def _ensure_record_capacity_locked(self) -> None:
        """Bound terminal history without letting it reject otherwise valid work."""

        while len(self._records) >= MAX_RECORDS:
            terminal = [
                row for row in self._records.values() if row.state in _TERMINAL_STATES
            ]
            if not terminal:
                raise ProviderQueueError("queue_full")
            self._drop_record_locked(
                min(
                    terminal,
                    key=lambda value: (
                        value.retain_until_unix or 0,
                        value.fairness_age,
                    ),
                )
            )

    def _consume_join_rate_locked(
        self,
        authority: AuthorityContext,
        owner: bytes,
        now: int,
    ) -> None:
        """Consume the exact per-authority join bucket under the queue lock.

        Nginx separately bounds anonymous/global transport attempts. This
        branch is the semantic authority limit: Priority has 6/min burst 2;
        Standard has 1/min burst 1 and may borrow only while the scheduler is
        truly empty, a slot is idle, and its prior provider admission is at
        least ten seconds old.
        """
        if authority.service_class == "standard":
            rate = STANDARD_QUEUE_JOIN_PER_MINUTE / 60.0
            capacity = 1.0 + STANDARD_QUEUE_JOIN_BURST
        else:
            rate = PRIORITY_QUEUE_JOIN_PER_MINUTE / 60.0
            capacity = 1.0 + PRIORITY_QUEUE_JOIN_BURST
        tokens, sampled = self._join_buckets.get(owner, (capacity, float(now)))
        elapsed = max(0.0, float(now) - sampled)
        tokens = min(capacity, tokens + elapsed * rate)
        if tokens >= 1.0:
            self._join_buckets[owner] = (tokens - 1.0, float(now))
            return
        if authority.service_class == "standard":
            last_admission = self._standard_last_provider_admission.get(owner)
            scheduler_empty = not self._active_records_locked()
            slot_idle = bool(self._free_slots)
            if (
                last_admission is not None
                and now - last_admission >= STANDARD_IDLE_BORROW_SECONDS
                and scheduler_empty
                and slot_idle
            ):
                self._join_buckets[owner] = (tokens, float(now))
                return
        self._join_buckets[owner] = (tokens, float(now))
        raise ProviderQueueError("queue_rate_limited")

    def _drop_record_locked(self, record: _QueueRecord) -> None:
        queue_id = record.queue_id
        self._records.pop(queue_id, None)
        self._eligible.discard(queue_id)
        self._legacy_waiters.discard(queue_id)
        self._poll_capabilities.pop(queue_id, None)
        self._claim_deliveries.pop(queue_id, None)
        if self._binding_index.get(record.binding_digest) == queue_id:
            self._binding_index.pop(record.binding_digest, None)
        if self._owner_index.get(record.owner_digest) == queue_id:
            self._owner_index.pop(record.owner_digest, None)

    def _dispatch_locked(self, now: int) -> None:
        wall_now = float(self._now())
        while self._free_slots:
            candidates = [
                row
                for row in self._records.values()
                if row.state == "queued"
                and row.queue_id in self._eligible
                and row.poll_active
                and (
                    (
                        row.legacy_internal
                        and row.queue_id in self._legacy_waiters
                        and row.queue_expires_at_unix > wall_now
                    )
                    or (
                        not row.legacy_internal
                        and row.queue_id in self._poll_capabilities
                        and row.queue_expires_at_unix
                        >= math.ceil(
                            wall_now
                            + (
                                CLAIM_HTTP_ACK_TTL_SECONDS
                                if row.claim_acknowledgement_pending
                                else CLAIM_TTL_SECONDS
                            )
                        )
                    )
                )
            ]
            if not candidates:
                return
            desired = CLAIM_GRANT_SEQUENCE[self._grant_cursor]
            preferred = [row for row in candidates if row.service_class == desired]
            pool = preferred if preferred else candidates
            selected = min(
                pool,
                key=lambda value: (value.fairness_age, value.enqueued_at_unix),
            )
            self._grant_cursor = (self._grant_cursor + 1) % len(CLAIM_GRANT_SEQUENCE)
            slot = min(self._free_slots)
            self._free_slots.remove(slot)
            if selected.legacy_internal:
                selected.state = "running"
                selected.reason = None
                selected.revision += 1
                selected.slot = slot
                self._eligible.discard(selected.queue_id)
                self._condition.notify_all()
                continue
            claim_jti = _b64url(self._fresh_bytes(16))
            issued = math.floor(wall_now)
            claim_ttl = (
                CLAIM_HTTP_ACK_TTL_SECONDS
                if selected.claim_acknowledgement_pending
                else CLAIM_TTL_SECONDS
            )
            # Epoch-second DTOs round the deadline upward so fractional grant
            # times never shorten the promised server-side validity. The exact
            # same integer deadline binds the record, token, and wire response.
            expires = math.ceil(wall_now + claim_ttl)
            selected.state = "claim_ready"
            selected.reason = None
            selected.revision += 1
            selected.slot = slot
            selected.claim_jti_digest = _digest_ascii(claim_jti)
            selected.claim_expires_at_unix = expires
            # For HTTP claims, begin_execute is the only reliable browser
            # acknowledgement. ASGI send completion is not delivery proof.
            capability = self._poll_capabilities.get(selected.queue_id)
            if capability is None:
                self._release_slot_locked(selected)
                selected.state = "queued"
                selected.revision -= 1
                selected.claim_jti_digest = None
                selected.claim_expires_at_unix = None
                return
            claim_payload = {
                "schema": CLAIM_TOKEN_SCHEMA,
                "kind": "provider_claim_v1",
                "jti": claim_jti,
                "boot_nonce": self._boot_nonce,
                "queue_id": selected.queue_id,
                "capability_jti": capability["jti"],
                "scope": capability["scope"],
                "service_class": selected.service_class,
                "session_nonce": capability["session_nonce"],
                "subject_id": capability["subject_id"],
                "slot": slot,
                "revision": selected.revision,
                "issued_at_unix": issued,
                "expires_at_unix": expires,
            }
            self._claim_deliveries[selected.queue_id] = self._encrypt(
                claim_payload,
                aead=self._claim_aead,
                context=CLAIM_TOKEN_CONTEXT,
            )
            self._condition.notify_all()

    def _release_slot_locked(self, record: _QueueRecord) -> None:
        if record.slot is not None:
            self._free_slots.add(record.slot)
            record.slot = None

    def _fresh_bytes(self, size: int) -> bytes:
        value = self._random_bytes(size)
        if not isinstance(value, bytes) or len(value) != size:
            raise RuntimeError("provider queue random source returned an invalid value")
        return value


def _digest_ascii(value: str) -> bytes:
    if not isinstance(value, str) or not value.isascii():
        raise ProviderQueueError()
    return hashlib.sha256(value.encode("ascii")).digest()


def _binding_digest(authority: AuthorityContext) -> bytes:
    _validate_authority(authority)
    value = "\x1f".join(
        (
            authority.scope,
            authority.service_class,
            authority.session_nonce,
            authority.subject_id or "",
        )
    )
    return hashlib.sha256(value.encode("ascii")).digest()


def _owner_digest(authority: AuthorityContext) -> bytes:
    _validate_authority(authority)
    value = (
        authority.session_nonce
        if authority.service_class == "standard"
        else str(authority.subject_id)
    )
    return hashlib.sha256(
        f"{authority.service_class}\x1f{value}".encode("ascii")
    ).digest()


def _validate_authority(authority: AuthorityContext) -> None:
    if not isinstance(authority, AuthorityContext):
        raise ProviderQueueError()
    if authority.scope == "public_guest":
        valid = authority.service_class == "standard" and authority.subject_id is None
    elif authority.scope == "priority_invite":
        valid = (
            authority.service_class == "priority"
            and isinstance(authority.subject_id, str)
            and _SUBJECT_PATTERN.fullmatch(authority.subject_id) is not None
        )
    else:
        valid = False
    if (
        not valid
        or not isinstance(authority.session_nonce, str)
        or _B64_PATTERN.fullmatch(authority.session_nonce) is None
        or type(authority.expires_at_unix) is not int
    ):
        raise ProviderQueueError()


def _require_b64(value: object, *, decoded_bytes: int | None) -> None:
    decoded = _decode_b64url(value)
    if decoded_bytes is not None and len(decoded) != decoded_bytes:
        raise ProviderQueueError()


def _status_absent() -> dict[str, object]:
    return {
        "state": "absent",
        "position": None,
        "reason": None,
        "enqueued_at_unix": None,
        "queue_expires_at_unix": None,
        "poll_after_ms": STATUS_POLL_AFTER_MS,
        "automatic_execute_possible": False,
    }

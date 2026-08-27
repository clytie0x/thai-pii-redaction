"""Session vault for storing original↔pseudonym mappings in memory.

SECURITY-CRITICAL: never written to disk or network; the audit log holds only
entity_id + action + timestamp; clear() drops references but cannot zeroize Python strings.
"""

import threading
import time
import uuid
from typing import NamedTuple

from amphrang.engine.anonymizer.token_generator import (
    TOKEN_LABEL,
    is_token_for_data_type,
    is_valid_token_namespace,
    new_token_namespace,
    token_namespace_from_candidate,
)
from amphrang.engine.detectors.sensitive_span import SENSITIVE_DATA_TYPE_SET
from amphrang.engine.models import VaultRecord

# data_type stamped on seed()-ed records; an exported mapping carries no data_type, so
# get_by_original() treats this sentinel as a wildcard.
SEEDED_DATA_TYPE = "SEEDED"
_SEED_COLLISION_ERROR = "seed pseudonym collision"


def _is_sensitive_category_token(record: VaultRecord) -> bool:
    """Whether this record's original is only the ม.26 CATEGORY WORD inside our own token.

    `trusted_pseudonyms()` refuses a replacement that contains its own original, because such
    a replacement carries the original VALUE outbound. A ม.26 span is masked with the fixed
    category name from `TOKEN_LABEL` (`ศาสนา`, `ข้อมูลสุขภาพ`, …) in both modes, and the ม.26
    detector's span very often IS that same cue word, so the record trips that rule while
    disclosing nothing the published label does not already print. Left untrusted, the leak
    guard's ม.26 rescan could not excuse the hit inside the mask this vault had just written,
    and the whole document failed closed
    (docs/decisions/2026-08-27-section26-span-masking.md §5.2 and §6.2, which both assume the
    token IS a trusted pseudonym occurrence).

    All three conditions are required, and the third is what keeps the exemption from ever
    covering a value: the contained text must be a substring of the category label itself, so
    a token whose namespace/nonce/ordinal happened to contain a real original still fails.
    """
    return (
        record.data_type in SENSITIVE_DATA_TYPE_SET
        and is_token_for_data_type(record.pseudonym, record.data_type)
        and record.original in TOKEN_LABEL.get(record.data_type, "")
    )


class _VaultAuditEntry(NamedTuple):
    """Immutable internal audit row; `audit_log()` retains the public dict shape."""

    action: str
    entity_id: str
    timestamp: float
    session_id: str


class VaultTimeoutError(Exception):
    """Raised when vault is accessed after idle timeout."""

    pass


class SessionVault:
    """In-memory vault for original↔pseudonym mappings.

    _clear_epoch prevents stale rollback snapshots from reviving cleared data;
    _token_namespace is the non-secret generation tag for token-mode identity.
    """

    def __init__(
        self,
        idle_timeout_s: float | None = 1800,
        *,
        token_namespace: str | None = None,
    ):
        """idle_timeout_s=None delegates expiry to a lifecycle manager; token_namespace
        continues an existing stateless chain."""
        if token_namespace is not None and not is_valid_token_namespace(token_namespace):
            raise ValueError("invalid token namespace")
        self._table: dict[str, VaultRecord] = {}  # entity_id → VaultRecord
        self._reverse: dict[str, str] = {}  # pseudonym → entity_id
        self._last_access: float = time.monotonic()
        self._idle_timeout_s = idle_timeout_s
        self.session_id: str = str(uuid.uuid4())
        self._token_namespace: str | None = token_namespace or new_token_namespace()
        self._audit_entries: list[_VaultAuditEntry] = []  # local audit log
        self._clear_epoch = 0
        self._lifecycle_lock = threading.RLock()

    @property
    def token_namespace(self) -> str:
        """Return the generation tag for tokens minted by this vault."""
        with self._lifecycle_lock:
            if self._token_namespace is None:
                self._token_namespace = new_token_namespace()
            return self._token_namespace

    def adopt_token_namespace(self, namespace: str) -> bool:
        """Continue a seeded stateless token chain before minting new tokens."""
        if not is_valid_token_namespace(namespace):
            raise ValueError("invalid token namespace")
        with self._lifecycle_lock:
            generated_namespaces = {
                candidate_namespace
                for entity_id, record in self._table.items()
                if record.data_type != SEEDED_DATA_TYPE
                and self._reverse.get(record.pseudonym) == entity_id
                and (candidate_namespace := token_namespace_from_candidate(record.pseudonym))
                is not None
            }
            if generated_namespaces and generated_namespaces != {namespace}:
                return False
            self._token_namespace = namespace
            return True

    def write(self, record: VaultRecord) -> None:
        """Store a record in _table and _reverse. Raises ValueError if the pseudonym already
        maps to a different original: a silent overwrite would restore the wrong person."""
        with self._lifecycle_lock:
            self._touch()
            existing_owner_id = self._reverse.get(record.pseudonym)
            if existing_owner_id is not None and existing_owner_id != record.entity_id:
                existing_owner = self._table.get(existing_owner_id)
                if existing_owner is not None and existing_owner.original != record.original:
                    # SECURITY: no pseudonym/original in the message (audit-safe)
                    raise ValueError(
                        f"pseudonym collision: entity {record.entity_id[:8]} "
                        f"vs {existing_owner_id[:8]}"
                    )
            if record.entity_id in self._table:
                old_pseudonym = self._table[record.entity_id].pseudonym
                if old_pseudonym != record.pseudonym:
                    self._reverse.pop(old_pseudonym, None)
            self._table[record.entity_id] = record
            self._reverse[record.pseudonym] = record.entity_id
            self._audit("write", record.entity_id)

    def get_by_entity_id(self, entity_id: str) -> VaultRecord | None:
        """Lookup by entity_id; None if missing. Raises VaultTimeoutError when idle."""
        with self._lifecycle_lock:
            self.check_idle()
            self._touch()
            record = self._table.get(entity_id)
            self._audit("read_by_id", entity_id)
            return record

    def get_by_pseudonym(self, pseudonym: str) -> VaultRecord | None:
        """Lookup by pseudonym; None if missing. Raises VaultTimeoutError when idle."""
        with self._lifecycle_lock:
            self.check_idle()
            self._touch()
            entity_id = self._reverse.get(pseudonym)
            if entity_id is None:
                return None
            self._audit("read_by_pseudonym", entity_id)
            return self._table.get(entity_id)

    def get_by_original(self, original: str, data_type: str | None = None) -> VaultRecord | None:
        """Lookup by original (optionally narrowed by data_type); raises VaultTimeoutError when idle.

        A seed()-ed record matches ANY data_type (the exported mapping carries none, and a strict
        match would issue the same person a second token every turn); exact matches win.
        """
        with self._lifecycle_lock:
            self.check_idle()
            self._touch()
            seeded_match: VaultRecord | None = None
            for record in self._table.values():
                if record.original != original:
                    continue
                if data_type is None or record.data_type == data_type:
                    self._audit("read_by_original", record.entity_id)
                    return record
                if record.data_type == SEEDED_DATA_TYPE and seeded_match is None:
                    seeded_match = record
            if seeded_match is not None:
                self._audit("read_by_original", seeded_match.entity_id)
            return seeded_match

    def export_mapping(self) -> dict[str, str]:
        """Return {pseudonym: original} for an in-process stateless adapter (legacy worker-v1
        opt-in only; the HTTP v2 wire does not export it)."""
        with self._lifecycle_lock:
            out: dict[str, str] = {}
            for pseudonym, entity_id in self._reverse.items():
                record = self._table.get(entity_id)
                if record is not None:
                    out[pseudonym] = record.original
            return out

    def trusted_pseudonyms(self) -> set[str]:
        """Pseudonyms this vault minted itself, excluding caller-supplied ones.

        SECURITY BOUNDARY: the leak guard excuses anything it believes is a pseudonym, so
        seed()-ed values (a caller's claim) must not count, else a caller could declare a real
        national ID to be "their pseudonym". Empty values and replacements containing their own
        original are never trusted either — except a ม.26 category token, where the contained
        text is the published category label and not a value (`_is_sensitive_category_token`).
        """
        with self._lifecycle_lock:
            return {
                record.pseudonym
                for record in self._table.values()
                if record.data_type != SEEDED_DATA_TYPE
                and record.pseudonym
                and (
                    record.original not in record.pseudonym or _is_sensitive_category_token(record)
                )
            }

    def seed(self, pseudonym: str, original: str) -> VaultRecord:
        """Re-admit a pair from a previous turn's exported mapping; returns the existing or new
        record. Replaying the same pair adds no audit event; a pseudonym already owned by a
        different original raises ValueError with a constant message. The synthesised
        entity_id is an opaque UUID, never caller text."""
        with self._lifecycle_lock:
            existing_id = self._reverse.get(pseudonym)
            if existing_id is not None:
                existing = self._table.get(existing_id)
                if existing is None or existing.original != original:
                    raise ValueError(_SEED_COLLISION_ERROR)
                return existing

            record = VaultRecord(
                entity_id=f"seed:{uuid.uuid4()}",
                original=original,
                pseudonym=pseudonym,
                type="FP",
                data_type=SEEDED_DATA_TYPE,
                span=(0, 0),
                timestamp=time.monotonic(),
            )
            prior_access = self._last_access
            prior_audit_length = len(self._audit_entries)
            try:
                self._touch()
                self._table[record.entity_id] = record
                self._reverse[record.pseudonym] = record.entity_id
                self._audit("seed", record.entity_id)
            except BaseException:
                self._table.pop(record.entity_id, None)
                if self._reverse.get(record.pseudonym) == record.entity_id:
                    self._reverse.pop(record.pseudonym, None)
                del self._audit_entries[prior_audit_length:]
                self._last_access = prior_access
                raise
            return record

    def clone(self) -> "SessionVault":
        """Return a detached copy for an unpublished transaction. The constructor is bypassed
        deliberately so cloning does not mint a new vault ID or access timestamp."""
        with self._lifecycle_lock:
            clone = object.__new__(type(self))
            clone._table = dict(self._table)
            clone._reverse = dict(self._reverse)
            clone._last_access = self._last_access
            clone._idle_timeout_s = self._idle_timeout_s
            clone.session_id = self.session_id
            clone._token_namespace = self._token_namespace
            clone._audit_entries = list(self._audit_entries)
            clone._clear_epoch = self._clear_epoch
            clone._lifecycle_lock = threading.RLock()
        return clone

    def snapshot(self) -> dict:
        """Return detached indexes plus the clear epoch that authorizes restoration."""
        with self._lifecycle_lock:
            return {
                "_table": dict(self._table),
                "_reverse": dict(self._reverse),
                "_token_namespace": self._token_namespace,
                "_clear_epoch": self._clear_epoch,
            }

    def restore(self, snapshot: dict) -> bool:
        """Restore a snapshot(); False when clear() has invalidated it."""
        with self._lifecycle_lock:
            if snapshot.get("_clear_epoch") != self._clear_epoch:
                return False
            self._table = dict(snapshot["_table"])
            self._reverse = dict(snapshot["_reverse"])
            self._token_namespace = snapshot["_token_namespace"]
            self._audit("restore", "snapshot")
            return True

    def clear(self) -> None:
        """Drop vault-owned references. Exposure reduction, not zeroization: Python strings
        cannot be overwritten and external references may outlive this vault."""
        with self._lifecycle_lock:
            self._clear_epoch += 1
            self._table.clear()
            self._reverse.clear()
            # A reused vault must never mint a token meaningful in the cleared generation.
            self._token_namespace = None
            self._audit("clear", "all")

    def is_idle(self) -> bool:
        """True at or beyond the standalone idle timeout; False when managed elsewhere."""
        with self._lifecycle_lock:
            return (
                self._idle_timeout_s is not None
                and (time.monotonic() - self._last_access) >= self._idle_timeout_s
            )

    def check_idle(self) -> None:
        """Raise VaultTimeoutError if idle timeout exceeded."""
        with self._lifecycle_lock:
            if self.is_idle():
                assert self._idle_timeout_s is not None
                raise VaultTimeoutError(f"Session vault idle timeout after {self._idle_timeout_s}s")

    def audit_log(self) -> list[dict]:
        """Return a copy of the audit log as dicts."""
        with self._lifecycle_lock:
            return [entry._asdict() for entry in self._audit_entries]

    # ========== Private Helpers ==========

    def _touch(self) -> None:
        """Update last access time to current monotonic time."""
        self._last_access = time.monotonic()

    def _audit(self, action: str, entity_id: str) -> None:
        """SECURITY: never log original or pseudonym, only entity_id + action + timestamp."""
        self._audit_entries.append(
            _VaultAuditEntry(
                action=action,
                entity_id=entity_id,
                timestamp=time.monotonic(),
                session_id=self.session_id,
            )
        )

"""Verified-authority rate buckets for the Hosted 3.0 local candidate.

The proxy has anonymous/global transport fences, but it cannot authenticate a
Priority Invite subject.  These process-local buckets therefore own every
published per-session/per-issued-invite limit.  Keys are one-way digests only.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable

from .authority import AuthorityContext


class AuthorityRateLimiter:
    """Exact verified-authority token buckets with no raw cookie retention."""

    _POLICIES = {
        "work": {"standard": (6, 2), "priority": (30, 5)},
        "document": {"standard": (1, 1), "priority": (4, 1)},
        "status": {"standard": (6, 1), "priority": (6, 1)},
        "claim": {"standard": (3, 1), "priority": (3, 1)},
        "cancel": {"standard": (2, 1), "priority": (2, 1)},
        "execute": {"standard": (4, 1), "priority": (4, 1)},
    }

    def __init__(self, *, now: Callable[[], float] | None = None):
        self._now = time.time if now is None else now
        self._buckets: dict[tuple[str, bytes], tuple[float, float, int]] = {}
        self._lock = threading.Lock()

    def consume(self, lane: str, authority: AuthorityContext) -> bool:
        """Consume one exact lane token for a verified browser/invite owner."""

        policy = self._POLICIES.get(lane, {}).get(authority.service_class)
        if policy is None:
            return False
        owner = authority.session_nonce if authority.service_class == "standard" else authority.subject_id
        if not isinstance(owner, str) or not owner.isascii():
            return False
        key = hashlib.sha256(
            f"{authority.service_class}\x1f{owner}".encode("ascii")
        ).digest()
        per_minute, burst = policy
        capacity = float(1 + burst)
        sampled = float(self._now())
        with self._lock:
            self._prune_locked(int(sampled))
            tokens, prior, expiry = self._buckets.get(
                (lane, key),
                (capacity, sampled, authority.expires_at_unix),
            )
            tokens = min(capacity, tokens + max(0.0, sampled - prior) * per_minute / 60.0)
            self._buckets[(lane, key)] = (
                tokens - 1.0 if tokens >= 1.0 else tokens,
                sampled,
                max(expiry, authority.expires_at_unix),
            )
            return tokens >= 1.0

    def clear_standard(self, authority: AuthorityContext) -> None:
        """Discard every bucket for an explicitly ended Standard session."""

        if authority.service_class != "standard":
            return
        owner = authority.session_nonce
        if not isinstance(owner, str) or not owner.isascii():
            return
        key = hashlib.sha256(f"standard\x1f{owner}".encode("ascii")).digest()
        with self._lock:
            for lane in self._POLICIES:
                self._buckets.pop((lane, key), None)

    def _prune_locked(self, now: int) -> None:
        for key, (_tokens, _sampled, expiry) in tuple(self._buckets.items()):
            if expiry <= now:
                self._buckets.pop(key, None)

#!/usr/bin/env python3
"""Exact Core-owned verified-authority rate policy for Stage 5."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from aift_hosted3.authority import AuthorityContext  # noqa: E402
from aift_hosted3.rate_limit import AuthorityRateLimiter  # noqa: E402


class Clock:
    now = 1_800_000_000.0


def authority(kind: str, nonce: str, subject: str | None = None) -> AuthorityContext:
    return AuthorityContext(
        scope="public_guest" if kind == "standard" else "priority_invite",
        service_class=kind,
        session_nonce=nonce,
        subject_id=subject,
        expires_at_unix=1_800_001_800,
    )


def main() -> int:
    clock = Clock()
    limiter = AuthorityRateLimiter(now=lambda: clock.now)
    standard = authority("standard", "standard_nonce_123456789")
    priority_one = authority(
        "priority", "priority_nonce_one_123456", "sub_AAAAAAAAAAAAAAAAAAAAAA"
    )
    priority_two = authority(
        "priority", "priority_nonce_two_123456", "sub_AAAAAAAAAAAAAAAAAAAAAA"
    )

    policies = {
        "work": ((standard, 3), (priority_one, 6)),
        "document": ((standard, 2), (priority_one, 2)),
        "status": ((standard, 2), (priority_one, 2)),
        "claim": ((standard, 2), (priority_one, 2)),
        "cancel": ((standard, 2), (priority_one, 2)),
        "execute": ((standard, 2), (priority_one, 2)),
    }
    for lane, cases in policies.items():
        for owner, capacity in cases:
            assert [limiter.consume(lane, owner) for _ in range(capacity)] == [True] * capacity
            assert limiter.consume(lane, owner) is False

    # A Priority rate owner is the issued opaque subject, not a reminted
    # session nonce. A second login cannot multiply its published quota.
    assert limiter.consume("work", priority_two) is False
    clock.now += 10
    assert limiter.consume("work", standard) is True  # 6/min refills one token in 10s
    assert all(isinstance(key[1], bytes) and len(key[1]) == 32 for key in limiter._buckets)
    limiter.clear_standard(standard)
    standard_key = hashlib.sha256(b"standard\x1fstandard_nonce_123456789").digest()
    assert not any(key[1] == standard_key for key in limiter._buckets)
    clock.now = standard.expires_at_unix
    future_priority = AuthorityContext(
        scope="priority_invite",
        service_class="priority",
        session_nonce="priority_nonce_future_12345",
        subject_id="sub_BBBBBBBBBBBBBBBBBBBBBB",
        expires_at_unix=int(clock.now) + 1800,
    )
    assert limiter.consume("status", future_priority) is True
    assert all(expiry > clock.now for _tokens, _sampled, expiry in limiter._buckets.values())
    print("hosted3 verified rate contract ok: exact per-session/per-issued-subject buckets, remint resistance, expiry pruning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

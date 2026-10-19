#!/usr/bin/env python3
"""Core health probe with bounded self-recovery after repeated failures."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

STATE = Path("/tmp/aift-health-failures")
THRESHOLD = 3


def _fail() -> int:
    try:
        failures = int(STATE.read_text(encoding="ascii")) + 1
    except (OSError, ValueError):
        failures = 1
    try:
        STATE.write_text(str(failures), encoding="ascii")
    except OSError:
        pass
    if failures >= THRESHOLD:
        os.kill(1, 15)
    return 1


def main() -> int:
    try:
        response = httpx.get(
            "http://127.0.0.1:8000/api/health",
            timeout=2,
            trust_env=False,
        )
        response.raise_for_status()
        STATE.unlink(missing_ok=True)
        return 0
    except Exception:
        return _fail()


if __name__ == "__main__":
    raise SystemExit(main())

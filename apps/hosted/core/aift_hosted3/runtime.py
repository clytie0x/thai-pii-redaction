"""Fail-closed process invariants for in-memory Hosted 3.0 state."""

from __future__ import annotations

import os
from collections.abc import Mapping


def require_single_worker(environ: Mapping[str, str] | None = None) -> None:
    """Reject multi-worker startup until replay/queue state has a shared store."""

    source = os.environ if environ is None else environ
    if source.get("UVICORN_WORKERS", "1") != "1":
        raise RuntimeError("Hosted 3.0 requires UVICORN_WORKERS=1")

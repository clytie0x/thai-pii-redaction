"""Select this checkout's canonical source for source-only contract scripts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HOSTED = Path(__file__).resolve().parents[1]
CHECKOUT = HOSTED.parents[1] if len(HOSTED.parents) > 1 else None


def source_root() -> Path:
    # This is a test harness only. Runtime has no checkout fallback.
    if (
        CHECKOUT is not None
        and (CHECKOUT / "pyproject.toml").is_file()
        and (CHECKOUT / "pii_redactor").is_dir()
    ):
        if str(CHECKOUT) not in sys.path:
            sys.path.insert(0, str(CHECKOUT))
        return CHECKOUT
    spec = importlib.util.find_spec("pii_redactor")
    if spec is None or spec.origin is None:
        raise RuntimeError(
            "install the supplied first-party canonical core before Hosted contracts"
        )
    return Path(spec.origin).resolve().parents[1]


CANONICAL = source_root()

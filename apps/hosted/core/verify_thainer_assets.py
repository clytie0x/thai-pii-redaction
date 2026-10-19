#!/usr/bin/env python3
"""Fail the hosted build if PyThaiNLP's baked thainer tree drifts."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

EXPECTED_TREE_SHA256 = "bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315"


def tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for candidate in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(candidate.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(os.environ.get("PYTHAINLP_DATA", ""))
    if not root.is_dir():
        raise SystemExit("PyThaiNLP data tree is missing")
    actual = tree_sha256(root)
    if actual != EXPECTED_TREE_SHA256:
        raise SystemExit("PyThaiNLP thainer asset tree digest mismatch")
    print("PyThaiNLP thainer asset tree verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

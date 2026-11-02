"""Bind approvals to the exact canonical protection source installed here."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


def protection_source_sha256() -> str:
    spec = importlib.util.find_spec("pii_redactor")
    if spec is None or spec.origin is None:
        raise RuntimeError("canonical first-party core is not installed")
    root = Path(spec.origin).resolve().parents[1]
    digest = hashlib.sha256()
    files = sorted(
        (
            path
            for namespace in ("app", "pii_redactor")
            for path in (root / namespace).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not files or any(path.is_symlink() for path in files):
        raise RuntimeError("canonical first-party source inventory is invalid")
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8") + b"\0" + path.read_bytes())
    return digest.hexdigest()

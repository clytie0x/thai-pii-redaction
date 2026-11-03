"""Exact canonical package inventory, source identity, and value-free scanning."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

SECRET_PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "gitlab-token": re.compile(rb"glpat-[A-Za-z0-9_-]{20,}"),
    "github-token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "aws-access-key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "openai-key": re.compile(rb"sk-[A-Za-z0-9]{32,}"),
    "google-api-key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
}


def source_files(root: Path) -> dict[str, Path]:
    files = {}
    for namespace in ("app", "pii_redactor"):
        package = root / namespace
        if package.is_symlink() or not (package / "__init__.py").is_file():
            raise ValueError("canonical source package is missing or unsafe")
        for path in package.rglob("*"):
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("canonical source symlinks are not allowed")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[path.relative_to(root).as_posix()] = path
    return dict(sorted(files.items()))


def source_snapshot(root: Path) -> dict[str, bytes]:
    return {relative: path.read_bytes() for relative, path in source_files(root).items()}


def snapshot_sha256(snapshot: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, payload in sorted(snapshot.items()):
        digest.update(relative.encode("utf-8") + b"\0" + payload)
    return digest.hexdigest()


def source_tree_sha256(root: Path) -> str:
    return snapshot_sha256(source_snapshot(root))


def assert_secret_free(snapshot: dict[str, bytes]) -> None:
    findings = []
    for relative, payload in sorted(snapshot.items()):
        name = Path(relative).name
        if name == ".env" or name.startswith(".env."):
            findings.append(f"{relative}:tracked-env-file")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(payload):
                findings.append(f"{relative}:{label}")
    if findings:
        raise ValueError("canonical secret-pattern candidates: " + ", ".join(findings))

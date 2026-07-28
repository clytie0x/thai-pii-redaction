#!/usr/bin/env python3
"""Vendor the runtime slice of thai-pii-redaction into this port repo.

    python sync/sync_from_upstream.py --from <upstream checkout> [--check]

Copies exactly the entries in SLICE from a CLEAN upstream working tree into
core/, then writes sync/PORT_MANIFEST.json recording the upstream commit and
a SHA-256 per vendored file. `--check` verifies the current core/ against the
manifest (used by CI) without copying anything.

Fail-loud rules:
- refuses to sync from a dirty or unborn upstream tree
- refuses if any SLICE entry is missing upstream
- --check fails on any hash mismatch, missing or extra file
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PORT_ROOT = Path(__file__).resolve().parent.parent
CORE = PORT_ROOT / "core"
MANIFEST = Path(__file__).resolve().parent / "PORT_MANIFEST.json"

# Directories are copied recursively minus caches; files are copied as-is.
SLICE = [
    "pii_redactor",
    "app",
    "demo/playground.html",
    "VERSION",
    "requirements.txt",
    "requirements-web.txt",
    "requirements-ocr.txt",
    "requirements.lock",
    "pyproject.toml",
    "LICENSE",
    "NOTICE",
]

_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def _die(msg: str) -> "NoReturn":  # noqa: F821 - py3.11+ typing note only
    print(f"sync: {msg}", file=sys.stderr)
    sys.exit(1)


def _git(upstream: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(upstream), *args], capture_output=True, text=True
    )
    if out.returncode != 0:
        _die(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_files(base: Path):
    for p in sorted(base.rglob("*")):
        if p.is_file() and not (set(p.parts) & _SKIP_DIRS):
            yield p


def do_sync(upstream: Path) -> None:
    if not (upstream / ".git").exists():
        _die(f"{upstream} is not a git checkout")
    if _git(upstream, "status", "--porcelain"):
        _die("upstream working tree is dirty — sync only from a clean, reviewed commit")
    commit = _git(upstream, "rev-parse", "HEAD")

    for entry in SLICE:
        if not (upstream / entry).exists():
            _die(f"SLICE entry missing upstream: {entry}")

    if CORE.exists():
        shutil.rmtree(CORE / "pii_redactor", ignore_errors=True)
        shutil.rmtree(CORE / "app", ignore_errors=True)
        shutil.rmtree(CORE / "demo", ignore_errors=True)
    CORE.mkdir(exist_ok=True)

    files: dict[str, str] = {}
    for entry in SLICE:
        src = upstream / entry
        dst = CORE / entry
        if src.is_dir():
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns(*_SKIP_DIRS, "*.pyc"),
                dirs_exist_ok=True,
            )
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for p in _iter_files(CORE):
        rel = p.relative_to(CORE).as_posix()
        # port-owned files inside core/ (Dockerfile, prewarm) are not vendored
        if rel in PORT_OWNED:
            continue
        files[rel] = _sha256(p)

    MANIFEST.write_text(
        json.dumps(
            {
                "upstream": "https://github.com/Teerapat-Vatpitak/thai-pii-redaction",
                "commit": commit,
                "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "files": files,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"synced {len(files)} files from {commit[:12]}")


# Files living under core/ that belong to the PORT, not upstream.
PORT_OWNED = {"Dockerfile", "prewarm_ocr.py"}


def do_check() -> None:
    if not MANIFEST.exists():
        _die("no PORT_MANIFEST.json — run a sync first")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    want: dict[str, str] = manifest["files"]
    have = {
        p.relative_to(CORE).as_posix(): _sha256(p)
        for p in _iter_files(CORE)
        if p.relative_to(CORE).as_posix() not in PORT_OWNED
    }
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    changed = sorted(k for k in set(want) & set(have) if want[k] != have[k])
    if missing or extra or changed:
        for k in missing:
            print(f"MISSING  {k}", file=sys.stderr)
        for k in extra:
            print(f"EXTRA    {k}", file=sys.stderr)
        for k in changed:
            print(f"CHANGED  {k}", file=sys.stderr)
        _die("core/ does not match PORT_MANIFEST.json")
    print(f"check ok: {len(want)} files match commit {manifest['commit'][:12]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="upstream", help="path to upstream checkout")
    ap.add_argument("--check", action="store_true", help="verify core/ against manifest")
    args = ap.parse_args()
    if args.check:
        do_check()
    elif args.upstream:
        do_sync(Path(args.upstream).resolve())
    else:
        ap.error("need --from <upstream> or --check")


if __name__ == "__main__":
    main()

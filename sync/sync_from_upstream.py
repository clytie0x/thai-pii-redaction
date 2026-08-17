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
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PORT_ROOT = Path(__file__).resolve().parent.parent
CORE = PORT_ROOT / "core"
MANIFEST = Path(__file__).resolve().parent / "PORT_MANIFEST.json"
UPSTREAM_URL = "https://github.com/Teerapat-Vatpitak/thai-pii-redaction"

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
    # NOTICE points at this file for the bundled Thai TTF; OFL-1.1 requires
    # the license text to travel with the font, so it must ride the slice.
    "licenses/OFL-1.1.txt",
]

_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache"}

# Everything in SLICE is text; normalize to LF at copy time so the manifest
# hashes are identical between a Windows dev checkout (CRLF working tree) and
# the Linux runner. .gitattributes pins `* -text` so git never converts back.
_TEXT_SUFFIXES = {".py", ".txt", ".toml", ".lock", ".html", ".md", ""}


def _normalized_bytes(src: Path) -> bytes:
    data = src.read_bytes()
    if src.suffix.lower() in _TEXT_SUFFIXES or src.name in (
        "VERSION",
        "LICENSE",
        "NOTICE",
    ):
        data = data.replace(b"\r\n", b"\n")
    return data


def _copy_normalized(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = _normalized_bytes(src)
    dst.write_bytes(data)


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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
            for f in _iter_files(src):
                _copy_normalized(f, dst / f.relative_to(src))
        else:
            _copy_normalized(src, dst)

    for p in _iter_files(CORE):
        rel = p.relative_to(CORE).as_posix()
        # Port-owned overlay files inside core/ are not vendored. Prefixes are
        # deliberately narrow so an unrelated extra file still fails --check.
        if _is_port_owned(rel):
            continue
        files[rel] = _sha256(p)

    manifest_text = json.dumps(
        {
            "upstream": UPSTREAM_URL,
            "commit": commit,
            "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": files,
        },
        ensure_ascii=False,
        indent=1,
    )
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(manifest_text + "\n")
    print(f"synced {len(files)} files from {commit[:12]}")


# Files living under core/ that belong to the PORT, not upstream.
PORT_OWNED = {
    ".dockerignore",
    "Dockerfile",
    "prewarm_ocr.py",
    "aift_auth.py",
    "aift_gateway.py",
    "aift_report_policy.py",
    "healthcheck.py",
    "requirements-aift-ocr.in",
    "requirements-aift.lock",
    "requirements-aift-security.in",
    "requirements-aift-security.lock",
    "verify_thainer_assets.py",
    # Hosted has its own release channel/version. The upstream VERSION remains
    # recorded in PORT_MANIFEST.json for provenance, but the deployed Hosted
    # value is intentionally release-owned and checked by Stage 7 contracts.
    "VERSION",
}

# Hosted-only code must live behind this one bounded package prefix. Vendored
# app/ and pii_redactor/ remain hash-pinned to PORT_MANIFEST.json.
PORT_OWNED_PREFIXES = ("aift_hosted3/",)


def _is_port_owned(relative: str) -> bool:
    return relative in PORT_OWNED or any(
        relative.startswith(prefix) for prefix in PORT_OWNED_PREFIXES
    )


def _slice_hashes(upstream: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for entry in SLICE:
        source = upstream / entry
        if not source.exists():
            _die(f"SLICE entry missing at recorded upstream commit: {entry}")
        if source.is_dir():
            for item in _iter_files(source):
                relative = (Path(entry) / item.relative_to(source)).as_posix()
                files[relative] = _sha256_bytes(_normalized_bytes(item))
        else:
            files[Path(entry).as_posix()] = _sha256_bytes(_normalized_bytes(source))
    return files


def _verify_recorded_upstream(manifest: dict, want: dict[str, str]) -> None:
    commit = manifest.get("commit")
    if (
        manifest.get("upstream") != UPSTREAM_URL
        or not isinstance(commit, str)
        or len(commit) != 40
        or any(char not in "0123456789abcdef" for char in commit)
    ):
        _die("manifest upstream identity is invalid")
    with tempfile.TemporaryDirectory(prefix="aiguard_upstream_") as temp:
        checkout = Path(temp) / "upstream"
        result = subprocess.run(
            ["git", "init", "--quiet", str(checkout)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            _die(f"git init failed: {result.stderr.strip()}")
        _git(checkout, "remote", "add", "origin", UPSTREAM_URL)
        _git(checkout, "fetch", "--quiet", "--depth", "1", "origin", commit)
        fetched = _git(checkout, "rev-parse", "FETCH_HEAD")
        if fetched != commit:
            _die("fetched upstream commit does not match the manifest")
        _git(checkout, "checkout", "--quiet", "--detach", "FETCH_HEAD")
        actual = _slice_hashes(checkout)
    if actual != want:
        missing = sorted(set(want) - set(actual))
        extra = sorted(set(actual) - set(want))
        changed = sorted(
            key for key in set(want) & set(actual) if want[key] != actual[key]
        )
        for key in missing:
            print(f"UPSTREAM_MISSING  {key}", file=sys.stderr)
        for key in extra:
            print(f"UPSTREAM_EXTRA    {key}", file=sys.stderr)
        for key in changed:
            print(f"UPSTREAM_CHANGED  {key}", file=sys.stderr)
        _die("manifest hashes do not match the recorded upstream Git object")


def do_check(*, verify_upstream: bool = False) -> None:
    if not MANIFEST.exists():
        _die("no PORT_MANIFEST.json — run a sync first")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("upstream") != UPSTREAM_URL:
        _die("manifest points at an unexpected upstream repository")
    manifest_files: dict[str, str] = manifest["files"]
    want: dict[str, str] = {
        relative: digest
        for relative, digest in manifest_files.items()
        if not _is_port_owned(relative)
    }
    have = {
        p.relative_to(CORE).as_posix(): _sha256(p)
        for p in _iter_files(CORE)
        if not _is_port_owned(p.relative_to(CORE).as_posix())
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
    if verify_upstream:
        _verify_recorded_upstream(manifest, manifest_files)
    print(
        f"check ok: {len(want)} vendored files match commit {manifest['commit'][:12]}; "
        "Hosted VERSION is release-owned and its upstream provenance remains in the manifest"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="upstream", help="path to upstream checkout")
    ap.add_argument(
        "--check", action="store_true", help="verify core/ against manifest"
    )
    ap.add_argument(
        "--verify-upstream",
        action="store_true",
        help="fetch the recorded Git object and verify every manifest hash",
    )
    args = ap.parse_args()
    if args.check:
        do_check(verify_upstream=args.verify_upstream)
    elif args.upstream:
        do_sync(Path(args.upstream).resolve())
    else:
        ap.error("need --from <upstream> or --check")


if __name__ == "__main__":
    main()

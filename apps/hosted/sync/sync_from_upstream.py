#!/usr/bin/env python3
"""Check Hosted ownership and inactive historical source provenance.

The runtime consumes a supplied canonical first-party wheel. This command
cannot recreate an independently maintained engine under core/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

PORT_ROOT = Path(__file__).resolve().parent.parent
CORE = PORT_ROOT / "core"
MANIFEST = Path(__file__).resolve().parent / "PORT_MANIFEST.json"
UPSTREAM_URL = "https://github.com/clytie0x/thai-pii-redaction"
PORT_OWNED = {
    ".dockerignore", "Dockerfile", "VERSION", "prewarm_ocr.py", "aift_auth.py",
    "aift_gateway.py", "aift_report_policy.py", "healthcheck.py",
    "requirements-aift-ocr.in", "requirements-aift.lock",
    "requirements-aift-security.in", "requirements-aift-security.lock",
    "verify_thainer_assets.py", "verify_core_install.py",
}
PORT_OWNED_PREFIXES = ("aift_hosted3/",)


def _is_port_owned(relative: str) -> bool:
    return relative in PORT_OWNED or any(relative.startswith(prefix) for prefix in PORT_OWNED_PREFIXES)


def _die(message: str) -> None:
    raise SystemExit(f"sync: {message}")


def _git(checkout: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True)
    if result.returncode:
        _die("historical Git-object verification failed")
    return result.stdout


def do_sync(_upstream: Path) -> None:
    _die("legacy source copying is disabled; prepare a supplied canonical wheel context")


def _verify_recorded_upstream(manifest: dict) -> None:
    commit = manifest.get("commit", "")
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        _die("invalid historical source revision")
    with tempfile.TemporaryDirectory(prefix="aiguard-historical-source-") as temporary:
        checkout = Path(temporary)
        subprocess.run(["git", "init", "--quiet", str(checkout)], check=True, capture_output=True)
        _git(checkout, "remote", "add", "origin", UPSTREAM_URL)
        _git(checkout, "fetch", "--quiet", "--depth", "1", "origin", commit)
        if _git(checkout, "rev-parse", "FETCH_HEAD").decode().strip() != commit:
            _die("historical source revision mismatch")
        for relative, expected in manifest["files"].items():
            name = PurePosixPath(relative)
            if name.is_absolute() or ".." in name.parts or "\\" in relative:
                _die("unsafe historical source inventory")
            payload = _git(checkout, "show", f"{commit}:{relative}")
            if name.suffix.lower() in {".py", ".txt", ".toml", ".lock", ".html", ".md", ""}:
                payload = payload.replace(b"\r\n", b"\n")
            if hashlib.sha256(payload).hexdigest() != expected:
                _die("historical source digest mismatch")


def do_check(*, verify_upstream: bool = False) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("upstream") != UPSTREAM_URL:
        _die("unexpected historical source repository")
    if any((CORE / name).exists() for name in ("app", "pii_redactor")):
        _die("an independent authored runtime core remains")
    dockerfile = (CORE / "Dockerfile").read_text(encoding="utf-8")
    if "COPY app " in dockerfile or "COPY pii_redactor " in dockerfile or "--no-index" not in dockerfile:
        _die("runtime must consume the supplied offline canonical wheel")
    retained = {relative: digest for relative, digest in manifest["files"].items() if not relative.startswith(("app/", "pii_redactor/")) and not _is_port_owned(relative)}
    for relative, digest in retained.items():
        path = CORE / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            _die("retained historical support-file digest mismatch")
    allowed = set(retained) | {relative for relative in manifest["files"] if _is_port_owned(relative)}
    for path in CORE.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(CORE).as_posix()
        if relative not in allowed and not _is_port_owned(relative):
            _die("unclassified Hosted core source file")
    if verify_upstream:
        _verify_recorded_upstream(manifest)
    print("check ok: canonical-wheel runtime, no authored engine copy; historical manifest is inactive provenance")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="upstream")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify-upstream", action="store_true")
    args = parser.parse_args()
    if args.upstream:
        do_sync(Path(args.upstream))
    elif args.check:
        do_check(verify_upstream=args.verify_upstream)
    else:
        parser.error("need --check; legacy --from is intentionally disabled")


if __name__ == "__main__":
    main()

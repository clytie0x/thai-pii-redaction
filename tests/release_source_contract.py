#!/usr/bin/env python3
"""Value-free secret scan and current-document consistency contract."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "44ef30b0e8ea2021fc4ceec9d3b12dc9f64c750f"
CURRENT_DOCS = (
    ROOT / "README.md",
    ROOT / "STATE.md",
    ROOT / "docs" / "DEPLOY-DAY.md",
    ROOT / "docs" / "DEPLOY-DESIGN.md",
)
SECRET_PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "gitlab-token": re.compile(rb"glpat-[A-Za-z0-9_-]{20,}"),
    "github-token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "aws-access-key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "openai-key": re.compile(rb"sk-[A-Za-z0-9]{32,}"),
    "google-api-key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
}


def tracked_files() -> list[Path]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [ROOT / item.decode("utf-8") for item in raw.split(b"\0") if item]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if path.name == ".env" or path.name.startswith(".env."):
            findings.append(f"{relative}:tracked-env-file")
            continue
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(f"{relative}:unreadable")
            continue
        if b"\0" in data:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                findings.append(f"{relative}:{label}")
    if findings:
        # Deliberately report classifications and paths, never matched values.
        raise AssertionError("secret-pattern candidates: " + ", ".join(findings))

    manifest = json.loads((ROOT / "sync" / "PORT_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["commit"] == UPSTREAM
    assert len(manifest["files"]) == 75
    assert (ROOT / "core" / "VERSION").read_text(encoding="utf-8").strip() == "2.5.0"

    current = "\n".join(path.read_text(encoding="utf-8") for path in CURRENT_DOCS)
    for required in (
        "44ef30b",
        "16 routes",
        "/redact-pdf",
        "/v1/redact-pdf",
        "APP_AIGUARD_API_KEY",
        "APP_AIFT_ACCESS_CODE",
        "APP_AIFT_COOKIE_SIGNING_KEY",
        "APP_TOKENMIND_API_KEY",
    ):
        assert required in current, required
    assert re.search(r"(?:fixed|proxy-level) 404", current, re.IGNORECASE)

    vendored = b"\n".join(
        path.read_bytes()
        for base in (ROOT / "core" / "app", ROOT / "core" / "pii_redactor")
        for path in base.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ).lower()
    for contamination in (b"native broker", b"native messaging", b"named pipe"):
        assert contamination not in vendored, contamination.decode("ascii")
    public_surface = b"\n".join(
        [
            *(path.read_bytes() for base in (ROOT / "api", ROOT / "web") for path in base.rglob("*") if path.is_file()),
            (ROOT / "core" / "aift_auth.py").read_bytes(),
            (ROOT / "core" / "aift_gateway.py").read_bytes(),
            (ROOT / "docker-compose.yml").read_bytes(),
            (ROOT / ".gitlab-ci.yml").read_bytes(),
        ]
    ).lower()
    for contamination in (b"native broker", b"native messaging", b"named pipe", b"chrome-extension://", b"tauri"):
        assert contamination not in public_surface, contamination.decode("ascii")
    print(
        "release source contract ok: tracked secret patterns absent, docs/version/pin consistent, "
        "hosted slice uncontaminated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

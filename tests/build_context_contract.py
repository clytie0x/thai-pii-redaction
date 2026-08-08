"""Executable contract for Docker context and image-copy exclusions."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
CONTEXTS = ("core", "api", "web")
FORBIDDEN_SENTINELS = (
    ".env",
    ".env.production",
    "service/.env",
    "service/.env.secret",
    ".git/config",
    "credentials.json",
    "nested/credentials.json",
    "service-account-prod.json",
    "private.pem",
    "nested/private.key",
    "tests/out/evidence.json",
    "artifacts/runtime.json",
    "out/result.txt",
    "__pycache__/module.pyc",
    ".vscode/settings.json",
    ".idea/workspace.xml",
    "runtime.log",
    "scratch.tmp",
)


def docker_ignored(relative: str, patterns: list[str]) -> bool:
    path = PurePosixPath(relative)
    ignored = False
    for raw in patterns:
        pattern = raw.strip()
        if not pattern or pattern.startswith("#"):
            continue
        negate = pattern.startswith("!")
        if negate:
            pattern = pattern[1:]
        matched = path.match(pattern) or any(
            parent.match(pattern) for parent in path.parents if str(parent) != "."
        )
        if matched:
            ignored = not negate
    return ignored


def main() -> int:
    for name in CONTEXTS:
        context = ROOT / name
        ignore_file = context / ".dockerignore"
        if not ignore_file.is_file():
            raise AssertionError(f"{name} context has no .dockerignore")
        patterns = ignore_file.read_text(encoding="utf-8").splitlines()
        escaped = [path for path in FORBIDDEN_SENTINELS if not docker_ignored(path, patterns)]
        if escaped:
            raise AssertionError(f"{name} context admits forbidden files: {escaped}")

        dockerfile = (context / "Dockerfile").read_text(encoding="utf-8")
        copies = re.findall(r"^COPY\s+(.+)$", dockerfile, re.MULTILINE)
        if any(re.match(r"(?:--\S+\s+)*\.?\.?(?:\s|$)", row) for row in copies):
            raise AssertionError(f"{name} Dockerfile uses an unbounded COPY")

    core_dockerfile = (ROOT / "core" / "Dockerfile").read_text(encoding="utf-8")
    for required in (
        "COPY app ./app",
        "COPY pii_redactor ./pii_redactor",
        "COPY aift_auth.py aift_gateway.py VERSION LICENSE NOTICE ./",
        "COPY licenses ./licenses",
    ):
        if required not in core_dockerfile:
            raise AssertionError(f"core runtime copy allowlist missing: {required}")
    print("build context contract ok: env, credential, VCS, output, cache, and editor sentinels excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

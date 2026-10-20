"""Executable contract for Docker context and image-copy exclusions."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
CONTEXTS = ("core", "api", "web", "pdf-parser")
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
        "COPY requirements.lock requirements-aift-security.lock ./",
        "--no-deps --require-hashes -r requirements-aift-security.lock",
        "COPY app ./app",
        "COPY pii_redactor ./pii_redactor",
        "COPY aift_hosted3 ./aift_hosted3",
        "COPY verify_thainer_assets.py ./",
        "python verify_thainer_assets.py",
        "COPY aift_auth.py aift_gateway.py aift_report_policy.py healthcheck.py VERSION LICENSE NOTICE ./",
        "COPY licenses ./licenses",
    ):
        if required not in core_dockerfile:
            raise AssertionError(f"core runtime copy allowlist missing: {required}")
    for excluded in (
        "prewarm_ocr.py",
        "requirements.lock requirements-aift.lock",
        "libgl1",
        "libglib2.0-0",
        "libgomp1",
    ):
        if excluded in core_dockerfile:
            raise AssertionError(f"disabled OCR runtime leaked into hosted image: {excluded}")

    security_overlay = (ROOT / "core" / "requirements-aift-security.lock").read_text(
        encoding="utf-8"
    )
    if "cryptography==50.0.0" not in security_overlay or "cryptography==49.0.0" in security_overlay:
        raise AssertionError("hosted security overlay does not close PYSEC-2026-3552")

    model_verifier = (ROOT / "core" / "verify_thainer_assets.py").read_text(
        encoding="utf-8"
    )
    evaluation = (
        ROOT / "evaluation" / "thai_pii" / "baseline.72e18bbe.json"
    ).read_text(encoding="utf-8")
    expected_model_hash = (
        "bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315"
    )
    if expected_model_hash not in model_verifier or expected_model_hash not in evaluation:
        raise AssertionError("hosted NER model digest is not bound to certified evidence")

    web_dockerfile = (ROOT / "web" / "Dockerfile").read_text(encoding="utf-8")
    api_dockerfile = (ROOT / "api" / "Dockerfile").read_text(encoding="utf-8")
    for required in (
        "home.css home.js app.html app.css hosted3-app.js product.css privacy.html terms.html help.html downloads.html developers.html 404.html robots.txt sitemap.xml",
        "assets/ai-guard-mark.svg assets/ai-guard-mark-one-color.svg assets/ai-guard-mark-inverse.svg assets/ai-guard-favicon.svg assets/ai-guard-favicon-inverse.svg",
        "assets/fonts/anuphan-thai.woff2 assets/fonts/anuphan-latin.woff2 assets/fonts/OFL-Anuphan.txt",
        "COPY healthcheck.sh /usr/local/bin/aift-healthcheck",
    ):
        if required not in web_dockerfile:
            raise AssertionError(f"web product image is incomplete: {required}")
    expected_web_asset_hashes = {
        "assets/fonts/anuphan-thai.woff2": "8a03cb45df9decacc349c794b1d626363109d99affb74f698a27d019996c220f",
        "assets/fonts/anuphan-latin.woff2": "3a98eb4685d98ab59073f8b2f9995629e23f850f737144025b3ce491f20372d6",
        "assets/fonts/OFL-Anuphan.txt": "94da26c98ca8d2ec3555ad30828a4184edfdf5832df92ae8cf4edd490e9ee655",
    }
    for relative_path, expected_hash in expected_web_asset_hashes.items():
        payload = (ROOT / "web" / relative_path).read_bytes()
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != expected_hash:
            raise AssertionError(
                f"web licensed asset digest changed: {relative_path} {actual_hash}"
            )
    if not (ROOT / "web" / "assets/fonts/anuphan-thai.woff2").read_bytes().startswith(b"wOF2"):
        raise AssertionError("Anuphan Thai asset is not WOFF2")
    if not (ROOT / "web" / "assets/fonts/anuphan-latin.woff2").read_bytes().startswith(b"wOF2"):
        raise AssertionError("Anuphan Latin asset is not WOFF2")
    if "COPY healthcheck.sh /usr/local/bin/aift-healthcheck" not in api_dockerfile:
        raise AssertionError("api image lacks its bounded recovery probe")
    print("build context contract ok: env, credential, VCS, output, cache, and editor sentinels excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

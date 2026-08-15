#!/usr/bin/env python3
"""Secret, current-document, and external release-identity contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import urllib.error
import urllib.request
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "44ef30b0e8ea2021fc4ceec9d3b12dc9f64c750f"
CURRENT_DOCS = (
    ROOT / "README.md",
    ROOT / "STATE.md",
    ROOT / "docs" / "DEPLOY-DAY.md",
    ROOT / "docs" / "DEPLOY-DESIGN.md",
    ROOT / "docs" / "GITLAB-HANDOFF.md",
)
RELEASE_PAGE = (
    "https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/tag/v3.0.0"
)
RELEASE_ASSET_BASE = (
    "https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/download/v3.0.0/"
)
RELEASE_ASSETS = (
    "AI.Guard_3.0.0_x64-setup.exe",
    "AI.Guard_3.0.0_amd64.deb",
    "AI.Guard_3.0.0_amd64.AppImage",
    "AI.Guard_3.0.0_aarch64.dmg",
    "aiguard-extension-3.0.0.zip",
)
RELEASE_ASSET_TRUST = {
    "AI.Guard_3.0.0_x64-setup.exe": {
        "sha256": "1d170bf792923564dcc599b849de9f72a19b89f18e0be82e43849cdad75880ef",
        "size": 70_696_034,
        "asset_id": "c7408bb6-d827-4481-bf61-3eba66f3c2de",
    },
    "AI.Guard_3.0.0_amd64.deb": {
        "sha256": "7b5fbdc0cf9019254e89c006870ae244a31fbf5db038ae699e4b0c3a91d6b9e8",
        "size": 98_758_624,
        "asset_id": "d35071ab-51cf-444f-9834-1174cd826907",
    },
    "AI.Guard_3.0.0_amd64.AppImage": {
        "sha256": "f0178a8b171bea1f28868563f52a05e0ad09008e93bdc6581a160d5bda486a34",
        "size": 172_784_120,
        "asset_id": "b1b0d584-27b9-4889-b7d0-363cb9cd4113",
    },
    "AI.Guard_3.0.0_aarch64.dmg": {
        "sha256": "663fff430671ff0210044a1c1b64675b2918597db27ebae16103a9dd5988a356",
        "size": 70_844_788,
        "asset_id": "cee04ccd-e0fa-4e9b-82c3-b4cc97144d19",
    },
    "aiguard-extension-3.0.0.zip": {
        "sha256": "feb048775ec3d2a2c57ade08b37000fc4fa035a72ffb77db201e5eb838357670",
        "size": 295_228,
        "asset_id": "f62e82b6-9029-476f-87c9-27857d27750c",
    },
}
CHECKSUMS_NAME = "SHA256SUMS"
CHECKSUMS_SHA256 = "ff3a8c68f7110d362d772f665cbe940b58bc5bfd4ad6e9a2f6c25e19529ed518"
CHECKSUMS_SIZE = 951
CHECKSUMS_ASSET_ID = "e9c2b6c9-cb25-4e04-a49a-fb0c01da5877"
RELEASE_ASSET_PATH_PREFIX = "/github-production-release-asset/1281827214/"
RELEASE_ASSET_HOST = "release-assets.githubusercontent.com"
SECURITY_SOURCE = (
    "https://github.com/Teerapat-Vatpitak/thai-pii-redaction/blob/v3.0.0/"
    "SECURITY.md#local-desktop-and-extension"
)
SECRET_PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "gitlab-token": re.compile(rb"glpat-[A-Za-z0-9_-]{20,}"),
    "github-token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "aws-access-key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "openai-key": re.compile(rb"sk-[A-Za-z0-9]{32,}"),
    "google-api-key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url: str, *, method: str = "HEAD") -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={"User-Agent": "aiguard-aift-release-contract/1"},
        method=method,
    )


def release_redirect(url: str) -> str:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        opener.open(request(url), timeout=30)
    except urllib.error.HTTPError as error:
        assert error.code == 302, (url, error.code)
        location = error.headers.get("Location", "")
        assert location
        return location
    raise AssertionError(f"release asset did not redirect: {url}")


def verify_release_assets() -> None:
    follow = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    expected = {
        **RELEASE_ASSET_TRUST,
        CHECKSUMS_NAME: {
            "sha256": CHECKSUMS_SHA256,
            "size": CHECKSUMS_SIZE,
            "asset_id": CHECKSUMS_ASSET_ID,
        },
    }
    for name, metadata in expected.items():
        url = RELEASE_ASSET_BASE + name
        location = release_redirect(url)
        redirect = urlparse(location)
        expected_path = RELEASE_ASSET_PATH_PREFIX + str(metadata["asset_id"])
        assert redirect.scheme == "https", name
        assert redirect.hostname == RELEASE_ASSET_HOST, name
        assert redirect.path == expected_path, name
        with follow.open(request(url), timeout=30) as response:
            final = urlparse(response.url)
            assert response.status == 200, name
            assert final.scheme == "https", name
            assert final.hostname == RELEASE_ASSET_HOST, name
            assert final.path == expected_path, name
            assert int(response.headers["Content-Length"]) == metadata["size"], name

    checksums_url = RELEASE_ASSET_BASE + CHECKSUMS_NAME
    with follow.open(request(checksums_url, method="GET"), timeout=30) as response:
        checksums = response.read()
    assert len(checksums) == CHECKSUMS_SIZE
    assert hashlib.sha256(checksums).hexdigest() == CHECKSUMS_SHA256
    checksum_lines = checksums.decode("ascii").splitlines()
    for name in RELEASE_ASSETS[:4]:
        expected_line = f'{RELEASE_ASSET_TRUST[name]["sha256"]}  {name}'
        assert expected_line in checksum_lines, name

    extension = RELEASE_ASSETS[-1]
    with follow.open(
        request(RELEASE_ASSET_BASE + extension, method="GET"), timeout=30
    ) as response:
        extension_bytes = response.read()
    assert len(extension_bytes) == RELEASE_ASSET_TRUST[extension]["size"]
    assert (
        hashlib.sha256(extension_bytes).hexdigest()
        == RELEASE_ASSET_TRUST[extension]["sha256"]
    )


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

    downloads_path = ROOT / "web" / "downloads.html"
    downloads = downloads_path.read_text(encoding="utf-8")
    frontend = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    terms = (ROOT / "web" / "terms.html").read_text(encoding="utf-8")
    release_links = (
        RELEASE_PAGE,
        *(RELEASE_ASSET_BASE + name for name in RELEASE_ASSETS),
    )
    for link in release_links:
        assert f'href="{link}"' in downloads, link
    for name in RELEASE_ASSETS:
        assert downloads.count(RELEASE_ASSET_BASE + name) == 1, name
        assert RELEASE_ASSET_TRUST[name]["sha256"] in downloads, name
    assert f'href="{RELEASE_ASSET_BASE + CHECKSUMS_NAME}"' in downloads
    assert CHECKSUMS_SHA256 in downloads
    assert "gh attestation verify" in downloads
    assert f'href="{SECURITY_SOURCE}"' in downloads
    assert "Manual / Developer installation" in downloads
    assert "AI Guard Desktop 3.0.0" in downloads
    assert 'data-recommended="true"' in downloads
    assert "แนะนำเริ่มต้น · Windows x64" in downloads
    assert "เผยแพร่ 14 ส.ค. 2569" in downloads
    assert "ความต้องการพื้นฐาน" in downloads
    for metadata in ("70.7 MB", "98.8 MB", "172.8 MB", "70.8 MB"):
        assert metadata in downloads, metadata
    assert '<details class="verification"' in downloads
    assert "Verify this file · ตรวจ SHA-256 และ provenance" in downloads
    verification_index = downloads.index('<details class="verification"')
    for name in RELEASE_ASSETS[:4]:
        assert downloads.index(RELEASE_ASSET_TRUST[name]["sha256"]) > verification_index
    assert downloads.index(RELEASE_ASSET_BASE + RELEASE_ASSETS[0]) < downloads.index(
        RELEASE_ASSET_BASE + RELEASE_ASSETS[1]
    )
    assert "Desktop 3.0.0 ไม่มีคำสั่งส่งข้อความไปยัง provider ภายนอก" in downloads
    assert "Pathumma" in downloads and "บริการ Team 08" in downloads
    assert "Native Messaging" in downloads
    assert "แตกไฟล์ ZIP" in downloads
    assert "Load unpacked" in downloads
    assert "การเซ็นโค้ดยังเลื่อนไว้" in downloads
    assert "อาจแสดงคำเตือน" in downloads
    for unsafe_instruction in (
        "ignore warnings",
        "ignore the warning",
        "เพิกเฉยต่อคำเตือน",
    ):
        assert unsafe_instruction not in downloads.lower(), unsafe_instruction
    for store_link in (
        "chrome.google.com/webstore/detail",
        "chromewebstore.google.com/detail",
    ):
        assert store_link not in downloads + frontend + terms, store_link
    for marker in ("เตรียมส่งตรวจสอบ", "ยังไม่เผยแพร่"):
        assert marker in downloads + frontend + terms, marker
    for privacy_boundary in (
        "ข้อความดิบเข้า DOM ของเว็บไซต์ AI",
        "โค้ดของเว็บไซต์อาจเห็นหรือส่งข้อความนั้นได้ก่อนการปกปิด",
        "Side Panel เป็นขอบเขตที่แข็งแรงกว่า",
    ):
        assert privacy_boundary in downloads + frontend, privacy_boundary
    assert len(re.findall(r'href="/downloads(?:#[^"]+)?"', frontend)) >= 4
    assert "AI Guard 3.0.0" in current

    vendored = b"\n".join(
        path.read_bytes()
        for base in (ROOT / "core" / "app", ROOT / "core" / "pii_redactor")
        for path in base.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ).lower()
    for contamination in (b"native broker", b"native messaging", b"named pipe"):
        assert contamination not in vendored, contamination.decode("ascii")
    public_surface_paths = [
        *(
            path
            for base in (ROOT / "api", ROOT / "web")
            for path in base.rglob("*")
            if path.is_file()
        ),
        ROOT / "core" / "aift_auth.py",
        ROOT / "core" / "aift_gateway.py",
        ROOT / "docker-compose.yml",
        ROOT / ".gitlab-ci.yml",
    ]
    public_surface = b"\n".join(path.read_bytes() for path in public_surface_paths).lower()
    for contamination in (b"native broker", b"named pipe", b"chrome-extension://", b"tauri"):
        assert contamination not in public_surface, contamination.decode("ascii")
    implementation_surface = b"\n".join(
        path.read_bytes() for path in public_surface_paths if path != downloads_path
    ).lower()
    assert b"native messaging" not in implementation_surface

    public_policy_path = ROOT / "tests" / "public_web_acceptance.py"
    public_policy_source = public_policy_path.read_text(encoding="utf-8")
    public_policy = runpy.run_path(str(public_policy_path))
    classify_http_redirect = public_policy["classify_http_redirect"]
    warning = classify_http_redirect(
        "/?sentinel=contract",
        200,
        {"Strict-Transport-Security": "max-age=31536000"},
        b"AI Guard",
    )
    assert warning == {
        "type": "external_http_to_https_redirect_unavailable",
        "scope": "organizer_public_edge",
        "owner_risk_decision_date": "2026-08-15",
        "path": "/",
        "observed_status": 200,
        "expected_redirect_status": 308,
        "expected_https_location": "https://team08.aiforthai.in.th/",
        "location_matches_expected_https": False,
        "plain_http_secure": False,
        "rollback_eligible": False,
    }
    assert classify_http_redirect(
        "/api/health?sentinel=contract",
        308,
        {"Location": "https://team08.aiforthai.in.th/api/health"},
        b"",
    ) is None
    try:
        classify_http_redirect(
            "/",
            308,
            {"Location": "http://team08.aiforthai.in.th/elsewhere"},
            b"",
        )
    except AssertionError:
        pass
    else:
        raise AssertionError("an incorrect 308 redirect must remain fatal")
    assert "assert status == 308" not in public_policy_source
    assert "PUBLIC_EDGE_WARNING " in public_policy_source
    assert "ssl.create_default_context()" in public_policy_source
    assert public_policy["LEGACY_DENIALS"] == (
        "/not-a-product-page",
        "/api/sanitize",
        "/api/reidentify",
        "/api/docs",
        "/api/openapi.json",
        "/api/api/health",
        "/api/detectx",
        "/api/v1/sanitize",
        "/api/auth/unknown",
        "/api/v1/auth/unknown",
        "/api/redact-pdf",
        "/api/v1/redact-pdf",
    )
    verify_release_assets()
    print(
        "release source contract ok: tracked secret patterns absent, docs/version/pin consistent, "
        "external assets pinned, hosted slice uncontaminated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

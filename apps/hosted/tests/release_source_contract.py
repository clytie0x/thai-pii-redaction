#!/usr/bin/env python3
"""Secret, current-document, and external release-identity contract."""

from __future__ import annotations

import json
from pathlib import Path
import re
import runpy
import subprocess


ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = "436d9ab7880762513826cc204d6ff770faf0e193"
CURRENT_DOCS = (
    ROOT / "README.md",
    ROOT / "STATE.md",
    ROOT / "docs" / "DEPLOY-DAY.md",
    ROOT / "docs" / "DEPLOY-DESIGN.md",
    ROOT / "docs" / "GITLAB-HANDOFF.md",
    ROOT / "docs" / "HOSTED-3-DEPLOY-API-GUIDE.md",
)
SECURITY_SOURCE = (
    "https://github.com/clytie0x/thai-pii-redaction/blob/main/"
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
    assert (ROOT / "core" / "VERSION").read_text(encoding="utf-8").strip() == "0.1.0"

    current = "\n".join(path.read_text(encoding="utf-8") for path in CURRENT_DOCS)
    for required in (
        "3c2997835dbd",
        "40 routes",
        "/redact-pdf",
        "/v1/redact-pdf",
        "APP_AIGUARD_API_KEY",
        "APP_AIFT_ACCESS_CODE",
        "APP_AIFT_COOKIE_SIGNING_KEY",
        "APP_AIFT_PRIORITY_INVITES_JSON",
        "APP_TOKENMIND_API_KEY",
    ):
        assert required in current, required
    assert re.search(r"(?:fixed|proxy-level) 404", current, re.IGNORECASE)

    current_guide = (ROOT / "docs" / "HOSTED-3-DEPLOY-API-GUIDE.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "514945a42f161a96672ace4545ae8afc9c856338",
        "#36540",
        "40 exact locations",
        "same-origin application",
        "web, api, core, pdf-parser",
        "APP_AIFT_PRIORITY_INVITES_JSON",
        "Pathumma ไม่ได้รับ source PDF",
    ):
        assert required in current_guide, required
    for forbidden in (
        "synthetic-distinct-core-key",
        "YOUR_PRIORITY_INVITE",
        "public arbitrary third-party API key",
    ):
        assert forbidden not in current_guide, forbidden
    hosted3_fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "hosted3" / "contract.json").read_text(
            encoding="utf-8"
        )
    )
    expected_canonical_routes = set(hosted3_fixture["existing_canonical_routes"]) | set(
        hosted3_fixture["additive_canonical_routes"]
    )
    documented_canonical_routes = set(
        re.findall(r"\| (?:GET|POST) \| `([^`]+)` \|", current_guide)
    )
    assert documented_canonical_routes == expected_canonical_routes
    for historical_name in (
        "DEPLOY-DAY.md",
        "DEPLOY-DESIGN.md",
        "GITLAB-HANDOFF.md",
        "PRODUCTION-READINESS.md",
    ):
        historical = (ROOT / "docs" / historical_name).read_text(encoding="utf-8")
        assert "Historical" in historical, historical_name
        assert "HOSTED-3-DEPLOY-API-GUIDE.md" in historical, historical_name

    downloads_path = ROOT / "web" / "downloads.html"
    downloads = downloads_path.read_text(encoding="utf-8")
    frontend = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    terms = (ROOT / "web" / "terms.html").read_text(encoding="utf-8")
    # No 0.x Desktop or Extension build is published (repository decision
    # docs/decisions/2026-10-19-version-reset.md), so the page links to no
    # release asset and says so.
    for release_path in ("/releases/download/", "/releases/tag/", "/releases/latest"):
        assert release_path not in downloads, release_path
    assert "ยังไม่มีไฟล์ให้ดาวน์โหลด" in downloads
    assert "AI Guard Desktop 0.1.0" in downloads
    assert f'href="{SECURITY_SOURCE}"' in downloads
    assert "ไม่มีคำสั่งส่งข้อความไปยัง provider ภายนอก" in downloads
    assert "Pathumma" in downloads and "บริการ Team 08" in downloads
    assert "Native Messaging" in downloads
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
    assert "Hosted 0.1.0" in current

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
    assert_no_insecure_network_reference = public_policy[
        "assert_no_insecure_network_reference"
    ]
    assert_no_insecure_network_reference(
        "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg "
        "xmlns='http://www.w3.org/2000/svg'%3E\">",
        "/inline-svg-contract",
    )
    for insecure_reference in (
        '<img src="http://example.invalid/pixel.png">',
        '<div style="background:url(http://example.invalid/pixel.png)">',
        '<script>fetch("http://example.invalid/data")</script>',
        '<source srcset="https://example.invalid/a.png 1x, '
        'http://example.invalid/b.png 2x">',
        '<meta http-equiv="refresh" content="0;url=http://example.invalid/">',
        '<svg><use xlink:href="http://example.invalid/sprite.svg#icon"></use></svg>',
    ):
        try:
            assert_no_insecure_network_reference(
                insecure_reference, "/mixed-content-contract"
            )
        except AssertionError:
            pass
        else:
            raise AssertionError("an active plain-HTTP reference must remain fatal")
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
        "/api/auth/guestx",
        "/api/v1/document-preview/x",
        "/api/provider-queue/join/",
    )
    print(
        "release source contract ok: tracked secret patterns absent, docs/version/pin consistent, "
        "no release asset linked, hosted slice uncontaminated"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

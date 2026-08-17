#!/usr/bin/env python3
"""Credential-free acceptance for the real AI for Thai public edge."""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import re
import ssl
import urllib.error
import urllib.request

HTTPS = "https://team08.aiforthai.in.th"
HTTP = "http://team08.aiforthai.in.th"
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
RELEASE_ASSET_SHA256 = (
    "1d170bf792923564dcc599b849de9f72a19b89f18e0be82e43849cdad75880ef",
    "7b5fbdc0cf9019254e89c006870ae244a31fbf5db038ae699e4b0c3a91d6b9e8",
    "f0178a8b171bea1f28868563f52a05e0ad09008e93bdc6581a160d5bda486a34",
    "663fff430671ff0210044a1c1b64675b2918597db27ebae16103a9dd5988a356",
    "feb048775ec3d2a2c57ade08b37000fc4fa035a72ffb77db201e5eb838357670",
)
HTTP_PROBES = (
    "/?sentinel=must-not-reflect",
    "/api/health?sentinel=must-not-reflect",
)
OWNER_HTTP_RISK_DECISION_DATE = "2026-08-15"
LEGACY_DENIALS = (
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
INSECURE_CSS_REFERENCE = re.compile(
    r"(?:url\(\s*['\"]?|@import\s+(?:url\(\s*)?['\"]?)http://",
    re.IGNORECASE,
)
INSECURE_SCRIPT_REFERENCE = re.compile(
    r"(?:fetch|WebSocket|EventSource)\s*\(\s*['\"](?:http|ws)://",
    re.IGNORECASE,
)
NETWORK_URL_ATTRIBUTES = {
    "action",
    "background",
    "cite",
    "formaction",
    "href",
    "longdesc",
    "manifest",
    "ping",
    "poster",
    "src",
    "xlink:href",
}
STATIC_ASSETS = {
    "/home.css": ("text/css", b"    @font-face", None),
    "/home.js": ("application/javascript", b"document.documentElement.classList.add", None),
    "/app.css": ("text/css", b"  @font-face", None),
    "/hosted3-app.js": ("application/javascript", b'"use strict";', None),
    "/product.css": ("text/css", b"@font-face", None),
    "/assets/ai-guard-mark.svg": ("image/svg+xml", b"<svg", None),
    "/assets/ai-guard-mark-one-color.svg": ("image/svg+xml", b"<svg", None),
    "/assets/ai-guard-mark-inverse.svg": ("image/svg+xml", b"<svg", None),
    "/assets/ai-guard-favicon.svg": ("image/svg+xml", b"<svg", None),
    "/assets/ai-guard-favicon-inverse.svg": ("image/svg+xml", b"<svg", None),
    "/assets/fonts/anuphan-thai.woff2": (
        "font/woff2",
        b"wOF2",
        "8a03cb45df9decacc349c794b1d626363109d99affb74f698a27d019996c220f",
    ),
    "/assets/fonts/anuphan-latin.woff2": (
        "font/woff2",
        b"wOF2",
        "3a98eb4685d98ab59073f8b2f9995629e23f850f737144025b3ce491f20372d6",
    ),
    "/assets/fonts/OFL-Anuphan.txt": (
        "text/plain",
        b"Copyright 2019 The Anuphan Project Authors",
        "94da26c98ca8d2ec3555ad30828a4184edfdf5832df92ae8cf4edd490e9ee655",
    ),
}


class NetworkReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.insecure_reference = False

    def _check_attributes(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        normalized = {name.lower(): value or "" for name, value in attributes}
        if tag.lower() == "meta" and normalized.get("http-equiv", "").lower() == "refresh":
            if re.search(r"url\s*=\s*['\"]?http://", normalized.get("content", ""), re.I):
                self.insecure_reference = True
        for name, value in attributes:
            if value is None:
                continue
            attribute = name.lower()
            candidate = value.strip().lower()
            if attribute in NETWORK_URL_ATTRIBUTES and candidate.startswith(
                ("http://", "ws://")
            ):
                self.insecure_reference = True
            elif (
                attribute == "data"
                and tag.lower() == "object"
                and candidate.startswith("http://")
            ):
                self.insecure_reference = True
            elif attribute == "srcset":
                urls = (item.strip().split(maxsplit=1)[0] for item in value.split(","))
                if any(url.lower().startswith("http://") for url in urls if url):
                    self.insecure_reference = True
            elif attribute == "style" and INSECURE_CSS_REFERENCE.search(value):
                self.insecure_reference = True

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        self._check_attributes(tag, attributes)

    def handle_startendtag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        self._check_attributes(tag, attributes)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    NoRedirect(),
    urllib.request.HTTPSHandler(context=ssl.create_default_context()),
)


def fetch(url: str) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "aiguard-public-acceptance/3.0"},
        method="GET",
    )
    try:
        with OPENER.open(request, timeout=20) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def classify_http_redirect(
    path: str,
    status: int,
    headers: dict[str, str],
    body: bytes,
) -> dict[str, object] | None:
    """Keep a correct redirect strict; report organizer-edge absence without rollback."""
    expected = HTTPS + path.split("?", 1)[0]
    if status == 308:
        assert headers.get("Location") == expected, (path, headers.get("Location"))
        assert b"AI Guard" not in body
        return None
    return {
        "type": "external_http_to_https_redirect_unavailable",
        "scope": "organizer_public_edge",
        "owner_risk_decision_date": OWNER_HTTP_RISK_DECISION_DATE,
        "path": path.split("?", 1)[0],
        "observed_status": status,
        "expected_redirect_status": 308,
        "expected_https_location": expected,
        "location_matches_expected_https": headers.get("Location") == expected,
        "plain_http_secure": False,
        "rollback_eligible": False,
    }


def assert_no_insecure_network_reference(text: str, path: str) -> None:
    """Reject active plain-HTTP references, not an inline SVG XML namespace."""
    parser = NetworkReferenceParser()
    parser.feed(text)
    assert not parser.insecure_reference, path
    assert INSECURE_CSS_REFERENCE.search(text) is None, path
    assert INSECURE_SCRIPT_REFERENCE.search(text) is None, path


def main() -> int:
    warnings: list[dict[str, object]] = []
    for path in HTTP_PROBES:
        status, headers, body = fetch(HTTP + path)
        warning = classify_http_redirect(path, status, headers, body)
        if warning is not None:
            warnings.append(warning)
            print("PUBLIC_EDGE_WARNING " + json.dumps(warning, sort_keys=True))

    pages = {
        "/": "ปกป้องข้อมูลก่อน",
        "/app": "Hosted 3.0.0 Web App",
        "/privacy": "ข้อมูลไปไหน",
        "/terms": "ใช้ได้เมื่อ",
        "/help": "แก้ปัญหา",
        "/downloads": "Manual / Developer installation",
        "/developers": "Contract &amp;",
        "/robots.txt": "Disallow: /api/",
        "/sitemap.xml": "https://team08.aiforthai.in.th/privacy",
    }
    for path, marker in pages.items():
        status, headers, body = fetch(HTTPS + path)
        text = body.decode("utf-8")
        assert status == 200, (path, status)
        assert marker in text, path
        assert headers.get("Strict-Transport-Security") == "max-age=31536000", path
        assert headers.get("X-Content-Type-Options") == "nosniff", path
        assert headers.get("X-Frame-Options") == "DENY", path
        assert headers.get("Referrer-Policy") == "no-referrer", path
        assert_no_insecure_network_reference(text, path)
        if path == "/":
            assert 'href="/downloads#desktop">ดาวน์โหลด Desktop 3.0.0' in text
            assert 'id="h3StartStandard"' not in text
            assert 'src="/app.js"' not in text
            assert "/app#privacy-scan" in text
        if path == "/app":
            assert 'content="noindex,nofollow"' in text
            assert 'id="h3StartStandard"' in text
            assert 'id="h3PrioritySubmit"' in text
            assert 'src="/hosted3-app.js" defer' in text
            assert "Hosted 3.0.0" in text
            assert "ข้อความต้นฉบับถึง AI for Thai edge" in text
            assert "Pathumma / thaillm-8b" in text
        if path == "/downloads":
            for link in (
                RELEASE_PAGE,
                *(RELEASE_ASSET_BASE + name for name in RELEASE_ASSETS),
            ):
                assert f'href="{link}"' in text, link
            assert "เตรียมส่งตรวจสอบ" in text
            assert "ยังไม่เผยแพร่" in text
            assert "SHA256SUMS" in text
            assert "gh attestation verify" in text
            assert 'data-recommended="true"' in text
            assert "Verify this file · ตรวจ SHA-256 และ provenance" in text
            assert "เผยแพร่ 14 ส.ค. 2569" in text
            for digest in RELEASE_ASSET_SHA256:
                assert digest in text
            assert "ข้อความดิบเข้า DOM ของเว็บไซต์ AI" in text
            assert "Side Panel เป็นขอบเขตที่แข็งแรงกว่า" in text
            assert "chrome.google.com/webstore/detail" not in text
            assert "chromewebstore.google.com/detail" not in text

    for path, (content_type, prefix, expected_sha256) in STATIC_ASSETS.items():
        status, headers, body = fetch(HTTPS + path)
        assert status == 200, (path, status)
        assert headers.get("Content-Type", "").lower().startswith(content_type), path
        assert body.startswith(prefix), path
        assert headers.get("Cache-Control") == "no-store", path
        if expected_sha256 is not None:
            assert hashlib.sha256(body).hexdigest() == expected_sha256, path

    status, headers, body = fetch(HTTPS + "/api/health")
    assert status == 200
    health = json.loads(body)
    assert health.get("status") == "ok"
    assert health.get("version") == "3.0.0"
    assert headers.get("Strict-Transport-Security") == "max-age=31536000"

    for path in LEGACY_DENIALS:
        status, headers, _body = fetch(HTTPS + path)
        assert status == 404, (path, status)
        assert headers.get("Strict-Transport-Security") == "max-age=31536000", path

    status, _headers, body = fetch(HTTPS + "/not-a-product-page")
    assert status == 404
    branded_404 = body.decode("utf-8")
    assert "หลงทาง" in branded_404
    assert "AI Guard" in branded_404
    for href in ('href="/"', 'href="/app"', 'href="/downloads"', 'href="/help"'):
        assert href in branded_404, href
    status, _headers, body = fetch(HTTPS + "/assets/ai-guard-mark.svgx")
    assert status == 404
    assert b"<!doctype html>" not in body.lower()
    for path in (
        "/app.html",
        "/privacy.html",
        "/terms.html",
        "/help.html",
        "/downloads.html",
        "/home.jsx",
        "/product.cssx",
        "/unknown.js",
        "/app.js",
    ):
        status, _headers, body = fetch(HTTPS + path)
        assert status == 404, (path, status)
        assert b"<!doctype html>" not in body.lower(), path
    status, headers, body = fetch(HTTPS + "/api/auth/session")
    assert status == 401
    assert headers.get("Content-Type", "").lower().startswith("application/json")
    assert json.loads(body) == {"error": {"code": "authentication_required"}}
    assert b"<!doctype html>" not in body.lower()

    print(
        "public web acceptance ok: HTTPS valid TLS/HSTS, product/docs surfaces, "
        f"health, {len(LEGACY_DENIALS)} exact legacy 404s; "
        f"external_http_warnings={len(warnings)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

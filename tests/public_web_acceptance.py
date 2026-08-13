#!/usr/bin/env python3
"""Credential-free acceptance for the real AI for Thai public edge."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

HTTPS = "https://team08.aiforthai.in.th"
HTTP = "http://team08.aiforthai.in.th"


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
        headers={"User-Agent": "aiguard-public-acceptance/2.5"},
        method="GET",
    )
    try:
        with OPENER.open(request, timeout=20) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def main() -> int:
    for path in ("/?sentinel=must-not-reflect", "/api/health?sentinel=must-not-reflect"):
        status, headers, body = fetch(HTTP + path)
        expected = HTTPS + path.split("?", 1)[0]
        assert status == 308, (path, status)
        assert headers.get("Location") == expected, (path, headers.get("Location"))
        assert b"AI Guard" not in body

    pages = {
        "/": "ใช้ AI Guard บนเว็บ",
        "/privacy": "ความเป็นส่วนตัวและความปลอดภัย",
        "/terms": "ข้อกำหนดและการใช้งานที่ยอมรับได้",
        "/help": "ช่วยเหลือและคำถามที่พบบ่อย",
        "/downloads": "ยังไม่มี Store listing",
        "/robots.txt": "Disallow: /api/",
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
        assert "http://" not in text, path

    status, headers, body = fetch(HTTPS + "/api/health")
    assert status == 200
    health = json.loads(body)
    assert health.get("status") == "ok"
    assert health.get("version") == "2.5.0"
    assert headers.get("Strict-Transport-Security") == "max-age=31536000"

    for path in (
        "/not-a-product-page",
        "/api/redact-pdf",
        "/api/v1/redact-pdf",
        "/api/openapi.json",
    ):
        status, _headers, _body = fetch(HTTPS + path)
        assert status == 404, (path, status)

    print(
        "public web acceptance ok: TLS-only edge, product/docs surfaces, headers, "
        "health, exact 404s, PDF/OCR denied"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

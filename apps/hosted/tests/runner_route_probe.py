"""Bounded post-build probe for the public PDPA report route.

The first hosted release intentionally excludes public PDF redaction/OCR. This
probe runs inside the core container and uses synthetic PII only.
"""

from __future__ import annotations

import base64
import os
import time
from http.cookies import SimpleCookie

import httpx

API = os.environ.get("AIFT_PROBE_API", "http://api:8000")
PUBLIC_HOST = "team08.aiforthai.in.th"
SYNTHETIC_TEXT = "ผมชื่อ นายสมชาย ใจดี โทร 081-234-5678 ครับ"


class ProbeFailure(RuntimeError):
    """A fixed route assertion failed."""


def _cookie_header(client: httpx.Client) -> str:
    access_code = os.environ.get("AIFT_ACCESS_CODE")
    if not access_code:
        raise ProbeFailure("caller auth configuration missing")
    response = client.post(
        "/auth/login", json={"access_code": access_code}, headers={"Host": PUBLIC_HOST}
    )
    access_code = None
    if response.status_code != 204:
        raise ProbeFailure("caller login failed")
    parsed = SimpleCookie()
    parsed.load(response.headers.get("set-cookie", ""))
    morsel = parsed.get("__Host-aift_session")
    if morsel is None:
        raise ProbeFailure("caller cookie missing")
    return f"__Host-aift_session={morsel.value}"


def _check_report(client: httpx.Client, headers: dict[str, str]) -> float:
    started = time.monotonic()
    response = client.post(
        "/analyze-report", json={"text": SYNTHETIC_TEXT}, headers=headers
    )
    if response.status_code != 200:
        raise ProbeFailure("PDPA report route failed")
    payload = response.json()
    try:
        report = base64.b64decode(payload["report_pdf_b64"], validate=True)
    except Exception as error:
        raise ProbeFailure("PDPA report response invalid") from error
    if not (
        report.startswith(b"%PDF-")
        and len(report) >= 1_000
        and SYNTHETIC_TEXT not in str(payload)
        and isinstance(payload.get("overall_score"), (int, float))
        and payload.get("overall_grade")
    ):
        raise ProbeFailure("PDPA report evidence incomplete")
    return time.monotonic() - started


def main() -> int:
    try:
        with httpx.Client(base_url=API, timeout=90, trust_env=False) as client:
            cookie = _cookie_header(client)
            headers = {"Host": PUBLIC_HOST, "Cookie": cookie}
            report_seconds = _check_report(client, headers)
            response = client.post("/auth/logout", headers=headers)
            if response.status_code != 204:
                raise ProbeFailure("caller logout failed")
        print(f"runner route probe passed: report_seconds={report_seconds:.1f}")
        return 0
    except ProbeFailure as error:
        print(f"runner route probe failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded post-build probes for the report and one-page scanned-PDF routes.

This file is copied into the running core container by the GitLab acceptance
job. It uses only synthetic PII and prints fixed, value-free results.
"""

from __future__ import annotations

import base64
import io
import os
import time
from http.cookies import SimpleCookie
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

API = os.environ.get("AIFT_PROBE_API", "http://api:8000")
PUBLIC_HOST = "team08.aiforthai.in.th"
SYNTHETIC_TEXT = "ผมชื่อ นายสมชาย ใจดี โทร 081-234-5678 ครับ"
FONT = Path("/app/pii_redactor/fonts/IBMPlexSansThaiLooped-Regular.ttf")


class ProbeFailure(RuntimeError):
    """A fixed route assertion failed."""


def _cookie_header(client: httpx.Client) -> str:
    access_code = os.environ.get("AIFT_ACCESS_CODE")
    if not access_code:
        raise ProbeFailure("caller auth configuration missing")
    response = client.post(
        "/auth/login",
        json={"access_code": access_code},
        headers={"Host": PUBLIC_HOST},
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


def _scanned_pdf() -> bytes:
    if not FONT.is_file():
        raise ProbeFailure("bundled Thai font missing")
    image = Image.new("RGB", (1400, 300), "white")
    font = ImageFont.truetype(str(FONT), 40)
    ImageDraw.Draw(image).text((50, 100), SYNTHETIC_TEXT, fill="black", font=font)
    output = io.BytesIO()
    document = canvas.Canvas(output, pagesize=A4)
    document.drawImage(ImageReader(image), 40, 500, width=500, height=110)
    document.showPage()
    document.save()
    return output.getvalue()


def _has_new_solid_redaction_band(original_pdf: bytes, encoded_png: str) -> bool:
    import pypdfium2 as pdfium

    try:
        after = Image.open(io.BytesIO(base64.b64decode(encoded_png))).convert("L")
        document = pdfium.PdfDocument(original_pdf)
        try:
            page = document[0]
            try:
                before = page.render(scale=2.0).to_pil().convert("L")
            finally:
                page.close()
        finally:
            document.close()
    except Exception:
        return False
    if before.size != after.size:
        return False
    minimum_run = max(20, after.width // 80)
    qualifying_rows: list[int] = []
    for y in range(after.height):
        current = 0
        qualifies = False
        for x in range(after.width):
            newly_black = (
                after.getpixel((x, y)) <= 24 and before.getpixel((x, y)) >= 192
            )
            if newly_black:
                current += 1
            else:
                if current >= minimum_run:
                    qualifies = True
                    break
                current = 0
        if qualifies or current >= minimum_run:
            qualifying_rows.append(y)
    streak = 0
    previous = -2
    for row in qualifying_rows:
        streak = streak + 1 if row == previous + 1 else 1
        if streak >= 6:
            return True
        previous = row
    return False


def _check_report(client: httpx.Client, headers: dict[str, str]) -> float:
    started = time.monotonic()
    response = client.post(
        "/analyze-report",
        json={"text": SYNTHETIC_TEXT},
        headers=headers,
    )
    try:
        payload = response.json()
        report = base64.b64decode(payload["report_pdf_b64"], validate=True)
    except Exception as error:
        raise ProbeFailure("report response invalid") from error
    pdf_ok = report.startswith(b"%PDF-")
    size_ok = len(report) >= 500
    source_absent = SYNTHETIC_TEXT.encode("utf-8") not in report
    score_ok = (
        isinstance(payload.get("overall_score"), int | float)
        and 0 <= payload["overall_score"] <= 100
        and payload.get("overall_grade") in {"A", "B", "C", "D", "F"}
    )
    if response.status_code != 200 or not all(
        (pdf_ok, size_ok, source_absent, score_ok)
    ):
        raise ProbeFailure(
            "report route failed "
            f"(status={response.status_code}, pdf={pdf_ok}, size={size_ok}, "
            f"source_absent={source_absent}, score={score_ok})"
        )
    return time.monotonic() - started


def _check_scanned_pdf(client: httpx.Client, headers: dict[str, str]) -> float:
    original_pdf = _scanned_pdf()
    started = time.monotonic()
    response = client.post(
        "/redact-pdf",
        files={"pdf_file": ("synthetic-scan.pdf", original_pdf, "application/pdf")},
        headers=headers,
        timeout=360,
    )
    if response.status_code != 200:
        raise ProbeFailure("scanned PDF route failed")
    try:
        payload = response.json()
        redacted = base64.b64decode(payload["redacted_pdf_b64"], validate=True)
    except Exception as error:
        raise ProbeFailure("scanned PDF response invalid") from error
    source_ok = payload.get("source_type") in {"pdf_text", "pdf_hybrid"}
    entity_ok = payload.get("detected_entity_count", 0) >= 2
    pdf_ok = len(redacted) >= 500
    bands_ok = _has_new_solid_redaction_band(
        original_pdf, payload.get("after_png_b64", "")
    )
    if not all((source_ok, entity_ok, pdf_ok, bands_ok)):
        raise ProbeFailure(
            "scanned PDF evidence incomplete "
            f"(source={source_ok}, entities={entity_ok}, pdf={pdf_ok}, "
            f"bands={bands_ok})"
        )
    return time.monotonic() - started


def main() -> int:
    try:
        with httpx.Client(base_url=API, timeout=90) as client:
            cookie = _cookie_header(client)
            headers = {"Host": PUBLIC_HOST, "Cookie": cookie}
            report_seconds = _check_report(client, headers)
            scanned_pdf_seconds = _check_scanned_pdf(client, headers)
        print(
            "runner route probe passed: report and one-page scanned PDF "
            f"(report_seconds={report_seconds:.1f}, "
            f"scanned_pdf_seconds={scanned_pdf_seconds:.1f})"
        )
        return 0
    except ProbeFailure as error:
        print(f"runner route probe failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Checklist ก-ฌ smoke harness against the running local stack.

Prereq:  APP_AIGUARD_API_KEY set, stack up via
         `docker compose -p team08 up -d --build`
Usage:   python tests/smoke.py            # ก ค ง จ ฉ + (ข ฌ if key/OCR ready)
         python tests/smoke.py --soak     # ซ: 8 concurrent x 10 min + restart

Writes tests/out/smoke-<ts>.json — the phase's evidence file. Synthetic PII
only. Failure modes check (ช) is manual by design (requires recreating the
stack without keys); steps are printed at the end.
"""

from __future__ import annotations

import base64
import concurrent.futures
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

API = "http://127.0.0.1:20071"
WEB = "http://127.0.0.1:20070"
NAME, PHONE = "นายสมชาย ใจดี", "081-234-5678"
SYN_TEXT = f"ผมชื่อ {NAME} โทร {PHONE} ครับ"
OUT = Path(__file__).parent / "out"
RESULTS: list[dict] = []


def record(check: str, ok: bool, detail: dict | str = ""):
    RESULTS.append({"check": check, "ok": ok, "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {check}  {detail if not ok else ''}")


def check_a_health():
    r = httpx.get(f"{API}/health", timeout=10)
    st = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", "team08-api-1"],
        capture_output=True, text=True,
    ).stdout.strip()
    record("ก.health", r.status_code == 200 and st == "healthy",
           {"http": r.status_code, "container": st})


def check_b_roundtrip_real():
    r = httpx.post(f"{API}/v1/roundtrip",
                   json={"text": SYN_TEXT, "mode": "token", "provider": "tokenmind"},
                   timeout=120)
    if r.status_code == 503:
        record("ข.roundtrip", False, "503 — TOKENMIND key not configured in stack")
        return
    body = r.json()
    san = body.get("sanitized_text", "")
    digits = re.sub(r"\D", "", PHONE)
    ok = (
        r.status_code == 200
        and body.get("provider_used") == "tokenmind"
        and digits not in re.sub(r"\D", "", san)
        and "สมชาย" not in san
        and PHONE in body.get("restored_text", "")
    )
    record("ข.roundtrip", ok, {"status": r.status_code, "warnings": body.get("warnings", [])})


def check_c_noquery_log():
    marker = "SECRETQUERYMARKER"
    httpx.get(f"{API}/health", params={"q": marker}, timeout=10)
    time.sleep(1)
    logs = subprocess.run(
        ["docker", "logs", "team08-api-1", "--tail", "50"],
        capture_output=True, text=True,
    )
    blob = logs.stdout + logs.stderr
    record("ค.noquery_log", marker not in blob and "/health" in blob,
           {"marker_leaked": marker in blob})


def check_d_allowlist():
    bad = {}
    for path in ("/sanitize", "/reidentify", "/docs", "/openapi.json", "/api/sanitize"):
        code = httpx.post(f"{API}{path}", json={"text": "x"}, timeout=10).status_code \
            if path != "/docs" and path != "/openapi.json" \
            else httpx.get(f"{API}{path}", timeout=10).status_code
        if code != 404:
            bad[path] = code
    record("ง.allowlist_404", not bad, bad)


def check_e_webpage():
    r = httpx.get(f"{WEB}/", timeout=10)
    ok = r.status_code == 200 and all(
        key in r.text for key in ("roundtrip", "redact-pdf", "analyze-report")
    )
    record("จ.webpage", ok, {"status": r.status_code, "bytes": len(r.content)})


def check_f_checkstage():
    # same logic as .gitlab-ci.yml check: run the vendored-integrity check here;
    # the shell grep rules run for real on GitLab (bash/alpine)
    p = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "sync" / "sync_from_upstream.py"),
         "--check"],
        capture_output=True, text=True,
    )
    record("ฉ.vendored_check", p.returncode == 0, p.stderr[-300:] if p.returncode else "")


def _scanned_pdf() -> bytes:
    """A PDF whose only content is a rendered IMAGE of Thai text (no text layer)."""
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    font = None
    for cand in (r"C:\Windows\Fonts\LeelawUI.ttf", r"C:\Windows\Fonts\tahoma.ttf"):
        if Path(cand).exists():
            font = ImageFont.truetype(cand, 40)
            break
    img = Image.new("RGB", (1400, 300), "white")
    ImageDraw.Draw(img).text((50, 100), SYN_TEXT, fill="black", font=font)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawImage(ImageReader(img), 40, 500, width=500, height=110)
    c.showPage()
    c.save()
    return buf.getvalue()


def check_i_ocr():
    t0 = time.monotonic()
    r = httpx.post(f"{API}/v1/redact-pdf",
                   files={"pdf_file": ("scan.pdf", _scanned_pdf(), "application/pdf")},
                   timeout=360)
    took = round(time.monotonic() - t0, 1)
    if r.status_code != 200:
        record("ฌ.ocr", False, {"status": r.status_code, "detail": r.text[:200], "s": took})
        return
    body = r.json()
    got_pdf = len(base64.b64decode(body.get("redacted_pdf_b64", ""))) > 500
    ok = body.get("source_type") in ("pdf_scanned", "pdf_hybrid") and got_pdf
    record("ฌ.ocr", ok, {
        "source_type": body.get("source_type"),
        "entities": body.get("entity_count"),
        "ocr_confidence": body.get("ocr_confidence"),
        "human_review": body.get("human_review"),
        "seconds": took,
    })


def soak():
    """ซ: 8 concurrent roundtrips for 10 minutes, then restart-recovery."""
    stop_at = time.monotonic() + 600
    counts = {"ok": 0, "s429": 0, "s5xx": 0, "s503": 0, "err": 0}

    def worker():
        while time.monotonic() < stop_at:
            try:
                r = httpx.post(f"{API}/v1/roundtrip",
                               json={"text": SYN_TEXT, "mode": "token",
                                     "provider": "tokenmind"}, timeout=120)
                if r.status_code == 200:
                    counts["ok"] += 1
                elif r.status_code == 429:
                    counts["s429"] += 1
                elif r.status_code == 503:
                    counts["s503"] += 1
                elif r.status_code >= 500:
                    counts["s5xx"] += 1
            except Exception:
                counts["err"] += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda _: worker(), range(8)))
    record("ซ.soak", counts["s5xx"] == 0 and counts["ok"] > 0, counts)

    subprocess.run(["docker", "compose", "-p", "team08", "restart"], capture_output=True)
    deadline = time.monotonic() + 180
    healthy = False
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{API}/health", timeout=5).status_code == 200:
                healthy = True
                break
        except Exception:
            pass
        time.sleep(5)
    record("ซ.restart_recovery", healthy, "")


def main():
    OUT.mkdir(exist_ok=True)
    if "--soak" in sys.argv:
        soak()
    else:
        check_a_health()
        check_b_roundtrip_real()
        check_c_noquery_log()
        check_d_allowlist()
        check_e_webpage()
        check_f_checkstage()
        check_i_ocr()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"smoke-{ts}.json"
    path.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nevidence: {path}")
    print("\nช (manual): 1) unset APP_AIGUARD_API_KEY -> `docker compose config` "
          "must fail loud  2) recreate stack without APP_TOKENMIND_API_KEY -> "
          "/v1/roundtrip must answer 503 with a clear detail")
    sys.exit(0 if all(r["ok"] for r in RESULTS) else 1)


if __name__ == "__main__":
    main()

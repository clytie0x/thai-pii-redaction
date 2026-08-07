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
AUTH_COOKIE = ""


def record(check: str, ok: bool, detail: dict | str = ""):
    RESULTS.append({"check": check, "ok": ok, "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}  {check}  {detail if not ok else ''}")


def check_a_health():
    r = httpx.get(f"{API}/health", timeout=10)
    st = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Health.Status}}", "team08-api-1"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    record(
        "ก.health",
        r.status_code == 200 and st == "healthy",
        {"http": r.status_code, "container": st},
    )


def check_auth():
    global AUTH_COOKIE
    code = os.environ.get("APP_AIFT_ACCESS_CODE", "")
    if not code:
        record("ก.auth", False, "APP_AIFT_ACCESS_CODE is not configured")
        return
    r = httpx.post(
        f"{API}/v1/auth/login",
        json={"access_code": code},
        timeout=10,
    )
    code = ""
    cookie = r.headers.get("set-cookie", "").split(";", 1)[0]
    ok = (
        r.status_code == 204
        and cookie.startswith("__Host-aift_session=")
        and "HttpOnly" in r.headers.get("set-cookie", "")
        and "Secure" in r.headers.get("set-cookie", "")
        and "SameSite=Strict" in r.headers.get("set-cookie", "")
    )
    AUTH_COOKIE = cookie if ok else ""
    record("ก.auth", ok, {"status": r.status_code})


def auth_headers() -> dict[str, str]:
    return {"Cookie": AUTH_COOKIE} if AUTH_COOKIE else {}


def check_b_roundtrip_real():
    r = httpx.post(
        f"{API}/v1/roundtrip",
        json={"text": SYN_TEXT, "mode": "token", "provider": "tokenmind"},
        headers=auth_headers(),
        timeout=120,
    )
    if r.status_code == 503:
        record("ข.roundtrip", False, "503 — TOKENMIND key not configured in stack")
        return
    body = r.json()
    san = body.get("sanitized_text", "")
    restored = body.get("restored_text", "")
    digits = re.sub(r"\D", "", PHONE)
    current_token = re.compile(r"\[[^\]\r\n]+_[a-f]{25}_[a-z]{20}_[1-9][0-9]*\]")
    restoration = body.get("restoration", {})
    restore_observed = restoration.get("replaced_count", 0) > 0
    restored_when_observed = not restore_observed or (
        restored != body.get("ai_response_masked")
        and (NAME in restored or PHONE in restored)
    )
    ok = (
        r.status_code == 200
        and body.get("provider_used") == "tokenmind"
        and digits not in re.sub(r"\D", "", san)
        and "สมชาย" not in san
        and restored_when_observed
        and current_token.search(restored) is None
        and body.get("detected_entity_count", 0) >= 2
        and body.get("safety") == {"status": "pass", "residual_count": 0}
        and restoration.get("status") == "complete"
        and restoration.get("leftover_count") == 0
        and not ({"mapping", "entities", "highlights"} & set(body))
    )
    record(
        "ข.roundtrip",
        ok,
        {
            "status": r.status_code,
            "warnings": body.get("warnings", []),
            "restore_observed": restore_observed,
        },
    )


def check_c_request_target_log():
    marker = "SECRETREQUESTTARGETMARKER"
    before = subprocess.run(
        ["docker", "compose", "-p", "team08", "logs", "--no-color", "--tail", "300"],
        capture_output=True,
        text=True,
    )
    before_lines = len((before.stdout + before.stderr).splitlines())
    httpx.get(f"{API}/{marker}", params={"q": marker}, timeout=10)
    httpx.get(
        f"{API}/v1/auth/session",
        params={"q": marker},
        headers=auth_headers(),
        timeout=10,
    )
    httpx.get(f"{WEB}/{marker}", params={"q": marker}, timeout=10)
    time.sleep(1)
    logs = subprocess.run(
        ["docker", "compose", "-p", "team08", "logs", "--no-color", "--tail", "300"],
        capture_output=True,
        text=True,
    )
    blob = logs.stdout + logs.stderr
    secret_leaked = any(
        value and value in blob
        for name in (
            "APP_AIGUARD_API_KEY",
            "APP_TOKENMIND_API_KEY",
            "APP_AIFT_ACCESS_CODE",
            "APP_AIFT_COOKIE_SIGNING_KEY",
        )
        if (value := os.environ.get(name, ""))
    )
    record(
        "ค.request_target_log",
        (
            marker not in blob
            and not secret_leaked
            and len(blob.splitlines()) > before_lines
        ),
        {
            "marker_leaked": marker in blob,
            "secret_leaked": secret_leaked,
        },
    )


def check_d_allowlist():
    bad = {}
    for path in ("/sanitize", "/reidentify", "/docs", "/openapi.json", "/api/sanitize"):
        code = (
            httpx.post(f"{API}{path}", json={"text": "x"}, timeout=10).status_code
            if path != "/docs" and path != "/openapi.json"
            else httpx.get(f"{API}{path}", timeout=10).status_code
        )
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
        [
            sys.executable,
            str(Path(__file__).parent.parent / "sync" / "sync_from_upstream.py"),
            "--check",
        ],
        capture_output=True,
        text=True,
    )
    record(
        "ฉ.vendored_check", p.returncode == 0, p.stderr[-300:] if p.returncode else ""
    )


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


def _has_new_solid_redaction_band(original_pdf: bytes, png_b64: str) -> bool:
    """Require a newly painted opaque area, not only a PDF-shaped payload."""
    import pypdfium2 as pdfium
    from PIL import Image

    try:
        after = Image.open(io.BytesIO(base64.b64decode(png_b64))).convert("L")
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


def check_i_ocr():
    t0 = time.monotonic()
    original_pdf = _scanned_pdf()
    r = httpx.post(
        f"{API}/v1/redact-pdf",
        files={"pdf_file": ("scan.pdf", original_pdf, "application/pdf")},
        headers=auth_headers(),
        timeout=360,
    )
    took = round(time.monotonic() - t0, 1)
    if r.status_code != 200:
        record(
            "ฌ.ocr", False, {"status": r.status_code, "detail": r.text[:200], "s": took}
        )
        return
    body = r.json()
    got_pdf = len(base64.b64decode(body.get("redacted_pdf_b64", ""))) > 500
    got_entities = body.get("detected_entity_count", 0) >= 2
    ok = (
        body.get("source_type") in ("pdf_text", "pdf_hybrid")
        and got_pdf
        and got_entities
        and _has_new_solid_redaction_band(original_pdf, body.get("after_png_b64", ""))
    )
    record(
        "ฌ.ocr",
        ok,
        {
            "source_type": body.get("source_type"),
            "entities": body.get("detected_entity_count"),
            "ocr_confidence": body.get("ocr_confidence"),
            "human_review": body.get("human_review"),
            "seconds": took,
        },
    )


def soak():
    """ซ: N concurrent roundtrips for M seconds, then restart-recovery.

    Env knobs (defaults preserve the 8-worker / 10-minute / always-restart
    behavior): SOAK_WORKERS, SOAK_SECONDS, SOAK_PROVIDER, and SOAK_SKIP_RESTART=1
    to skip the restart leg — used by the light real-provider pass, since the
    main fake pass already exercises restart recovery and re-running it against
    the organizer gateway wastes real LLM calls.
    """
    workers = int(os.environ.get("SOAK_WORKERS", "8"))
    seconds = int(os.environ.get("SOAK_SECONDS", "600"))
    provider = os.environ.get("SOAK_PROVIDER", "tokenmind")
    stop_at = time.monotonic() + seconds
    counts = {
        "ok": 0,
        "s429": 0,
        "s4xx": 0,
        "s5xx": 0,
        "s503": 0,
        "err": 0,
    }

    def worker():
        while time.monotonic() < stop_at:
            try:
                r = httpx.post(
                    f"{API}/v1/roundtrip",
                    json={"text": SYN_TEXT, "mode": "token", "provider": provider},
                    headers=auth_headers(),
                    timeout=120,
                )
                if r.status_code == 200:
                    counts["ok"] += 1
                elif r.status_code == 429:
                    counts["s429"] += 1
                elif r.status_code == 503:
                    counts["s503"] += 1
                elif r.status_code >= 500:
                    counts["s5xx"] += 1
                elif r.status_code >= 400:
                    counts["s4xx"] += 1
            except Exception:
                counts["err"] += 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda _: worker(), range(workers)))
    detail = {**counts, "provider": provider, "workers": workers, "seconds": seconds}
    record(
        f"ซ.soak[{provider},{workers}w,{seconds}s]",
        (
            counts["ok"] > 0
            and counts["s4xx"] == 0
            and counts["s5xx"] == 0
            and counts["s503"] == 0
            and counts["err"] == 0
        ),
        detail,
    )

    if os.environ.get("SOAK_SKIP_RESTART") == "1":
        return
    subprocess.run(
        ["docker", "compose", "-p", "team08", "restart"], capture_output=True
    )
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
        check_auth()
        soak()
    else:
        check_a_health()
        check_auth()
        check_b_roundtrip_real()
        check_c_request_target_log()
        check_d_allowlist()
        check_e_webpage()
        check_f_checkstage()
        check_i_ocr()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"smoke-{ts}.json"
    path.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nevidence: {path}")
    print(
        "\nช (manual): 1) unset any required APP_AIGUARD/API auth secret -> "
        "`docker compose config` must fail loud  2) recreate stack without "
        "APP_TOKENMIND_API_KEY -> authenticated /v1/roundtrip must answer "
        "a fixed provider-configuration error"
    )
    sys.exit(0 if all(r["ok"] for r in RESULTS) else 1)


if __name__ == "__main__":
    main()

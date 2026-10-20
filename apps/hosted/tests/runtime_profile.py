"""Aggregate-only local detect latency probe for the rebuilt AIFT stack."""

from __future__ import annotations

import json
import math
import os
import time
from http.cookies import SimpleCookie

import httpx

API = os.environ.get("AIFT_PROBE_API", "http://api:8000")
PUBLIC_HOST = "team08.aiforthai.in.th"
SYNTHETIC_TEXT = "ผมชื่อ นายสมชาย ใจดี โทร 081-234-5678 ครับ"
WARMUPS = 5
REQUESTS = 100
MIN_INTERVAL_SECONDS = 0.11


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _cookie_header(client: httpx.Client) -> str:
    access_code = os.environ.get("AIFT_ACCESS_CODE")
    if not access_code:
        raise RuntimeError("caller auth configuration missing")
    response = client.post(
        "/auth/login",
        json={"access_code": access_code},
        headers={"Host": PUBLIC_HOST},
    )
    access_code = None
    if response.status_code != 204:
        raise RuntimeError("caller login failed")
    parsed = SimpleCookie()
    parsed.load(response.headers.get("set-cookie", ""))
    morsel = parsed.get("__Host-aift_session")
    if morsel is None:
        raise RuntimeError("caller cookie missing")
    return f"__Host-aift_session={morsel.value}"


def _detect(client: httpx.Client, headers: dict[str, str]) -> float:
    started = time.perf_counter()
    response = client.post("/detect", json={"text": SYNTHETIC_TEXT}, headers=headers)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if response.status_code != 200:
        raise RuntimeError("detect request failed")
    payload = response.json()
    if payload.get("detected_entity_count", 0) < 2:
        raise RuntimeError("detect result incomplete")
    return elapsed_ms


def main() -> int:
    try:
        with httpx.Client(base_url=API, timeout=30) as client:
            cookie = _cookie_header(client)
            headers = {"Host": PUBLIC_HOST, "Cookie": cookie}
            for _ in range(WARMUPS):
                _detect(client, headers)
                time.sleep(MIN_INTERVAL_SECONDS)
            latencies: list[float] = []
            for _ in range(REQUESTS):
                cycle_started = time.perf_counter()
                latencies.append(_detect(client, headers))
                remaining = MIN_INTERVAL_SECONDS - (time.perf_counter() - cycle_started)
                if remaining > 0:
                    time.sleep(remaining)
        print(
            json.dumps(
                {
                    "requests": REQUESTS,
                    "success": len(latencies),
                    "p50_ms": round(_percentile(latencies, 0.50), 2),
                    "p95_ms": round(_percentile(latencies, 0.95), 2),
                    "max_ms": round(max(latencies), 2),
                },
                separators=(",", ":"),
            )
        )
        return 0
    except Exception:
        print('{"error":"runtime profile failed"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

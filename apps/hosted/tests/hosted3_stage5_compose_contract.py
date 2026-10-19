#!/usr/bin/env python3
"""Caller-facing local four-service probe for the exact Stage 5 candidate.

Run only against the isolated local Compose override; it never touches the
deployed loopback ports or uses a provider credential. A missing provider key
is intentional evidence that the protected queue/claim path reaches the fixed
Core failure without any real provider mutation.
"""

from __future__ import annotations

import http.client
import json
import os
import sys
from http.cookies import SimpleCookie


BASE = os.environ.get("AIGUARD_STAGE5_API_BASE", "").rstrip("/")
PRIORITY_CODE = os.environ.get("AIGUARD_STAGE5_PRIORITY_CODE", "")


def request(path: str, *, method: str = "POST", payload: object | None = None, content_type: str = "application/json", cookie: str | None = None):
    if not BASE.startswith("http://"):
        raise AssertionError("AIGUARD_STAGE5_API_BASE must be an isolated local http URL")
    host_port = BASE.removeprefix("http://")
    host, port = host_port.rsplit(":", 1)
    body = None
    if payload is not None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Host": "team08.aiforthai.in.th"}
    if body is not None:
        headers["Content-Type"] = content_type
    if cookie:
        headers["Cookie"] = cookie
    connection = http.client.HTTPConnection(host, int(port), timeout=40)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, {key.lower(): value for key, value in response.getheaders()}, response.read()
    finally:
        connection.close()


def core_response(result: tuple[int, dict[str, str], bytes]) -> tuple[int, dict[str, str], bytes]:
    status, headers, body = result
    assert "cache-control" in headers and headers["cache-control"] == "no-store"
    assert "x-aiguard-server-time-ms" in headers, (status, body[:200])
    return result


def main() -> int:
    if not BASE:
        print("stage5 compose contract skipped: isolated local candidate is not running")
        return 0
    status, headers, body = core_response(request("/auth/guest", payload={}))
    assert status == 201
    set_cookie = SimpleCookie(headers["set-cookie"])
    cookie = "__Host-aift_guest=" + set_cookie["__Host-aift_guest"].value
    status, headers, _ = core_response(request("/auth/session", method="GET", cookie=cookie))
    assert status == 200 and headers["x-aiguard-service-class"] == "standard"

    # Duplicate authority names fail at the proxy before Core can select a
    # different SimpleCookie value or undertake any sensitive work.
    status, headers, _ = request(
        "/guard",
        payload={"text": "Synthetic duplicate cookie check"},
        cookie="__Host-aift_guest=attacker-controlled; " + cookie,
    )
    assert status == 400 and "x-aiguard-server-time-ms" not in headers

    status, _headers, body = core_response(request("/protection-preview", payload={"text": "Synthetic test@example.invalid", "mode": "token"}, cookie=cookie))
    assert status == 200
    ticket = json.loads(body)["ticket"]
    status, _headers, body = core_response(request("/provider-queue/join", payload={"ticket": ticket}, cookie=cookie))
    assert status == 201
    capability = json.loads(body)["queue_capability"]
    status, _headers, body = core_response(request("/provider-queue/claim", payload={"queue_capability": capability, "last_revision": 1}, cookie=cookie))
    assert status == 200
    claim = json.loads(body)["claim_token"]
    status, _headers, body = core_response(request("/protection-execute", payload={"text": "Synthetic test@example.invalid", "queue_capability": capability, "claim_token": claim}, cookie=cookie))
    assert status == 503 and json.loads(body)["error"]["code"] == "provider_configuration"

    status, _headers, _body = core_response(request("/guest/preview", payload={"scenario_id": "hr-resume-pdf-structured-v1"}, cookie=cookie))
    assert status == 200
    status, _headers, body = core_response(request("/document-preview", payload=b"not-a-pdf", content_type="application/pdf", cookie=cookie))
    assert status == 422 and json.loads(body)["error"]["code"] in {"document_unsupported", "pdf_text_layer_required"}

    # Status is a bodyless GET lane. Nginx rejects declared content before the
    # Core/status provider can run and therefore supplies no Core timing.
    status, headers, _ = request("/provider-queue/status", method="GET", payload=b"x", cookie=cookie)
    assert status == 413 and "x-aiguard-server-time-ms" not in headers

    # Every additive alias reaches the Core fixed schema path rather than the
    # Nginx fallback. Rate saturation is deliberately allowed here and proves
    # the counterpart: an edge-only 429 contains no forged Core time.
    aliases = (
        ("/v1/auth/guest", "POST", {}), ("/v1/guest/preview", "POST", {}),
        ("/v1/guest/execute", "POST", {}), ("/v1/protection-preview", "POST", {}),
        ("/v1/protection-execute", "POST", {}), ("/v1/document-preview", "POST", {}),
        ("/v1/document-execute", "POST", {}), ("/v1/provider-queue/join", "POST", {}),
        ("/v1/provider-queue/status", "GET", None), ("/v1/provider-queue/claim", "POST", {}),
        ("/v1/provider-queue/cancel", "POST", {}),
    )
    saw_edge_429 = False
    for path, method, payload in aliases:
        status, headers, body = request(path, method=method, payload=payload, cookie=cookie)
        assert status in {200, 201, 204, 400, 401, 403, 405, 409, 410, 413, 422, 429, 503}, (path, status)
        if status == 429:
            saw_edge_429 = True
            assert "x-aiguard-server-time-ms" not in headers
            assert json.loads(body)["error"]["code"] in {"rate_limited", "queue_rate_limited"}
        else:
            core_response((status, headers, body))
    assert saw_edge_429
    for denied in ("/v2/protection-preview", "/v3/provider-queue/status", "/protection-preview/x", "/redact-pdf", "/api/protection-preview"):
        status, headers, _ = request(denied, method="GET", cookie=cookie)
        assert status == 404 and "x-aiguard-server-time-ms" not in headers, denied
    if PRIORITY_CODE:
        priority_cookies = []
        for _ in range(2):
            status, headers, _ = request("/auth/login", payload={"access_code": PRIORITY_CODE})
            assert status == 204
            priority_cookies.append(
                "__Host-aift_session="
                + SimpleCookie(headers["set-cookie"])["__Host-aift_session"].value
            )
        priority_results = [
            request(
                "/guard",
                payload={"text": "Synthetic Priority subject quota check"},
                cookie=priority_cookies[index % 2],
            )
            for index in range(7)
        ]
        assert [result[0] for result in priority_results] == [200] * 6 + [429]
        assert json.loads(priority_results[-1][2])["error"]["code"] == "rate_limited"
    status, _headers, _body = request("/v1/auth/guest/end", payload={}, cookie=cookie)
    assert status == 204
    print("hosted3 stage5 compose contract ok: local four-service preview/queue/claim path, aliases, edge provenance, and exact denials")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, ValueError, http.client.HTTPException) as error:
        print(f"hosted3 stage5 compose contract failed: {error}", file=sys.stderr)
        raise SystemExit(1)

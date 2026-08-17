#!/usr/bin/env python3
"""Static Stage 5 contract for the exact local API candidate.

This complements the built-Nginx integration test: a route count alone could
false-pass a prefix location, so every exact location is also tied to its
approved upstream path, body lane, and error provenance.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/hosted3/contract.json").read_text("utf-8"))
NGINX = (ROOT / "api/default.conf.template").read_text("utf-8")


def block(path: str) -> str:
    match = re.search(rf"^  location = {re.escape(path)} \{{(?P<body>.*?)^  \}}", NGINX, re.M | re.S)
    assert match is not None, path
    return match.group("body")


def require_all(value: str, *needles: str) -> None:
    for needle in needles:
        assert needle in value, needle


def main() -> int:
    existing = FIXTURE["existing_canonical_routes"]
    additive = FIXTURE["additive_canonical_routes"]
    approved = existing + additive + [f"/v1{path}" for path in existing + additive]
    locations = re.findall(r"^  location = (/[^ {]+) \{", NGINX, re.M)
    assert locations == approved
    assert len(locations) == len(set(locations)) == 40

    declarations = re.findall(
        r"^\s*location\s+(?:(=|~\*|~|\^~)\s+)?([^\s{]+)\s*\{", NGINX, re.M
    )
    assert all(
        modifier == "="
        or (not modifier and (path in {"/", "/internal-health"} or path.startswith("@")))
        for modifier, path in declarations
    ), declarations

    # Every route is explicitly wired. Canonical and alias paths must remain
    # behavioural twins at the proxy, apart from their location name.
    protected = {
        "/guest/preview": "/api/guest/preview",
        "/guest/execute": "/api/guest/execute",
        "/protection-preview": "/api/protection-preview",
        "/protection-execute": "/api/protection-execute",
        "/document-preview": "/api/document-preview",
        "/document-execute": "/api/document-execute",
        "/provider-queue/join": "/api/provider-queue/join",
        "/provider-queue/status": "/api/provider-queue/status",
        "/provider-queue/claim": "/api/provider-queue/claim",
        "/provider-queue/cancel": "/api/provider-queue/cancel",
    }
    auth = {"/auth/guest": "/aift/auth/guest", "/auth/guest/end": "/aift/auth/guest/end"}
    for path, upstream in {**protected, **auth}.items():
        canonical = block(path)
        alias = block("/v1" + path)
        # Comments may explain an ownership boundary once; effective
        # directives must remain alias-identical.
        normalized_canonical = "\n".join(
            line.strip() for line in canonical.splitlines() if line.strip() and not line.lstrip().startswith("#")
        )
        normalized_alias = "\n".join(
            line.strip() for line in alias.splitlines() if line.strip() and not line.lstrip().startswith("#")
        )
        assert normalized_canonical == normalized_alias, path
        require_all(canonical, f"proxy_pass http://core:8000{upstream};")
        if path in protected:
            require_all(canonical, "proxy_intercept_errors off;", "error_page 413 = @error_payload_too_large;")
        else:
            require_all(canonical, 'proxy_set_header X-AIGuard-Key "";', 'proxy_set_header X-AIGuard-Contract-Version "";')

    for path in ("/guest/preview", "/protection-preview"):
        require_all(block(path), "client_max_body_size 96k;", "limit_req zone=standard_work burst=2 nodelay;", "limit_req zone=priority_work burst=5 nodelay;")
    for path in ("/guest/execute", "/protection-execute", "/document-execute"):
        require_all(block(path), "client_max_body_size 96k;", "limit_req zone=queue_execute_global burst=5 nodelay;", "limit_req zone=queue_execute_caller burst=1 nodelay;", "proxy_read_timeout 200s;")
    require_all(block("/document-preview"), "client_max_body_size 5m;", "proxy_request_buffering off;", "limit_req zone=document_global burst=1 nodelay;", "limit_req zone=standard_document burst=1 nodelay;", "limit_req zone=priority_document burst=1 nodelay;", "limit_conn document_global_conn 1;", "limit_conn standard_document_conn 1;", "limit_conn priority_document_conn 1;")
    require_all(block("/provider-queue/join"), "limit_req zone=queue_join_global burst=4 nodelay;", "error_page 429 = @error_queue_rate_limited;")
    require_all(block("/provider-queue/status"), "client_max_body_size 1;", "if ($aift_status_has_body = 1) { return 413; }", "if ($aift_status_has_transfer_encoding = 1) { return 413; }", "limit_req zone=queue_status_global burst=12 nodelay;", "limit_req zone=queue_status_caller burst=1 nodelay;")
    require_all(block("/provider-queue/claim"), "limit_req zone=queue_claim_global burst=12 nodelay;", "limit_req zone=queue_claim_caller burst=1 nodelay;", "limit_conn queue_claim_global_conn 16;", "limit_conn queue_claim_caller_conn 1;", "proxy_read_timeout 30s;")
    require_all(block("/provider-queue/cancel"), "limit_req zone=queue_cancel_global burst=5 nodelay;", "limit_req zone=queue_cancel_caller burst=1 nodelay;")
    require_all(block("/auth/guest"), "limit_req zone=standard_start_global burst=10 nodelay;", "limit_conn standard_start_global_conn 10;")

    for marker in (
        'location @error_payload_too_large',
        '"code":"payload_too_large"',
        'location @error_rate_limited',
        'location @error_queue_rate_limited',
        '"code":"queue_rate_limited"',
        "map $http_cookie $aift_standard_caller_key",
        "map $http_cookie $aift_priority_caller_key",
        "map $http_cookie $aift_duplicate_standard_cookie",
        "limit_req_zone  $server_name zone=document_global:1m rate=4r/m;",
        "limit_conn_zone $server_name zone=document_global_conn:1m;",
    ):
        assert marker in NGINX, marker
    assert "X-AIGuard-Server-Time-Ms" not in NGINX

    overlay = (ROOT / "core/aift_hosted3/overlay.py").read_text("utf-8")
    gateway = (ROOT / "core/aift_auth.py").read_text("utf-8")
    assert "HOSTED3_INTERNAL_PATHS" in overlay
    for internal in protected.values():
        assert internal in overlay, internal
    assert 'STANDARD_START_PATH = "/aift/auth/guest"' in gateway
    assert 'STANDARD_END_PATH = "/aift/auth/guest/end"' in gateway
    queue = (ROOT / "core/aift_hosted3/provider_queue.py").read_text("utf-8")
    for marker in (
        "STANDARD_QUEUE_JOIN_PER_MINUTE = 1",
        "STANDARD_QUEUE_JOIN_BURST = 1",
        "PRIORITY_QUEUE_JOIN_PER_MINUTE = 6",
        "PRIORITY_QUEUE_JOIN_BURST = 2",
        "STANDARD_IDLE_BORROW_SECONDS = 10",
        "_consume_join_rate_locked",
    ):
        assert marker in queue, marker
    rates = (ROOT / "core/aift_hosted3/rate_limit.py").read_text("utf-8")
    for marker in ('"work": {"standard": (6, 2), "priority": (30, 5)}', '"document": {"standard": (1, 1), "priority": (4, 1)}', '"status": {"standard": (6, 1), "priority": (6, 1)}', '"claim": {"standard": (3, 1), "priority": (3, 1)}', '"cancel": {"standard": (2, 1), "priority": (2, 1)}', '"execute": {"standard": (4, 1), "priority": (4, 1)}'):
        assert marker in rates, marker

    docs = (ROOT / "docs/production-web-redesign.md").read_text("utf-8")
    state = (ROOT / "STATE.md").read_text("utf-8")
    assert "HOSTED3_IMPLEMENTATION_STAGE=stage9_postdeploy_fix" in docs
    assert "Production is Hosted `3.0.0` with exactly 40 public locations" in state
    assert (ROOT / "core/VERSION").read_text("utf-8").strip() == "3.0.0"
    print("hosted3 stage5 contract ok: exact 40-route proxy/core matrix and bounded edge lanes retained for Hosted 3.0.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

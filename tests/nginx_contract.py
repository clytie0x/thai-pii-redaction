#!/usr/bin/env python3
"""Pin the `api` proxy's contract, in the check stage, before anything deploys.

The proxy is the whole security boundary of this deployment. It re-adds the
`/api` prefix the platform strips, it decides which of the core's routes exist
at all, and it holds the service key so the frontend never has to. A one-line
mistake in `api/default.conf.template` re-exposes `/api/sanitize` — the
stateful, vault-bearing route this deployment deliberately does not offer —
and nothing else in the pipeline would notice.

So this runs against the REAL `api/Dockerfile`, not a copy of its config, with
a stub standing in for `core`. The stub answers 200 everywhere and echoes back
the path it was asked for and the key header it received, which is what makes
the interesting distinction testable: a 404 because the proxy refused, versus
a 404 that came back from core after the request got through.

The same check pins the hosted wording statically, builds the exact web image,
runs `nginx -t`, sends a request-target marker through it, and verifies that
the runtime access row exists without recording that marker.

Constraints this file lives under:

- The runner is `docker:27.3.1` with a bare `python3` from `apk add`. No venv,
  no httpx, no pytest. Standard library only, and a non-zero exit on failure.
- Names and ports are prefixed so a run can never collide with the deployed
  `team08` stack, and every container, network and image is removed in a
  `finally` even when an assertion fails mid-way.

Usage: python3 tests/nginx_contract.py
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CI_JOB_ID = os.environ.get("CI_JOB_ID", "").strip()
RUN_ID = f"ci-{CI_JOB_ID}" if CI_JOB_ID else f"local-{uuid.uuid4().hex[:12]}"
PREFIX = f"aiguard-contract-{RUN_ID}"
NETWORK = f"{PREFIX}-net"
STUB = f"{PREFIX}-stub"
PROXY = f"{PREFIX}-api"
WEB = f"{PREFIX}-web"
STUB_IMAGE = f"aiguard-contract-stub:{RUN_ID}"
PROXY_IMAGE = f"aiguard-contract-api:{RUN_ID}"
WEB_IMAGE = f"aiguard-contract-web:{RUN_ID}"

# Docker assigns ephemeral loopback ports so concurrent branch checks cannot
# tear down or exercise another job's candidate.
BASE = ""
WEB_BASE = ""
CONNECT_HOST = os.environ.get("AIFT_CONTRACT_CONNECT_HOST", "127.0.0.1")

TEST_KEY = "contract-test-key-not-a-real-secret"
REQUEST_TARGET_MARKER = "SECRET_MARKER_9f3a1c"

# The proxy rate-limits at 10r/s with burst 10. Pacing below that keeps a
# failure here meaning "the contract is wrong", never "the test was too fast".
PACE_SECONDS = 0.15

ENDPOINTS = ["health", "detect", "guard", "roundtrip", "analyze-report"]
AUTH_ENDPOINTS = ("login", "logout", "session")
PUBLIC_ROUTE_COUNT = 16

# Paths that must not exist on this deployment. The first four are the routes
# the core really serves and this deployment withholds; /api/health catches a
# proxy that forwards its own prefix; the last two catch prefix-matching where
# only exact matching is allowed.
DENIED = [
    "/sanitize",
    "/reidentify",
    "/docs",
    "/openapi.json",
    "/api/health",
    "/detectx",
    "/v1/sanitize",
    "/auth/unknown",
    "/v1/auth/unknown",
    "/redact-pdf",
    "/v1/redact-pdf",
]


class ContractFailure(Exception):
    pass


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise ContractFailure(f"{' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def published_base(container: str, target: int) -> str:
    row = run("docker", "port", container, f"{target}/tcp").strip().splitlines()
    if len(row) != 1 or ":" not in row[0]:
        raise ContractFailure(f"could not resolve the published port for {container}")
    host, port = row[0].rsplit(":", 1)
    if host != "127.0.0.1" or not port.isdigit():
        raise ContractFailure(f"{container} did not publish on loopback")
    if CONNECT_HOST not in {"127.0.0.1", "host.docker.internal"}:
        raise ContractFailure("unsupported contract-test connect host")
    return f"http://{CONNECT_HOST}:{port}"


def get(path: str) -> tuple[int, dict[str, str], str]:
    """GET `path`, returning (status, headers, body) for 404s as well as 200s."""
    time.sleep(PACE_SECONDS)
    request = urllib.request.Request(BASE + path, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return (
                response.status,
                dict(response.headers),
                response.read().decode("utf-8"),
            )
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def web_get(path: str) -> tuple[int, str]:
    request = urllib.request.Request(WEB_BASE + path, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def stub_log_lines() -> int:
    return len([ln for ln in run("docker", "logs", STUB).splitlines() if ln.strip()])


def teardown() -> None:
    run("docker", "rm", "-f", STUB, PROXY, WEB, check=False)
    run("docker", "network", "rm", NETWORK, check=False)
    run(
        "docker",
        "image",
        "rm",
        "-f",
        STUB_IMAGE,
        PROXY_IMAGE,
        WEB_IMAGE,
        check=False,
    )


def setup() -> None:
    global BASE, WEB_BASE
    teardown()  # a previous run that died hard must not poison this one
    run("docker", "build", "-q", "-t", STUB_IMAGE, str(REPO / "tests" / "stub-core"))
    run("docker", "build", "-q", "-t", PROXY_IMAGE, str(REPO / "api"))
    run("docker", "build", "-q", "-t", WEB_IMAGE, str(REPO / "web"))
    run("docker", "network", "create", NETWORK)
    # --network-alias rather than --name core: api/default.conf.template
    # hardcodes http://core:8000, but claiming the bare name `core` on the
    # host would be a collision waiting to happen.
    run(
        "docker",
        "run",
        "-d",
        "--name",
        STUB,
        "--network",
        NETWORK,
        "--network-alias",
        "core",
        STUB_IMAGE,
    )
    run(
        "docker",
        "run",
        "-d",
        "--name",
        PROXY,
        "--network",
        NETWORK,
        "-p",
        "127.0.0.1::8000",
        "-e",
        f"AIGUARD_API_KEY={TEST_KEY}",
        # Same filter the deployment uses. Widen it and every nginx $variable
        # in the template is blanked by envsubst.
        "-e",
        "NGINX_ENVSUBST_FILTER=^AIGUARD_API_KEY$",
        PROXY_IMAGE,
    )
    run(
        "docker",
        "run",
        "-d",
        "--name",
        WEB,
        "--network",
        NETWORK,
        "-p",
        "127.0.0.1::3000",
        WEB_IMAGE,
    )
    BASE = published_base(PROXY, 8000)
    WEB_BASE = published_base(WEB, 3000)
    for _ in range(60):
        try:
            if get("/health")[0] == 200 and web_get("/")[0] == 200:
                run("docker", "exec", WEB, "nginx", "-t")
                return
        except Exception:
            pass
        time.sleep(1)
    raise ContractFailure(
        "proxy/web never became ready:\n"
        f"{run('docker', 'logs', PROXY, check=False)}\n"
        f"{run('docker', 'logs', WEB, check=False)}"
    )


# ── the contract properties ───────────────────────────────────────────────


def check_frontend_static_boundary(failures: list[str]) -> None:
    config = (REPO / "web" / "nginx.conf").read_text(encoding="utf-8")
    safe_log_format = (
        """log_format private '$remote_addr $status $body_bytes_sent """
        """"$request_method"';"""
    )
    if (
        "access_log /var/log/nginx/access.log private;" not in config
        or safe_log_format not in config
    ):
        failures.append(
            "web log hygiene: frontend access log can record a request target"
        )
    if "combined" in config or "$request_uri" in config or "$args" in config:
        failures.append(
            "web log hygiene: frontend config can record request data visible in Dozzle"
        )

    page = (REPO / "web" / "index.html").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    forbidden_claims = (
        "ก่อนที่ข้อความจะออกจากเครื่อง",
        "สิ่งที่ออกจากเครื่องจริง ๆ",
        "mapping คืนผู้เรียก",
        "การจับคู่ระหว่างของจริงกับข้อมูลปกปิดถูกส่งกลับมาพร้อมคำตอบ",
        "หลักฐานว่าข้อมูลไม่หลุด",
        "ส่งเข้า AI อย่างปลอดภัย",
    )
    for claim in forbidden_claims:
        if claim in page or claim in readme:
            failures.append(
                f"hosted wording: stale local-only claim remains: {claim!r}"
            )

    required_boundaries = (
        "ข้อความต้นฉบับเดินทางถึงแพลตฟอร์มและเซิร์ฟเวอร์ AI Guard ก่อน",
        "ส่งต่อจากเซิร์ฟเวอร์ไปยังโมเดลภาษา",
        "ไม่คืน mapping หรือ token-bearing entity projection",
    )
    for boundary in required_boundaries:
        if boundary not in page:
            failures.append(
                f"hosted wording: required disclosure missing: {boundary!r}"
            )
    required_auth_claims = (
        "business API ทุกเส้นต้อง login",
        "HttpOnly",
        "ไม่บันทึก access code ลง browser storage",
    )
    for claim in required_auth_claims:
        if claim not in page + readme:
            failures.append(f"hosted wording: caller-auth boundary missing: {claim!r}")
    for forbidden_storage in ("localStorage", "sessionStorage"):
        if forbidden_storage in page:
            failures.append(
                f"frontend auth: credential storage primitive present: {forbidden_storage}"
            )
    if 'id="accessCode"' not in page or 'autocomplete="off"' not in page:
        failures.append(
            "frontend auth: access-code input does not disable autocomplete"
        )
    for stale_projection in (
        "body.entities",
        "body.before_png_b64",
        "body.entity_count",
        "body.section26 &&",
    ):
        if stale_projection in page:
            failures.append(
                f"frontend contract: stale reconstructable/v1 field remains: {stale_projection}"
            )
    for required_projection in (
        "body.highlights",
        "body.detected_entity_count",
        'fetch("/api/auth/login"',
        "codePointRangeToUtf16(text, e.start, e.end)",
        "body.authenticated === true",
        'provider_configuration: "บริการ LLM ยังไม่พร้อม',
        'ner_unavailable: "ระบบตรวจชื่อยังไม่พร้อม',
        'body.safety.status === "pass"',
        'body.restoration.status === "complete"',
        "body.restoration.leftover_count === 0",
    ):
        if required_projection not in page:
            failures.append(
                f"frontend contract: strict/minimized field missing: {required_projection}"
            )
    for required_session_safety in (
        "function clearSensitiveState()",
        "function invalidateBusinessRequests()",
        "function invalidateAuthCheck()",
        "function setAuthMutationState(value)",
        "authGeneration += 1;",
        "controller.abort();",
        "generation !== authCheckGeneration",
        "generation !== authGeneration",
        "generation !== detectGeneration || text !== editor.value",
        "if (isStaleBusinessError(err)) return;",
        "complete = r.status === 204;",
        "session บนเซิร์ฟเวอร์อาจยังอยู่",
    ):
        if required_session_safety not in page:
            failures.append(
                "frontend session safety: missing stale-response/state-clear guard: "
                f"{required_session_safety!r}"
            )
    logout_start = page.find('logoutBtn.addEventListener("click"')
    logout_invalidate = page.find("setAuthState(false", logout_start)
    logout_request = page.find('fetch("/api/auth/logout"', logout_start)
    if not (
        logout_start >= 0
        and logout_invalidate > logout_start
        and logout_request > logout_invalidate
    ):
        failures.append(
            "frontend session safety: logout does not invalidate state before its request"
        )
    if (
        page.count("if (authMutationInFlight) return;") < 2
        or page.count("setAuthMutationState(true);") < 2
        or page.count("setAuthMutationState(false);") < 2
    ):
        failures.append(
            "frontend session safety: login/logout mutations are not serialized"
        )

    api_config = (REPO / "api" / "default.conf.template").read_text(encoding="utf-8")
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    if "proxy_request_buffering off;" not in api_config:
        failures.append("volatile storage: api still buffers request bodies")
    if "proxy_buffering off;" not in api_config:
        failures.append("volatile storage: api still buffers response bodies")
    for mount in (
        "/var/cache/nginx:size=64m",
        "/tmp:size=1g,mode=1777",
    ):
        if mount not in compose:
            failures.append(f"volatile storage: compose tmpfs mount missing: {mount}")


def check_web_request_target_stays_out_of_log(failures: list[str]) -> None:
    before = run("docker", "logs", WEB).count("\n")
    status, _body = web_get(f"/{REQUEST_TARGET_MARKER}?q={REQUEST_TARGET_MARKER}")
    logs = run("docker", "logs", WEB)
    if status != 200:
        failures.append(f"web log hygiene: frontend returned {status}, expected 200")
    if REQUEST_TARGET_MARKER in logs:
        failures.append(
            "web log hygiene: attacker-controlled request target reached the runtime log"
        )
    if logs.count("\n") <= before:
        failures.append(
            "web log hygiene: no access row was emitted, so the request-target assertion "
            "did not exercise runtime logging"
        )


def check_web_api_does_not_fall_back_to_spa(failures: list[str]) -> None:
    status, body = web_get("/api/auth/session")
    if status != 404 or "<!doctype html>" in body.lower():
        failures.append(
            "frontend routing: /api/auth/session fell back to the SPA instead of 404"
        )


def check_prefix_is_re_added(failures: list[str]) -> None:
    for endpoint in ENDPOINTS:
        for path in (f"/{endpoint}", f"/v1/{endpoint}"):
            status, _headers, body = get(path)
            if status != 200:
                failures.append(f"prefix: {path} returned {status}, expected 200")
                continue
            seen = json.loads(body)["path"]
            expected = f"/api/{endpoint}"
            if seen != expected:
                failures.append(
                    f"prefix: {path} reached core as {seen}, expected {expected}"
                )
            if json.loads(body)["contract"] != "2":
                failures.append(f"contract: {path} did not inject HTTP contract 2")


def check_auth_paths_are_port_owned(failures: list[str]) -> None:
    for endpoint in AUTH_ENDPOINTS:
        for path in (f"/auth/{endpoint}", f"/v1/auth/{endpoint}"):
            status, _headers, body = get(path)
            if status != 200:
                failures.append(f"auth path: {path} returned {status}, expected 200")
                continue
            seen = json.loads(body)
            expected = f"/aift/auth/{endpoint}"
            if seen["path"] != expected:
                failures.append(
                    f"auth path: {path} reached core as {seen['path']}, expected {expected}"
                )
            if seen["key"] or seen["contract"]:
                failures.append(f"auth path: {path} received an internal core header")


def check_allowlist_denies_at_the_proxy(failures: list[str]) -> None:
    before = stub_log_lines()
    for path in DENIED:
        status, _headers, _body = get(path)
        if status != 404:
            failures.append(f"allowlist: {path} returned {status}, expected 404")
    after = stub_log_lines()
    # The status code alone cannot tell a proxy-side refusal from a 404 the
    # core produced after the request was forwarded. Only one of those is the
    # property being claimed.
    if after != before:
        failures.append(
            f"allowlist: {after - before} denied request(s) still reached core "
            f"— the proxy forwarded what it should have refused"
        )


def check_key_is_injected(failures: list[str]) -> None:
    _status, _headers, body = get("/detect")
    seen = json.loads(body)["key"]
    if seen != TEST_KEY:
        failures.append(
            f"key injection: core saw {seen!r}, expected the configured key"
        )


def check_request_target_stays_out_of_the_log(failures: list[str]) -> None:
    # Force the global limiter to delay/reject requests. Nginx normally writes
    # those warnings with the complete request line, a second query leak path
    # independent of access_log.
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        list(
            executor.map(
                lambda _: get(f"/detect?q={REQUEST_TARGET_MARKER}"),
                range(24),
            )
        )
    get(f"/{REQUEST_TARGET_MARKER}")
    if REQUEST_TARGET_MARKER in run("docker", "logs", PROXY):
        failures.append(
            "log hygiene: attacker-controlled request target reached runtime output"
        )
    for path in ("/health", "/v1/health"):
        status, _headers, _body = get(path)
        if status != 200:
            failures.append(
                f"health isolation: {path} returned {status} after business throttling"
            )


def check_responses_are_not_cacheable(failures: list[str]) -> None:
    for path in ("/health", "/v1/detect", "/auth/session", "/sanitize"):
        _status, headers, _body = get(path)
        if headers.get("Cache-Control") != "no-store":
            failures.append(
                f"cache: {path} returned Cache-Control={headers.get('Cache-Control')!r}, "
                f"expected 'no-store' — responses can carry restored PII"
            )


def main() -> int:
    failures: list[str] = []
    try:
        check_frontend_static_boundary(failures)
        setup()
        check_prefix_is_re_added(failures)
        check_auth_paths_are_port_owned(failures)
        check_allowlist_denies_at_the_proxy(failures)
        check_key_is_injected(failures)
        check_request_target_stays_out_of_the_log(failures)
        check_web_request_target_stays_out_of_log(failures)
        check_web_api_does_not_fall_back_to_spa(failures)
        check_responses_are_not_cacheable(failures)
    except ContractFailure as e:
        print(f"nginx contract: could not run — {e}", file=sys.stderr)
        return 2
    finally:
        teardown()

    if failures:
        print("nginx contract FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    if len(ENDPOINTS) * 2 + len(AUTH_ENDPOINTS) * 2 != PUBLIC_ROUTE_COUNT:
        raise ContractFailure("public route count drifted from 16")
    print(
        f"nginx contract ok: {len(ENDPOINTS) * 2} paths proxied, "
        f"{len(AUTH_ENDPOINTS) * 2} auth aliases isolated, "
        f"{len(DENIED)} denied at the proxy, key/contract injected, api/web logs clean, "
        "web nginx syntax valid, hosted wording bounded, no-store set"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

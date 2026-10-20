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
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CI_JOB_ID = os.environ.get("CI_JOB_ID", "").strip()
DRIVER_OVERRIDE = os.environ.get("AIFT_CONTRACT_DRIVER_CONTAINER", "").strip()
DRIVER_CONTAINER = ""
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

# The proxy uses independent public/work/provider lanes. Pacing keeps a
# failure here meaning "the contract is wrong", never "the test was too fast".
PACE_SECONDS = 0.15

ENDPOINTS = ["health", "detect", "guard", "roundtrip", "analyze-report"]
AUTH_ENDPOINTS = ("login", "logout", "session")

HOSTED3_FIXTURE = json.loads(
    (REPO / "tests" / "fixtures" / "hosted3" / "contract.json").read_text(
        encoding="utf-8"
    )
)
HOSTED3_PLANNED = HOSTED3_FIXTURE["additive_canonical_routes"] + [
    f"/v1{path}" for path in HOSTED3_FIXTURE["additive_canonical_routes"]
]
PUBLIC_ROUTE_COUNT = HOSTED3_FIXTURE["target_exact_route_count"]
HOSTED3_AUTH = ("/auth/guest", "/auth/guest/end")
HOSTED3_PROTECTED = {
    "/guest/preview": ("POST", b'{"scenario_id":"fixture"}', "/api/guest/preview"),
    "/guest/execute": ("POST", b'{"ticket":"fixture"}', "/api/guest/execute"),
    "/protection-preview": ("POST", b'{"text":"fixture","mode":"token"}', "/api/protection-preview"),
    "/protection-execute": ("POST", b'{"text":"fixture"}', "/api/protection-execute"),
    "/document-preview": ("POST", b"%PDF-fixture", "/api/document-preview"),
    "/document-execute": ("POST", b'{"protected_text":"fixture"}', "/api/document-execute"),
    "/provider-queue/join": ("POST", b'{"ticket":"fixture"}', "/api/provider-queue/join"),
    "/provider-queue/status": ("GET", None, "/api/provider-queue/status"),
    "/provider-queue/claim": ("POST", b'{"queue_capability":"fixture","last_revision":1}', "/api/provider-queue/claim"),
    "/provider-queue/cancel": ("POST", b"{}", "/api/provider-queue/cancel"),
}

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


def resolve_driver_container() -> str:
    """Resolve this Docker-executor job to the daemon's container identity."""

    if DRIVER_OVERRIDE:
        return DRIVER_OVERRIDE
    if not CI_JOB_ID:
        return ""

    # GitLab Runner labels the build container with the job ID. This is more
    # reliable than HOSTNAME: the runner deliberately sets a friendly hostname
    # that need not be a container name known to the Docker daemon.
    labelled = run(
        "docker",
        "ps",
        "-q",
        "--filter",
        f"label=com.gitlab.gitlab-runner.job.id={CI_JOB_ID}",
        "--filter",
        "label=com.gitlab.gitlab-runner.type=build",
    ).splitlines()
    if len(labelled) == 1:
        return labelled[0]

    # The runner simulator supplies the same labels. Keep a hostname-inspection
    # fallback for other CI-like containers without them, without inspecting
    # environments or printing any other container metadata.
    hostname = os.environ.get("HOSTNAME", "").strip()
    matches = []
    if hostname:
        for container_id in run("docker", "ps", "-q").splitlines():
            configured = run(
                "docker", "inspect", "-f", "{{.Config.Hostname}}", container_id
            ).strip()
            if configured == hostname:
                matches.append(container_id)
    if len(matches) != 1:
        raise ContractFailure(
            "could not uniquely resolve the Docker-executor job container"
        )
    return matches[0]


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


def get(
    path: str, *, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, str], str]:
    """GET `path`, returning (status, headers, body) for 404s as well as 200s."""
    time.sleep(PACE_SECONDS)
    request_headers = {"Host": "team08.aiforthai.in.th"}
    request_headers.update(headers or {})
    request = urllib.request.Request(BASE + path, headers=request_headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return (
                response.status,
                dict(response.headers),
                response.read().decode("utf-8"),
            )
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def call(
    path: str,
    *,
    method: str,
    data: bytes | None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], str]:
    """Call the built proxy without relying on a route count alone."""
    time.sleep(PACE_SECONDS)
    request_headers = {"Host": "team08.aiforthai.in.th"}
    request_headers.update(headers or {})
    if data is not None:
        request_headers.setdefault(
            "Content-Type", "application/pdf" if path.endswith("document-preview") else "application/json"
        )
    request = urllib.request.Request(BASE + path, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8", "replace")


def web_response(path: str) -> tuple[int, dict[str, str], str]:
    request = urllib.request.Request(
        WEB_BASE + path,
        headers={"Host": "team08.aiforthai.in.th"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8", "replace")


def web_binary_response(path: str) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        WEB_BASE + path,
        headers={"Host": "team08.aiforthai.in.th"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def no_redirect_response(
    base: str, path: str, headers: dict[str, str]
) -> tuple[int, dict[str, str]]:
    request_headers = {"Host": "team08.aiforthai.in.th"}
    request_headers.update(headers)
    request = urllib.request.Request(base + path, headers=request_headers, method="GET")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=15) as response:
            return response.status, dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers)


def web_get(path: str) -> tuple[int, str]:
    status, _headers, body = web_response(path)
    return status, body


def stub_log_lines() -> int:
    return len([ln for ln in run("docker", "logs", STUB).splitlines() if ln.strip()])


def teardown() -> None:
    run("docker", "rm", "-f", STUB, PROXY, WEB, check=False)
    if DRIVER_CONTAINER:
        run(
            "docker",
            "network",
            "disconnect",
            "-f",
            NETWORK,
            DRIVER_CONTAINER,
            check=False,
        )
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
    global BASE, DRIVER_CONTAINER, WEB_BASE
    DRIVER_CONTAINER = resolve_driver_container()
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
    # Docker-executor jobs run inside a container. Host-loopback publications
    # are deliberately unreachable from that container, so attach the job
    # container to this isolated test network and use Docker DNS. Local runs
    # retain the published-loopback path. In both modes, resolving the
    # publication first proves the production bind stays on 127.0.0.1.
    proxy_published = published_base(PROXY, 8000)
    web_published = published_base(WEB, 3000)
    if DRIVER_CONTAINER:
        run("docker", "network", "connect", NETWORK, DRIVER_CONTAINER)
        BASE = f"http://{PROXY}:8000"
        WEB_BASE = f"http://{WEB}:3000"
    else:
        BASE = proxy_published
        WEB_BASE = web_published
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
        "log_format private 'surface=web status=$status bytes=$body_bytes_sent "
        "method=$request_method rt=$request_time';"
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

    home = (REPO / "web" / "index.html").read_text(encoding="utf-8")
    app_page = (REPO / "web" / "app.html").read_text(encoding="utf-8")
    app_js = (REPO / "web" / "hosted3-app.js").read_text(encoding="utf-8")
    page = app_page + "\n" + app_js
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
        if claim in home or claim in page or claim in readme:
            failures.append(
                f"hosted wording: stale local-only claim remains: {claim!r}"
            )

    required_boundaries = (
        "ข้อความและ PDF แบบมี text layer ผ่าน organizer proxy และ AI Guard Core",
        "Pathumma ได้รับเฉพาะข้อความที่ปกป้องและอนุมัติแล้ว",
        "ไม่ได้รับ PDF, ข้อความต้นฉบับ หรือ mapping",
    )
    for boundary in required_boundaries:
        if boundary not in page:
            failures.append(
                f"hosted wording: required disclosure missing: {boundary!r}"
            )
    required_auth_claims = (
        "Start Standard access",
        "Use Priority Invite",
        "ไม่เก็บข้อมูลส่วนตัวในเบราว์เซอร์",
    )
    for claim in required_auth_claims:
        if claim not in page + readme:
            failures.append(f"hosted wording: caller-auth boundary missing: {claim!r}")
    for forbidden_storage in ("localStorage", "sessionStorage"):
        if re.search(rf"{forbidden_storage}\s*[.\[]", app_js):
            failures.append(
                f"frontend auth: credential storage primitive present: {forbidden_storage}"
            )
    if 'id="h3Invite"' not in page or 'autocomplete="off"' not in page:
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
        'api("/api/auth/login"',
        "body.authenticated !== true",
        "function customResultStatus(body, expectedProtected)",
        'body.safety.status !== "pass"',
        'status === "complete"',
        'status === "incomplete"',
        'status === "unsafe"',
        'body.restored_text !== ""',
        '!Object.hasOwn(body, "restored_text")',
    ):
        if required_projection not in page:
            failures.append(
                f"frontend contract: strict/minimized field missing: {required_projection}"
            )
    for required_session_safety in (
        "function resetSensitive(",
        "function setAuthorityBusy(value)",
        "state.generation += 1",
        "state.inspectRequest += 1",
        "state.claimAbort.abort()",
        "function isCurrent(generation)",
        "if (state.authorityMutation) return",
        "setProviderRunning(true)",
        "ไม่สามารถรับประกันการยกเลิก upstream",
    ):
        if required_session_safety not in page:
            failures.append(
                "frontend session safety: missing stale-response/state-clear guard: "
                f"{required_session_safety!r}"
            )
    logout_start = page.find("async function endAuthority()")
    logout_invalidate = page.find("resetSensitive({ keepInputs: false })", logout_start)
    logout_request = page.find("await api(path", logout_start)
    if not (
        logout_start >= 0
        and logout_invalidate > logout_start
        and logout_request > logout_invalidate
    ):
        failures.append(
            "frontend session safety: logout does not invalidate state before its request"
        )
    if (
        page.count("if (state.authorityMutation) return;") < 3
        or page.count("setAuthorityBusy(true);") < 3
        or page.count("setAuthorityBusy(false);") < 3
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
        "/tmp:size=128m,mode=1777",
    ):
        if mount not in compose:
            failures.append(f"volatile storage: compose tmpfs mount missing: {mount}")


def check_web_request_target_stays_out_of_log(failures: list[str]) -> None:
    before = run("docker", "logs", WEB).count("\n")
    status, _body = web_get(f"/{REQUEST_TARGET_MARKER}?q={REQUEST_TARGET_MARKER}")
    logs = run("docker", "logs", WEB)
    if status != 404:
        failures.append(f"web routing: unknown path returned {status}, expected 404")
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


def check_frontend_security_headers(failures: list[str]) -> None:
    _status, headers, _body = web_response("/")
    expected = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
        "Strict-Transport-Security": "max-age=31536000",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
    }
    for name, value in expected.items():
        if headers.get(name) != value:
            failures.append(f"frontend header: {name} is not {value!r}")
    csp = headers.get("Content-Security-Policy", "")
    for directive in (
        "default-src 'self'",
        "connect-src 'self'",
        "font-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
        "script-src 'self'",
    ):
        if directive not in csp:
            failures.append(f"frontend header: CSP missing {directive!r}")


def check_product_pages_and_https_enforcement(failures: list[str]) -> None:
    web_config = (REPO / "web" / "nginx.conf").read_text(encoding="utf-8")
    expected_pages = {
        "/": "ปกป้องข้อมูลก่อน",
        "/app": "Hosted 3.0.2 Web App",
        "/privacy": "ข้อมูลไปไหน",
        "/terms": "ใช้ได้เมื่อ",
        "/help": "แก้ปัญหา",
        "/downloads": "ข้อมูลอยู่ในเครื่อง",
        "/developers": "Contract &amp;".replace("&amp;", "&"),
        "/robots.txt": "Disallow: /api/",
        "/sitemap.xml": "https://team08.aiforthai.in.th/privacy",
    }
    for path, marker in expected_pages.items():
        status, body = web_get(path)
        if status != 200 or marker not in body:
            failures.append(f"product page: {path} was not the expected static surface")
        if path in {"/privacy", "/terms", "/help", "/downloads"} and (
            'href="/app">Hosted Web</a>' not in body
        ):
            failures.append(
                f"product page: {path} Web App navigation bypassed invite access"
            )
        if path in {"/privacy", "/terms", "/help", "/downloads"} and (
            'href="/assets/ai-guard-favicon.svg"' not in body
        ):
            failures.append(f"product page: {path} does not use the production favicon")
        if path in {"/privacy", "/terms", "/help", "/downloads", "/developers"} and (
            'href="/developers">Contract &amp; evidence</a>' not in body
            and path != "/developers"
        ):
            failures.append(f"product page: {path} does not link Contract & evidence")

    static_assets = {
        "/assets/ai-guard-mark.svg": ("image/svg+xml", b"<svg"),
        "/assets/ai-guard-mark-one-color.svg": ("image/svg+xml", b"<svg"),
        "/assets/ai-guard-mark-inverse.svg": ("image/svg+xml", b"<svg"),
        "/assets/ai-guard-favicon.svg": ("image/svg+xml", b"<svg"),
        "/assets/ai-guard-favicon-inverse.svg": ("image/svg+xml", b"<svg"),
        "/assets/fonts/anuphan-thai.woff2": ("font/woff2", b"wOF2"),
        "/assets/fonts/anuphan-latin.woff2": ("font/woff2", b"wOF2"),
        "/assets/fonts/OFL-Anuphan.txt": ("text/plain", b"Copyright 2019 The Anuphan Project Authors"),
        "/home.css": ("text/css", b"    @font-face"),
        "/home.js": ("application/javascript", b"document.documentElement.classList.add"),
        "/app.css": ("text/css", b"  @font-face"),
        "/hosted3-app.js": ("application/javascript", b"(() => {"),
        "/product.css": ("text/css", b"@font-face"),
    }
    for path, (content_type, prefix) in static_assets.items():
        if f"location = {path}" not in web_config or f"try_files {path} =404;" not in web_config:
            failures.append(f"static asset: exact allowlist route missing for {path}")
            continue
        status, headers, body = web_binary_response(path)
        if status != 200:
            failures.append(f"static asset: {path} returned {status}")
        if not headers.get("Content-Type", "").lower().startswith(content_type):
            failures.append(
                f"static asset: {path} content type was {headers.get('Content-Type')!r}"
            )
        if not body.startswith(prefix):
            failures.append(f"static asset: {path} payload signature/marker mismatch")
    status, _headers, _body = web_binary_response("/assets/fonts/anuphan-thai.woff2x")
    if status != 404:
        failures.append("static asset: near-match font route was not denied")
    status, body = web_get("/not-a-product-page")
    if status != 404 or "หลงทาง" not in body or "AI Guard" not in body:
        failures.append("web routing: unknown human route did not preserve branded 404")
    for href in ('href="/"', 'href="/app"', 'href="/downloads"', 'href="/help"'):
        if href not in body:
            failures.append(f"web routing: branded 404 recovery is missing {href}")
    status, body = web_get("/assets/ai-guard-mark.svgx")
    if status != 404 or "<!doctype html>" in body.lower():
        failures.append("web routing: asset near-match returned branded HTML")
    for path in (
        "/app.html",
        "/privacy.html",
        "/terms.html",
        "/help.html",
        "/downloads.html",
        "/developers.html",
        "/home.jsx",
        "/product.cssx",
        "/unknown.js",
    ):
        status, body = web_get(path)
        if status != 404 or "<!doctype html>" in body.lower():
            failures.append(f"web routing: filename-like route was not fixed 404: {path}")
    status, body = web_get("/404.html")
    if status != 404 or "หลงทาง" in body:
        failures.append("web routing: internal 404 document is directly accessible")
    for base, path, location in (
        (WEB_BASE, "/private?q=must-not-reflect", "https://team08.aiforthai.in.th/private"),
        (BASE, "/health?q=must-not-reflect", "https://team08.aiforthai.in.th/api/health"),
    ):
        status, headers = no_redirect_response(
            base, path, {"X-Forwarded-Proto": "http"}
        )
        if status != 308 or headers.get("Location") != location:
            failures.append(
                f"https enforcement: {path} returned {status}/{headers.get('Location')!r}"
            )


def check_rate_and_log_policy(failures: list[str]) -> None:
    config = (REPO / "api" / "default.conf.template").read_text(encoding="utf-8")
    web_config = (REPO / "web" / "nginx.conf").read_text(encoding="utf-8")
    core_dockerfile = (REPO / "core" / "Dockerfile").read_text(encoding="utf-8")
    if "$remote_addr" in config or "$remote_addr" in web_config:
        failures.append("log privacy: client IP remains in an application log format")
    if "--no-access-log" not in core_dockerfile:
        failures.append("log privacy: Uvicorn client metadata logging remains enabled")
    for required in (
        '"~(?:^|;[[:space:]]*)__Host-aift_session=v1\\.[0-9]{1,12}\\.([A-Za-z0-9_-]{22})\\.[A-Za-z0-9_-]{43}(?:;|$)" $1;',
        "$aift_duplicate_session_cookie",
        "$aift_duplicate_standard_cookie",
        "zone=document_global:1m rate=4r/m",
        "zone=document_global_conn:1m",
        "zone=public_global:1m rate=30r/s",
        "zone=auth_global:1m rate=2r/s",
        "zone=provider_global:1m rate=6r/m",
        "zone=provider_caller:4m rate=2r/m",
        "limit_conn provider_global_conn 2;",
        "limit_conn provider_caller_conn 1;",
        "listen 127.0.0.1:8001;",
        "location /internal-health",
    ):
        if required not in config:
            failures.append(f"abuse control: missing {required!r}")
    for location in ("/health", "/v1/health", "/auth/session", "/v1/auth/session"):
        match = re.search(
            rf"location = {re.escape(location)} \{{(?P<body>.*?)\n  \}}",
            config,
            re.DOTALL,
        )
        if match is None or "limit_req zone=public_global" not in match.group("body"):
            failures.append(f"abuse control: {location} lacks public control-plane limit")
    for location in ("/roundtrip", "/v1/roundtrip"):
        match = re.search(
            rf"location = {re.escape(location)} \{{(?P<body>.*?)\n  \}}",
            config,
            re.DOTALL,
        )
        body = match.group("body") if match else ""
        if "limit_req zone=provider_global" not in body or "limit_req zone=provider_caller" not in body:
            failures.append(f"abuse control: {location} lacks provider request lanes")

    # Exercise the real v1 cookie shape.  Six requests fit one caller's
    # work-lane capacity (base request + burst 5); the seventh is rejected,
    # while a different session nonce retains its own allowance.  This pins
    # the fairness key to the AuthGateway token grammar instead of a regex
    # that can silently fall back to one proxy/client address.
    def shaped_cookie(nonce: str) -> str:
        return "__Host-aift_session=v1.1800001800." + nonce + "." + "s" * 43

    first_headers = {"Cookie": shaped_cookie("callerA".ljust(22, "a"))}
    statuses = [get("/guard", headers=first_headers)[0] for _ in range(7)]
    if statuses[:6] != [200] * 6 or statuses[6] != 429:
        failures.append(f"abuse control: caller work lane was not 6 then 429: {statuses!r}")
    second_status, _headers, _body = get(
        "/guard",
        headers={"Cookie": shaped_cookie("callerB".ljust(22, "b"))},
    )
    if second_status != 200:
        failures.append("abuse control: a distinct valid session nonce shared the first caller lane")
    shadow_status, _headers, _body = get(
        "/guard",
        headers={
            "Cookie": "shadow="
            + shaped_cookie("callerA".ljust(22, "a"))
            + "; "
            + shaped_cookie("shadowSafe".ljust(22, "s"))
        },
    )
    if shadow_status != 200:
        failures.append("abuse control: cookie-name text embedded in a value selected the rate key")
    duplicate_status, _headers, _body = get(
        "/guard",
        headers={
            "Cookie": shaped_cookie("rotated".ljust(22, "r"))
            + "; "
            + shaped_cookie("authenticated".ljust(22, "a"))
        },
    )
    if duplicate_status != 400:
        failures.append("abuse control: duplicate session authorities were not rejected")
    duplicate_standard_status, _headers, _body = get(
        "/guard",
        headers={
            "Cookie": "__Host-aift_guest="
            + shaped_cookie("rotatedGuest".ljust(22, "r")).split("=", 1)[1]
            + "; __Host-aift_guest="
            + shaped_cookie("authenticatedGuest".ljust(22, "a")).split("=", 1)[1]
        },
    )
    if duplicate_standard_status != 400:
        failures.append("abuse control: duplicate Standard authorities were not rejected")

    # Exhaust the public control-plane bucket, then prove container liveness
    # uses the unexported listener and cannot be forced into a restart loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=48) as executor:
        public_statuses = list(executor.map(lambda _: get("/health")[0], range(96)))
    if 429 not in public_statuses:
        failures.append("abuse control: public health saturation did not reach its bound")
    probe = subprocess.run(
        [
            "docker",
            "exec",
            PROXY,
            "wget",
            "-q",
            "-T",
            "2",
            "-t",
            "1",
            "-O",
            "/dev/null",
            "http://127.0.0.1:8001/internal-health",
        ],
        capture_output=True,
    )
    if probe.returncode != 0:
        failures.append("health isolation: public saturation broke private liveness")


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


def check_hosted3_exact_routes_reach_only_approved_core_paths(failures: list[str]) -> None:
    """Exercise every new canonical and alias route through the built proxy."""
    for path in HOSTED3_AUTH:
        for public_path in (path, "/v1" + path):
            status, _headers, body = call(public_path, method="POST", data=b"{}")
            if status != 200:
                failures.append(f"stage5 auth: {public_path} returned {status}, expected 200")
                continue
            seen = json.loads(body)
            if seen.get("path") != "/aift" + path or seen.get("key") or seen.get("contract"):
                failures.append(f"stage5 auth: {public_path} did not isolate port-owned auth")
    for index, (path, (method, data, upstream)) in enumerate(HOSTED3_PROTECTED.items()):
        expected_body = None
        cookie = (
            "__Host-aift_guest=v1.1800001800."
            + f"stage5{index}".ljust(22, "x")
            + "."
            + "s" * 43
        )
        for public_path in (path, "/v1" + path):
            status, _headers, body = call(
                public_path, method=method, data=data, headers={"Cookie": cookie}
            )
            if status != 200:
                failures.append(f"stage5 route: {public_path} returned {status}, expected 200")
                continue
            seen = json.loads(body)
            if seen.get("path") != upstream or seen.get("key") != TEST_KEY or seen.get("contract") != "2":
                failures.append(f"stage5 route: {public_path} did not reach only {upstream}")
            if expected_body is None:
                expected_body = body
            elif body != expected_body:
                failures.append(f"stage5 parity: {path} and /v1 alias differ at proxy")

    before = stub_log_lines()
    status, headers, _body = call(
        "/provider-queue/status",
        method="GET",
        data=b"x",
        headers={"Cookie": "__Host-aift_guest=v1.1800001800." + "bodyless".ljust(22, "x") + "." + "s" * 43},
    )
    if status != 413 or "X-AIGuard-Server-Time-Ms" in headers:
        failures.append("stage5 status: nonempty GET body was not headerless edge 413")
    if stub_log_lines() != before:
        failures.append("stage5 status: rejected body reached Core")

    operation_map = (REPO / "api" / "default.conf.template").read_text(encoding="utf-8")
    expected_operations = {
        "/auth/guest": "auth_guest",
        "/auth/guest/end": "auth_guest_end",
        "/guest/preview": "guest_preview",
        "/guest/execute": "guest_execute",
        "/protection-preview": "protection_preview",
        "/protection-execute": "protection_execute",
        "/document-preview": "document_preview",
        "/document-execute": "document_execute",
        "/provider-queue/join": "provider_queue_join",
        "/provider-queue/status": "provider_queue_status",
        "/provider-queue/claim": "provider_queue_claim",
        "/provider-queue/cancel": "provider_queue_cancel",
    }
    for path, operation in expected_operations.items():
        if f"  {path} {operation};" not in operation_map or f"  /v1{path} {operation};" not in operation_map:
            failures.append(f"stage5 logging: {path} does not have its value-free operation label")


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


def check_fixed_proxy_failures_and_timeout_policy(failures: list[str]) -> None:
    expected = {
        413: ("request_too_large", "request", False),
        429: ("rate_limited", "rate_limit", True),
        502: ("upstream_unavailable", "upstream", True),
        504: ("upstream_timeout", "upstream", True),
    }
    for status_code, (code, category, retryable) in expected.items():
        status, headers, body = get(
            "/detect",
            headers={
                "X-Contract-Failure": str(status_code),
                "Cookie": (
                    "__Host-aift_session=v1.1800001800."
                    + f"contract{status_code}".ljust(22, "x")
                    + "."
                    + "s" * 43
                ),
            },
        )
        if status != status_code:
            failures.append(
                f"fixed error: upstream {status_code} became {status}, expected {status_code}"
            )
            continue
        try:
            payload = json.loads(body)
        except ValueError:
            failures.append(f"fixed error: {status_code} response was not JSON")
            continue
        if payload != {
            "error": {
                "code": code,
                "status": status_code,
                "category": category,
                "count": 0,
                "retryable": retryable,
            }
        }:
            failures.append(f"fixed error: {status_code} response shape drifted")
        if "UNSAFE-UPSTREAM-BODY" in body:
            failures.append(f"fixed error: {status_code} relayed the upstream body")
        if headers.get("Cache-Control") != "no-store":
            failures.append(f"fixed error: {status_code} omitted no-store")
        if not headers.get("Content-Type", "").startswith("application/json"):
            failures.append(f"fixed error: {status_code} content type is not JSON")

    config = (REPO / "api" / "default.conf.template").read_text(encoding="utf-8")
    for location in ("/roundtrip", "/v1/roundtrip"):
        block = re.search(
            rf"location = {re.escape(location)} \{{(?P<body>.*?)\n  \}}",
            config,
            re.DOTALL,
        )
        if block is None or "proxy_read_timeout 200s;" not in block.group("body"):
            failures.append(f"timeout: {location} does not cover the shared 183s policy")
    if config.count("proxy_read_timeout 200s;") != 8:
        failures.append("timeout: provider deadline is not limited to the two legacy and six Stage 5 execute aliases")

    frontend = (REPO / "web" / "hosted3-app.js").read_text(encoding="utf-8")
    for marker in (
        "setProviderRunning(true)",
        "one unresolved provider-bound",
        "ไม่สามารถรับประกันการยกเลิก upstream",
    ):
        if marker not in frontend and marker not in (
            REPO / "docs" / "production-web-redesign.md"
        ).read_text(encoding="utf-8"):
            failures.append(
                f"timeout: Hosted 3 caller lost unresolved-provider truth: {marker!r}"
            )


def main() -> int:
    failures: list[str] = []
    try:
        check_frontend_static_boundary(failures)
        setup()
        check_prefix_is_re_added(failures)
        check_auth_paths_are_port_owned(failures)
        check_hosted3_exact_routes_reach_only_approved_core_paths(failures)
        check_allowlist_denies_at_the_proxy(failures)
        check_key_is_injected(failures)
        check_request_target_stays_out_of_the_log(failures)
        check_web_request_target_stays_out_of_log(failures)
        check_web_api_does_not_fall_back_to_spa(failures)
        check_frontend_security_headers(failures)
        check_product_pages_and_https_enforcement(failures)
        check_responses_are_not_cacheable(failures)
        check_fixed_proxy_failures_and_timeout_policy(failures)
        check_rate_and_log_policy(failures)
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
    if len(ENDPOINTS) * 2 + len(AUTH_ENDPOINTS) * 2 + len(HOSTED3_AUTH) * 2 + len(HOSTED3_PROTECTED) * 2 != PUBLIC_ROUTE_COUNT:
        raise ContractFailure("public route count drifted from the approved 40")
    print(
        f"nginx contract ok: {len(ENDPOINTS) * 2} paths proxied, "
        f"{(len(AUTH_ENDPOINTS) + len(HOSTED3_AUTH)) * 2} auth aliases isolated, "
        f"{len(HOSTED3_PROTECTED) * 2} Stage 5 paths route to approved Core targets, "
        f"{len(DENIED)} denied at the proxy, key/contract injected, api/web logs clean, "
        "web nginx syntax valid, hosted wording bounded, no-store set"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

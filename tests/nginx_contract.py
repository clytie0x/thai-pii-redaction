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

Constraints this file lives under:

- The runner is `docker:27.3.1` with a bare `python3` from `apk add`. No venv,
  no httpx, no pytest. Standard library only, and a non-zero exit on failure.
- Names and ports are prefixed so a run can never collide with the deployed
  `team08` stack, and every container, network and image is removed in a
  `finally` even when an assertion fails mid-way.

Usage: python3 tests/nginx_contract.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PREFIX = "aiguard-contract"
NETWORK = f"{PREFIX}-net"
STUB = f"{PREFIX}-stub"
PROXY = f"{PREFIX}-api"
STUB_IMAGE = f"{PREFIX}-stub:test"
PROXY_IMAGE = f"{PREFIX}-api:test"

# Outside the team's 20070-20079 allocation on purpose: a contract run must not
# be able to take a port the real deployment wants.
PORT = 21099
BASE = f"http://127.0.0.1:{PORT}"

TEST_KEY = "contract-test-key-not-a-real-secret"
QUERY_MARKER = "SECRET_MARKER_9f3a1c"

# The proxy rate-limits at 10r/s with burst 10. Pacing below that keeps a
# failure here meaning "the contract is wrong", never "the test was too fast".
PACE_SECONDS = 0.15

ENDPOINTS = ["health", "detect", "guard", "roundtrip", "analyze-report", "redact-pdf"]

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
]


class ContractFailure(Exception):
    pass


def run(*args: str, check: bool = True) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise ContractFailure(f"{' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def get(path: str) -> tuple[int, dict[str, str], str]:
    """GET `path`, returning (status, headers, body) for 404s as well as 200s."""
    time.sleep(PACE_SECONDS)
    request = urllib.request.Request(BASE + path, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")


def stub_log_lines() -> int:
    return len([ln for ln in run("docker", "logs", STUB).splitlines() if ln.strip()])


def teardown() -> None:
    run("docker", "rm", "-f", STUB, PROXY, check=False)
    run("docker", "network", "rm", NETWORK, check=False)
    run("docker", "image", "rm", "-f", STUB_IMAGE, PROXY_IMAGE, check=False)


def setup() -> None:
    teardown()  # a previous run that died hard must not poison this one
    run("docker", "build", "-q", "-t", STUB_IMAGE, str(REPO / "tests" / "stub-core"))
    run("docker", "build", "-q", "-t", PROXY_IMAGE, str(REPO / "api"))
    run("docker", "network", "create", NETWORK)
    # --network-alias rather than --name core: api/default.conf.template
    # hardcodes http://core:8000, but claiming the bare name `core` on the
    # host would be a collision waiting to happen.
    run(
        "docker", "run", "-d", "--name", STUB,
        "--network", NETWORK, "--network-alias", "core", STUB_IMAGE,
    )
    run(
        "docker", "run", "-d", "--name", PROXY, "--network", NETWORK,
        "-p", f"127.0.0.1:{PORT}:8000",
        "-e", f"AIGUARD_API_KEY={TEST_KEY}",
        # Same filter the deployment uses. Widen it and every nginx $variable
        # in the template is blanked by envsubst.
        "-e", "NGINX_ENVSUBST_FILTER=^AIGUARD_API_KEY$",
        PROXY_IMAGE,
    )
    for _ in range(60):
        try:
            if get("/health")[0] == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise ContractFailure(f"proxy never became ready:\n{run('docker', 'logs', PROXY, check=False)}")


# ── the five properties ───────────────────────────────────────────────────


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
                failures.append(f"prefix: {path} reached core as {seen}, expected {expected}")


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
        failures.append(f"key injection: core saw {seen!r}, expected the configured key")


def check_query_string_stays_out_of_the_log(failures: list[str]) -> None:
    get(f"/detect?q={QUERY_MARKER}")
    if QUERY_MARKER in run("docker", "logs", PROXY):
        failures.append(
            "log hygiene: the query string reached the access log — it is visible in Dozzle"
        )


def check_responses_are_not_cacheable(failures: list[str]) -> None:
    for path in ("/health", "/v1/detect", "/sanitize"):
        _status, headers, _body = get(path)
        if headers.get("Cache-Control") != "no-store":
            failures.append(
                f"cache: {path} returned Cache-Control={headers.get('Cache-Control')!r}, "
                f"expected 'no-store' — responses can carry restored PII"
            )


def main() -> int:
    failures: list[str] = []
    try:
        setup()
        check_prefix_is_re_added(failures)
        check_allowlist_denies_at_the_proxy(failures)
        check_key_is_injected(failures)
        check_query_string_stays_out_of_the_log(failures)
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
    print(f"nginx contract ok: {len(ENDPOINTS) * 2} paths proxied, {len(DENIED)} denied at the proxy, key injected, log clean, no-store set")
    return 0


if __name__ == "__main__":
    sys.exit(main())

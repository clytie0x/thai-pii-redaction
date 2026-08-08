#!/usr/bin/env python3
"""Value-safe post-deploy acceptance for the exact running team08 stack.

Application credentials are read from inherited environment only. They are
used inside this process for HTTP requests and in-memory log comparisons;
none is placed in a child-process argument or printed on failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from http.cookies import SimpleCookie

TEAM = os.environ.get("TEAM", "team08")
PORT = os.environ.get("BASE_1", "20071")
BASE_URL = f"http://127.0.0.1:{PORT}"
EXPECTED_REVISION = os.environ.get("CI_COMMIT_SHA", "local-working-tree")
SYNTHETIC_TEXT = "ผมชื่อ นายสมชาย ใจดี โทร 081-234-5678"
APP_VARIABLES = (
    "APP_AIGUARD_API_KEY",
    "APP_AIFT_ACCESS_CODE",
    "APP_AIFT_COOKIE_SIGNING_KEY",
    "APP_TOKENMIND_API_KEY",
)


class AcceptanceFailure(RuntimeError):
    """A fixed, value-free acceptance assertion failed."""


def _value_free_child_environment() -> dict[str, str]:
    return {name: value for name, value in os.environ.items() if name not in APP_VARIABLES}


def _run(*args: str) -> bytes:
    result = subprocess.run(args, capture_output=True, env=_value_free_child_environment())
    if result.returncode:
        raise AcceptanceFailure("container inspection command failed")
    return result.stdout


def _request(
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    cookie: str = "",
    origin: str = "",
    timeout: float = 30,
) -> tuple[int, object, bytes]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    request = urllib.request.Request(
        BASE_URL + path, data=body, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()
    except Exception as error:
        raise AcceptanceFailure("public HTTP request failed") from error


def _json(body: bytes) -> dict:
    try:
        value = json.loads(body)
    except Exception as error:
        raise AcceptanceFailure("public response was not JSON") from error
    if not isinstance(value, dict):
        raise AcceptanceFailure("public response shape was invalid")
    return value


def _login() -> str:
    access_code = os.environ.get("APP_AIFT_ACCESS_CODE", "")
    if not access_code:
        raise AcceptanceFailure("caller authentication configuration missing")
    status, headers, _body = _request(
        "/auth/login", method="POST", payload={"access_code": access_code}
    )
    access_code = ""
    if status != 204:
        raise AcceptanceFailure("caller login failed")
    raw_cookie = headers.get("Set-Cookie", "")
    if not all(flag in raw_cookie for flag in ("Secure", "HttpOnly", "SameSite=Strict")):
        raise AcceptanceFailure("caller cookie flags are incomplete")
    parsed = SimpleCookie()
    parsed.load(raw_cookie)
    morsel = parsed.get("__Host-aift_session")
    if morsel is None:
        raise AcceptanceFailure("caller cookie missing")
    return f"__Host-aift_session={morsel.value}"


def _verify_revisions() -> None:
    for service in ("web", "api", "core"):
        actual = _run(
            "docker",
            "inspect",
            "-f",
            '{{ index .Config.Labels "org.opencontainers.image.revision" }}',
            f"{TEAM}-{service}-1",
        ).decode("utf-8", "replace").strip()
        if actual != EXPECTED_REVISION:
            raise AcceptanceFailure("running image revision mismatch")


def _verify_public_contract(cookie: str) -> None:
    status, _headers, _body = _request(
        "/detect", method="POST", payload={"text": "synthetic"}
    )
    if status != 401:
        raise AcceptanceFailure("unauthenticated business request was accepted")
    status, _headers, _body = _request(
        "/detect",
        method="POST",
        payload={"text": "synthetic"},
        cookie="__Host-aift_session=tampered",
    )
    if status != 401:
        raise AcceptanceFailure("tampered caller cookie was accepted")
    status, _headers, _body = _request(
        "/roundtrip",
        method="POST",
        payload={"text": SYNTHETIC_TEXT, "mode": "token", "provider": "tokenmind"},
        cookie=cookie,
        origin="https://example.invalid",
    )
    if status != 403:
        raise AcceptanceFailure("cross-site request was accepted")
    for path in (
        "/sanitize",
        "/reidentify",
        "/docs",
        "/openapi.json",
        "/redact-pdf",
        "/v1/redact-pdf",
    ):
        status, _headers, _body = _request(path, method="POST")
        if status != 404:
            raise AcceptanceFailure("a forbidden public route escaped the allowlist")


def _verify_live_roundtrip(cookie: str) -> None:
    status, _headers, raw = _request(
        "/roundtrip",
        method="POST",
        payload={"text": SYNTHETIC_TEXT, "mode": "token", "provider": "tokenmind"},
        cookie=cookie,
        timeout=210,
    )
    if status != 200:
        raise AcceptanceFailure("live roundtrip failed")
    body = _json(raw)
    sanitized = str(body.get("sanitized_text", ""))
    restoration = body.get("restoration") or {}
    safe = body.get("safety") or {}
    token_projection = {"mapping", "entities", "highlights"} & set(body)
    if not (
        body.get("provider_used") == "tokenmind"
        and "สมชาย" not in sanitized
        and "081-234-5678" not in sanitized
        and body.get("detected_entity_count", 0) >= 2
        and safe == {"status": "pass", "residual_count": 0}
        and restoration.get("status") == "complete"
        and restoration.get("leftover_count") == 0
        and not token_projection
    ):
        raise AcceptanceFailure("live roundtrip safety projection failed")


def _verify_report_probe() -> None:
    container = f"{TEAM}-core-1"
    try:
        _run("docker", "cp", "tests/runner_route_probe.py", f"{container}:/app/runner_route_probe.py")
        _run(
            "docker",
            "exec",
            "-e",
            "AIFT_PROBE_API=http://api:8000",
            container,
            "python",
            "/app/runner_route_probe.py",
        )
    finally:
        subprocess.run(
            ["docker", "exec", container, "rm", "-f", "/app/runner_route_probe.py"],
            capture_output=True,
            env=_value_free_child_environment(),
        )


def _verify_logs(cookie: str) -> None:
    markers = [cookie, "สมชาย", "081-234-5678"]
    markers.extend(value for name in APP_VARIABLES if (value := os.environ.get(name, "")))
    for service in ("web", "api", "core"):
        logs = _run("docker", "logs", f"{TEAM}-{service}-1").decode(
            "utf-8", "replace"
        )
        if any(marker and marker in logs for marker in markers):
            raise AcceptanceFailure("sensitive value reached retained runtime logs")


def main() -> int:
    try:
        _verify_revisions()
        status, _headers, _body = _request("/health")
        if status != 200:
            raise AcceptanceFailure("public health failed")
        cookie = _login()
        _verify_public_contract(cookie)
        _verify_live_roundtrip(cookie)
        _verify_report_probe()
        _verify_logs(cookie)
        status, _headers, _body = _request(
            "/auth/logout", method="POST", cookie=cookie
        )
        if status != 204:
            raise AcceptanceFailure("caller logout failed")
        cookie = ""
        print("platform acceptance passed: auth, allowlist, live roundtrip, report, logs")
        return 0
    except AcceptanceFailure as error:
        print(f"platform acceptance failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

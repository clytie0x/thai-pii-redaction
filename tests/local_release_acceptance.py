#!/usr/bin/env python3
"""Provider-free acceptance for an exact locally built hosted candidate.

All application values are read from the inherited environment and are used
only in this process. Docker child arguments and the aggregate JSON result are
value-free. The deployment compose file is never invoked by this helper, so it
cannot implicitly read a repository `.env` file.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
from datetime import datetime, timezone
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "out"
API = "http://127.0.0.1:20071"
WEB = "http://127.0.0.1:20070"
TEAM = "team08"
SYNTHETIC_NAME = "นายสมชาย ใจดี"
SYNTHETIC_PHONE = "081-234-5678"
BODY_MARKER = "SYNTHETIC-REQUEST-BODY-MARKER-7F31"
TEXT = f"{BODY_MARKER} ผมชื่อ {SYNTHETIC_NAME} โทร {SYNTHETIC_PHONE} ครับ"
APP_VARIABLES = (
    "APP_AIGUARD_API_KEY",
    "APP_AIFT_ACCESS_CODE",
    "APP_AIFT_COOKIE_SIGNING_KEY",
    "APP_TOKENMIND_API_KEY",
)
CONTAINERS = tuple(f"{TEAM}-{name}-1" for name in ("web", "api", "core"))
CLIENT_ACCESS_LOG = re.compile(
    r'^INFO:\s+\S+:\d+\s+-\s+"(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s',
    re.MULTILINE,
)


class AcceptanceFailure(RuntimeError):
    pass


def child_environment() -> dict[str, str]:
    return {
        name: value
        for name, value in os.environ.items()
        if name not in APP_VARIABLES and not name.startswith("APP_")
    }


def run(*args: str) -> bytes:
    result = subprocess.run(args, capture_output=True, env=child_environment())
    if result.returncode:
        raise AcceptanceFailure("local container inspection command failed")
    return result.stdout


def request(
    base: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    cookie: str = "",
    origin: str = "",
    timeout: float = 60,
) -> tuple[int, object, bytes]:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()
    except Exception as error:
        raise AcceptanceFailure("local HTTP request failed") from error


def payload(raw: bytes) -> dict:
    try:
        result = json.loads(raw)
    except Exception as error:
        raise AcceptanceFailure("local response was not JSON") from error
    if not isinstance(result, dict):
        raise AcceptanceFailure("local response shape was invalid")
    return result


def wait_healthy() -> None:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        states = [
            run("docker", "inspect", "-f", "{{.State.Health.Status}}", name)
            .decode("ascii", "replace")
            .strip()
            for name in CONTAINERS
        ]
        if states == ["healthy", "healthy", "healthy"]:
            return
        time.sleep(2)
    raise AcceptanceFailure("local stack did not become healthy")


def login() -> str:
    access_code = os.environ.get("APP_AIFT_ACCESS_CODE", "")
    if not access_code:
        raise AcceptanceFailure("synthetic caller access configuration missing")
    status, headers, _raw = request(
        API,
        "/auth/login",
        method="POST",
        payload={"access_code": access_code},
    )
    access_code = ""
    set_cookie = headers.get("Set-Cookie", "")
    if status != 204 or not all(
        flag in set_cookie for flag in ("Secure", "HttpOnly", "SameSite=Strict")
    ):
        raise AcceptanceFailure("valid caller login or cookie flags failed")
    parsed = SimpleCookie()
    parsed.load(set_cookie)
    morsel = parsed.get("__Host-aift_session")
    if morsel is None:
        raise AcceptanceFailure("caller cookie missing")
    return f"__Host-aift_session={morsel.value}"


def verify_runtime(revision: str) -> dict:
    expected = {
        f"{TEAM}-web-1": {"memory": 256 * 1024**2, "nano_cpus": 500_000_000, "pids": 128},
        f"{TEAM}-api-1": {"memory": 256 * 1024**2, "nano_cpus": 500_000_000, "pids": 128},
        f"{TEAM}-core-1": {"memory": 2 * 1024**3, "nano_cpus": 2_000_000_000, "pids": 256},
    }
    image_ids = {}
    for name, limits in expected.items():
        raw = run("docker", "inspect", name)
        item = json.loads(raw)[0]
        label = item["Config"]["Labels"].get("org.opencontainers.image.revision")
        if label != revision:
            raise AcceptanceFailure("running revision label mismatch")
        host = item["HostConfig"]
        if host["Memory"] != limits["memory"] or host["NanoCpus"] != limits["nano_cpus"]:
            raise AcceptanceFailure("running resource limit mismatch")
        if host["PidsLimit"] != limits["pids"]:
            raise AcceptanceFailure("running process limit mismatch")
        if not host["ReadonlyRootfs"]:
            raise AcceptanceFailure("running root filesystem is writable")
        if "no-new-privileges:true" not in host.get("SecurityOpt", []):
            raise AcceptanceFailure("running no-new-privileges policy missing")
        if item["Config"].get("StopTimeout") != 210:
            raise AcceptanceFailure("running graceful stop window mismatch")
        if host["RestartPolicy"]["Name"] != "unless-stopped":
            raise AcceptanceFailure("running restart policy mismatch")
        if host["LogConfig"] != {
            "Type": "json-file",
            "Config": {"max-file": "3", "max-size": "50m"},
        }:
            raise AcceptanceFailure("running log rotation mismatch")
        image_ids[name] = item["Image"]

    core = json.loads(run("docker", "inspect", f"{TEAM}-core-1"))[0]
    api = json.loads(run("docker", "inspect", f"{TEAM}-api-1"))[0]
    web = json.loads(run("docker", "inspect", f"{TEAM}-web-1"))[0]
    if core["NetworkSettings"]["Ports"].get("8000/tcp") is not None:
        raise AcceptanceFailure("internal core port was host-published")
    expected_ports = {
        ("127.0.0.1", "20070", "3000/tcp"),
        ("127.0.0.1", "20071", "8000/tcp"),
    }
    actual_ports = set()
    for item in (web, api):
        for target, bindings in item["NetworkSettings"]["Ports"].items():
            for binding in bindings or []:
                actual_ports.add((binding["HostIp"], binding["HostPort"], target))
    if actual_ports != expected_ports:
        raise AcceptanceFailure("host port publication mismatch")
    if core["HostConfig"]["Tmpfs"] != {"/tmp": "size=128m,mode=1777"}:
        raise AcceptanceFailure("core tmpfs mismatch")
    if set(core["HostConfig"].get("CapDrop") or []) != {"ALL"}:
        raise AcceptanceFailure("core capability drop mismatch")
    if api["HostConfig"]["Tmpfs"] != {
        "/var/cache/nginx": "size=64m",
        "/var/run": "size=4m",
        "/tmp": "size=4m",
        "/etc/nginx/conf.d": "size=4m",
    }:
        raise AcceptanceFailure("api tmpfs mismatch")
    if web["HostConfig"]["Tmpfs"] != {
        "/var/cache/nginx": "size=32m",
        "/var/run": "size=4m",
        "/tmp": "size=4m",
    }:
        raise AcceptanceFailure("web tmpfs mismatch")
    return image_ids


def verify_auth_and_public_operations() -> tuple[str, dict]:
    status, _headers, _raw = request(API, "/health")
    if status != 200:
        raise AcceptanceFailure("public health failed")
    status, headers, body = request(WEB, "/")
    if status != 200 or b"Privacy Scan" not in body or b"redact-pdf" in body:
        raise AcceptanceFailure("public frontend contract failed")
    if headers.get("X-Frame-Options") != "DENY":
        raise AcceptanceFailure("frontend security headers missing")

    status, _headers, _raw = request(
        API, "/auth/login", method="POST", payload={"access_code": "invalid-synthetic-code"}
    )
    if status != 401:
        raise AcceptanceFailure("invalid caller access code was accepted")
    cookie = login()

    for supplied_cookie in ("", "__Host-aift_session=tampered"):
        status, _headers, _raw = request(
            API, "/detect", method="POST", payload={"text": "synthetic"}, cookie=supplied_cookie
        )
        if status != 401:
            raise AcceptanceFailure("missing or tampered caller cookie was accepted")
    status, _headers, _raw = request(
        API,
        "/detect",
        method="POST",
        payload={"text": "synthetic"},
        cookie=cookie,
        origin="https://example.invalid",
    )
    if status != 403:
        raise AcceptanceFailure("cross-site business request was accepted")

    status, _headers, raw = request(
        API, "/detect", method="POST", payload={"text": TEXT}, cookie=cookie
    )
    detect = payload(raw)
    if status != 200 or detect.get("detected_entity_count", 0) < 2:
        raise AcceptanceFailure("authenticated Privacy Scan failed")

    status, _headers, raw = request(
        API, "/guard", method="POST", payload={"text": TEXT}, cookie=cookie
    )
    guard = payload(raw)
    if (
        status != 200
        or type(guard.get("flagged")) is not bool
        or not isinstance(guard.get("guard_findings"), list)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("category"), str)
            or not isinstance(item.get("severity"), str)
            for item in guard["guard_findings"]
        )
    ):
        raise AcceptanceFailure("authenticated prompt-risk warning contract failed")

    status, _headers, raw = request(
        API,
        "/analyze-report",
        method="POST",
        payload={"text": TEXT},
        cookie=cookie,
        timeout=120,
    )
    report = payload(raw)
    try:
        report_bytes = base64.b64decode(report["report_pdf_b64"], validate=True)
    except Exception as error:
        raise AcceptanceFailure("PDPA report payload invalid") from error
    if status != 200 or not report_bytes.startswith(b"%PDF"):
        raise AcceptanceFailure("authenticated PDPA Report failed")

    roundtrip_modes = {}
    for mode in ("token", "surrogate"):
        status, _headers, raw = request(
            API,
            "/roundtrip",
            method="POST",
            payload={"text": TEXT, "mode": mode, "provider": "fake"},
            cookie=cookie,
            timeout=120,
        )
        roundtrip = payload(raw)
        sanitized = str(roundtrip.get("sanitized_text", ""))
        restored = str(roundtrip.get("restored_text", ""))
        counts = roundtrip.get("entity_type_counts")
        restoration = roundtrip.get("restoration") or {}
        if not (
            status == 200
            and roundtrip.get("provider_used") == "fake"
            and isinstance(counts, dict)
            and all(isinstance(name, str) and type(count) is int and count > 0 for name, count in counts.items())
            and sum(counts.values()) == roundtrip.get("detected_entity_count")
            and isinstance(roundtrip.get("section26_categories"), list)
            and isinstance(roundtrip.get("guard_findings"), list)
            and SYNTHETIC_NAME not in sanitized
            and SYNTHETIC_PHONE not in sanitized
            and SYNTHETIC_NAME in restored
            and SYNTHETIC_PHONE in restored
            and roundtrip.get("safety") == {"status": "pass", "residual_count": 0}
            and restoration.get("status") == "complete"
            and type(restoration.get("replaced_count")) is int
            and restoration.get("replaced_count") >= 0
            and restoration.get("leftover_count") == 0
            and not ({"mapping", "entities", "highlights"} & set(roundtrip))
        ):
            raise AcceptanceFailure(
                f"deterministic fake-provider {mode} safety flow failed"
            )
        roundtrip_modes[mode] = {
            "provider": "fake",
            "safety": "pass",
            "restoration": "complete",
            "raw_values_absent_from_sanitized": True,
            "raw_values_restored": True,
        }

    forbidden = (
        "/sanitize",
        "/reidentify",
        "/docs",
        "/openapi.json",
        "/redact-pdf",
        "/v1/redact-pdf",
        "/api/sanitize",
        "/metrics",
        "/admin",
    )
    for path in forbidden:
        status, _headers, _raw = request(API, path, method="GET")
        if status != 404:
            raise AcceptanceFailure("forbidden public route escaped the allowlist")

    status, logout_headers, _raw = request(
        API, "/auth/logout", method="POST", cookie=cookie
    )
    cleared_cookie = logout_headers.get("Set-Cookie", "")
    if status != 204 or not all(
        flag in cleared_cookie
        for flag in ("__Host-aift_session=", "Max-Age=0", "Secure", "HttpOnly", "SameSite=Strict")
    ):
        raise AcceptanceFailure("caller logout failed")
    return cookie, {
        "detect_entities": detect["detected_entity_count"],
        "guard": {
            "flagged": guard["flagged"],
            "finding_count": len(guard["guard_findings"]),
        },
        "report_score": report["overall_score"],
        "report_grade": report["overall_grade"],
        "roundtrip_modes": roundtrip_modes,
    }


def verify_rate_limit() -> dict:
    cookie = login()

    def one(_index: int) -> int:
        status, _headers, _raw = request(
            API,
            "/detect",
            method="POST",
            payload={"text": "synthetic concurrency"},
            cookie=cookie,
            timeout=30,
        )
        return status

    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
        statuses = list(pool.map(one, range(48)))
    if any(status not in (200, 429) for status in statuses):
        raise AcceptanceFailure("short concurrency produced an unbounded status")
    if 200 not in statuses or 429 not in statuses:
        raise AcceptanceFailure("local rate-limit behavior was not observed")
    return {str(status): statuses.count(status) for status in sorted(set(statuses))}


def resource_snapshot() -> dict:
    rows = run(
        "docker",
        "stats",
        "--no-stream",
        "--format",
        "{{json .}}",
        *CONTAINERS,
    ).decode("utf-8", "replace").splitlines()
    result = {}
    for row in rows:
        item = json.loads(row)
        result[item["Name"]] = {
            "memory": item["MemUsage"],
            "memory_percent": item["MemPerc"],
            "cpu": item["CPUPerc"],
        }
    return result


def scan_logs(cookie: str) -> None:
    chunks = []
    for name in CONTAINERS:
        result = subprocess.run(
            ["docker", "logs", name],
            capture_output=True,
            env=child_environment(),
        )
        if result.returncode:
            raise AcceptanceFailure("local container log read failed")
        chunks.extend((result.stdout, result.stderr))
    logs = b"\n".join(chunks).decode("utf-8", "replace")
    markers = [cookie, SYNTHETIC_NAME, SYNTHETIC_PHONE, BODY_MARKER]
    markers.extend(os.environ.get(name, "") for name in APP_VARIABLES)
    if any(marker and marker in logs for marker in markers):
        raise AcceptanceFailure("synthetic sensitive marker reached retained logs")
    if CLIENT_ACCESS_LOG.search(logs):
        raise AcceptanceFailure("client metadata reached retained runtime logs")


def restart_and_verify(revision: str) -> None:
    prior_cookie = login()
    run("docker", "restart", *CONTAINERS)
    wait_healthy()
    verify_runtime(revision)
    status, _headers, _raw = request(
        API,
        "/detect",
        method="POST",
        payload={"text": "synthetic expired restart probe"},
        cookie=prior_cookie,
    )
    if status != 401:
        raise AcceptanceFailure("restart revived prior session authority")
    cookie = login()
    status, _headers, raw = request(
        API,
        "/detect",
        method="POST",
        payload={"text": "synthetic restart probe"},
        cookie=cookie,
    )
    if status != 200 or "detected_entity_count" not in payload(raw):
        raise AcceptanceFailure("post-restart fresh session request failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()
    revision = os.environ.get("AIFT_EXPECTED_REVISION", "")
    if len(revision) != 40:
        print("local release acceptance failed: exact revision is missing")
        return 1
    started = time.monotonic()
    try:
        wait_healthy()
        image_ids = verify_runtime(revision)
        idle = resource_snapshot()
        cookie, operations = verify_auth_and_public_operations()
        after_operations = resource_snapshot()
        rate_limit = verify_rate_limit()
        after_load = resource_snapshot()
        scan_logs(cookie)
        if args.restart:
            restart_and_verify(revision)
            scan_logs("")
        result = {
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "revision": revision,
            "provider_mode": "deterministic-fake-only",
            "image_ids": image_ids,
            "operations": operations,
            "rate_limit_statuses": rate_limit,
            "resources": {
                "idle": idle,
                "after_operations": after_operations,
                "after_short_load": after_load,
            },
            "restart_recovery": bool(args.restart),
            "seconds": round(time.monotonic() - started, 1),
        }
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"local-release-{revision[:12]}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            "local release acceptance passed: provider-free auth/routes/report/fake flow, "
            "logs, rate limiting, resources, restart/recovery"
        )
        print(f"aggregate evidence: {path.relative_to(ROOT)}")
        return 0
    except AcceptanceFailure as error:
        print(f"local release acceptance failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

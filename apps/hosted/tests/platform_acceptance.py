#!/usr/bin/env python3
"""Value-safe post-deploy acceptance for the exact running team08 stack.

Application credentials are read from inherited environment only. They are
used inside this process for HTTP requests and in-memory log comparisons;
none is placed in a child-process argument or printed on failure.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.cookies import SimpleCookie

TEAM = os.environ.get("TEAM", "team08")
PORT = os.environ.get("BASE_1", "20071")
WEB_PORT = os.environ.get("BASE", "20070")
BASE_URL = f"http://127.0.0.1:{PORT}"
PUBLIC_HOST = os.environ.get("AIFT_PUBLIC_HOST", f"{TEAM}.aiforthai.in.th")
CI_JOB_ID = os.environ.get("CI_JOB_ID", "").strip()
EXPECTED_REVISION = os.environ.get("CI_COMMIT_SHA", "local-working-tree")
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
SYNTHETIC_TEXT = "ผมชื่อ นายสมชาย ใจดี โทร 081-234-5678"
APP_VARIABLES = (
    "APP_AIGUARD_API_KEY",
    "APP_AIFT_ACCESS_CODE",
    "APP_AIFT_COOKIE_SIGNING_KEY",
    "APP_AIFT_PRIORITY_INVITES_JSON",
    "APP_TOKENMIND_API_KEY",
)
CLIENT_ACCESS_LOG = re.compile(
    r'^INFO:\s+\S+:\d+\s+-\s+"(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s',
    re.MULTILINE,
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


def _single_identifier(output: bytes, failure: str) -> str:
    identifiers = [
        line.strip()
        for line in output.decode("ascii", "replace").splitlines()
        if line.strip()
    ]
    if len(identifiers) != 1:
        raise AcceptanceFailure(failure)
    return identifiers[0]


def _resolve_job_container() -> str:
    return _single_identifier(
        _run(
            "docker",
            "ps",
            "-q",
            "--filter",
            f"label=com.gitlab.gitlab-runner.job.id={CI_JOB_ID}",
            "--filter",
            "label=com.gitlab.gitlab-runner.type=build",
        ),
        "could not uniquely resolve the acceptance job container",
    )


def _resolve_compose_network() -> str:
    return _single_identifier(
        _run(
            "docker",
            "network",
            "ls",
            "-q",
            "--filter",
            f"label=com.docker.compose.project={TEAM}",
            "--filter",
            "label=com.docker.compose.network=default",
        ),
        "could not uniquely resolve the production network",
    )


@contextmanager
def _reachable_api():
    """Temporarily join this Docker-executor job to the Compose network."""

    global BASE_URL
    if not CI_JOB_ID:
        yield
        return

    job_container = _resolve_job_container()
    network = _resolve_compose_network()
    _run("docker", "network", "connect", network, job_container)
    previous_base = BASE_URL
    BASE_URL = "http://api:8000"
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        BASE_URL = previous_base
        result = subprocess.run(
            ["docker", "network", "disconnect", network, job_container],
            capture_output=True,
            env=_value_free_child_environment(),
        )
        if result.returncode and not failed:
            raise AcceptanceFailure("acceptance job network cleanup failed")


def _request(
    path: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    raw_payload: bytes | None = None,
    content_type: str = "application/json",
    cookie: str = "",
    origin: str = "",
    timeout: float = 30,
) -> tuple[int, object, bytes]:
    body = None
    # This direct path validates the deployed api/core stack while deliberately
    # bypassing the organizer edge, TLS, prefix stripping, and host publication.
    # Preserve the real public Host contract; test those edge behaviors later.
    headers = {"Host": PUBLIC_HOST}
    if payload is not None and raw_payload is not None:
        raise AcceptanceFailure("public request body configuration was invalid")
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = content_type
    elif raw_payload is not None:
        body = raw_payload
        headers["Content-Type"] = content_type
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    request = urllib.request.Request(
        BASE_URL + path, data=body, headers=headers, method=method
    )
    try:
        # Never let runner-level HTTP(S)_PROXY settings receive the access
        # code, signed cookie, or synthetic request. This path is Docker DNS.
        with DIRECT_OPENER.open(request, timeout=timeout) as response:
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


def _start_standard() -> str:
    status, headers, _body = _request("/auth/guest", method="POST", payload={})
    if status != 201:
        raise AcceptanceFailure("Standard authority start failed")
    raw_cookie = headers.get("Set-Cookie", "")
    parsed = SimpleCookie()
    parsed.load(raw_cookie)
    morsel = parsed.get("__Host-aift_guest")
    if morsel is None or not all(
        flag in raw_cookie for flag in ("Secure", "HttpOnly", "SameSite=Strict")
    ):
        raise AcceptanceFailure("Standard authority cookie was invalid")
    return f"__Host-aift_guest={morsel.value}"


def _verify_revisions() -> None:
    expected = {
        "web": (
            256 * 1024**2,
            500_000_000,
            128,
            {
                "/var/cache/nginx": "size=32m,uid=101,gid=101,mode=0755",
                "/var/run": "size=4m,uid=101,gid=101,mode=0755",
                "/tmp": "size=4m,uid=101,gid=101,mode=1777",
            },
        ),
        "api": (
            256 * 1024**2,
            500_000_000,
            128,
            {
                "/var/cache/nginx": "size=64m,uid=101,gid=101,mode=0755",
                "/var/run": "size=4m,uid=101,gid=101,mode=0755",
                "/tmp": "size=4m,uid=101,gid=101,mode=1777",
                "/etc/nginx/conf.d": "size=4m,uid=101,gid=101,mode=0755",
            },
        ),
        "core": (2 * 1024**3, 2_000_000_000, 256, {"/tmp": "size=128m,mode=1777"}),
        "pdf-parser": (
            512 * 1024**2,
            1_000_000_000,
            32,
            {"/work": "rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=0700"},
        ),
    }
    for service in ("web", "api", "core", "pdf-parser"):
        container = f"{TEAM}-{service}-1"
        # Narrow projections only. A full Docker inspect includes Config.Env
        # and would unnecessarily retrieve production credential values.
        actual = _run(
            "docker",
            "inspect",
            "-f",
            '{{ index .Config.Labels "org.opencontainers.image.revision" }}',
            container,
        ).decode("ascii", "replace").strip()
        if actual != EXPECTED_REVISION:
            raise AcceptanceFailure("running image revision mismatch")
        host = json.loads(
            _run("docker", "inspect", "-f", "{{json .HostConfig}}", container)
        )
        stop_timeout = int(
            _run("docker", "inspect", "-f", "{{.Config.StopTimeout}}", container)
            .decode("ascii", "replace")
            .strip()
        )
        memory, nano_cpus, pids, tmpfs = expected[service]
        if (host["Memory"], host["NanoCpus"], host["PidsLimit"]) != (
            memory,
            nano_cpus,
            pids,
        ):
            raise AcceptanceFailure("running resource limit mismatch")
        if (
            not host["ReadonlyRootfs"]
            or "no-new-privileges:true" not in host.get("SecurityOpt", [])
            or stop_timeout != 210
            or host["RestartPolicy"]["Name"] != "unless-stopped"
        ):
            raise AcceptanceFailure("running isolation/recovery policy mismatch")
        if host["LogConfig"] != {
            "Type": "json-file",
            "Config": {"max-file": "3", "max-size": "50m"},
        }:
            raise AcceptanceFailure("running log rotation mismatch")
        if host.get("Tmpfs") != tmpfs:
            raise AcceptanceFailure("running volatile-storage policy mismatch")
        bindings = host.get("PortBindings") or {}
        expected_binding = {
            "web": {"3000/tcp": [{"HostIp": "127.0.0.1", "HostPort": WEB_PORT}]},
            "api": {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": PORT}]},
            "core": {},
            "pdf-parser": {},
        }[service]
        if bindings != expected_binding:
            raise AcceptanceFailure("running public-port boundary mismatch")
    core_host = json.loads(
        _run(
            "docker",
            "inspect",
            "-f",
            "{{json .HostConfig}}",
            f"{TEAM}-core-1",
        )
    )
    if set(core_host.get("CapDrop") or []) != {"ALL"}:
        raise AcceptanceFailure("running core capability policy mismatch")
    parser_host = json.loads(
        _run("docker", "inspect", "-f", "{{json .HostConfig}}", f"{TEAM}-pdf-parser-1")
    )
    if parser_host.get("NetworkMode") != "none":
        raise AcceptanceFailure("running parser network isolation mismatch")


def _claim_ready(capability: str, cookie: str) -> str:
    revision = 0
    for _attempt in range(4):
        status, _headers, raw = _request(
            "/provider-queue/claim",
            method="POST",
            payload={"queue_capability": capability, "last_revision": revision},
            cookie=cookie,
            timeout=35,
        )
        if status != 200:
            raise AcceptanceFailure("provider queue claim failed")
        body = _json(raw)
        revision = body.get("revision", revision)
        if body.get("state") == "claim_ready" and isinstance(
            body.get("claim_token"), str
        ):
            return body["claim_token"]
        if body.get("state") not in {"queued", "paused"}:
            raise AcceptanceFailure("provider queue entered an unexpected state")
        time.sleep(1)
    raise AcceptanceFailure("provider queue did not issue a claim")


def _join(ticket: str, cookie: str) -> tuple[str, str]:
    status, _headers, raw = _request(
        "/provider-queue/join",
        method="POST",
        payload={"ticket": ticket},
        cookie=cookie,
    )
    if status != 201:
        raise AcceptanceFailure("provider queue join failed")
    body = _json(raw)
    capability = body.get("queue_capability")
    if not isinstance(capability, str):
        raise AcceptanceFailure("provider queue capability missing")
    return capability, _claim_ready(capability, cookie)


def _custom_result_status(result: dict, *, expected_protected: str) -> str | None:
    safety = result.get("safety") or {}
    restoration = result.get("restoration") or {}
    receipt = result.get("receipt") or {}
    provider = result.get("provider") or {}
    warnings = result.get("warnings")
    status = restoration.get("status")
    leftover = restoration.get("leftover_count")
    restored_text = result.get("restored_text")
    warnings_valid = isinstance(warnings, list) and all(
        isinstance(warning, dict)
        and set(warning) == {"code", "count"}
        and warning.get("code") in {"foreign_replacement", "generated_pii"}
        and type(warning.get("count")) is int
        and warning["count"] > 0
        for warning in warnings
    )
    classified = bool(
        type(leftover) is int
        and leftover >= 0
        and warnings_valid
        and (
            (
                status == "complete"
                and leftover == 0
                and warnings == []
                and isinstance(restored_text, str)
                and bool(restored_text)
            )
            or (
                status == "incomplete"
                and leftover > 0
                and warnings == []
                and restored_text == ""
            )
            or (status == "unsafe" and bool(warnings) and restored_text == "")
        )
    )
    request_id = result.get("request_id")
    provider_attempts = provider.get("attempt_count")
    receipt_attempts = receipt.get("provider_attempt_count")
    valid = bool(
        result.get("hosted_version") == "0.1.0"
        and result.get("source_kind") == "custom_standard"
        and safety == {"status": "pass", "residual_count": 0}
        and classified
        and result.get("protected_text") == expected_protected
        and "สมชาย" not in expected_protected
        and "test@example.invalid" not in expected_protected
        and isinstance(request_id, str)
        and request_id
        and receipt.get("request_id") == request_id
        and receipt.get("hosted_version") == result.get("hosted_version")
        and receipt.get("source_kind") == result.get("source_kind")
        and receipt.get("restoration_status") == status
        and receipt.get("digest_match") is True
        and receipt.get("outbound_gate_status") == "no_residual_signal_detected"
        and provider.get("id") == "tokenmind"
        and provider.get("model") == "thaillm-8b"
        and type(provider_attempts) is int
        and 1 <= provider_attempts <= 3
        and receipt.get("provider_id") == provider.get("id")
        and receipt.get("provider_model") == provider.get("model")
        and type(receipt_attempts) is int
        and receipt_attempts == provider_attempts
        and isinstance(restored_text, str)
    )
    return status if valid else None


def _verify_hosted3_custom(cookie: str) -> str:
    source = "ผู้สมัครสังเคราะห์ สมชาย ใจดี ติดต่อ test@example.invalid"
    status, headers, raw = _request(
        "/protection-preview",
        method="POST",
        payload={"text": source, "mode": "token"},
        cookie=cookie,
    )
    if status != 200 or headers.get("X-AIGuard-Service-Class") != "standard":
        raise AcceptanceFailure("Hosted 3 custom preview failed")
    preview = _json(raw)
    protected = str(preview.get("protected_text", ""))
    ticket = preview.get("ticket")
    if not (
        preview.get("can_execute") is True
        and isinstance(ticket, str)
        and "สมชาย" not in protected
        and "test@example.invalid" not in protected
    ):
        raise AcceptanceFailure("Hosted 3 custom preview boundary failed")
    capability, claim = _join(ticket, cookie)
    status, _headers, raw = _request(
        "/protection-execute",
        method="POST",
        payload={"text": source, "queue_capability": capability, "claim_token": claim},
        cookie=cookie,
        timeout=210,
    )
    if status != 200:
        raise AcceptanceFailure("Hosted 3 custom execute failed")
    result = _json(raw)
    restoration_status = _custom_result_status(result, expected_protected=protected)
    if restoration_status is None:
        raise AcceptanceFailure("Hosted 3 custom result gates failed")
    return restoration_status


def _verify_hosted3_document(cookie: str) -> None:
    fixture = (
        Path(__file__).resolve().parent.parent
        / "pdf-parser/scenarios/hr-resume-pdf-structured-v1.pdf"
    ).read_bytes()
    status, _headers, raw = _request(
        "/document-preview",
        method="POST",
        raw_payload=fixture,
        content_type="application/pdf",
        cookie=cookie,
        timeout=30,
    )
    fixture = b""
    if status != 200:
        raise AcceptanceFailure("Hosted 3 document preview failed")
    preview = _json(raw)
    ticket = preview.get("ticket")
    protected = preview.get("protected_text")
    if not (
        preview.get("can_execute") is True
        and isinstance(ticket, str)
        and isinstance(protected, str)
        and protected
    ):
        raise AcceptanceFailure("Hosted 3 document preview gates failed")
    capability, claim = _join(ticket, cookie)
    status, _headers, raw = _request(
        "/document-execute",
        method="POST",
        payload={
            "protected_text": protected,
            "queue_capability": capability,
            "claim_token": claim,
        },
        cookie=cookie,
        timeout=210,
    )
    protected = ""
    if status != 200:
        raise AcceptanceFailure("Hosted 3 document execute failed")
    artifact = _json(raw)
    if not (
        artifact.get("hosted_version") == "0.1.0"
        and artifact.get("source_kind") == "document_standard"
        and isinstance(artifact.get("protected_markdown"), str)
        and "PII was not restored" in artifact["protected_markdown"]
        and "restored_text" not in artifact
        and isinstance(artifact.get("receipt"), dict)
    ):
        raise AcceptanceFailure("Hosted 3 protected document artifact failed")


def _verify_usable_custom_release_path() -> list[str]:
    standard_cookies: list[str] = []
    for attempt in range(3):
        standard_cookie = _start_standard()
        standard_cookies.append(standard_cookie)
        status, headers, _body = _request(
            "/auth/session", method="GET", cookie=standard_cookie
        )
        if status != 200 or headers.get("X-AIGuard-Service-Class") != "standard":
            raise AcceptanceFailure("Standard authority verification failed")
        restoration_status = _verify_hosted3_custom(standard_cookie)
        print(
            "Hosted 3 custom live classification "
            f"attempt {attempt + 1}: {restoration_status}"
        )
        status, _headers, _body = _request(
            "/auth/guest/end", method="POST", payload={}, cookie=standard_cookie
        )
        if status != 204:
            raise AcceptanceFailure("Standard authority end failed")
        if restoration_status == "complete":
            return standard_cookies
    raise AcceptanceFailure(
        "Hosted 3 custom path produced no usable result after bounded attempts"
    )


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
    # The production core has a read-only root filesystem. Stream this fixed,
    # tracked probe over stdin instead of copying it into /app. The probe then
    # reads its already-scoped caller configuration only inside the container;
    # no credential value enters child argv, output, or the acceptance process.
    probe = (Path(__file__).resolve().parent / "runner_route_probe.py").read_bytes()
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", "-"],
        input=probe,
        capture_output=True,
        env=_value_free_child_environment(),
    )
    if result.returncode:
        raise AcceptanceFailure("PDPA report route probe failed")


def _verify_logs(*cookies: str) -> None:
    markers = [*cookies, "สมชาย", "081-234-5678", "test@example.invalid"]
    markers.extend(value for name in APP_VARIABLES if (value := os.environ.get(name, "")))
    for service in ("web", "api", "core", "pdf-parser"):
        logs = _run("docker", "logs", f"{TEAM}-{service}-1").decode(
            "utf-8", "replace"
        )
        if any(marker and marker in logs for marker in markers):
            raise AcceptanceFailure("sensitive value reached retained runtime logs")
        if CLIENT_ACCESS_LOG.search(logs):
            raise AcceptanceFailure("client metadata reached retained runtime logs")


def main() -> int:
    try:
        with _reachable_api():
            _verify_revisions()
            status, _headers, raw_health = _request("/health")
            if status != 200:
                raise AcceptanceFailure("public health failed")
            if _json(raw_health).get("version") != "0.1.0":
                raise AcceptanceFailure("public health version mismatch")

            priority_cookie = _login()
            status, headers, _body = _request(
                "/auth/session", method="GET", cookie=priority_cookie
            )
            if status != 200 or headers.get("X-AIGuard-Service-Class") != "priority":
                raise AcceptanceFailure("Priority authority verification failed")
            _verify_public_contract(priority_cookie)
            _verify_live_roundtrip(priority_cookie)
            _verify_report_probe()
            status, _headers, _body = _request(
                "/auth/logout", method="POST", cookie=priority_cookie
            )
            if status != 204:
                raise AcceptanceFailure("caller logout failed")
            status, _headers, _body = _request(
                "/detect",
                method="POST",
                payload={"text": "synthetic revoked-session probe"},
                cookie=priority_cookie,
            )
            if status != 401:
                raise AcceptanceFailure("logged-out caller cookie remained usable")

            standard_cookies = _verify_usable_custom_release_path()

            document_cookie = _start_standard()
            standard_cookies.append(document_cookie)
            _verify_hosted3_document(document_cookie)
            _verify_logs(priority_cookie, *standard_cookies)
            status, _headers, _body = _request(
                "/auth/guest/end", method="POST", payload={}, cookie=document_cookie
            )
            if status != 204:
                raise AcceptanceFailure("Standard authority end failed")
            priority_cookie = ""
            standard_cookie = ""
            document_cookie = ""
        print(
            "platform acceptance passed: Priority legacy, Standard Hosted 3 text/PDF, "
            "queue/provider/artifacts, allowlist, report, resources, logs"
        )
        return 0
    except AcceptanceFailure as error:
        print(f"platform acceptance failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

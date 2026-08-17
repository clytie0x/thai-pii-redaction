#!/usr/bin/env python3
"""Deterministic contract for Docker-executor production acceptance topology."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent


def load_acceptance():
    path = ROOT / "tests" / "platform_acceptance.py"
    spec = importlib.util.spec_from_file_location("platform_acceptance_contract_target", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load platform acceptance helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Completed:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode


class Response:
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    @staticmethod
    def read() -> bytes:
        return b"{}"


def main() -> int:
    acceptance = load_acceptance()
    acceptance_source = (ROOT / "tests" / "platform_acceptance.py").read_text(
        encoding="utf-8"
    )
    public_source = (ROOT / "tests" / "public_web_acceptance.py").read_text(
        encoding="utf-8"
    )
    for marker in (
        "HOSTED3_CANONICAL_PATHS",
        'method="DELETE"',
        '"/v1" + canonical',
        'status in {401, 405, 429}',
        '"method_not_allowed"',
        '"/api/auth/guestx"',
        '"/api/v1/document-preview/x"',
    ):
        if marker not in public_source:
            raise AssertionError(f"public Hosted 3 route acceptance missing: {marker}")
    if '_run("docker", "inspect", f"{TEAM}-' in acceptance_source:
        raise AssertionError("production acceptance can perform a full secret-bearing inspect")
    if '"docker", "cp"' in acceptance_source:
        raise AssertionError("production acceptance writes a probe into the read-only core")
    for marker in ('"docker", "exec", "-i"', 'container, "python", "-"', "input=probe"):
        if marker not in acceptance_source:
            raise AssertionError("production report probe is not streamed over stdin")
    if "{{json .HostConfig}}" not in acceptance_source or "{{.Config.StopTimeout}}" not in acceptance_source:
        raise AssertionError("production acceptance lacks narrow runtime-policy projections")
    proxy_handlers = [
        handler
        for handler in acceptance.DIRECT_OPENER.handlers
        if isinstance(handler, acceptance.urllib.request.ProxyHandler)
    ]
    if any(handler.proxies for handler in proxy_handlers):
        raise AssertionError("acceptance internal requests can inherit an ambient proxy")
    acceptance.CI_JOB_ID = "24680"
    original_base = acceptance.BASE_URL
    docker_calls: list[tuple[str, ...]] = []
    disconnect_calls: list[list[str]] = []

    def fake_run(*args: str) -> bytes:
        docker_calls.append(args)
        if args[:3] == ("docker", "ps", "-q"):
            return b"job-container-id\n"
        if args[:4] == ("docker", "network", "ls", "-q"):
            return b"compose-network-id\n"
        if args[:3] == ("docker", "network", "connect"):
            return b""
        raise AssertionError(f"unexpected Docker call: {args!r}")

    def fake_subprocess_run(args, **_kwargs):
        disconnect_calls.append(list(args))
        return Completed()

    with patch.object(acceptance, "_run", side_effect=fake_run), patch.object(
        acceptance.subprocess, "run", side_effect=fake_subprocess_run
    ):
        try:
            with acceptance._reachable_api():
                if acceptance.BASE_URL != "http://api:8000":
                    raise AssertionError("CI acceptance did not use Compose service DNS")
                raise RuntimeError("synthetic acceptance failure")
        except RuntimeError:
            pass

    if acceptance.BASE_URL != original_base:
        raise AssertionError("acceptance base URL survived cleanup")
    expected_disconnect = [
        "docker",
        "network",
        "disconnect",
        "compose-network-id",
        "job-container-id",
    ]
    if disconnect_calls != [expected_disconnect]:
        raise AssertionError("acceptance job was not disconnected after failure")
    expected_connect = (
        "docker",
        "network",
        "connect",
        "compose-network-id",
        "job-container-id",
    )
    if expected_connect not in docker_calls:
        raise AssertionError("acceptance job used the wrong network-connect target")

    flattened = [item for call in docker_calls for item in call]
    for required in (
        "label=com.gitlab.gitlab-runner.job.id=24680",
        "label=com.gitlab.gitlab-runner.type=build",
        "label=com.docker.compose.project=team08",
        "label=com.docker.compose.network=default",
    ):
        if required not in flattened:
            raise AssertionError(f"missing exact Docker identity filter: {required}")

    captured = {}

    def fake_urlopen(request, **_kwargs):
        captured["host"] = request.get_header("Host")
        return Response()

    acceptance.BASE_URL = "http://api:8000"
    with patch.object(acceptance.DIRECT_OPENER, "open", side_effect=fake_urlopen):
        status, _headers, _body = acceptance._request("/health")
    if status != 200 or captured.get("host") != "team08.aiforthai.in.th":
        raise AssertionError("acceptance did not preserve the public Host contract")

    with patch.object(acceptance, "_run", return_value=b"one\ntwo\n"):
        try:
            acceptance._resolve_job_container()
        except acceptance.AcceptanceFailure:
            pass
        else:
            raise AssertionError("ambiguous job-container resolution did not fail closed")

    print(
        "platform acceptance contract ok: exact runner/container network, public Host, cleanup"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

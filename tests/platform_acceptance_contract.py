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

    base_result = {
        "request_id": "req_complete",
        "hosted_version": "3.0.1",
        "source_kind": "custom_standard",
        "protected_text": "[NAME_1] [EMAIL_1]",
        "restored_text": "synthetic result",
        "warnings": [],
        "safety": {"status": "pass", "residual_count": 0},
        "restoration": {"status": "complete", "leftover_count": 0},
        "provider": {"id": "tokenmind", "model": "thaillm-8b", "attempt_count": 1},
        "receipt": {
            "restoration_status": "complete",
            "request_id": "req_complete",
            "hosted_version": "3.0.1",
            "source_kind": "custom_standard",
            "digest_match": True,
            "outbound_gate_status": "no_residual_signal_detected",
            "provider_id": "tokenmind",
            "provider_model": "thaillm-8b",
            "provider_attempt_count": 1,
        },
    }
    if acceptance._custom_result_status(
        base_result, expected_protected="[NAME_1] [EMAIL_1]"
    ) != "complete":
        raise AssertionError("complete custom result did not pass acceptance")
    incomplete_result = {
        **base_result,
        "request_id": "req_incomplete",
        "restored_text": "",
        "warnings": [],
        "restoration": {"status": "incomplete", "leftover_count": 1},
        "receipt": {
            **base_result["receipt"],
            "request_id": "req_incomplete",
            "restoration_status": "incomplete",
        },
    }
    if acceptance._custom_result_status(
        incomplete_result, expected_protected="[NAME_1] [EMAIL_1]"
    ) != "incomplete":
        raise AssertionError("truthfully classified incomplete result did not pass safety subgate")
    unsafe_result = {
        **base_result,
        "request_id": "req_unsafe",
        "restored_text": "",
        "warnings": [{"code": "generated_pii", "count": 1}],
        "restoration": {"status": "unsafe", "leftover_count": 0},
        "receipt": {
            **base_result["receipt"],
            "request_id": "req_unsafe",
            "restoration_status": "unsafe",
        },
    }
    if acceptance._custom_result_status(
        unsafe_result, expected_protected="[NAME_1] [EMAIL_1]"
    ) != "unsafe":
        raise AssertionError("truthfully classified unsafe custom result did not pass fail-closed acceptance")
    mismatched_result = {
        **unsafe_result,
        "receipt": {**unsafe_result["receipt"], "restoration_status": "complete"},
    }
    if acceptance._custom_result_status(
        mismatched_result, expected_protected="[NAME_1] [EMAIL_1]"
    ) is not None:
        raise AssertionError("mismatched restoration receipt passed acceptance")
    for malformed in (
        {**incomplete_result, "warnings": [{"code": "generated_pii", "count": 1}]},
        {**unsafe_result, "warnings": [], "restoration": {"status": "unsafe", "leftover_count": 1}},
        {**base_result, "restoration": {"status": "complete", "leftover_count": True}},
        {**unsafe_result, "warnings": [{"code": "unknown", "count": 1}]},
        {**unsafe_result, "restored_text": "unsafe result"},
        {**base_result, "protected_text": "สมชาย test@example.invalid"},
        {**base_result, "request_id": "", "receipt": {**base_result["receipt"], "request_id": ""}},
        {**base_result, "provider": {**base_result["provider"], "attempt_count": True}, "receipt": {**base_result["receipt"], "provider_attempt_count": True}},
    ):
        if acceptance._custom_result_status(
            malformed, expected_protected="[NAME_1] [EMAIL_1]"
        ) is not None:
            raise AssertionError("malformed custom restoration combination passed acceptance")

    def session_or_end(path: str, **_kwargs):
        if path == "/auth/session":
            return 200, {"X-AIGuard-Service-Class": "standard"}, b"{}"
        if path == "/auth/guest/end":
            return 204, {}, b""
        raise AssertionError(f"unexpected custom release request: {path}")

    with patch.object(
        acceptance, "_start_standard", side_effect=["cookie-1"]
    ) as start_once, patch.object(
        acceptance, "_verify_hosted3_custom", return_value="complete"
    ) as verify_once, patch.object(
        acceptance, "_request", side_effect=session_or_end
    ) as request_once:
        if acceptance._verify_usable_custom_release_path() != ["cookie-1"]:
            raise AssertionError("complete custom release path did not stop after one run")
        if start_once.call_count != 1 or verify_once.call_count != 1 or request_once.call_count != 2:
            raise AssertionError("complete custom release path repeated authority work")

    with patch.object(
        acceptance, "_start_standard", side_effect=["cookie-1", "cookie-2", "cookie-3"]
    ) as start_three, patch.object(
        acceptance,
        "_verify_hosted3_custom",
        side_effect=["unsafe", "incomplete", "complete"],
    ) as verify_three, patch.object(
        acceptance, "_request", side_effect=session_or_end
    ) as request_three:
        if acceptance._verify_usable_custom_release_path() != [
            "cookie-1",
            "cookie-2",
            "cookie-3",
        ]:
            raise AssertionError("bounded custom release path lost authority history")
        if [call.args[0] for call in verify_three.call_args_list] != [
            "cookie-1",
            "cookie-2",
            "cookie-3",
        ]:
            raise AssertionError("custom release retries did not use fresh authorities")
        if start_three.call_count != 3 or request_three.call_count != 6:
            raise AssertionError("custom release retry lifecycle count drift")

    with patch.object(
        acceptance, "_start_standard", side_effect=["cookie-1", "cookie-2", "cookie-3"]
    ), patch.object(
        acceptance,
        "_verify_hosted3_custom",
        side_effect=["unsafe", "incomplete", "unsafe"],
    ), patch.object(acceptance, "_request", side_effect=session_or_end):
        try:
            acceptance._verify_usable_custom_release_path()
        except acceptance.AcceptanceFailure:
            pass
        else:
            raise AssertionError("three non-usable custom results approved release")
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

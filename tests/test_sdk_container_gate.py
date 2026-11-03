"""Docker checks must stay local and remove only their verified test containers."""

import itertools
import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts import check_sdk_container as gate

CID_A, CID_B = "a" * 64, "b" * 64


def result(stdout="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)


def test_docker_transport_uses_local_socket_and_no_operator_credentials(monkeypatch):
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return result()

    monkeypatch.setenv("DOCKER_HOST", "ssh://production.example")
    monkeypatch.setenv("AIFORTHAI_API_KEY", "private-marker")
    monkeypatch.setattr(gate.subprocess, "run", run)
    gate.Docker("docker", "synthetic-owner").call(["version"])
    assert seen["command"][:3] == ["docker", "--host", "unix:///var/run/docker.sock"]
    assert "DOCKER_HOST" not in seen["env"]
    assert "private-marker" not in seen["env"].values()
    assert 0 < seen["timeout"] <= 40


def test_create_uses_network_none_and_never_a_secret_in_argv(tmp_path, monkeypatch):
    docker = gate.Docker("docker", "synthetic-owner")
    seen = []
    monkeypatch.setattr(
        docker, "call", lambda command, **kwargs: seen.append(command) or result(CID_A)
    )
    env_file = tmp_path / "private.key"
    env_file.write_text("AMPHRANG_API_KEY=private-marker", encoding="utf-8")
    assert docker.create("sha256:" + CID_B, env_file) == CID_A
    assert seen[0][seen[0].index("--network") + 1] == "none"
    assert "--publish" not in seen[0] and "-p" not in seen[0]
    assert "private-marker" not in str(seen)


def test_cleanup_does_not_remove_a_foreign_label(monkeypatch):
    docker = gate.Docker("docker", "synthetic-owner")
    docker.created = {"owned-name": CID_A}
    calls = []
    monkeypatch.setattr(
        docker,
        "call",
        lambda command, **kwargs: calls.append(command) or result(CID_A + " foreign-owner"),
    )
    assert not docker.cleanup()
    assert not any("rm" in command for command in calls)


def test_cleanup_continues_after_one_container_inspection_fails(monkeypatch):
    docker = gate.Docker("docker", "synthetic-owner")
    docker.created = {"first": CID_A, "second": CID_B}
    calls = []

    def call(command, **kwargs):
        calls.append(command)
        if command[-1] == "first":
            raise OSError("synthetic daemon failure")
        if "inspect" in command:
            return result(CID_B + " synthetic-owner")
        return result()

    monkeypatch.setattr(docker, "call", call)
    assert not docker.cleanup()
    assert any("rm" in command and CID_B in command for command in calls)


def test_missing_key_timeout_is_a_failure_not_expected_refusal(monkeypatch):
    docker = gate.Docker("docker", "synthetic-owner")
    monkeypatch.setattr(docker, "call", lambda *_a, **_k: result("true 0"))
    clock = itertools.count()
    monkeypatch.setattr(gate.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(gate.time, "sleep", lambda _: None)
    with pytest.raises(gate.CheckFailed):
        docker.require_refusal(CID_A)


@pytest.mark.parametrize("change", ["extra", "http", "auth", "type"])
def test_probe_report_cannot_hide_a_failure_or_extra_body(change):
    payload = dict(gate.EXPECTED)
    if change == "extra":
        payload["mapping"] = "private-marker"
    elif change == "http":
        payload["sanitize"] = 500
    elif change == "auth":
        payload["wrong_key"] = 200
    else:
        payload["phone_masked"] = 1
    with pytest.raises(gate.CheckFailed) as error:
        gate.validate_probe(json.dumps(payload))
    assert "private-marker" not in str(error.value)


def test_nonzero_docker_call_fails_without_reflecting_output(monkeypatch):
    monkeypatch.setattr(gate.subprocess, "run", lambda *a, **k: result("private-marker", 1))
    with pytest.raises(gate.CheckFailed) as error:
        gate.Docker("docker", "synthetic-owner").call(["version"])
    assert "private-marker" not in str(error.value)


@pytest.mark.parametrize(
    "state,logs",
    [("false 0", "without AMPHRANG_API_KEY"), ("false 1", "unrelated startup failure")],
)
def test_missing_key_requires_the_specific_refusal_and_exit_code(monkeypatch, state, logs):
    docker = gate.Docker("docker", "synthetic-owner")
    monkeypatch.setattr(
        docker,
        "call",
        lambda arguments, **kwargs: result(logs if arguments[0] == "logs" else state),
    )
    with pytest.raises(gate.CheckFailed):
        docker.require_refusal(CID_A)


@pytest.mark.parametrize("failure", [None, "probe", "cleanup", "cleanup_exception"])
def test_full_gate_cleans_generated_key_even_when_probe_or_cleanup_fails(tmp_path, failure):
    class Engine:
        key_file = None
        cleaned = False

        def image(self, *_args):
            return "sha256:" + CID_A

        def create(self, image, env_file=None):
            self.key_file = env_file or self.key_file
            return CID_B

        def call(self, arguments, **kwargs):
            if arguments[0] == "exec":
                if failure == "probe":
                    raise gate.CheckFailed("synthetic_probe_failed")
                return result(json.dumps(gate.EXPECTED))
            return result()

        def require_refusal(self, identifier):
            pass

        def cleanup(self):
            self.cleaned = True
            if failure == "cleanup_exception":
                raise OSError("private-marker")
            return failure != "cleanup"

    engine = Engine()
    report = gate.run_check(engine, "synthetic-image", "a" * 40, tmp_path)
    assert report["passed"] is (failure is None)
    assert engine.cleaned and engine.key_file and not engine.key_file.exists()
    assert "private-marker" not in json.dumps(report)

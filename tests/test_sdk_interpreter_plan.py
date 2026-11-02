"""Windows direct-base launch must keep the locked venv and fail on identity drift."""

import json
import sys
from types import SimpleNamespace

import pytest

from scripts import run_sdk_api_collection as gate


def test_regular_launch_keeps_the_current_interpreter_without_a_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "IS_WINDOWS", False, raising=False)
    monkeypatch.setattr(gate.subprocess, "run", lambda *a, **k: pytest.fail("unexpected probe"))
    original = {"PATH": "test-tools"}
    executable, environment = gate.launch_plan(original, tmp_path)
    assert executable == sys.executable and environment == original
    assert environment is not original


@pytest.mark.parametrize("mismatch", [False, True])
def test_windows_base_launch_requires_matching_runtime_identity(tmp_path, monkeypatch, mismatch):
    venv, base = tmp_path / "venv-python.exe", tmp_path / "base-python.exe"
    venv.touch()
    base.touch()
    expected = {
        "prefix": "synthetic-prefix",
        "origins": {"amphrang": "a", "fastapi": "f", "psutil": "p"},
    }
    observed = {}

    def run(command, **kwargs):
        observed.update(command=command, **kwargs)
        return SimpleNamespace(
            returncode=0, stdout=json.dumps({"prefix": "private-marker"} if mismatch else expected)
        )

    monkeypatch.setattr(gate, "IS_WINDOWS", True, raising=False)
    monkeypatch.setattr(gate, "runtime_identity", lambda: expected, raising=False)
    monkeypatch.setattr(sys, "executable", str(venv))
    monkeypatch.setattr(sys, "_base_executable", str(base))
    monkeypatch.setattr(gate.subprocess, "run", run)
    original = {"PATH": "test-tools"}
    if mismatch:
        with pytest.raises(gate.CheckFailed) as error:
            gate.launch_plan(original, tmp_path)
        assert "private-marker" not in str(error.value)
        assert error.value.__context__ is None
    else:
        executable, environment = gate.launch_plan(original, tmp_path)
        assert executable == str(base)
        assert environment["__PYVENV_LAUNCHER__"] == str(venv)
        assert observed["command"][0] == str(base) and observed["timeout"] <= 10
    assert "__PYVENV_LAUNCHER__" not in original

"""Imported products need explicit non-deploy root CI, not nested workflow files."""

import re
import runpy
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/subtree-checks.yml"


def workflow():
    assert WORKFLOW.is_file(), "Imported Hosted/SDK checks are absent from root CI"
    return "\n".join(line.split("#", 1)[0] for line in WORKFLOW.read_text().splitlines())


def job(text, name):
    match = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z][\w-]*:|\Z)", text, re.M | re.S)
    assert match, f"Missing explicit subtree job: {name}"
    return match[1]


def test_ci_covers_each_shipped_subtree():
    text = workflow()
    hosted = job(text, "hosted-checks")
    sdk = job(text, "sdk-checks")
    assert "working-directory: apps/hosted" in hosted
    assert "working-directory: packages/amphrang" in sdk
    assert 'python: ["3.11", "3.13"]' in sdk
    assert ".venv/bin/python -m pytest -q" in sdk
    assert "enterprise-postgres:" in (ROOT / ".github/workflows/ci.yml").read_text()


def test_hosted_uses_complete_existing_check_inventory_and_exact_image():
    hosted = job(workflow(), "hosted-checks")
    assert "python tests/run_ci_local.py --job check --gitlab-network" in hosted
    source = (ROOT / "apps/hosted/.gitlab-ci.yml").read_text()
    check = source.split("\ncheck:\n", 1)[1].split("\ndeploy:\n", 1)[0]
    assert "node tests/frontend_session_contract.mjs" in check
    assert "node tests/hosted3_frontend_behavior_contract.mjs" in check
    assert "sync/sync_from_upstream.py --check --verify-upstream" in check
    assert "--file core/Dockerfile" in hosted and " core" in hosted
    assert "--network none" in hosted


def test_sdk_uses_frozen_dependencies_pinned_builder_and_installed_wheel():
    sdk = job(workflow(), "sdk-checks")
    assert "uv sync --frozen --extra server --extra mcp --group dev --no-install-project" in sdk
    assert "--build-constraints ../../requirements-build.lock" in sdk
    assert "--no-deps --editable ." in sdk
    assert "uv build --python" in sdk and "--wheel --build-constraints" in sdk
    assert "--target" in sdk and "--no-deps" in sdk
    assert " -I " in sdk and "check_sdk_installed.py" in sdk


def test_check_pipeline_cannot_deploy_or_inherit_production_credentials():
    text = workflow()
    assert "contents: read" in text
    assert "workflow_dispatch:" in text and "push:" in text and "pull_request:" in text
    for forbidden in (
        "secrets.",
        "contents: write",
        "id-token: write",
        "environment:",
        "deploy_production",
        "--job deploy",
        "--job acceptance",
        "--all",
        "docker compose up",
        "docker stack deploy",
        "git push",
        "pip publish",
        "twine upload",
    ):
        assert forbidden not in text, f"A check-only job acquired an outward action: {forbidden}"


def test_sdk_core_profile_does_not_hide_optional_dependency_imports():
    sdk = job(workflow(), "sdk-checks")
    assert 'profile: ["core", "server-mcp"]' in sdk
    assert "uv sync --frozen --group dev --no-install-project" in sdk
    assert 'find_spec("fastapi") is None' in sdk
    assert 'find_spec("mcp") is None' in sdk


@pytest.mark.parametrize("asset_ok", [True, False])
def test_hosted_image_smoke_reaches_detection_only_after_asset_success(monkeypatch, asset_ok):
    hosted = job(workflow(), "hosted-checks")
    match = re.search(r" -c '\n(.*?)'(?=\n|$)", hosted, re.S)
    assert match, "Hosted image Python smoke is missing"
    program = textwrap.dedent(match.group(1))
    calls = []

    def checked_asset(command, **kwargs):
        assert command == [sys.executable, "/app/verify_thainer_assets.py"]
        calls.append("assets")
        if not asset_ok and kwargs.get("check"):
            raise subprocess.CalledProcessError(1, ["synthetic-asset-check"])
        return subprocess.CompletedProcess(command, 0 if asset_ok else 1)

    def old_asset_entry(*_args, **_kwargs):
        calls.append("assets")
        raise SystemExit(0 if asset_ok else 1)

    def detect(_text):
        calls.append("detect")
        return [SimpleNamespace(data_type="PHONE")]

    aggregate = ModuleType("pii_redactor.detectors.aggregate")
    aggregate.detect_all = detect
    monkeypatch.setitem(sys.modules, "pii_redactor", ModuleType("pii_redactor"))
    monkeypatch.setitem(sys.modules, "pii_redactor.detectors", ModuleType("pii_redactor.detectors"))
    monkeypatch.setitem(sys.modules, "pii_redactor.detectors.aggregate", aggregate)
    monkeypatch.setattr(runpy, "run_path", old_asset_entry)
    monkeypatch.setattr(subprocess, "run", checked_asset)
    monkeypatch.setenv("PYTHAINLP_OFFLINE", "1")
    if asset_ok:
        exec(program, {})
        assert calls == ["assets", "detect"]
    else:
        with pytest.raises((subprocess.CalledProcessError, SystemExit)):
            exec(program, {})
        assert calls == ["assets"]

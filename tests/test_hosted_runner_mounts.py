"""Canonical source discovery must survive a shallow Hosted runner mount."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_runner():
    path = ROOT / "apps/hosted/tests/run_ci_local.py"
    spec = importlib.util.spec_from_file_location("hosted_shallow_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_fixture(root):
    for namespace in ("app", "pii_redactor"):
        (root / namespace).mkdir(parents=True)
        (root / namespace / "__init__.py").write_bytes(b"# synthetic source\n")
    (root / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("# synthetic build metadata\n", encoding="utf-8")
    return root


def test_shallow_repo_mount_uses_selected_canonical_source_and_private_env(tmp_path):
    runner = load_runner()
    runner.REPO = Path("/w")
    runner.CANONICAL = canonical_fixture(tmp_path / "selected-core")
    synthetic = {"APP_AIGUARD_API_KEY": "synthetic-private-env-only"}
    with runner.private_env_file(synthetic) as env_file:
        command = runner.docker_command(
            {"default": {"image": "synthetic-runner"}}, env_file, gitlab_network=True
        )
        for name in ("app", "pii_redactor", "VERSION", "pyproject.toml"):
            assert f"{runner.CANONICAL / name}:/canonical-core/{name}:ro" in command
        assert "PYTHONPATH=/canonical-core" in command
        assert command[command.index("--env-file") + 1] == str(env_file)
        assert synthetic["APP_AIGUARD_API_KEY"] not in "\0".join(command)
        assert synthetic["APP_AIGUARD_API_KEY"] in env_file.read_text(encoding="utf-8")
    assert not env_file.exists()


def test_manifest_and_mount_share_selected_canonical_source(tmp_path, monkeypatch):
    runner = load_runner()
    runner.REPO = tmp_path / "hosted"
    runner.REPO.mkdir()
    (runner.REPO / "safe.py").write_bytes(b"# synthetic Hosted source\n")
    runner.CANONICAL = canonical_fixture(tmp_path / "selected-core")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda args, **_kwargs: SimpleNamespace(
            stdout=b"safe.py\0" if "ls-files" in args else "a" * 40
        ),
    )
    with runner.tracked_source_manifest() as manifest:
        inventory = json.loads(manifest.read_text(encoding="utf-8"))
        expected = runner.SOURCE_INTEGRITY["source_snapshot"](runner.CANONICAL)
        assert inventory["canonical_source"] == {
            "files": {
                name: hashlib.sha256(payload).hexdigest() for name, payload in expected.items()
            },
            "source_tree_sha256": runner.SOURCE_INTEGRITY["snapshot_sha256"](expected),
        }
        command = runner.docker_command(
            {"default": {"image": "synthetic-runner"}},
            tmp_path / "private.env",
            source_inventory=manifest,
        )
        assert f"{manifest}:/source-inventory/tracked.json:ro" in command
        assert f"{runner.CANONICAL / 'pii_redactor'}:/canonical-core/pii_redactor:ro" in command


def test_incomplete_selected_canonical_mount_fails_without_fallback(tmp_path):
    runner = load_runner()
    runner.REPO = tmp_path / "hosted"
    runner.CANONICAL = canonical_fixture(tmp_path / "selected-core")
    (runner.CANONICAL / "VERSION").unlink()
    with pytest.raises(RuntimeError, match="canonical source mount"):
        runner.docker_command({"default": {"image": "synthetic-runner"}}, tmp_path / "private.env")

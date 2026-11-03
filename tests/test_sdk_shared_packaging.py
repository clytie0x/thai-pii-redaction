"""The SDK resolves only its supplied matching first-party core artifact."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "packages/amphrang"


def test_sdk_requires_exact_core_version_and_explicit_local_development_source():
    metadata = tomllib.loads((SDK / "pyproject.toml").read_text(encoding="utf-8"))
    version = (ROOT / "VERSION").read_text().strip()
    assert f"thai-pii-redaction-core=={version}" in metadata["project"]["dependencies"]
    assert metadata["tool"]["uv"]["sources"]["thai-pii-redaction-core"] == {"path": "../.."}
    lock = tomllib.loads((SDK / "uv.lock").read_text(encoding="utf-8"))
    core = next(p for p in lock["package"] if p["name"] == "thai-pii-redaction-core")
    assert core.get("version", version) == version
    assert core["source"]["directory"].rstrip("/") == "../.."
    assert not any(p["name"] == "aiguard" for p in lock["package"])


def test_root_wheel_declares_enterprise_connector_package():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "pii_redactor.governance.connectors" in metadata["tool"]["setuptools"]["packages"]


def test_sdk_container_installs_only_verified_offline_supplied_artifacts():
    source = (SDK / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY wheels" in source and "COPY wheelhouse" in source
    assert "COPY models" in source
    assert "verify_supplied_tree" in source
    assert "--no-index" in source and "--network=none" in source
    assert "check_sdk_installed.py" in source
    assert 'pip install ".[server]"' not in source
    assert "prewarm_ner.py" not in source
    assert "PYTHAINLP_OFFLINE=1" in source


def test_frozen_sdk_sync_excludes_first_party_build_until_explicit_install():
    source = (ROOT / ".github/workflows/subtree-checks.yml").read_text()
    sdk = source.split("  sdk-checks:\n", 1)[1].split("  sdk-container:\n", 1)[0]
    syncs = [line for line in sdk.splitlines() if "uv sync --frozen" in line]
    assert syncs and all("--no-install-package thai-pii-redaction-core" in line for line in syncs)
    assert "--no-index --no-deps" in sdk
    assert "--package thai-pii-redaction-core" not in sdk
    assert '"$core_wheel"' in sdk and '"$sdk_wheel"' in sdk

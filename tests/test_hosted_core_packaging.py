"""Fail-closed Hosted canonical artifact and source-inventory boundaries."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_source_test_helper_accepts_shallow_runner_mount():
    root = Path(__file__).resolve().parents[1]
    helper = root / "apps/hosted/tests/canonical_core.py"
    namespace = {"__file__": "/w/tests/canonical_core.py"}
    exec(compile(helper.read_text(encoding="utf-8"), str(helper), "exec"), namespace)
    assert namespace["CANONICAL"] == root


ROOT = Path(__file__).resolve().parents[1]


def load_script():
    path = ROOT / "scripts" / "prepare_hosted_core.py"
    spec = importlib.util.spec_from_file_location("prepare_hosted_core", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wheel_fixture(tmp_path, *, changed=False):
    source = tmp_path / "source"
    source.mkdir()
    (source / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    for name in ("app", "pii_redactor"):
        directory = source / name
        directory.mkdir()
        (directory / "__init__.py").write_text("# synthetic canonical source\n", encoding="utf-8")
    wheel = tmp_path / "thai_pii_redaction_core-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in ("app", "pii_redactor"):
            archive.writestr(
                f"{name}/__init__.py",
                b"changed" if changed else (source / name / "__init__.py").read_bytes(),
            )
        archive.writestr(
            "thai_pii_redaction_core-0.1.0.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: thai-pii-redaction-core\nVersion: 0.1.0\n",
        )
    return source, wheel


def canonical_inventory_fixture(tmp_path):
    canonical = tmp_path / "canonical"
    for namespace in ("app", "pii_redactor"):
        (canonical / namespace).mkdir(parents=True)
        (canonical / namespace / "__init__.py").write_bytes(b"# synthetic source\n")
    return canonical


def canonical_inventory(canonical):
    integrity = load_script().SOURCE_INTEGRITY
    snapshot = integrity["source_snapshot"](canonical)
    return {
        "source_tree_sha256": integrity["snapshot_sha256"](snapshot),
        "files": {name: hashlib.sha256(payload).hexdigest() for name, payload in snapshot.items()},
    }


def test_supplied_wheel_is_bound_to_exact_canonical_source(tmp_path):
    prepare = load_script()
    source, wheel = wheel_fixture(tmp_path)
    expected = hashlib.sha256(wheel.read_bytes()).hexdigest()
    digest = prepare.source_tree_sha256(source)
    identity = prepare.verify_core_wheel(
        wheel, source, expected_sha256=expected, expected_source_sha256=digest
    )
    assert identity["distribution"] == "thai-pii-redaction-core"
    assert identity["version"] == "0.1.0"
    assert identity["source_tree_sha256"] == digest
    with pytest.raises(ValueError, match="wheel digest"):
        prepare.verify_core_wheel(
            wheel, source, expected_sha256="0" * 64, expected_source_sha256=digest
        )
    with pytest.raises(ValueError, match="source digest"):
        prepare.verify_core_wheel(
            wheel, source, expected_sha256=expected, expected_source_sha256="0" * 64
        )


def test_stale_or_extra_core_wheel_sources_are_rejected(tmp_path):
    prepare = load_script()
    source, wheel = wheel_fixture(tmp_path, changed=True)
    with pytest.raises(ValueError, match="canonical source"):
        prepare.verify_core_wheel(
            wheel,
            source,
            expected_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
            expected_source_sha256=prepare.source_tree_sha256(source),
        )


def test_wheel_cannot_install_unreviewed_extra_namespace_or_startup_hook(tmp_path):
    prepare = load_script()
    source, wheel = wheel_fixture(tmp_path)
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("unreviewed.pth", "import unreviewed_hook\n")
    with pytest.raises(ValueError, match="unexpected executable wheel member"):
        prepare.verify_core_wheel(
            wheel,
            source,
            expected_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
            expected_source_sha256=prepare.source_tree_sha256(source),
        )


def test_exact_canonical_wheel_source_is_secret_scanned(tmp_path):
    prepare = load_script()
    source, wheel = wheel_fixture(tmp_path)
    marker = "ghp_" + "S" * 36
    payload = f"# synthetic secret marker\nSYNTHETIC = '{marker}'\n".encode()
    (source / "pii_redactor/synthetic.py").write_bytes(payload)
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("pii_redactor/synthetic.py", payload)
    with pytest.raises(ValueError, match="secret-pattern") as raised:
        prepare.verify_core_wheel(
            wheel,
            source,
            expected_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
            expected_source_sha256=prepare.source_tree_sha256(source),
        )
    assert marker not in str(raised.value)


def test_wheel_metadata_is_also_secret_scanned(tmp_path):
    prepare = load_script()
    source, wheel = wheel_fixture(tmp_path)
    marker = "ghp_" + "S" * 36
    with zipfile.ZipFile(wheel) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    metadata = "thai_pii_redaction_core-0.1.0.dist-info/METADATA"
    contents[metadata] += f"\nSynthetic fixture: {marker}\n".encode()
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, payload in contents.items():
            archive.writestr(name, payload)
    with pytest.raises(ValueError, match="secret-pattern") as raised:
        prepare.verify_core_wheel(
            wheel,
            source,
            expected_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
            expected_source_sha256=prepare.source_tree_sha256(source),
        )
    assert marker not in str(raised.value)


def test_dependency_wheelhouse_rejects_unpinned_or_modified_wheels(tmp_path):
    prepare = load_script()
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "synthetic_dependency-1.2.3-py3-none-any.whl"
    wheel.write_bytes(b"synthetic pinned artifact")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    lock = tmp_path / "runtime.lock"
    lock.write_text(f"synthetic-dependency==1.2.3 --hash=sha256:{digest}\n", encoding="utf-8")
    assert prepare.verify_wheelhouse(wheelhouse, [lock]) == [wheel]
    wheel.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="dependency digest"):
        prepare.verify_wheelhouse(wheelhouse, [lock])


def test_runtime_has_no_authored_engine_or_network_install_fallback():
    docker = (ROOT / "apps/hosted/core/Dockerfile").read_text(encoding="utf-8")
    assert "COPY app " not in docker and "COPY pii_redactor " not in docker
    assert "--no-index" in docker and "--require-hashes" in docker
    assert "python -m pip check" in docker
    assert "COPY models " in docker
    assert "NER(engine='thainer')" not in docker
    assert "verify_thainer_assets.py" in docker
    assert "apt-get" not in docker
    assert "verify_core_install.py" in docker


def test_approval_binding_matches_complete_artifact_source_identity(monkeypatch):
    path = ROOT / "apps/hosted/core/aift_hosted3/core_identity.py"
    spec = importlib.util.spec_from_file_location("hosted_canonical_identity", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module.importlib.util,
        "find_spec",
        lambda _name: SimpleNamespace(origin=str(ROOT / "pii_redactor/__init__.py")),
    )
    assert module.protection_source_sha256() == load_script().source_tree_sha256(ROOT)


def test_tracked_inventory_requires_matching_manifest_and_file_hashes(tmp_path):
    contract_path = ROOT / "apps/hosted/tests/release_source_contract.py"
    spec = importlib.util.spec_from_file_location("hosted_release_source", contract_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path / "hosted"
    module.ROOT.mkdir()
    canonical = canonical_inventory_fixture(tmp_path)
    source = module.ROOT / "synthetic.py"
    source.write_bytes(b"# synthetic source\n")
    manifest = tmp_path / "inventory.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "revision": "a" * 40,
                "files": {"synthetic.py": hashlib.sha256(source.read_bytes()).hexdigest()},
                "canonical_source": canonical_inventory(canonical),
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert module.verified_inventory(manifest, digest, "a" * 40, canonical_root=canonical) == [
        source,
        canonical / "app/__init__.py",
        canonical / "pii_redactor/__init__.py",
    ]
    source.write_bytes(b"changed source")
    with pytest.raises(AssertionError, match="source inventory"):
        module.verified_inventory(manifest, digest, "a" * 40, canonical_root=canonical)


def test_source_inventory_rejects_bad_digest_revision_and_path_escape(tmp_path):
    contract_path = ROOT / "apps/hosted/tests/release_source_contract.py"
    spec = importlib.util.spec_from_file_location("hosted_release_source_failures", contract_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path
    manifest = tmp_path / "inventory.json"
    manifest.write_text(
        json.dumps(
            {"schema_version": 2, "revision": "a" * 40, "files": {"../escape.py": "0" * 64}}
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    with pytest.raises(AssertionError, match="digest mismatch"):
        module.verified_inventory(manifest, "0" * 64, "a" * 40)
    with pytest.raises(AssertionError, match="revision mismatch"):
        module.verified_inventory(manifest, digest, "b" * 40)
    with pytest.raises(AssertionError, match="path escape"):
        module.verified_inventory(manifest, digest, "a" * 40)


def test_runner_passes_verified_inventory_read_only_without_git_metadata(tmp_path):
    path = ROOT / "apps/hosted/tests/run_ci_local.py"
    spec = importlib.util.spec_from_file_location("hosted_runner_inventory", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inventory = tmp_path / "tracked.json"
    inventory.write_text(
        json.dumps(
            {"schema_version": 1, "revision": "a" * 40, "files": {"synthetic.py": "b" * 64}}
        ),
        encoding="utf-8",
    )
    command = module.docker_command(
        {"default": {"image": "synthetic-runner"}},
        tmp_path / "private.env",
        source_inventory=inventory,
    )
    assert f"{inventory}:/source-inventory/tracked.json:ro" in command
    assert "AIFT_TRACKED_SOURCE_MANIFEST=/source-inventory/tracked.json" in command
    assert "AIFT_TRACKED_SOURCE_REVISION=" + "a" * 40 in command
    assert (
        "AIFT_TRACKED_SOURCE_SHA256=" + hashlib.sha256(inventory.read_bytes()).hexdigest()
        in command
    )


def test_canonical_inventory_requires_exact_files_hash_and_secret_scan(tmp_path):
    path = ROOT / "apps/hosted/tests/release_source_contract.py"
    spec = importlib.util.spec_from_file_location("hosted_canonical_secret_inventory", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = tmp_path / "hosted"
    module.ROOT.mkdir()
    (module.ROOT / "safe.py").write_bytes(b"# synthetic\n")
    canonical = canonical_inventory_fixture(tmp_path)
    manifest = tmp_path / "inventory.json"
    payload = {
        "schema_version": 2,
        "revision": "a" * 40,
        "files": {"safe.py": hashlib.sha256(b"# synthetic\n").hexdigest()},
        "canonical_source": canonical_inventory(canonical),
    }

    def verify():
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        return module.verified_inventory(
            manifest,
            hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "a" * 40,
            canonical_root=canonical,
        )

    assert len(verify()) == 3
    payload["canonical_source"]["source_tree_sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="canonical source inventory tree"):
        verify()
    payload["canonical_source"] = canonical_inventory(canonical)
    (canonical / "pii_redactor/extra.py").write_bytes(b"# synthetic addition\n")
    with pytest.raises(AssertionError, match="canonical source inventory file"):
        verify()
    marker = "ghp_" + "S" * 36
    (canonical / "pii_redactor/extra.py").write_text(f"SYNTHETIC = '{marker}'\n", encoding="utf-8")
    payload["canonical_source"] = canonical_inventory(canonical)
    with pytest.raises(ValueError, match="secret-pattern") as raised:
        verify()
    assert marker not in str(raised.value)
    del payload["canonical_source"]
    with pytest.raises(AssertionError, match="canonical source inventory is missing"):
        verify()


def test_runner_inventory_binds_canonical_wheel_input_and_refuses_synthetic_secret(
    tmp_path, monkeypatch
):
    path = ROOT / "apps/hosted/tests/run_ci_local.py"
    spec = importlib.util.spec_from_file_location("hosted_full_source_inventory", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    canonical = canonical_inventory_fixture(tmp_path)
    module.REPO = canonical / "apps/hosted"
    module.REPO.mkdir(parents=True)
    (module.REPO / "safe.py").write_bytes(b"# synthetic\n")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **_kwargs: SimpleNamespace(
            stdout=b"safe.py\0" if "ls-files" in args else "a" * 40
        ),
    )
    with module.tracked_source_manifest() as manifest:
        inventory = json.loads(manifest.read_text(encoding="utf-8"))
        assert inventory["schema_version"] == 2
        assert inventory["canonical_source"] == canonical_inventory(canonical)
        assert inventory["canonical_source"][
            "source_tree_sha256"
        ] == load_script().source_tree_sha256(canonical)
    marker = "ghp_" + "S" * 36
    (canonical / "pii_redactor/synthetic.py").write_text(
        f"SYNTHETIC = '{marker}'\n", encoding="utf-8"
    )
    with (
        pytest.raises(ValueError, match="secret-pattern") as raised,
        module.tracked_source_manifest(),
    ):
        pass
    assert marker not in str(raised.value)

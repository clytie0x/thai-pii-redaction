"""Fail-closed Hosted canonical artifact and source-inventory boundaries."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import runpy
import subprocess
import sys
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


def generated_wheel_fixture(tmp_path):
    source, wheel = wheel_fixture(tmp_path)
    inputs = {
        "pyproject.toml": b"""[project]
name = "thai-pii-redaction-core"
license-files = ["LICENSE", "NOTICE", "licenses/OFL-1.1.txt"]
[tool.setuptools]
cmdclass = { build_py = "_aiguard_build.ArtifactBuildPy" }
[tool.setuptools.dynamic]
dependencies = { file = "requirements.txt" }
optional-dependencies.web = { file = "requirements-web.txt" }
[tool.aiguard.artifact]
locks = ["requirements.lock"]
build-inputs = ["_aiguard_build.py", "MANIFEST.in"]
""",
        "requirements.txt": b"# synthetic dependencies\n",
        "requirements-web.txt": b"# synthetic optional dependencies\n",
        "requirements.lock": b"# synthetic dependency lock\n",
        "_aiguard_build.py": b"# synthetic build input\n",
        "MANIFEST.in": b"# synthetic manifest input\n",
        "LICENSE": b"synthetic license\n",
        "NOTICE": b"synthetic notice\n",
        "licenses/OFL-1.1.txt": b"synthetic font license\n",
    }
    for name, payload in inputs.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    (source / "pii_redactor/artifact_identity.py").write_bytes(
        (ROOT / "pii_redactor/artifact_identity.py").read_bytes()
    )
    (source / "pii_redactor/__init__.py").write_bytes(
        b"raise AssertionError('canonical engines must not be imported')\n"
    )
    (source / "pii_redactor/data.bin").write_bytes(b"synthetic canonical data\n")
    identity = runpy.run_path(str(ROOT / "pii_redactor/artifact_identity.py"))
    manifest = identity["source_manifest"](source)
    contents = {name: (source / name).read_bytes() for name in manifest["runtime"]} | {
        identity["RESOURCE"] + "/" + name: (source / name).read_bytes()
        for name in manifest["inputs"]
    }
    contents[identity["RESOURCE"] + "/manifest.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    prefix = "thai_pii_redaction_core-0.1.0.dist-info/"
    contents[prefix + "METADATA"] = (
        b"Metadata-Version: 2.4\nName: thai-pii-redaction-core\nVersion: 0.1.0\n"
    )
    for name in ("LICENSE", "NOTICE", "licenses/OFL-1.1.txt"):
        contents[prefix + "licenses/" + name] = inputs[name]
    rewrite_wheel(wheel, contents)
    return source, wheel, contents


def rewrite_wheel(wheel, contents):
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, payload in contents.items():
            archive.writestr(name, payload)


def verify_fixture(source, wheel):
    prepare = load_script()
    return prepare.verify_core_wheel(
        wheel,
        source,
        expected_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
        expected_source_sha256=prepare.source_tree_sha256(source),
    )


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"], ids=["linux", "windows"])
def test_generated_wheel_resources_match_the_canonical_build_contract(
    tmp_path, monkeypatch, newline
):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    name = "pii_redactor/_artifact/manifest.json"
    contents[name] = contents[name][:-1] + newline
    rewrite_wheel(wheel, contents)
    monkeypatch.setitem(
        sys.modules,
        "pii_redactor.artifact_identity",
        SimpleNamespace(source_manifest=lambda _source: pytest.fail("foreign identity import")),
    )
    assert verify_fixture(source, wheel)["version"] == "0.1.0"


def test_prepared_context_binds_runtime_generated_metadata_and_trusted_cache_helper(
    tmp_path, monkeypatch
):
    prepare = load_script()
    source, wheel, _ = generated_wheel_fixture(tmp_path)
    models = tmp_path / "synthetic-models"
    models.mkdir()
    monkeypatch.setattr(prepare, "MODEL_SHA256", prepare.model_tree_sha256(models))
    monkeypatch.setattr(prepare, "verify_wheelhouse", lambda _root, _locks: [])
    monkeypatch.setattr(
        prepare.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout="a" * 40)
    )
    output = tmp_path / "prepared-context"
    identity = prepare.prepare_context(
        SimpleNamespace(
            source=source,
            core_wheel=wheel,
            core_wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
            source_tree_sha256=prepare.source_tree_sha256(source),
            source_revision="a" * 40,
            wheelhouse=tmp_path / "supplied-wheelhouse",
            models=models,
            output=output,
        )
    )
    assert identity["schema_version"] == 2
    assert identity["source_tree_sha256"] == prepare.source_tree_sha256(source)
    inventory = identity["installed_core"]
    assert "pii_redactor/data.bin" in inventory["runtime"]
    assert "pii_redactor/_artifact/manifest.json" in inventory["generated"]
    assert "thai_pii_redaction_core-0.1.0.dist-info/licenses/LICENSE" in inventory["metadata"]
    assert not set(inventory["runtime"]) & set(inventory["generated"])
    helper = output / "verify_core_cache.py"
    assert helper.read_bytes() == (ROOT / "pii_redactor/_cache_identity.py").read_bytes()
    assert identity["cache_verifier"] == {
        "file": helper.name,
        "sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
    }
    assert identity["files"][helper.name] == identity["cache_verifier"]["sha256"]
    assert identity["files"]["wheels/" + wheel.name] == identity["wheel_sha256"]


def test_generated_wheel_validation_loads_only_the_current_stdlib_identity_helper(tmp_path):
    source, wheel, _ = generated_wheel_fixture(tmp_path)
    program = """
import importlib.abc, pathlib, runpy, sys
class NoRuntimeImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'app', 'pii_redactor', 'setuptools', 'torch', 'fastapi'}:
            raise AssertionError('runtime or optional import attempted')
sys.meta_path.insert(0, NoRuntimeImports())
prepare = runpy.run_path(sys.argv[1])
source, wheel = map(pathlib.Path, sys.argv[2:])
prepare['verify_core_wheel'](
    wheel, source,
    expected_sha256=prepare['sha256'](wheel),
    expected_source_sha256=prepare['source_tree_sha256'](source),
)
assert 'pii_redactor' not in sys.modules and 'app' not in sys.modules
print('canonical_generated_wheel_verified')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            program,
            str(ROOT / "scripts/prepare_hosted_core.py"),
            str(source),
            str(wheel),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "canonical_generated_wheel_verified"


def test_supplied_source_identity_helper_is_hashed_without_execution(tmp_path):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    sentinel = tmp_path / "untrusted-source-helper-executed"
    name = "pii_redactor/artifact_identity.py"
    payload = (
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('synthetic side effect')\n"
        "raise AssertionError('untrusted source helper executed')\n"
    ).encode()
    (source / name).write_bytes(payload)
    contents[name] = payload
    manifest_name = "pii_redactor/_artifact/manifest.json"
    manifest = json.loads(contents[manifest_name])
    manifest["runtime"][name] = hashlib.sha256(payload).hexdigest()
    contents[manifest_name] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    rewrite_wheel(wheel, contents)
    assert verify_fixture(source, wheel)["version"] == "0.1.0"
    assert not sentinel.exists()


@pytest.mark.parametrize(
    "name",
    [
        "pii_redactor/_artifact/LICENSE",
        "pii_redactor/_artifact/NOTICE",
        "pii_redactor/_artifact/licenses/OFL-1.1.txt",
        "pii_redactor/_artifact/VERSION",
        "pii_redactor/_artifact/pyproject.toml",
        "pii_redactor/_artifact/requirements.lock",
        "pii_redactor/_artifact/_aiguard_build.py",
        "pii_redactor/data.bin",
        "thai_pii_redaction_core-0.1.0.dist-info/licenses/LICENSE",
        "thai_pii_redaction_core-0.1.0.dist-info/licenses/licenses/OFL-1.1.txt",
    ],
)
def test_generated_wheel_rejects_changed_canonical_inputs_and_data(tmp_path, name):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    contents[name] = b"synthetic changed payload\n"
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError, match="canonical"):
        verify_fixture(source, wheel)


@pytest.mark.parametrize(
    "name",
    [
        "pii_redactor/_artifact/manifest.json",
        "pii_redactor/_artifact/LICENSE",
        "pii_redactor/_artifact/requirements.lock",
        "pii_redactor/_artifact/_aiguard_build.py",
        "pii_redactor/data.bin",
        "thai_pii_redaction_core-0.1.0.dist-info/licenses/NOTICE",
    ],
)
def test_generated_wheel_rejects_missing_resources_and_canonical_files(tmp_path, name):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    del contents[name]
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError, match="canonical"):
        verify_fixture(source, wheel)


@pytest.mark.parametrize(
    "name",
    [
        "pii_redactor/_artifact/private.key",
        "pii_redactor/_artifact/.env",
        "pii_redactor/_artifact/extra.json",
        "pii_redactor/_artifact/__pycache__/residue.json",
        "pii_redactor/_artifact/unknown/",
        "thai_pii_redaction_core-0.1.0.dist-info/licenses/private.key",
    ],
)
def test_generated_wheel_rejects_unknown_and_private_resources(tmp_path, name):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    contents[name] = b"synthetic unreviewed resource\n"
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError):
        verify_fixture(source, wheel)


@pytest.mark.parametrize(
    "field", ["format", "distribution", "version", "runtime", "inputs", "extra"]
)
def test_generated_wheel_rejects_changed_manifest_contract(tmp_path, field):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    name = "pii_redactor/_artifact/manifest.json"
    manifest = json.loads(contents[name])
    manifest[field] = {} if field in {"runtime", "inputs"} else "synthetic-changed-metadata"
    contents[name] = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError, match="canonical"):
        verify_fixture(source, wheel)


@pytest.mark.parametrize("newline", [b"", b"\r", b"\n\n", b"\r\n\r\n"])
def test_generated_manifest_accepts_only_a_single_builder_newline(tmp_path, newline):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    name = "pii_redactor/_artifact/manifest.json"
    contents[name] = contents[name][:-1] + newline
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError, match="canonical"):
        verify_fixture(source, wheel)


def test_current_build_contract_cannot_fall_back_to_runtime_only_wheel(tmp_path):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    contents = {name: data for name, data in contents.items() if "/_artifact/" not in name}
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError, match="canonical"):
        verify_fixture(source, wheel)
    pyproject = source / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'thai-pii-redaction-core'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="canonical"):
        verify_fixture(source, wheel)
    pyproject.unlink()
    with pytest.raises(ValueError, match="canonical"):
        verify_fixture(source, wheel)


def test_legacy_runtime_only_fixture_without_artifact_build_contract_is_supported(tmp_path):
    source, wheel = wheel_fixture(tmp_path)
    (source / "pyproject.toml").write_text(
        "[project]\nname = 'thai-pii-redaction-core'\n", encoding="utf-8"
    )
    assert verify_fixture(source, wheel)["version"] == "0.1.0"


@pytest.mark.parametrize(
    "name",
    [
        "pii_redactor/_artifact//LICENSE",
        "pii_redactor/_artifact/./LICENSE",
        "pii_redactor/_artifact/../LICENSE",
        "pii_redactor/_artifact/LICENSE/",
        "pii_redactor/_artifact/license",
    ],
)
def test_generated_resource_path_aliases_are_rejected(tmp_path, name):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    contents[name] = contents["pii_redactor/_artifact/LICENSE"]
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError):
        verify_fixture(source, wheel)


def test_generated_resource_zip_symlink_is_rejected(tmp_path):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    name = "pii_redactor/_artifact/LICENSE"
    payload = contents.pop(name)
    rewrite_wheel(wheel, contents)
    link = zipfile.ZipInfo(name)
    link.create_system = 3
    link.external_attr = 0o120777 << 16
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(link, payload)
    with pytest.raises(ValueError, match="unsafe core wheel inventory"):
        verify_fixture(source, wheel)


def test_current_artifact_metadata_cannot_add_an_executable_payload(tmp_path):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    contents["thai_pii_redaction_core-0.1.0.dist-info/startup.pth"] = b"import synthetic_hook\n"
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError, match="unexpected executable wheel member"):
        verify_fixture(source, wheel)


@pytest.mark.parametrize("field", ["Name", "Version"])
def test_current_artifact_identity_rejects_duplicate_metadata_headers(tmp_path, field):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    name = "thai_pii_redaction_core-0.1.0.dist-info/METADATA"
    value = "thai-pii-redaction-core" if field == "Name" else "0.1.0"
    contents[name] += f"{field}: {value}\n".encode()
    rewrite_wheel(wheel, contents)
    with pytest.raises(ValueError, match="invalid first-party core identity"):
        verify_fixture(source, wheel)


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
    module.CANONICAL = canonical
    (canonical / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (canonical / "pyproject.toml").write_text("# synthetic build metadata\n", encoding="utf-8")
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

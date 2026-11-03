"""A reused build directory must not leak extra private resources into a wheel."""

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_isolated_builder_can_load_the_manifest_without_the_runtime_package(tmp_path):
    program = """
import importlib.util, sys
from pathlib import Path
root = Path(sys.argv[1])
assert 'pii_redactor' not in sys.modules
spec = importlib.util.spec_from_file_location('_artifact_builder', root / 'pii_redactor/artifact_identity.py')
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)
manifest = identity.source_manifest(root)
assert 'pii_redactor/_cache_identity.py' in manifest['runtime']
assert 'pii_redactor' not in sys.modules
print('isolated_build_manifest_ready')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", program, str(ROOT)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "isolated_build_manifest_ready"


def build_helper(monkeypatch):
    # The resource writer is stdlib-only; setuptools is a build-time dependency.
    for name in ("setuptools", "setuptools.command", "setuptools.command.build_py"):
        module = ModuleType(name)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)
    sys.modules["setuptools.command.build_py"].build_py = object
    spec = importlib.util.spec_from_file_location(
        "artifact_build_residue", ROOT / "_aiguard_build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    spec = importlib.util.spec_from_file_location(
        "artifact_resource_inventory", ROOT / "pii_redactor/artifact_identity.py"
    )
    identity = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(identity)
    return module, identity


def fixture(tmp_path):
    source, target = tmp_path / "source", tmp_path / "build"
    source.mkdir()
    resources = target / "pii_redactor/_artifact"
    resources.mkdir(parents=True)
    (source / "VERSION").write_bytes(b"0.1.0\n")
    manifest = {"inputs": {"VERSION": hashlib.sha256(b"0.1.0\n").hexdigest()}, "runtime": {}}
    return source, target, resources, manifest


@pytest.mark.parametrize(
    "name", ["private.key", "requirements-removed.lock", "__pycache__/residue.json"]
)
def test_reused_resource_directory_rejects_unknown_residue_without_deleting_it(
    tmp_path, monkeypatch, name
):
    helper, identity = build_helper(monkeypatch)
    source, target, resources, manifest = fixture(tmp_path)
    residue = resources / name
    residue.parent.mkdir(parents=True, exist_ok=True)
    residue.write_bytes(b"synthetic-residue-do-not-package")
    with pytest.raises(ValueError):
        helper.write_resources(identity, source, target, manifest)
    assert residue.read_bytes() == b"synthetic-residue-do-not-package"
    assert not (resources / "manifest.json").exists()


def test_known_resources_are_fully_replaced_and_final_inventory_is_exact(tmp_path, monkeypatch):
    helper, identity = build_helper(monkeypatch)
    source, target, resources, manifest = fixture(tmp_path)
    (resources / "VERSION").write_bytes(b"old-generated-version")
    (resources / "manifest.json").write_bytes(b"old-generated-manifest")
    helper.write_resources(identity, source, target, manifest)
    assert (resources / "VERSION").read_bytes() == (source / "VERSION").read_bytes()
    assert {p.name for p in resources.iterdir()} == {"VERSION", "manifest.json"}

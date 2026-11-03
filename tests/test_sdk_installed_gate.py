"""Exercise the installed-artifact gate, including its public result type."""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.check_sdk_installed import compare_wheels, verify_supplied_tree

CHECKER = Path(__file__).resolve().parents[1] / "scripts/check_sdk_installed.py"
FACADE = """from types import SimpleNamespace
from pii_redactor.models import Entity
from pii_redactor.detectors.aggregate import detect_all as _detect_all
detect = _detect_all
def anonymize(text):
    return SimpleNamespace(text="[TOKEN]", mapping={"[TOKEN]":text})
def restore(text, mapping):
    return SimpleNamespace(text=mapping[text])
"""
CORE = {
    "app/__init__.py": "",
    "pii_redactor/__init__.py": "",
    "pii_redactor/models.py": "from types import SimpleNamespace\nEntity = SimpleNamespace\n",
    "pii_redactor/detectors/__init__.py": "",
    "pii_redactor/detectors/aggregate.py": """from pii_redactor.models import Entity
def detect_all(text):
    start = text.index(": ") + 2
    return [Entity(data_type="PHONE", original_text=text[start:], span=(start,len(text)))]
""",
}


def artifact(
    tmp_path,
    extra=None,
    changed=False,
    core_name="thai-pii-redaction-core",
    core_version="0.1.0",
    pin="thai-pii-redaction-core==0.1.0",
):
    target = tmp_path / "installed"
    (target / "amphrang").mkdir(parents=True)
    changed_source = (
        "from pathlib import Path\n"
        f"Path({str(tmp_path / 'import-side-effect')!r}).write_text('imported')\n" + FACADE
    )
    (target / "amphrang/__init__.py").write_bytes(
        (changed_source if changed else FACADE).encode("utf-8")
    )
    wheel = tmp_path / "synthetic.whl"
    metadata = f"Name: amphrang\nVersion: 0.1.0\nRequires-Dist: {pin}\n\n"
    sdk_metadata = "amphrang-0.1.0.dist-info/METADATA"
    (target / sdk_metadata).parent.mkdir()
    (target / sdk_metadata).write_bytes(metadata.encode("utf-8"))
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("amphrang/__init__.py", FACADE)
        archive.writestr(sdk_metadata, metadata)
        if extra:
            archive.writestr(extra, "synthetic-private-marker")
    core_wheel = tmp_path / "core.whl"
    core_metadata = f"thai_pii_redaction_core-{core_version}.dist-info/METADATA"
    with zipfile.ZipFile(core_wheel, "w") as archive:
        for name, source in {
            **CORE,
            core_metadata: f"Name: {core_name}\nVersion: {core_version}\n\n",
        }.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.encode("utf-8"))
            archive.writestr(name, source)
    return target, wheel, core_wheel


def run(target, wheel, core_wheel):
    return subprocess.run(
        [sys.executable, "-I", str(CHECKER), str(target), str(wheel), str(core_wheel)],
        env={**os.environ, "AMPHRANG_NER_ENGINE": "thainer", "PYTHAINLP_OFFLINE": "1"},
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_valid_installed_result_projects_restore_text(tmp_path):
    result = run(*artifact(tmp_path))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "extra",
    [
        "amphrang/.env",
        "amphrang/.env.production",
        "amphrang/private.key",
        "amphrang-0.1.0.data/purelib/app/server.py",
        "amphrang-0.1.0.data/platlib/pii_redactor/__init__.py",
    ],
)
def test_private_resources_and_generic_installed_namespaces_are_denied(tmp_path, extra):
    result = run(*artifact(tmp_path, extra))
    assert result.returncode == 1
    assert "synthetic-private-marker" not in result.stdout + result.stderr


def test_mismatched_installed_source_is_denied_before_import(tmp_path):
    result = run(*artifact(tmp_path, changed=True))
    assert result.returncode == 1
    assert not (tmp_path / "import-side-effect").exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"core_name": "aiguard"},
        {"core_version": "9.9.9"},
        {"pin": "aiguard==0.1.0"},
        {"pin": "thai-pii-redaction-core>=0.1.0"},
    ],
)
def test_wrong_unrelated_or_unpinned_core_is_denied(tmp_path, changes):
    assert run(*artifact(tmp_path, **changes)).returncode == 1


def test_missing_supplied_core_wheel_is_denied(tmp_path):
    target, wheel, _ = artifact(tmp_path)
    assert run(target, wheel, tmp_path / "missing.whl").returncode == 1


def test_generic_namespace_collision_is_denied_before_import(tmp_path):
    arguments = artifact(tmp_path)
    target = arguments[0]
    (target / "app/foreign.py").write_text("raise AssertionError('must not import')")
    assert run(*arguments).returncode == 1


def test_another_distribution_cannot_own_the_core_namespace(tmp_path):
    arguments = artifact(tmp_path)
    info = arguments[0] / "foreign-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Name: foreign\nVersion: 1.0\n\n")
    (info / "RECORD").write_text("app/__init__.py,,\n")
    assert run(*arguments).returncode == 1


def test_editable_core_metadata_is_denied(tmp_path):
    arguments = artifact(tmp_path)
    info = arguments[0] / "thai_pii_redaction_core-0.1.0.dist-info"
    (info / "direct_url.json").write_text('{"dir_info":{"editable":true}}')
    assert run(*arguments).returncode == 1


def test_rebuilt_wheel_comparison_checks_unpacked_bytes(tmp_path):
    first, second = tmp_path / "first.whl", tmp_path / "second.whl"
    for path in (first, second):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("synthetic.txt", "synthetic")
    compare_wheels(first, second)
    with zipfile.ZipFile(second, "w") as archive:
        archive.writestr("synthetic.txt", "changed")
    with pytest.raises(ValueError):
        compare_wheels(first, second)


@pytest.mark.parametrize("extra", [False, True])
def test_supplied_tree_requires_complete_digest_inventory(tmp_path, extra):
    import hashlib

    artifact = tmp_path / "synthetic.whl"
    artifact.write_bytes(b"synthetic")
    (tmp_path / "SHA256SUMS").write_text(
        hashlib.sha256(artifact.read_bytes()).hexdigest() + "  synthetic.whl\n"
    )
    if extra:
        (tmp_path / "unqualified.whl").write_bytes(b"synthetic")
        with pytest.raises(ValueError):
            verify_supplied_tree(tmp_path)
    else:
        verify_supplied_tree(tmp_path)

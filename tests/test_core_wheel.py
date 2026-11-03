"""Reject wrong first-party identities before installed-wheel qualification."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
spec = importlib.util.spec_from_file_location(
    "check_core_wheel", ROOT / "scripts/check_enterprise_wheel.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def wheel(tmp_path, *, name="thai-pii-redaction-core", version=VERSION, duplicate_name=False):
    path = tmp_path / "candidate.whl"
    info = f"{name.replace('-', '_')}-{version}.dist-info"
    metadata = f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n"
    if duplicate_name:
        metadata += "Name: unrelated\n"
    with zipfile.ZipFile(path, "w") as archive:
        for resource in gate.REQUIRED:
            archive.writestr(resource, "")
        archive.writestr(info + "/licenses/licenses/OFL-1.1.txt", "Synthetic license")
        archive.writestr(info + "/METADATA", metadata)
    return path


def test_core_wheel_accepts_the_selected_distribution(tmp_path):
    path = wheel(tmp_path)
    assert gate.main([str(path)]) == 0


@pytest.mark.parametrize(
    "options",
    [{"name": "aiguard"}, {"version": "9.9.9"}, {"duplicate_name": True}],
)
def test_core_wheel_rejects_wrong_or_ambiguous_identity(tmp_path, options):
    path = wheel(tmp_path, **options)
    assert gate.main([str(path)]) == 1


def test_core_wheel_rejects_conflicting_dist_info(tmp_path):
    path = wheel(tmp_path)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr(
            "aiguard-0.1.0.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: aiguard\nVersion: 0.1.0\n",
        )
    assert gate.main([str(path)]) == 1


def test_core_wheel_rejects_duplicate_metadata_member(tmp_path):
    path = wheel(tmp_path)
    metadata = f"thai_pii_redaction_core-{VERSION}.dist-info/METADATA"
    with zipfile.ZipFile(path, "a") as archive, pytest.warns(UserWarning, match="Duplicate name"):
        archive.writestr(metadata, f"Name: thai-pii-redaction-core\nVersion: {VERSION}\n")
    assert gate.main([str(path)]) == 1

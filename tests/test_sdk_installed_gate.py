"""Exercise the installed-artifact gate, including its public result type."""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "scripts/check_sdk_installed.py"
FACADE = """from types import SimpleNamespace
def detect(text):
    start = text.index(": ") + 2
    return [SimpleNamespace(data_type="PHONE", original_text=text[start:], span=(start,len(text)))]
def anonymize(text):
    return SimpleNamespace(text="[TOKEN]", mapping={"[TOKEN]":text})
def restore(text, mapping):
    return SimpleNamespace(text=mapping[text])
"""


def artifact(tmp_path, extra=None, changed=False):
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
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("amphrang/__init__.py", FACADE)
        if extra:
            archive.writestr(extra, "synthetic-private-marker")
    return target, wheel


def run(target, wheel):
    return subprocess.run(
        [sys.executable, "-I", str(CHECKER), str(target), str(wheel)],
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

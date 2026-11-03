"""Trusted Hosted inventories must cover the complete installed core wheel."""

from __future__ import annotations

import base64
import compileall
import csv
import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tests.test_hosted_core_packaging import (
    generated_wheel_fixture,
    rewrite_wheel,
    verify_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
METADATA = "thai_pii_redaction_core-0.1.0.dist-info"


def load_verifier():
    path = ROOT / "apps/hosted/core/verify_core_install.py"
    spec = importlib.util.spec_from_file_location("hosted_installed_core_verifier", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_record(root):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        name = path.relative_to(root).as_posix()
        if name == METADATA + "/RECORD":
            continue
        payload = path.read_bytes()
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, str(len(payload))))
    writer.writerow((METADATA + "/RECORD", "", ""))
    (root / METADATA / "RECORD").write_bytes(buffer.getvalue().encode())


def wheel_record(contents):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    for name, payload in sorted(contents.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, str(len(payload))))
    writer.writerow((METADATA + "/RECORD", "", ""))
    return buffer.getvalue().encode()


def installed_fixture(tmp_path, monkeypatch, *, untrusted_checker=None):
    source, wheel, contents = generated_wheel_fixture(tmp_path)
    if untrusted_checker is not None:
        name = "pii_redactor/_cache_identity.py"
        (source / name).write_bytes(untrusted_checker)
        contents[name] = untrusted_checker
        manifest_name = "pii_redactor/_artifact/manifest.json"
        manifest = json.loads(contents[manifest_name])
        manifest["runtime"][name] = hashlib.sha256(untrusted_checker).hexdigest()
        contents[manifest_name] = (
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
    contents[METADATA + "/WHEEL"] = (
        b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    )
    contents[METADATA + "/top_level.txt"] = b"app\npii_redactor\n"
    contents[METADATA + "/RECORD"] = wheel_record(contents)
    rewrite_wheel(wheel, contents)
    identity = verify_fixture(source, wheel)
    identity["schema_version"] = 2
    installed = tmp_path / "site-packages"
    installed.mkdir()
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(installed)
    (installed / METADATA / "INSTALLER").write_bytes(b"pip\n")
    (installed / METADATA / "REQUESTED").write_bytes(b"")
    (installed / METADATA / "direct_url.json").write_text(
        json.dumps(
            {
                "url": wheel.as_uri(),
                "archive_info": {"hashes": {"sha256": identity["wheel_sha256"]}},
            }
        ),
        encoding="utf-8",
    )
    write_record(installed)
    verifier = load_verifier()
    distribution = importlib.metadata.PathDistribution(installed / METADATA)
    monkeypatch.setattr(verifier.importlib.metadata, "distribution", lambda _name: distribution)
    monkeypatch.setattr(
        verifier.importlib.util,
        "find_spec",
        lambda name: importlib.machinery.PathFinder.find_spec(name, [str(installed)]),
    )
    context = tmp_path / "context"
    context.mkdir()
    (context / "wheels").mkdir()
    shutil.copyfile(wheel, context / "wheels" / wheel.name)
    (context / "verify_core_cache.py").write_bytes(
        (ROOT / "pii_redactor/_cache_identity.py").read_bytes()
    )
    identity["files"] = {
        path.relative_to(context).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in context.rglob("*")
        if path.is_file()
    }
    identity_path = context / "CORE_BUILD_IDENTITY.json"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    return verifier, identity, installed, context, identity_path


def test_generated_resources_do_not_change_the_canonical_installed_source_digest(
    tmp_path, monkeypatch
):
    verifier, identity, installed, context, identity_path = installed_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        verifier,
        "Path",
        lambda value: identity_path if value == "/app/CORE_BUILD_IDENTITY.json" else Path(value),
    )
    assert verifier.main() == 0


@pytest.mark.parametrize(
    "name",
    [
        "pii_redactor/data.bin",
        "pii_redactor/_artifact/manifest.json",
        "pii_redactor/_artifact/LICENSE",
        "pii_redactor/_artifact/requirements.lock",
        METADATA + "/licenses/licenses/OFL-1.1.txt",
        METADATA + "/METADATA",
    ],
)
@pytest.mark.parametrize("operation", ["change", "remove"])
def test_installed_core_rejects_changed_or_missing_bound_payloads(
    tmp_path, monkeypatch, name, operation
):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    path = installed / name
    if operation == "change":
        path.write_bytes(b"synthetic tampered installed payload\n")
    else:
        path.unlink()
    write_record(installed)
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)


@pytest.mark.parametrize(
    "name",
    [
        "pii_redactor/extra.py",
        "pii_redactor/_artifact/private.key",
        "pii_redactor/_artifact/.env",
        "pii_redactor/_artifact/extra.json",
        "pii_redactor/_artifact/unknown/",
        METADATA + "/private.key",
        METADATA + "/startup.pth",
    ],
)
def test_installed_core_rejects_extra_files_and_directories(tmp_path, monkeypatch, name):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    path = installed / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if name.endswith("/"):
        path.mkdir()
    else:
        path.write_bytes(b"synthetic unexpected installed payload\n")
    write_record(installed)
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)


@pytest.mark.parametrize("operation", ["missing", "wrong-hash", "wrong-size", "duplicate", "alias"])
def test_installed_core_rejects_incomplete_or_false_record_ownership(
    tmp_path, monkeypatch, operation
):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    record = installed / METADATA / "RECORD"
    rows = list(csv.reader(io.StringIO(record.read_text(encoding="utf-8"))))
    selected = next(row for row in rows if row[0] == "pii_redactor/data.bin")
    if operation == "missing":
        rows.remove(selected)
    elif operation == "wrong-hash":
        selected[1] = "sha256=" + "A" * 43
    elif operation == "wrong-size":
        selected[2] = "999999"
    elif operation == "duplicate":
        rows.append(selected)
    else:
        selected[0] = "pii_redactor/./data.bin"
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    record.write_bytes(buffer.getvalue().encode())
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)


def test_installed_namespace_cannot_be_claimed_by_another_distribution(tmp_path, monkeypatch):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    foreign = installed / "synthetic_foreign-1.0.dist-info"
    foreign.mkdir()
    (foreign / "METADATA").write_bytes(b"Name: synthetic-foreign\nVersion: 1.0\n")
    (foreign / "RECORD").write_bytes(b"pii_redactor/data.bin,,\n")
    with pytest.raises(ValueError, match="ownership"):
        verifier.verify_install(identity, context)


def test_uv_archive_metadata_without_hash_does_not_replace_the_trusted_wheel_digest(
    tmp_path, monkeypatch
):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    (installed / METADATA / "INSTALLER").write_bytes(b"uv")
    direct_url = installed / METADATA / "direct_url.json"
    value = json.loads(direct_url.read_text(encoding="utf-8"))
    value["archive_info"] = {}
    direct_url.write_text(json.dumps(value), encoding="utf-8")
    write_record(installed)
    assert verifier.verify_install(identity, context) is None
    (context / "wheels" / identity["wheel_filename"]).write_bytes(b"synthetic changed wheel")
    with pytest.raises(ValueError, match="context inputs"):
        verifier.verify_install(identity, context)


def test_installed_core_rejects_duplicate_distribution_owners(tmp_path, monkeypatch):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    duplicate = installed / "thai_pii_redaction_core-0.2.0.dist-info"
    duplicate.mkdir()
    (duplicate / "METADATA").write_bytes(b"Name: thai-pii-redaction-core\nVersion: 0.2.0\n")
    with pytest.raises(ValueError, match="ownership"):
        verifier.verify_install(identity, context)


def test_installed_core_rejects_foreign_namespace_origin_before_import(tmp_path, monkeypatch):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        verifier.importlib.util,
        "find_spec",
        lambda name: importlib.machinery.PathFinder.find_spec(name, [str(ROOT)]),
    )
    with pytest.raises(ValueError, match="origin"):
        verifier.verify_install(identity, context)


@pytest.mark.parametrize("field", ["schema_version", "installed_core", "cache_verifier"])
def test_current_installed_contract_cannot_downgrade_to_an_old_identity(
    tmp_path, monkeypatch, field
):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    identity.pop(field, None)
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)


def test_current_installed_contract_requires_generated_manifest_inventory(tmp_path, monkeypatch):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    identity["installed_core"]["generated"] = {}
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)


@pytest.mark.parametrize(
    ("section", "name"),
    [
        ("generated", "pii_redactor/_artifact/LICENSE"),
        ("metadata", METADATA + "/licenses/LICENSE"),
    ],
)
def test_identity_inventory_cannot_strip_files_from_the_bound_wheel(
    tmp_path, monkeypatch, section, name
):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    identity["installed_core"][section].pop(name)
    (installed / name).unlink()
    write_record(installed)
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)


@pytest.mark.parametrize(
    "name", ["verify_core_cache.py", "wheels/thai_pii_redaction_core-0.1.0-py3-none-any.whl"]
)
def test_installed_verification_rejects_changed_context_trust_inputs(tmp_path, monkeypatch, name):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    (context / name).write_bytes(b"raise AssertionError('untrusted checker must not execute')\n")
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)


def test_installer_created_current_tag_caches_are_verified_against_bound_source(
    tmp_path, monkeypatch
):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    assert compileall.compile_dir(installed, quiet=2, force=True)
    assert verifier.verify_install(identity, context) is None


def test_current_tag_cache_body_cannot_change_the_installed_runtime(tmp_path, monkeypatch):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    assert compileall.compile_dir(installed, quiet=2, force=True)
    source = installed / "pii_redactor/__init__.py"
    cache = Path(importlib.util.cache_from_source(str(source)))
    payload = cache.read_bytes()
    cache.write_bytes(payload[:16] + b"synthetic invalid executable body")
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)


def test_cache_validation_never_executes_the_installed_wheel_checker(tmp_path, monkeypatch):
    sentinel = tmp_path / "untrusted-wheel-checker-executed"
    payload = (
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('synthetic side effect')\n"
        "raise AssertionError('untrusted wheel checker executed')\n"
    ).encode()
    verifier, identity, installed, context, _ = installed_fixture(
        tmp_path, monkeypatch, untrusted_checker=payload
    )
    assert compileall.compile_dir(installed, quiet=2, force=True)
    assert verifier.verify_install(identity, context) is None
    assert not sentinel.exists()


def test_isolated_installed_verification_imports_no_core_or_optional_engine(tmp_path, monkeypatch):
    verifier, identity, installed, context, identity_path = installed_fixture(tmp_path, monkeypatch)
    program = """
import json, pathlib, runpy, sys
def no_runtime_import(event, args):
    if event == 'import' and args[0].split('.')[0] in {'app', 'pii_redactor', 'fastapi', 'torch', 'setuptools'}:
        raise AssertionError('core or optional engine import attempted')
sys.addaudithook(no_runtime_import)
sys.path.insert(0, sys.argv[1])
verifier = runpy.run_path(sys.argv[2])
context = pathlib.Path(sys.argv[3])
identity = json.loads((context / 'CORE_BUILD_IDENTITY.json').read_text())
verifier['verify_install'](identity, context)
assert 'app' not in sys.modules and 'pii_redactor' not in sys.modules
print('isolated_installed_identity_verified')
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            program,
            str(installed),
            str(ROOT / "apps/hosted/core/verify_core_install.py"),
            str(context),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "isolated_installed_identity_verified"


def test_inert_foreign_tag_cache_is_not_treated_as_current_executable_code(tmp_path, monkeypatch):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    cache = installed / "pii_redactor/__pycache__/__init__.foreign-tag.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"synthetic inert foreign-interpreter cache")
    assert verifier.verify_install(identity, context) is None


def test_stale_timestamp_cache_is_rejected_by_python_without_loading_its_body(
    tmp_path, monkeypatch
):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    source = installed / "pii_redactor/__init__.py"
    cache = Path(importlib.util.cache_from_source(str(source)))
    cache.parent.mkdir()
    stale_mtime = (int(source.stat().st_mtime) + 100) & 0xFFFFFFFF
    cache.write_bytes(
        importlib.util.MAGIC_NUMBER
        + b"\0" * 4
        + stale_mtime.to_bytes(4, "little")
        + source.stat().st_size.to_bytes(4, "little")
    )
    assert verifier.verify_install(identity, context) is None


@pytest.mark.parametrize("name", ["orphan.cpython-313.pyc", "unexpected.json"])
def test_unbound_cache_inventory_is_rejected(tmp_path, monkeypatch, name):
    verifier, identity, installed, context, _ = installed_fixture(tmp_path, monkeypatch)
    cache = installed / "pii_redactor/__pycache__" / name
    cache.parent.mkdir()
    cache.write_bytes(b"synthetic orphan cache residue")
    with pytest.raises(ValueError):
        verifier.verify_install(identity, context)

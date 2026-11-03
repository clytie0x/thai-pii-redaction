"""The operator identity binds live code and works without a source checkout."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import json
import marshal
import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path
from types import CodeType

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = "pii_redactor/_artifact"
OWNER = "thai_pii_redaction_core-0.1.0.dist-info"


def _run(root, before="", *, flags=()):
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        + before
        + "from pii_redactor.governance.operations import artifact_identity; "
        "print(artifact_identity())"
    )
    return subprocess.run(
        [sys.executable, "-I", *flags, "-c", code, str(root)],
        cwd=root.parent,
        env={**os.environ, "PYTHONUTF8": "1"},
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture
def source(tmp_path):
    target = tmp_path / "source"
    target.mkdir()
    for namespace in ("app", "pii_redactor"):
        shutil.copytree(
            ROOT / namespace,
            target / namespace,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_artifact"),
        )
    for pattern in (
        "VERSION",
        "pyproject.toml",
        "requirements*",
        "MANIFEST.in",
        "_aiguard_build.py",
    ):
        for item in ROOT.glob(pattern):
            if item.is_file():
                shutil.copyfile(item, target / item.name)
    for name in ("LICENSE", "NOTICE", "licenses/OFL-1.1.txt"):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, path)
    return target


def _manifest_install(source, target):
    """Use literal wheel metadata and RECORD rather than a fake metadata API."""
    target.mkdir()
    for namespace in ("app", "pii_redactor"):
        shutil.copytree(source / namespace, target / namespace)
    runtime = {
        p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for namespace in ("app", "pii_redactor")
        for p in (target / namespace).rglob("*")
        if p.is_file()
    }
    inputs = {
        p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in source.rglob("*")
        if p.is_file() and p.relative_to(source).parts[0] not in {"app", "pii_redactor"}
    }
    resource = target / RESOURCE
    resource.mkdir()
    for name in inputs:
        (resource / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, resource / name)
    manifest = {
        "format": 1,
        "distribution": "thai-pii-redaction-core",
        "version": "0.1.0",
        "runtime": runtime,
        "inputs": inputs,
    }
    (resource / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    metadata = target / OWNER
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: thai-pii-redaction-core\nVersion: 0.1.0\n", encoding="utf-8"
    )
    (metadata / "WHEEL").write_text(
        "Wheel-Version: 1.0\nGenerator: setuptools (83.0.0)\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        encoding="utf-8",
    )
    _record(target)


def _record(target):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.name != "RECORD":
            body = path.read_bytes()
            encoded = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=").decode()
            writer.writerow([path.relative_to(target).as_posix(), "sha256=" + encoded, len(body)])
    writer.writerow([OWNER + "/RECORD", "", ""])
    (target / OWNER / "RECORD").write_text(output.getvalue(), encoding="utf-8")


@pytest.fixture
def installed(source, tmp_path):
    target = tmp_path / "site-packages"
    _manifest_install(source, target)
    return target


def test_source_identity_changes_when_live_access_logging_helper_changes(source):
    before = _run(source)
    assert before.returncode == 0, before.stderr
    with (source / "app/access_logging.py").open("a", encoding="utf-8") as output:
        output.write("\nARTIFACT_TEST_REVISION = 1\n")
    after = _run(source)
    assert after.returncode == 0, after.stderr
    assert after.stdout != before.stdout


def test_installed_identity_uses_owned_resources_without_checkout_files(installed):
    result = _run(installed)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.strip()) == 64
    assert not (installed / "VERSION").exists()
    assert not (installed / "requirements.lock").exists()


@pytest.mark.parametrize(
    "change",
    [
        "tamper",
        "missing",
        "extra",
        "resource_missing",
        "resource_extra",
        "manifest_escape",
        "wrong_owner",
        "collision",
        "collision_traversal",
        "duplicate_owner",
        "metadata_extra",
        "metadata_tamper",
        "manifest_missing",
        "manifest_tamper",
        "missing_resources_with_source_decoy",
    ],
)
def test_installed_identity_rejects_unbound_or_unowned_content(installed, change):
    if change == "tamper":
        with (installed / "app/access_logging.py").open("a", encoding="utf-8") as output:
            output.write("\nUNBOUND = True\n")
    elif change == "missing":
        (installed / "pii_redactor/fonts/IBMPlexSansThaiLooped-Regular.ttf").unlink()
    elif change == "extra":
        (installed / "app/enterprise/unbound.py").write_text("UNBOUND = True\n")
    elif change == "resource_missing":
        (installed / RESOURCE / "requirements.lock").unlink()
    elif change == "resource_extra":
        (installed / RESOURCE / "private.key").write_text("synthetic forbidden resource")
    elif change == "manifest_escape":
        path = installed / RESOURCE / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["inputs"]["../VERSION"] = "a" * 64
        path.write_text(json.dumps(manifest))
        _record(installed)
    elif change == "wrong_owner":
        path = installed / OWNER / "METADATA"
        path.write_text(path.read_text().replace("thai-pii-redaction-core", "aiguard"))
    elif change in {"collision", "collision_traversal"}:
        metadata = installed / "other-1.0.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text("Metadata-Version: 2.4\nName: other\nVersion: 1.0\n")
        claim = "app/access_logging.py"
        if change == "collision_traversal":
            claim = "other-1.0.dist-info/../" + claim
        (metadata / "RECORD").write_text(claim + ",,\n")
    elif change == "duplicate_owner":
        shutil.copytree(installed / OWNER, installed / "duplicate-0.1.0.dist-info")
    elif change == "metadata_extra":
        (installed / OWNER / "unbound.py").write_text("UNBOUND = True\n")
    elif change == "metadata_tamper":
        (installed / OWNER / "WHEEL").write_text("Wheel-Version: 9.9\n")
    elif change == "manifest_missing":
        (installed / RESOURCE / "manifest.json").unlink()
    elif change == "manifest_tamper":
        path = installed / RESOURCE / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["version"] = "0.0.0"
        path.write_text(json.dumps(manifest))
    elif change == "missing_resources_with_source_decoy":
        for item in (installed / RESOURCE).iterdir():
            destination = installed / item.name
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copyfile(item, destination)
        shutil.rmtree(installed / RESOURCE)
    result = _run(installed)
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


def test_source_identity_requires_declared_locks(source):
    (source / "requirements-enterprise.lock").unlink()
    result = _run(source)
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


@pytest.mark.parametrize("namespace", ["app", "pii_redactor"])
def test_identity_rejects_foreign_loaded_first_party_module(source, namespace):
    result = _run(
        source,
        f"import types; foreign=types.ModuleType('{namespace}.foreign'); "
        f"foreign.__file__='/unowned/foreign.py'; sys.modules['{namespace}.foreign']=foreign; ",
    )
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


def test_identity_rejects_ambient_app_namespace(source, tmp_path):
    ambient = tmp_path / "ambient"
    (ambient / "app").mkdir(parents=True)
    (ambient / "app/__init__.py").write_text("")
    result = _run(source, f"sys.path.insert(0, {str(ambient)!r}); ")
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


def test_source_identity_binds_pdf_font_and_license(source):
    before = _run(source)
    assert before.returncode == 0, before.stderr
    with (source / "pii_redactor/fonts/IBMPlexSansThaiLooped-Regular.ttf").open("ab") as output:
        output.write(b"synthetic artifact change")
    font_changed = _run(source)
    assert font_changed.returncode == 0, font_changed.stderr
    assert font_changed.stdout != before.stdout
    with (source / "NOTICE").open("a", encoding="utf-8") as output:
        output.write("\nSynthetic notice change\n")
    license_changed = _run(source)
    assert license_changed.returncode == 0, license_changed.stderr
    assert license_changed.stdout != font_changed.stdout


def test_identity_rejects_linked_private_resource_directory(installed, tmp_path):
    original = installed / RESOURCE / "licenses"
    moved = tmp_path / "external_licenses"
    original.rename(moved)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(original), str(moved)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    else:
        original.symlink_to(moved, target_is_directory=True)
    result = _run(installed)
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


def test_installed_manifest_bytes_are_bound_even_when_json_is_equivalent(installed):
    before = _run(installed)
    assert before.returncode == 0, before.stderr
    path = installed / RESOURCE / "manifest.json"
    path.write_text(json.dumps(json.loads(path.read_text()), indent=2))
    _record(installed)
    after = _run(installed)
    assert after.returncode == 0, after.stderr
    assert after.stdout != before.stdout


def test_source_identity_rejects_case_insensitive_private_environment_file(source):
    (source / "app/.ENV.production").write_text("synthetic forbidden resource")
    result = _run(source)
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


def _tampered_timestamp_cache(target, flags=0):
    source = target / "app/access_logging.py"
    body = source.read_bytes()
    cache = Path(importlib.util.cache_from_source(str(source)))
    cache.parent.mkdir(exist_ok=True)
    info = source.stat()
    fingerprint = (
        (int(info.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little")
        + (len(body) & 0xFFFFFFFF).to_bytes(4, "little")
        if flags == 0
        else importlib.util.source_hash(body)
    )
    header = importlib.util.MAGIC_NUMBER + flags.to_bytes(4, "little") + fingerprint
    code = compile("CACHE_TEST_MARKER = 'tampered'\n", str(source), "exec", dont_inherit=True)
    cache.write_bytes(header + marshal.dumps(code))
    assert source.read_bytes() == body


@pytest.mark.parametrize("load_first", [False, True])
@pytest.mark.parametrize("flags", [0, 1, 3])
def test_identity_rejects_valid_header_tampered_cache(installed, load_first, flags):
    _tampered_timestamp_cache(installed, flags)
    before = ""
    if load_first:
        before = (
            "import app.access_logging as helper; "
            "assert helper.CACHE_TEST_MARKER == 'tampered'; print('tampered_cache_loaded'); "
        )
    result = _run(installed, before)
    if load_first:
        assert "tampered_cache_loaded" in result.stdout
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


@pytest.mark.parametrize("level", [0, 1, 2])
@pytest.mark.parametrize(
    "mode",
    [
        py_compile.PycInvalidationMode.TIMESTAMP,
        py_compile.PycInvalidationMode.CHECKED_HASH,
        py_compile.PycInvalidationMode.UNCHECKED_HASH,
    ],
)
def test_identity_accepts_source_derived_relocated_optimized_caches(source, level, mode):
    baseline = _run(source)
    assert baseline.returncode == 0, baseline.stderr
    py_compile.compile(
        str(source / "app/access_logging.py"),
        dfile="/previous/location/ภาษาไทย/app/access_logging.py",
        doraise=True,
        optimize=level,
        invalidation_mode=mode,
    )
    result = _run(
        source, "import app.access_logging; ", flags=("-" + "O" * level,) if level else ()
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == baseline.stdout


@pytest.mark.parametrize(
    "kind", ["oversized", "unsupported_flags", "unsupported_tag_shape", "bad_magic"]
)
def test_identity_rejects_unsupported_or_oversized_current_cache(source, kind):
    path = source / "app/access_logging.py"
    py_compile.compile(str(path), doraise=True)
    cache = Path(importlib.util.cache_from_source(str(path)))
    if kind == "oversized":
        with cache.open("r+b") as output:
            output.truncate(32 * 1024 * 1024)
    elif kind == "unsupported_flags":
        body = cache.read_bytes()
        cache.write_bytes(body[:4] + (0xFF).to_bytes(4, "little") + body[8:])
    elif kind == "unsupported_tag_shape":
        cache.rename(cache.with_name(cache.name.replace(".pyc", ".opt-unknown.pyc")))
    else:
        body = cache.read_bytes()
        cache.write_bytes(b"xxxx" + body[4:])
    result = _run(source)
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


def test_identity_allows_inactive_stale_timestamp_cache(source):
    baseline = _run(source)
    assert baseline.returncode == 0, baseline.stderr
    _tampered_timestamp_cache(source)
    path = Path(importlib.util.cache_from_source(str(source / "app/access_logging.py")))
    body = path.read_bytes()
    path.write_bytes(body[:8] + (0).to_bytes(4, "little") + body[12:])
    result = _run(source)
    assert result.returncode == 0, result.stderr
    assert result.stdout == baseline.stdout


def test_identity_keeps_other_interpreter_cache_tags_inert(source):
    baseline = _run(source)
    assert baseline.returncode == 0, baseline.stderr
    path = source / "app/__pycache__/access_logging.foreign-interpreter.pyc"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(b"inert foreign interpreter cache")
    result = _run(source)
    assert result.returncode == 0, result.stderr
    assert result.stdout == baseline.stdout


def test_identity_accepts_explicit_external_pycache_prefix(source, tmp_path):
    result = _run(source, flags=("-X", "pycache_prefix=" + str(tmp_path / "cache-prefix")))
    assert result.returncode == 0, result.stderr


def test_identity_supports_read_only_no_bytecode_write_mode(source):
    result = _run(source, flags=("-B",))
    assert result.returncode == 0, result.stderr


def test_identity_rejects_changed_loader_with_canonical_file_claim(source):
    result = _run(
        source,
        "import app.access_logging as helper; helper.__spec__.loader = object(); ",
    )
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr


def test_identity_accepts_valid_cache_with_different_marshal_reference_sharing(source):
    path = source / "app/access_logging.py"
    py_compile.compile(str(path), doraise=True)
    cache = Path(importlib.util.cache_from_source(str(path)))
    code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    retained_constants = tuple(code.co_consts)
    cache.write_bytes(cache.read_bytes()[:16] + marshal.dumps(code))
    result = _run(source, "import app.access_logging; ")
    assert result.returncode == 0, result.stderr


def test_identity_accepts_normalized_windows_source_import_paths(source):
    result = _run(source, "sys.path[0] = sys.path[0].replace(chr(92), '/'); ")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind", ["cycle", "huge_count", "depth", "trailing", "mixed_filenames"])
def test_identity_rejects_malformed_bounded_cache_data_without_importing_it(source, kind):
    path = source / "app/access_logging.py"
    py_compile.compile(str(path), doraise=True)
    cache = Path(importlib.util.cache_from_source(str(path)))
    original = cache.read_bytes()
    prefix = b"\xe3" + bytes(20)
    if kind == "cycle":
        body = prefix + b"r" + bytes(4)
    elif kind == "huge_count":
        body = prefix + b"(" + (0x7FFFFFFF).to_bytes(4, "little")
    elif kind == "depth":
        body = prefix + b")\x01" * 220 + b"N"
    elif kind == "trailing":
        body = original[16:] + b"unbound trailing cache bytes"
    else:
        code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
        values = list(code.co_consts)
        for index, value in enumerate(values):
            if isinstance(value, CodeType):
                values[index] = value.replace(co_filename="/unrelated/filename.py")
                break
        changed = code.replace(co_consts=tuple(values))
        body = marshal.dumps(changed)
    cache.write_bytes(original[:16] + body)
    result = _run(source)
    assert result.returncode != 0
    assert "artifact_identity_invalid" in result.stderr

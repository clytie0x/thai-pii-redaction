#!/usr/bin/env python3
"""Verify installed bytes with the trusted, source-bound Hosted inventory."""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
import io
import json
import re
import runpy
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

DISTRIBUTION = "thai-pii-redaction-core"
NAMESPACES = ("app", "pii_redactor")
RESOURCE = "pii_redactor/_artifact/"
MAX_CACHE_BYTES = 16 * 1024 * 1024
MAX_CACHE_FILES = 4096


class _Invalid(ValueError):
    pass


def _fail(reason):
    raise _Invalid("canonical installed " + reason)


def _name(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        _fail("inventory invalid")
    path = PurePosixPath(value)
    if (
        not path.parts
        or path.is_absolute()
        or path.as_posix() != value
        or any(
            part in {".", ".."}
            or part.lower().startswith(".env")
            or any(ord(char) < 32 for char in part)
            for part in path.parts
        )
        or path.suffix.lower() in {".key", ".pem", ".p12", ".pfx", ".env"}
    ):
        _fail("inventory invalid")
    return path


def _linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _path(root, name):
    current = root
    if _linked(current):
        _fail("path invalid")
    for part in _name(name).parts:
        current = current / part
        if _linked(current):
            _fail("path invalid")
    if not current.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        _fail("path invalid")
    return current


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected(identity):
    if (
        identity["schema_version"] != 2
        or identity["distribution"] != DISTRIBUTION
        or re.fullmatch(r"\d+\.\d+\.\d+", identity["version"]) is None
        or re.fullmatch(r"[0-9a-f]{64}", identity["source_tree_sha256"]) is None
        or re.fullmatch(r"[0-9a-f]{64}", identity["wheel_sha256"]) is None
        or re.fullmatch(r"[A-Za-z0-9_.+\-]+\.whl", identity["wheel_filename"]) is None
    ):
        _fail("identity invalid")
    inventory = identity["installed_core"]
    if (
        set(inventory) != {"format", "runtime", "generated", "metadata"}
        or type(inventory["format"]) is not int
        or inventory["format"] != 1
    ):
        _fail("identity invalid")
    metadata_root = DISTRIBUTION.replace("-", "_") + "-" + identity["version"] + ".dist-info"
    expected = {}
    folded = set()
    for section in ("runtime", "generated", "metadata"):
        entries = inventory[section]
        if not isinstance(entries, dict) or (section != "generated" and not entries):
            _fail("inventory invalid")
        for name, digest in entries.items():
            path = _name(name)
            if (
                not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or name.casefold() in folded
                or "__pycache__" in path.parts
                or path.suffix == ".pyc"
                or (
                    section == "runtime"
                    and (path.parts[0] not in NAMESPACES or name.startswith(RESOURCE))
                )
                or (section == "generated" and not name.startswith(RESOURCE))
                or (section == "metadata" and path.parts[0] != metadata_root)
            ):
                _fail("inventory invalid")
            folded.add(name.casefold())
            expected[name] = digest
    if (
        any(f"{name}/__init__.py" not in inventory["runtime"] for name in NAMESPACES)
        or any(
            f"{metadata_root}/{name}" not in inventory["metadata"] for name in ("METADATA", "WHEEL")
        )
        or (
            "pii_redactor/artifact_identity.py" in inventory["runtime"]
            and RESOURCE + "manifest.json" not in inventory["generated"]
        )
    ):
        _fail("inventory invalid")
    return expected, metadata_root


def _context_inputs(identity, context, expected, metadata_root):
    checker = identity["cache_verifier"]
    if set(checker) != {"file", "sha256"} or checker["file"] != "verify_core_cache.py":
        _fail("cache verifier invalid")
    helper = _path(context, checker["file"])
    wheel_name = "wheels/" + identity["wheel_filename"]
    wheel = _path(context, wheel_name)
    if (
        re.fullmatch(r"[0-9a-f]{64}", checker["sha256"]) is None
        or identity["files"][checker["file"]] != checker["sha256"]
        or _hash(helper) != checker["sha256"]
        or identity["files"][wheel_name] != identity["wheel_sha256"]
        or _hash(wheel) != identity["wheel_sha256"]
    ):
        _fail("context inputs invalid")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len({name.casefold().rstrip("/") for name in names}):
            _fail("wheel inventory invalid")
        for name in names:
            _name(name.removesuffix("/") if name.endswith("/") else name)
        if {name for name in names if not name.endswith("/")} != set(expected) | {
            metadata_root + "/RECORD"
        }:
            _fail("wheel inventory mismatch")
        if any(
            hashlib.sha256(archive.read(name)).hexdigest() != value
            for name, value in expected.items()
        ):
            _fail("wheel payload mismatch")
    return helper


def _ownership(root):
    owners = 0
    for distribution in importlib.metadata.distributions(path=[str(root)]):
        name = re.sub(r"[-_.]+", "-", distribution.metadata.get("Name", "")).lower()
        if name == DISTRIBUTION:
            owners += 1
        for record in distribution.files or ():
            relative = str(record).replace("\\", "/")
            path = PurePosixPath(relative)
            located = Path(distribution.locate_file(record)).resolve()
            if name != DISTRIBUTION and (
                (path.parts and path.parts[0] in NAMESPACES)
                or any(located.is_relative_to(root / namespace) for namespace in NAMESPACES)
            ):
                _fail("ownership invalid")
    if owners != 1:
        _fail("ownership invalid")


def _inventory(root, metadata_root, expected):
    installer_names = {
        metadata_root + "/" + name
        for name in ("INSTALLER", "REQUESTED", "direct_url.json", "uv_cache.json", "RECORD")
    }
    allowed_dirs = {
        parent.as_posix()
        for name in set(expected) | installer_names
        for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    }
    allowed_dirs.update(
        (PurePosixPath(name).parent / "__pycache__").as_posix()
        for name in expected
        if name.endswith(".py")
    )
    files = {}
    folded = set()
    for base in (*NAMESPACES, metadata_root):
        for candidate in _path(root, base).rglob("*"):
            name = candidate.relative_to(root).as_posix()
            _name(name)
            path = _path(root, name)
            if path.is_dir():
                if name not in allowed_dirs:
                    _fail("inventory invalid")
                continue
            if not path.is_file() or name.casefold() in folded:
                _fail("inventory invalid")
            folded.add(name.casefold())
            files[name] = path
    caches = {
        name: path for name, path in files.items() if "__pycache__" in PurePosixPath(name).parts
    }
    installed = set(files) - set(caches)
    dynamic = installed & installer_names
    if installed != set(expected) | dynamic or not {
        metadata_root + "/INSTALLER",
        metadata_root + "/RECORD",
    }.issubset(dynamic):
        _fail("inventory mismatch")
    for name, digest in expected.items():
        if _hash(files[name]) != digest:
            _fail("payload mismatch")
    return files, caches, dynamic


def _installer(files, metadata_root, identity):
    installer = files[metadata_root + "/INSTALLER"].read_bytes()
    if installer not in {b"pip", b"pip\n", b"uv", b"uv\n"}:
        _fail("installer metadata invalid")
    requested = files.get(metadata_root + "/REQUESTED")
    if requested and requested.read_bytes() != b"":
        _fail("installer metadata invalid")
    direct_url = files.get(metadata_root + "/direct_url.json")
    if direct_url:
        value = json.loads(direct_url.read_text(encoding="utf-8"))
        archive = value["archive_info"]
        if (
            set(value) != {"url", "archive_info"}
            or not value["url"].startswith("file:")
            or not set(archive).issubset({"hash", "hashes"})
            or (not archive and installer.strip() != b"uv")
            or ("hash" in archive and archive["hash"] != "sha256=" + identity["wheel_sha256"])
            or ("hashes" in archive and archive["hashes"] != {"sha256": identity["wheel_sha256"]})
        ):
            _fail("installer metadata invalid")
    uv_cache = files.get(metadata_root + "/uv_cache.json")
    if uv_cache:
        value = json.loads(uv_cache.read_text(encoding="utf-8"))
        timestamp = value["timestamp"]
        if (
            installer.strip() != b"uv"
            or set(value) != {"timestamp", "commit", "tags", "env", "directories"}
            or set(timestamp) != {"secs_since_epoch", "nanos_since_epoch"}
            or type(timestamp["secs_since_epoch"]) is not int
            or type(timestamp["nanos_since_epoch"]) is not int
            or timestamp["secs_since_epoch"] < 0
            or not 0 <= timestamp["nanos_since_epoch"] < 1_000_000_000
            or value["commit"] is not None
            or value["tags"] is not None
            or value["env"] != {}
            or value["directories"] != {}
        ):
            _fail("installer metadata invalid")


def _record(files, caches, expected, dynamic, metadata_root):
    record_name = metadata_root + "/RECORD"
    rows = csv.reader(io.StringIO(files[record_name].read_text(encoding="utf-8")), strict=True)
    recorded = set()
    folded = set()
    for row in rows:
        if len(row) != 3:
            _fail("RECORD invalid")
        name, digest, size = row
        _name(name)
        if name.casefold() in folded or name not in files:
            _fail("RECORD ownership invalid")
        folded.add(name.casefold())
        recorded.add(name)
        if name == record_name:
            if digest or size:
                _fail("RECORD invalid")
            continue
        if name in caches and not digest and not size:
            continue
        payload = files[name].read_bytes()
        actual = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=").decode()
        if digest != "sha256=" + actual or size != str(len(payload)):
            _fail("RECORD payload invalid")
    if recorded - set(caches) != set(expected) | dynamic:
        _fail("RECORD ownership invalid")


def _origins(root, context):
    for namespace in NAMESPACES:
        spec = importlib.util.find_spec(namespace)
        expected = _path(root, namespace + "/__init__.py")
        if (
            spec is None
            or spec.origin is None
            or Path(spec.origin).absolute() != expected
            or type(spec.loader) is not importlib.machinery.SourceFileLoader
            or [Path(value).absolute() for value in (spec.submodule_search_locations or ())]
            != [expected.parent]
            or expected.is_relative_to(context)
        ):
            _fail("namespace origin mismatch")


def _caches(root, expected, caches, helper):
    sources = {name: _path(root, name) for name in expected if name.endswith(".py")}
    candidates = set(caches.values())
    for source in sources.values():
        for level in ("", "1", "2"):
            cache = Path(importlib.util.cache_from_source(str(source), optimization=level))
            if cache.exists() or cache.is_symlink():
                candidates.add(cache)
    if len(candidates) > MAX_CACHE_FILES:
        _fail("cache inventory invalid")
    if not candidates:
        return
    # Only this context helper is executed, after its independently bound hash.
    checker = runpy.run_path(str(helper))["verify_cache_body"]
    for cache in candidates:
        for path in (cache, *cache.parents):
            if _linked(path):
                _fail("cache path invalid")
        source = Path(importlib.util.source_from_cache(str(cache)))
        name = source.relative_to(root).as_posix()
        if name not in sources or not cache.is_file():
            _fail("cache inventory invalid")
        suffix = cache.name[len(source.stem) + 1 :].split(".")
        if (
            not cache.name.startswith(source.stem + ".")
            or len(suffix) not in {2, 3}
            or suffix[-1] != "pyc"
            or re.fullmatch(r"[A-Za-z0-9_-]+", suffix[0]) is None
        ):
            _fail("cache inventory invalid")
        if suffix[0] != sys.implementation.cache_tag:
            continue
        if cache.stat().st_size > MAX_CACHE_BYTES:
            _fail("cache inventory invalid")
        level = 0
        if len(suffix) == 3:
            if suffix[1] not in {"opt-0", "opt-1", "opt-2"}:
                _fail("cache inventory invalid")
            level = int(suffix[1][-1])
        payload = cache.read_bytes()
        if (
            len(payload) < 16
            or payload[:4] != importlib.util.MAGIC_NUMBER
            or int.from_bytes(payload[4:8], "little") not in {0, 1, 3}
        ):
            _fail("cache invalid")
        info = source.stat()
        if int.from_bytes(payload[4:8], "little") == 0 and (
            int.from_bytes(payload[8:12], "little") != int(info.st_mtime) & 0xFFFFFFFF
            or int.from_bytes(payload[12:16], "little") != info.st_size & 0xFFFFFFFF
        ):
            continue
        if len(payload) == 16:
            _fail("cache invalid")
        checker(source.read_bytes(), payload[16:], level)


def verify_install(identity, context):
    try:
        context = Path(context).absolute()
        expected, metadata_root = _expected(identity)
        helper = _context_inputs(identity, context, expected, metadata_root)
        distribution = importlib.metadata.distribution(DISTRIBUTION)
        if distribution.metadata.get_all("Name") != [DISTRIBUTION] or distribution.metadata.get_all(
            "Version"
        ) != [identity["version"]]:
            _fail("distribution identity invalid")
        root = Path(distribution.locate_file("")).absolute()
        _ownership(root)
        files, caches, dynamic = _inventory(root, metadata_root, expected)
        _installer(files, metadata_root, identity)
        _record(files, caches, expected, dynamic, metadata_root)
        digest = hashlib.sha256()
        for name in sorted(identity["installed_core"]["runtime"]):
            digest.update(name.encode("utf-8") + b"\0" + files[name].read_bytes())
        if digest.hexdigest() != identity["source_tree_sha256"]:
            _fail("source digest mismatch")
        _origins(root, context)
        _caches(root, expected, caches, helper)
    except _Invalid as error:
        raise ValueError(str(error)) from None
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        ImportError,
        SyntaxError,
        OverflowError,
        csv.Error,
        zipfile.BadZipFile,
    ):
        raise ValueError("canonical installed identity invalid") from None


def main() -> int:
    identity_path = Path("/app/CORE_BUILD_IDENTITY.json")
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    verify_install(identity, identity_path.parent)
    print("Canonical first-party core identity and installed source verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

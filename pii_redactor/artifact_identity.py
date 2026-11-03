"""Bind source and current-interpreter caches, not process or host attestation.

The loaded checker is a trust root. It cannot attest its own already executed
instructions, prior imports, memory patches, or files changed after this check.
Dependency and host acceptance remain separate.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import re
import stat
import sys
import tomllib
from pathlib import Path, PurePosixPath

DISTRIBUTION = "thai-pii-redaction-core"
NAMESPACES = ("app", "pii_redactor")
RESOURCE = "pii_redactor/_artifact"
MAX_CACHE_BYTES = 16 * 1024 * 1024
MAX_CACHE_FILES = 4096


def _fail():
    raise ValueError("artifact_identity_invalid")


def _name(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        _fail()
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
        _fail()
    return path


def _path(root, name):
    relative = _name(name)
    current = root
    if _linked(current):
        _fail()
    for part in relative.parts:
        current = current / part
        if _linked(current):
            _fail()
    if not current.resolve(strict=True).is_relative_to(root):
        _fail()
    return current


def _linked(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory(root, bases, *, resources=False):
    result = {}
    folded = set()
    for base in bases:
        directory = _path(root, base)
        if not directory.is_dir():
            _fail()
        for candidate in directory.rglob("*"):
            name = candidate.relative_to(root).as_posix()
            relative = _name(name)
            if "__pycache__" in relative.parts:
                continue
            if candidate.suffix == ".pyc":
                _fail()
            if not resources and (name == RESOURCE or name.startswith(RESOURCE + "/")):
                continue
            path = _path(root, name)
            if path.is_dir():
                continue
            if not path.is_file() or name.casefold() in folded:
                _fail()
            folded.add(name.casefold())
            result[name] = _hash(path)
    return result


def _inputs(root):
    metadata = tomllib.loads(_path(root, "pyproject.toml").read_text(encoding="utf-8"))
    if metadata["project"]["name"] != DISTRIBUTION:
        _fail()
    settings = metadata["tool"]["aiguard"]["artifact"]
    locks = settings["locks"]
    if not isinstance(locks, list) or not locks or len(locks) != len(set(locks)):
        _fail()
    if set(locks) != {p.name for p in root.glob("requirements*.lock")}:
        _fail()
    names = {"VERSION", "pyproject.toml", *locks, *settings["build-inputs"]}
    names.update(p.name for p in root.glob("requirements*.txt"))
    dynamic = metadata["tool"]["setuptools"]["dynamic"]
    for declaration in (dynamic["dependencies"], *dynamic["optional-dependencies"].values()):
        files = declaration["file"]
        names.update([files] if isinstance(files, str) else files)
    for pattern in metadata["project"]["license-files"]:
        matches = list(root.glob(pattern))
        if not matches:
            _fail()
        names.update(p.relative_to(root).as_posix() for p in matches)
    if len({name.casefold() for name in names}) != len(names):
        _fail()
    return {name: _hash(_path(root, name)) for name in sorted(names)}


def source_manifest(root):
    """Build inputs and the complete canonical payload, without importing engines."""
    root = Path(root).absolute()
    runtime = _inventory(root, NAMESPACES)
    for namespace in NAMESPACES:
        if f"{namespace}/__init__.py" not in runtime:
            _fail()
    version = _path(root, "VERSION").read_text(encoding="utf-8").strip()
    if re.fullmatch(r"\d+\.\d+\.\d+", version) is None:
        _fail()
    return {
        "format": 1,
        "distribution": DISTRIBUTION,
        "version": version,
        "runtime": runtime,
        "inputs": _inputs(root),
    }


def _origins(root, runtime):
    for namespace in NAMESPACES:
        spec = importlib.util.find_spec(namespace)
        expected = _path(root, f"{namespace}/__init__.py")
        if (
            spec is None
            or spec.origin is None
            or Path(spec.origin).absolute() != expected
            or [Path(value).absolute() for value in (spec.submodule_search_locations or ())]
            != [expected.parent]
        ):
            _fail()
    for name, module in tuple(sys.modules.items()):
        if name.split(".", 1)[0] not in NAMESPACES:
            continue
        origin = getattr(module, "__file__", None)
        if not origin:
            _fail()
        path = Path(origin).absolute()
        if not path.is_relative_to(root):
            _fail()
        relative = path.relative_to(root).as_posix()
        if relative not in runtime or _path(root, relative) != path:
            _fail()
        module_path = name.replace(".", "/")
        if relative not in {module_path + ".py", module_path + "/__init__.py"}:
            _fail()
        if hasattr(module, "__path__") and [
            Path(value).absolute() for value in module.__path__
        ] != [path.parent]:
            _fail()
        spec = getattr(module, "__spec__", None)
        loader = getattr(module, "__loader__", None)
        if (
            spec is None
            or type(loader) is not importlib.machinery.SourceFileLoader
            or spec.loader is not loader
            or Path(spec.origin).absolute() != path
            or Path(loader.path).absolute() != path
            or Path(spec.cached).absolute()
            != Path(importlib.util.cache_from_source(str(path))).absolute()
            or Path(getattr(module, "__cached__", "")).absolute() != Path(spec.cached).absolute()
        ):
            _fail()


def _verify_cache(source, cache, level):
    """Compare executable bytes with a trusted compile, allowing path relocation."""
    from pii_redactor._cache_identity import verify_cache_body

    for path in (cache, *cache.parents):
        if _linked(path):
            _fail()
    if not cache.is_file() or cache.stat().st_size > MAX_CACHE_BYTES:
        _fail()
    with cache.open("rb") as stream:
        header = stream.read(16)
    if (
        len(header) != 16
        or header[:4] != importlib.util.MAGIC_NUMBER
        or int.from_bytes(header[4:8], "little") not in {0, 1, 3}
    ):
        _fail()
    info = source.stat()
    if int.from_bytes(header[4:8], "little") == 0 and (
        int.from_bytes(header[8:12], "little") != int(info.st_mtime) & 0xFFFFFFFF
        or int.from_bytes(header[12:16], "little") != info.st_size & 0xFFFFFFFF
    ):
        # SourceFileLoader always rejects stale timestamp caches. Read-only
        # source checkouts may retain them because Python cannot rewrite them.
        return
    data = source.read_bytes()
    with cache.open("rb") as stream:
        contents = stream.read(MAX_CACHE_BYTES + 1)
    if (
        not 16 < len(contents) <= MAX_CACHE_BYTES
        or contents[:4] != importlib.util.MAGIC_NUMBER
        or int.from_bytes(contents[4:8], "little") not in {0, 1, 3}
    ):
        _fail()
    verify_cache_body(data, contents[16:], level)


def _caches(root, source_names):
    """Check all current-tag namespace caches, including not-yet-imported modules."""
    sources = {_path(root, name) for name in source_names if name.endswith(".py")}
    candidates = set()
    expected_sources = {}
    for namespace in NAMESPACES:
        for candidate in _path(root, namespace).rglob("*"):
            relative = candidate.relative_to(root)
            if "__pycache__" not in relative.parts:
                continue
            path = _path(root, relative.as_posix())
            if path.is_dir():
                continue
            if path.suffix != ".pyc":
                _fail()
            candidates.add(path)
            if len(candidates) > MAX_CACHE_FILES:
                _fail()
    # cache_from_source also covers an explicit interpreter pycache_prefix.
    for source in sources:
        for level in ("", "1", "2"):
            path = Path(importlib.util.cache_from_source(str(source), optimization=level))
            expected_sources[path] = source
            if path.exists() or path.is_symlink():
                candidates.add(path)
                if len(candidates) > MAX_CACHE_FILES:
                    _fail()
    for cache in candidates:
        source = expected_sources.get(cache)
        if source is None:
            source = Path(importlib.util.source_from_cache(str(cache)))
        if source not in sources:
            _fail()
        suffix = cache.name[len(source.stem) + 1 :].split(".")
        if (
            not cache.name.startswith(source.stem + ".")
            or len(suffix) not in {2, 3}
            or suffix[-1] != "pyc"
            or re.fullmatch(r"[A-Za-z0-9_-]+", suffix[0]) is None
        ):
            _fail()
        # A different cache tag is never selected by this interpreter's source
        # loader. Its bytes do not become part of the current runtime identity.
        if suffix[0] != sys.implementation.cache_tag:
            continue
        level = 0
        if len(suffix) == 3:
            if suffix[1] not in {"opt-0", "opt-1", "opt-2"}:
                _fail()
            level = int(suffix[1][-1])
        _verify_cache(source, cache, level)


def _normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _owners(root):
    owners = []
    for pattern in ("*.dist-info", "*.egg-info"):
        for candidate in root.glob(pattern):
            _path(root, candidate.name)
            if candidate.is_dir():
                for metadata_file in ("METADATA", "PKG-INFO", "RECORD", "direct_url.json"):
                    path = candidate / metadata_file
                    if path.exists() or path.is_symlink():
                        _path(root, path.relative_to(root).as_posix())
    for distribution in importlib.metadata.distributions(path=[str(root)]):
        name = _normalized(distribution.metadata.get("Name", ""))
        records = distribution.files
        if name == DISTRIBUTION:
            owners.append(distribution)
        for record in records or ():
            relative = str(record).replace("\\", "/")
            top = PurePosixPath(relative).parts[0]
            located = Path(distribution.locate_file(record)).resolve()
            canonical_claim = any(located.is_relative_to(root / base) for base in NAMESPACES)
            if (top in NAMESPACES or canonical_claim) and name != DISTRIBUTION:
                _fail()
    if len(owners) != 1:
        _fail()
    return owners[0]


def _installed(root):
    owner = _owners(root)
    if (
        len(owner.metadata.get_all("Name", [])) != 1
        or len(owner.metadata.get_all("Version", [])) != 1
    ):
        _fail()
    direct_url = owner.read_text("direct_url.json")
    if direct_url and json.loads(direct_url).get("dir_info", {}).get("editable") is True:
        _fail()
    manifest_path = _path(root, RESOURCE + "/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        set(manifest) != {"format", "distribution", "version", "runtime", "inputs"}
        or manifest["format"] != 1
        or manifest["distribution"] != DISTRIBUTION
        or manifest["version"] != owner.version
    ):
        _fail()
    for inventory in (manifest["runtime"], manifest["inputs"]):
        if not isinstance(inventory, dict) or not inventory:
            _fail()
        for name, value in inventory.items():
            _name(name)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                _fail()
    runtime = _inventory(root, NAMESPACES)
    if runtime != manifest["runtime"]:
        _fail()
    resource_root = _path(root, RESOURCE)
    inputs = _inputs(resource_root)
    if inputs != manifest["inputs"]:
        _fail()
    resources = _inventory(root, [RESOURCE], resources=True)
    expected_resources = {RESOURCE + "/" + name: value for name, value in inputs.items()}
    expected_resources[RESOURCE + "/manifest.json"] = _hash(manifest_path)
    if resources != expected_resources:
        _fail()
    if _path(resource_root, "VERSION").read_text(encoding="utf-8").strip() != owner.version:
        _fail()
    expected = {**runtime, **resources}
    records = owner.files
    if not records:
        _fail()
    recorded = set()
    metadata = {}
    metadata_roots = set()
    expected_metadata_root = DISTRIBUTION.replace("-", "_") + "-" + owner.version + ".dist-info"
    for record in records:
        name = str(record).replace("\\", "/")
        path = _name(name)
        if "__pycache__" in path.parts:
            if path.suffix != ".pyc":
                _fail()
            continue
        if name in recorded:
            _fail()
        recorded.add(name)
        top = path.parts[0]
        if top in NAMESPACES or top.endswith(".dist-info"):
            installed = _path(root, name)
            if Path(owner.locate_file(record)).absolute() != installed:
                _fail()
            if top.endswith(".dist-info"):
                if top != expected_metadata_root:
                    _fail()
                metadata_roots.add(top)
                if path.name in {"RECORD", "INSTALLER", "direct_url.json", "REQUESTED"}:
                    continue
                metadata[name] = _hash(installed)
            if (
                record.hash is None
                or record.hash.mode != "sha256"
                or record.hash.value
                != base64.urlsafe_b64encode(hashlib.sha256(installed.read_bytes()).digest())
                .rstrip(b"=")
                .decode()
                or record.size != installed.stat().st_size
            ):
                _fail()
        else:
            _fail()
    if (
        len(metadata_roots) != 1
        or not any(name.endswith("/METADATA") for name in metadata)
        or not any(name.endswith("/WHEEL") for name in metadata)
        or {name for name in recorded if PurePosixPath(name).parts[0] in NAMESPACES}
        != set(expected)
    ):
        _fail()
    if set(_inventory(root, metadata_roots, resources=True)) != {
        name for name in recorded if PurePosixPath(name).parts[0] in metadata_roots
    }:
        _fail()
    metadata[RESOURCE + "/manifest.json"] = _hash(manifest_path)
    return manifest, metadata


def runtime_identity():
    """Fail closed on mixed origins, missing resources, changed bytes or ownership."""
    try:
        root = Path(__file__).absolute().parent.parent
        if (
            (root / "pyproject.toml").exists()
            and not (root / RESOURCE).exists()
            and not (root / RESOURCE).is_symlink()
            and not any(root.glob("*.dist-info"))
        ):
            manifest = source_manifest(root)
            layout = "source"
            metadata = {}
        else:
            manifest, metadata = _installed(root)
            layout = "installed-wheel"
        cache_sources = set(manifest["runtime"])
        cache_sources.update(
            name if layout == "source" else RESOURCE + "/" + name
            for name in manifest["inputs"]
            if name.endswith(".py")
        )
        _caches(root, cache_sources)
        _origins(root, manifest["runtime"])
        value = {"layout": layout, "manifest": manifest, "build_metadata": metadata}
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        ImportError,
        SyntaxError,
        OverflowError,
    ):
        raise ValueError("artifact_identity_invalid") from None

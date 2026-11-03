"""Qualify an explicitly supplied SDK/core wheel pair outside source."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

_OWNERS = {"amphrang": {"amphrang"}, "thai-pii-redaction-core": {"app", "pii_redactor"}}


def compare_wheels(first: Path, second: Path) -> None:
    """Compare every unpacked byte, including metadata and RECORD."""
    with zipfile.ZipFile(first) as left, zipfile.ZipFile(second) as right:
        if any(
            len(archive.namelist()) != len(set(archive.namelist())) for archive in (left, right)
        ):
            raise ValueError("wheel_duplicate_member")
        left_files = {name: left.read(name) for name in left.namelist()}
        right_files = {name: right.read(name) for name in right.namelist()}
    if left_files != right_files:
        raise ValueError("rebuilt_wheel_bytes_mismatch")


def _normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _installed_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    parts = path.parts
    if len(parts) > 2 and parts[0].endswith(".data") and parts[1] in {"purelib", "platlib"}:
        path = PurePosixPath(*parts[2:])
    if (
        not parts
        or path.is_absolute()
        or ".." in parts
        or any(part.startswith(".env") for part in parts)
        or path.suffix in {".key", ".env", ".pem", ".p12", ".pfx"}
    ):
        raise ValueError("wheel_private_resource_or_path_invalid")
    return path


def verify_supplied_tree(directory: Path) -> None:
    """Require an exact SHA256SUMS inventory before using supplied build inputs."""
    directory = directory.resolve(strict=True)
    expected: dict[str, str] = {}
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise ValueError("supplied_manifest_invalid")
        digest, name = match.groups()
        path = _installed_path(name)
        if path.as_posix() != name or name in expected or name == "SHA256SUMS":
            raise ValueError("supplied_manifest_invalid")
        expected[name] = digest
    observed = {
        candidate.relative_to(directory).as_posix(): candidate
        for candidate in directory.rglob("*")
        if candidate.is_file() and candidate != directory / "SHA256SUMS"
    }
    if not expected or set(observed) != set(expected):
        raise ValueError("supplied_inventory_mismatch")
    for name, candidate in observed.items():
        if (
            candidate.is_symlink()
            or not candidate.resolve().is_relative_to(directory)
            or hashlib.sha256(candidate.read_bytes()).hexdigest() != expected[name]
        ):
            raise ValueError("supplied_digest_mismatch")


def _wheel(target: Path, wheel: Path, owner: str) -> tuple[str, set[str]]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("wheel_duplicate_member")
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ValueError("wheel_metadata_missing")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        if len(metadata.get_all("Name", [])) != 1 or _normalized(metadata.get("Name", "")) != owner:
            raise ValueError("first_party_identity_invalid")
        version = metadata.get("Version", "")
        if (
            len(metadata.get_all("Version", [])) != 1
            or re.fullmatch(r"\d+\.\d+\.\d+", version) is None
        ):
            raise ValueError("first_party_version_invalid")
        if owner == "amphrang":
            pins = [
                requirement
                for requirement in metadata.get_all("Requires-Dist", [])
                if _normalized(re.split(r"[<>=!~;\[\s]", requirement, maxsplit=1)[0])
                in {"thai-pii-redaction-core", "aiguard"}
            ]
            if pins != [f"thai-pii-redaction-core=={version}"]:
                raise ValueError("sdk_core_pin_invalid")
        owned: set[str] = set()
        metadata_path = PurePosixPath(metadata_names[0])
        for name in names:
            if name.endswith("/"):
                continue
            path = _installed_path(name)
            top = path.parts[0]
            if top.endswith(".dist-info"):
                if top != metadata_path.parts[0]:
                    raise ValueError("wheel_metadata_owner_invalid")
                if path.name == "RECORD":
                    continue
            elif top not in _OWNERS[owner]:
                raise ValueError("wheel_namespace_owner_invalid")
            else:
                owned.add(path.as_posix())
            installed = (target / path.as_posix()).resolve(strict=True)
            if (
                not installed.is_relative_to(target)
                or hashlib.sha256(installed.read_bytes()).digest()
                != hashlib.sha256(archive.read(name)).digest()
            ):
                raise ValueError("installed_first_party_bytes_mismatch")
        if not all(f"{namespace}/__init__.py" in owned for namespace in _OWNERS[owner]):
            raise ValueError("first_party_namespace_missing")
        return version, owned


def _check_owners(target: Path, version: str) -> None:
    observed: dict[str, int] = {}
    for distribution in importlib.metadata.distributions(path=[str(target)]):
        name = _normalized(distribution.metadata.get("Name", ""))
        if name in _OWNERS:
            observed[name] = observed.get(name, 0) + 1
            if distribution.version != version:
                raise ValueError("installed_first_party_version_mismatch")
            direct_url = distribution.read_text("direct_url.json")
            if direct_url and json.loads(direct_url).get("dir_info", {}).get("editable") is True:
                raise ValueError("editable_first_party_core_denied")
        for record in distribution.files or ():
            top = PurePosixPath(str(record).replace("\\", "/")).parts[0]
            if top in {"amphrang", "app", "pii_redactor"} and top not in _OWNERS.get(name, set()):
                raise ValueError("installed_namespace_collision")
    if observed != dict.fromkeys(_OWNERS, 1):
        raise ValueError("installed_first_party_distribution_missing_or_duplicate")


def check(target: Path, wheel: Path, core_wheel: Path) -> None:
    target = target.resolve(strict=True)
    if (
        os.environ.get("AMPHRANG_NER_ENGINE") != "thainer"
        or os.environ.get("PYTHAINLP_OFFLINE") != "1"
    ):
        raise ValueError("offline_profile_required")
    sdk_version, sdk_files = _wheel(target, wheel, "amphrang")
    core_version, core_files = _wheel(target, core_wheel, "thai-pii-redaction-core")
    if sdk_version != core_version:
        raise ValueError("first_party_version_pair_mismatch")
    _check_owners(target, sdk_version)
    actual = {
        candidate.relative_to(target).as_posix()
        for namespace in ("amphrang", "app", "pii_redactor")
        for candidate in (target / namespace).rglob("*")
        if candidate.is_file()
        and "__pycache__" not in candidate.parts
        and candidate.suffix != ".pyc"
    }
    if actual != sdk_files | core_files:
        raise ValueError("installed_namespace_inventory_mismatch")
    for name, module in tuple(sys.modules.items()):
        if name.split(".", 1)[0] in {"amphrang", "app", "pii_redactor"}:
            source = getattr(module, "__file__", None)
            if source is None or not Path(source).resolve().is_relative_to(target):
                raise ValueError("ambient_first_party_module_denied")
    sys.path.insert(0, str(target))
    import amphrang

    from pii_redactor.detectors.aggregate import detect_all
    from pii_redactor.models import Entity

    if amphrang.Entity is not Entity or amphrang._detect_all is not detect_all:
        raise ValueError("sdk_canonical_identity_invalid")
    text = "Synthetic contact: 081-234-5678"
    entities = amphrang.detect(text)
    if not any(
        e.data_type == "PHONE" and e.original_text == text[slice(*e.span)] for e in entities
    ):
        raise ValueError("installed_sdk_detection_invalid")
    masked = amphrang.anonymize(text)
    if (
        not masked.mapping
        or "081-234-5678" in masked.text
        or amphrang.restore(masked.text, masked.mapping).text != text
    ):
        raise ValueError("installed_sdk_roundtrip_invalid")
    for name, module in tuple(sys.modules.items()):
        if name.split(".", 1)[0] in {"amphrang", "app", "pii_redactor"}:
            source = getattr(module, "__file__", None)
            if source and not Path(source).resolve().is_relative_to(target):
                raise ValueError("first_party_source_tree_import")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("core_wheel", type=Path)
    args = parser.parse_args(argv)
    try:
        check(args.target, args.wheel, args.core_wheel)
    except Exception:
        print(
            "Installed SDK/core qualification failed; details and values suppressed.",
            file=sys.stderr,
        )
        return 1
    print(
        "Supplied SDK/core wheel identities, installed bytes and offline synthetic roundtrip passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

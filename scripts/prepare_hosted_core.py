#!/usr/bin/env python3
"""Prepare an offline Hosted context from explicit, source-bound artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import runpy
import shutil
import subprocess
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
HOSTED = ROOT / "apps" / "hosted"
SOURCE_INTEGRITY = runpy.run_path(str(HOSTED / "sync" / "source_integrity.py"))
PORT_FILES = (
    ".dockerignore",
    "Dockerfile",
    "VERSION",
    "LICENSE",
    "NOTICE",
    "requirements.lock",
    "requirements-aift-security.lock",
    "verify_thainer_assets.py",
    "verify_core_install.py",
    "aift_auth.py",
    "aift_gateway.py",
    "aift_report_policy.py",
    "healthcheck.py",
)
MODEL_SHA256 = "bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(source: Path) -> dict[str, Path]:
    return SOURCE_INTEGRITY["source_files"](source)


def source_tree_sha256(source: Path) -> str:
    return SOURCE_INTEGRITY["source_tree_sha256"](source)


def verify_core_wheel(
    wheel: Path, source: Path, *, expected_sha256: str, expected_source_sha256: str
) -> dict[str, str]:
    if wheel.is_symlink() or not re.fullmatch(r"[A-Za-z0-9_.+\-]+\.whl", wheel.name):
        raise ValueError("invalid first-party core wheel path")
    if sha256(wheel) != expected_sha256:
        raise ValueError("first-party core wheel digest mismatch")
    expected = SOURCE_INTEGRITY["source_snapshot"](source)
    actual_source = SOURCE_INTEGRITY["snapshot_sha256"](expected)
    if actual_source != expected_source_sha256:
        raise ValueError("canonical source digest mismatch")
    SOURCE_INTEGRITY["assert_secret_free"](expected)
    if not expected or not all(
        f"{name}/__init__.py" in expected for name in ("app", "pii_redactor")
    ):
        raise ValueError("canonical source packages are missing")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
            PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name
            for name in names
        ):
            raise ValueError("unsafe core wheel inventory")
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_paths) != 1:
            raise ValueError("invalid first-party core identity")
        metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
        metadata_prefix = metadata_paths[0].rsplit("/", 1)[0] + "/"
        if any(not name.startswith(("app/", "pii_redactor/", metadata_prefix)) for name in names):
            raise ValueError("unexpected executable wheel member")
        SOURCE_INTEGRITY["assert_secret_free"](
            {name: archive.read(name) for name in names if not name.endswith("/")}
        )
        version = (source / "VERSION").read_text(encoding="utf-8").strip()
        if metadata["Name"] != "thai-pii-redaction-core" or metadata["Version"] != version:
            raise ValueError("invalid first-party core identity")
        actual = {
            name
            for name in names
            if name.startswith(("app/", "pii_redactor/")) and not name.endswith("/")
        }
        if actual != set(expected) or any(archive.read(name) != expected[name] for name in actual):
            raise ValueError("wheel does not match canonical source")
        if any(name.endswith((".pth", ".data/scripts")) for name in names):
            raise ValueError("unexpected executable wheel member")
    return {
        "distribution": "thai-pii-redaction-core",
        "version": version,
        "wheel_sha256": expected_sha256,
        "source_tree_sha256": actual_source,
    }


def _lock_artifacts(locks: list[Path]) -> dict[tuple[str, str], set[str]]:
    allowed: dict[tuple[str, str], set[str]] = {}
    for lock in locks:
        content = lock.read_text(encoding="utf-8").replace("\\\n", " ")
        for raw in content.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^\s;]+)", line)
            hashes = set(re.findall(r"--hash=sha256:([0-9a-f]{64})", line))
            if not match or not hashes:
                raise ValueError("dependency lock is not exact and hash-qualified")
            name = re.sub(r"[-_.]+", "-", match[1]).lower()
            allowed.setdefault((name, match[2]), set()).update(hashes)
    return allowed


def verify_wheelhouse(wheelhouse: Path, locks: list[Path]) -> list[Path]:
    if wheelhouse.is_symlink():
        raise ValueError("dependency wheelhouse symlinks are not allowed")
    allowed = _lock_artifacts(locks)
    wheels = sorted(wheelhouse.iterdir())
    if not wheels or any(
        not path.is_file() or path.suffix != ".whl" or path.is_symlink() for path in wheels
    ):
        raise ValueError("dependency wheelhouse must contain only supplied wheels")
    for path in wheels:
        pieces = path.name.split("-")
        if len(pieces) < 5:
            raise ValueError("invalid dependency wheel filename")
        identity = (re.sub(r"[-_.]+", "-", pieces[0]).lower(), pieces[1])
        if sha256(path) not in allowed.get(identity, set()):
            raise ValueError("unqualified dependency digest")
    return wheels


def model_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    if root.is_symlink() or any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("model symlinks are not allowed")
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise ValueError("model symlinks are not allowed")
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0" + path.read_bytes())
    return digest.hexdigest()


def prepare_context(args: argparse.Namespace) -> dict:
    source = args.source.resolve()
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_revision) or revision != args.source_revision:
        raise ValueError("canonical source revision mismatch")
    identity = verify_core_wheel(
        args.core_wheel,
        source,
        expected_sha256=args.core_wheel_sha256,
        expected_source_sha256=args.source_tree_sha256,
    )
    locks = [
        HOSTED / "core" / name for name in ("requirements.lock", "requirements-aift-security.lock")
    ]
    dependencies = verify_wheelhouse(args.wheelhouse, locks)
    if not args.models.is_dir() or model_tree_sha256(args.models) != MODEL_SHA256:
        raise ValueError("certified thainer model digest mismatch")
    output = args.output.resolve()
    if output.is_relative_to(source):
        raise ValueError("prepared artifacts must stay outside the source checkout")
    if output.exists():
        raise ValueError("output context must not already exist")
    output.mkdir(parents=True)
    for name in PORT_FILES:
        shutil.copy2(HOSTED / "core" / name, output / name)
    for name in ("aift_hosted3", "licenses"):
        shutil.copytree(
            HOSTED / "core" / name,
            output / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    (output / "wheels").mkdir()
    shutil.copy2(args.core_wheel, output / "wheels" / args.core_wheel.name)
    (output / "wheelhouse").mkdir()
    for path in dependencies:
        shutil.copy2(path, output / "wheelhouse" / path.name)
    shutil.copytree(args.models, output / "models")
    requirement = f"./wheels/{args.core_wheel.name} --hash=sha256:{args.core_wheel_sha256}\n"
    (output / "core-wheel.lock").write_text(requirement, encoding="utf-8")
    identity.update(
        {
            "schema_version": 1,
            "source_revision": revision,
            "model_tree_sha256": MODEL_SHA256,
            "historical_port_manifest_active": False,
        }
    )
    identity["files"] = {
        path.relative_to(output).as_posix(): sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    (output / "CORE_BUILD_IDENTITY.json").write_text(
        json.dumps(identity, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--print-source-digest", action="store_true")
    parser.add_argument("--core-wheel", type=Path)
    parser.add_argument("--core-wheel-sha256")
    parser.add_argument("--source-revision")
    parser.add_argument("--source-tree-sha256")
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--models", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.print_source_digest:
        print(source_tree_sha256(args.source))
        return 0
    for name in (
        "core_wheel",
        "core_wheel_sha256",
        "source_revision",
        "source_tree_sha256",
        "wheelhouse",
        "models",
        "output",
    ):
        if getattr(args, name) is None:
            parser.error(f"--{name.replace('_', '-')} is required")
    try:
        identity = prepare_context(args)
    except (ValueError, OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        raise SystemExit(
            f"Hosted context preparation refused: {type(error).__name__}: {error}"
        ) from None
    print(
        json.dumps(
            {
                key: identity[key]
                for key in (
                    "distribution",
                    "version",
                    "wheel_sha256",
                    "source_tree_sha256",
                    "model_tree_sha256",
                )
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

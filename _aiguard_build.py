"""Generate private artifact inputs only in the wheel build directory."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

from setuptools.command.build_py import build_py


def write_resources(identity, root, target, manifest):
    resources = target / identity.RESOURCE
    expected = {identity.RESOURCE + "/" + name: value for name, value in manifest["inputs"].items()}
    manifest_name = identity.RESOURCE + "/manifest.json"
    allowed = {*expected, manifest_name}

    def inventory():
        result = {}
        identity._path(target, identity.RESOURCE)
        for candidate in resources.rglob("*"):
            name = candidate.relative_to(target).as_posix()
            path = identity._path(target, name)
            if path.is_dir():
                if not any(item.startswith(name + "/") for item in allowed):
                    raise ValueError("artifact_build_resource_residue")
            elif path.is_file() and name in allowed:
                result[name] = identity._hash(path)
            else:
                raise ValueError("artifact_build_resource_residue")
        return result

    if resources.exists() or resources.is_symlink():
        inventory()
    else:
        resources.mkdir(parents=True)
        identity._path(target, identity.RESOURCE)
    for name in manifest["inputs"]:
        destination = resources / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            identity._path(root, name),
            identity._path(target, identity.RESOURCE + "/" + name)
            if destination.exists()
            else destination,
        )
    manifest_path = resources / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    expected[manifest_name] = identity._hash(manifest_path)
    if inventory() != expected:
        raise ValueError("artifact_build_resources_mismatch")


class ArtifactBuildPy(build_py):
    def run(self):
        root = Path(__file__).absolute().parent
        spec = importlib.util.spec_from_file_location(
            "_artifact_builder", root / "pii_redactor/artifact_identity.py"
        )
        identity = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(identity)
        manifest = identity.source_manifest(root)
        super().run()
        target = Path(self.build_lib).absolute()
        if identity._inventory(target, identity.NAMESPACES) != manifest["runtime"]:
            raise ValueError("artifact_build_payload_mismatch")
        write_resources(identity, root, target, manifest)

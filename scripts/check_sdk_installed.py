"""Check actual SDK wheel imports, namespace, bytes and offline public roundtrip."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile
from pathlib import Path, PurePosixPath


def check(target: Path, wheel: Path):
    target = target.resolve(strict=True)
    if (
        os.environ.get("AMPHRANG_NER_ENGINE") != "thainer"
        or os.environ.get("PYTHAINLP_OFFLINE") != "1"
    ):
        raise ValueError("offline_profile_required")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for name in names:
            path = PurePosixPath(name)
            parts = path.parts
            if len(parts) > 2 and parts[0].endswith(".data") and parts[1] in {"purelib", "platlib"}:
                parts = parts[2:]
            if (
                not parts
                or path.is_absolute()
                or ".." in parts
                or parts[0] in {"app", "app.py", "pii_redactor", "pii_redactor.py"}
                or path.name.startswith(".env")
                or path.suffix in {".key", ".env"}
            ):
                raise ValueError("sdk_namespace_or_private_resource_invalid")
        sources = [name for name in names if name.startswith("amphrang/") and name.endswith(".py")]
        if "amphrang/__init__.py" not in sources:
            raise ValueError("sdk_facade_missing")
        for name in sources:
            installed = (target / name).resolve(strict=True)
            if (
                not installed.is_relative_to(target)
                or hashlib.sha256(installed.read_bytes()).digest()
                != hashlib.sha256(archive.read(name)).digest()
            ):
                raise ValueError("installed_sdk_source_mismatch")
    sys.path.insert(0, str(target))
    import amphrang

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
        if name == "amphrang" or name.startswith("amphrang."):
            source = getattr(module, "__file__", None)
            if source and not Path(source).resolve().is_relative_to(target):
                raise ValueError("sdk_source_tree_import")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    try:
        check(args.target, args.wheel)
    except Exception:
        print(
            "Installed SDK qualification failed; error details and values suppressed.",
            file=sys.stderr,
        )
        return 1
    print("Installed SDK wheel bytes, private namespace and offline synthetic roundtrip passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

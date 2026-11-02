#!/usr/bin/env python3
"""Verify the installed canonical core against its supplied build identity."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path


def main() -> int:
    identity = json.loads(Path("/app/CORE_BUILD_IDENTITY.json").read_text(encoding="utf-8"))
    distribution = importlib.metadata.distribution("thai-pii-redaction-core")
    assert distribution.metadata["Name"] == identity["distribution"] == "thai-pii-redaction-core"
    assert distribution.version == identity["version"]
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in distribution.files or ()
        if str(path).startswith(("app/", "pii_redactor/")) and path.suffix != ".pyc"
    )
    assert files, "canonical installed source inventory is empty"
    for path in files:
        digest.update(
            str(path).encode("utf-8") + b"\0" + distribution.locate_file(path).read_bytes()
        )
    assert digest.hexdigest() == identity["source_tree_sha256"], (
        "canonical installed source digest mismatch"
    )
    for namespace in ("app", "pii_redactor"):
        spec = importlib.util.find_spec(namespace)
        assert spec and spec.origin
        assert (
            Path(spec.origin).resolve()
            == distribution.locate_file(f"{namespace}/__init__.py").resolve()
        ), "canonical import origin mismatch"
        assert not Path(spec.origin).is_relative_to("/app"), (
            "runtime must use the installed first-party wheel"
        )
    print("Canonical first-party core identity and installed source verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Killable one-document parser worker launched by the socket supervisor."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from parser_engine import DocumentError, parse_pdf
from protocol import MAX_RESPONSE_BYTES

_JOB_NAME = re.compile(r"^(?:job|result)-[0-9a-f]{32}\.(?:pdf|json)$")
_SCENARIO_NAME = "hr-resume-pdf-structured-v1.pdf"


def _allowed_input(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    return (
        resolved.parent == Path("/work")
        and _JOB_NAME.fullmatch(resolved.name) is not None
        and resolved.suffix == ".pdf"
    ) or (
        resolved.parent == Path("/app/scenarios")
        and resolved.name == _SCENARIO_NAME
    )


def _allowed_output(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    return (
        resolved.parent == Path("/work")
        and _JOB_NAME.fullmatch(resolved.name) is not None
        and resolved.suffix == ".json"
    )


def main() -> int:
    if len(sys.argv) != 3:
        return 64
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    if not _allowed_input(source) or not _allowed_output(output):
        return 64
    try:
        value = {"ok": True, "result": parse_pdf(source)}
    except DocumentError as error:
        value = {"ok": False, "code": error.code}
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if not payload or len(payload) > MAX_RESPONSE_BYTES:
        return 65
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


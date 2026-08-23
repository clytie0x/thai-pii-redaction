#!/usr/bin/env python3
"""Release gate: VERSION, CHANGELOG.md, and the git tag must agree.

Pure stdlib so CI can run it before any ``pip install``.

    python scripts/check_release.py                       # CI on every push
    python scripts/check_release.py --expect-tag v0.1.0   # release.yml on a tag
    python scripts/check_release.py --expect-tag v0.1.0 --notes > notes.md

Checks: VERSION is semver; CHANGELOG.md has a ``## [<VERSION>]`` section; with
``--expect-tag`` the tag is exactly ``v<VERSION>`` and the section is dated
(``## [x.y.z] - YYYY-MM-DD``), because a tag builds an immutable artifact and
"unreleased" must not be what ships. ``--notes`` prints that section as the
GitHub Release body. Exit 1 with every problem listed otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def read_version(root: Path) -> str:
    return (root / "VERSION").read_text(encoding="utf-8").strip()


def _section(root: Path, version: str) -> tuple[str | None, str] | None:
    """(date or None, body) of the CHANGELOG section for ``version``."""
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(
        rf"^## \[{re.escape(version)}\](?:\s*[-—]\s*(?P<date>\S+))?\s*$\n(?P<body>.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        return None
    date = match.group("date")
    if date is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        date = None
    return date, match.group("body").strip()


def check(root: Path, *, expect_tag: str | None = None, require_dated: bool = False) -> list[str]:
    problems: list[str] = []
    try:
        version = read_version(root)
    except OSError as error:
        return [f"VERSION: {error}"]
    if not _SEMVER.match(version):
        problems.append(f"VERSION: {version!r} is not semver (MAJOR.MINOR.PATCH)")
    if expect_tag is not None and expect_tag != f"v{version}":
        problems.append(
            f"tag {expect_tag!r} does not match VERSION {version!r} (expected v{version})"
        )
    try:
        section = _section(root, version)
    except OSError as error:
        return [*problems, f"CHANGELOG.md: {error}"]
    if section is None:
        problems.append(f"CHANGELOG.md: no '## [{version}]' section")
        return problems
    date, body = section
    if not body:
        problems.append(f"CHANGELOG.md: section for {version} is empty")
    if (require_dated or expect_tag is not None) and date is None:
        problems.append(
            f"CHANGELOG.md: section for {version} must be dated '## [{version}] - YYYY-MM-DD' before tagging"
        )
    return problems


def release_notes(root: Path, version: str) -> str:
    section = _section(root, version)
    if section is None:
        raise ValueError(f"no CHANGELOG section for {version}")
    date, body = section
    heading = f"## amphrang {version}" + (f" ({date})" if date else "")
    return f"{heading}\n\n{body}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--expect-tag", default=None, help="git tag being released (v<VERSION>)")
    parser.add_argument(
        "--notes", action="store_true", help="print the CHANGELOG section on success"
    )
    args = parser.parse_args(argv)
    problems = check(
        args.root, expect_tag=args.expect_tag, require_dated=args.expect_tag is not None
    )
    if problems:
        for problem in problems:
            print(f"release gate: {problem}", file=sys.stderr)
        return 1
    if args.notes:
        print(release_notes(args.root, read_version(args.root)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

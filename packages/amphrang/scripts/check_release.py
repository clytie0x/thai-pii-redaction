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
import ast
import re
import sys
from pathlib import Path

_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")

_SURFACE_MANIFEST = Path("docs") / "api-surface.txt"
_FACADE = Path("amphrang") / "__init__.py"

_COVERAGE_PROFILE = Path("docs") / "pdpa-coverage.md"
_TOKEN_GENERATOR = Path("pii_redactor") / "anonymizer" / "token_generator.py"
_REPORT_CATEGORIES = Path("pii_redactor") / "pdpa_categories.py"
_PROFILE_TYPE_NAME = re.compile(r"`([A-Z][A-Z0-9_]*)`")


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


def _facade_all(root: Path) -> set[str] | str:
    """Names in the facade's ``__all__`` (parsed, never imported), or an error."""
    path = root / _FACADE
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as error:
        return f"{_FACADE}: {error}"
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            try:
                names = ast.literal_eval(node.value)
            except ValueError:
                return f"{_FACADE}: __all__ is not a literal list"
            return set(names)
    return f"{_FACADE}: no __all__ found"


def check_surface(root: Path) -> list[str]:
    """The facade's ``__all__`` must equal docs/api-surface.txt exactly.

    A surface change is only legitimate as a deliberate two-file diff (facade
    plus manifest, with a CHANGELOG entry per the stability policy); this
    catches the accidental one-file kind.
    """
    manifest_path = root / _SURFACE_MANIFEST
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return [f"{_SURFACE_MANIFEST}: {error}"]
    declared = {line.strip() for line in lines if line.strip() and not line.startswith("#")}
    actual = _facade_all(root)
    if isinstance(actual, str):
        return [actual]
    problems: list[str] = []
    added = sorted(actual - declared)
    removed = sorted(declared - actual)
    if added:
        problems.append(
            f"public surface grew: {', '.join(added)} in __all__ but not in "
            f"{_SURFACE_MANIFEST} — if intentional, update the manifest in the same "
            "commit and record the addition in CHANGELOG.md"
        )
    if removed:
        problems.append(
            f"public surface shrank: {', '.join(removed)} in {_SURFACE_MANIFEST} but "
            "not in __all__ — removing a public name is a breaking change; update the "
            "manifest deliberately and record it in CHANGELOG.md"
        )
    return problems


def _literal_table(path: Path, table_name: str) -> set[str] | str:
    """Read canonical type names without importing model or provider code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as error:
        return f"{path.name}: {error}"
    for node in tree.body:
        target = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == table_name and node.value is not None:
            try:
                mapping = ast.literal_eval(node.value)
            except ValueError:
                return f"{path.name}: {table_name} is not literal"
            return set(mapping)
    return f"{path.name}: no {table_name} found"


def check_profile(root: Path, *, core_root: Path | None = None) -> list[str]:
    """Check documented type names against canonical identifiers and report categories.

    Sensitive reporting categories are not masking types. This gate checks names;
    it does not qualify archived measurements for the current core or policy.
    """
    profile_path = root / _COVERAGE_PROFILE
    try:
        lines = profile_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return [f"{_COVERAGE_PROFILE}: {error}"]
    documented: set[str] = set()
    for line in lines:
        if line.startswith("|"):
            documented.update(_PROFILE_TYPE_NAME.findall(line))
    core_root = core_root if core_root is not None else root.resolve().parents[1]
    identifiers = _literal_table(core_root / _TOKEN_GENERATOR, "TOKEN_LABEL")
    categories = _literal_table(core_root / _REPORT_CATEGORIES, "SECTION26_CATEGORIES")
    errors = [item for item in (identifiers, categories) if isinstance(item, str)]
    if errors:
        return errors
    actual = identifiers | categories
    problems: list[str] = []
    missing = sorted(actual - documented)
    extra = sorted(documented - actual)
    if missing:
        problems.append(
            f"{_COVERAGE_PROFILE}: canonical identifier/report type(s) not documented: "
            f"{', '.join(missing)}"
        )
    if extra:
        problems.append(
            f"{_COVERAGE_PROFILE}: documented type(s) outside canonical identifier/report tables: {', '.join(extra)}"
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
        "--core-root", type=Path, help="matching canonical source tree (default: monorepo root)"
    )
    parser.add_argument(
        "--notes", action="store_true", help="print the CHANGELOG section on success"
    )
    args = parser.parse_args(argv)
    problems = check(
        args.root, expect_tag=args.expect_tag, require_dated=args.expect_tag is not None
    )
    problems += check_surface(args.root)
    problems += check_profile(args.root, core_root=args.core_root)
    if problems:
        for problem in problems:
            print(f"release gate: {problem}", file=sys.stderr)
        return 1
    if args.notes:
        print(release_notes(args.root, read_version(args.root)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

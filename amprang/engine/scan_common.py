"""Shared file-discovery and value-canonicalization helpers for the corpus-scanning
storefronts (`breach.py`, `dsar.py`). See docs/decisions/2026-08-01-dsar-helper.md.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

_DISCOVER_SUFFIXES = (".txt", ".pdf")

_NAME_TYPE = "NAME"

_NAME_TITLE_RE = re.compile(r"^(?:นางสาว|นาย|นาง|น\.ส\.|ด\.ช\.|ด\.ญ\.|เด็กชาย|เด็กหญิง|คุณ)\s*")


def path_spellings(path: Path) -> set[str]:
    """Every spelling of `path` an exception message might embed: as given, resolved, both slash
    directions, and the repr-escaped (doubled-backslash) forms `OSError.__str__` produces.
    """
    spellings = {str(path)}
    try:
        spellings.add(str(path.resolve()))
    except OSError:
        pass
    for spelling in list(spellings):
        spellings.add(spelling.replace("\\", "/"))
        spellings.add(spelling.replace("/", "\\"))
    for spelling in list(spellings):
        spellings.add(spelling.replace("\\", "\\\\"))
        spellings.add(repr(spelling)[1:-1])
    return spellings


def short_reason(exc: Exception, path: Path) -> str:
    """`{ExceptionClassName} {message}` with every spelling of the file's path folded to its
    basename (stdlib messages embed the full path, which may disclose a directory name).
    Space, not colon, between class and message: the string reaches Thai-facing output.
    """
    message = str(exc)
    basename = path.name
    for spelling in path_spellings(path):
        if spelling and spelling != basename:
            message = message.replace(spelling, basename)
    return f"{type(exc).__name__} {message}"


def discover_files(paths: Sequence[str | Path], *, recursive: bool) -> tuple[list[Path], list[str]]:
    """Resolve `paths` to a deterministic, de-duplicated file list plus the basenames a directory
    scan skipped (non *.txt/*.pdf), so a report never silently claims full folder coverage.
    A non-directory path is taken as-is so a bad path becomes a failed-file row, not a skip.
    """
    found: list[Path] = []
    skipped: list[str] = []
    seen: set[Path] = set()
    seen_skipped: set[Path] = set()

    def _resolved(candidate: Path) -> Path:
        try:
            return candidate.resolve()
        except OSError:
            return candidate

    def _add(candidate: Path) -> None:
        key = _resolved(candidate)
        if key not in seen:
            seen.add(key)
            found.append(candidate)

    def _add_skipped(candidate: Path) -> None:
        key = _resolved(candidate)
        if key not in seen_skipped:
            seen_skipped.add(key)
            skipped.append(candidate.name)

    for raw in paths:
        candidate_path = Path(raw)
        if candidate_path.is_dir():
            pattern = "**/*" if recursive else "*"
            for child in sorted(candidate_path.glob(pattern)):
                if not child.is_file():
                    continue
                if child.suffix.lower() in _DISCOVER_SUFFIXES:
                    _add(child)
                else:
                    _add_skipped(child)
        else:
            _add(candidate_path)

    return found, skipped


def canonical_value(data_type: str, value: str) -> str:
    """Fold formatting differences that would inflate a distinct count. Strong types get bespoke
    normalization; NAME strips a leading title but stays a WEAK identifier (never feeds
    subjects_min/max); everything else gets a whitespace/case fold.
    """
    if data_type == "THAI_ID":
        return re.sub(r"\D", "", value)
    if data_type == "PASSPORT":
        return re.sub(r"[\s-]", "", value).upper()
    if data_type == "PHONE":
        digits = re.sub(r"\D", "", value)
        # +66 drops the domestic leading 0 (66 + 9 mobile / 66 + 8 landline digits); fold back so
        # "+66 81 234 5678" and "081-234-5678" count once.
        if digits.startswith("66") and len(digits) in (10, 11):
            digits = "0" + digits[2:]
        return digits
    if data_type == "EMAIL":
        return value.strip().casefold()
    if data_type == _NAME_TYPE:
        stripped = _NAME_TITLE_RE.sub("", value.strip())
        return re.sub(r"\s+", " ", stripped).strip().casefold()
    return re.sub(r"\s+", " ", value.strip()).casefold()

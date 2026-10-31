"""Shared scan-only source mapping for input and release checks."""

import re
import unicodedata

from pii_redactor.detectors.fp_detector import _iban_check, detect_fp
from pii_redactor.models import Entity

_SPACED_IBAN_START_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2}\d{2})(?= )")


_SPACED_IBAN_GROUP_RE = re.compile(r"([A-Z0-9]{1,4})(?![A-Z0-9])")


_MAX_IBAN_LENGTH = 34


_MAX_IBAN_GROUPS = 9
OBFUSCATED_STRUCTURED_TYPES = frozenset(
    {
        "ADDRESS",
        "BANK_ACCOUNT",
        "CREDIT_CARD",
        "DATE_OF_BIRTH",
        "EMAIL",
        "IBAN",
        "MEDICAL_ID",
        "PASSPORT",
        "PHONE",
        "POSTAL_CODE",
        "STUDENT_ID",
        "THAI_ID",
        "VEHICLE_PLATE",
    }
)


def canonical_character(character: str) -> str:
    code = ord(character)
    if 0xFF01 <= code <= 0xFF5E:
        return chr(code - 0xFEE0)
    if "๐" <= character <= "๙":
        return str(code - ord("๐"))
    return character


def _security_scan_view(text: str) -> tuple[str, list[int]]:
    """Build a scan-only view without changing caller-visible text or spans."""
    visible: list[str] = []
    source_offsets: list[int] = []
    for offset, character in enumerate(text):
        if unicodedata.category(character) == "Cf":
            continue
        visible.append(canonical_character(character))
        source_offsets.append(offset)

    compact: list[str] = []
    compact_offsets: list[int] = []
    index = 0
    while index < len(visible):
        if not visible[index].isspace():
            compact.append(visible[index])
            compact_offsets.append(source_offsets[index])
            index += 1
            continue
        end = index + 1
        while end < len(visible) and visible[end].isspace():
            end += 1
        if end - index == 1:
            compact.append(visible[index])
            compact_offsets.append(source_offsets[index])
        index = end
    return "".join(compact), compact_offsets


def _map_security_view_entities(
    text: str,
    security_view: str,
    source_offsets: list[int],
    *,
    allowed_types: frozenset[str],
) -> list[Entity]:
    mapped: list[Entity] = []
    for entity in detect_fp(security_view):
        if entity.data_type not in allowed_types:
            continue
        start, end = entity.span
        if start < 0 or end <= start or end > len(source_offsets):
            continue
        source_start = source_offsets[start]
        source_end = source_offsets[end - 1] + 1
        mapped.append(
            Entity(
                entity_id=entity.entity_id,
                redact_type=entity.redact_type,
                data_type=entity.data_type,
                span=(source_start, source_end),
                score=entity.score,
                original_text=text[source_start:source_end],
            )
        )
    return mapped


def _single_spaced_iban_views(text: str, *, group_pattern=None) -> list[tuple[str, list[int]]]:
    """Return checksum-ready views for standard four-character IBAN groups."""
    views: list[tuple[str, list[int]]] = []
    for start_match in _SPACED_IBAN_START_RE.finditer(text):
        groups = [
            (
                start_match.group(1),
                start_match.start(1),
                start_match.end(1),
            )
        ]
        cursor = start_match.end(1)
        compact_length = len(start_match.group(1))
        while len(groups) < _MAX_IBAN_GROUPS and cursor < len(text) and text[cursor] == " ":
            group_match = (group_pattern or _SPACED_IBAN_GROUP_RE).match(text, cursor + 1)
            if group_match is None:
                break
            group = group_match.group(1)
            if compact_length + len(group) > _MAX_IBAN_LENGTH:
                break
            groups.append(
                (
                    group,
                    group_match.start(1),
                    group_match.end(1),
                )
            )
            compact_length += len(group)
            cursor = group_match.end(1)
            if len(group) < 4:
                break

        for group_count in range(len(groups), 1, -1):
            selected = groups[:group_count]
            if any(len(group) != 4 for group, _start, _end in selected[1:-1]):
                continue
            compact = "".join(group for group, _start, _end in selected)
            if not 15 <= len(compact) <= _MAX_IBAN_LENGTH:
                continue
            offsets = [offset for _group, start, end in selected for offset in range(start, end)]
            if _iban_check(compact):
                views.append((compact, offsets))
                break
    return views


def original_guard_entities(text: str) -> list[Entity]:
    """Keep original structured units before replacements can break signatures."""
    view, offsets = _security_scan_view(text)
    result = _map_security_view_entities(
        text, view, offsets, allowed_types=OBFUSCATED_STRUCTURED_TYPES
    )
    for compact, positions in _single_spaced_iban_views(view):
        result.extend(
            _map_security_view_entities(
                text, compact, [offsets[i] for i in positions], allowed_types=frozenset({"IBAN"})
            )
        )
    for compact, positions in _single_spaced_iban_views(text):
        result.extend(
            _map_security_view_entities(text, compact, positions, allowed_types=frozenset({"IBAN"}))
        )
    return result

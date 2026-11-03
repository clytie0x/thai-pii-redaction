"""Bounded input recovery projected onto unchanged original source intervals."""

import re
import unicodedata

from pii_redactor.detectors import scan_views
from pii_redactor.detectors.fp_detector import _JURISTIC_CUE_RE
from pii_redactor.models import Entity

_TYPES = frozenset(
    {
        "THAI_ID",
        "JURISTIC_ID",
        "PHONE",
        "EMAIL",
        "CREDIT_CARD",
        "BANK_ACCOUNT",
        "STUDENT_ID",
        "PASSPORT",
        "VEHICLE_PLATE",
        "IBAN",
        "MEDICAL_ID",
    }
)
_CUES = {
    "PHONE": re.compile(r"โทร|เบอร์|มือถือ|phone", re.IGNORECASE),
    "THAI_ID": re.compile(r"บัตรประชาชน|เลขประจำตัวประชาชน|ปชช"),
    "JURISTIC_ID": _JURISTIC_CUE_RE,
    "CREDIT_CARD": re.compile(r"บัตรเครดิต|บัตรเดบิต|credit\s*card", re.IGNORECASE),
    "BANK_ACCOUNT": re.compile(r"บัญชี|account", re.IGNORECASE),
    "STUDENT_ID": re.compile(r"รหัสนักศึกษา|รหัสนักเรียน|รหัสนิสิต"),
}
_REPEATED_DIGIT_GAP = re.compile(r"(?<=\d) {2,}(?=\d)")
_HARD_BOUNDARIES = "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029\t"


def source_view(text: str, *, compact: bool = False) -> tuple[str, list[int]]:
    """Only format controls, Thai digits and ASCII-width forms change here.

    No global compatibility normalization, Unicode expansion, or line joining.
    """
    chars, offsets = [], []
    for index, char in enumerate(text):
        if unicodedata.category(char) == "Cf":
            continue
        chars.append(scan_views.canonical_character(char))
        offsets.append(index)
    view = "".join(chars)
    if compact:
        remove = {i for match in _REPEATED_DIGIT_GAP.finditer(view) for i in range(*match.span())}
        return "".join(c for i, c in enumerate(chars) if i not in remove), [
            offset for i, offset in enumerate(offsets) if i not in remove
        ]
    return view, offsets


def recover_structured(text: str) -> list[Entity]:
    repeated = _REPEATED_DIGIT_GAP.search(text) is not None
    changed = any(
        unicodedata.category(c) == "Cf" or 0xFF01 <= ord(c) <= 0xFF5E or "๐" <= c <= "๙"
        for c in text
    )
    has_iban = scan_views._SPACED_IBAN_START_RE.search(text) is not None
    if not (repeated or changed or has_iban):
        return []
    view, offsets = source_view(text)
    candidates = []
    if view != text:
        candidates.extend(
            scan_views._map_security_view_entities(text, view, offsets, allowed_types=_TYPES)
        )
    if repeated:
        compact_view, compact_offsets = source_view(text, compact=True)
        for entity in scan_views._map_security_view_entities(
            text, compact_view, compact_offsets, allowed_types=_TYPES
        ):
            start = entity.span[0]
            line_start = max(text.rfind(c, 0, start) for c in _HARD_BOUNDARIES) + 1
            context = text[max(line_start, start - 40) : start]
            cue = _CUES.get(entity.data_type)
            if cue and cue.search(context):
                candidates.append(entity)
    for compact_view, compact_offsets in scan_views._single_spaced_iban_views(view):
        candidates.extend(
            scan_views._map_security_view_entities(
                text,
                compact_view,
                [offsets[i] for i in compact_offsets],
                allowed_types=frozenset({"IBAN"}),
            )
        )
    seen = set()
    result = []
    for entity in candidates:
        if any(c in entity.original_text for c in _HARD_BOUNDARIES):
            continue
        key = (entity.span, entity.data_type)
        if key not in seen:
            result.append(entity)
            seen.add(key)
    return result


def admit_recovery(raw: list[Entity], recovered: list[Entity], *, required=()) -> list[Entity]:
    """Additional evidence may never uncover any raw protected character."""
    kept = list(raw)
    for candidate in sorted(recovered, key=lambda e: (e.span[0], -(e.span[1] - e.span[0]))):
        start, end = candidate.span
        guard_overlaps = [e for e in required if e.span[0] < end and start < e.span[1]]
        if any(e.span[0] < start or e.span[1] > end for e in guard_overlaps):
            continue
        overlaps = [e for e in kept if e.span[0] < end and start < e.span[1]]
        if any(e.span[0] < start or e.span[1] > end for e in overlaps):
            continue
        if any(e.span == candidate.span and e.score >= candidate.score for e in overlaps):
            continue
        kept = [e for e in kept if e not in overlaps]
        kept.append(candidate)
    return sorted(kept, key=lambda e: e.span)

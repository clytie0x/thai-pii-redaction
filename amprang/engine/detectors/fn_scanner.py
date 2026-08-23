"""False-negative (FN) second pass scanner using lightweight regex patterns."""

from __future__ import annotations

import re
import uuid

from amprang.engine.detectors.fp_detector import _NON_STUDENT_NUM_CUE_RE, _STUDENT_INTRO_RE
from amprang.engine.models import Entity

# ---------------------------------------------------------------------------
# Patterns for common false-negative scenarios
# ---------------------------------------------------------------------------

_FN_PATTERNS: list[tuple[re.Pattern[str], str, str, float]] = [
    # redact_type must be "FP" (as in fp_detector) so the anonymizer routes these through
    # generate_fp() instead of the literal "[REDACTED_x]" fallback.
    # Digit-boundary lookarounds, not \b: \b never fires between Thai script and a digit.
    (re.compile(r"(?<!\d)(\d{13})(?!\d)"), "THAI_ID", "FP", 0.6),
    (re.compile(r"([^\s@]+@[^\s@]+\.[^\s@]{2,})"), "EMAIL", "FP", 0.7),
    # Labeled DATE, not DATE_OF_BIRTH: this fallback has no cue context to gate on.
    (
        re.compile(r"(?<!\d)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})(?!\d)"),
        "DATE",
        "FP",
        0.6,
    ),
]


# ---------------------------------------------------------------------------
# Corrupted-duplicate structured id scan.
#
# The OCR retry merge can leave a corrupted copy of a structured value beside the valid
# read ("13122+1506581" next to "1312271505581"); it matches neither regex nor checksum, so
# 12 of 13 digits of a national id would leave unmasked. A 12-15 char run that is digits
# except for 1-2 INNER junk chars (+ $ #) is tagged ID_NUMBER. Comma/period are excluded on
# purpose: "1,234,567.89" is the likeliest false-positive source.
#
# Cue gate: a summed amount has the same shape ("รวมเป็นเงิน 600000+120000"), so
# nearest-cue-wins: an amount cue nearer than an id cue suppresses the tag. The amount side
# is imported from fp_detector so the two rules cannot drift. Default is KEEP (recall >
# precision). Windows are clipped at the line.
#
# The id side cannot just BE _STUDENT_INTRO_RE: it knows nothing about national-id-card
# phrasing, so "ค่าธรรมเนียม 500 บาท เลขบัตร 13122+1506581" found no id cue and บาท suppressed
# a real corrupted id. Longest alternative first.
_AMOUNT_CUE_RE = re.compile(
    _NON_STUDENT_NUM_CUE_RE.pattern + r"|รวม|บาท|total",
    re.IGNORECASE,
)
_CORRUPTED_ID_CUE_RE = re.compile(
    _STUDENT_INTRO_RE.pattern
    + r"|เลขที่บัตรประชาชน|เลขบัตรประชาชน|เลขประจำตัวประชาชน|บัตรประชาชน"
    + r"|เลขที่บัตร|เลขบัตร|เลขประชาชน|national id",
    re.IGNORECASE,
)
_CORRUPTED_ID_CUE_WINDOW = 40
_CORRUPTED_ID_JUNK_CHARS = "+$#"
_CORRUPTED_ID_CANDIDATE_RE = re.compile(r"(?<![0-9+$#])[0-9+$#]+(?![0-9+$#])")


def _nearest_cue_distance(pattern: re.Pattern[str], text: str, start: int, end: int) -> int | None:
    """Chars to the nearest `pattern` match either side, same line, or None."""
    before = text[max(0, start - _CORRUPTED_ID_CUE_WINDOW) : start]
    before = before.rsplit("\n", 1)[-1]
    after = text[end : end + _CORRUPTED_ID_CUE_WINDOW]
    after = after.split("\n", 1)[0]

    best: int | None = None
    for m in pattern.finditer(before):
        distance = len(before) - m.end()
        if best is None or distance < best:
            best = distance
    first_after = pattern.search(after)
    if first_after is not None and (best is None or first_after.start() < best):
        best = first_after.start()
    return best


def _competing_amount_cue_wins(text: str, start: int, end: int) -> bool:
    amount = _nearest_cue_distance(_AMOUNT_CUE_RE, text, start, end)
    if amount is None:
        return False
    id_cue = _nearest_cue_distance(_CORRUPTED_ID_CUE_RE, text, start, end)
    # Tie goes to the id cue -- recall > precision.
    return id_cue is None or amount < id_cue


def _is_corrupted_id_candidate(candidate: str) -> bool:
    if not (12 <= len(candidate) <= 15):
        return False
    if not candidate[0].isdigit() or not candidate[-1].isdigit():
        return False
    junk_count = sum(1 for ch in candidate if ch in _CORRUPTED_ID_JUNK_CHARS)
    non_digit_count = sum(1 for ch in candidate if not ch.isdigit())
    if junk_count != non_digit_count:
        # Defensive: candidate class is [0-9+$#], so this cannot happen.
        return False
    return junk_count in (1, 2)


def scan_fn(text: str, existing_entities: list[Entity]) -> list[Entity]:
    """Second-pass regex scan; returns only NEW entities not overlapping existing ones."""
    existing_spans = {(e.span[0], e.span[1]) for e in existing_entities}

    new_entities: list[Entity] = []
    for pattern, data_type, redact_type, score in _FN_PATTERNS:
        for m in pattern.finditer(text):
            start, end = m.start(1), m.end(1)
            if end - start < 2:
                continue
            overlaps = any(not (end <= es[0] or start >= es[1]) for es in existing_spans)
            if not overlaps:
                new_entities.append(
                    Entity(
                        entity_id=str(uuid.uuid4()),
                        redact_type=redact_type,
                        data_type=data_type,
                        span=(start, end),
                        score=score,
                        original_text=text[start:end],
                    )
                )
                existing_spans.add((start, end))

    for m in _CORRUPTED_ID_CANDIDATE_RE.finditer(text):
        start, end = m.start(), m.end()
        candidate = text[start:end]
        if not _is_corrupted_id_candidate(candidate):
            continue
        if _competing_amount_cue_wins(text, start, end):
            continue
        overlaps = any(not (end <= es[0] or start >= es[1]) for es in existing_spans)
        if overlaps:
            continue
        new_entities.append(
            Entity(
                entity_id=str(uuid.uuid4()),
                redact_type="FP",
                data_type="ID_NUMBER",
                span=(start, end),
                score=0.6,
                original_text=candidate,
            )
        )
        existing_spans.add((start, end))

    return sorted(new_entities, key=lambda e: e.span[0])

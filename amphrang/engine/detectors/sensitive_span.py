"""Person-linked ม.26 (PDPA section 26) sensitive-span detection.

Frozen design: `docs/decisions/2026-08-27-section26-span-masking.md`. The document-level
flag scan in `report.py` says a document *contains* sensitive content; this module says
*which characters* are the sensitive claim, and only when the segment carrying them is
linked to a natural person. An impersonal ประกาศ about "แนวทางการรักษาผู้ป่วย" keeps its
text; a patient record does not.

Two rules do the work. A hit and its person anchor must share a SEGMENT (newline, a
period/semicolon plus whitespace, or two or more spaces — a single space is an
intra-sentence phrase break in Thai and a name sits one space from its predicate). The
anchor is TWO-TIER: a first-person pronoun or a title+given-name is never vetoed; a bare role
word is vetoed when it belongs to an organization name or sits in an impersonal institutional
register; a NAME/SURNAME span anchors like tier 1 except that the impersonal register vetoes
it too, because that route's evidence is a CRF guess and legal boilerplate is where the CRF
invents one.

The span is forward-only from the keyword: the anchor sits *before* the keyword in nearly
every Thai construction ("ผู้ป่วยรายนี้มีประวัติการรักษา…"), so a backward-expanding span
eats its own anchor.
"""

from __future__ import annotations

import re
import uuid

from amphrang.engine.models import Entity

SENSITIVE_DATA_TYPES: tuple[str, ...] = (
    "RACE_ETHNICITY",
    "POLITICAL_OPINION",
    "RELIGION",
    "HEALTH",
    "SEXUAL_BEHAVIOR",
    "CRIMINAL_RECORD",
    "DISABILITY",
    "LABOR_UNION",
    "GENETIC",
    "BIOMETRIC",
)
SENSITIVE_DATA_TYPE_SET: frozenset[str] = frozenset(SENSITIVE_DATA_TYPES)
MAX_SPAN_CHARS: int = 48

# This table is the span detector's own. `report.py::_SECTION26_KEYWORDS` is the
# document-level flag scan that `analyze()` and the HTTP `section26_categories` field are
# pinned to and stays byte-identical. Two deliberate departures from it: RACE_ETHNICITY
# drops สัญชาติ (nationality is a Level-B quasi-identifier, not a ม.26 category) and gains
# ชาติพันธุ์|ชนเผ่า; HEALTH carries the category-error veto below.
# Flags: re.UNICODE and nothing else. No IGNORECASE (DNA is upper case only, as the flag
# table has always had it); no MULTILINE/DOTALL (no pattern uses ^, $ or .).
_SPAN_PATTERNS = {
    "RACE_ETHNICITY": r"(?:เชื้อชาติ|เผ่าพันธุ์|ชาติพันธุ์|ชนเผ่า)",
    "POLITICAL_OPINION": r"(?:ความคิดเห็นทางการเมือง|พรรคการเมือง|อุดมการณ์)",
    "RELIGION": r"(?:ศาสนา|ความเชื่อ|พุทธ|คริสต์|อิสลาม|ฮินดู)",
    "HEALTH": r"(?:โรค|การรักษา|ผล(?:การ)?ตรวจ|สุขภาพ|ประวัติ(?:การ)?รักษา)",
    "SEXUAL_BEHAVIOR": r"(?:เพศ(?:สัมพันธ์|วิถี)|รสนิยมทางเพศ)",
    "CRIMINAL_RECORD": r"(?:คดี|ต้องโทษ|จำคุก|ประวัติอาชญากรรม|ถูกฟ้อง)",
    "DISABILITY": r"(?:ทุพพลภาพ|ความพิการ|คนพิการ)",
    "LABOR_UNION": r"(?:สหภาพแรงงาน|สมาคมลูกจ้าง)",
    "GENETIC": r"(?:พันธุกรรม|ดีเอ็นเอ|DNA|จีโนม|โครโมโซม|ยีน(?!ส์))",
    "BIOMETRIC": r"(?:ข้อมูลชีวภาพ|ชีวมิติ|ไบโอเมตริก|ลายนิ้วมือ|ม่านตา"
    r"|สแกน(?:ใบหน้า|นิ้ว)|จดจำใบหน้า)",
}
_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (data_type, re.compile(pattern, re.UNICODE)) for data_type, pattern in _SPAN_PATTERNS.items()
)

# สุขภาพ also names the condition of a machine ("การตรวจสอบสุขภาพระบบประจำสัปดาห์" in an IT
# incident report). That is a category error — not a natural person — so it is a DROP, not
# a trim.
_HEALTH_MACHINE_RE = re.compile(
    r"(?:ระบบ|เครื่อง|เซิร์ฟเวอร์|เครือข่าย|อุปกรณ์|ฐานข้อมูล|แอปพลิเคชัน|ไอที)",
    re.UNICODE,
)

_SEGMENT_SPLIT = re.compile(r"[\n\r]+|(?<=[.;])\s|  +", re.UNICODE)

# Tier 1 — never vetoed.
_PRONOUN_RE = re.compile(r"(?:ผม|กระผม|ดิฉัน|ข้าพเจ้า|หนู)", re.UNICODE)
# The negative lookahead is why a bare นาย is not enough: นายจ้าง, นายทะเบียน and นายอำเภอ
# are not references to a person.
_TITLE_NAME_RE = re.compile(
    r"(?:นาย|นาง|นางสาว|น\.ส\.|ด\.ช\.|ด\.ญ\.)\s?"
    r"(?!จ้าง|ทะเบียน|อำเภอ|ก\.|กเทศ|แพทย์|ประกัน)[ก-ฮ][ก-๙]{1,20}",
    re.UNICODE,
)

# Tier 2 — role references, vetoable.
_ROLE_RE = re.compile(
    r"(?:ผู้ป่วย|ผู้ต้องหา|จำเลย|โจทก์|ผู้เสียหาย|ลูกจ้าง|พนักงาน|ผู้เอาประกัน"
    r"|ผู้รับบริการ|เจ้าของข้อมูล|ผู้สมัคร|นักเรียน|นักศึกษา)",
    re.UNICODE,
)
_SPECIFICITY_RE = re.compile(
    r"(?:รายนี้|คนนี้|ท่านนี้|ผู้นี้|ดังกล่าว|ชื่อ|รายดังกล่าว)",
    re.UNICODE,
)
_SPECIFICITY_WINDOW = 12
_ORG_FORMING_RE = re.compile(
    r"(?:สมาคม|สหภาพ|สหพันธ์|ชมรม|กลุ่ม|กองทุน|มูลนิธิ|เครือข่าย|สภา|สำนักงาน|ศูนย์|กรม|กระทรวง)$",
    re.UNICODE,
)
# Fitted to 30 authored near-misses; its independent check is the 45-document negative gold
# slice, where it costs nothing. Task 10 widens it with impersonal gold documents.
_IMPERSONAL_REGISTER_RE = re.compile(
    r"ประกาศ|กฎกระทรวง|พระราชบัญญัติ|พ\.ร\.บ\.|ระเบียบ|ข้อบังคับ|แนวทาง|แนวปฏิบัติ|หลักสูตร"
    r"|รายวิชา|มาตรฐาน|งานวิจัย|สถิติ|นิทรรศการ|บรรทัดฐาน|ประมวลกฎหมาย|มาตรา\s*\d|งบประมาณ"
    r"|แบบสำรวจ|สัมมนา|ตีพิมพ์|เผยแพร่|ทั่วประเทศ|ในประเทศไทย",
    re.UNICODE,
)

# ผล(?:การ)?ตรวจ is a RESULT CUE: on its own it asserts nothing about a person, and what was
# tested is named by the keyword that follows it. In "ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน" (gold
# `sn13`) it matches six characters before GENETIC's ดีเอ็นเอ, wins the region on start order
# and masks genetic data under HEALTH. When a specific biological category matches wholly
# inside the span the cue claimed, the cue yields its label to it. The characters never move,
# so this is label correctness only. The other HEALTH keywords (โรค, การรักษา, สุขภาพ,
# ประวัติการรักษา) assert a health fact themselves and do not yield.
_RESULT_CUE_RE = re.compile(r"ผล(?:การ)?ตรวจ", re.UNICODE)
_SPECIFIC_OVER_RESULT_CUE = ("GENETIC", "BIOMETRIC")

_BOUNDARY_RE = re.compile(r"[\s,;.()\[\]/\\|\"'“”‘’<>{}!?:]", re.UNICODE)
# Used only in the overrun fallback, never on a well-formed span.
_STOP_SET = frozenset(
    """มา เมื่อ ตั้งแต่ จาก ใน และ จึง ของ ต่อ อย่าง ไว้ เพื่อ แต่ โดย ซึ่ง หลัง ก่อน ขณะ จน หรือ กับ
    แล้ว ยัง ทั้งนี้ ส่วน รวมทั้ง""".split()
)
# Extra characters handed to the tokenizer past the cap so the boundary near the cap is
# decided with context; the result is still clamped at the cap.
_TRUNCATION_LOOKAHEAD = 20

_HONEST_FALLBACK_TYPES = frozenset({"LOCATION", "ORGANIZATION", "DATE"})

_tokenizer = None


def _get_tokenizer():
    """Lazy module-level newmm tokenizer over the installed pythainlp dictionary."""
    global _tokenizer
    if _tokenizer is None:
        from pythainlp.corpus.common import thai_words
        from pythainlp.tokenize import Tokenizer

        _tokenizer = Tokenizer(custom_dict=thai_words(), engine="newmm")
    return _tokenizer


def _segments(text: str) -> list[tuple[int, int]]:
    """Segment offsets. A single space never splits."""
    out: list[tuple[int, int]] = []
    position = 0
    for match in _SEGMENT_SPLIT.finditer(text):
        out.append((position, match.start()))
        position = match.end()
    out.append((position, len(text)))
    return [(start, end) for start, end in out if end > start]


def _anchored(
    text: str,
    segment: tuple[int, int],
    hit: tuple[int, int],
    person_spans: list[tuple[int, int]],
) -> bool:
    """Two-tier person linkage inside one segment.

    An anchor that lies INSIDE the sensitive hit never counts — a phrase cannot anchor
    itself (the same principle as `_drop_unanchored_facility_spans`).
    """
    segment_start, segment_end = segment
    hit_start, hit_end = hit

    def _outside_hit(start: int, end: int) -> bool:
        return not (hit_start <= start and end <= hit_end)

    register_vetoed = _IMPERSONAL_REGISTER_RE.search(text, segment_start, segment_end) is not None

    # The NAME/SURNAME overlap is the one tier-1 route whose evidence is a model guess and
    # not an exact lexical pattern, and Thai legal boilerplate is exactly where the CRF
    # invents one: 'ยื่นคำร้องตามมาตรา' anchored a CRIMINAL_RECORD span in a sentence with no
    # person in it at all. So the register veto reaches this route too. The pronoun and
    # title+given-name routes below stay never-vetoed, which is what keeps a real named
    # person in a regulatory document a person ("ประกาศ… นายสมชาย ใจดี แจ้งเชื้อชาติ…").
    if not register_vetoed:
        for person_start, person_end in person_spans:
            if person_end <= segment_start or person_start >= segment_end:
                continue
            if _outside_hit(person_start, person_end):
                return True
    for tier1 in (_PRONOUN_RE, _TITLE_NAME_RE):
        for match in tier1.finditer(text, segment_start, segment_end):
            if _outside_hit(match.start(), match.end()):
                return True

    for match in _ROLE_RE.finditer(text, segment_start, segment_end):
        if not _outside_hit(match.start(), match.end()):
            continue
        # The window is clamped at the segment end, as the span shape of §4.3 is: a marker
        # one character past a newline is not evidence about this segment's role word.
        window_end = min(match.end() + _SPECIFICITY_WINDOW, segment_end)
        if _SPECIFICITY_RE.search(text, match.end(), window_end):
            return True  # a specific individual: the veto no longer applies
        if _ORG_FORMING_RE.search(text, segment_start, match.start()):
            continue  # the role word is part of an organization name
        if register_vetoed:
            continue
        return True
    return False


def _stop_word_cut(text: str, tail_start: int, hard_end: int) -> int:
    """End the span BEFORE the first Thai function word in the tail."""
    end = tail_start
    for token in _get_tokenizer().word_tokenize(text[tail_start:hard_end]):
        if token.strip() in _STOP_SET:
            break
        end += len(token)
    return end


def _truncate_at_cap(text: str, tail_start: int, cap: int) -> int:
    """Truncate at the last whole token inside the cap."""
    end = tail_start
    for token in _get_tokenizer().word_tokenize(text[tail_start : cap + _TRUNCATION_LOOKAHEAD]):
        if end + len(token) > cap:
            break
        end += len(token)
    return end


def _span_end(
    text: str,
    match: re.Match[str],
    segment_end: int,
    blocked: list[tuple[int, int]],
) -> int:
    """Forward-only, whitespace-bounded, capped end offset for one keyword hit.

    Whitespace rather than always tokenizing: over the 40 dev spans the whitespace rule
    over-masks 20 characters and under-masks 10, the token rule over-masks 3 and under-masks
    40. Under-masking is a leak, over-masking is only lost utility.
    """
    boundary = _BOUNDARY_RE.search(text, match.end())
    end = boundary.start() if boundary is not None else len(text)
    end = min(end, segment_end)
    for blocked_start, _blocked_end in blocked:
        if match.end() <= blocked_start < end:
            end = blocked_start
    start = match.start()
    if end - start <= MAX_SPAN_CHARS:
        return end

    end = _stop_word_cut(text, match.end(), end)
    if end - start <= MAX_SPAN_CHARS:
        return max(end, match.end())

    return max(_truncate_at_cap(text, match.end(), start + MAX_SPAN_CHARS), match.end())


def _result_cue_category(text: str, data_type: str, match: re.Match[str], end: int) -> str:
    """The specific category a HEALTH result cue is really reporting, or `data_type`.

    "Same region" means the specific keyword matches wholly inside the characters the cue's
    span already claimed, so the label moves and the mask does not.
    """
    if data_type != "HEALTH" or _RESULT_CUE_RE.fullmatch(match.group(0)) is None:
        return data_type
    for specific, pattern in _COMPILED:
        if specific in _SPECIFIC_OVER_RESULT_CUE and pattern.search(text, match.end(), end):
            return specific
    return data_type


def detect_sensitive_spans(
    text: str,
    person_spans: list[tuple[int, int]],
    *,
    blocked_spans: list[tuple[int, int]] | None = None,
) -> list[Entity]:
    """Person-linked ม.26 spans, sorted by start, never overlapping each other."""
    if not text:
        return []
    blocked = sorted(blocked_spans or [])
    persons = list(person_spans or [])
    claimed: list[tuple[int, int]] = []
    out: list[Entity] = []

    for segment_start, segment_end in _segments(text):
        candidates: list[tuple[int, int, str, re.Match[str]]] = []
        for order, (data_type, pattern) in enumerate(_COMPILED):
            for match in pattern.finditer(text, segment_start, segment_end):
                candidates.append((match.start(), order, data_type, match))
        candidates.sort(key=lambda item: (item[0], item[1]))

        for start, _order, data_type, match in candidates:
            if any(claimed_start <= start < claimed_end for claimed_start, claimed_end in claimed):
                continue  # sensitive spans never overlap each other; first claimed wins
            if data_type == "HEALTH" and _HEALTH_MACHINE_RE.match(text, match.end()):
                continue
            if not _anchored(text, (segment_start, segment_end), (start, match.end()), persons):
                continue
            end = _span_end(text, match, segment_end, blocked)
            if end <= start:
                continue
            claimed.append((start, end))
            out.append(
                Entity(
                    entity_id=str(uuid.uuid4()),
                    redact_type="TB",
                    data_type=_result_cue_category(text, data_type, match, end),
                    span=(start, end),
                    score=0.9,
                    original_text=text[start:end],
                )
            )
    return sorted(out, key=lambda entity: entity.span[0])


def _subtract(
    span: tuple[int, int],
    blockers: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Every maximal sub-interval of `span` that no blocker covers, in order.

    Total: the union of what this returns plus the union of the blockers covers `span`
    exactly. That is the whole proof of the merge's coverage invariant — every character a
    span loses is a character some other retained entity covers.
    """
    pieces = [span]
    for blocker_start, blocker_end in sorted(blockers):
        nxt = []
        for start, end in pieces:
            if blocker_end <= start or blocker_start >= end:
                nxt.append((start, end))
                continue
            if blocker_start > start:
                nxt.append((start, min(blocker_start, end)))
            if blocker_end < end:
                nxt.append((max(blocker_end, start), end))
        pieces = [(start, end) for start, end in nxt if end > start]
        if not pieces:
            return []
    return pieces


def _pieces_to_entities(
    entity: Entity,
    pieces: list[tuple[int, int]],
    text: str,
) -> list[Entity]:
    """Split one entity across its remainders.

    The lowest-start piece inherits the original `entity_id` and every further piece gets a
    fresh uuid4 — the same convention `merge_address_spans` and `_prefer_record_names` use
    for the inverse operation. Required, not cosmetic: two pieces sharing one id would be
    written with one pseudonym and one vault record, and the other fragment would be
    unrecoverable on restore.
    """
    return [
        Entity(
            entity_id=entity.entity_id if index == 0 else str(uuid.uuid4()),
            redact_type=entity.redact_type,
            data_type=entity.data_type,
            span=(start, end),
            score=entity.score,
            original_text=text[start:end],
        )
        for index, (start, end) in enumerate(pieces)
    ]


def merge_sensitive_spans(
    text: str,
    kept: list[Entity],
    sensitive: list[Entity],
) -> list[Entity]:
    """Fold sensitive spans into the pipeline's entity list without uncovering
    a single character. Sorted by start, non-overlapping."""
    if not sensitive:
        return kept

    # Rule 1: a candidate is subtracted against every retained FP entity and every retained
    # TB entity that is not one of the three honest-fallback labels. Every remainder is kept.
    blockers = [
        entity.span
        for entity in kept
        if entity.redact_type != "TB" or entity.data_type not in _HONEST_FALLBACK_TYPES
    ]
    claimed: list[tuple[int, int]] = []
    out: list[Entity] = []
    for candidate in sorted(sensitive, key=lambda entity: entity.span[0]):
        # Rule 3: sensitive candidates never overlap each other; the first claimed wins.
        pieces = _subtract(candidate.span, blockers + claimed)
        if not pieces:
            continue
        claimed.extend(pieces)
        out.extend(_pieces_to_entities(candidate, pieces, text))

    # Rule 2: LOCATION / ORGANIZATION / DATE are the ontology's honest-labels catch-alls, so
    # a ม.26 claim on the same characters is strictly more specific. They yield the
    # overlapping characters and keep every remaining piece.
    for entity in kept:
        if entity.redact_type == "TB" and entity.data_type in _HONEST_FALLBACK_TYPES:
            pieces = _subtract(entity.span, claimed)
            if pieces:
                out.extend(_pieces_to_entities(entity, pieces, text))
        else:
            out.append(entity)
    return sorted(out, key=lambda entity: entity.span[0])

"""Format-preserving (FP) PII detector using regex + checksum validation."""

from __future__ import annotations

import re
import uuid

from amphrang.engine.detectors.thai_id import is_valid_thai_id
from amphrang.engine.models import Entity

# ---------------------------------------------------------------------------
# Checksum helpers
# ---------------------------------------------------------------------------


def _luhn_check(digits: str) -> bool:
    """Return True if digits pass the Luhn algorithm."""
    if not digits:
        return False
    try:
        total = 0
        for i, ch in enumerate(reversed(digits)):
            n = int(ch)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0
    except Exception:
        return False


def _iban_check(iban: str) -> bool:
    """Return True if the IBAN passes the mod-97 check."""
    try:
        rearranged = iban[4:] + iban[:4]
        # Letters map to A=10 ... Z=35
        digits = ""
        for ch in rearranged:
            if ch.isalpha():
                digits += str(ord(ch.upper()) - ord("A") + 10)
            else:
                digits += ch
        return int(digits) % 97 == 1
    except Exception:
        return False


def _date_sanity(day: int, month: int) -> bool:
    """Return True if day is 1-31 and month is 1-12."""
    return 1 <= day <= 31 and 1 <= month <= 12


def is_valid_juristic_id(value: str) -> bool:
    """Return True for a 0-leading 13-digit juristic registration number.

    The check digit is byte-for-byte the citizen mod-11 (verified 8/8 against real
    public registration numbers — see docs/decisions/2026-08-26-new-datatype-specs.md),
    so this delegates instead of carrying a second copy of the algorithm.
    """
    raw = _SEP_RE.sub("", value)
    return raw.startswith("0") and is_valid_thai_id(raw)


# ---------------------------------------------------------------------------
# Entity factory
# ---------------------------------------------------------------------------


def _make_entity(data_type: str, match: re.Match, text: str, score: float = 1.0) -> Entity:
    start, end = match.start(1), match.end(1)
    return Entity(
        entity_id=str(uuid.uuid4()),
        redact_type="FP",
        data_type=data_type,
        span=(start, end),
        score=score,
        original_text=text[start:end],
    )


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _deduplicate(
    entities: list[Entity], single_char_ok: frozenset[tuple[int, int]] = frozenset()
) -> list[Entity]:
    """Remove overlapping spans; prefer higher score, then earliest start.

    Score MUST be the primary key: sorting start-first let a 0.9 plate ("ปชช 1")
    evict an overlapping checksum-valid THAI_ID/PHONE and leak it.
    `single_char_ok` exempts label-anchored 1-digit house/moo spans from the 2-char floor."""
    sorted_ents = sorted(entities, key=lambda e: (-e.score, e.span[0]))
    kept: list[Entity] = []
    for ent in sorted_ents:
        if (ent.span[1] - ent.span[0]) < 2 and ent.span not in single_char_ok:
            continue
        overlaps = any(not (ent.span[1] <= k.span[0] or ent.span[0] >= k.span[1]) for k in kept)
        if not overlaps:
            kept.append(ent)
    return sorted(kept, key=lambda e: e.span[0])


# ---------------------------------------------------------------------------
# BANK vs PHONE context disambiguation
# ---------------------------------------------------------------------------


def _rightmost_cue(pattern: re.Pattern, ctx: str) -> int:
    """End offset of the cue nearest the number (rightmost match in ctx), or -1."""
    end = -1
    for m in pattern.finditer(ctx):
        end = m.end()
    return end


def _disambiguate_bank_phone(text: str, candidates: list[Entity]) -> list[Entity]:
    """Resolve spans that are both PHONE and BANK_ACCOUNT.

    Nearest cue in the preceding window decides; tie favours BANK; no cue leaves
    the default (PHONE) untouched.
    """
    types_by_span: dict[tuple[int, int], set[str]] = {}
    for e in candidates:
        types_by_span.setdefault(e.span, set()).add(e.data_type)

    drop_phone: set[tuple[int, int]] = set()
    drop_bank: set[tuple[int, int]] = set()
    for span, types in types_by_span.items():
        if "PHONE" not in types or "BANK_ACCOUNT" not in types:
            continue
        ctx = text[max(0, span[0] - _CUE_WINDOW) : span[0]]
        bank = _rightmost_cue(_BANK_CUE_RE, ctx)
        phone = _rightmost_cue(_PHONE_CUE_RE, ctx)
        if bank < 0 and phone < 0:
            continue
        if bank >= phone:
            drop_phone.add(span)
        else:
            drop_bank.add(span)

    if not drop_phone and not drop_bank:
        return candidates
    out: list[Entity] = []
    for e in candidates:
        if e.data_type == "PHONE" and e.span in drop_phone:
            continue
        if e.data_type == "BANK_ACCOUNT" and e.span in drop_bank:
            continue
        out.append(e)
    return out


def _bank_separators_nonstandard(raw: str) -> bool:
    """True when the separator layout matches no Thai bank-account format.

    Accepted: bare digits, xxx-x-xxxxx-x, xxxxxxx-xxx. Anything else ("2569-004512")
    is a formatted document number.
    """
    positions: list[int] = []
    digits = 0
    for ch in raw:
        if ch.isdigit():
            digits += 1
        else:
            positions.append(digits)
    return bool(positions) and positions != [3, 4, 9] and positions != [7]


def _disambiguate_bank_student(text: str, candidates: list[Entity]) -> list[Entity]:
    """Resolve spans that are both STUDENT_ID and BANK_ACCOUNT.

    Nearer cue decides; a bank cue at least as near keeps BANK. The student side
    uses _student_evidence's anchor distance (tier 3 may have no person word nearby).
    """
    types_by_span: dict[tuple[int, int], set[str]] = {}
    for e in candidates:
        types_by_span.setdefault(e.span, set()).add(e.data_type)

    drop_bank: set[tuple[int, int]] = set()
    drop_student: set[tuple[int, int]] = set()
    for span, types in types_by_span.items():
        if "STUDENT_ID" not in types or "BANK_ACCOUNT" not in types:
            continue
        ctx = text[max(0, span[0] - _CUE_WINDOW) : span[0]]
        bank = _rightmost_cue(_BANK_CUE_RE, ctx)
        bank_dist = len(ctx) - bank if bank >= 0 else None
        student_dist = _student_evidence(text, span[0], span[1])
        if bank_dist is not None and (student_dist is None or bank_dist <= student_dist):
            drop_student.add(span)
        else:
            drop_bank.add(span)

    if not drop_bank and not drop_student:
        return candidates
    out: list[Entity] = []
    for e in candidates:
        if e.data_type == "BANK_ACCOUNT" and e.span in drop_bank:
            continue
        if e.data_type == "STUDENT_ID" and e.span in drop_student:
            continue
        out.append(e)
    return out


def _disambiguate_thai_juristic(text: str, candidates: list[Entity]) -> list[Entity]:
    """Resolve spans that are both THAI_ID and JURISTIC_ID.

    The juristic check digit IS the citizen check digit, so every real registration
    number validates as both and both score 1.0. A juristic cue in the preceding
    window keeps JURISTIC_ID; without one the personal label wins, because 0-leading
    citizen ids exist (persons without registration status) and the value is masked
    either way — the recall-safe default.
    """
    types_by_span: dict[tuple[int, int], set[str]] = {}
    for e in candidates:
        types_by_span.setdefault(e.span, set()).add(e.data_type)

    drop_thai: set[tuple[int, int]] = set()
    drop_juristic: set[tuple[int, int]] = set()
    for span, types in types_by_span.items():
        if "JURISTIC_ID" not in types:
            continue
        if _cue_before(_JURISTIC_CUE_RE, text, span[0]):
            drop_thai.add(span)
        else:
            drop_juristic.add(span)

    if not drop_thai and not drop_juristic:
        return candidates
    out: list[Entity] = []
    for e in candidates:
        if e.data_type == "THAI_ID" and e.span in drop_thai:
            continue
        if e.data_type == "JURISTIC_ID" and e.span in drop_juristic:
            continue
        out.append(e)
    return out


def _disambiguate_driver_student(text: str, candidates: list[Entity]) -> list[Entity]:
    """Resolve spans that are both DRIVER_LICENSE and STUDENT_ID.

    Nearest cue decides; a tie favours DRIVER_LICENSE, whose cue gate is direct
    evidence while the student side may be tier-3 circumstantial.
    """
    types_by_span: dict[tuple[int, int], set[str]] = {}
    for e in candidates:
        types_by_span.setdefault(e.span, set()).add(e.data_type)

    drop_driver: set[tuple[int, int]] = set()
    drop_student: set[tuple[int, int]] = set()
    for span, types in types_by_span.items():
        if "DRIVER_LICENSE" not in types or "STUDENT_ID" not in types:
            continue
        ctx = text[max(0, span[0] - _CUE_WINDOW) : span[0]]
        driver = _rightmost_cue(_DRIVER_CUE_RE, ctx)
        driver_dist = len(ctx) - driver if driver >= 0 else None
        student_dist = _student_evidence(text, span[0], span[1])
        if driver_dist is not None and (student_dist is None or driver_dist <= student_dist):
            drop_student.add(span)
        else:
            drop_driver.add(span)

    if not drop_driver and not drop_student:
        return candidates
    out: list[Entity] = []
    for e in candidates:
        if e.data_type == "DRIVER_LICENSE" and e.span in drop_driver:
            continue
        if e.data_type == "STUDENT_ID" and e.span in drop_student:
            continue
        out.append(e)
    return out


def _student_evidence(text: str, start: int, end: int) -> int | None:
    """Return the distance to a student cue, or ``None``.

    Compound code word blocks. Tier 1: person cue before. Tier 2: person cue after.
    Tier 3: id-introducer on the same line + education cue nearby. A closer bank,
    phone, or sales cue wins.
    """
    line_start = text.rfind("\n", 0, start) + 1

    intro_ctx = text[max(line_start, start - _STUDENT_INTRO_WINDOW) : start]
    if _STUDENT_BLOCKER_RE.search(intro_ctx):
        return None

    # Tier 1 — person cue before, nearest-wins vs commerce.
    ctx = text[max(0, start - _STUDENT_PERSON_WINDOW) : start]
    person = _rightmost_cue(_STUDENT_CUE_RE, ctx)
    competing = _rightmost_cue(_NON_STUDENT_NUM_CUE_RE, ctx)
    if person >= 0 and person > competing:
        return len(ctx) - person

    # Tier 2 — person cue after the digits; any commerce/bank/phone cue in front vetoes
    # ("ใบเสร็จเลขที่ 68123456 นักศึกษาต้องเก็บไว้" — the receipt label owns the digits).
    if competing < 0:
        front = text[max(0, start - _CUE_WINDOW) : start]
        front_owned = (
            _rightmost_cue(_BANK_CUE_RE, front) >= 0 or _rightmost_cue(_PHONE_CUE_RE, front) >= 0
        )
        if not front_owned:
            after = text[end : end + _STUDENT_AFTER_WINDOW]
            m_person = _STUDENT_CUE_RE.search(after)
            if m_person:
                m_commerce = _NON_STUDENT_NUM_CUE_RE.search(after)
                if not m_commerce or m_person.start() < m_commerce.start():
                    return m_person.start() + 1

    # Tier 3 — id-introducer + education context.
    intro = _rightmost_cue(_STUDENT_INTRO_RE, intro_ctx)
    if intro >= 0:
        veto_ctx = text[max(line_start, start - _CUE_WINDOW) : start]
        if not _NON_STUDENT_NUM_CUE_RE.search(veto_ctx):
            edu_ctx = text[max(0, start - _EDU_WINDOW) : min(len(text), end + _EDU_WINDOW)]
            if _EDU_CONTEXT_RE.search(edu_ctx):
                return len(intro_ctx) - intro
    return None


# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Numeric PII uses (?<!\d)...(?!\d) instead of \b: Thai letters are word chars, so \b
# never fires between Thai script and a digit ("เลขบัตรประชาชน1101700230708").
_RE_THAI_ID = re.compile(r"(?<!\d)(\d{1}[-\s]?\d{4}[-\s]?\d{5}[-\s]?\d{2}[-\s]?\d{1})(?!\d)")
# Juristic registration numbers are 13 digits led by 0 and carry the SAME mod-11 check
# digit, so this mirrors _RE_THAI_ID's optional separators (the dashed registration form
# "0-1075-36000-10-2" must be ONE span, byte-identical to the THAI_ID span the same text
# produces) and only pins the leading 0. The pair is resolved by _disambiguate_thai_juristic.
_RE_JURISTIC_ID = re.compile(r"(?<!\d)(0[-\s]?\d{4}[-\s]?\d{5}[-\s]?\d{2}[-\s]?\d{1})(?!\d)")
_RE_CREDIT_CARD = re.compile(r"(?<!\d)(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})(?!\d)")
# Total length 15-34 (real IBAN range). Do not loosen: a looser floor let a 9-char
# passport-shaped string pass mod-97 by chance and steal the span from PASSPORT.
_RE_IBAN = re.compile(r"\b([A-Z]{2}\d{2}[A-Z0-9]{11,30})\b")
# Same Thai-adjacency lookarounds as above ("อีเมลmanop.d@x.com" clipped the local part).
# The trailing lookahead allows "." so a sentence-final period keeps the whole address.
_RE_EMAIL = re.compile(
    r"(?<![a-zA-Z0-9._%+\-])([a-zA-Z0-9][a-zA-Z0-9._%+\-]*@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})"
    r"(?![a-zA-Z0-9\-])"
)
_RE_PHONE_MOBILE = re.compile(r"(?<!\d)(0[- ]?[6-9]\d[-\s]?\d{3}[-\s]?\d{4})(?!\d)")
# Thai landlines are 9 digits: Bangkok 02-XXX-XXXX, provincial 0XX-XXX-XXX. [2-7] never
# collides with mobile 0[6-9]. The separator after the leading 0 is optional (0-2123-4567)
# and is [- ], NOT [-\s]: a newline there fused a lone '0' ending a table row with the next
# row's digits, and a false cross-row span causes irreversible PDF masking on both rows.
_RE_PHONE_LANDLINE = re.compile(
    r"(?<!\d)(0[- ]?(?:2[-\s]?\d{3}[-\s]?\d{4}|[3-7]\d[-\s]?\d{3}[-\s]?\d{3}))(?!\d)"
)
# +66 drops the leading 0, so 8 (landline) or 9 (mobile) digits follow.
_RE_PHONE_INTL = re.compile(r"(?<![a-zA-Z0-9_])(\+66[-\s]?\d(?:[-\s]?\d){7,8})(?!\d)")
_RE_BANK_ACCOUNT_1 = re.compile(r"(?<!\d)(\d{3}[-\s]?\d{1}[-\s]?\d{5}[-\s]?\d{1})(?!\d)")
_RE_BANK_ACCOUNT_2 = re.compile(r"(?<!\d)(\d{7}[-\s]?\d{3})(?!\d)")
_RE_DATE = re.compile(
    # day-first OR ISO year-first; year-first must come second so day-first wins short years.
    r"(?<!\d)(\d{1,2}[/\-]\d{1,2}[/\-](?:\d{4}|\d{2})|\d{4}[/\-]\d{1,2}[/\-]\d{1,2})(?!\d)"
)
# Thai-month dates ("16 สิงหาคม 2508"). Day + month + year ALL required: no day is a month
# reference, no year is a period endpoint ("ระหว่างวันที่ 1 เมษายน ถึง ..."). Separators are
# literal spaces (a newline between tokens is not one date). Same เกิด-cue routing as numeric.
_THAI_MONTHS = (
    "มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม"
)
_RE_DATE_THAI_MONTH = re.compile(
    rf"(?<!\d)(\d{{1,2}} (?:{_THAI_MONTHS}) (?:พ\.?ศ\.? ?)?\d{{4}})(?!\d)"
)
# Trailing (?!\d) is load-bearing: without it the pattern bit the first digits of a longer
# number ("ปชช 1101...") and evicted the checksum-valid THAI_ID/PHONE. No leading (?<!\d):
# the new-format leading digit ("1กก 1234") is re-attached after matching (step 8) because a
# digit-led alternative loses to an earlier bogus match that eats the digit ("ทะเบียน 2กท").
_RE_VEHICLE_PLATE = re.compile(r"([ก-ฮ]{1,3}\s*\d{1,4})(?!\d)")
# Alnum-boundary lookarounds, not \b: a passport glued to Thai text slipped past \b.
_RE_PASSPORT_TH = re.compile(r"(?<![A-Za-z0-9_])([A-Z]{2}\d{7})(?![A-Za-z0-9_])")
_RE_PASSPORT = re.compile(r"(?<![A-Za-z0-9_])([A-Z]{1,2}\d{6,9})(?![A-Za-z0-9_])")
_RE_STUDENT_ID = re.compile(r"(?<!\d)(\d{8,12})(?!\d)")
# Dashed student-id shape, label-gated at the call site (see step 10b).
_RE_STUDENT_ID_DASHED = re.compile(r"(?<!\d)(\d{2}-\d{2}-\d{4})(?!\d)")
_STUDENT_LABEL_RE = re.compile(r"(?:รหัส|เลขประจำตัว)(?:นักศึกษา|นิสิต|นักเรียน)")

# Thai address components key on structure (label word + value) because NER only knows
# place NAMES, the least identifying part. Group 1 is the value only; the label and an
# optional ASCII/full-width colon stay outside it so the span is exactly the value.
# The ที่อยู่ suffixes are a closed list, not a free-text gap — "ที่อยู่เดิมราคา 88" must
# never capture.
_RE_HOUSE_NO = re.compile(
    r"(?:บ้านเลขที่|เลขที่|ทะเบียนบ้าน|ที่อยู่(?:ปัจจุบัน|ตามทะเบียนบ้าน|ที่ติดต่อได้)?"
    r"|สถานที่เช่า|ที่ตั้งสำนักงานใหญ่)\s*[:：]?\s*(\d{1,4}(?:\s*[/-]\s*\d{1,4})?)(?!\d)"
)
# Some form rows start with the house number and put the street cue after it.
_RE_HOUSE_BEFORE_STREET = re.compile(
    r"(?<!\d)(\d{1,4}(?:\s*[/-]\s*\d{1,4})?)\s+(?=(?:ถนน|ถ\.|ซอย|ซ\.|ตรอก))"
)
# Condo rows put the room number first. Slash-form ONLY: a bare number before a building
# word is usually a quantity ("จำนวน 88 หมู่บ้าน").
_RE_HOUSE_BEFORE_BUILDING = re.compile(
    r"(?<!\d)(\d{1,4}\s*/\s*\d{1,4})\s+(?=(?:คอนโด|อาคาร|หมู่บ้าน|ตึก|นิคม|หมู่))"
)
_RE_YEAR_PREFIX = re.compile(r"(?:ปี(?:งบประมาณ|ภาษี)?|พ\.?\s*ศ\.?)\s*$")
# Soi/road NAME plus number ("ลาดพร้าว 71"): masking only the digits leaves the person locatable.
_RE_SOI_ROAD = re.compile(r"(?:ซอย|ซ\.|ถนน|ถ\.)\s*([ก-๛A-Za-z0-9]+(?:\s*\d{1,4})?)(?!\d)")
# Industrial-estate NAME; the lookahead keeps the state agency (การนิคมฯแห่งประเทศไทย) out.
_RE_ESTATE = re.compile(r"นิคมอุตสาหกรรม\s*(?!แห่งประเทศไทย)([ก-๛A-Za-z0-9]+)")
_RE_MOO = re.compile(r"(?:หมู่ที่|หมู่|ม\.)\s*(\d{1,3})(?!\d)")
# Admin-area NAMES after their label. The lookbehinds are load-bearing: อำเภอ inside นายอำเภอ
# (a title) produced an ADDRESS span that evicted a correct NAME span. เขต(?!บริการ|พื้นที่)
# excludes the agency terms เขตบริการ / เขตพื้นที่การศึกษา (no Bangkok เขต starts that way).
_RE_ADMIN_AREA = re.compile(
    r"(?:แขวง|ตำบล|ต\.|(?<!นาย)(?<!ปลัด)(?<!รอง)(?<!ท่าน)(?:อำเภอ|เขต(?!บริการ|พื้นที่))|อ\.|จังหวัด|จ\.)\s*([ก-๛]{2,})"
)
# The 77 provinces (fixed national list). A bare province ends most addresses and no label
# keys it. Adjacency-gated at the call site (only shortly AFTER an admin-area capture) so a
# province in prose never fires. Longest-first so สมุทรสงคราม is not clipped by a sibling.
_PROVINCES = (
    "กระบี่",
    "กรุงเทพมหานคร",
    "กาญจนบุรี",
    "กาฬสินธุ์",
    "กำแพงเพชร",
    "ขอนแก่น",
    "จันทบุรี",
    "ฉะเชิงเทรา",
    "ชลบุรี",
    "ชัยนาท",
    "ชัยภูมิ",
    "ชุมพร",
    "เชียงราย",
    "เชียงใหม่",
    "ตรัง",
    "ตราด",
    "ตาก",
    "นครนายก",
    "นครปฐม",
    "นครพนม",
    "นครราชสีมา",
    "นครศรีธรรมราช",
    "นครสวรรค์",
    "นนทบุรี",
    "นราธิวาส",
    "น่าน",
    "บึงกาฬ",
    "บุรีรัมย์",
    "ปทุมธานี",
    "ประจวบคีรีขันธ์",
    "ปราจีนบุรี",
    "ปัตตานี",
    "พระนครศรีอยุธยา",
    "พะเยา",
    "พังงา",
    "พัทลุง",
    "พิจิตร",
    "พิษณุโลก",
    "เพชรบุรี",
    "เพชรบูรณ์",
    "แพร่",
    "ภูเก็ต",
    "มหาสารคาม",
    "มุกดาหาร",
    "แม่ฮ่องสอน",
    "ยโสธร",
    "ยะลา",
    "ร้อยเอ็ด",
    "ระนอง",
    "ระยอง",
    "ราชบุรี",
    "ลพบุรี",
    "ลำปาง",
    "ลำพูน",
    "เลย",
    "ศรีสะเกษ",
    "สกลนคร",
    "สงขลา",
    "สตูล",
    "สมุทรปราการ",
    "สมุทรสงคราม",
    "สมุทรสาคร",
    "สระแก้ว",
    "สระบุรี",
    "สิงห์บุรี",
    "สุโขทัย",
    "สุพรรณบุรี",
    "สุราษฎร์ธานี",
    "สุรินทร์",
    "หนองคาย",
    "หนองบัวลำภู",
    "อ่างทอง",
    "อำนาจเจริญ",
    "อุดรธานี",
    "อุตรดิตถ์",
    "อุทัยธานี",
    "อุบลราชธานี",
)
_RE_PROVINCE = re.compile("(" + "|".join(sorted(_PROVINCES, key=len, reverse=True)) + ")")
_PROVINCE_ADJACENCY_WINDOW = 20
_THAI_LETTER_RE = re.compile(r"[ก-๛]")
# Sibling window for the 1-digit house/moo exemption (see step 11).
_ADDR_SIBLING_WINDOW = 40
# A bare 5-digit run is too common to mask on sight; claimed only with an address cue in front.
_RE_POSTAL_CODE = re.compile(r"(?<!\d)(\d{5})(?!\d)")
# HN is typically 5-9 digits, below the generic 8-digit catch-all floor; needs its own cue.
_RE_MEDICAL_ID = re.compile(
    r"(?<![A-Za-z])(?:HN|เวชระเบียน|ผู้ป่วยเลขที่)\s*[:：]?\s*(\d{4,9})(?!\d)", re.IGNORECASE
)

# Smart-card driving-licence number: 8 digits with no self-validating structure, so the
# cue gate (step 15) is the whole precision story. The legacy alphanumeric form
# ("กก.00000/00") is deliberately out of scope — it collides with _RE_VEHICLE_PLATE.
_RE_DRIVER_LICENSE = re.compile(r"(?<!\d)(\d{8})(?!\d)")
# House registration code (เลขรหัสประจำบ้าน): 11 digits, no verified checksum, cue-gated.
_RE_HOUSE_REG = re.compile(r"(?<!\d)(\d{11})(?!\d)")
# LINE handle. The cue is part of the pattern because it must sit BEFORE the value on the
# SAME line (the gap class excludes newlines), which is the entire gate. The alnum
# lookbehind stops "online"/"deadline" from cueing, and group 1 must start alnum (after an
# optional "@") so a stray hyphen never leads the handle.
_RE_LINE_ID = re.compile(
    r"(?<![A-Za-z0-9_])(?:LINE|ไลน์)[ \t]*(?:ID|ไอดี)?[ \t:：=]{0,12}"
    r"(@?[A-Za-z0-9][A-Za-z0-9._\-]{3,23})(?![A-Za-z0-9._\-])",
    re.IGNORECASE,
)
# Decimal lat/lon pair. >=4 decimals on BOTH sides is what separates a coordinate from a
# money pair ("12.50, 100.75"); the in-globe range check runs in the step body.
_RE_GPS = re.compile(r"(?<![\d.])(-?\d{1,2}\.\d{4,7},\s?-?\d{1,3}\.\d{4,7})(?![\d.])")
# IPv4 dotted quad. The trailing guard is (?!\.?\d), NOT (?![\d.]): a sentence-final period
# ("เข้าถึงจาก IP 192.168.1.44.") must not kill the match, while a fifth dotted group still
# must ("1.2.3.4.5" — the "." IS followed by a digit). Together with (?<![\d.]), which blocks
# every later start inside such a run, that is what rejects five groups. \b cannot do either.
# Octet range is checked in the step body.
_RE_IP_V4 = re.compile(r"(?<![\d.])(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?!\.?\d)")
# IPv6: the full form pinned at EXACTLY 8 groups, or a ::-compressed form. A 3-7 group
# alternative would read a timestamp ("10:15:20") as an address, so only the two shapes
# that carry their own evidence are admitted. The compressed group count is bounded to
# 2..8 in the step body. Alnum/colon boundaries, not \b — a Thai char is a word char. "."
# is deliberately NOT in the boundary classes: it would drop a sentence-final address.
_RE_IP_V6 = re.compile(
    r"(?<![0-9A-Za-z:])("
    r"(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,7}:(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,6})?"
    r"|::(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,7})?"
    r")(?![0-9A-Za-z:])"
)
# MAC: six hex pairs, ONE separator style per value (no mixed ":"/"-" form exists). Six
# pairs is the whole gate — a time range ("10:15-11:30") is two groups and never reaches it.
# Same reason as IPv6 for keeping "." out of the boundary classes.
_RE_MAC = re.compile(
    r"(?<![0-9A-Za-z:\-])((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}"
    r"|(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2})(?![0-9A-Za-z:\-])"
)
# Land-deed number: 1-6 digits, frozen by docs/decisions/2026-08-26-wave1-format-specs.md.
# No checksum exists (the number is a per-อำเภอ sequential integer), so the cue gate is the
# entire precision story. Like _RE_LINE_ID the cue lives INSIDE the pattern because it must
# sit before the value on the SAME line; the gap class excludes newlines. Group 1 is the
# digits only, so the 0.9 span wins just the deed digits in _deduplicate and leaves the
# ตำบล/อำเภอ chain behind it for the ADDRESS pass.
# The น.ส. suffix letters are the กรมที่ดิน form series, not a guess: น.ส.3 / น.ส.3ก / น.ส.3ข
# are the หนังสือรับรองการทำประโยชน์, and the โฉนดที่ดิน series runs น.ส.4 / น.ส.4ก / น.ส.4ข /
# น.ส.4ค (กฎกระทรวง ฉบับที่ 5 พ.ศ.2497) / น.ส.4ง (ฉบับที่ 17 พ.ศ.2514) / น.ส.4จ, the current
# ครุฑแดง form. ก-ง are no longer issued but still circulate on paper, so all five stay.
_RE_LAND_DEED = re.compile(
    r"(?:โฉนด(?:ที่ดิน)?\s*เลขที่|เลขที่โฉนด|น\.ส\.\s*(?:3\s*[กข]?|4\s*[กขคงจ]?)\s*เลขที่)"
    r"[ \t:：]{0,20}(?<!\d)(\d{1,6})(?!\d)"
)

_SEP_RE = re.compile(r"[-\s]")
_THAI_CHAR_RE = re.compile(r"[฀-๿]")

# BANK-vs-PHONE cues. `บัญชี` already covers เลขบัญชี / เลขที่บัญชี as a substring.
_BANK_CUE_RE = re.compile(r"บัญชี|ธนาคาร")
_PHONE_CUE_RE = re.compile(r"โทรศัพท์|โทร|เบอร์|มือถือ|ติดต่อ")

# "เกิด" covers วันเกิด / เกิดวันที่ / เกิดเมื่อ but NOT เกิดเหตุ/เหตุเกิด (an accident date was
# labeled a birthday). English DOB labels are a real register on Thai visa/passport forms.
_BIRTH_CUE_RE = re.compile(r"(?<!เหตุ)เกิด(?!เหตุ)|date of birth|\bd\.?o\.?b\b", re.IGNORECASE)
# Postal cue window is wider than _CUE_WINDOW: the code sits at the END of the address line,
# a whole district/province name away from the nearest cue.
_POSTAL_CUE_RE = re.compile(r"รหัสไปรษณีย์|จังหวัด|แขวง|ตำบล|อำเภอ|เขต(?!บริการ)|กรุงเทพ|ที่อยู่")
_POSTAL_CUE_WINDOW = 45
# Sibling five-digit groups count as an enumeration only when nothing but glue sits between
# them; Thai words between codes mean distinct addresses on one line, all real PII.
_POSTAL_SIBLING_WINDOW = 25
_POSTAL_GLUE_RE = re.compile(r"(?:\s|,|/|และ|หรือ)*")
# Bare "รหัส" is deliberately NOT here: it also labels รหัสสินค้า / รหัสวิชา / รหัสไปรษณีย์,
# which are masked as ID_NUMBER anyway, so admitting it would only cost an honest label.
# ผู้เข้าสอบ recovers gold sv09 ("ผู้เข้าสอบลำดับที่ 14 66011204 ห้องสอบ 302" — no introducer
# at all); อาจารย์ที่ปรึกษา recovers gold sv17 ("แจ้งผลสอบของ 66021450 ให้อาจารย์ที่ปรึกษาทราบ" —
# the only person word is behind the digits, so tier 2 needs it). Both are academic-institution
# role words, not topic words.
_STUDENT_CUE_RE = re.compile(
    r"รหัสนักศึกษา|รหัสนิสิต|นักศึกษา|นิสิต|นักเรียน|ผู้เรียน|student|ผู้เข้าสอบ|อาจารย์ที่ปรึกษา",
    re.IGNORECASE,
)
# Compound "รหัสX" code words block every student tier even with education words nearby.
# Closed list of document-field names, not topic words.
_STUDENT_BLOCKER_RE = re.compile(
    r"รหัส(?:ราย)?วิชา|รหัสหลักสูตร|รหัสเอกสาร|รหัสพนักงาน|รหัสอ้างอิง|รหัสชำระ"
    r"|รหัสสินค้า|รหัสรายการ|รหัสสั่งซื้อ|รหัสโครงการ|รหัสครุภัณฑ์|รหัสผ่าน"
)
# Bare id-introducers for tier 3. \bid\b so it does not fire inside "paid"/"provider".
_STUDENT_INTRO_RE = re.compile(r"รหัสประจำตัว|เลขประจำตัว|รหัส|\bid\b", re.IGNORECASE)
# Deliberately narrow: no คณะ (คณะกรรมการ), no bare สอบ and no bare วิชา (วิชาชีพ), no
# มหาวิทยาลัย/โรงเรียน (ambient org), no ทะเบียน (registries), no คัดเลือก (hiring).
# ที่นั่งสอบ (exam-seat row) recovers gold ed15, สอบสัมภาษณ์ recovers gold ed04's three roster
# lines, ทุนวิจัย recovers gold sv11 — all three are exam/funding COMPOUNDS, which is why the
# bare สอบ ban still holds.
_EDU_CONTEXT_RE = re.compile(
    r"นักศึกษา|นิสิต|นักเรียน|ผู้เรียน|student|ลงทะเบียนเรียน|ภาคเรียน|สหกิจศึกษา"
    r"|หน่วยกิต|ขาดเรียน|ค่าเทอม|สำเร็จการศึกษา|อาจารย์ที่ปรึกษา|ชั้นปี|เกรดเฉลี่ย"
    r"|ที่นั่งสอบ|สอบสัมภาษณ์|ทุนวิจัย",
    re.IGNORECASE,
)
_STUDENT_PERSON_WINDOW = 60  # tier 1: person cue before the digits
_STUDENT_AFTER_WINDOW = 45  # tier 2: person cue after the digits
_STUDENT_INTRO_WINDOW = 20  # tier 3: introducer must be this close, same line
# tier 3: education token within this many chars either side. 120, not 100, because gold ed04's
# THIRD roster line sits 105 characters after the สอบสัมภาษณ์ heading that vouches for the list.
_EDU_WINDOW = 120
# Commerce words that own a nearby number ("นักเรียนสั่งซื้อสินค้ารหัส 88910423" is an order
# number); nearest-cue-wins against the person cue.
_NON_STUDENT_NUM_CUE_RE = re.compile(
    r"ราคา|ยอด|จำนวนเงิน|ใบเสร็จ|ใบแจ้งหนี้|ใบกำกับ|สินค้า|สั่งซื้อ|คำสั่งซื้อ|ออเดอร์|invoice|order",
    re.IGNORECASE,
)
_PASSPORT_CUE_RE = re.compile(r"พาสปอร์ต|หนังสือเดินทาง|passport", re.IGNORECASE)
# JURISTIC vs THAI_ID cue. Not a gate on emission (the checksum is), only the tie-breaker
# in _disambiguate_thai_juristic. `นิติบุคคล` already covers เลขทะเบียนนิติบุคคล as a substring.
_JURISTIC_CUE_RE = re.compile(
    r"นิติบุคคล|ทะเบียนบริษัท|ทะเบียนพาณิชย์|เลข(?:ประจำตัว)?ผู้เสียภาษี|tax\s*id|juristic",
    re.IGNORECASE,
)
_DRIVER_CUE_RE = re.compile(
    r"ใบขับขี่|ใบอนุญาตขับขี่|ใบอนุญาตขับรถ|driv(?:er'?s?|ing)\s*licen[cs]e", re.IGNORECASE
)
# `รหัสประจำบ้าน` already covers เลขรหัสประจำบ้าน as a substring.
_HOUSE_REG_CUE_RE = re.compile(r"รหัสประจำบ้าน")
# IPv4 cue set, promoting the catch-all to 0.9. Case-sensitive on purpose: an IGNORECASE
# "IP" fires inside ordinary lowercase prose ("equipment", "recipient").
_IP_CUE_RE = re.compile(
    r"IP|ไอพี|address|แอดเดรส|server|เซิร์ฟเวอร์|host|โฮสต์|router|เราเตอร์|เชื่อมต่อ|log"
)
# Dotted quads that are not addresses at all, suppressing the 0.8 catch-all ONLY — a
# cue-gated 0.9 hit is never suppressed, so "IP 1.2.3.4" survives every word here. Version
# strings share the shape byte for byte, and so do Thai document-section references:
# "ตามข้อ 1.2.3.4", "ตามมาตรา 26.1.2.3", "เอกสารหมายเลข 2.5.1.9", "หนังสือที่ ศธ 0.5.12.7".
# `ข้อ` carries a negative lookahead for `มูล`: ข้อมูล is by far the commonest Thai word
# starting with it, and the one that sits beside real addresses ("ตรวจสอบข้อมูล 203.154.77.9").
_IP_SUPPRESS_CUE_RE = re.compile(
    r"version|เวอร์ชัน|รุ่น|build|ข้อ(?!มูล)|มาตรา|หมายเลข|หนังสือที่", re.IGNORECASE
)

# A KNOWN document-code prefix glued onto the digits ("PO-2569-004512") marks one org code.
# Closed list, NOT any letters- prefix: the generic form silenced real accounts written as
# SCB-/KBANK-/A/C-<digits> and org-issued personal ids (EMP-...).
_GLUED_CODE_PREFIX_RE = re.compile(r"(?:PO|RC|TX|SKU|ITM)-\Z", re.IGNORECASE)
_GLUED_PREFIX_LOOKBACK = 12


def _glued_code_prefix(text: str, start: int) -> bool:
    return bool(_GLUED_CODE_PREFIX_RE.search(text[max(0, start - _GLUED_PREFIX_LOOKBACK) : start]))


# Full field labels introducing an organizational number; bare โครงการ/สิทธิบัตร are topic
# words and deliberately absent ("เงินรางวัลสิทธิบัตรจะโอนเข้า<บัญชี>" is a royalty transfer).
# Positive evidence of a document number, so nothing is emitted (unlike ID_NUMBER demotions).
_ORG_NUM_CUE_RE = re.compile(r"เลขที่โครงการ|ISSN|คำขอรับสิทธิบัตร|สิทธิบัตรเลขที่", re.IGNORECASE)


def _org_number_cued(text: str, start: int) -> bool:
    ctx = text[max(0, start - _CUE_WINDOW) : start]
    org = _rightmost_cue(_ORG_NUM_CUE_RE, ctx)
    return org >= 0 and org > _rightmost_cue(_BANK_CUE_RE, ctx)


def _cue_before(cue_re: re.Pattern, text: str, start: int) -> bool:
    return bool(cue_re.search(text[max(0, start - _CUE_WINDOW) : start]))


# A plate cue shortly before the match relaxes the mid-word guard (plate glued to Thai text).
_PLATE_CUE_RE = re.compile(r"ทะเบียน")
_PLATE_CUE_WINDOW = 15
# Civil-registration compounds (ทะเบียนบ้าน etc.) must not cue: they turned house numbers into
# plates ("ทะเบียนบ้าน 203" -> "น 203"). Any unblocked occurrence in the window still cues.
_PLATE_CUE_BLOCKED_CONTINUATIONS = ("บ้าน", "สมรส", "ราษฎร", "หย่า")
# Uncued-only all-consonant prose word-leads (amounts, times, counts). Unlike _PLATE_STOPWORDS
# a cue relaxes these: a 3-letter motorcycle series can legally spell them.
_PLATE_UNCUED_LEAD_STOPWORDS = frozenset({"ยอด", "ออก", "รวม"})
# Below checksum-backed (1.0), above numeric catch-alls (0.8). The re-attached variant sits a
# hair higher so it wins _deduplicate against the candidate whose digit it claimed (step 8).
_PLATE_SCORE = 0.9
_PLATE_REATTACHED_SCORE = 0.91


def _plate_cue_before(text: str, start: int) -> bool:
    """A plate cue in the window whose continuation is not civil registration."""
    for cue in _PLATE_CUE_RE.finditer(text, max(0, start - _PLATE_CUE_WINDOW), start):
        if not text.startswith(_PLATE_CUE_BLOCKED_CONTINUATIONS, cue.end()):
            return True
    return False


# A glued cue lets [ก-ฮ]{1,3} eat the cue word's tail consonant ("ทะเบียนรถขก 4471" ->
# "ถขก 4471"); the full cue-word forms locate where the cue really ends.
_PLATE_CUE_TRIM_RE = re.compile(r"ทะเบียน(?:รถ(?:ยนต์|จักรยานยนต์)?)?")


def _trim_glued_plate_cue(text: str, start: int, end: int) -> int:
    """Return the plate start with any glued cue-word overlap removed."""
    for cue in _PLATE_CUE_TRIM_RE.finditer(text, max(0, start - _PLATE_CUE_WINDOW), end):
        if cue.start() <= start < cue.end() <= end and _PLATE_LEAD_RE.match(text[cue.end() : end]):
            return cue.end()
    return start


# All-consonant locality words that precede a number ("ซอย N"); real plate prefixes are not words.
_PLATE_STOPWORDS = frozenset({"ซอย", "ถนน"})
# Ministry abbreviations in government document refs ("ที่ ศธ 0521/..."). Uncued matches with
# these prefixes are document numbers; a plate cue overrides (they are legal plate pairs too).
_MINISTRY_DOC_CODES = frozenset(
    {
        "ศธ",
        "กค",
        "มท",
        "นร",
        "สธ",
        "กษ",
        "ตช",
        "อว",
        "คค",
        "ทส",
        "พณ",
        "รง",
        "วธ",
        "พม",
        "ยธ",
        "ดศ",
        "กต",
        "กห",
        "ปช",
    }
)
_PLATE_LEAD_RE = re.compile(r"[ก-ฮ]{1,3}")
# Generous: Thai has no spaces and the cue can sit a whole clause before the number.
_CUE_WINDOW = 30


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------


def detect_fp(text: str) -> list[Entity]:
    """Detect format-preserving PII via regex + checksum.

    Returns FP entities sorted by start, non-overlapping, spans >= 2 chars.
    """
    candidates: list[Entity] = []

    # 1. THAI_ID
    for m in _RE_THAI_ID.finditer(text):
        raw = _SEP_RE.sub("", m.group(1))
        if len(raw) == 13 and is_valid_thai_id(raw):
            candidates.append(_make_entity("THAI_ID", m, text, score=1.0))

    # 2. CREDIT_CARD
    for m in _RE_CREDIT_CARD.finditer(text):
        raw = _SEP_RE.sub("", m.group(1))
        if len(raw) == 16 and _luhn_check(raw):
            candidates.append(_make_entity("CREDIT_CARD", m, text, score=1.0))

    # 3. IBAN
    for m in _RE_IBAN.finditer(text):
        if _iban_check(m.group(1)):
            candidates.append(_make_entity("IBAN", m, text, score=1.0))

    # 4. EMAIL
    for m in _RE_EMAIL.finditer(text):
        candidates.append(_make_entity("EMAIL", m, text, score=1.0))

    # 5. PHONE (mobile, landline, international)
    for pattern in (_RE_PHONE_MOBILE, _RE_PHONE_LANDLINE, _RE_PHONE_INTL):
        for m in pattern.finditer(text):
            candidates.append(_make_entity("PHONE", m, text, score=1.0))

    # 6. BANK_ACCOUNT. Uncued, a bare id-introducer ("รหัส <10 digits>") with no student
    # evidence, or a non-standard separator layout, demotes to ID_NUMBER (still masked,
    # recall-first). When student tiers fire, BANK_ACCOUNT is still emitted and
    # _disambiguate_bank_student resolves the pair.
    for pattern in (_RE_BANK_ACCOUNT_1, _RE_BANK_ACCOUNT_2):
        for m in pattern.finditer(text):
            start = m.start(1)
            line_start = text.rfind("\n", 0, start) + 1
            intro_ctx = text[max(line_start, start - _STUDENT_INTRO_WINDOW) : start]
            bank_cued = _rightmost_cue(_BANK_CUE_RE, text[max(0, start - _CUE_WINDOW) : start]) >= 0
            if not bank_cued and (_glued_code_prefix(text, start) or _org_number_cued(text, start)):
                continue
            if not bank_cued and _bank_separators_nonstandard(m.group(1)):
                candidates.append(_make_entity("ID_NUMBER", m, text, score=0.8))
            elif (
                not bank_cued
                and _STUDENT_INTRO_RE.search(intro_ctx)
                and not _STUDENT_BLOCKER_RE.search(intro_ctx)
                and _student_evidence(text, start, m.end(1)) is None
            ):
                candidates.append(_make_entity("ID_NUMBER", m, text, score=0.8))
            else:
                candidates.append(_make_entity("BANK_ACCOUNT", m, text, score=1.0))

    # 7. DATE (generic) / DATE_OF_BIRTH (only with a birth cue nearby)
    for m in _RE_DATE.finditer(text):
        raw = m.group(1)
        parts = re.split(r"[/\-]", raw)
        if len(parts) == 3:
            try:
                # 4-digit leading field = ISO year-first.
                if len(parts[0]) == 4:
                    day, month = int(parts[2]), int(parts[1])
                else:
                    day, month = int(parts[0]), int(parts[1])
                if _date_sanity(day, month):
                    dtype = (
                        "DATE_OF_BIRTH" if _cue_before(_BIRTH_CUE_RE, text, m.start(1)) else "DATE"
                    )
                    candidates.append(_make_entity(dtype, m, text, score=1.0))
            except ValueError:
                pass

    # 7b. Thai-month dates, same เกิด-cue routing as the numeric shapes.
    for m in _RE_DATE_THAI_MONTH.finditer(text):
        day = int(m.group(1).split(" ", 1)[0])
        if not 1 <= day <= 31:
            continue
        dtype = "DATE_OF_BIRTH" if _cue_before(_BIRTH_CUE_RE, text, m.start(1)) else "DATE"
        candidates.append(_make_entity(dtype, m, text, score=1.0))

    # 8. VEHICLE_PLATE. Mid-word matches (preceded by a Thai char) are rejected unless a plate
    # cue precedes. Uncued matches also reject government document refs (slash on either
    # side, ministry prefix), prose word-leads, and digits continuing as [.,]<digit> (amount
    # or clock time). The cue wins every uncued guard: those prefixes are legal plate series.
    for m in _RE_VEHICLE_PLATE.finditer(text):
        start = m.start(1)
        lead = _PLATE_LEAD_RE.match(m.group(1))
        if lead and lead.group() in _PLATE_STOPWORDS:
            continue
        plate_cued = _plate_cue_before(text, start)
        if start > 0 and _THAI_CHAR_RE.match(text[start - 1]) and not plate_cued:
            continue
        if not plate_cued:
            before = text[:start].rstrip()
            after = text[m.end(1) :].lstrip()
            if before.endswith("/") or after.startswith("/"):
                continue
            if lead and lead.group() in _MINISTRY_DOC_CODES:
                continue
            if lead and lead.group() in _PLATE_UNCUED_LEAD_STOPWORDS:
                continue
            nxt = text[m.end(1) : m.end(1) + 2]
            if len(nxt) == 2 and nxt[0] in ".," and nxt[1].isdigit():
                continue
        end = m.end(1)
        score = _PLATE_SCORE
        if plate_cued and start > 0 and _THAI_CHAR_RE.match(text[start - 1]):
            start = _trim_glued_plate_cue(text, start, end)
        elif (
            lead is not None
            and len(lead.group()) == 2
            and start > 0
            and text[start - 1].isdigit()
            and (start < 2 or not text[start - 2].isdigit())
        ):
            # New-format plate: a SINGLE digit before exactly two letters is part of the
            # registration ("2กท 8899"); more digits behind it is a longer number's tail.
            start -= 1
            # The span now overlaps an earlier candidate that ate that digit ("รถ 2"), so it
            # must outrank it in _deduplicate or the whole plate ships unmasked.
            score = _PLATE_REATTACHED_SCORE
        candidates.append(
            Entity(
                entity_id=str(uuid.uuid4()),
                redact_type="FP",
                data_type="VEHICLE_PLATE",
                span=(start, end),
                score=score,
                original_text=text[start:end],
            )
        )

    # 9. PASSPORT — Thai format always; the general catch-all only with a cue, else ID_NUMBER.
    for m in _RE_PASSPORT_TH.finditer(text):
        candidates.append(_make_entity("PASSPORT", m, text, score=1.0))
    for m in _RE_PASSPORT.finditer(text):
        if _cue_before(_PASSPORT_CUE_RE, text, m.start(1)):
            candidates.append(_make_entity("PASSPORT", m, text, score=1.0))
        elif not _glued_code_prefix(text, m.start(1)):
            candidates.append(_make_entity("ID_NUMBER", m, text, score=0.8))

    # 10. STUDENT_ID when the tiered evidence fires; otherwise the generic ID_NUMBER.
    for m in _RE_STUDENT_ID.finditer(text):
        has_student = _student_evidence(text, m.start(1), m.end(1)) is not None
        if not has_student and (
            _glued_code_prefix(text, m.start(1)) or _org_number_cued(text, m.start(1))
        ):
            continue
        dtype = "STUDENT_ID" if has_student else "ID_NUMBER"
        candidates.append(_make_entity(dtype, m, text, score=0.8))

    # 10b. Dashed student ids ("รหัสนักศึกษา 68-01-4429"), which the TB layer reads as DATE.
    # Only a student label with nothing but whitespace/colon before the value qualifies —
    # "รหัสนักศึกษา วันที่ 01-02-2568" must stay a date.
    for m in _RE_STUDENT_ID_DASHED.finditer(text):
        lead = text[max(0, m.start(1) - 25) : m.start(1)]
        label = None
        for lm in _STUDENT_LABEL_RE.finditer(lead):
            label = lm
        if label is not None and re.fullmatch(r"[\s:]*", lead[label.end() :]):
            candidates.append(_make_entity("STUDENT_ID", m, text, score=0.9))

    # 11. ADDRESS components, scored 0.85: above numeric catch-alls (0.8), below checksum
    # types (1.0). Bare "เลขที่" rejects N/<Buddhist year> (document numbering, คำสั่งที่ 27/2569).
    # `addr_candidates` feeds the 1-digit house/moo exemption and the province gate below.
    addr_candidates: list[Entity] = []
    single_digit_addr: list[Entity] = []

    def _addr_candidate(ent: Entity) -> Entity:
        addr_candidates.append(ent)
        candidates.append(ent)
        return ent

    for m in _RE_HOUSE_NO.finditer(text):
        if m.group(0).startswith("เลขที่") and "/" in m.group(1):
            tail = m.group(1).split("/")[-1].strip()
            if tail.isdigit() and 2400 <= int(tail) <= 2699:
                continue
        # Continuing as "-<digit>" is the head of a larger number ("เลขที่ 2569-004512").
        nxt = text[m.end(1) : m.end(1) + 2]
        if len(nxt) == 2 and nxt[0] in "-/" and nxt[1].isdigit():
            continue
        ent = _addr_candidate(_make_entity("ADDRESS", m, text, score=0.85))
        # Only บ้านเลขที่ earns the 1-digit exemption ("ใบเสร็จเลขที่ 7" stays under the floor).
        if m.end(1) - m.start(1) < 2 and m.group(0).startswith("บ้านเลขที่"):
            single_digit_addr.append(ent)
    for pattern in (_RE_HOUSE_BEFORE_STREET, _RE_HOUSE_BEFORE_BUILDING):
        for m in pattern.finditer(text):
            raw = re.sub(r"\s", "", m.group(1))
            prefix = text[max(0, m.start() - 20) : m.start()]
            if raw.isdigit() and 2400 <= int(raw) <= 2699 and _RE_YEAR_PREFIX.search(prefix):
                continue
            _addr_candidate(_make_entity("ADDRESS", m, text, score=0.85))
    for pattern in (_RE_SOI_ROAD, _RE_ESTATE):
        for m in pattern.finditer(text):
            _addr_candidate(_make_entity("ADDRESS", m, text, score=0.85))
    for m in _RE_MOO.finditer(text):
        ent = _addr_candidate(_make_entity("ADDRESS", m, text, score=0.85))
        # หมู่/หมู่ที่ only — ม. also writes school grades ("ชั้น ม.5").
        if m.end(1) - m.start(1) < 2 and m.group(0).startswith("หมู่"):
            single_digit_addr.append(ent)
    admin_value_spans: list[tuple[int, int]] = []
    for m in _RE_ADMIN_AREA.finditer(text):
        # A label glued to a preceding Thai word ("ต่างจังหวัด") may not capture across a
        # newline; a standalone label keeps the reach (forms split label and value by line).
        if (
            m.start() > 0
            and _THAI_CHAR_RE.match(text[m.start() - 1])
            and "\n" in text[m.start() : m.start(1)]
        ):
            continue
        _addr_candidate(_make_entity("ADDRESS", m, text, score=0.85))
        admin_value_spans.append((m.start(1), m.end(1)))

    # 11b. Province gazetteer: standalone name within a short same-line window AFTER an
    # admin-area capture. Provinces do not anchor each other (no cascade). Without an anchor
    # the 77-way scan is skipped outright (measurable rescan cost).
    for m in _RE_PROVINCE.finditer(text) if admin_value_spans else ():
        s, t = m.start(1), m.end(1)
        if s > 0 and _THAI_LETTER_RE.match(text[s - 1]):
            continue
        if t < len(text) and _THAI_LETTER_RE.match(text[t]):
            continue
        if any(e.span[0] < t and s < e.span[1] for e in addr_candidates):
            continue
        if any(
            0 <= s - a_end <= _PROVINCE_ADJACENCY_WINDOW and "\n" not in text[a_end:s]
            for _, a_end in admin_value_spans
        ):
            _addr_candidate(_make_entity("ADDRESS", m, text, score=0.85))

    # 12. POSTAL_CODE — only with an address cue in front. A run of >=3 five-digit groups
    # chained by enumeration glue is a coverage list, not an address tail; Thai words between
    # codes break the chain. Matches come from ONE full-text scan: an endpos-bounded rescan
    # truncated a six-digit neighbor into a phantom five-digit sibling.
    postal_matches = list(_RE_POSTAL_CODE.finditer(text))
    run_lengths: list[int] = []
    run_len = 1
    for prev, cur in zip(postal_matches, postal_matches[1:]):
        gap = text[prev.end(1) : cur.start(1)]
        if len(gap) <= _POSTAL_SIBLING_WINDOW and _POSTAL_GLUE_RE.fullmatch(gap):
            run_len += 1
        else:
            run_lengths.extend([run_len] * run_len)
            run_len = 1
    run_lengths.extend([run_len] * run_len)
    for m, run in zip(postal_matches, run_lengths):
        if run >= 3:
            continue
        ctx = text[max(0, m.start(1) - _POSTAL_CUE_WINDOW) : m.start(1)]
        if not _POSTAL_CUE_RE.search(ctx):
            continue
        _addr_candidate(_make_entity("POSTAL_CODE", m, text, score=0.85))

    # A 1-digit house/moo value survives the 2-char floor only with a sibling address fragment
    # nearby ("บ้านเลขที่ 7 หมู่ที่ 9 ต.แม่เหียะ" yes, a lone "ทหารหมู่ 5" no).
    single_char_ok: set[tuple[int, int]] = set()
    for ent in single_digit_addr:
        s, t = ent.span
        for other in addr_candidates:
            if other is ent:
                continue
            if (
                other.span[0] - t <= _ADDR_SIBLING_WINDOW
                and s - other.span[1] <= _ADDR_SIBLING_WINDOW
            ):
                single_char_ok.add(ent.span)
                break

    # 13. MEDICAL_ID (HN) — cue-gated.
    for m in _RE_MEDICAL_ID.finditer(text):
        candidates.append(_make_entity("MEDICAL_ID", m, text, score=0.9))

    # 14. JURISTIC_ID — 0-leading 13-digit registration number, checksum-scored 1.0. Step 1
    # emits the very same span as THAI_ID (same check digit); _disambiguate_thai_juristic
    # keeps exactly one of them.
    for m in _RE_JURISTIC_ID.finditer(text):
        if is_valid_juristic_id(m.group(1)):
            candidates.append(_make_entity("JURISTIC_ID", m, text, score=1.0))

    # 15. DRIVER_LICENSE — cue-gated ONLY; an uncued 8-digit run still falls out as
    # ID_NUMBER via step 10. 0.9 outranks that 0.8 catch-all in _deduplicate.
    for m in _RE_DRIVER_LICENSE.finditer(text):
        if _cue_before(_DRIVER_CUE_RE, text, m.start(1)):
            candidates.append(_make_entity("DRIVER_LICENSE", m, text, score=0.9))

    # 16. LINE_ID — the cue lives inside the pattern (before the value, same line), so an
    # uncued handle is never claimed.
    for m in _RE_LINE_ID.finditer(text):
        candidates.append(_make_entity("LINE_ID", m, text, score=0.9))

    # 17. GPS_COORD — the only new type needing no cue: the >=4-decimal pair shape plus the
    # in-globe range check carries its own evidence.
    for m in _RE_GPS.finditer(text):
        lat_raw, lon_raw = m.group(1).split(",")
        lat, lon = float(lat_raw), float(lon_raw)
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            candidates.append(_make_entity("GPS_COORD", m, text, score=0.95))

    # 18. HOUSE_REG_ID — cue-gated ONLY (no checksum is publicly verifiable); 0.9 beats the
    # 0.8 STUDENT_ID/ID_NUMBER catch-all that also reads an 11-digit run.
    for m in _RE_HOUSE_REG.finditer(text):
        if _cue_before(_HOUSE_REG_CUE_RE, text, m.start(1)):
            candidates.append(_make_entity("HOUSE_REG_ID", m, text, score=0.9))

    # 19. IP_ADDRESS — IPv4 at 0.9 with a network cue, else a 0.8 catch-all. The catch-all
    # is suppressed for version strings and Thai document-section references, which share the
    # dotted-quad shape byte for byte ("v1.2.3.4", "รุ่น 10.15.7.2", "ตามข้อ 1.2.3.4",
    # "ตามมาตรา 26.1.2.3"); a cued hit is never suppressed. IPv4 collides with no
    # existing digit detector — the dots break every (?<!\d)...(?!\d) run.
    for m in _RE_IP_V4.finditer(text):
        if any(int(octet) > 255 for octet in m.group(1).split(".")):
            continue
        start = m.start(1)
        if _cue_before(_IP_CUE_RE, text, start):
            candidates.append(_make_entity("IP_ADDRESS", m, text, score=0.9))
            continue
        if start > 0 and text[start - 1] in "vV":
            continue
        if _cue_before(_IP_SUPPRESS_CUE_RE, text, start):
            continue
        candidates.append(_make_entity("IP_ADDRESS", m, text, score=0.8))

    # 19b. IPv6 needs no cue: the colon-group shape carries its own evidence. The group count
    # is bounded both ways — below 2 a bare "::" would be claimed, above 8 the value is not an
    # address at all (the compressed alternative can spell more groups than IPv6 allows).
    for m in _RE_IP_V6.finditer(text):
        if 2 <= len([group for group in m.group(1).split(":") if group]) <= 8:
            candidates.append(_make_entity("IP_ADDRESS", m, text, score=0.9))

    # 20. MAC_ADDRESS — no cue: six hex pairs in one separator style is the evidence.
    for m in _RE_MAC.finditer(text):
        candidates.append(_make_entity("MAC_ADDRESS", m, text, score=0.9))

    # 21. LAND_DEED_ID — cue-gated ONLY (the cue lives in the pattern). 0.9 outranks the
    # 0.85 ADDRESS claim that already reads a deed number sitting before ตำบล as a house
    # number, and the span covers the digits alone so the admin-area chain still masks.
    # Deed numbering starts at 1, so a 1-digit deed is a real value: it takes the same
    # single_char_ok exemption from _deduplicate's 2-char floor that บ้านเลขที่/หมู่ take.
    # Unconditional, unlike theirs — the in-pattern cue IS the evidence, so no sibling
    # fragment is needed to vouch for it.
    for m in _RE_LAND_DEED.finditer(text):
        ent = _make_entity("LAND_DEED_ID", m, text, score=0.9)
        candidates.append(ent)
        if ent.span[1] - ent.span[0] < 2:
            single_char_ok.add(ent.span)

    candidates = _disambiguate_thai_juristic(text, candidates)
    candidates = _disambiguate_driver_student(text, candidates)
    candidates = _disambiguate_bank_student(text, candidates)
    candidates = _disambiguate_bank_phone(text, candidates)
    return _deduplicate(candidates, single_char_ok=frozenset(single_char_ok))

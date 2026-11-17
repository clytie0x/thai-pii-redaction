"""Quasi-identifier values and the WP3 document-risk definitions.

Gold entity spans stay the eleven v2 types. Quasi-identifiers are a second
layer, built from placeholders, never from a detector. Section 26 codes are
the tuple in ``pii_redactor.pdpa_categories`` and are not redaction labels.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from pii_redactor.pdpa_categories import SECTION26_CATEGORIES

from .protocol import K_ANONYMITY

# Placeholder kind -> Section 26 code, or None when the QI is not Section 26.
QI_KINDS: dict[str, str | None] = {
    "nickname": None,
    "address_short": None,
    "be_date": None,
    "age": None,
    "occupation": None,
    "s26_race": "RACE_ETHNICITY",
    "s26_politics": "POLITICAL_OPINION",
    "s26_religion": "RELIGION",
    "s26_health": "HEALTH",
    "s26_sexual": "SEXUAL_BEHAVIOR",
    "s26_criminal": "CRIMINAL_RECORD",
    "s26_disability": "DISABILITY",
    "s26_union": "LABOR_UNION",
    "s26_genetic": "GENETIC",
    "s26_biometric": "BIOMETRIC",
}

_MONTHS = (
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)
_NICKNAMES = ("เปี๊ยก", "มิ้น", "โอ๊ต", "บอส", "นัท", "เมย์", "ต้น", "ฟ้า", "น้ำ", "เจ", "กาย", "ปอ")
_JOBS = (
    "ช่างเชื่อม",
    "ครูประจำชั้น",
    "พนักงานขายประกัน",
    "เกษตรกรสวนยาง",
    "พยาบาลเวรดึก",
    "เจ้าหน้าที่ห้องบัตร",
    "คนขับส่งเอกสาร",
    "ช่างซ่อมลิฟต์",
    "แม่ค้าตลาดนัด",
    "เจ้าหน้าที่สินไหม",
)
_SHORT_PLACES = (
    ("พหลฯ", "สามเสนใน", "พญาไท"),
    ("มิตรภาพ", "ศิลา", "เมืองขอนแก่น"),
    ("เพชรเกษม", "บางหว้า", "ภาษีเจริญ"),
    ("ติวานนท์", "สวนใหญ่", "เมืองนนทบุรี"),
    ("สุขุมวิท", "เนินพระ", "เมืองระยอง"),
    ("แสงชูโต", "บ้านเหนือ", "เมืองกาญจนบุรี"),
)
_PHRASES: dict[str, tuple[str, ...]] = {
    "s26_race": (
        "ช่องเชื้อชาติกรอกว่าไทย",
        "ช่องเชื้อชาติเว้นว่าไม่ประสงค์ระบุ",
        "ช่องเผ่าพันธุ์กรอกว่าไม่ทราบ",
    ),
    "s26_politics": (
        "ระบุความคิดเห็นทางการเมืองว่าไม่สังกัดพรรค",
        "บรรทัดพรรคการเมืองเว้นว่าง",
        "ข้อความอุดมการณ์ที่ผู้กรอกขีดฆ่า",
    ),
    "s26_religion": (
        "นับถือศาสนาพุทธ",
        "นับถือศาสนาอิสลาม",
        "นับถือศาสนาคริสต์",
    ),
    "s26_health": (
        "มีประวัติเบาหวานชนิดที่สอง",
        "แพ้ยาเพนิซิลลิน",
        "เคยรักษาไข้เลือดออกเมื่อปีก่อน",
    ),
    "s26_sexual": (
        "ช่องรสนิยมทางเพศกรอกว่าไม่ประสงค์ตอบ",
        "ช่องพฤติกรรมทางเพศเว้นว่าง",
        "ไม่เปิดเผยรสนิยมทางเพศ",
    ),
    "s26_criminal": (
        "ช่องประวัติอาชญากรรมกรอกว่าไม่เคยต้องโทษ",
        "แจ้งว่าไม่เคยถูกฟ้องคดี",
        "ไม่มีประวัติอาชญากรรมที่แนบมา",
    ),
    "s26_disability": (
        "แจ้งความพิการทางการเคลื่อนไหว",
        "ไม่แจ้งความพิการ",
        "ใช้ไม้เท้าตามความพิการที่แจ้งไว้",
    ),
    "s26_union": (
        "เป็นสมาชิกสหภาพแรงงานของสถานประกอบการ",
        "ไม่ได้เป็นสมาชิกสหภาพแรงงาน",
        "เคยเป็นกรรมการสหภาพแรงงาน",
    ),
    "s26_genetic": (
        "ผลตรวจข้อมูลยีนระบุว่าไม่พบตัวบ่งชี้ที่รายงาน",
        "ไม่ได้แนบข้อมูลยีน",
        "ใบรายงานจีโนมเป็นฉบับสังเคราะห์สำหรับแบบฟอร์ม",
    ),
    "s26_biometric": (
        "แบบฟอร์มระบุว่าไม่เก็บลายนิ้วมือ",
        "ไม่แนบข้อมูลชีวภาพ",
        "ช่องลายนิ้วมือขีดว่าไม่ได้สแกน",
    ),
}


@dataclass(frozen=True)
class QiSpan:
    start: int
    end: int
    qi_type: str
    section26: str | None


def catalog_section26() -> tuple[str, ...]:
    """Section 26 codes this study is allowed to emit. The product tuple, unchanged."""
    return SECTION26_CATEGORIES


def draw_qi(rng: random.Random, kind: str) -> str:
    """One fabricated quasi-identifier surface. No real person's data."""
    if kind not in QI_KINDS:
        raise ValueError("unknown-qi")
    if kind == "nickname":
        return rng.choice(_NICKNAMES)
    if kind == "occupation":
        return rng.choice(_JOBS)
    if kind == "age":
        return f"{rng.randint(18, 80)} ปี"
    if kind == "be_date":
        day, month, year = rng.randint(1, 28), rng.randint(1, 12), rng.randint(2560, 2568)
        if rng.random() < 0.5:
            return f"{day} {_MONTHS[month - 1]} {year}"
        return f"{day:02d}/{month:02d}/{year}"
    if kind == "address_short":
        road, local, area = rng.choice(_SHORT_PLACES)
        form = rng.randrange(3)
        if form == 0:
            return f"ซ.{road} {rng.randint(1, 40)} แขวง{local}"
        if form == 1:
            return f"ม.{rng.randint(1, 12)} ต.{local} อ.{area}"
        return f"ถ.{road} เขต{area}"
    return rng.choice(_PHRASES[kind])


def qi_signature(
    text: str,
    qi: Sequence[QiSpan],
    *,
    redacted: Sequence[tuple[int, int]] = (),
) -> tuple[tuple[str, str], ...]:
    """Residual quasi-identifiers after redaction.

    A quasi-identifier stays if any character of it is outside every redacted
    span. Partial coverage is still residual: the risk layer fails closed.
    The key is the sorted set of ``(qi_type, surface)`` pairs, so a repeated
    mention does not change the co-occurrence. Marginal uniqueness of one
    field is not this key.
    """
    kept: set[tuple[str, str]] = set()
    for span in qi:
        if _fully_covered(span.start, span.end, redacted):
            continue
        kept.add((span.qi_type, text[span.start : span.end]))
    return tuple(sorted(kept))


def _fully_covered(start: int, end: int, redacted: Sequence[tuple[int, int]]) -> bool:
    if start >= end:
        return False
    covered = [False] * (end - start)
    for left, right in redacted:
        lo, hi = max(start, left), min(end, right)
        for index in range(lo, hi):
            covered[index - start] = True
    return all(covered)


def document_risk(
    signatures: Sequence[tuple[tuple[str, str], ...]],
    population: Sequence[tuple[tuple[str, str], ...]],
    *,
    k: int = K_ANONYMITY,
) -> dict:
    """Document-level uniqueness against a separate synthetic population.

    A document with no residual quasi-identifier is not risky. A document is
    risky when its co-occurring QI key occurs fewer than ``k`` times in the
    population. The document is not inserted into the population first.
    ``risk_rate`` uses every document as the denominator.
    """
    if k < 1:
        raise ValueError("k-below-1")
    counts = Counter(population)
    risky = 0
    with_qi = 0
    sizes: list[int] = []
    for signature in signatures:
        if not signature:
            sizes.append(0)
            continue
        with_qi += 1
        sizes.append(len({qi_type for qi_type, _surface in signature}))
        if counts[signature] < k:
            risky += 1
    documents = len(signatures)
    return {
        "cooccurrence_sizes": sizes,
        "documents": documents,
        "documents_with_residual_qi": with_qi,
        "k": k,
        "risky_documents": risky,
        "risk_rate": (risky / documents) if documents else 0.0,
    }


def synthetic_population(
    seed: int, n: int, *, fields: Sequence[str] | None = None
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """``n`` background keys. ``n`` is a caller choice: no size is registered yet."""
    if n < 1:
        raise ValueError("population-size")
    chosen = tuple(fields) if fields is not None else tuple(QI_KINDS)
    for field in chosen:
        if field not in QI_KINDS:
            raise ValueError("unknown-qi")
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        present = [field for field in chosen if rng.random() < 0.5]
        if chosen and not present:
            present = [rng.choice(chosen)]
        rows.append(tuple(sorted((field, draw_qi(rng, field)) for field in present)))
    return tuple(rows)


def trir_by_section26(outcomes: Sequence[tuple[str, bool]]) -> dict:
    """Aggregate a supplied attacker. This function is not an attacker.

    Each outcome is ``(section26 code, attack succeeded)``. Categories with no
    trials have a null rate. Codes outside the catalog are rejected.
    """
    allowed = set(SECTION26_CATEGORIES)
    trials = dict.fromkeys(SECTION26_CATEGORIES, 0)
    successes = dict.fromkeys(SECTION26_CATEGORIES, 0)
    for category, succeeded in outcomes:
        if category not in allowed:
            raise ValueError("unknown-section26")
        trials[category] += 1
        successes[category] += int(succeeded)
    return {
        category: {
            "rate": (successes[category] / trials[category]) if trials[category] else None,
            "successes": successes[category],
            "trials": trials[category],
        }
        for category in SECTION26_CATEGORIES
    }

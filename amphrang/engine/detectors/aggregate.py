"""Shared PII detection assembly used by both the web API and the benchmark.

detect_all() is the exact ensemble /api/sanitize runs (FP + TB + FN scan, then
dedup), so the benchmark measures precisely what ships.
"""

from __future__ import annotations

import re

from amphrang.engine.detectors.fn_scanner import scan_fn
from amphrang.engine.detectors.fp_detector import detect_fp
from amphrang.engine.detectors.name_context import detect_parallel_record_names
from amphrang.engine.detectors.sensitive_span import (
    detect_sensitive_spans,
    merge_sensitive_spans,
)
from amphrang.engine.detectors.tb_detector import NERChunkDiagnostics, detect_tb
from amphrang.engine.models import Entity


def dedupe_spans(entities: list[Entity]) -> list[Entity]:
    """Drop overlapping spans, keeping a non-overlapping set.

    FP (regex/checksum) entities go first so a fuzzy TB span can never displace a
    precise hit it overlaps. Within each tier: earlier start, then longer span.
    """

    def _key(e: Entity):
        return (e.span[0], -(e.span[1] - e.span[0]))

    kept: list[Entity] = []

    def _overlaps(e: Entity) -> bool:
        return any(not (e.span[1] <= k.span[0] or e.span[0] >= k.span[1]) for k in kept)

    fp = sorted((e for e in entities if e.redact_type == "FP"), key=_key)
    tb = sorted((e for e in entities if e.redact_type != "FP"), key=_key)
    for e in (*fp, *tb):
        if not _overlaps(e):
            kept.append(e)
    return sorted(kept, key=lambda e: e.span[0])


def _prefer_record_names(
    entities: list[Entity],
    record_names: list[Entity],
) -> list[Entity]:
    """Keep strong record context above a conflicting TB label."""
    kept = list(entities)
    for name in record_names:
        overlaps = [
            entity
            for entity in kept
            if name.span[0] < entity.span[1] and entity.span[0] < name.span[1]
        ]
        if any(entity.redact_type == "FP" for entity in overlaps):
            continue
        # Relabeling a coextensive span is the point; UNCOVERING is not. An overlap reaching
        # outside the record name would lose its tail to a shorter NAME (recall > precision).
        # Guard every data_type, not just NAME.
        if any(
            entity.span[0] < name.span[0] or entity.span[1] > name.span[1] for entity in overlaps
        ):
            continue
        kept = [entity for entity in kept if entity not in overlaps]
        kept.append(name)
    return sorted(kept, key=lambda entity: entity.span[0])


# ── ADDRESS coalescing ─────────────────────────────────────────────────────
# FP address patterns capture components as separate spans; one address became several
# entities (several pseudonyms, several PDF boxes). Merge only CONSECUTIVE entities of the
# full sorted list so a chain can never swallow an intervening NAME. Over-merging is costly:
# on the PDF path every word of a merged span becomes a document-wide redaction fragment.

_MERGE_TYPES = {"ADDRESS", "POSTAL_CODE"}
_STRICT_GAP_RE = re.compile(r"[ , ]{0,3}")
# FP captures VALUES only, so labels live in the gaps. A bridge gap is short, single-line,
# must contain a glue word, digit runs <= 3 (a moo/floor number, never a phone). Cap 25 fits
# a building name (" คอนโดริเวอร์ไซด์ ชั้น " is 23); the veto words keep two-party splits apart.
_BRIDGE_CHARSET_RE = re.compile(r"[ .,ก-๎0-9]{1,25}")
_ADDRESS_GLUE_RE = re.compile(
    r"ตำบล|อำเภอ|จังหวัด|แขวง|เขต|หมู่ที่|หมู่|ซอย|ถนน|ต\.|อ\.|จ\.|ม\."
    r"|อาคาร|หมู่บ้าน|ตึก|ชั้น|ห้อง|คอนโด|ตรอก|แยก|นิคม"
)
_BRIDGE_VETO_RE = re.compile(
    r"บ้านเลขที่|ที่อยู่|เลขที่|ผู้ซื้อ|ผู้ขาย|ผู้กู้|ผู้ค้ำ|ผู้เช่า|ผู้ให้เช่า|ส่งที่|ติดต่อ|นาย|นาง|นางสาว"
)
# A postal code may merge BACKWARD across exactly one bare Thai token (the label-less
# province word ending most addresses, "เขตหลักสี่ กทม 10210"). Worst case is over-masking
# one word before a real postcode, never a new claim. Digits, newlines, veto words still break.
_POSTAL_BACKSTEP_RE = re.compile(r" ?[ก-๎]{2,18} ?")


def _gap_ok(gap: str, prev_type: str, next_type: str) -> bool:
    if _STRICT_GAP_RE.fullmatch(gap):
        return True
    # Bridges continue an ADDRESS, never extend forward from a postal code.
    if prev_type != "ADDRESS":
        return False
    if any(ch in gap for ch in "\n\t\r\v\f"):
        return False
    if not _BRIDGE_CHARSET_RE.fullmatch(gap):
        return False
    if any(len(run) > 3 for run in re.findall(r"\d+", gap)):
        return False
    if _BRIDGE_VETO_RE.search(gap):
        return False
    if _ADDRESS_GLUE_RE.search(gap):
        return True
    return next_type == "POSTAL_CODE" and bool(_POSTAL_BACKSTEP_RE.fullmatch(gap))


def merge_address_spans(text: str, entities: list[Entity]) -> list[Entity]:
    """Coalesce adjacent ADDRESS/POSTAL_CODE entities into single ADDRESS spans.

    Input must be sorted and non-overlapping; output keeps that. A chain merges only
    if it contains an ADDRESS; the merged entity is TB so the anonymizer routes it to
    the Thai address surrogate generator.
    """
    out: list[Entity] = []
    i = 0
    while i < len(entities):
        e = entities[i]
        if e.data_type not in _MERGE_TYPES:
            out.append(e)
            i += 1
            continue
        chain = [e]
        j = i + 1
        while j < len(entities) and entities[j].data_type in _MERGE_TYPES:
            gap = text[chain[-1].span[1] : entities[j].span[0]]
            if not _gap_ok(gap, chain[-1].data_type, entities[j].data_type):
                break
            chain.append(entities[j])
            j += 1
        if len(chain) == 1 or not any(c.data_type == "ADDRESS" for c in chain):
            out.append(e)
            i += 1
            continue
        start, end = chain[0].span[0], chain[-1].span[1]
        out.append(
            Entity(
                entity_id=chain[0].entity_id,
                redact_type="TB",
                data_type="ADDRESS",
                span=(start, end),
                score=max(c.score for c in chain),
                original_text=text[start:end],
            )
        )
        i = j
    return out


def _extend_address_chains(text: str, entities: list[Entity], tb: list[Entity]) -> list[Entity]:
    """Union a retained ADDRESS span with raw TB ADDRESS spans dedupe dropped.

    The wider CRF span is often the only one that saw the label-less tail ("อำเภอเมือง
    ขอนแก่น"). Clamped at neighboring retained entities so a NAME beside the address is
    never swallowed. Re-merged afterwards since an extension can close a POSTAL_CODE gap.
    """
    tb_addr = [t for t in tb if t.data_type == "ADDRESS"]
    if not tb_addr:
        return entities
    ents = sorted(entities, key=lambda e: e.span[0])
    out: list[Entity] = []
    changed = False
    floor = 0  # end of the previous (possibly already extended) entity
    for i, e in enumerate(ents):
        ceiling = ents[i + 1].span[0] if i + 1 < len(ents) else len(text)
        if e.data_type != "ADDRESS":
            out.append(e)
            floor = e.span[1]
            continue
        start, end = e.span
        for t in tb_addr:
            if t.span[0] < end and start < t.span[1]:
                start = min(start, t.span[0])
                end = max(end, t.span[1])
        start = max(start, floor)
        end = min(end, ceiling)
        if (start, end) == e.span:
            out.append(e)
        else:
            changed = True
            out.append(
                Entity(
                    entity_id=e.entity_id,
                    redact_type="TB",
                    data_type="ADDRESS",
                    span=(start, end),
                    score=e.score,
                    original_text=text[start:end],
                )
            )
        floor = end
    if not changed:
        return entities
    return merge_address_spans(text, out)


# An ADDRESS with no number at all. docs/annotation-guidelines.md precedent 3: an address
# is read "from the first locatable component (house number, named soi/road with number, or
# a tambon/amphoe/province chain)", so a span carrying neither a digit nor an admin-area
# word is a vague place mention. Runs POST-merge, so a real address's label-less fragment
# has already been absorbed into a chain that carries the chain's digits; every digit-free
# ADDRESS left on gold-v5 is a measured false positive (ms04 เมือง, lf19 ถนนมิตรภาพ, bz03
# บ้านตามทะเบียนบ้าน) and none of the 58 gold ADDRESS spans is matched by one. RELABELS to
# LOCATION rather than dropping: the characters stay masked, only the claim changes.
_ADMIN_AREA_RE = re.compile(r"ตำบล|อำเภอ|จังหวัด|แขวง|เขต|หมู่|ต\.|อ\.|จ\.|ม\.")


def _relabel_numberless_addresses(entities: list[Entity]) -> list[Entity]:
    out: list[Entity] = []
    for e in entities:
        if (
            e.data_type == "ADDRESS"
            and not any(ch.isdigit() for ch in e.original_text)
            and not _ADMIN_AREA_RE.search(e.original_text)
        ):
            e = Entity(
                entity_id=e.entity_id,
                redact_type=e.redact_type,
                data_type="LOCATION",
                span=e.span,
                score=e.score,
                original_text=e.original_text,
            )
        out.append(e)
    return out


# Bare facility designators (a bookable meeting room) are furniture, not a place tied to a
# person; the CRF emits them as LOCATION. Runs post-merge so a facility word inside a real
# address is already absorbed. Dropping UNMASKS, so absence of evidence is not evidence
# (a bare delivery line "ส่งเอกสารมาที่ อาคาร 7 ชั้น 3" lost its building). Both required:
# positive register vocabulary in the window (facility spans blanked so they cannot vouch
# for themselves) AND no retained non-facility entity nearby (siblings never anchor each other).
_FACILITY_SPAN_RE = re.compile(r"(?:ห้องประชุม|ห้องเรียน|ห้อง|อาคาร|ตึก|ชั้น)\s*\d+")
_FACILITY_ANCHOR_WINDOW = 80
# Bare สอบ deliberately absent (substring of ตรวจสอบ/สอบถาม); exam-room forms spelled out.
_FACILITY_REGISTER_RE = re.compile(
    r"ความจุ|ที่นั่ง|จอง|ประชุม|อบรม|สัมมนา|บรรยาย|ห้องสอบ|สนามสอบ|ตารางสอบ|ผู้เข้าสอบ"
)


def _drop_unanchored_facility_spans(text: str, entities: list[Entity]) -> list[Entity]:
    facility = {
        i
        for i, e in enumerate(entities)
        if e.data_type == "LOCATION" and _FACILITY_SPAN_RE.fullmatch(text[e.span[0] : e.span[1]])
    }
    if not facility:
        return entities
    # Blank the facility spans so they are not their own register evidence.
    masked = list(text)
    for i in facility:
        for pos in range(*entities[i].span):
            masked[pos] = " "
    masked_text = "".join(masked)
    anchors = [e for i, e in enumerate(entities) if i not in facility]
    drop = set()
    for i in facility:
        s, t = entities[i].span
        lo = max(0, s - _FACILITY_ANCHOR_WINDOW)
        hi = min(len(text), t + _FACILITY_ANCHOR_WINDOW)
        if not _FACILITY_REGISTER_RE.search(masked_text[lo:hi]):
            continue
        if not any(a.span[0] < hi and lo < a.span[1] for a in anchors):
            drop.add(i)
    if not drop:
        return entities
    return [e for i, e in enumerate(entities) if i not in drop]


def _relabel_student_ids(tb: list[Entity], kept: list[Entity]) -> list[Entity]:
    """Give a TB STUDENT_ID span its honest label past the FP-first dedupe.

    FP-first dedupe keeps the generic ID_NUMBER over a TB STUDENT_ID on the same
    digits; only the label (and surrogate) changes, never the masked span.
    """
    student_spans = {e.span for e in tb if e.data_type == "STUDENT_ID"}
    if not student_spans:
        return kept
    out = []
    for e in kept:
        if e.data_type == "ID_NUMBER" and e.span in student_spans:
            e = Entity(
                entity_id=e.entity_id,
                redact_type=e.redact_type,
                data_type="STUDENT_ID",
                span=e.span,
                score=e.score,
                original_text=e.original_text,
            )
        out.append(e)
    return out


def detect_all(
    text: str,
    *,
    ner_diagnostics: NERChunkDiagnostics | None = None,
) -> list[Entity]:
    """Run the full detection ensemble and return deduped entities."""
    fp = detect_fp(text)
    if ner_diagnostics is None:
        tb = detect_tb(text)
    else:
        tb = detect_tb(text, diagnostics=ner_diagnostics)
    fn = scan_fn(text, fp + tb)
    record_names = detect_parallel_record_names(text, fp + tb + fn)
    deduped = dedupe_spans(fp + tb + fn + record_names)
    kept = merge_address_spans(text, _prefer_record_names(deduped, record_names))
    kept = _extend_address_chains(text, kept, tb)
    kept = _relabel_numberless_addresses(kept)
    kept = _drop_unanchored_facility_spans(text, kept)
    kept = _relabel_student_ids(tb, kept)
    # ม.26 spans deliberately do NOT go through dedupe_spans: that keeps the existing
    # ensemble's output untouched up to the final merge.
    sensitive = detect_sensitive_spans(
        text,
        [e.span for e in kept if e.data_type in ("NAME", "SURNAME")],
        blocked_spans=[e.span for e in kept if e.redact_type == "FP"],
    )
    return merge_sensitive_spans(text, kept, sensitive)

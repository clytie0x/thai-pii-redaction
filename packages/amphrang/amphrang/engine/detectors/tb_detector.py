"""Text-based (TB) PII detector using PyThaiNLP NER (thainer CRF by default;
WangchanBERTa opt-in via AMPHRANG_NER_ENGINE)."""

from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass

from pythainlp import sent_tokenize
from pythainlp.tag import NER

from amphrang.engine.detectors.ner_failure import NERFailureError, ner_failure_metadata
from amphrang.engine.models import Entity
from amphrang.engine.safe_errors import discard_exception_graph

_LOG = logging.getLogger(__name__)


@dataclass
class NERChunkDiagnostics:
    attempted: int = 0
    succeeded: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "skipped": self.skipped,
        }


# Label mapping: thainer labels -> PDPA data_type (None = skip)

LABEL_MAP: dict[str, str | None] = {
    "PERSON": "NAME",
    # AI for Thai TNER uses these compact labels on the live API.
    "PER": "NAME",
    "ORGANIZATION": "ORGANIZATION",  # quasi-identifier (employer/hospital)
    "LOCATION": "LOCATION",  # upgraded to ADDRESS by cue (below)
    "DATE": "DATE",  # upgraded to DATE_OF_BIRTH by cue (below)
    "DTM": "DATE",
    "TIME": None,
    "MONEY": None,
    "PERCENT": None,
    "FACILITY": None,
    "PRODUCT": None,
    # Aliases from brief (kept for safety)
    "ORG": "ORGANIZATION",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
}

# Cue-based upgrades (cue-window like fp_detector; regexes copied, not imported, to avoid a
# circular import). The ADDRESS check includes the span itself (cues sit inside address text);
# the DOB check uses the preceding context plus the span's non-digit head (the CRF absorbs a
# glued cue into the DATE span). `เลขที่` lookahead: เลขที่บัญชี/เลขที่สัญญา... mean "number of
# <thing>", not an address — without it an account-number label became a fake street address
# and the pre-send guard halted clean prompts. บ้านเลขที่ must be tried before เลขที่.
_ADDR_CUE_RE = re.compile(
    r"ที่อยู่|บ้านเลขที่|อาศัยอยู่|พักอยู่"
    r"|เลขที่(?!บัญชี|ใบ|สัญญา|เอกสาร|คำสั่ง|กรมธรรม์|พัสดุ|คดี|หนังสือ|บัตร)"
    r"|ซอย|ถนน|ตำบล|แขวง|อำเภอ|เขต|จังหวัด"
)
# Copy of fp_detector._BIRTH_CUE_RE by design: เกิดเหตุ/เหตุเกิด never introduce a birth date;
# the English labels are a real register on Thai visa/passport paperwork.
_TB_BIRTH_CUE_RE = re.compile(r"(?<!เหตุ)เกิด(?!เหตุ)|date of birth|\bd\.?o\.?b\b", re.IGNORECASE)
_TB_CUE_WINDOW = 30

# thainer CRF forces a non-O label onto out-of-distribution (non-Thai) input rather than
# abstaining; ORGANIZATION has no cue gate of its own, so an all-Latin "organization" span is
# always that degenerate guess -- reject it.
_THAI_CHAR_RE = re.compile(r"[฀-๿]")
_ISOLATED_NAME_LINE_RE = re.compile(r"[ก-ฮเ-ไ][ก-ฮะ-์]*(?:[ \t]+[ก-ฮเ-ไ][ก-ฮะ-์]*){1,3}")
# A one-run Thai line is admitted to the retry only via `name_context.is_glued_name_run` (OCR
# deletes the space inside a name). Relaxing the regex above to {0,3} instead would spend the
# _ISOLATED_NAME_MAX_LINES budget on single-word form headers before reaching a real name.
_ISOLATED_GLUED_LINE_RE = re.compile(r"[ก-ฮเ-ไ][ก-ฮะ-์]*")
# Thai-letter words separated by single spaces/tabs and nothing else: excludes digit runs and a
# glued non-name prefix like an OCR-corrupted "และ..." co-applicant marker -- the parallel-record
# bootstrap (name_context.detect_parallel_record_names) extracts that bare name and must win
# dedupe over a hygiene segment that also grabbed the prefix.
_NAME_SEGMENT_SHAPE_RE = re.compile(r"^[ก-ฮเ-ไ][ก-ฮะ-์]*(?:[ \t]+[ก-ฮเ-ไ][ก-ฮะ-์]*)*$")
_ISOLATED_NAME_PREFIX_RE = re.compile(r"(?:ชื่อ(?:-นามสกุล)?|ผู้[ก-๛]{1,30})[ \t:：]+")
_ISOLATED_NAME_MAX_CHARS = 80
_ISOLATED_NAME_MAX_LINES = 8
# Document/form compounds the CRF hallucinates as PERSON. Anchored at span start; each entry is
# a compound so real given names sharing a prefix (เลขา, ใบเฟิร์น, ประกาศิต, นิคม) survive.
_NAME_CUE_AFTER_BREAK_RE = re.compile(r"(?:[ก-๛]{0,12}ชื่อ|นาย|นางสาว|นาง|ด\.ช\.|ด\.ญ\.)")
_NAME_DOC_COMPOUND_RE = re.compile(
    r"ตารางสอบ|ตารางเรียน|ตารางนัด|รายงานการ|สถานีตำรวจ|ประวัติการ|นิคมอุตสาหกรรม"
    r"|เลขครุภัณฑ์|เลขที่|เลขเอกสาร|ใบสมัคร|ใบคำร้อง|ใบเสร็จ|ใบกำกับ|ใบแจ้ง"
    r"|บันทึกข้อความ|ประกาศรายชื่อ|ประกาศผล|กำหนดการ|ระเบียบวาระ"
    # Document-title heads (measured gold false positives). Compounds only: bare แบบ and bare
    # สัญญา are real given names (แบบบุญมี, สัญญา ธรรมศักดิ์) and must stay out.
    r"|รายชื่อ|แบบประเมิน|สัญญาเช่า|สัญญาจ้าง|ขอขอบคุณ|ขอบคุณ"
    # Form labels glued to real names in label-first OCR order: "เดือนปีเกิด" is a field, not a
    # person. Used with .match(), so the full spelling "วันเดือนปีเกิด" needs its own alternative
    # (it leaked as a NAME without one). Longer alternative first.
    r"|วันเดือนปีเกิด|เดือนปีเกิด"
)
# Punctuation an OCR line break leaves hanging on a name ("สมชาย ใจดี,"): TRIMMED from a tail
# segment rather than failing the shape gate. Deliberately narrow: clause-ending chars only.
_NAME_SEGMENT_TRIM_CHARS = ",.;:!?)]}\"'"
# A digit run inside a NAME span is junk the CRF glued on (e.g. a trailing account number);
# aggregate.dedupe_spans then dropped the WHOLE span for overlapping the FP BANK_ACCOUNT and
# unmasked the name. The HEAD segment is truncated at its first digit run (Thai names never
# contain digits, so no name text is lost); tail segments keep their wholesale shape rejection
# instead — see the loop below.
_NAME_DIGIT_RUN_RE = re.compile(r"[0-9][0-9\s./-]*")
# น.ส. followed IMMEDIATELY by a digit is the land-document class, never the person title
# น.ส. Two different กรมที่ดิน series share the shape: น.ส.3 / น.ส.3ก / น.ส.3ข are the
# หนังสือรับรองการทำประโยชน์, while the น.ส.4 series (…ก ข ค ง จ) is the โฉนดที่ดิน title deed
# itself — น.ส.4จ is the current ครุฑแดง โฉนด. Checked before the digit-run
# split, which otherwise mints two names from one abbreviation (head "น.ส." plus whatever the
# tail rule accepts after the digits, gold dg18 "ก เดิม"). A letter after the dot is the real
# title (น.ส.สมศรี) and never reaches this regex.
_LAND_DOC_ABBREV_RE = re.compile(r"น\.ส\.\d")


# A CRF "location" that is really document numbering: the span IS a เลขที่<document> field
# label (same compound list the ADDRESS cue refuses to upgrade on), or it carries digits plus a
# Buddhist year with no Thai letter RUN ("จ.44/2569"). The year requirement keeps a bare house
# number ("214/9" — emitted as its own LOCATION span, absolutely PII) alive; a real place with
# a digit ("เชียงใหม่ 50200") keeps its Thai run. บัตร: เลขที่บัตรประชาชน/เลขที่บัตรเครดิต are
# card-number labels, never addresses; the card digits keep their own checksum detectors.
_DOC_NUMBER_LABEL_RE = re.compile(r"เลขที่(?:บัญชี|ใบ|สัญญา|เอกสาร|คำสั่ง|กรมธรรม์|พัสดุ|คดี|หนังสือ|บัตร)")
_THAI_RUN_RE = re.compile(r"[ก-๛]{2,}")
_BUDDHIST_YEAR_RE = re.compile(r"(?<!\d)2[456]\d{2}(?!\d)")
# A "date" right after มอก. is the standard's number ("มอก. 2540-2555"), not a calendar date.
# The left boundary keeps words ending in the same letters (ทะเลหมอก) from swallowing a date.
_STANDARD_CUE_RE = re.compile(r"(?<![ก-๛])มอก\.?\s*$")
_STANDARD_CUE_LOOKBACK = 10
# No calendar date has five digits in a row — such a run means the CRF swallowed a
# serial/reference number into the span ("ISSN 08571724 เผยแพร่เดือนกันยายน 2568").
_DATE_SERIAL_RE = re.compile(r"\d{5,}")
# An "organization" opening with the fee-compound head ค่า+noun (ค่าธรรมเนียม/ค่าบริการ) is a
# price-list label, never a name; in surrogate mode it became a fake org name. The ย lookahead
# protects camp orgs (ค่ายอาสาพัฒนาชนบท). Used with .match(), anchored at span start.
_FEE_COMPOUND_RE = re.compile(r"ค่า(?!ย)")
# Organization leads that make a ค่า-prefixed span a real org name. Same closed vocabulary as
# name_context's _NON_PERSON_LEADS, kept literal here to avoid a circular import.
_ORG_LEAD_IN_SPAN_RE = re.compile(
    r"บริษัท|ห้าง|ธนาคาร|โรงพยาบาล|มหาวิทยาลัย|โรงเรียน|สำนักงาน|โรงงาน|มูลนิธิ|สมาคม|สหกรณ์"
)


def _apply_cue_upgrades(text: str, start: int, end: int, data_type: str) -> str | None:
    """Cue-driven label upgrade, or ``None`` when the span is no PII at all."""
    if data_type == "ORGANIZATION":
        entity_text = text[start:end]
        if _FEE_COMPOUND_RE.match(entity_text) and not _ORG_LEAD_IN_SPAN_RE.search(entity_text):
            # A fee word glued in front of a real org ("ค่าจ้างบริษัท เอบีซี จำกัด") is still an
            # organization span; only the bare price-list label is dropped.
            return None
    elif data_type == "LOCATION":
        entity_text = text[start:end]
        if _DOC_NUMBER_LABEL_RE.match(entity_text):
            return None
        if _BUDDHIST_YEAR_RE.search(entity_text) and not _THAI_RUN_RE.search(entity_text):
            return None
        ctx = text[max(0, start - _TB_CUE_WINDOW) : end]
        if _ADDR_CUE_RE.search(ctx):
            return "ADDRESS"
    elif data_type == "DATE":
        if _STANDARD_CUE_RE.search(text[max(0, start - _STANDARD_CUE_LOOKBACK) : start]):
            return None
        if _DATE_SERIAL_RE.search(text[start:end]):
            return None
        # Preceding window PLUS the span's non-digit head: the CRF absorbs a glued cue into the
        # span; the head is contiguous original text, so the lookarounds still see across the
        # join. A clean date span has an empty head and is unaffected.
        span_text = text[start:end]
        first_digit = re.search(r"\d", span_text)
        head = span_text[: first_digit.start()] if first_digit else span_text
        ctx = text[max(0, start - _TB_CUE_WINDOW) : start] + head
        if _TB_BIRTH_CUE_RE.search(ctx):
            return "DATE_OF_BIRTH"
    return data_type


def _spaceless_run_is_not_a_name(segment: str) -> bool:
    """True when a space-free Thai NAME segment is a form label, not a person.

    A space-free Thai run the CRF called PERSON carries no space evidence at all, so it
    is judged by the two facts that hold for every name: it is at most
    `_GLUED_NAME_MAX_CHARS` long (gold's longest NAME value of any shape is 24 chars;
    its longest SPACELESS one is 9), and it does not open with a form-label token
    (`is_non_person_segment`, the same gate tail segments already pass).

    Rejects gold-v5 bz07 (เลขผู้เสียภาษี -- label token), bz17 and bz19 (27- and 36-char
    document-title lines). Keeps all three spaceless TRUE positives (nc12 ทิพย์มณี /
    fn03 วรากร / lf02 อริยะสกุล) and a plain dictionary-word given name (มานพ), which is
    why the multi-token `is_glued_name_run` test is NOT used here: it answers "did OCR
    delete a space", not "is this a name". Latin and mixed-script runs are left alone.
    """
    from amphrang.engine.detectors.name_context import (
        _GLUED_NAME_MAX_CHARS,
        is_non_person_segment,
    )

    if not _ISOLATED_GLUED_LINE_RE.fullmatch(segment):
        return False
    return len(segment) > _GLUED_NAME_MAX_CHARS or is_non_person_segment(segment)


def _name_hygiene(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Shared NAME span hygiene for every neural engine (CRF and fine-tuned).

    A person's name never spans a line break or contains a digit run, and on label-first OCR
    order the CRF glues a form label to the name(s) after it into one span -- so the span is
    split into segments, judged by deliberately different rules because the evidence differs:

    - HEAD (what the CRF actually started on) keeps the lenient rule: >= 2 chars after rstrip
      and not a document compound. A strict name shape here dropped real names for a trailing
      comma, a parenthesised role, an age, or Latin script ("สมชาย ใจดี," / "John Smith").
    - TAIL segments carry no such evidence: they must match `_NAME_SEGMENT_SHAPE_RE` (after
      trailing clause punctuation is TRIMMED, not counted against them) AND survive
      `name_context.is_non_person_segment` plus the document-compound regex, which keeps form
      labels (ที่อยู่, ตำแหน่ง) and letter closings (ขอแสดงความนับถือ) from becoming NAMEs.

    Exception: if the line right after the first break opens with a name cue (นาย/นาง/ชื่อ/...),
    the cue pass owns the person and the WHOLE span is dropped. Same-line spans and the head
    also get `name_context.trim_same_line_name_edges` (leading role word, trailing field-label
    group; whole-token evidence only, and only while two name groups remain).
    """
    from amphrang.engine.detectors.name_context import (
        is_non_person_segment,
        trim_same_line_name_edges,
    )

    def _tail_segment(line: str, line_start: int) -> tuple[int, int] | None:
        lstripped = line.lstrip()
        pad = len(line) - len(lstripped)
        seg = lstripped.rstrip().rstrip(_NAME_SEGMENT_TRIM_CHARS).rstrip()
        if len(seg) < 2:
            return None
        if _NAME_DOC_COMPOUND_RE.match(seg):
            return None
        if not _NAME_SEGMENT_SHAPE_RE.match(seg):
            return None
        if is_non_person_segment(seg):
            return None
        seg_start = line_start + pad
        return (seg_start, seg_start + len(seg))

    entity_text = text[start:end]
    if "\n" not in entity_text and not _NAME_DIGIT_RUN_RE.search(entity_text):
        compound = _NAME_DOC_COMPOUND_RE.match(entity_text)
        if compound:
            # A document compound at the head does NOT make the whole span a header: the CRF
            # glues one onto a real name ("รายชื่อ สมชาย ใจดี") and dropping it unmasked the name.
            # The compound must END the word (a glued compound is one longer header phrase,
            # "รายชื่อนักศึกษาฝึกงาน", still dropped); what follows passes the strict tail gate
            # plus a two-group floor.
            rest = entity_text[compound.end() :]
            if not rest[:1].isspace():
                return []
            seg = _tail_segment(rest, start + compound.end())
            if seg is None or " " not in text[seg[0] : seg[1]]:
                return []
            return [seg]
        t_lo, t_hi = trim_same_line_name_edges(entity_text)
        if t_hi - t_lo < 2 or _NAME_DOC_COMPOUND_RE.match(entity_text[t_lo:t_hi]):
            return []
        if _spaceless_run_is_not_a_name(entity_text[t_lo:t_hi]):
            return []
        return [(start + t_lo, start + t_hi)]

    if "\n" in entity_text:
        _head, tail = entity_text.split("\n", 1)
        if _NAME_CUE_AFTER_BREAK_RE.match(tail.lstrip()):
            return []

    spans: list[tuple[int, int]] = []
    offset = 0
    for index, line in enumerate(entity_text.split("\n")):
        line_start = start + offset
        offset += len(line) + 1
        if index == 0:
            # A land-document abbreviation owns the whole head line: drop it before the digit
            # split so neither the truncated head nor the after-digits tail becomes a NAME.
            if _LAND_DOC_ABBREV_RE.match(line.lstrip()):
                continue
            # HEAD only: split at the first digit run (tail lines keep wholesale shape rejection;
            # truncating them would mint "วันที่" from "วันที่ 1 สิงหาคม"). BOTH sides are judged:
            # prefix-only dropped numbered roster lines ("1. สมชาย ใจดี"); the part AFTER the
            # digits has no start-of-span evidence, so it goes through the strict TAIL gate.
            digits = _NAME_DIGIT_RUN_RE.search(line)
            head = line[: digits.start()] if digits else line
            if digits:
                got = _tail_segment(line[digits.end() :], line_start + digits.end())
                if got:
                    spans.append(got)
            seg = head.rstrip()
            if len(seg) < 2 or _NAME_DOC_COMPOUND_RE.match(seg):
                continue
            # Same-line edge trim, re-checking the compound gate: a trim can expose a document
            # compound the role word was glued in front of.
            t_lo, t_hi = trim_same_line_name_edges(seg)
            if t_hi - t_lo < 2 or _NAME_DOC_COMPOUND_RE.match(seg[t_lo:t_hi]):
                continue
            if _spaceless_run_is_not_a_name(seg[t_lo:t_hi]):
                continue
            spans.append((line_start + t_lo, line_start + t_hi))
            continue
        got = _tail_segment(line, line_start)
        if got:
            spans.append(got)
    return sorted(spans)


_FINETUNED_LABEL_MAP = {
    "PERSON": "NAME",
    "LOCATION": "LOCATION",
    "ORGANIZATION": "ORGANIZATION",
    "DATE": "DATE",
    "STUDENT_ID": "STUDENT_ID",
}
_finetuned_cache: dict[str, object] = {}


def _detect_tb_finetuned(text: str) -> list[Entity]:
    """TB detection under the fine-tuned engine (AMPHRANG_NER_ENGINE=finetuned).

    Model spans arrive as character offsets (no BIO reconstruction) and get the same hygiene
    and cue-upgrade layers. The extended name-cue passes are kept only when they OVERLAP a
    model PERSON span (model-as-verifier) because they measurably cost precision in registers
    gold does not cover; the strong passes (titles, explicit labels) stay unconditional.
    """
    from amphrang.engine.detectors.finetuned_engine import FinetunedEngine
    from amphrang.engine.detectors.name_context import detect_name_context_passes

    if "engine" not in _finetuned_cache:
        _finetuned_cache["engine"] = FinetunedEngine()
    engine = _finetuned_cache["engine"]

    thresholds = getattr(engine, "thresholds", {}) or {}
    candidates: list[Entity] = []
    model_name_spans: list[tuple[int, int]] = []
    for start, end, label, conf in engine.spans(text):
        data_type = _FINETUNED_LABEL_MAP.get(label)
        if data_type is None or end - start < 2:
            continue
        if conf < thresholds.get(label, 0.0):
            continue
        entity_text = text[start:end]
        if data_type == "ORGANIZATION" and not _THAI_CHAR_RE.search(entity_text):
            continue
        if data_type == "NAME":
            segments = _name_hygiene(text, start, end)
            for seg_start, seg_end in segments:
                model_name_spans.append((seg_start, seg_end))
                seg_data_type = _apply_cue_upgrades(text, seg_start, seg_end, data_type)
                if seg_data_type is None:
                    continue
                candidates.append(
                    Entity(
                        entity_id=str(uuid.uuid4()),
                        redact_type="TB",
                        data_type=seg_data_type,
                        span=(seg_start, seg_end),
                        score=round(min(0.99, max(0.5, conf)), 3),
                        original_text=text[seg_start:seg_end],
                    )
                )
            continue
        data_type = _apply_cue_upgrades(text, start, end, data_type)
        if data_type is None:
            continue
        candidates.append(
            Entity(
                entity_id=str(uuid.uuid4()),
                redact_type="TB",
                data_type=data_type,
                span=(start, end),
                score=round(min(0.99, max(0.5, conf)), 3),
                original_text=text[start:end],
            )
        )

    cue_kept: list[Entity] = []
    for pass_name, e in detect_name_context_passes(text):
        if pass_name == "strong" or any(
            e.span[0] < me and ms < e.span[1] for ms, me in model_name_spans
        ):
            cue_kept.append(e)
    # A verified cue span carries the full name boundary; drop a model NAME span it contains so
    # dedupe cannot prefer the clipped span and leak the surname.
    if cue_kept:
        contained = {
            id(c)
            for c in candidates
            if c.data_type == "NAME"
            and any(k.span[0] <= c.span[0] and c.span[1] <= k.span[1] for k in cue_kept)
        }
        candidates = [c for c in candidates if id(c) not in contained]
    return _deduplicate(candidates + cue_kept)


class NEREngineUnavailableError(RuntimeError):
    """AMPHRANG_NER_ENGINE is set to an engine whose dependency isn't installed."""


def _raise_explicit_ner_failure(
    error: Exception,
    *,
    default_category: str,
    default_count: int,
) -> None:
    """Drop an explicit-engine failure graph and raise fixed metadata only."""

    if isinstance(error, NERFailureError):
        code, category, count = ner_failure_metadata(error)
    else:
        code = "ner_unavailable"
        category = default_category
        count = default_count
    discard_exception_graph(error)
    raise NERFailureError(code, category=category, count=count) from None


# Curated allow-list: only engines verified to emit the (word, "B-"/"I-"/"O"-tag) shape that
# _bio_to_spans() decodes. Do NOT add thai-nner or tltk without verifying their .tag() shape --
# they are known to differ (nested entities / different tuple layout).
_ENGINE_CONFIG: dict[str, dict[str, str | None]] = {
    "thainer": {"ner_engine": "thainer", "requires": None},
    "wangchanberta": {"ner_engine": "thainer-v2", "requires": "transformers"},
}

# Lazy NER cache keyed by engine name; a dict so `union` can hold both engines.
_ner_cache: dict[str, NER] = {}


def _load_ner(name: str) -> NER:
    """Return the cached NER engine for one engine name, loading it on first use. Raises
    ValueError for an unknown name, NEREngineUnavailableError for a missing dependency."""
    if name not in _ENGINE_CONFIG:
        raise ValueError(
            f"Unknown AMPHRANG_NER_ENGINE={name!r}; supported: {sorted(_ENGINE_CONFIG)} (or 'union')"
        )
    if name not in _ner_cache:
        config = _ENGINE_CONFIG[name]
        requires = config["requires"]
        if requires is not None:
            try:
                __import__(requires)
            except ImportError:
                raise NEREngineUnavailableError(
                    f"AMPHRANG_NER_ENGINE={name!r} requires {requires!r}. "
                    f'Run: pip install "amphrang[ml]"'
                ) from None
        _ner_cache[name] = NER(engine=config["ner_engine"])
    return _ner_cache[name]


def _resolve_engine_name() -> str:
    """The engine named by AMPHRANG_NER_ENGINE, defaulting to the offline CRF. The default is
    load-bearing: detection is claimed offline, true only while network engines stay opt-in."""
    return os.environ.get("AMPHRANG_NER_ENGINE", "thainer")


def _get_ner() -> NER:
    """Select the single engine named by AMPHRANG_NER_ENGINE (default thainer)."""
    return _load_ner(_resolve_engine_name())


# BIO tag decoding


def _bio_to_spans(tokens: list[tuple[str, str]], text: str) -> list[tuple[str, int, int, str]]:
    """Convert BIO-tagged tokens to (entity_text, start, end, label) spans with char offsets."""
    spans: list[tuple[str, int, int, str]] = []
    current_label: str | None = None
    current_start: int | None = None
    current_end: int | None = None
    pos = 0

    for word, tag in tokens:
        idx = text.find(word, pos)
        if idx == -1:
            continue
        token_end = idx + len(word)

        # Live TNER emits separators as whitespace tokens with a blank tag; keep them
        # transparent so a following I-tag extends the same span without losing the gap.
        if not word.strip() and not tag.strip():
            pos = token_end
            continue

        if tag.startswith("B-"):
            if current_label and current_start is not None and current_end is not None:
                spans.append(
                    (
                        text[current_start:current_end],
                        current_start,
                        current_end,
                        current_label,
                    )
                )
            current_label = tag[2:]
            current_start = idx
            current_end = token_end
        elif tag.startswith("I-") and current_label == tag[2:]:
            # Source positions preserve an internal separator the tokenizer omitted.
            current_end = token_end
        else:
            if current_label and current_start is not None and current_end is not None:
                spans.append(
                    (
                        text[current_start:current_end],
                        current_start,
                        current_end,
                        current_label,
                    )
                )
            current_label = None
            current_start = None
            current_end = None

        pos = token_end

    if current_label and current_start is not None and current_end is not None:
        spans.append(
            (
                text[current_start:current_end],
                current_start,
                current_end,
                current_label,
            )
        )

    return spans


# Deduplication (copied from fp_detector to avoid circular import)


def _covered_by_kept(span: tuple[int, int], kept: list[Entity]) -> bool:
    """True when every character of ``span`` lies inside kept spans."""
    lo, hi = span
    cur = lo
    for s, e in sorted(k.span for k in kept if k.span[0] < hi and k.span[1] > lo):
        if s > cur:
            return False
        cur = max(cur, e)
    return cur >= hi


def _deduplicate(entities: list[Entity]) -> list[Entity]:
    """Remove redundant spans: higher score wins, then earlier start.

    Score-first (same key as fp_detector and name_context's contract) lets a cue span with the
    exact boundary beat the CRF span that glued a role word on. But the CRF can emit ONE wide
    span over TWO people while a cue span covers only the first at higher score, and plain
    score-first eviction unmasked the second person — so a candidate is dropped only when its
    characters are FULLY covered by spans already kept (eviction never reduces coverage). The
    surviving overlap is resolved by `aggregate.dedupe_spans` start-first-then-longer, so the
    wide span wins downstream and nothing is unmasked."""
    sorted_ents = sorted(entities, key=lambda e: (-e.score, e.span[0]))
    kept: list[Entity] = []
    for ent in sorted_ents:
        if (ent.span[1] - ent.span[0]) < 2:
            continue
        if not _covered_by_kept(ent.span, kept):
            kept.append(ent)
    return sorted(kept, key=lambda e: e.span[0])


# Stride-chunk NER (single engine)

_CHUNK_CORE_CHARS = 500

# Degenerate-chunk guard (gov-form OCR): on noisy input the CRF sometimes returns a SINGLE span
# covering nearly the whole chunk instead of abstaining, and when its label maps to None the
# chunk silently yields zero entities. Two shapes: LABEL_MAP.get(label) is None (true both for
# a label missing from LABEL_MAP, like "LAW", AND for one explicitly mapped to None, like MONEY
# -- `label not in LABEL_MAP` would miss the second) or a mapped label swallowing several lines.
_DEGENERATE_COVERAGE_RATIO = 0.8
_DEGENERATE_MIN_LINES = 3


def _finalize_tb_candidate(text: str, orig_start: int, orig_end: int, label: str) -> list[Entity]:
    """Apply LABEL_MAP -> hygiene -> cue-upgrade to one decoded BIO span; returns zero, one or
    several Entities. Shared by the per-chunk loop and the degenerate-chunk fallback so both
    paths accept/reject identically."""
    data_type = LABEL_MAP.get(label)
    if data_type is None:
        return []
    if (orig_end - orig_start) < 2:
        return []
    entity_text = text[orig_start:orig_end]
    if data_type == "ORGANIZATION" and not _THAI_CHAR_RE.search(entity_text):
        return []
    # NAME hygiene: split at line breaks into segments (see `_name_hygiene`) rather than trim to
    # the head -- trimming alone kept a glued form label as a false-positive NAME.
    if data_type == "NAME":
        segments = _name_hygiene(text, orig_start, orig_end)
    else:
        segments = [(orig_start, orig_end)]
    entities: list[Entity] = []
    for seg_start, seg_end in segments:
        seg_data_type = _apply_cue_upgrades(text, seg_start, seg_end, data_type)
        if seg_data_type is None:
            continue
        entities.append(
            Entity(
                entity_id=str(uuid.uuid4()),
                redact_type="TB",
                data_type=seg_data_type,
                span=(seg_start, seg_end),
                score=0.85,
                original_text=text[seg_start:seg_end],
            )
        )
    return entities


def _retag_degenerate_chunk(
    text: str,
    ner: NER,
    core_begin: int,
    core_end: int,
    *,
    fail_closed: bool = False,
) -> list[Entity]:
    """Re-tag a degenerate chunk's core one physical line at a time.

    The whole-chunk call is not retried -- it produced the bad guess. Isolating each line
    removes the noisy neighbours; verified on คร.1 OCR text, the CRF tags a name correctly only
    once its line is presented alone.
    """
    candidates: list[Entity] = []
    core_text = text[core_begin:core_end]
    offset = 0
    for raw_line in core_text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        if line.strip():
            line_start = core_begin + offset
            try:
                tagged_line = ner.tag(line)
            except Exception as exc:
                if fail_closed:
                    _raise_explicit_ner_failure(
                        exc,
                        default_category="dependency",
                        default_count=1,
                    )
                _LOG.warning(
                    "NER tagging failed on degenerate-chunk line at char %d (%d chars; %s); "
                    "skipping — PII on this line may be missed",
                    line_start,
                    len(line),
                    type(exc).__name__,
                )
                tagged_line = []
            for ent_text, ls, le, label in _bio_to_spans(tagged_line, line):
                candidates.extend(
                    _finalize_tb_candidate(text, line_start + ls, line_start + le, label)
                )
        offset += len(raw_line)
    return candidates


def _retag_unknown_label_span(
    text: str,
    ner: NER,
    start: int,
    end: int,
    *,
    fail_closed: bool = False,
) -> list[Entity]:
    """Re-tag an unknown-label multi-line span's physical lines individually.

    A label absent from LABEL_MAP (the CRF's LAW-class confusion — unlike MONEY/TIME, which map
    to None deliberately) that crosses a newline has swallowed form lines the model tags fine
    alone (a DOB was silently dropped with the bogus span); the degenerate-chunk guard cannot
    catch it because these sit among other decoded spans. Lines are expanded to full physical
    lines, and retagged NAME candidates are gated through `is_non_person_segment` — the retag
    context is exactly where the CRF hallucinates PERSON on field labels ("เลขบัตรประชาชน").
    """
    from amphrang.engine.detectors.name_context import is_non_person_segment

    line_begin = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    return [
        e
        for e in _retag_degenerate_chunk(
            text,
            ner,
            line_begin,
            line_end,
            fail_closed=fail_closed,
        )
        if e.data_type != "NAME" or not is_non_person_segment(text[e.span[0] : e.span[1]])
    ]


def _ner_candidates(
    text: str,
    ner: NER,
    sentence_offsets: list[tuple[str, int]],
    margin_sentences: int,
    diagnostics: NERChunkDiagnostics | None = None,
    *,
    fail_closed: bool = False,
) -> list[Entity]:
    """Run one NER engine over stride chunks and return TB Entity candidates at original-text
    offsets (pre-dedup).

    Chunks are consecutive sentences capped at ~_CHUNK_CORE_CHARS (always >= 1 sentence), padded
    with `margin_sentences` of context each side. The tagged string is ALWAYS a slice of the
    original text (joining sentence strings would drop the gaps and corrupt every later offset).
    Only spans that START inside the core are kept, so margins never duplicate entities.
    """
    n = len(sentence_offsets)
    candidates: list[Entity] = []

    def _sent_start(i: int) -> int:
        return sentence_offsets[i][1]

    def _sent_end(i: int) -> int:
        s, off = sentence_offsets[i]
        return off + len(s)

    chunk_first = 0
    while chunk_first < n:
        # grow the core until the char cap (always >= 1 sentence)
        chunk_last = chunk_first
        while (
            chunk_last + 1 < n
            and _sent_end(chunk_last + 1) - _sent_start(chunk_first) <= _CHUNK_CORE_CHARS
        ):
            chunk_last += 1

        core_begin = _sent_start(chunk_first)
        core_end = _sent_end(chunk_last)
        ctx_begin = _sent_start(max(0, chunk_first - margin_sentences))
        ctx_end = _sent_end(min(n - 1, chunk_last + margin_sentences))
        context_text = text[ctx_begin:ctx_end]

        if diagnostics is not None:
            diagnostics.attempted += 1
        try:
            tagged: list[tuple[str, str]] = ner.tag(context_text)
        except Exception as exc:
            # Dropping a whole chunk is recall-negative; never silence it. Offsets and the
            # exception class are safe; the message and traceback are NOT logged because they
            # can embed the input text.
            if diagnostics is not None:
                diagnostics.skipped += 1
            if fail_closed:
                _raise_explicit_ner_failure(
                    exc,
                    default_category="dependency",
                    default_count=1,
                )
            _LOG.warning(
                "NER tagging failed on chunk chars %d-%d (%d chars; %s); "
                "skipping — PII in this chunk may be missed",
                core_begin,
                core_end,
                len(context_text),
                type(exc).__name__,
            )
            chunk_first = chunk_last + 1
            continue
        if diagnostics is not None:
            diagnostics.succeeded += 1

        if tagged:
            bio_spans = _bio_to_spans(tagged, context_text)

            # Degenerate-chunk guard: a SINGLE span covering most of the core is a bogus unmapped
            # label or a mapped label that swallowed several lines; letting it fall through
            # would drop every real entity the model could find on this chunk's lines.
            if len(bio_spans) == 1:
                _ent_text, sp_ctx_start, sp_ctx_end, sp_label = bio_spans[0]
                sp_start = ctx_begin + sp_ctx_start
                sp_end = ctx_begin + sp_ctx_end
                core_len = core_end - core_begin
                overlap = max(0, min(sp_end, core_end) - max(sp_start, core_begin))
                crosses_lines = text[sp_start:sp_end].count("\n") + 1 >= _DEGENERATE_MIN_LINES
                if (
                    core_len > 0
                    and overlap >= _DEGENERATE_COVERAGE_RATIO * core_len
                    and (LABEL_MAP.get(sp_label) is None or crosses_lines)
                ):
                    _LOG.info(
                        "Degenerate whole-chunk NER span (label=%s, chunk_chars=%d); "
                        "re-tagging chunk line-by-line",
                        "remote" if fail_closed else sp_label,
                        core_len,
                    )
                    candidates.extend(
                        _retag_degenerate_chunk(
                            text,
                            ner,
                            core_begin,
                            core_end,
                            fail_closed=fail_closed,
                        )
                    )
                    chunk_first = chunk_last + 1
                    continue

            for ent_text, ctx_start, ctx_end_pos, label in bio_spans:
                orig_start = ctx_begin + ctx_start
                orig_end = ctx_begin + ctx_end_pos
                if not (core_begin <= orig_start < core_end):
                    continue
                if label not in LABEL_MAP and "\n" in text[orig_start:orig_end]:
                    candidates.extend(
                        _retag_unknown_label_span(
                            text,
                            ner,
                            orig_start,
                            orig_end,
                            fail_closed=fail_closed,
                        )
                    )
                    continue
                candidates.extend(_finalize_tb_candidate(text, orig_start, orig_end, label))

        chunk_first = chunk_last + 1

    return candidates


def _trim_unoccupied_isolated_name_prefix(
    text: str,
    candidate: Entity,
) -> Entity | None:
    """Remove a field or role before an isolated NAME.

    The prefix is matched on the physical LINE, not the candidate: same-line hygiene can strip
    the role word off the candidate first, and the remainder must still be probed — a
    prefix-led isolated line mints a NAME only when its value passes the normal name rules.
    """
    line_begin = text.rfind("\n", 0, candidate.span[0]) + 1
    prefix = _ISOLATED_NAME_PREFIX_RE.match(text, line_begin)
    if prefix is None:
        return candidate
    value_start = max(candidate.span[0], prefix.end())
    if value_start >= candidate.span[1]:
        return None

    # Check the value with the normal name rules, then map it to the source.
    from amphrang.engine.detectors.name_context import detect_name_context

    label = "ชื่อ "
    value = text[value_start : candidate.span[1]]
    probe = label + value
    validated = [
        entity
        for entity in detect_name_context(probe)
        if entity.data_type == "NAME" and entity.span[0] >= len(label)
    ]
    if not validated:
        return None

    best = max(validated, key=lambda entity: entity.span[1] - entity.span[0])
    start = value_start + best.span[0] - len(label)
    end = value_start + best.span[1] - len(label)
    if not (candidate.span[0] <= start < end <= candidate.span[1]):
        return None
    return Entity(
        entity_id=candidate.entity_id,
        redact_type=candidate.redact_type,
        data_type=candidate.data_type,
        span=(start, end),
        score=candidate.score,
        original_text=text[start:end],
    )


def _isolated_line_name_candidates(
    text: str,
    ner: NER,
    occupied: list[Entity],
    diagnostics: NERChunkDiagnostics | None = None,
) -> tuple[list[Entity], set[str]]:
    """Retry short Thai lines with no entity or only NAME entities."""
    if "\n" not in text and "\r" not in text:
        return [], set()

    from amphrang.engine.detectors.name_context import is_glued_name_run

    def _has_name_shape(line: str) -> bool:
        if _ISOLATED_NAME_LINE_RE.fullmatch(line):
            return True
        return bool(_ISOLATED_GLUED_LINE_RE.fullmatch(line)) and is_glued_name_run(line)

    candidates: list[Entity] = []
    superseded_ids: set[str] = set()
    attempted = 0
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        line_end = offset + len(line)
        line_entities = [
            entity
            for entity in occupied
            if not (line_end <= entity.span[0] or offset >= entity.span[1])
        ]
        line_has_non_name = any(entity.data_type != "NAME" for entity in line_entities)
        if (
            attempted < _ISOLATED_NAME_MAX_LINES
            and not line_has_non_name
            and len(line) <= _ISOLATED_NAME_MAX_CHARS
            and _has_name_shape(line)
        ):
            attempted += 1
            line_candidates = [
                entity
                for entity in _ner_candidates(
                    text,
                    ner,
                    [(line, offset)],
                    0,
                    diagnostics=diagnostics,
                )
                if entity.data_type == "NAME"
            ]
            if not line_entities:
                candidates.extend(
                    trimmed
                    for candidate in line_candidates
                    if (trimmed := _trim_unoccupied_isolated_name_prefix(text, candidate))
                    is not None
                )
                offset += len(raw_line)
                continue

            for candidate in line_candidates:
                overlapping = [
                    entity
                    for entity in line_entities
                    if not (
                        candidate.span[1] <= entity.span[0] or candidate.span[0] >= entity.span[1]
                    )
                ]
                preserves_start = overlapping and all(
                    candidate.span[0] == entity.span[0] for entity in overlapping
                )
                extends_right = all(
                    candidate.span[1] >= entity.span[1] for entity in overlapping
                ) and any(candidate.span[1] > entity.span[1] for entity in overlapping)
                if preserves_start and extends_right:
                    candidates.append(candidate)
                    superseded_ids.update(entity.entity_id for entity in overlapping)
        offset += len(raw_line)

    return candidates, superseded_ids


# Main detector


def _detect_tb_impl(
    text: str,
    *,
    window_size: int = 1,
    diagnostics: NERChunkDiagnostics | None = None,
) -> list[Entity]:
    """Detect text-based PII entities using PyThaiNLP NER.

    window_size: sentences of margin context each side of a chunk (raise to 2 if benchmark
    recall regresses). Returns Entities (redact_type="TB") sorted by span start; an overlap
    survives only in `_deduplicate`'s coverage-guard case. Spans < 2 chars are rejected.
    """
    if not text or not text.strip():
        return []

    # Sentence tokenization with cumulative offsets. crfcut is ~28% of detect time; line-break
    # units were measured (same output on all gold docs, 18% faster) but lost a name on the คร.1
    # OCR regression that crfcut's grouping recovers. Recall wins; crfcut stays.
    raw_sentences = sent_tokenize(text, engine="crfcut")
    if not raw_sentences:
        return []

    sentence_offsets: list[tuple[str, int]] = []
    pos = 0
    for sent in raw_sentences:
        idx = text.find(sent, pos)
        if idx == -1:
            idx = pos
        sentence_offsets.append((sent, idx))
        pos = idx + len(sent)

    # Engine selection: union runs both, everything else is a single engine.
    name = _resolve_engine_name()
    if name == "finetuned":
        return _detect_tb_finetuned(text)
    if name == "union":
        ners = [_load_ner("thainer"), _load_ner("wangchanberta")]
    else:
        ners = [_load_ner(name)]

    candidates: list[Entity] = []
    for ner in ners:
        candidates.extend(
            _ner_candidates(
                text,
                ner,
                sentence_offsets,
                window_size,
                diagnostics=diagnostics,
            )
        )

    # Recall booster: title/label-cued names the NER missed or clipped (engine-independent).
    from amphrang.engine.detectors.name_context import (
        detect_conjunction_names,
        detect_name_context,
    )

    candidates.extend(detect_name_context(text))
    # A conjunction right after an accepted NAME introduces the NEXT person; the CRF stops at
    # และ and that name shipped unmasked.
    candidates.extend(detect_conjunction_names(text, candidates))
    if name == "thainer":
        isolated_names, superseded_ids = _isolated_line_name_candidates(
            text,
            ners[0],
            candidates,
            diagnostics=diagnostics,
        )
        candidates = [entity for entity in candidates if entity.entity_id not in superseded_ids]
        candidates.extend(isolated_names)

    return _deduplicate(candidates)


def detect_tb(
    text: str,
    *,
    window_size: int = 1,
    diagnostics: NERChunkDiagnostics | None = None,
) -> list[Entity]:
    """Run TB detection while containing explicit remote-engine failures."""

    failure = None
    try:
        return _detect_tb_impl(
            text,
            window_size=window_size,
            diagnostics=diagnostics,
        )
    except NERFailureError as error:
        failure = ner_failure_metadata(error)
        discard_exception_graph(error)

    text = ""
    diagnostics = None
    code, category, count = failure
    failure = None
    raise NERFailureError(code, category=category, count=count) from None

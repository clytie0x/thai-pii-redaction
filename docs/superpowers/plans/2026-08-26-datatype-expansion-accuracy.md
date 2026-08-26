# Data-Type Expansion + Accuracy Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five new Thai structured PII types (JURISTIC_ID, DRIVER_LICENSE, LINE_ID, GPS_COORD, HOUSE_REG_ID) end-to-end — detect → surrogate → token → leak guard → gold benchmark — and raise accuracy on the two documented weak spots (STUDENT_ID recall 0.719; negative-slice clean rate 31/45).

**Architecture:** New types follow the existing fp_detector "numbered step + score ladder + cue window" idiom exactly; every type flows through the same 9-surface integration checklist (detector, generator, token label, leak-guard sets, canonical_value, benchmark types/corpus/gold, docs). Accuracy work is evidence-first: enumerate the exact missed/false gold spans before touching any pattern.

**Tech Stack:** Python 3.11+, regex, pytest, existing benchmark harness (`python -m benchmark --source gold`).

**Spec:** `docs/decisions/2026-08-25-production-enterprise-direction.md` (Phase 1 item 2: published accuracy) + `README.md` "Measured accuracy" (baseline numbers) + this plan's Type Specification table (the contract for the new types).

**Executor model routing (set by the orchestrator when dispatching each task):**

| Task | Model | Why |
|---|---|---|
| 1 Checksum research + spec freeze | opus | external verification, judgment |
| 2 Detectors (fp_detector) | opus | precision/recall risk, precedence design |
| 3 Generators + labels + guard sets | sonnet | mechanical, fully specified |
| 4 Benchmark corpus + synthetic wiring | sonnet | mechanical, byte-identity care |
| 5 Gold slice authoring | sonnet | authoring to a written contract |
| 6 STUDENT_ID recall campaign | opus | diagnostic + pattern design |
| 7 Negative-slice precision campaign | opus | diagnostic + policy judgment |
| 8 Docs sweep | sonnet | mechanical |
| 9 Final verification + numbers | sonnet | run + report, no code |

## Global Constraints

- **Recall-first**: no task may reduce any existing per-type gold recall (README table is the baseline; re-run `python -m benchmark --source gold` to confirm).
- **Blind set is off limits**: never read, decrypt, or score `benchmark/data/blind-*`; never run `python -m benchmark --source blind` (reveal budget is 6/6 spent). `TYPE_MINIMUMS`/blind artifacts are NOT edited in this plan.
- **TDD** (superpowers:test-driven-development): failing test first, watch it fail, minimal code, watch it pass. Every commit runs the pre-commit hooks.
- **Public facade unchanged**: `amphrang/__init__.py` and `docs/api-surface.txt` must not change; `Entity.data_type` is an open string, so new types need no facade edit. `scripts/check_release.py` must stay green.
- **Deterministic corpus**: `benchmark/corpus.py` warns (lines 53–57) that extra rng draws shift every downstream value; add samplers keyed by type (no unconditional draws) and append templates only at the END of `_CORE_TEMPLATES`.
- **Thai punctuation in Thai strings**: spaces, never colons (repo convention).
- **Lint/format**: `./.venv/Scripts/python.exe -m ruff check .` and `ruff format` clean before every commit.
- **Commit style**: imperative subject, body states what was verified with real output numbers.
- Full test command used everywhere: `./.venv/Scripts/python.exe -m pytest -q`.

---

## Type Specification (the shared contract — all tasks use these exact values)

| data_type | Thai token label | Shape | Score | Cue regex (30-char window before) | Surrogate |
|---|---|---|---|---|---|
| `JURISTIC_ID` | `ทะเบียนนิติบุคคล` | 13 digits starting `0`, plain or dashed `0-1075-36000-10-2` | 1.0 with valid checksum; cue-gated 0.9 if Task 1 cannot verify the checksum | `นิติบุคคล\|ทะเบียนบริษัท\|ทะเบียนพาณิชย์\|เลข(?:ประจำตัว)?ผู้เสียภาษี\|tax\s*id\|juristic` | `0` + 12 digits (checksum-valid if verified) |
| `DRIVER_LICENSE` | `ใบขับขี่` | 8 digits, cue-gated ONLY | 0.9 | `ใบขับขี่\|ใบอนุญาตขับขี่\|ใบอนุญาตขับรถ\|driv(?:er'?s?\|ing)\s*licen[cs]e` | 8 digits |
| `LINE_ID` | `ไลน์ไอดี` | `@?[A-Za-z0-9._-]{4,24}` within 12 chars after cue, same line, cue-gated ONLY | 0.9 | `(?:LINE\|ไลน์)\s*(?:ID\|ไอดี)?` (cue BEFORE value) | lowercase letters+digits, length-preserving, keep leading `@` |
| `GPS_COORD` | `พิกัด` | `lat, lon` decimal pair, both with ≥4 decimals, lat∈[-90,90], lon∈[-180,180] | 0.95 (no cue needed) | — | `f"{rng.uniform(5.6, 20.5):.6f}, {rng.uniform(97.3, 105.6):.6f}"` |
| `HOUSE_REG_ID` | `รหัสประจำบ้าน` | 11 digits, cue-gated ONLY | 0.9 | `รหัสประจำบ้าน\|เลขรหัสประจำบ้าน` | 11 digits |

Shared rules for all five:
- `redact_type="FP"` (the anonymizer routes FP → `generate_fp`; see `amphrang/engine/detectors/fn_scanner.py:16-17` for the trap).
- Alnum-boundary lookarounds `(?<![A-Za-z0-9_])…(?![A-Za-z0-9_])` for latin/digit shapes, `(?<!\d)…(?!\d)` for pure digit runs (glued-to-Thai recall; see `_RE_PASSPORT_TH`).
- Value in regex **group 1** (`_make_entity` uses group 1).
- Membership in `SAFE_OUTBOUND_LEAK_TYPES` and `_OBFUSCATED_STRUCTURED_TYPES` (all five are structured).
- `canonical_value` folding: digits-only fold for JURISTIC_ID / DRIVER_LICENSE / HOUSE_REG_ID; strip leading `@` + casefold for LINE_ID; whitespace-fold for GPS_COORD (default branch already does this — only the first four need code).
- Precedence facts to preserve (CORRECTED after Task 1 — see `docs/decisions/2026-08-26-new-datatype-specs.md`): `_RE_THAI_ID` (fp_detector.py:250) does NOT restrict the first digit, and the juristic check digit is the SAME citizen mod-11 (`is_valid_thai_id` reuses apply), so today every real juristic number is emitted as THAI_ID 1.0. Do NOT gate THAI_ID by first digit — 0-leading citizen-style IDs exist (persons without registration status) and gold has first digits 1–9. Instead: the JURISTIC_ID step emits 1.0 on 0-leading checksum-valid runs, and a new `_disambiguate_thai_juristic` pass (modeled on `_disambiguate_bank_student`, fp_detector.py:162-195) resolves the same-span THAI_ID/JURISTIC_ID pair — juristic cue in the 30-char window → keep JURISTIC_ID, otherwise keep THAI_ID (the personal label is the recall-safe default; the value is masked either way). DRIVER_LICENSE (8 digits, 0.9 cue-gated) outranks STUDENT_ID/ID_NUMBER (0.8) in `_deduplicate` by score; a doc with BOTH driver and student cues near one 8-digit run resolves by nearest cue (Task 2 step for `_disambiguate_driver_student`, modeled on `_disambiguate_bank_student` at fp_detector.py:162-195). HOUSE_REG_ID (11 digits) overlaps `_RE_STUDENT_ID` (8–12): cue-gated 0.9 beats 0.8.

Baseline numbers (from README, gold v4, 2026-08-25 run): overall R 0.969 / P 0.867 / F2 0.947 (CI 0.928–0.964); STUDENT_ID R 0.719 (n=57); negative slice 31/45 clean docs. These are the regression floors and improvement targets.

---

### Task 1: Checksum research + spec freeze (opus)

**Files:**
- Create: `docs/decisions/2026-08-26-new-datatype-specs.md`

**Interfaces:**
- Produces: the frozen spec record later tasks cite; in particular the verdict `JURISTIC_CHECKSUM: verified|unverified` plus, if verified, the exact algorithm and 5 test vectors.

- [ ] **Step 1: Verify the juristic-ID check digit** — research (WebSearch/WebFetch) whether Thai juristic registration numbers (เลขทะเบียนนิติบุคคล, 13 digits starting 0) use the citizen-ID mod-11 algorithm `check = (11 - (sum(d[i]*(13-i) for i in 0..11) % 11)) % 10`. Collect at least 5 REAL public juristic numbers (listed-company registration numbers are public record) and test the formula against every one. If all 5 validate → verdict `verified`. If any fails or sources conflict → verdict `unverified` (the detector then ships cue-gated 0.9, honest-labels rule).
- [ ] **Step 2: Verify HOUSE_REG_ID** — confirm the house registration code (เลขรหัสประจำบ้าน in ทะเบียนบ้าน) is 11 digits; do NOT claim a checksum unless verified the same way (5 real examples are not publicly collectible → expected verdict: shape-only, cue-gated).
- [ ] **Step 3: Confirm DRIVER_LICENSE number shape** — modern Thai licence cards carry an 8-digit ใบอนุญาตเลขที่; record the source. If evidence shows a different/variable length, adjust the spec table value and say so in the record.
- [ ] **Step 4: Write the decision record** — `docs/decisions/2026-08-26-new-datatype-specs.md` containing: the five-type spec table copied from this plan (with any Step-1–3 corrections applied), each verdict with sources and test vectors, and the sentence "Blind-v1 is frozen; these types enter the blind corpus only at the next rotation."
- [ ] **Step 5: Commit** — `git add docs/decisions/2026-08-26-new-datatype-specs.md && git commit` (subject: `docs: freeze specs for 5 new PII types (juristic checksum <verdict>)`).

### Task 2: Detectors in fp_detector (opus)

**Files:**
- Modify: `amphrang/engine/detectors/fp_detector.py` (patterns near :250-421, cues near :423-563, steps inside `detect_fp` after step 10b at :735, disambiguator beside :162-195)
- Test: `tests/test_new_types_detection.py` (create)

**Interfaces:**
- Consumes: Task 1's verdicts (checksum yes/no, shapes).
- Produces: `detect_fp` emits the five types per the spec table; helper `is_valid_juristic_id(value: str) -> bool` (only if verified); all entities `redact_type="FP"`, value in group 1.

- [ ] **Step 1: Write the failing tests** — create `tests/test_new_types_detection.py`:

```python
"""Detection contract for the five types added 2026-08-26 (see the spec ADR)."""

import pytest

from amphrang.engine.detectors.fp_detector import detect_fp


def _types(text):
    return {(e.data_type, e.original_text) for e in detect_fp(text)}


# JURISTIC_ID — use a checksum-VALID number from Task 1's vectors if verified,
# else any 0-leading 13-digit value with the cue.
def test_juristic_id_with_cue_detected():
    found = _types("เลขทะเบียนนิติบุคคล 0107536000102 ของบริษัทจดทะเบียน")
    assert ("JURISTIC_ID", "0107536000102") in found


def test_juristic_dashed_form_detected():
    found = _types("เลขประจำตัวผู้เสียภาษี 0-1075-36000-10-2 ตามหนังสือรับรอง")
    assert any(t == "JURISTIC_ID" for t, _ in found)


def test_thai_id_never_becomes_juristic():
    # a checksum-valid citizen id with a citizen cue must stay THAI_ID
    found = _types("เลขบัตรประชาชน 1101700230708")
    assert ("THAI_ID", "1101700230708") in found
    assert not any(t == "JURISTIC_ID" for t, _ in found)


def test_zero_leading_id_without_juristic_cue_stays_thai_id():
    # 0-leading checksum-valid runs are ambiguous (stateless-person ids exist);
    # without a juristic cue the personal label wins — recall-safe default.
    found = _types("เลขประจำตัว 0107536000102 ของผู้ยื่นคำร้อง")
    assert any(t == "THAI_ID" for t, _ in found)
    assert not any(t == "JURISTIC_ID" for t, _ in found)


def test_driver_license_with_cue_detected():
    found = _types("ใบขับขี่เลขที่ 63012345 ออกโดยกรมการขนส่งทางบก")
    assert ("DRIVER_LICENSE", "63012345") in found


def test_bare_8_digits_without_cue_is_not_driver_license():
    found = _types("เอกสารอ้างอิง 63012345 ลงวันที่วันนี้")
    assert not any(t == "DRIVER_LICENSE" for t, _ in found)


def test_driver_vs_student_nearest_cue_wins():
    found = _types("รหัสนักศึกษา 63012345 และใบขับขี่ 71234568 ของนักศึกษาคนเดียวกัน")
    assert ("DRIVER_LICENSE", "71234568") in found
    assert ("STUDENT_ID", "63012345") in found


def test_line_id_after_cue_detected():
    found = _types("ติดต่อทาง LINE ID @somchai_j99 ได้เลย")
    assert ("LINE_ID", "@somchai_j99") in found


def test_line_word_without_id_value_is_clean():
    assert not any(t == "LINE_ID" for t, _ in _types("เดินข้ามเส้น line กลางถนน"))


def test_gps_pair_detected_without_cue():
    found = _types("จุดนัดพบ 13.7563, 100.5018 หน้าตึก")
    assert ("GPS_COORD", "13.7563, 100.5018") in found


def test_money_pair_with_two_decimals_is_not_gps():
    assert not any(t == "GPS_COORD" for t, _ in _types("ราคา 12.50, 100.75 บาท"))


def test_house_reg_with_cue_detected():
    found = _types("เลขรหัสประจำบ้าน 10240012345 ตามทะเบียนบ้าน")
    assert ("HOUSE_REG_ID", "10240012345") in found


def test_bare_11_digits_without_cue_not_house_reg():
    assert not any(t == "HOUSE_REG_ID" for t, _ in _types("รายการเลขที่ 10240012345"))
```

- [ ] **Step 2: Run and watch every test fail** — `./.venv/Scripts/python.exe -m pytest -q tests/test_new_types_detection.py`; expected: FAIL/assert on every test (types not emitted yet).
- [ ] **Step 3: Implement** — add to `fp_detector.py`, following the PASSPORT template exactly (patterns section, cue section, then numbered steps 14–18 at the end of the step list, before `_disambiguate_bank_student` is applied):
  - patterns `_RE_JURISTIC_ID = re.compile(r"(?<!\d)(0\d{12})(?!\d)")` and a dashed variant mirroring how THAI_ID's dashed form is handled (read step 1 of `detect_fp` first and mirror it); `_RE_DRIVER_LICENSE = re.compile(r"(?<!\d)(\d{8})(?!\d)")`; `_RE_LINE_ID` (cue + gap ≤12 chars + `(@?[A-Za-z0-9._-]{4,24})` in group 1, same line); `_RE_GPS = re.compile(r"(?<![\d.])(-?\d{1,2}\.\d{4,7},\s?-?\d{1,3}\.\d{4,7})(?![\d.])")` with a range check in the step body; `_RE_HOUSE_REG = re.compile(r"(?<!\d)(\d{11})(?!\d)")`.
  - cue regexes from the spec table; `is_valid_juristic_id` delegates to the existing `amphrang/engine/detectors/thai_id.py::is_valid_thai_id` (Task 1 proved the algorithm is identical, 8/8 real vectors) — unit-test with those vectors from the ADR.
  - a `_disambiguate_thai_juristic` pass (see the corrected precedence bullet in the spec section): same-span THAI_ID/JURISTIC_ID pair → juristic cue in window keeps JURISTIC_ID, otherwise THAI_ID. Must leave gold THAI_ID recall untouched (no gold THAI_ID starts with 0; verified in Task 1's histogram).
  - a `_disambiguate_driver_student` pass modeled on `_disambiguate_bank_student` (:162-195), nearest-cue-wins, tie favours DRIVER_LICENSE (cue-gated evidence is stronger than tier-3 student evidence).
- [ ] **Step 4: Run to green** — new suite passes AND `pytest -q tests/test_step2_detection.py tests/test_recall_leaks.py tests/test_plate_precision.py tests/test_student_id_context.py tests/test_document_code_fps.py` all pass unchanged.
- [ ] **Step 5: Commit** — subject `feat: detect JURISTIC_ID, DRIVER_LICENSE, LINE_ID, GPS_COORD, HOUSE_REG_ID`.

### Task 3: Generators, token labels, guard sets, canonical folding (sonnet)

**Files:**
- Modify: `amphrang/engine/anonymizer/fp_generator.py` (:121-180), `amphrang/engine/anonymizer/token_generator.py` (:11-31), `amphrang/engine/leak_guard.py` (:38-71, :164-180), `amphrang/engine/scan_common.py` (:12-33), `amphrang/engine/models.py` (:14-17 docstring vocabulary)
- Test: `tests/test_new_types_roundtrip.py` (create)

**Interfaces:**
- Consumes: Task 2's emitted types.
- Produces: `generate_fp` branches for the five types; `TOKEN_LABEL` entries per spec table; both leak-guard frozensets extended; `canonical_value` folds per spec.

- [ ] **Step 1: Write the failing tests** — `tests/test_new_types_roundtrip.py`:

```python
"""Every new type must round-trip the full facade in both modes."""

import pytest

import amphrang
from amphrang.engine.anonymizer.fp_generator import generate_fp
from amphrang.engine.anonymizer.token_generator import TOKEN_LABEL
from amphrang.engine.leak_guard import SAFE_OUTBOUND_LEAK_TYPES, _OBFUSCATED_STRUCTURED_TYPES
from amphrang.engine.scan_common import canonical_value

NEW_TYPES = ["JURISTIC_ID", "DRIVER_LICENSE", "LINE_ID", "GPS_COORD", "HOUSE_REG_ID"]

TEXTS = {
    "JURISTIC_ID": "เลขทะเบียนนิติบุคคล 0107536000102 ของบริษัท",
    "DRIVER_LICENSE": "ใบขับขี่เลขที่ 63012345 หมดอายุปีหน้า",
    "LINE_ID": "ติดต่อ LINE ID @somchai_j99 หลังเลิกงาน",
    "GPS_COORD": "พบกันที่ 13.7563, 100.5018 ตอนเที่ยง",
    "HOUSE_REG_ID": "เลขรหัสประจำบ้าน 10240012345 ตามทะเบียนบ้าน",
}


@pytest.mark.parametrize("dtype", NEW_TYPES)
def test_registered_everywhere(dtype):
    assert dtype in TOKEN_LABEL
    assert dtype in SAFE_OUTBOUND_LEAK_TYPES
    assert dtype in _OBFUSCATED_STRUCTURED_TYPES


@pytest.mark.parametrize("dtype", NEW_TYPES)
def test_token_mode_round_trip(dtype):
    text = TEXTS[dtype]
    masked = amphrang.anonymize(text, mode="token", salt="s")
    assert dtype in masked.entity_type_counts, masked.entity_type_counts
    assert amphrang.restore(masked.text, masked.mapping).text == text


@pytest.mark.parametrize("dtype", NEW_TYPES)
def test_surrogate_mode_round_trip_and_shape(dtype):
    text = TEXTS[dtype]
    masked = amphrang.anonymize(text, mode="surrogate", salt="s")
    assert amphrang.restore(masked.text, masked.mapping).text == text
    # the surrogate itself must re-detect as the same type (shape preserved)
    remasked = amphrang.detect(masked.text)
    assert any(e.data_type == dtype for e in remasked), masked.text


def test_juristic_surrogate_starts_with_zero():
    value = generate_fp("JURISTIC_ID", "0107536000102", salt="s")
    assert value.startswith("0") and len(value) == 13 and value.isdigit()


def test_canonical_value_folds_dashes_for_juristic():
    assert canonical_value("JURISTIC_ID", "0-1075-36000-10-2") == "0107536000102"


def test_canonical_value_line_id_case_and_at():
    assert canonical_value("LINE_ID", "@Somchai_J99") == canonical_value(
        "LINE_ID", "somchai_j99"
    )
```

- [ ] **Step 2: Watch them fail** — expected KeyError/assert on registration test first.
- [ ] **Step 3: Implement** — `_gen_juristic_id` (checksum-valid if Task 1 verified — reuse the ADR's algorithm; else `"0" + 12 digits`), `_gen_driver_license` (8 digits), `_gen_line_id` (keep leading `@` if present, lowercase letters+digits, same length), `_gen_gps` (spec table f-string), `_gen_house_reg` (11 digits); `elif` branches in `generate_fp`; `TOKEN_LABEL` entries (spec table, watch for label collisions with existing values); extend both frozensets; `canonical_value` branches (digits-fold for the three digit types via `re.sub(r"\D", "", value)`, LINE_ID `value.strip().lstrip("@").casefold()`); update the `models.py` data_type docstring comment; update the parametrize table in `tests/test_leak_guard.py:230-251` (obfuscated-structured rows) with one row per new digit type.
- [ ] **Step 4: Run** — new suite + `pytest -q tests/test_leak_guard.py tests/test_stateless.py tests/test_amprang_facade.py` green; then FULL suite green.
- [ ] **Step 5: Commit** — subject `feat: surrogates, token labels, guard registration for the 5 new types`.

### Task 4: Synthetic benchmark wiring (sonnet)

**Files:**
- Modify: `benchmark/types.py` (:5-18), `benchmark/corpus.py` (sampler :25-61, templates end of `_CORE_TEMPLATES`, `_SLOT_KEY_TO_TYPE` :107-120), `benchmark/llm_strategy.py` (:24-35 prompt bullets)
- Test: existing `tests/test_benchmark.py`, `tests/test_perf_harness.py`, `tests/test_leak_guard.py` (the 55-line regression)

**Interfaces:**
- Consumes: Tasks 2–3 (detection + generators).
- Produces: `SHARED_ENTITY_TYPES` includes the five names; corpus emits them via two new templates appended at the END of `_CORE_TEMPLATES`.

- [ ] **Step 1: Extend `SHARED_ENTITY_TYPES`** with the five names (append at the end of the tuple).
- [ ] **Step 2: Add sampler branches** in `_sample_value` reusing `fp_generator` (single source of truth), e.g.:

```python
    if entity_type == "JURISTIC_ID":
        return fg._gen_juristic_id(rng)
    if entity_type == "DRIVER_LICENSE":
        return fg._gen_driver_license(rng)
    if entity_type == "LINE_ID":
        return "@" + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(9))
    if entity_type == "GPS_COORD":
        return f"{rng.uniform(5.6, 20.5):.6f}, {rng.uniform(97.3, 105.6):.6f}"
    if entity_type == "HOUSE_REG_ID":
        return "".join(str(rng.randint(0, 9)) for _ in range(11))
```

- [ ] **Step 3: Append two templates at the END of `_CORE_TEMPLATES`** (appending keeps earlier rotation byte-stable; verify with the perf/leak tests below):

```python
    (
        "business",
        "บริษัทจดทะเบียนเลขนิติบุคคล {juristic} ติดต่อ LINE ID {line} พิกัดสำนักงาน {gps}",
        [("juristic", "JURISTIC_ID"), ("line", "LINE_ID"), ("gps", "GPS_COORD")],
    ),
    (
        "transport",
        "ผู้ขับ {name} ใบขับขี่ {license} เลขรหัสประจำบ้าน {housereg}",
        [("name", "NAME"), ("license", "DRIVER_LICENSE"), ("housereg", "HOUSE_REG_ID")],
    ),
```

  plus `_SLOT_KEY_TO_TYPE` entries `"juristic"`, `"line"`, `"gps"`, `"license"`, `"housereg"`.
- [ ] **Step 4: Add the five Thai bullets** to the LLM prompt list in `llm_strategy.py:24-35` (`- JURISTIC_ID เลขทะเบียนนิติบุคคล` etc.).
- [ ] **Step 5: Run the ripple checks** — `pytest -q tests/test_benchmark.py tests/test_perf_harness.py tests/test_leak_guard.py tests/test_benchmark_strategies.py`; then `./.venv/Scripts/python.exe -m benchmark` (synthetic) and paste the OVERALL row into the commit body. If `tests/test_leak_guard.py::test_long_document_with_record_name_lines_is_not_leak_blocked` fails because corpus content shifted, re-bisect the minimal blocking prefix (the test's docstring explains it) — but content-shift breakage means templates were NOT appended at the end; fix that instead.
- [ ] **Step 6: Full suite, then commit** — subject `feat: wire 5 new types into the synthetic benchmark corpus`.

### Task 5: Gold slice authoring (sonnet)

**Files:**
- Modify: `benchmark/data/gold.jsonl` (append), `benchmark/gold.py` (:51 GOLD_VERSION → `"gold-v5"`, :55-68 add slice), `tests/test_benchmark_gold.py` (slice contract), `.github/ISSUE_TEMPLATE/gold_document.yml` (:44-60 slice dropdown), `.github/ISSUE_TEMPLATE/detection_report.yml` (:50-54 vocabulary)

**Interfaces:**
- Consumes: the spec table values (formats) and Task 4's `SHARED_ENTITY_TYPES`.
- Produces: new `business_ids` slice (layer `balanced`), ≥20 gold instances of EACH new type.

- [ ] **Step 1: Add slice** `"business_ids": "balanced"` to `SLICE_LAYERS`, bump `GOLD_VERSION` to `"gold-v5"`.
- [ ] **Step 2: Author ~28 documents** appended to `gold.jsonl`, slice `business_ids`, `doc_id` prefix `bz01…bz28`, following `docs/annotation-guidelines.md` end-to-end first. Coverage budget: each of the five types ≥20 spans total (`_MIN_PER_TYPE = 20` in `tests/test_benchmark_gold.py:33`); values all distinct across documents (value-reuse test); synthetic values only, juristic numbers checksum-valid iff Task 1 verified. Vary one axis at a time (dashed/plain juristic, `@`-less LINE ids, negative-longitude GPS is NOT valid for Thailand — keep Thai-range coordinates, 4–6 decimals). Include in several documents unlabeled look-alike context that must NOT be flagged as the new types (prices with two decimals near the word พิกัด, an 8-digit invoice number near ใบขับขี่ of someone else, the word "ไลน์" as a queue/line noun) — these police precision through the OUT_OF_SCHEME lane. Example document (format reference):

```json
{"doc_id": "bz01", "slice": "business_ids", "layer": "balanced", "annotated": "บริษัทออดิทไทย จำกัด เลขทะเบียนนิติบุคคล [[JURISTIC_ID|0105561012345]] มอบหมายให้ [[NAME|นายปกรณ์ ตั้งใจ]] ใบขับขี่ [[DRIVER_LICENSE|63219876]] เดินทางไปพิกัด [[GPS_COORD|13.7563, 100.5018]] ติดต่อ LINE ID [[LINE_ID|@audit_th]] ราคาประเมิน 1250.50 บาท"}
```

- [ ] **Step 3: Update the slice-contract test** — in `tests/test_benchmark_gold.py`, add `business_ids` to any slice enumeration the file asserts, plus a contract test: every `business_ids` doc carries at least one of the five new types.
- [ ] **Step 4: Update the two issue templates** (slice dropdown + type vocabulary lists).
- [ ] **Step 5: Validate** — `pytest -q tests/test_benchmark_gold.py` green, then `python -m benchmark --source gold` and record per-type rows for the five new types in the commit body. Target: recall ≥ 0.95 per new type on gold; if a new type scores below, file the misses verbatim in the commit body and hand back to the orchestrator (do NOT patch detectors in this task).
- [ ] **Step 6: Full suite, commit** — subject `bench: gold-v5 adds business_ids slice covering the 5 new types`.

### Task 6: STUDENT_ID recall campaign (opus)

**Files:**
- Modify: `amphrang/engine/detectors/fp_detector.py` (`_student_evidence` :198-241, cues :441-468, steps 10/10b :716-735)
- Test: `tests/test_student_id_context.py` (extend), `tests/test_document_code_fps.py` (must stay green)

**Interfaces:** consumes gold-v5; produces STUDENT_ID gold recall ≥ 0.85 with precision still 1.000-ish (≥ 0.97) and zero new negative-slice predictions.

- [ ] **Step 1: Evidence first (no code)** — run `python -m benchmark --source gold --json <scratch>/gold.json`, then list EVERY missed STUDENT_ID span verbatim with its document text (write a script over the json + `benchmark/gold.py.load_gold()`; misses = gold spans with no overlapping prediction of the right type). Group the misses by cause (cue distance beyond `_STUDENT_PERSON_WINDOW`? unseen introducer word? dashed variants? length?). Record the grouped list in the task report — this is the deliverable that justifies each change.
- [ ] **Step 2: For each cause group, one failing test** in `tests/test_student_id_context.py` reproducing a real missed span (copy the gold text verbatim).
- [ ] **Step 3: Minimal pattern/tier changes** — widen only what the evidence names (e.g. one new introducer word, one window bump with the measured distance). Every widening must state, in a comment, which gold doc it recovers.
- [ ] **Step 4: Prove no collateral** — `pytest -q tests/test_student_id_context.py tests/test_document_code_fps.py tests/test_plate_precision.py` green; `python -m benchmark --source gold`: STUDENT_ID recall ≥ 0.85, STUDENT_ID precision ≥ 0.97, negative-slice false_positives NOT increased (baseline 15), every other type's recall unchanged or better.
- [ ] **Step 5: Full suite, commit** — subject `fix: STUDENT_ID recall <before>-><after> on gold (evidence-driven)`, body carries the per-group evidence.

### Task 7: Negative-slice precision campaign (opus)

**Files:**
- Modify: whatever the evidence names — expected: `amphrang/engine/detectors/tb_detector.py` cue-upgrade/date handling, `amphrang/engine/detectors/name_context.py` non-person lexicon
- Test: `tests/test_document_code_fps.py` (extend with the exact FP texts)

**Interfaces:** consumes gold-v5; produces negative-slice clean docs ≥ 38/45 with zero recall loss anywhere.

- [ ] **Step 1: Evidence first (no code)** — enumerate every prediction on every `negative` document (14 dirty docs, baseline 15 FPs; the weakness-closure record says the remainder are document-issue, deadline and effective dates). List each: doc_id, predicted type, exact span text.
- [ ] **Step 2: Classify each FP**: (a) label noise the detector is RIGHT to flag → propose a gold adjudication note instead of code (do not edit gold to flatter the detector — flag to orchestrator); (b) genuine FP → one failing test with the verbatim text.
- [ ] **Step 3: Minimal suppressions** — each keyed to a named FP; date-family suppressions must not touch DATE_OF_BIRTH cue upgrades (tests `test_step2_detection.py:679-794` pin honest labels).
- [ ] **Step 4: Prove** — `python -m benchmark --source gold`: clean docs ≥ 38/45, all per-type recalls unchanged or better, overall F2 ≥ 0.947. Full suite green.
- [ ] **Step 5: Commit** — subject `fix: negative-slice precision <before>-><after> clean docs`, evidence in body.

### Task 8: Docs sweep (sonnet)

**Files:**
- Modify: `docs/annotation-guidelines.md` (types table + per-type annotate/do-not rows), `docs/decisions/2026-08-05-http-contract-v2.md` (:417-421 vocabulary +5), `docs/decisions/README.md` (index rows for the two new decision records: 2026-08-26-new-datatype-specs and this initiative's outcome), `docs/research/gov-doc-policy-ontology.md` (rows for the five types), `README.md` ("What it detects" sentence + regenerate the accuracy table from Task 9's run), `CHANGELOG.md` (Unreleased → Added entry listing the five types; Fixed entries for Tasks 6–7 with before/after numbers)

- [ ] **Step 1: Update each doc** — the annotation guidelines gain one row per new type in the annotate/do-not-annotate table (mirror the existing VEHICLE_PLATE row style; the do-not column carries the look-alikes from Task 5 step 2).
- [ ] **Step 2: CHANGELOG** — under `## [Unreleased]` `### Added`: one bullet naming all five types with their gating (checksum/cue) exactly as shipped; under `### Fixed`: STUDENT_ID and negative-slice bullets with the measured before→after.
- [ ] **Step 3: Do NOT edit the README numbers yet** (Task 9 produces the authoritative run); leave a `<!-- refreshed by Task 9 -->` marker only if the table would otherwise be stale.
- [ ] **Step 4: Full suite (docs changes can still break gold tests via templates), commit** — subject `docs: five new PII types across guidelines, contract vocabulary, ontology`.

### Task 9: Final verification + published numbers (sonnet)

**Files:**
- Modify: `README.md` (accuracy table), Create: nothing else

- [ ] **Step 1: Full gates** — run and record raw output of ALL of: `ruff check .`, `ruff format --check .`, `python -m pytest -q` (expect 0 failures), `python scripts/check_release.py`, `python -m benchmark --source gold`, `python -m benchmark` (synthetic), `python -m benchmark.perf --profile ci`.
- [ ] **Step 2: Regression matrix** — compare against the baselines in this plan's spec section: every pre-existing type recall ≥ baseline; STUDENT_ID ≥ 0.85; clean negative docs ≥ 38/45; five new types recall ≥ 0.95 and precision ≥ 0.90 each. Any miss → STOP and hand back to the orchestrator with the exact rows (do not patch code in this task).
- [ ] **Step 3: Refresh the README accuracy table** from the fresh gold run (same format, new date line, now with 16 type rows), keeping the blind paragraph byte-identical (blind was not re-run).
- [ ] **Step 4: Commit** — subject `bench+docs: publish gold-v5 accuracy (16 types)`, body = the full per-type table and the regression matrix verdicts.

## Self-review notes (orchestrator, done at planning time)

- Spec coverage: five types × nine integration surfaces are covered by Tasks 2–5+8; the two accuracy targets by Tasks 6–7; publication by Task 9. Blind untouched everywhere.
- Type consistency: names/labels/scores appear only via the spec table; `_gen_*` names used in Task 4 match Task 3's definitions.
- Known risk registered: corpus template append shifts nothing (append-only rule) but Task 4 step 5 still verifies the perf/leak tests that depend on corpus bytes.

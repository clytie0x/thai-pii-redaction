# PDPA-Standard Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every text-detectable gap in the PDPA data ontology — three new structured types (IP_ADDRESS, MAC_ADDRESS, LAND_DEED_ID), two new quasi-identifiers (nationality, weight/height), person-linked span masking for ม.26 sensitive content — and publish a CI-gated **PDPA Coverage Profile** that maps every legal category to a treatment and a measured number, so amphrang can honestly claim reference-implementation ("standard") coverage.

**Architecture:** Wave 1 extends the proven fp_detector idiom (numbered step, score ladder, cue window, 9-surface integration) and the reid-risk QI scan. Wave 2 is a design-spike-then-implement pair: sensitive keywords become maskable span entities only when person-linked, so impersonal mentions never flag. Wave 3 turns the ontology into a public conformance artifact enforced by `check_release.py`, the same way `docs/api-surface.txt` pins the facade.

**Tech Stack:** Python 3.11+, regex, pytest, existing benchmark harness (`python -m benchmark --source gold`).

**Spec:** `docs/decisions/2026-08-26-pdpa-data-ontology.md` (the registry this plan implements — every task cites its level and row) + `docs/decisions/2026-08-25-production-enterprise-direction.md` (strategic frame) + this plan's spec tables.

**Executor model routing (set by the orchestrator when dispatching each task):**

| Task | Model | Why |
|---|---|---|
| 1 Legal-format research + verdict freeze | opus | external verification, judgment |
| 2 Wave-1 detectors (fp_detector) | opus | precision/recall risk, suppression design |
| 3 Generators + labels + guard sets | sonnet | mechanical, fully specified |
| 4 QI extension (reid_risk) | sonnet | mechanical, fully specified |
| 5 Corpus templates + samplers | sonnet | mechanical, byte-identity care |
| 6 Gold slice authoring (digital_ids, gold-v6) | sonnet | authoring to a written contract |
| 7 Wave-1 measurement checkpoint | sonnet | run + report, no code |
| 8 ม.26 span-masking design spike | opus | the campaign's hardest judgment |
| 9 Sensitive-span detector implementation | opus | precision/recall risk, guard integration |
| 10 Sensitive gold slice (gold-v7) + guidelines addendum | opus | annotation judgment |
| 11 PDPA Coverage Profile + CI gate | sonnet | mechanical, AST-parse pattern exists |
| 12 Docs sweep + final verification | sonnet | mechanical; orchestrator re-verifies |

## Global Constraints

- **Recall-first**: no task may reduce any existing per-type gold recall (README "Measured accuracy" table, gold-v5 run 2026-08-26, is the baseline; re-run `python -m benchmark --source gold` to confirm).
- **Blind set is off limits**: never read, decrypt, or score `benchmark/data/blind-*`; never run `python -m benchmark --source blind` (reveal budget is 6/6 spent). `TYPE_MINIMUMS`/blind artifacts are NOT edited in this plan.
- **Negative-slice budget**: the 45 negative docs stay at exactly 15 false positives / 31 clean docs (the policy-bound floor per the 2026-08-26 adjudication). Every new detector and the sensitive-span pass must add ZERO new negative-slice flags.
- **TDD** (superpowers:test-driven-development): failing test first, watch it fail, minimal code, watch it pass. Every commit runs the pre-commit hooks.
- **Public facade unchanged by default**: `amphrang/__init__.py` and `docs/api-surface.txt` change ONLY if Task 8's decision record explicitly requires a public knob, and then only with the manifest + CHANGELOG diff the stability policy demands. `Entity.data_type` is an open string, so new types alone need no facade edit. `scripts/check_release.py` must stay green.
- **Deterministic corpus**: `benchmark/corpus.py` warns (lines 53–57) that extra rng draws shift every downstream value; add samplers keyed by type (no unconditional draws) and append templates only at the END of `_CORE_TEMPLATES`.
- **Repo stays local**: no push, no GitHub, no release/tag (owner rule; 1.0 additionally requires explicit owner approval).
- **Thai punctuation in Thai strings**: spaces, never colons (repo convention).
- **Lint/format**: `./.venv/Scripts/python.exe -m ruff check .` and `ruff format` clean before every commit.
- **Commit style**: imperative subject, body states what was verified with real output numbers.
- Full test command used everywhere: `./.venv/Scripts/python.exe -m pytest -q`.

---

## Wave-1 Type Specification (the shared contract — all tasks use these exact values)

| data_type | Thai token label | Shape | Score | Cue regex (30-char window before) | Surrogate |
|---|---|---|---|---|---|
| `IP_ADDRESS` | `ไอพี` | IPv4 dotted quad, each octet 0–255, `(?<![\d.])…(?![\d.])`; or IPv6 (full / `::`-compressed, ≥2 groups) | IPv4 0.9 cue-gated, 0.8 catch-all with version suppression; IPv6 0.9 no cue | `IP\|ไอพี\|address\|แอดเดรส\|server\|เซิร์ฟเวอร์\|host\|โฮสต์\|router\|เราเตอร์\|เชื่อมต่อ\|log` | `f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"` |
| `MAC_ADDRESS` | `แมคแอดเดรส` | six hex pairs joined by `:` or `-` (one separator style per value) | 0.9 no cue | — | six random hex pairs joined by the original separator |
| `LAND_DEED_ID` | `โฉนด` | 1–6 digits (frozen by Task 1 — `docs/decisions/2026-08-26-wave1-format-specs.md`), cue-gated ONLY, value within 20 chars after the cue on the same line | 0.9 | cue BEFORE value `โฉนด(?:ที่ดิน)?\s*เลขที่\|เลขที่โฉนด\|น\.ส\.\s*[34]\s*(?:ก\|ข)?\s*เลขที่` | digits, length-preserving |

Version suppression for the IPv4 catch-all (the 0.8 step, not the cue-gated 0.9 step): skip the match when the char immediately before is `v`/`V`, or when `version|เวอร์ชัน|รุ่น|build` appears in the 30-char `_cue_before` window. A cue-gated 0.9 hit is never suppressed.

Shared rules for all three (identical to the 2026-08-26 five-type campaign):
- `redact_type="FP"`; value in regex **group 1** (`_make_entity` uses group 1).
- Membership in `SAFE_OUTBOUND_LEAK_TYPES` and `_OBFUSCATED_STRUCTURED_TYPES`.
- `canonical_value` folding: MAC_ADDRESS strips `:`/`-` and casefolds; LAND_DEED_ID digits-only fold; IP_ADDRESS casefold only (IPv6 letters) — whitespace-fold default branch covers the rest.
- Precedence (amended after Task 1): LAND_DEED_ID is 1–6 digits, so it never overlaps `_RE_STUDENT_ID` (8–12) — no student disambiguator is needed. The real collision is ADDRESS — the Task 1 probe shows `<deed number> ตำบล…` is already claimed at 0.85 by the address pass, so the 0.9 LAND_DEED_ID entity must win the deed digits in dedupe while the admin-area chain after it stays masked as ADDRESS/LOCATION — Task 2 must pin this with a test (deed digits → `LAND_DEED_ID`, and ตำบล/อำเภอ text still masked, not dropped by overlap dedupe). IPv4 never collides with existing digit detectors (dots break `(?<!\d)…(?!\d)` runs); MAC never collides (hex pairs + separators).

New QI spec (Level B rows "campaign Wave 1" in the ontology):

| QI key | Pattern (added to `_QI_PATTERNS` in `amphrang/engine/reid_risk.py`) |
|---|---|
| `nationality` | `re.compile(r"สัญชาติ\s*(?:ไทย\|ลาว\|พม่า\|เมียนมา\|กัมพูชา\|เขมร\|จีน\|เวียดนาม\|มาเลเซีย\|อินเดีย\|ญี่ปุ่น\|เกาหลี\|อเมริกัน\|อังกฤษ\|ฝรั่งเศส\|เยอรมัน\|[ก-๙]{2,12})", re.UNICODE)` |
| `body_metrics` | `re.compile(r"(?:น้ำหนัก\s*\d{2,3}(?:\.\d+)?\s*(?:กก\.?\|กิโลกรัม)\|ส่วนสูง\s*\d{2,3}\s*(?:ซม\.?\|เซนติเมตร))", re.UNICODE)` |

Baseline numbers (README, gold-v5, run 2026-08-26): overall n=788, R 0.985 / P 0.878 / F2 0.961 (CI 0.949–0.972); STUDENT_ID R 0.860; negative slice 15 FP / 31 of 45 clean. These are the regression floors.

---

### Task 1: Legal-format research + verdict freeze (opus)

**Files:**
- Modify: `docs/decisions/2026-08-26-pdpa-data-ontology.md` (the "Open verdicts" section becomes dated verdicts)
- Create: `docs/decisions/2026-08-26-wave1-format-specs.md`

**Interfaces:**
- Produces: verdicts `SSO_NUMBER: thai_id_alias|distinct|gap`, `PERSONAL_TIN: thai_id_alias|distinct|gap`, `LAND_DEED_SHAPE: <digits spec>|too_loose_to_ship`, each with sources; later tasks cite this record.

- [ ] **Step 1: เลขประกันสังคม** — research (WebSearch/WebFetch, พ.ร.บ.ประกันสังคม + สำนักงานประกันสังคม sources) whether the SSO insured-person number for Thai nationals is the 13-digit citizen ID (expected yes) and what foreign insured workers receive (SSO-issued 13-digit — check whether it passes the citizen mod-11). Verdict `thai_id_alias` means: no new detector, the ontology row says "covered via THAI_ID", and Task 6 must include gold docs where a citizen ID appears in a ประกันสังคม context to prove coverage. If foreign-worker numbers fail the checksum, record the gap honestly — do NOT loosen `_RE_THAI_ID`.
- [ ] **Step 2: เลขผู้เสียภาษีบุคคลธรรมดา** — verify personal TIN = citizen ID (Revenue Department rule, in force since 2012). Check whether legacy 10-digit TINs still appear on current documents; expected verdict: `thai_id_alias` + recorded legacy gap. Note the interplay already shipped: the `เลข(?:ประจำตัว)?ผู้เสียภาษี` cue near a 0-leading number yields JURISTIC_ID; near a 1–9-leading citizen ID the `_disambiguate_thai_juristic` pass keeps THAI_ID — confirm with one runtime probe (`detect_fp` on both cases) and quote the output in the record.
- [ ] **Step 3: เลขโฉนดที่ดิน** — verify the deed-number shape from กรมที่ดิน sources and real published deed examples (auction notices are public record). Freeze digits range (candidate 1–8) or verdict `too_loose_to_ship`. Never claim a checksum without 5 validated real examples.
- [ ] **Step 4: IP/MAC sanity pass** — no legal research needed (shapes are RFC-defined); confirm the ontology's PDPC-guidance basis line for IP addresses cites a source that actually says it (fix the citation if not).
- [ ] **Step 5: Write the record + amend the ontology** — `docs/decisions/2026-08-26-wave1-format-specs.md` with all verdicts, sources, probe output; replace the ontology's "Open verdicts" bullets with one-line dated verdicts pointing at the record. Commit (subject: `docs: freeze wave-1 format verdicts (SSO/TIN/land-deed)`).

### Task 2: Wave-1 detectors in fp_detector (opus)

**Files:**
- Modify: `amphrang/engine/detectors/fp_detector.py` (patterns beside the existing block near :250-421, cues near :423-563, steps appended after step 18 inside `detect_fp`, disambiguator beside `_disambiguate_driver_student`)
- Test: `tests/test_wave1_types_detection.py` (create)

**Interfaces:**
- Consumes: Task 1's verdicts (land-deed shape; skip the LAND_DEED_ID steps entirely on `too_loose_to_ship` and say so in the commit body).
- Produces: `detect_fp` emits `IP_ADDRESS`, `MAC_ADDRESS`, `LAND_DEED_ID` per the spec table; all `redact_type="FP"`, value in group 1.

- [ ] **Step 1: Write the failing tests** — create `tests/test_wave1_types_detection.py`:

```python
"""Detection contract for the wave-1 types (see the PDPA ontology ADR)."""

from amphrang.engine.detectors.fp_detector import detect_fp


def _types(text):
    return {(e.data_type, e.original_text) for e in detect_fp(text)}


def test_ipv4_with_cue_detected():
    found = _types("เชื่อมต่อจาก IP 192.168.1.44 เมื่อเวลา 10.30 น.")
    assert ("IP_ADDRESS", "192.168.1.44") in found


def test_ipv4_bare_catch_all_detected():
    found = _types("พบการเข้าถึงจาก 203.154.77.9 ในบันทึกระบบ")
    assert ("IP_ADDRESS", "203.154.77.9") in found


def test_version_string_is_not_an_ip():
    found = _types("อัปเดตเป็น v1.2.3.4 และรุ่น 10.15.7.2 แล้ว")
    assert not any(t == "IP_ADDRESS" for t, _ in found)


def test_octet_over_255_rejected():
    assert not any(t == "IP_ADDRESS" for t, _ in _types("ค่าคือ 300.1.2.3 หน่วยทดสอบ"))


def test_five_group_run_is_not_an_ip():
    assert not any(t == "IP_ADDRESS" for t, _ in _types("รหัสรุ่น 1.2.3.4.5 ตามคู่มือ"))


def test_ipv6_detected_without_cue():
    found = _types("บันทึกจาก 2001:0db8:85a3:0000:0000:8a2e:0370:7334 เข้าระบบ")
    assert any(t == "IP_ADDRESS" for t, _ in found)


def test_ipv6_compressed_detected():
    found = _types("ที่อยู่ 2001:db8::8a2e:370:7334 ปรากฏใน log")
    assert any(t == "IP_ADDRESS" for t, _ in found)


def test_mac_colon_form_detected():
    found = _types("อุปกรณ์ MAC 00:1B:44:11:3A:B7 ลงทะเบียนแล้ว")
    assert ("MAC_ADDRESS", "00:1B:44:11:3A:B7") in found


def test_mac_dash_form_detected():
    found = _types("หมายเลขเครื่อง 00-1b-44-11-3a-b7 ตรวจพบในระบบ")
    assert ("MAC_ADDRESS", "00-1b-44-11-3a-b7") in found


def test_time_range_is_not_a_mac():
    assert not any(t == "MAC_ADDRESS" for t, _ in _types("เวลา 10:15-11:30 น. ประชุม"))


def test_land_deed_with_cue_detected():
    found = _types("โฉนดที่ดินเลขที่ 12345 ตำบลบางรัก อำเภอเมือง")
    assert ("LAND_DEED_ID", "12345") in found


def test_bare_digits_without_deed_cue_not_land_deed():
    assert not any(t == "LAND_DEED_ID" for t, _ in _types("ใบสั่งซื้อเลขที่ 12345 ลงวันนี้"))
```

- [ ] **Step 2: Run to verify all fail** — `./.venv/Scripts/python.exe -m pytest tests/test_wave1_types_detection.py -q`; expected: every test fails on a missing type.
- [ ] **Step 3: Implement** — add compiled patterns + cue regexes per the spec table, three numbered steps after the last existing step in `detect_fp` (keep the numbered-comment idiom), the IPv4 version-suppression check via the existing `_cue_before` helper, and extend the driver/student disambiguator family with the โฉนด cue set for the 8-digit overlap. IPv6 pattern: full form `(?:[0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}` plus compressed `(?=[0-9A-Fa-f:]*::)(?:[0-9A-Fa-f]{1,4}:?)+:(?:[0-9A-Fa-f]{1,4}:?)*` guarded by alnum boundaries — Opus may substitute a cleaner equivalent, but MUST keep `test_five_group_run_is_not_an_ip` and the time-range MAC test passing.
- [ ] **Step 4: Full suite + gold regression** — `pytest -q` all green; `python -m benchmark --source gold` shows every per-type row at or above the baseline table and the negative slice still exactly 15 FP / 31 of 45.
- [ ] **Step 5: Commit** — subject `feat: detect IP_ADDRESS, MAC_ADDRESS, LAND_DEED_ID`; body quotes the gold OVERALL and negative-slice lines.

### Task 3: Generators + labels + guard sets (sonnet)

**Files:**
- Modify: `amphrang/engine/anonymizer/fp_generator.py`, `amphrang/engine/anonymizer/token_generator.py` (TOKEN_LABEL), `amphrang/engine/leak_guard.py` (`SAFE_OUTBOUND_LEAK_TYPES`, `_OBFUSCATED_STRUCTURED_TYPES`), `amphrang/engine/scan_common.py` (`canonical_value`), `amphrang/engine/models.py` (docstring vocab)
- Test: `tests/test_wave1_types_roundtrip.py` (create)

**Interfaces:**
- Consumes: Task 2's entities.
- Produces: full round-trip (mask → surrogate/token → restore) for the three types; TOKEN_LABEL gains `IP_ADDRESS: "ไอพี"`, `MAC_ADDRESS: "แมคแอดเดรส"`, `LAND_DEED_ID: "โฉนด"`.

- [ ] **Step 1: Write the failing round-trip tests** — mirror `tests/test_new_types_roundtrip.py` (same structure, same helper style) for the three types: surrogate mode replaces the value with a same-shape fake (assert the original is absent and the surrogate matches the shape regex), token mode emits `[ไอพี_…]`-style tokens, `restore` returns the exact original, and `scan_outbound_leaks` accepts the masked text (no leak block). Include one MAC value in `-` form to pin separator preservation.
- [ ] **Step 2: Run to verify they fail**, then implement — `_gen_ip_address` / `_gen_mac_address` / `_gen_land_deed` + elif branches in `generate_fp` using the spec-table surrogates; TOKEN_LABEL entries; both leak-guard set memberships; `canonical_value` branches (MAC strip separators + casefold, LAND_DEED digits-fold, IP casefold).
- [ ] **Step 3: Full suite green** — `pytest -q`; then commit (subject: `feat: round-trip + guard coverage for wave-1 types`).

### Task 4: QI extension in reid_risk (sonnet)

**Files:**
- Modify: `amphrang/engine/reid_risk.py:17-25` (`_QI_PATTERNS`)
- Test: `tests/test_reid_risk.py` (extend the existing file if present; create otherwise)

**Interfaces:**
- Produces: `assess_reid_risk` reports `nationality` and `body_metrics` in `qi_found`; `analyze()` surfaces them with no facade change.

- [ ] **Step 1: Failing tests** —

```python
from amphrang.engine.reid_risk import assess_reid_risk


def test_nationality_is_a_qi():
    result = assess_reid_risk("ผู้สมัคร สัญชาติไทย อาศัยในกรุงเทพ")
    assert "nationality" in result.qi_found


def test_body_metrics_are_a_qi():
    result = assess_reid_risk("น้ำหนัก 62 กก. ส่วนสูง 171 ซม.")
    assert "body_metrics" in result.qi_found


def test_borderless_word_is_not_nationality():
    result = assess_reid_risk("บริษัทข้ามสัญชาติขยายกิจการ")
    assert "nationality" not in result.qi_found
```

- [ ] **Step 2: Verify fail, implement** — add the two `_QI_PATTERNS` rows exactly as the QI spec table defines (the `สัญชาติ\s*…` pattern requires a following nationality word or a 2–12-char Thai run, which the "ข้ามสัญชาติ" compound does not satisfy because the cue must start the match — confirm with the test; if the compound still matches, add `(?<![ก-๙])` before `สัญชาติ`).
- [ ] **Step 3: Full suite + negative-slice check** — `pytest -q` green; `python -m benchmark --source gold` negative slice unchanged (QIs never mask, but confirm anyway since `analyze` scoring feeds no benchmark — quote the line). Commit (subject: `feat: nationality and body-metrics quasi-identifiers`).

### Task 5: Corpus templates + samplers (sonnet)

**Files:**
- Modify: `benchmark/types.py` (SHARED_ENTITY_TYPES 16→19), `benchmark/corpus.py` (samplers + templates appended at END), `benchmark/llm_strategy.py` (prompt bullets)
- Test: `tests/test_corpus_determinism.py` (extend if present; otherwise assert via the existing corpus tests)

**Interfaces:**
- Produces: synthetic corpus can emit the three new types; slot keys `ip_address`, `mac_address`, `land_deed_id`.

- [ ] **Step 1: Failing test** — extend the corpus test file with one test per new slot key asserting a generated doc containing the slot yields a gold span of the right type, following the exact pattern the five 2026-08-26 types used in their corpus tests.
- [ ] **Step 2: Implement** — samplers keyed by type (IPv4 from `10.x.y.z`, MAC six hex pairs, deed digits per Task 1 shape), two templates appended at the END of `_CORE_TEMPLATES` ("it_incident" — a network-incident report using IP/MAC in Thai prose; "land_transaction" — a sale-agreement excerpt using the deed number), llm_strategy bullets for the three types.
- [ ] **Step 3: Byte-identity check** — regenerate the synthetic corpus twice, diff for determinism, and confirm pre-existing docs are byte-identical to before the change (append-only rule). Quote the diff result in the commit body. Commit (subject: `bench: wave-1 types in synthetic corpus`).

### Task 6: Gold slice authoring — digital_ids, gold-v6 (sonnet)

**Files:**
- Modify: `benchmark/data/gold.jsonl` (append ~24 docs, ids `dg01`–`dg24`), `benchmark/gold.py` (GOLD_VERSION → `gold-v6`, SLICE_LAYERS + `"digital_ids": "balanced"`)

**Interfaces:**
- Consumes: annotation guidelines (`docs/` benchmark guidelines as amended 2026-08-26) + Task 1 verdicts.
- Produces: ≥20 gold entities per new type (`_MIN_PER_TYPE=20`), value-uniqueness respected.

- [ ] **Step 1: Author the slice** — ~24 Thai documents in `[[TYPE|value]]` markup: IT-incident reports, router configs quoted in email prose, land-office letters. Every doc mixes at least one existing type (NAME/PHONE/ADDRESS) so cross-type interference is exercised. Include the Task-1 alias proofs: ≥3 docs with a citizen ID in ประกันสังคม/ผู้เสียภาษี context annotated `[[THAI_ID|…]]` (NOT a new type). Include look-alike traps unannotated: a version string `v2.4.1.9`, a time range `10:15-11:30`, a PO number near เลขที่ without a โฉนด cue.
- [ ] **Step 2: Bump gold-v6 + run** — `python -m benchmark --source gold`; every new type ≥20 n; existing per-type rows at or above baseline; negative slice exactly 15 FP / 31 of 45.
- [ ] **Step 3: Commit** — subject `bench: gold-v6 digital_ids slice (24 docs)`; body quotes the three new per-type rows and OVERALL.

### Task 7: Wave-1 measurement checkpoint (sonnet — run + report, no code)

- [ ] **Step 1: Full verification run** — `pytest -q` (expect ≥ current 1763 passing), `scripts/check_release.py` GATE-OK, `python -m benchmark --source gold` full table.
- [ ] **Step 2: Report to the orchestrator** — per-type rows for the three new types, OVERALL vs the 0.985/0.878/0.961 baseline, negative-slice line, and any row that moved. NO fixes in this task — a regression stops the campaign and returns to the orchestrator for a diagnosis task. Nothing to commit unless numbers belong in the plan checklist (checkbox ticks only).

### Task 8: ม.26 span-masking design spike (opus)

**Files:**
- Create: `docs/decisions/2026-08-26-section26-span-masking.md`
- Scratch prototypes live in the session scratchpad, never in the repo.

**Interfaces:**
- Consumes: `report.py::_SECTION26_KEYWORDS` (10 categories), `sensitive_detector.py` (semantic, `[ml]`-only), the ontology's Level-C section.
- Produces: a frozen design record that Tasks 9–10 implement verbatim; the orchestrator amends Tasks 9–10 from it before dispatch.

The candidate design to validate (the spike may refute any part with evidence):

1. New module `amphrang/engine/detectors/sensitive_span.py`, function `detect_sensitive_spans(text: str, person_spans: list[tuple[int, int]]) -> list[Entity]`.
2. **Person-linkage rule**: a sensitive keyword hit becomes an entity only when its sentence/segment (split on `\n` and Thai sentence spacing) also contains a person anchor — an overlap with a NAME/SURNAME entity span, or a personal reference (`นาย|นาง|นางสาว|ผม|ดิฉัน|ข้าพเจ้า|ผู้ป่วย|ผู้ต้องหา|จำเลย|ลูกจ้าง|พนักงาน`). "วันสำคัญทางศาสนา" in impersonal prose never flags.
3. **Span shape**: the keyword phrase expanded to its space/punctuation-bounded segment (a diagnosis phrase, not the whole sentence).
4. **Labels**: the 10 existing category names (`HEALTH`, `CRIMINAL_RECORD`, …) — they are already reserved in `leak_guard.py`/`http_v2.py` allowlists; `redact_type="FP"`; TOKEN_LABEL additions with Thai labels (`ข้อมูลสุขภาพ`, `ประวัติคดี`, `ความพิการ`, `ข้อมูลพันธุกรรม`, `ข้อมูลชีวภาพ`, `ศาสนา`, `เชื้อชาติ`, `พฤติกรรมทางเพศ`, `ความเห็นการเมือง`, `สหภาพแรงงาน`).
5. **Masking semantics**: token mode = normal token; surrogate mode = the category-generic Thai phrase in brackets is NOT acceptable (breaks surrogate realism) → spike must decide between (a) token-style replacement even in surrogate mode, or (b) a fixed neutral phrase per category; record the choice and its restore semantics.
6. **Default**: ON in `detect()`/`anonymize()` (recall-first), with the negative-slice zero-new-flags budget as the precision gate. If the spike cannot hold that budget, the fallback design is opt-in via an engine-level switch (NOT a facade change unless unavoidable — see Global Constraints).

- [ ] **Step 1: Build the dev set** — author 40 person-linked sensitive spans + 30 impersonal near-misses (scratchpad file), covering all 10 categories, before writing any detector code.
- [ ] **Step 2: Prototype + measure** — implement the candidate in the scratchpad against `detect_fp`/NER outputs; report recall on the 40 and false flags on the 30 and on the 45-doc negative gold slice. Acceptance to freeze: dev recall ≥ 0.90, impersonal false flags ≤ 2 of 30, negative slice +0.
- [ ] **Step 3: Decide leak-guard interplay** — masked sensitive spans must not trip `scan_residual_signals` (the replacement text is category words — verify the rescan does not re-flag it); record the required allowlist wiring.
- [ ] **Step 4: Write the decision record** — accepted design (or the measured fallback), the dev-set numbers, exact module/function signatures, TOKEN_LABEL rows, guard wiring, and the facade verdict (knob or no knob). Commit (subject: `docs: freeze ม.26 span-masking design (dev R=<x>)`).

### Task 9: Sensitive-span detector implementation (opus — dispatch only after the orchestrator amends this task from Task 8's record)

**Files:**
- Create: `amphrang/engine/detectors/sensitive_span.py`
- Modify: `amphrang/engine/aggregate.py` (wire into the detect pipeline per the record), `token_generator.py` (TOKEN_LABEL rows from the record), `leak_guard.py` (wiring from the record), `fp_generator.py` or the record's chosen masking path
- Test: `tests/test_sensitive_span.py` (create)

**Interfaces:**
- Consumes: Task 8's record verbatim.
- Produces: `detect()` emits person-linked sensitive spans; `anonymize()` masks them; round-trip restore intact.

- [ ] **Step 1: Failing tests from the record's dev set** — port ≥12 dev-set cases (mix of all 10 categories, plus ≥4 impersonal near-misses asserting NO entity) into `tests/test_sensitive_span.py`; one round-trip test (anonymize → assert diagnosis absent → restore → exact original); one leak-guard test (masked output passes `scan_outbound_leaks`).
- [ ] **Step 2: Verify fail, implement per the record, verify pass** — no design departures without returning to the orchestrator.
- [ ] **Step 3: Full suite + gold** — `pytest -q` green; gold run: all baselines hold, negative slice +0. Commit (subject: `feat: person-linked ม.26 sensitive-span masking`).

### Task 10: Sensitive gold slice + guidelines addendum — gold-v7 (opus)

**Files:**
- Modify: the benchmark annotation guidelines doc (add a "sensitive spans" section defining span boundaries and the person-linkage rule as annotation law), `benchmark/data/gold.jsonl` (append ~22 docs, ids `sv01`–`sv22`), `benchmark/gold.py` (GOLD_VERSION → `gold-v7`, slice `"sensitive": "balanced"`), `benchmark/types.py` (add the 10 category labels to the scored set per the guidelines decision)

- [ ] **Step 1: Guidelines first** — write the annotation addendum BEFORE authoring docs (span = bounded phrase; impersonal mentions unannotated; mixed docs annotate both the person and the sensitive span).
- [ ] **Step 2: Author ~22 docs** — medical certificates, HR records, court summaries, temple/union membership prose; every doc person-linked; ≥20 sensitive spans total across categories (per-category minimums are NOT required in v7 — record that as a known limit); include ≥6 impersonal near-miss docs annotated with zero sensitive spans.
- [ ] **Step 3: gold-v7 run + commit** — full gold table; sensitive-category recall/precision reported; baselines hold; negative slice +0. Subject `bench: gold-v7 sensitive slice (22 docs)`.

### Task 11: PDPA Coverage Profile + CI gate (sonnet)

**Files:**
- Create: `docs/pdpa-coverage.md`
- Modify: `scripts/check_release.py` (add `check_profile()`), `.github/workflows/ci.yml` only if the lint job does not already run the whole script
- Test: `tests/test_check_release.py` (extend if present; otherwise the script's own `GATE-OK` path is the test — run it both green and deliberately broken)

**Interfaces:**
- Consumes: the ontology record + the gold-v7 measured table.
- Produces: the public conformance artifact; CI fails when the profile and the code disagree.

- [ ] **Step 1: Write `docs/pdpa-coverage.md`** — one table per ontology level. Level A rows: `| data_type | Thai label | PDPA basis | gold recall | gold precision |` with numbers copied from the latest gold run, `unmeasured` written out for IBAN/MEDICAL_ID, and JURISTIC_ID footnoted "outside PDPA scope (juristic person) — business-confidentiality feature". Levels B–E copied from the ontology with their mechanisms. Header states the profile version (`pdpa-profile-v1`), the gold version it was measured on, and the rule that PDPC catch-all announcements enter by dated amendment.
- [ ] **Step 2: `check_profile()` in `check_release.py`** — AST-parse `TOKEN_LABEL` keys from `amphrang/engine/anonymizer/token_generator.py` (same no-import trick as `check_surface`), parse the backticked names in the profile's Level-A table, and fail with a named diff unless the sets match exactly (fallback labels included). Wire it into the script's main sequence so GATE-OK implies profile consistency.
- [ ] **Step 3: Prove the gate bites** — temporarily remove one profile row, run the script, quote the failure line in the commit body, restore the row, re-run to GATE-OK. Commit (subject: `docs+ci: pdpa-coverage profile v1, gated by check_release`).

### Task 12: Docs sweep + final verification (sonnet; orchestrator re-verifies independently)

**Files:**
- Modify: `README.md` ("What it detects" — three new types + sensitive-span sentence + a "PDPA coverage" pointer to `docs/pdpa-coverage.md`; "Measured accuracy" — full gold-v7 table, dated), `CHANGELOG.md` (Unreleased: Added entries for wave-1 types, QIs, sensitive-span masking, coverage profile), `docs/decisions/README.md` (rows for the three new records)

- [ ] **Step 1: README + CHANGELOG** — keep the blind paragraph byte-identical; extend its trailing clause so the predate list covers everything added 2026-08-26 in this campaign as well.
- [ ] **Step 2: Full final run** — `pytest -q`, `check_release.py` (now including the profile gate), `python -m benchmark --source gold`; quote all three outputs in the commit body. Subject `bench+docs: publish pdpa-profile-v1 coverage and gold-v7 accuracy`.
- [ ] **Step 3: Orchestrator verification** — the orchestrator (not this task) independently re-runs the three commands and compares before declaring the campaign done.

---

## Self-review notes (written at planning time)

- Spec coverage: every "campaign Wave 1/2/3" row in the ontology maps to a task (IP/MAC/LAND_DEED → 2–7; nationality/body_metrics → 4; ม.26 spans → 8–10; profile → 11; publication → 12). SSO/TIN aliases are covered by Task 1 verdicts + Task 6 alias-proof docs.
- Tasks 9–10 are deliberately amendment-gated on Task 8 — the same pattern the 2026-08-26 campaign used for its Task 1; the orchestrator must amend before dispatch, and the candidate design above is concrete enough to execute if the spike confirms it unchanged.
- Type-name consistency: `IP_ADDRESS`/`MAC_ADDRESS`/`LAND_DEED_ID` and the QI keys `nationality`/`body_metrics` are spelled identically in every task; TOKEN_LABEL Thai labels appear once in the spec table and once in Task 3.

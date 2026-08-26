# ม.26 person-linked sensitive-span masking — frozen design

Date: 2026-08-27. Campaign: PDPA-standard, Wave 2, Task 8 (design spike).
Status: **accepted and frozen**. Tasks 9 and 10 implement this record verbatim;
a departure returns to the orchestrator rather than being decided in the
implementing task.

This record closes the gap the data ontology
(`2026-08-26-pdpa-data-ontology.md`, Level C) names as the flagship: ม.26
sensitive content is flagged at document level but forwarded verbatim by the
sanitizing proxy. A document saying "นายสมชายเป็นมะเร็ง" masks the name and
ships the diagnosis. After Task 9 the diagnosis becomes a maskable span when,
and only when, its segment is linked to a person.

Everything below was measured in the session scratchpad against a purpose-built
dev set and the real gold corpus. No production code was changed by this task.

---

## 1. Acceptance measurements

| Gate (from the campaign plan) | Target | Measured | Verdict |
|---|---|---|---|
| Dev recall on 40 person-linked spans | ≥ 0.90 | **0.925 (37/40)** | pass |
| False flags on 30 impersonal near-misses | ≤ 2 of 30 | **0 of 30** | pass |
| Negative gold slice (45 docs) delta | +0 | **+0** (`false_positives=15 clean_docs=31/45`) | pass |

Supporting numbers from the same run:

- Character coverage of the 40 gold dev spans (`R_mask`, the safety view): **0.900**.
- Over-masking: **+0.03x** of gold span length (20 characters over, 10 under,
  across 40 spans).
- Gold-v6 behaviour: **12** sensitive spans fired across 304 documents,
  **0** of them in the `negative` slice.
- Full gold table with the design patched in: every per-type row byte-identical
  to the Task-7 reference; `shared_11 R=0.987 P=0.992 F2=0.988` unchanged.
  `OVERALL` precision moves 0.879 → 0.868 only because gold-v6 carries no
  sensitive annotations, so all 12 predictions land in the `OUT_OF_SCHEME`
  bucket (`excluded` 116 → 128). Task 10 converts them into scored spans.
- End-to-end over the 40 dev positives in `mode="surrogate"`: **0/40** outbound
  guard failures, **0/40** restore failures, **0/40** new output-validator
  failures (with the Section 6 change; without it, 2/40 — see there).
- Existing suite with the Section 6 output-validator change applied in memory:
  **1817 passed, 9 skipped** — identical to the Task-7 baseline.

### Dev set

40 person-linked sensitive spans + 30 impersonal near-misses, 4 positives and
3 negatives per category for all ten categories, authored before any detector
code. Person anchors are deliberately mixed (8 bare full name, 5 title+name,
11 first-person pronoun, 16 role reference). The set lives in the session
scratchpad; **Task 9 Step 1 ports ≥ 12 positives covering all ten categories
plus ≥ 4 near-misses into `tests/test_sensitive_span.py`**, and Task 10 reuses
the near-misses as impersonal gold documents.

---

## 2. What the candidate design got right, and what the evidence refuted

The brief carried a six-point candidate. Points 1, 2 (in outline), 3 (in
outline) and 6 survive. Points 4 and 5 are refuted in part, and the exact
formulation of 2 and 3 is refuted with measurements.

| Candidate | Verdict | Evidence |
|---|---|---|
| 1. New module + `detect_sensitive_spans(text, person_spans)` | **accepted**, with a second exported function (Section 3) | — |
| 2. Anchor list `นาย\|นาง\|…\|พนักงาน`, segment split on `\n` and Thai sentence spacing | **accepted in outline, refuted as written** | the flat anchor list false-flags **2 of 30** near-misses; the tiered rule flags **0 of 30**. Splitting on *any* whitespace run drops recall to **0.550**; splitting on newline / double space keeps **0.925** |
| 3. Span = the keyword expanded to its space/punctuation-bounded **segment** | **refuted** | the segment shape swallows the anchor itself, and with a self-anchoring rule recall collapses to **0.375**; it also over-masks **+0.68x** vs **+0.03x** for the accepted forward-only shape |
| 4. Labels already reserved in `leak_guard.py`/`http_v2.py`; `redact_type="FP"` | **both halves refuted** | only 4 of 10 names are in `SAFE_OUTBOUND_LEAK_TYPES` today (Section 6); `redact_type` must be `"TB"`, not `"FP"` (Section 5) |
| 5. Surrogate mode: choose token-style or a fixed neutral phrase | **decided: token-style (option a)**; option (b) is not merely undesirable, it **crashes** | a fixed phrase per category raises `ValueError: unable to generate a unique pseudonym … after 64 attempts` on any document with two spans of one category |
| 6. Default ON, no facade knob unless the budget fails | **accepted**, budget held | negative slice +0 |

---

## 3. Module and signatures (Task 9 implements exactly these)

`amphrang/engine/detectors/sensitive_span.py`

```python
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


def detect_sensitive_spans(
    text: str,
    person_spans: list[tuple[int, int]],
    *,
    blocked_spans: list[tuple[int, int]] | None = None,
) -> list[Entity]:
    """Person-linked ม.26 spans, sorted by start, never overlapping each other."""


def merge_sensitive_spans(
    text: str,
    kept: list[Entity],
    sensitive: list[Entity],
) -> list[Entity]:
    """Fold sensitive spans into the pipeline's entity list without uncovering
    a single character. Sorted by start, non-overlapping."""
```

`person_spans` are the `NAME`/`SURNAME` spans the pipeline already produced.
`blocked_spans` are the retained `FP` spans; a sensitive candidate is trimmed
away from them and dropped when nothing survives, so a `THAI_ID` inside a
sensitive phrase always stays `THAI_ID`.

`amphrang/engine/detectors/aggregate.py` — the wiring is the **last** step of
`detect_all`, after `_relabel_student_ids`:

```python
kept = _relabel_student_ids(tb, kept)
sensitive = detect_sensitive_spans(
    text,
    [e.span for e in kept if e.data_type in ("NAME", "SURNAME")],
    blocked_spans=[e.span for e in kept if e.redact_type == "FP"],
)
return merge_sensitive_spans(text, kept, sensitive)
```

Sensitive spans deliberately **do not go through `dedupe_spans`**. That keeps
the existing ensemble's output untouched up to the final merge, which is why
every per-type gold row is byte-identical.

### Pattern table

The span detector owns its own table. `report.py::_SECTION26_KEYWORDS` is **not**
touched — it is the document-level flag scan that `analyze()` and the HTTP
`section26_categories` field are pinned to, and it stays byte-identical.

```python
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
```

Two departures from the flag table, both required:

1. **`RACE_ETHNICITY` drops `สัญชาติ` and gains `ชาติพันธุ์|ชนเผ่า`.** Nationality
   is a Level-B quasi-identifier in the ontology (a Wave-1 `_QI_PATTERNS` entry),
   not a ม.26 category; masking it here would double-treat one field under two
   levels. `ชาติพันธุ์` is the ordinary Thai word for ethnicity and the flag table
   never had it.
2. **Category-error veto for `HEALTH`.** `สุขภาพ` also names the condition of a
   machine. Gold `dg03` reads "ระหว่างการตรวจสอบสุขภาพระบบประจำสัปดาห์" in an IT
   incident report. A hit is dropped outright when the match is immediately
   followed by `ระบบ|เครื่อง|เซิร์ฟเวอร์|เครือข่าย|อุปกรณ์|ฐานข้อมูล|แอปพลิเคชัน|ไอที`.
   This is a category error (not a natural person), not a boundary judgement,
   so it is a drop and not a trim.

---

## 4. The two rules that do the work

### 4.1 Segment scope

A sensitive hit and its anchor must share a **segment**:

```python
_SEGMENT_SPLIT = re.compile(r"[\n\r]+|(?<=[.;])\s|  +", re.UNICODE)
```

Newline, a period or semicolon followed by whitespace, or a run of **two or
more** spaces. A **single** space never splits. Thai marks a sentence end with
a double space or a newline; a single space is an intra-sentence phrase break,
and a name sits one space from its predicate in almost every real document.

Measured (dev set, everything else held fixed):

| Segment rule | dev R_span | gold-v6 sensitive spans |
|---|---|---|
| newline / `.`,`;`+space / 2+ spaces (**accepted**) | **0.925** | 12 |
| any whitespace run (the literal reading of the brief) | 0.550 | 4 |
| no split at all | 0.925 | 21 |

The dev set cannot separate the accepted rule from "no split" — its documents
are single-segment by construction. The gold corpus can: without segmentation
the detector fires 21 times instead of 12, the extra 9 coming from an anchor in
an unrelated part of a long document. That is the precision case for the rule,
and it is a measurement, not an assertion.

### 4.2 Two-tier person linkage

An anchor that lies **inside** the sensitive hit never counts — a phrase cannot
anchor itself. (The same principle as `_drop_unanchored_facility_spans`, which
blanks facility spans so they cannot be their own register evidence.) This one
rule alone kills the `สมาคมลูกจ้างในประเทศไทย` near-miss, where the only
"person" word is the `ลูกจ้าง` inside the union's own name.

**Tier 1 — never vetoed.**

- an overlap with a retained `NAME`/`SURNAME` span that is not swallowed by the hit;
- a first-person pronoun `ผม|กระผม|ดิฉัน|ข้าพเจ้า|หนู` — self-reference never occurs
  in institutional prose;
- a title immediately followed by a Thai given name:
  `(?:นาย|นาง|นางสาว|น\.ส\.|ด\.ช\.|ด\.ญ\.)\s?(?!จ้าง|ทะเบียน|อำเภอ|ก\.|กเทศ|แพทย์|ประกัน)[ก-ฮ][ก-๙]{1,20}`.
  The negative lookahead is why the brief's bare `นาย` is not enough — `นายจ้าง`,
  `นายทะเบียน`, `นายอำเภอ` are not references to a person.

**Tier 2 — role references, vetoable.**

`ผู้ป่วย|ผู้ต้องหา|จำเลย|โจทก์|ผู้เสียหาย|ลูกจ้าง|พนักงาน|ผู้เอาประกัน|ผู้รับบริการ|เจ้าของข้อมูล|ผู้สมัคร|นักเรียน|นักศึกษา`

- **Promoted to tier 1** when followed within 12 characters by a specificity
  marker `รายนี้|คนนี้|ท่านนี้|ผู้นี้|ดังกล่าว|ชื่อ|รายดังกล่าว` — that is a specific
  individual, and the veto no longer applies.
- **Vetoed** when the text between the segment start and the role word ends in
  an organization-forming word
  `สมาคม|สหภาพ|สหพันธ์|ชมรม|กลุ่ม|กองทุน|มูลนิธิ|เครือข่าย|สภา|สำนักงาน|ศูนย์|กรม|กระทรวง`
  — the role word is part of an organization name.
- **Vetoed** when the segment carries an impersonal institutional register:
  `ประกาศ|กฎกระทรวง|พระราชบัญญัติ|พ\.ร\.บ\.|ระเบียบ|ข้อบังคับ|แนวทาง|แนวปฏิบัติ|หลักสูตร|รายวิชา|มาตรฐาน|งานวิจัย|สถิติ|นิทรรศการ|บรรทัดฐาน|ประมวลกฎหมาย|มาตรา\s*\d|งบประมาณ|แบบสำรวจ|สัมมนา|ตีพิมพ์|เผยแพร่|ทั่วประเทศ|ในประเทศไทย`.
  This kills "แนวทางการรักษาผู้ป่วยไข้เลือดออก" in a ประกาศ from กรมควบคุมโรค,
  which the flat anchor list flags.

The register veto applies to **tier-2 anchors only**. A real named person in a
regulatory document is still a person: "นายสมชาย ใจดี ระบุเชื้อชาติกะเหรี่ยง
ในแบบฟอร์ม" flags, and must.

The register vocabulary is the part of this design most exposed to
over-fitting: it was written against 30 authored near-misses. Its independent
check is the 45-document negative gold slice, where it costs nothing (+0). Task
10 must widen that check with ≥ 6 impersonal gold documents; if the vocabulary
turns out to be brittle there, the fix is a Task-10 finding, not a Task-9
improvisation.

### 4.3 Span shape — forward-only, capped

```
start = the keyword match start        # never expands backwards
end   = the next boundary character in [\s,;.()\[\]/\\|"'“”‘’<>{}!?:]
        clamped at the segment end and at the nearest neighbouring entity
if end - start > MAX_SPAN_CHARS (48):
        re-cut with pythainlp newmm word tokens, stopping at the first
        Thai function word in the stop set
if still > MAX_SPAN_CHARS:
        truncate at the last whole token inside the cap
```

Stop set (used only in the overrun fallback):
`มา เมื่อ ตั้งแต่ จาก ใน และ จึง ของ ต่อ อย่าง ไว้ เพื่อ แต่ โดย ซึ่ง หลัง ก่อน ขณะ จน หรือ กับ แล้ว ยัง ทั้งนี้ ส่วน รวมทั้ง`

Why forward-only rather than the brief's whole segment: the anchor sits *before*
the keyword in nearly every Thai construction ("ผู้ป่วยรายนี้มี**ประวัติการรักษา**…"),
so a backward-expanding span eats its own anchor. Measured cost of the segment
shape: recall 0.375 and over-masking +0.68x, against 0.925 and +0.03x.

Why whitespace-bounded rather than always tokenizing: measured over the 40 dev
spans, the whitespace rule over-masks 20 characters and under-masks 10; the
token rule over-masks 3 and under-masks **40**. Under-masking is a leak,
over-masking is only lost utility, so recall-first picks whitespace. The
tokenizer stays as the overrun fallback because Thai is frequently written
without spaces, where a pure whitespace rule would mask a whole line. On the
dev set the cap never fires; it is a bound on the worst case, not a tuning knob.

Boundary quality on the dev set: 34 of 40 spans reproduce the authored gold
boundary exactly. The six that differ are `ต้องโทษจำคุก` (gold `ต้องโทษจำคุก 2 ปี`),
`คนพิการประเภทที่` (gold `… ที่ 3`), `ถูกฟ้องคดีฉ้อโกง` (gold `ฟ้องคดีฉ้อโกง`),
`ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน` (gold `ดีเอ็นเอตรงกับ…`), `พันธุกรรม`
(gold `สารพันธุกรรม`) and `โรคเบาหวานมาห้าปีแล้ว` (gold `โรคเบาหวาน`). The residue
left unmasked in the under-cut cases (" 2 ปี", " 3", "สาร") carries no ม.26
content on its own. Task 10's annotation addendum settles these boundaries as
annotation law; **Task 9 must not tune the span rule to them.**

### 4.4 Merge — `merge_sensitive_spans`

Three rules, in order:

1. A sensitive candidate is trimmed away from every retained **FP** entity and
   from every retained **TB** entity that is not one of the three honest-fallback
   labels; dropped when nothing survives.
2. A retained TB entity of `LOCATION`, `ORGANIZATION` or `DATE` **yields** its
   overlapping characters to the sensitive span, and keeps its non-overlapping
   remainder as an entity of its own type (dropped when nothing remains). Those
   three labels are the ontology's declared "honest-labels catch-alls, not PDPA
   categories themselves", so a ม.26 claim on the same characters is strictly
   more specific. This is the `_relabel_student_ids` precedent applied to a
   partial overlap.
3. Sensitive candidates never overlap each other; the first one claimed wins.

**Invariant, and Task 9 must pin it as a test:** the merge never uncovers a
character and never produces overlapping spans. Verified over 1122 (document,
policy) pairs — all 70 dev documents and all 304 gold documents, under all three
merge policies considered — with **zero** violations.

Rule 2 is what carries the design over the recall gate: without it, dev recall
is 0.850; restricting it to full containment gives 0.875; with it, 0.925. It
fires on **0 of 304** gold-v6 documents, so it carries no measured regression
risk, and correspondingly it is untested on real data outside the dev set. That
asymmetry is deliberate and recorded rather than hidden.

---

## 5. Labels, `redact_type`, and masking semantics

### 5.1 `redact_type = "TB"` — the brief's `"FP"` is refuted

Three measurements:

1. `generate_fp("HEALTH", "โรคเบาหวาน", salt=…)` returns `'vujefkbjzc'`, and
   `"ศาสนาอิสลาม"` returns `'bvsgidิzxcd'`. `_gen_generic` preserves the character
   class, and Thai letters are `isalpha()`, so an `FP` sensitive entity that ever
   reached the format-preserving path would emit Latin mojibake of the same
   length — not obviously redacted, and shape-preserving of the very content we
   are removing. `generate_tb`'s fallback returns `'[REDACTED_HEALTH]'`, which is
   English and blunt but unmistakably a redaction. **`TB` fails safe, `FP` does not.**
2. `enforce_outbound_policy` maps `redact_type == "FP"` to the policy category
   `"structured"` and everything else to `"text"`. A ม.26 phrase is prose, not a
   structured identifier; `TB` produces the honest category.
3. The FP branch of `_generate_unique_pseudonym` may never take a `#N` collision
   suffix and re-rolls to exhaustion; the TB branch may. See 5.3.

`TB` is also the safer tier if a future change ever routes these entities through
`dedupe_spans`: FP-first ordering means an `FP` sensitive span could displace a
precise structured hit it overlaps, which `TB` cannot.

Everything else about the entity: `score = 0.9`, `data_type` one of the ten
names, `original_text` the exact source slice.

### 5.2 `TOKEN_LABEL` rows

Added to `amphrang/engine/anonymizer/token_generator.py`, in this order, at the
end of the existing table:

| `data_type` | Thai token label |
|---|---|
| `HEALTH` | `ข้อมูลสุขภาพ` |
| `CRIMINAL_RECORD` | `ประวัติคดี` |
| `DISABILITY` | `ความพิการ` |
| `GENETIC` | `ข้อมูลพันธุกรรม` |
| `BIOMETRIC` | `ข้อมูลชีวภาพ` |
| `RELIGION` | `ศาสนา` |
| `RACE_ETHNICITY` | `เชื้อชาติ` |
| `SEXUAL_BEHAVIOR` | `พฤติกรรมทางเพศ` |
| `POLITICAL_OPINION` | `ความเห็นการเมือง` |
| `LABOR_UNION` | `สหภาพแรงงาน` |

Verified: no collision with any existing label, all ten unique among themselves,
and each round-trips through `generate_token` →
`token_data_type_from_candidate` / `is_token_for_data_type` /
`token_ordinal_from_candidate`. Sample:
`[ข้อมูลสุขภาพ_bbfcbafccdfbccddcbcbbaccc_pvtipfxoluzfogjrsioc_1]`.

Recorded hazard: **8 of these 10 labels are themselves ม.26 span keywords**
(`ข้อมูลสุขภาพ` contains `สุขภาพ`, `ความพิการ` and `ศาสนา` and `เชื้อชาติ` and
`สหภาพแรงงาน` and `ข้อมูลชีวภาพ` are keywords outright, `ข้อมูลพันธุกรรม` contains
`พันธุกรรม`, `ประวัติคดี` contains `คดี`; only `พฤติกรรมทางเพศ` and
`ความเห็นการเมือง` are clean). A re-scan of masked text therefore re-flags the
replacement token itself. This is safe only because the hit is positionally
contained in a trusted pseudonym occurrence — see Section 6. **Task 9 must not
change a token label without re-checking this**, and `scripts/check_release.py`
already gates `TOKEN_LABEL` against the coverage profile, so Task 11 will pick
up a drift.

### 5.3 Masking is a token in **both** modes

`anonymize()` routes by **`data_type`**, not by mode:

```python
if mode == "token" or entity.data_type in SENSITIVE_DATA_TYPE_SET:
    pseudonym = _next_token(entity, text, vault, compact_text)
else:
    pseudonym = _generate_unique_pseudonym(...)
```

`vault.token_namespace` is available in both modes (it is minted in
`SessionVault.__init__` regardless), so nothing else has to change.
`_adopt_seeded_token_namespace` stays token-mode-only.

Measured surrogate-mode output — the names and the phone still get realistic
fakes, only the ม.26 spans become tokens:

```
IN   นายสมชาย ใจดี ป่วยเป็นโรคเบาหวาน และเข้ารับการรักษาที่โรงพยาบาลศิริราช โทร 081-234-5678
OUT  ณัฐกิตติ์ นาคสุวรรณ ป่วยเป็น[ข้อมูลสุขภาพ_…_2] และเข้ารับ[ข้อมูลสุขภาพ_…_1] โทร 02 347 9409

IN   นายอนันต์ พงษ์ไพบูลย์ เคยต้องโทษจำคุก และนับถือศาสนาอิสลาม
OUT  วิทยา วงษ์ทอง เคย[ประวัติคดี_…_1] และนับถือ[ศาสนา_…_1]
```

**Why not a realistic surrogate (the thing surrogate mode exists for).** A
"realistic" fake for ม.26 content means fabricating a false health, criminal,
religious or sexual claim about a person. The downstream model then reasons
about a disease the person does not have, and its answer is restored into the
user's document as advice about the wrong condition. That is an active harm,
not a realism trade-off. Masking removes a fact; surrogating asserts a false
one.

**Why not option (b), a fixed neutral phrase per category.** It does not merely
read badly, it crashes. `_generate_unique_pseudonym` rejects a candidate that
another entity already owns, and the FP branch cannot take a `#N` suffix.
Measured on a two-`HEALTH`-span document:

```
entities: [('HEALTH', 'ประวัติการรักษามะเร็งเต้านม'), ('HEALTH', 'โรคหัวใจร่วมด้วย')]
RAISED ValueError: unable to generate a unique pseudonym for entity 69473adf (HEALTH) after 64 attempts
```

Two sensitive spans of one category in one document is the normal case in a
medical record, so option (b) is not implementable without also relaxing the
anonymizer's uniqueness invariant. Refused.

### 5.4 Restore

Unchanged semantics: the token is a vault key, `reverse_map` restores the exact
original slice. Measured **40/40 exact round-trips** with no flags, in both
modes. The vault holds the sensitive original exactly as it holds any other
original — no new trust boundary, and `0003-mcp-no-plaintext-mapping` still
governs what may leave.

The proxy (`amphrang/proxy/core.py`) calls the facade
`amphrang.anonymize(text, mode="token", …)` and contains nothing type-specific,
so it inherits all of this with **no proxy change**.

---

## 6. Guard and validator wiring

### 6.1 `scan_residual_signals` — no change needed, verified

The replacement text is `[<Thai label>_<25 hex-ish>_<20 letters>_<ordinal>]`.
`scan_residual_signals` looks for runs of 6+ digits and for obfuscated
structured entities; neither is present. Measured **0 residual signals on 40/40**
masked dev documents.

### 6.2 `scan_outbound_leaks` — sensitive detection is added

`scan_outbound_leaks` gains the sensitive pass, excused by the same
trusted-pseudonym containment rule the other detectors use:

```python
for entity in detect_fp(text) + detect_tb(text) + _sensitive_leaks(text):
```

where `_sensitive_leaks` runs `detect_sensitive_spans` over the masked text with
person spans taken from that same rescan.

The value this buys is **not** catching what the same detector missed — that is
correlated by construction. It is catching an *implementation* failure: a
sensitive entity detected but not masked (a dedupe change, an offset bug, a
merge regression) is exactly the class of bug the outbound guard exists for, and
it is uncorrelated with detector recall.

Measured cost: over the 40 masked dev documents the rescan produced **25 hits,
all 25 excused by pseudonym containment, 0 unexcused**. The self-flagging
labels of Section 5.2 are all inside their own tokens, so containment covers
them; a sensitive phrase that was genuinely left unmasked would not be.

**Consequence: the ten names must be added to `SAFE_OUTBOUND_LEAK_TYPES`.** The
brief states they are already reserved there. They are not — measured today:

| present | absent |
|---|---|
| `HEALTH`, `RELIGION`, `POLITICAL_OPINION`, `DISABILITY` | `RACE_ETHNICITY`, `SEXUAL_BEHAVIOR`, `CRIMINAL_RECORD`, `LABOR_UNION`, `GENETIC`, `BIOMETRIC` |

Three stale short names — `CRIMINAL`, `ETHNICITY`, `UNION` — sit in the set
instead, matching the comment in `models.py` rather than any label the code
emits. They correspond to no `data_type` any detector produces. **Task 9 adds
the six missing names and does NOT remove the three stale ones**; removing a
member of a fail-closed allowlist is a separate, separately-verified change.

The **`http_v2.py` half of the brief's claim is correct**: `_SECTION26_ORDER` and
the `section26_categories` `Literal` already carry all ten. No contract change
is needed for the new entity type either — `entity_type_counts` keys are
validated by `_DATA_TYPE = ^[A-Z][A-Z0-9_]*$` (an open string) and
`Highlight.redact_type` is `Literal["FP","TB"]`, which `"TB"` satisfies.

`_OBFUSCATED_STRUCTURED_TYPES` gains **nothing**: these are prose spans, not
structured identifiers, and the whitespace-collapsing security view exists for
digit strings.

### 6.3 `output_validator._layer1_pii_scan` — a required change

`_layer1_pii_scan` re-runs `detect_all` on the **restored** text and excuses a
detection only when its whole span fits inside **one** validated restored range.
When the merge splits one CRF span into an entity plus a sensitive span, the
restored text re-detects the original wide span, which now straddles **two**
adjacent restored ranges — and the pipeline halts with `PIILeakError` on text
that is entirely correct.

Measured: **2 of 40** dev positives (`p_crime_02`, `p_relig_02`) raise
`PIILeakError` without the change and **0 of 40** with it. Both are documents
where the CRF emitted an `ORGANIZATION` span covering a whole clause.

The change: excuse a detection when **every character** of its span lies inside
**some** validated restored range, instead of when the whole span lies inside a
single one.

```python
expected: set[int] = set()
for item in reverse_result.restored_ranges:
    if <the same per-range validation as today>:
        expected.update(range(item[0], item[1]))
...
unexpected = [e for e in detected if not all(i in expected for i in range(*e.span))]
```

This is not a weakening. Each range is still validated individually against
`known_originals`; the rule additionally accepts a span covered by two or more
*contiguous* validated ranges, and still rejects any span containing a character
that was not restored. The current rule is the special case of one range.

Verified: the full existing suite run with this change applied in memory gives
**1817 passed, 9 skipped** — identical to the Task-7 baseline.

Baseline note for Task 9: the same 40 documents produce 3
`possible_truncation:no_terminal_punctuation` Layer-3 flags **with and without**
the sensitive pass. They are an artefact of one-sentence dev documents, not a
regression; the control run of the shipped pipeline reproduces them.

---

## 7. Default and facade verdict

**Default: ON, unconditionally, in `detect()` and `anonymize()`.** The
precision gate the campaign set as the price of default-ON is the negative
slice at exactly 15 false positives / 31 clean documents of 45, and the design
holds it at **+0**. Recall-first, and a ม.26 category that is off by default is
not a PDPA standard.

**Facade verdict: NO KNOB.** `amphrang/__init__.py` and `docs/api-surface.txt`
are unchanged, and `scripts/check_release.py` stays green without a manifest or
CHANGELOG surface diff. Concretely:

- no new public symbol, no new parameter on `detect`/`anonymize`/`analyze`;
- `Entity.data_type` is an open string, so ten new type values need no facade
  edit — the same reasoning the campaign already applied to the Wave-1 types;
- there is no engine-level switch either. A switch was the brief's fallback for
  a failed precision budget; the budget held, and adding a dead switch would be
  surface we would then have to keep.

The one user-visible consequence to document in Task 12, not to gate on:
`analyze()` now counts sensitive spans in `direct_pii_count` and lists them in
`breakdown`, so a document with ม.26 content scores higher than before. That is
the intended behaviour change, and `section26_categories` — driven by the
untouched `report.py` flag scan — is unaffected.

---

## 8. Known limits, recorded rather than fixed

Each of these is a measurement from this spike, not a suspicion.

1. **Three dev positives are unrecoverable by design** (`p_gene_02`,
   `p_relig_04`, `p_race_03`, giving 0.925 rather than 1.000). In each the CRF
   emitted a `NAME` span that swallows the sensitive phrase
   (`NAME(0,46)` over "นางสาวพิมพ์ใจ ศรีทอง เปลี่ยนมานับถือศาสนาฮินดู"). The
   characters *are* masked — as a fake person name — so nothing leaks, but the
   ม.26 label is lost and gold-v7 will score them as misses. The merge
   deliberately refuses to trim `NAME`/`SURNAME`: a Thai surname such as
   `พุทธรักษา` contains a `RELIGION` keyword, and trimming names to make room
   for sensitive spans would put gold `NAME` recall at risk for a labelling
   gain. **Task 10 must annotate these cases and report them separately**; the
   real fix is the CRF's over-spanning, which is out of scope here.
2. **The keyword table is cue vocabulary, not value vocabulary.** It fires on
   document titles and section headers where the words are labels rather than
   data, and it misses diagnoses stated without a cue word. Of the 12 gold-v6
   hits, 6 are real health facts about a named person (`ms08`, `md03`, `md08`
   ×2, `ed05`, `lf17`), and 5 are labels or clauses — `md07`
   "แบบยินยอมรับ**การรักษา**", `md11` "แบบคัดกรอง**สุขภาพจิต**เบื้องต้น", `lf11`
   "ข้อมูล**สุขภาพเพื่อการรักษาพยาบาลเท่านั้น**", `lf15` "ส่วนที่ 3 ข้อมูล**สุขภาพ**",
   `lf17` "หนังสือส่งตัวผู้ป่วยพร้อม**ประวัติการรักษา**". In the same documents the
   detector *misses* "ภาวะซึมเศร้า" (`lf02`), "ภาวะภูมิแพ้อากาศ และแพ้อาหารทะเล"
   (`lf15`) and "ก้อนที่เต้านมข้างซ้าย" (`lf17`), because no cue word precedes them.
   No header veto is frozen here on purpose: whether a section header counts as
   ม.26 data is an **annotation** question, and Task 10 Step 1 writes the
   guidelines before the documents. A veto fitted to 12 unannotated
   observations would be over-fitting dressed as a rule.
3. **`sensitive_detector.py` (the embedding pass) is not part of this design.**
   It is `[ml]`-extra only and returns `[]` without `sentence-transformers`,
   which is not installed in the reference environment. It is the natural answer
   to limit 2 and stays where it is — an `analyze()`-only enhancement. Raising
   it to a masking detector would make masking depend on an optional extra, so
   the core install would mask less than the extra install, which the coverage
   profile could not honestly describe.
4. **The impersonal-register vocabulary is fitted to 30 authored near-misses.**
   Its only independent evidence is the negative gold slice, where it costs
   nothing. Task 10's ≥ 6 impersonal gold documents are the real test.
5. **Merge rule 2 fires on 0 of 304 gold documents.** It is the rule that
   carries the recall gate on the dev set and it is untested on real data.
6. **Nothing here measures multi-turn or streaming behaviour.** The proxy path
   was checked for type-specific code (there is none) and the single-turn
   round-trip is verified 40/40; `stream_restore.py` was not exercised.

---

## 9. What Tasks 9 and 10 owe this record

**Task 9** — new file `sensitive_span.py` with the two signatures in Section 3;
`aggregate.py` wiring at the end of `detect_all`; the ten `TOKEN_LABEL` rows
(5.2); `anonymize()` routing by `data_type` (5.3); the six additions to
`SAFE_OUTBOUND_LEAK_TYPES` and the sensitive pass inside `scan_outbound_leaks`
(6.2); the `_layer1_pii_scan` change (6.3). No change to `report.py`,
`fp_generator.py`, `tb_generator.py`, `_OBFUSCATED_STRUCTURED_TYPES`, the
facade, or `docs/api-surface.txt`. Tests must pin: the coverage/non-overlap
invariant of 4.4; the two-tier anchor including the four near-miss classes; the
`สุขภาพระบบ` category-error drop; a two-`HEALTH`-span round trip in both modes;
`scan_outbound_leaks` clean on masked output; the two `PIILeakError` cases of
6.3. Gates: `pytest -q` green, gold negative slice exactly 15 / 31 of 45, every
per-type row at or above the Task-7 reference.

**Task 10** — the annotation addendum first, ruling on: the six boundary cases
in 4.3; whether a section header or form title is annotated (limit 2); how the
CRF-swallowed cases of limit 1 are annotated and reported. Then ~22 documents,
≥ 6 of them impersonal with zero sensitive spans, and the ten category names
added to `benchmark/types.py` per the guidelines decision.

---

## Reproduction

Every number above comes from the session scratchpad harness of 2026-08-27,
which imports `amphrang` read-only and monkey-patches
`amphrang.engine.detectors.aggregate.detect_all` for the gold runs. The control
run with the patch disabled reproduces the Task-7 reference table exactly, which
is what makes the patched runs comparable. Commands used:
`python -m pytest -q`, and the benchmark driven programmatically through
`benchmark.runner.run_benchmark(engine="crf", source="gold", seed=42, size=200)`.
`benchmark/data/blind-*` was not read, decrypted, or scored.

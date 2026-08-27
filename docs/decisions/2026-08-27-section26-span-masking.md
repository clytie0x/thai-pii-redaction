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

The campaign plan names this file `2026-08-26-section26-span-masking.md`. It is
dated `2026-08-27` for the day the spike ran and the design was frozen; that
name supersedes the plan's, and Tasks 9 to 10 should cite this one.

**Revision 2 (2026-08-27, fix round 1).** Amended after review. Substantive
changes: the merge algorithm in §4.4 now holds its coverage invariant by
construction rather than by luck (the first revision's one-remainder trim
silently dropped characters whenever a blocker sat strictly inside the span
being trimmed, a shape that occurs zero times in the dev set and zero times on
gold, so the original measurement could not see it); §5.3's rejection of a fixed
neutral phrase is re-argued, because the `ValueError` cited for it was an
artifact of an earlier `redact_type="FP"` prototype and does not occur under the
frozen `"TB"`; §6.2 specifies `_sensitive_leaks` completely; §9 names the one
existing test the design breaks. The three acceptance gates are unchanged and
were re-measured after every amendment.

**Revision 3 (2026-08-27, post-Task-9).** Documentation only; no design change
and no gate re-measurement. Task 9 implemented this record and its review round
closed one ambiguity and two observations. Substantive changes: §4.2 now defines
explicitly that "the hit" means the **raw regex match span**, not the shaped span
of §4.3 (the reading Task 9 shipped, now binding); §8 limit 2's gold ledger goes
from 12 rows to **13** and `excluded` on gold-v6 from 128 to **129**, superseding
the prototype's measurement, which evidently used the shaped-span reading; §8
gains limits 8 and 9, recording a guard limitation the reviewer measured and the
unclamped specificity window. The three acceptance gates are untouched by all of
this and were re-run by Task 9 and again by its reviewer: dev design unchanged,
negative slice `false_positives=15 clean_docs=31/45`, every per-type gold row
byte-identical to the Task-7 reference.

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
- Gold-v6 behaviour: ~~**12**~~ **13** sensitive spans fired across 304 documents,
  **0** of them in the `negative` slice. (Superseded by revision 3: the 12 was
  measured under the shaped-span reading of "the hit", which §4.2 now rules
  against. See §8 limit 2 row 13.)
- Full gold table with the design patched in: every per-type row byte-identical
  to the Task-7 reference; `shared_11 R=0.987 P=0.992 F2=0.988` unchanged.
  `OVERALL` precision moves 0.879 → 0.868 only because gold-v6 carries no
  sensitive annotations, so all predictions land in the `OUT_OF_SCHEME`
  bucket (`excluded` 116 → ~~128~~ **129**, superseded as above; the precision
  figure 0.868 is unchanged by the extra span). Task 10 converts them into
  scored spans.
- End-to-end over the 40 dev positives in `mode="surrogate"`: **0/40** outbound
  guard failures, **0/40** restore failures, **0/40** new output-validator
  failures (with the Section 6 change; without it, 2/40 — see there).
- Existing suite with **only** the §6.3 output-validator change applied in
  memory: **1817 passed, 9 skipped** — identical to the Task-7 baseline. That
  number bounds the validator change alone and nothing else.
- Existing suite with the **whole** design applied in memory (all five parts of
  §9): **1816 passed, 1 failed, 9 skipped**. The single failure is the
  `TOKEN_LABEL` length assertion, which Task 9 updates — see §9.
- Merge coverage invariant (§4.4): **13140 (case, policy) pairs, 0 violations**,
  including six synthetic fixtures built specifically to exercise the
  two-remainder path.

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
| 3. Span = the keyword expanded to its space/punctuation-bounded **segment** | **refuted** | at the matched `TIERED`/`TRIM_TB` configuration the segment shape swallows the anchor itself and recall collapses to **0.375** against **0.925**, while over-masking **+0.21x** against **+0.03x**. (Revision 1 quoted **+0.68x** here; that figure is the `SEGMENT`/`NAIVE`/`ADDITIVE` cell of the measurement grid, a different anchor rule and a different merge policy, so it was not the comparable number. Corrected.) |
| 4. Labels already reserved in `leak_guard.py`/`http_v2.py`; `redact_type="FP"` | **both halves refuted** | only 4 of 10 names are in `SAFE_OUTBOUND_LEAK_TYPES` today (Section 6); `redact_type` must be `"TB"`, not `"FP"` (Section 5) |
| 5. Surrogate mode: choose token-style or a fixed neutral phrase | **decided: token-style (option a)** | the governing reason is false-assertion harm — a realistic surrogate fabricates a health, criminal or religious claim about a person. Option (b) is separately rejected because it carries no per-entity restore identity (§5.3). **Correction to revision 1:** option (b) was reported there as crashing with `ValueError`; that was an artifact of the earlier `redact_type="FP"` prototype and does **not** happen under the frozen `"TB"` |
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

`blocked_spans` are the retained `FP` spans. It is an **early clamp, not a
guarantee**: it lets the detector stop a candidate at a precise structured hit
before the span shape runs, which keeps the emitted span tidy. The guarantee
that a `THAI_ID` inside a sensitive phrase stays `THAI_ID` comes from **merge
rule 1** (§4.4), which subtracts every retained `FP` span from every candidate
regardless of what was passed here. Passing `blocked_spans=None` changes span
boundaries, never correctness.

`entity_id` is a fresh `str(uuid.uuid4())` per emitted span, the same convention
every other detector in `amphrang/engine/detectors/` uses. See §4.4 for what
happens to an id when the merge splits a span.

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

**Compile flags: `re.UNICODE` and nothing else.** No `IGNORECASE` — `DNA` is
matched in upper case only, exactly as the flag table in `report.py` has always
done, and lower-case `dna` is a known non-match carried over unchanged rather
than silently widened here. No `MULTILINE` or `DOTALL`: no pattern uses `^`,
`$` or `.`, and scanning is bounded per segment with
`pattern.finditer(text, segment_start, segment_end)`, never with a sliced
string, so match offsets are always document offsets.

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

All three counts in that table were taken under the shaped-span reading of "the
hit" that §4.2 now rules against. Under the frozen reading the accepted row is
**13**, not 12 (§8 limit 2 row 13); the other two rows were **not** re-measured,
so they are left as recorded rather than adjusted by inference. The comparison
the table exists to make — segmentation costs recall nothing and buys a large
precision margin over "no split" — is unaffected by a one-document shift.

### 4.2 Two-tier person linkage

An anchor that lies **inside** the sensitive hit never counts — a phrase cannot
anchor itself. (The same principle as `_drop_unanchored_facility_spans`, which
blanks facility spans so they cannot be their own register evidence.) This one
rule alone kills the `สมาคมลูกจ้างในประเทศไทย` near-miss, where the only
"person" word is the `ลูกจ้าง` inside the union's own name.

**"The hit" means the RAW REGEX MATCH span `(m.start(), m.end())`, never the
shaped span of §4.3.** (Ruling, revision 3, 2026-08-27 post-Task-9; binding.)
Anchoring is therefore decided *before* the span shape runs, consistent with §3's
description of `blocked_spans` as an early clamp "before the span shape runs" and
with §3's own interchangeable use of "hit" and "match" in the category-error rule.
The `สมาคมลูกจ้าง` example above does **not** discriminate between the two readings —
`ลูกจ้าง` lies inside the match and inside the shaped span alike — so it is not
evidence either way, and the ruling is made on the ordering argument instead.

The two readings differ on exactly one real document in the whole corpus
(`lf17`, §8 limit 2 row 13), and they differ in the direction of **more** masking:
the shaped-span reading suppresses that span, the match reading emits it.
Recall-first settles a one-document tie towards masking. The prototype
measurements in §1 and the original 12-row ledger were taken under the
shaped-span reading; the match reading supersedes them, and the only numbers that
move are the two named in revision 3's note. No acceptance gate moves.

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

**Stop-set boundary: the span ends BEFORE the stop token.** The function word is
excluded from the span, along with everything after it. Walking the tokens, the
end offset advances by `len(token)` for each token, and the walk breaks on the
first token that is in the stop set without advancing past it.

**Exact tokenizer.** A module-level lazy singleton, built once:

```python
from pythainlp.corpus.common import thai_words
from pythainlp.tokenize import Tokenizer

_tokenizer = Tokenizer(custom_dict=thai_words(), engine="newmm")
```

It is applied **only to the tail** `text[m.end():hard_end]`, where `hard_end` is
the whitespace-bounded end — never to the whole document and never to text
before the match. The keyword match itself is never re-tokenized, so a keyword
that newmm would split cannot move the span start. `thai_words()` is the
installed pythainlp dictionary (5.3.7 in the reference environment); a
dictionary change can move a fallback boundary by a token, which is why the
fallback is confined to the overrun path and never runs on a well-formed span.

Why forward-only rather than the brief's whole segment: the anchor sits *before*
the keyword in nearly every Thai construction ("ผู้ป่วยรายนี้มี**ประวัติการรักษา**…"),
so a backward-expanding span eats its own anchor. Measured cost of the segment
shape at the matched configuration: recall 0.375 and over-masking +0.21x,
against 0.925 and +0.03x.

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

**The binding requirement is the invariant, and the algorithm below is written
so the invariant holds by construction:**

> The merge never uncovers a character that the pipeline's entity list already
> covered, never emits overlapping spans, and never emits two entities with the
> same `entity_id`.

Revision 1 stated the same invariant but implemented a trim that returned a
single remainder and kept "the longer side" when a blocker fell strictly inside
the span being trimmed. That silently dropped the shorter side:
`_trim_candidate((0, 20), [(5, 10)])` returned `(10, 20)`, uncovering characters
0 to 4. The shape occurs **zero** times in the dev set and **zero** times across
the 304 gold documents (counted directly), so the original 1122-pair
measurement could not see it. It is fixed here by making subtraction total.

#### The primitive

```python
def _subtract(
    span: tuple[int, int],
    blockers: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Every maximal sub-interval of `span` that no blocker covers, in order."""
    pieces = [span]
    for bs, be in sorted(blockers):
        nxt = []
        for start, end in pieces:
            if be <= start or bs >= end:
                nxt.append((start, end))
                continue
            if bs > start:
                nxt.append((start, min(bs, end)))
            if be < end:
                nxt.append((max(be, start), end))
        pieces = [(s, e) for s, e in nxt if e > s]
        if not pieces:
            return []
    return pieces
```

`_subtract` is **total**: the union of what it returns plus the union of the
blockers covers `span` exactly. That is the whole proof of the invariant — every
character a span loses is a character some other retained entity covers, so no
merge step can reduce total coverage.

#### The three rules

1. A sensitive candidate is `_subtract`ed against every retained **FP** entity
   and every retained **TB** entity that is not one of the three
   honest-fallback labels. **Every** remainder is kept, each as its own entity
   of the same `data_type`; the candidate is dropped only when `_subtract`
   returns nothing.
2. A retained TB entity of `LOCATION`, `ORGANIZATION` or `DATE` **yields** its
   overlapping characters to the sensitive span, and keeps **every** remaining
   piece as an entity of its own type. Those three labels are the ontology's
   declared "honest-labels catch-alls, not PDPA categories themselves", so a
   ม.26 claim on the same characters is strictly more specific. This is the
   `_relabel_student_ids` precedent applied to a partial overlap.
3. Sensitive candidates never overlap each other; the first one claimed wins,
   and later candidates are `_subtract`ed against what is already claimed.

Worked example of the two-remainder path, on a fixture built for it — an
`ORGANIZATION` at `(0, 20)` with a `HEALTH` span at `(5, 10)` strictly inside:

```
revision 1 (broken):  [('HEALTH', (5, 10)), ('ORGANIZATION', (10, 20))]      <- 0-4 uncovered
this revision:        [('ORGANIZATION', (0, 5)), ('HEALTH', (5, 10)), ('ORGANIZATION', (10, 20))]
```

#### `entity_id` semantics on a split

When a span becomes several pieces, **the lowest-start piece inherits the
original `entity_id` and every further piece gets a fresh `str(uuid.uuid4())`.**
This mirrors the existing convention for the inverse operation — both
`merge_address_spans` and `_prefer_record_names` keep `chain[0].entity_id` when
they merge — and it is required, not cosmetic.

The `vault.get_by_entity_id` consequence, spelled out because it is the thing a
duplicate id would corrupt:

- `anonymize()` opens with `existing = vault.get_by_entity_id(entity.entity_id)`
  and, on a hit, reuses that record's pseudonym while splicing at **this**
  entity's span. Two pieces sharing one id would therefore be written with one
  pseudonym and one vault record whose `original` is only one of the two
  fragments — the other fragment's text would be unrecoverable on restore.
  Minting a fresh id per extra piece keeps `vault._table` one-to-one, so each
  piece gets its own `vault.write` and its own restorable record.
- Cross-turn identity is unaffected. Every detector mints `str(uuid.uuid4())` per
  `detect()` call, so `entity_id` is never stable across turns and cross-turn
  continuity flows through `vault.get_by_original`, not `get_by_entity_id`. The
  practical consequence is that a split fragment is a **new original** and draws
  its own pseudonym, which is correct — the fragment is not the same value as the
  unsplit span.

#### Verification

**Task 9 must pin the invariant as a test, and the test must include a
two-remainder fixture** — a natural corpus does not produce one, so a test built
only from real documents would pass on the broken algorithm.

Re-measured after the fix: **13140 (case, policy) pairs, 0 violations**, across
three merge policies and three populations:

| Population | Cases | Two-remainder path exercised |
|---|---|---|
| Synthetic fixtures (sensitive inside `ORGANIZATION`/`LOCATION`; two sensitive inside one entity; `THAI_ID` inside a candidate; `NAME` inside a candidate; mixed) | 6 | yes, by construction |
| Randomized fuzz over span layouts, seed 20260827 | 4000 | yes |
| Natural corpus (70 dev + 304 gold documents) | 374 | **no — 0 occurrences** |

Coverage, non-overlap and `entity_id` uniqueness were all checked on every pair.
The three acceptance gates were re-run after the fix and are unchanged: dev
recall 0.925, impersonal 0/30, negative slice `false_positives=15
clean_docs=31/45`.

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
change a token label without re-checking this.** There is no automated gate on
`TOKEN_LABEL` today: `scripts/check_release.py` does not read it. The
`check_profile()` function that will AST-parse `TOKEN_LABEL` and diff it against
the coverage profile is **Task 11's deliverable**, and only from then on will a
label drift be caught by CI.

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

**Why not option (b), a fixed neutral phrase per category.**

*Correction to revision 1.* That revision reported option (b) as crashing with
`ValueError: unable to generate a unique pseudonym … after 64 attempts`. The
measurement was real but it was taken while the prototype still emitted
`redact_type="FP"`, whose branch of `_generate_unique_pseudonym` may not take a
collision suffix. Under the frozen `"TB"` the TB branch takes the suffix and
**option (b) does not crash.** Re-measured on the same two-`HEALTH`-span
document:

```
entities: [('HEALTH', 'TB', 'ประวัติการรักษามะเร็งเต้านม'), ('HEALTH', 'TB', 'โรคหัวใจร่วมด้วย')]
RESULT:   ผู้ป่วยรายนี้มี[ข้อมูลสุขภาพที่ปกปิดตามมาตรา 26]#2 และมี[ข้อมูลสุขภาพที่ปกปิดตามมาตรา 26]
```

The decision is unchanged, on the standing rationale plus what that output
shows. Option (b) carries **no per-entity restore identity**: the anonymizer's
uniqueness invariant forces the second span to a `#2` collision suffix, so the
phrase is not fixed after all, and the ordinal it lands on is an artifact of
generation order rather than a designed, restorable identity. A session token is
exactly option (b) with that identity supplied — the same neutral bracketed Thai
category phrase, plus the namespace, nonce and ordinal that make restore exact
and the marker hard to forge. Option (b) is therefore strictly dominated, and
two sensitive spans of one category in one document is the normal case in a
medical record. Refused.

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

`scan_outbound_leaks` gains a sensitive pass. It is specified in full here
because "runs the detector over the masked text" leaves four decisions open.

**Where it lives.** A private helper in `amphrang/engine/leak_guard.py`, beside
`_segment_leaks`. It imports `detect_sensitive_spans` from
`amphrang.engine.detectors.sensitive_span`, which is import-cycle-safe:
`sensitive_span.py` imports only `amphrang.engine.models`, and `aggregate.py`
imports `sensitive_span`, not the other way round.

**Exact signature and body.** `scan_outbound_leaks` already computes
`detect_fp(text) + detect_tb(text)`; the helper **reuses that one pass** rather
than calling `detect_all`, which would run a second NER over the masked text for
no gain:

```python
def _sensitive_leaks(text: str, found: list[Entity]) -> list[Entity]:
    """ม.26 spans in already-masked text. `found` is the guard's own
    detect_fp + detect_tb result for `text`, reused for its person anchors."""
    return detect_sensitive_spans(
        text,
        [e.span for e in found if e.data_type in ("NAME", "SURNAME")],
        blocked_spans=[e.span for e in found if e.redact_type == "FP"],
    )
```

- **`person_spans`** come from `found`, i.e. the guard's own `detect_fp` +
  `detect_tb` pass over the masked text — not from `detect_all`, and not from
  the original document's entity list, which the guard deliberately does not
  hold.
- **`blocked_spans`** is passed, from the same `found` list, for the reason in
  §3: it keeps a candidate from running across a structured hit. It is a
  boundary aid here, not the correctness mechanism.
- **`merge_sensitive_spans` does NOT run in the guard path.** The guard is not
  assembling an entity list for masking; it is answering "is there an unmasked
  ม.26 phrase here". Merging would subtract candidates against entities that are
  themselves leak findings, which is meaningless in this context.

**Behaviour in the TB fuzzy-overlap branch (`leak_guard.py:424-442`).**
Sensitive findings are `redact_type == "TB"`, so left in the main loop they
would fall into the branch that forgives a TB span overlapping a trusted range
when the per-segment remainder rescan and `_cue_leak_in_window` come back clean.
**They must not.** That forgiveness exists for fuzzy CRF spans that swallow an
embedded pseudonym, and `_segment_leaks` runs only `detect_fp` + `detect_tb`, so
it cannot see a ม.26 phrase in the remainder at all — a sensitive span
straddling a token boundary would be waved through on a remainder that was never
examined for sensitive content.

Sensitive findings therefore **bypass the loop and are appended after it**, with
exactly two excuses, both strict:

```python
def scan_outbound_leaks(text, guard_context):
    trusted = guard_context.trusted_pseudonyms()
    trusted_ranges = pseudonym_ranges(text, sorted(trusted, key=len, reverse=True))
    found = detect_fp(text) + detect_tb(text)
    real_leaks = []
    for entity in found:
        ...  # existing loop, unchanged
    for hit in _sensitive_leaks(text, found):
        if hit.original_text in trusted:
            continue  # excuse 1: the whole span is a pseudonym we wrote
        if any(cs <= hit.span[0] and hit.span[1] <= ce for cs, ce in trusted_ranges):
            continue  # excuse 2: positionally inside one such occurrence
        real_leaks.append(hit)
    return real_leaks
```

The justification for the stricter treatment is that a sensitive span comes from
an exact regex, not from a fuzzy model: a partial overlap with a pseudonym is
not span fuzziness to be forgiven, it is a real residual.

The value this buys is **not** catching what the same detector missed — that is
correlated by construction. It is catching an *implementation* failure: a
sensitive entity detected but not masked (a dedupe change, an offset bug, a
merge regression) is exactly the class of bug the outbound guard exists for, and
it is uncorrelated with detector recall.

Measured cost: over the 40 masked dev documents the rescan produced **25 hits,
all 25 excused by containment, 0 unexcused** — identical under both the
`detect_all` formulation first prototyped and the cheaper `detect_fp +
detect_tb` formulation specified above, which is why the cheaper one is frozen.
The self-flagging labels of §5.2 are all inside their own tokens, so containment
covers them; a sensitive phrase that was genuinely left unmasked would not be.

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
   data, and it misses diagnoses stated without a cue word. The full gold-v6
   ledger, all **13** hits (rows 1 to 12 are the prototype's; row 13 was added in
   revision 3 — see the note under the table):

   | # | doc | span | reading |
   |---|---|---|---|
   | 1 | `ms08` | `การรักษาแผนกอายุรกรรม` | real — which ward a named patient was admitted to |
   | 2 | `md03` | `การรักษาด้วยอาการเจ็บแน่นหน้าอก` | real — a presenting symptom |
   | 3 | `md07` | `การรักษา` | **label** — inside the form title "แบบยินยอมรับการรักษา" |
   | 4 | `md08` | `ผลการตรวจร่างกายอยู่ในเกณฑ์ปกติ` | real — an examination finding |
   | 5 | `md08` | `โรคที่เป็นอุปสรรคต่อการปฏิบัติงาน` | real — a negative finding is still health data |
   | 6 | `md11` | `สุขภาพจิตเบื้องต้น` | **label** — inside "แบบคัดกรองสุขภาพจิตเบื้องต้น" |
   | 7 | `ed05` | `สุขภาพ` | real — a student's stated reason for leave |
   | 8 | `lf02` | `การรักษาต่อเนื่อง` | real — but it starts *after* the diagnosis "ภาวะซึมเศร้า", which is left unmasked |
   | 9 | `lf11` | `สุขภาพเพื่อการรักษาพยาบาลเท่านั้น` | **clause** — a consent purpose statement |
   | 10 | `lf15` | `สุขภาพ` | **header** — "ส่วนที่ 3 ข้อมูลสุขภาพ"; the data under it is not masked |
   | 11 | `lf17` | `ประวัติการรักษา` | **label** — inside the covering-letter title |
   | 12 | `lf17` | `โรคเบาหวานชนิดที่` | real — a diagnosis |
   | 13 | `lf17` | `การรักษาโดย` | **unadjudicated** — see the note below |

   **Row 13, added in revision 3 (2026-08-27, post-Task-9).** Task 9's gold run
   emits `HEALTH (468, 479) 'การรักษาโดย'` in `lf17`, a thirteenth span the
   prototype did not produce. Measured, not inferred:

   ```
   segment (425, 492): 'เหตุผลการส่งตัว เพื่อตรวจชิ้นเนื้อและวางแผนการรักษาโดยแพทย์เฉพาะทาง'
   entities:  TB HEALTH (468,479) 'การรักษาโดย'   TB NAME (479,492) 'แพทย์เฉพาะทาง'
   ```

   Its anchor is a **CRF `NAME` false positive** over `แพทย์เฉพาะทาง`, which is not a
   person name at all. That NAME sits in the segment and outside the `การรักษา`
   match at `(468, 476)`, so under the §4.2 ruling it is a tier-1 anchor; merge
   rule 1 then trims the candidate at the NAME, giving `(468, 479)`. The
   prototype's 12-row ledger and its `excluded` figure were taken under the
   shaped-span reading, where the NAME is swallowed and the span is suppressed;
   **the frozen reading supersedes them**, so gold-v6 carries **13** sensitive
   spans and `excluded` is **129**, not 128/12. Every acceptance gate is
   unaffected: negative slice `false_positives=15 clean_docs=31/45`, every
   per-type row byte-identical, `OVERALL` precision on the already-predicted
   0.868. **Task 10's annotation addendum must adjudicate this row** — whether
   `วางแผนการรักษาโดยแพทย์เฉพาะทาง` in a referral letter about a named patient is ม.26
   data, and separately whether a span anchored only by a NAME false positive
   should count at all.

   Seven real, five labels or clauses, one unadjudicated. In the same documents the detector
   *misses* "ภาวะซึมเศร้า" (`lf02`, hit 8), "ภาวะภูมิแพ้อากาศ และแพ้อาหารทะเล"
   (`lf15`, hit 10) and "ก้อนที่เต้านมข้างซ้าย" (`lf17`), because no cue word
   precedes them. No header veto is frozen here on purpose: whether a section
   header counts as ม.26 data is an **annotation** question, and Task 10 Step 1
   writes the guidelines before the documents. A veto fitted to 13 unannotated
   observations would be over-fitting dressed as a rule.
3. **The gold-side evidence covers `HEALTH` and nothing else.** All 13 hits
   above are `HEALTH` — row 13 included, so revision 3 strengthens this limit
   rather than softening it. The other nine categories fired **zero** times across the
   304 gold-v6 documents, so the "negative slice +0" result is a real but
   *narrow* precision datum: it constrains `HEALTH` on real documents and
   constrains the other nine only insofar as the corpus contains text that could
   have triggered them, which it largely does not. For `CRIMINAL_RECORD`,
   `RELIGION`, `RACE_ETHNICITY`, `SEXUAL_BEHAVIOR`, `POLITICAL_OPINION`,
   `LABOR_UNION`, `DISABILITY`, `GENETIC` and `BIOMETRIC` the only precision
   evidence in this record is the 30 authored near-misses (3 per category).
   **Task 10 must give the nine under-evidenced categories real gold documents**,
   both person-linked and impersonal, before any claim is made about their
   precision in the coverage profile.
4. **`sensitive_detector.py` (the embedding pass) is not part of this design.**
   It is `[ml]`-extra only and returns `[]` without `sentence-transformers`,
   which is not installed in the reference environment. It is the natural answer
   to limit 2 and stays where it is — an `analyze()`-only enhancement. Raising
   it to a masking detector would make masking depend on an optional extra, so
   the core install would mask less than the extra install, which the coverage
   profile could not honestly describe.
5. **The impersonal-register vocabulary is fitted to 30 authored near-misses.**
   Its only independent evidence is the negative gold slice, where it costs
   nothing. Task 10's ≥ 6 impersonal gold documents are the real test.
6. **Merge rule 2 fires on 0 of 304 gold documents**, and the two-remainder path
   of §4.4 occurs 0 times there too. Both are exercised only by synthetic
   fixtures and fuzz. They are the rules that carry the recall gate and the
   coverage invariant respectively, and neither has real-document evidence.
7. **Nothing here measures multi-turn or streaming behaviour.** The proxy path
   was checked for type-specific code (there is none) and the single-turn
   round-trip is verified 40/40; `stream_restore.py` was not exercised.
8. **The §6.2 guard pass is blind to a sensitive span whose only anchor was a
   name that got tokenized** — measured by the Task-9 reviewer: `_sensitive_leaks`
   sources its `person_spans` from the guard's own `detect_fp + detect_tb` over the
   *masked* text, so once the anchoring `NAME` has become a bracket token there is
   no anchor left to re-find and an unspliced sensitive value goes unflagged. This
   is faithful to §6.2's own specification, not a defect against it, and it does not
   weaken the stated value of the pass (catching a detected-but-not-masked span,
   which is an implementation failure, not a recall correlation); recorded for
   Tasks 10 and 12 rather than fixed here.
9. **The 12-character specificity window of §4.2 is not clamped at the segment
   end**, unlike the span shape of §4.3, which says "clamped at the segment end"
   where it means it — so a `รายนี้` sitting just past a segment boundary can promote
   a tier-2 role word across that boundary. No dev or gold document exercises it;
   **Task 10 should include a cross-segment promotion probe document** so the
   reading has real evidence either way.

---

## 9. What Tasks 9 and 10 owe this record

**Task 9** — new file `sensitive_span.py` with the two signatures in Section 3;
`aggregate.py` wiring at the end of `detect_all`; the ten `TOKEN_LABEL` rows
(5.2); `anonymize()` routing by `data_type` (5.3); the six additions to
`SAFE_OUTBOUND_LEAK_TYPES` and the sensitive pass inside `scan_outbound_leaks`
(6.2); the `_layer1_pii_scan` change (6.3). No change to `report.py`,
`fp_generator.py`, `tb_generator.py`, `_OBFUSCATED_STRUCTURED_TYPES`, the
facade, or `docs/api-surface.txt`.

**One existing test must be updated, and it is the only one.** Measured by
running the whole suite with the entire design applied in memory:

```
FAILED tests/test_step3_pseudonymize.py::test_token_label_map_matches_v2_contract
E       AssertionError: assert 37 == 27
tests/test_step3_pseudonymize.py:604: assert len(TOKEN_LABEL) == 27
1 failed, 1816 passed, 9 skipped
```

`tests/test_step3_pseudonymize.py:604` asserts `len(TOKEN_LABEL) == 27`; the ten
rows of §5.2 make it **37**. Task 9 updates that assertion to `37` and leaves
the rest of the test untouched — the other assertions are per-key label checks
that all still hold. **The §9 gate is therefore "`pytest -q` green after that
one assertion is updated", not "green with no test edits."** Nothing else in the
suite moves: 1816 of 1817 pass unchanged.

Tests Task 9 must add, pinning: the coverage / non-overlap / `entity_id`
uniqueness invariant of §4.4, **including at least one two-remainder fixture**
(a sensitive span strictly inside an `ORGANIZATION`) — a test built only from
real documents passes on the broken algorithm, because the corpus contains zero
such cases; the two-tier anchor including the four near-miss classes; the
`สุขภาพระบบ` category-error drop; a two-`HEALTH`-span round trip in both modes;
`scan_outbound_leaks` clean on masked output; the two `PIILeakError` cases of
§6.3. Gates: `pytest -q` green, gold negative slice exactly 15 / 31 of 45, every
per-type row at or above the Task-7 reference.

**Task 10** — the annotation addendum first, ruling on: the six boundary cases
in §4.3; whether a section header or form title is annotated (limit 2); the
`lf17` row 13 of that same ledger, including whether a span anchored only by a
CRF `NAME` false positive counts at all; how the CRF-swallowed cases of limit 1
are annotated and reported. It should also carry a cross-segment promotion probe
document for limit 9. Then ~22 documents,
≥ 6 of them impersonal with zero sensitive spans, **weighted towards the nine
categories that have no gold evidence at all** (limit 3), and the ten category
names added to `benchmark/types.py` per the guidelines decision.

---

## Reproduction

Every number above comes from the session scratchpad harness of 2026-08-27,
which imports `amphrang` read-only and monkey-patches
`amphrang.engine.detectors.aggregate.detect_all` for the gold runs. The control
run with the patch disabled reproduces the Task-7 reference table exactly, which
is what makes the patched runs comparable. Commands used:
`python -m pytest -q`, and the benchmark driven programmatically through
`benchmark.runner.run_benchmark(engine="crf", source="gold", seed=42, size=200)`.

The two whole-suite figures were produced by pytest plugins that apply the
design in memory, so nothing in the repository was edited to obtain them: one
plugin applying only the §6.3 validator change (1817 passed), one applying all
five parts of §9 (1816 passed, 1 failed). The second rebinds `detect_all` and
`scan_outbound_leaks` in every module that imported them by value, so the wiring
is genuinely in force everywhere and not only at the definition site.

`benchmark/data/blind-*` was not read, decrypted, or scored.

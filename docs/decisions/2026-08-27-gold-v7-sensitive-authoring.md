# Gold-v7 `sensitive` slice authoring and ม.26 adjudication record

Date: 2026-08-27
Status: accepted

## Context

Task 10 of the PDPA-standard campaign. Task 9 (commit `d7d836a`) shipped
person-linked ม.26 span detection per the frozen design
[2026-08-27 ม.26 span masking](2026-08-27-section26-span-masking.md); this task
makes those spans **scored**, which is what turns the design's claims into
numbers. §9 of that record sets this task's contract: write the annotation
addendum first, rule on the open boundary cases, on section headers and form
titles, on the CRF-swallowed cases, and on ledger row 13; then author the gold
documents, weighted towards the nine categories with no gold evidence at all.

The addendum landed first and is the law this record applies:
`docs/annotation-guidelines.md`, section "Sensitive spans (มาตรา 26)", rules S1
to S7.

**Doc-id note.** The campaign plan names the new documents `sv01`-`sv22`. That
prefix is already taken by the `student_id_varied` slice (`sv01`-`sv25`), so
the slice ships as `sn01`-`sn28`.

## What shipped

- `benchmark/data/gold.jsonl`: 28 new documents (`sn01`-`sn28`, slice
  `sensitive`, layer `balanced`) and 17 pre-v7 documents re-annotated under S7
  (listed under "Change control" below). 304 documents become 332.
- `benchmark/gold.py`: `GOLD_VERSION` → `gold-v7`,
  `SLICE_LAYERS["sensitive"] = "balanced"`, docstring.
- `benchmark/types.py`: `SENSITIVE_ENTITY_TYPES` (the ten names) and
  `SCORED_ENTITY_TYPES = SHARED_ENTITY_TYPES + SENSITIVE_ENTITY_TYPES`.
- `benchmark/scorer.py`: the unrestricted view scores predictions against
  `SCORED_ENTITY_TYPE_SET`, so a `HEALTH` prediction lands on the `HEALTH` row
  instead of the `OUT_OF_SCHEME` bucket. The shared-scheme view now drops
  sensitive gold spans as well as sensitive predictions (`_shared_samples`) —
  without that, a ม.26 gold span would be an unanswerable false negative in a
  view whose predictions can never contain one.
- `tests/test_benchmark_gold.py`: the two exemptions the addendum defines
  (per-category `n >= 20`, and value reuse across documents), plus two slice
  contract tests.

No detector or engine code was touched. `SHARED_ENTITY_TYPES` stays at 19, so
`benchmark/corpus.py`, `benchmark/blind.py`'s draft validator and
`benchmark/llm_strategy.py`'s prompt scheme are all unchanged.

### Measured — `python -m benchmark --source gold` (332 docs, 1031 gold entities)

| type | n | recall | precision |
|---|---|---|---|
| HEALTH | 30 | 0.333 | 0.588 |
| RELIGION | 3 | 0.667 | 1.000 |
| GENETIC | 3 | 0.667 | 1.000 |
| BIOMETRIC | 3 | 1.000 | 1.000 |
| CRIMINAL_RECORD | 3 | 1.000 | 1.000 |
| DISABILITY | 3 | 1.000 | 1.000 |
| LABOR_UNION | 2 | 1.000 | 1.000 |
| POLITICAL_OPINION | 2 | 1.000 | 1.000 |
| RACE_ETHNICITY | 2 | 1.000 | 1.000 |
| SEXUAL_BEHAVIOR | 2 | 1.000 | 1.000 |

`OVERALL 1031 recall 0.967 precision 0.876 F2 0.947`,
`shared_11 R=0.988 P=0.993 F2=0.989 excluded=165`,
`slice negative false_positives=15 clean_docs=31/45`.

Every pre-existing per-type row is **at or above** its Task-7/9 reference:
`NAME 270 0.993/0.989` (was `247 0.992/0.988`), `BANK_ACCOUNT 0.973` (0.972),
`PHONE 0.991` (0.989), `ADDRESS 0.973` (0.971), `STUDENT_ID 0.862` (0.860),
`VEHICLE_PLATE 0.963` (0.962), `PASSPORT 0.962` (0.962), everything else
1.000/1.000 as before. `shared_11` moves up from `0.987/0.992/0.988` because
the 28 new documents carry easy structured entities.

`OVERALL` recall falls 0.987 → 0.967 and precision rises 0.868 → 0.876. Both
moves are the same fact: 53 ม.26 gold spans entered the scheme, the detector
finds 31 of them, and the 13 predictions that were `OUT_OF_SCHEME` false
positives on gold-v6 are now scored against real annotations. `excluded` rises
116 → 165 because that counter is defined against the **shared** 19-type set,
and every sensitive prediction is outside it by construction; it is no longer
a count of junk.

### Sensitive-span ledger, whole corpus

| | count |
|---|---|
| gold sensitive spans | 53 |
| true positives | 31 |
| misses whose characters were **covered** by some other prediction | 2 |
| misses left **uncovered** (a real leak) | 20 |
| false positives | 7 |

The covered/uncovered split is required by S6, because the two failures differ
by whether anything leaked. The two covered misses are the two probe documents
described below. The 20 uncovered misses are all `HEALTH`, all in pre-v7
documents plus `sn19`, and all instances of the design record's §8 limit 2: a
diagnosis stated without a cue word (`ภาวะหัวใจล้มเหลวเรื้อรังกำเริบ`,
`แพ้ยากลุ่มเพนิซิลลิน`, `ก้อนที่เต้านมข้างซ้าย`, `ยาลดความดัน`) or a cue word whose
segment holds no person anchor (`md06`'s lab-result line, `md11`'s screening
result).

The seven false positives:

| doc | span | why it is not a value |
|---|---|---|
| `md07` | `การรักษา` | inside the form title แบบยินยอมรับการรักษา (S2) |
| `md11` | `สุขภาพจิตเบื้องต้น` | inside the form title แบบคัดกรองสุขภาพจิตเบื้องต้น (S2) |
| `lf11` | `สุขภาพเพื่อการรักษาพยาบาลเท่านั้น` | a consent purpose clause (S2) |
| `lf15` | `สุขภาพ` | the section header ส่วนที่ 3 ข้อมูลสุขภาพ (S2) |
| `lf17` | `ประวัติการรักษา` | inside the covering-letter title (S2) |
| `sn13` | `ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน` | the right characters under the **wrong category** — see finding F3 |
| `sn28` | `การรักษาพยาบาลสำหรับผู้ป่วย` | the limit-9 probe firing on an impersonal ประกาศ — finding F1 |

Five of the seven are the label/header/title class the addendum's S2 rules out,
which is the measured answer to §9's "whether a section header or form title is
annotated": **no**, and the cost of saying no is exactly these five spans.

## Rulings

### R1 — the six §4.3 boundary disputes

Settled in the addendum's S4 table, unchanged from the inherited draft after
review: `ต้องโทษจำคุก 2 ปี`, `คนพิการประเภทที่ 3`, `ถูกฟ้องคดีฉ้อโกง`,
`ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน`, `สารพันธุกรรม`, `โรคเบาหวาน` (temporal trailer
excluded). Three of the six are now live in gold — `sn07`, `sn10`, `sn08` — and
one, `lf17`'s `โรคเบาหวานชนิดที่ 2`, keeps the type qualifier that the record's
own `โรคเบาหวาน` example drops, because the qualifier is part of the diagnosis
while `มาห้าปีแล้ว` is not.

Two boundary rules were **added** during authoring because the pre-v7
adjudication needed them and the draft did not have them:

1. The leading-verb rule applies at the **start** of the value only. `md08`
   ไม่พบโรคที่เป็นอุปสรรค… cuts after ไม่พบ; `md11`
   ผลคัดกรองพบความเสี่ยงระดับปานกลาง keeps its พบ because ผลคัดกรอง comes first.
   Without this the draft's own `ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน` row contradicts
   its own พบ bullet.
2. ประวัติ in front of a condition is inside the value (`ประวัติโรคหอบหืด`,
   `ประวัติสูบบุหรี่`); ประวัติ standing alone as a form field is a label
   (`ประวัติการแพ้ยา`, `ประวัติการเจ็บป่วย`).

### R2 — section headers and form titles are not values

S2. Measured cost above: five false positives that no rule can remove without
making gold a record of detector behavior. The alternative — annotating a form
title as its own subject's health data — would say that
แบบยินยอมรับการรักษา asserts something about the patient, which it does not.

### R3 — ledger row 13, `lf17` `การรักษาโดย`

Both halves of §9's question resolve in favour of the label, under S5.

The referral reason `เหตุผลการส่งตัว เพื่อตรวจชิ้นเนื้อและวางแผนการรักษาโดยแพทย์เฉพาะทาง`
is a course of care planned for a named patient in a referral letter, so it is a
value under S1/S2/S3; the field label เหตุผลการส่งตัว stays outside and the
และ splits it into **two** values, `ตรวจชิ้นเนื้อ` and
`วางแผนการรักษาโดยแพทย์เฉพาะทาง`.

The detector's prediction overlaps the second, so it scores as a true positive
even though its only person anchor is a CRF `NAME` false positive over
แพทย์เฉพาะทาง. Gold labels the fact, not the evidence chain: conditioning a gold
label on what anchored a prediction would make the corpus a record of the
detector rather than of the documents.

The consequence is recorded rather than hidden: **this true positive depends on
a `NAME` false positive.** `lf17`'s `แพทย์เฉพาะทาง` `NAME` span is one of the three
`NAME` false positives holding `NAME` precision at 0.989; fixing it would remove
a ม.26 true positive and turn `วางแผนการรักษาโดยแพทย์เฉพาะทาง` into an uncovered
miss, because `ตรวจชิ้นเนื้อ` next to it is already one. That is a design
fragility (§4.2 of the design record), and a future task that cleans up the CRF
must expect this row to move.

### R4 — CRF-swallowed spans (limit 1)

S6: annotated anyway, scored as a miss on their category, and reported
separately as **covered** rather than **uncovered** because nothing leaked.
`sn20` is authored specifically to reproduce the shape, and does — see F2.

### R5 — pre-v7 documents are adjudicated, not grandfathered

S7, and this is the ruling §9 did not ask for but the numbers force. Opening a
new annotated family puts every document in the corpus in scope for it.

The alternative was to leave the pre-v7 documents unannotated and accept the
measured false-positive cost. That cost was computed from the same run: gold
`HEALTH` would be the 3 spans in the new slice alone, the detector's 2 hits on
them would be its only true positives, and all 13 gold-v6 predictions plus
`sn13` and `sn28` would be false positives — `HEALTH` precision
`2/(2+15) = 0.118` on a corpus where **8 of those 13 predictions are correct**
and merely unlabelled. Publishing that would blame the detector for being right.
Refused.

The audit was a **read**, not a detector run: a Thai ม.26 vocabulary far wider
than the detector's own table (`โรค ภาวะ อาการ รักษา วินิจฉัย สุขภาพ ป่วย แพ้ ผ่าตัด
ตรวจ เลือด ยา พิการ ทุพพลภาพ ศาสนา พุทธ คริสต์ อิสลาม ฮินดู ความเชื่อ เชื้อชาติ เผ่าพันธุ์
ชาติพันธุ์ ชนเผ่า สัญชาติ การเมือง พรรค อุดมการณ์ คดี จำคุก ต้องโทษ อาชญากรรม ฟ้อง จำเลย
ผู้ต้องหา ศาล สหภาพ ลูกจ้าง สมาคม พันธุกรรม ดีเอ็นเอ DNA จีโนม โครโมโซม ชีวภาพ ชีวมิติ
ไบโอเมตริก ลายนิ้วมือ ม่านตา ใบหน้า เพศสัมพันธ์ เพศวิถี รสนิยม ตั้งครรภ์ ครรภ์`) flagged
**77 of the 304** documents; each was read and adjudicated by hand. 17 carried a
value; the detector finds 8 of the 27 values they carry, so the pass produced
19 misses against 8 hits — which is what a read-based audit looks like and what
a detector-led one could not have produced.

Documents the audit read and **declined** to annotate, recorded because they are
the boundary:

- `nc08` แพทย์ผู้ตรวจ [ชื่อ] ลงความเห็นให้พักรักษาตัว 3 วัน — names the doctor;
  the patient is never identified (S1, now precedent 11).
- `md05` an outpatient appointment slip, `md12` a referral routing note, `md13`
  a blank new-patient record header — administration only, no content about the
  person (S3).
- `lf11` สิทธิการรักษา ประกันสังคม and `dg20`'s whole subject — entitlements
  (S3, now precedent 12).
- `dg03` การตรวจสอบสุขภาพระบบประจำสัปดาห์ — a machine's health (S1). The
  detector's own category-error veto drops it, so gold and detector agree.
- `nc03` (รักษาสัตย์, a surname), `nc12` (รักษาการหัวหน้าแผนก, acting head),
  `nc15` (คำวินิจฉัย, an appeal ruling), `ng45` (ระเบียบว่าด้วยการรักษาความปลอดภัย)
  — the keyword in a non-ม.26 sense.

## Change control — every edited pre-v7 line

17 documents, 27 added values. Only ม.26 markup was inserted; not one character
of document text changed, so every pre-existing span offset and every
structured annotation is untouched.

| doc | before → after (the changed fragment only) |
|---|---|
| `nc18` | `เข้ารับการผ่าตัดตามนัดหมายของแพทย์` → `เข้ารับ[[HEALTH\|การผ่าตัด]]ตามนัดหมายของแพทย์` |
| `ms08` | `เข้ารับการรักษาแผนกอายุรกรรม` → `เข้ารับ[[HEALTH\|การรักษาแผนกอายุรกรรม]]` |
| `md01` | `เห็นควรให้หยุดพักรักษาตัวเป็นเวลา 5 วัน` → `เห็นควรให้[[HEALTH\|หยุดพักรักษาตัว]]เป็นเวลา 5 วัน` |
| `md02` | `เรื่องภาวะความดันโลหิตสูง` → `เรื่อง[[HEALTH\|ภาวะความดันโลหิตสูง]]` |
| `md03` | `เข้ารับการรักษาด้วยอาการเจ็บแน่นหน้าอก` → `เข้ารับ[[HEALTH\|การรักษาด้วยอาการเจ็บแน่นหน้าอก]]` |
| `md06` | `ผลตรวจระดับน้ำตาลในเลือดสูงกว่าเกณฑ์ ควรพบแพทย์เพื่อประเมินภาวะเบาหวาน` → `[[HEALTH\|ผลตรวจระดับน้ำตาลในเลือดสูงกว่าเกณฑ์]] ควรพบแพทย์เพื่อประเมิน[[HEALTH\|ภาวะเบาหวาน]]` |
| `md07` | `ยินยอมให้แพทย์ทำการผ่าตัดตามที่ได้อธิบายไว้แล้ว` → `ยินยอมให้แพทย์ทำ[[HEALTH\|การผ่าตัด]]ตามที่ได้อธิบายไว้แล้ว` |
| `md08` | `ผลการตรวจร่างกายอยู่ในเกณฑ์ปกติ ไม่พบโรคที่เป็นอุปสรรคต่อการปฏิบัติงาน` → `[[HEALTH\|ผลการตรวจร่างกายอยู่ในเกณฑ์ปกติ]] ไม่พบ[[HEALTH\|โรคที่เป็นอุปสรรคต่อการปฏิบัติงาน]]` |
| `md09` | `ผู้ป่วยมีภาวะซึมเศร้าร่วมด้วย` → `ผู้ป่วยมี[[HEALTH\|ภาวะซึมเศร้า]]ร่วมด้วย` |
| `md10` | `จ่ายยาลดไขมันในเลือด 1 เดือน` → `จ่าย[[HEALTH\|ยาลดไขมันในเลือด]] 1 เดือน` |
| `md11` | `ผลคัดกรองพบความเสี่ยงระดับปานกลาง` → `[[HEALTH\|ผลคัดกรองพบความเสี่ยงระดับปานกลาง]]` |
| `ed05` | `เนื่องจากปัญหาสุขภาพ` → `เนื่องจาก[[HEALTH\|ปัญหาสุขภาพ]]` |
| `lf02` | `การวินิจฉัยหลัก ภาวะหัวใจล้มเหลวเรื้อรังกำเริบ ร่วมกับภาวะไตเสื่อมระยะที่ 3` → `การวินิจฉัยหลัก [[HEALTH\|ภาวะหัวใจล้มเหลวเรื้อรังกำเริบ]] ร่วมกับ[[HEALTH\|ภาวะไตเสื่อมระยะที่ 3]]` |
| `lf02` | `ผู้ป่วยมีประวัติสูบบุหรี่มานาน 30 ปี และมีภาวะซึมเศร้าที่ได้รับการรักษาต่อเนื่อง` → `ผู้ป่วยมี[[HEALTH\|ประวัติสูบบุหรี่]]มานาน 30 ปี และมี[[HEALTH\|ภาวะซึมเศร้าที่ได้รับการรักษาต่อเนื่อง]]` |
| `lf11` | `ประวัติการแพ้ยา แพ้ยากลุ่มเพนิซิลลิน มีประวัติโรคหอบหืดตั้งแต่วัยเด็ก` → `ประวัติการแพ้ยา [[HEALTH\|แพ้ยากลุ่มเพนิซิลลิน]] มี[[HEALTH\|ประวัติโรคหอบหืด]]ตั้งแต่วัยเด็ก` |
| `lf15` | `นักเรียนมีภาวะภูมิแพ้อากาศ และแพ้อาหารทะเล` → `นักเรียนมี[[HEALTH\|ภาวะภูมิแพ้อากาศ]] และ[[HEALTH\|แพ้อาหารทะเล]]` |
| `lf17` | `เป็นโรคเบาหวานชนิดที่ 2 ตั้งแต่ปี 2560` → `เป็น[[HEALTH\|โรคเบาหวานชนิดที่ 2]] ตั้งแต่ปี 2560` |
| `lf17` | `และตรวจพบก้อนที่เต้านมข้างซ้ายเมื่อเดือนมิถุนายน 2569` → `และตรวจพบ[[HEALTH\|ก้อนที่เต้านมข้างซ้าย]]เมื่อเดือนมิถุนายน 2569` |
| `lf17` | `เพื่อตรวจชิ้นเนื้อและวางแผนการรักษาโดยแพทย์เฉพาะทาง` → `เพื่อ[[HEALTH\|ตรวจชิ้นเนื้อ]]และ[[HEALTH\|วางแผนการรักษาโดยแพทย์เฉพาะทาง]]` |
| `lf19` | `ล้มได้รับบาดเจ็บที่ขาขวา` → `ล้มได้รับ[[HEALTH\|บาดเจ็บที่ขาขวา]]` |

Everything else in `gold.jsonl` is append-only.

## Document mix — `sn01`-`sn28`

**20 person-linked** (`sn01`-`sn20`), 26 sensitive spans, weighted to the nine
categories that had no gold evidence at all (§8 limit 3): 3 RELIGION, 3
BIOMETRIC, 3 CRIMINAL_RECORD, 3 DISABILITY, 3 GENETIC, 2 RACE_ETHNICITY, 2
POLITICAL_OPINION, 2 LABOR_UNION, 2 SEXUAL_BEHAVIOR, 3 HEALTH. Skeletons are
deliberately different: a hospital dietary note, a school culture survey, a
social-work home visit, an HR complaint intake, a disciplinary fact-finding
memo, a union-dues deduction letter, a pre-employment background report, a
criminal case summary, a licence refusal letter, a disability-card application,
a workplace-accommodation request, a parking allocation memo, a forensic lab
report, a carrier-screening letter, an access-control enrolment record, a
consent-withdrawal request, a counselling note, a family-medicine history, a
chronic-clinic summary, and a membership change note.

Anchor constructions are mixed, because the two-tier rule of §4.2 is the
design's load-bearing part: title+name (`sn01`, `sn06`, `sn07`, `sn09`, `sn10`,
`sn14`, `sn20`), first-person ข้าพเจ้า (`sn05`, `sn11`, `sn16`), and tier-2 role
words carrying a specificity marker — นักเรียนรายนี้ (`sn02`), พนักงานรายนี้
(`sn12`), ผู้ต้องหารายนี้ (`sn13`), ผู้รับบริการรายนี้ (`sn17`), ผู้ป่วยรายนี้
(`sn18`).

**These do not isolate tier 2.** Every one of the 20 documents also carries a
detected `NAME`/`SURNAME` span in the anchoring segment, because a realistic
Thai record names its subject, and a `NAME` overlap is tier 1 and is checked
first. So the promoted-role constructions are *present* in gold but the linkage
that actually fires is tier 1 in all 20. A document that reaches the promotion
path alone would have to withhold the person's name from the segment, which no
document of these kinds does. Recorded as a limit, not worked around: the
promotion rule's only measured evidence stays the design record's dev set plus
`sn28`, which exercises it in the direction of a false positive.

Every document also carries at least one of the 19 structured types, so the
slice measures the two annotated families together.

**8 impersonal** (`sn21`-`sn28`), zero sensitive spans, each built so a
category keyword sits in a segment with an institutional register: a
กรมควบคุมโรค treatment guideline (`sn21`), a union's own annual-meeting
invitation (`sn22`), an ethnicity research summary (`sn23`), a
comparative-religion course announcement (`sn24`), a criminal-code circular
(`sn25`), a fingerprint-reader procurement spec (`sn26`), a genetics seminar
programme (`sn27`), and the limit-9 probe (`sn28`). Seven of the eight produce
**zero** sensitive predictions; the eighth is the probe and is meant to fail.

This is the independent check the design record asks for on the register-veto
vocabulary (§8 limit 5), which until now had only the 30 authored dev
near-misses behind it. It holds on 7 of 8, and the one failure is a
segmentation bug, not a vocabulary gap.

## Findings

### F1 — limit 9 is real: the specificity window crosses segment boundaries

`sn28` is authored to the design record's §8 limit 9 and confirms it.

```
ประกาศแนวทางการรักษาพยาบาลสำหรับผู้ป่วย
ดังกล่าวให้สถานพยาบาลทุกแห่งถือปฏิบัติโดยเคร่งครัด
```

The `การรักษา` hit and the tier-2 anchor ผู้ป่วย share segment 1, which carries
two register-veto words (ประกาศ, แนวทาง), so the anchor should be vetoed. But
`_SPECIFICITY_RE.search(text, match.end(), match.end() + _SPECIFICITY_WINDOW)`
in `sensitive_span.py` is **not clamped at `segment_end`**, and ดังกล่าว sits 1
character past the newline. The role word is promoted to tier 1, the veto no
longer applies, and the detector emits
`TB HEALTH (12, 39) 'การรักษาพยาบาลสำหรับผู้ป่วย'` in a document about nobody.

Measured, not inferred. The distance matters: an earlier draft of this document
put ดังกล่าว nine characters past the role word, and the window (12) could not
fit the eight-character marker, so nothing fired. The probe only works when the
marker starts within the window.

This is one gold false positive out of eight impersonal documents. **No fix is
attempted here** — the constraint on this task is annotation and benchmark
wiring only, and a change to `_SPECIFICITY_WINDOW`'s clamp is a detector change
that belongs to whoever owns `sensitive_span.py` next. Clamping it at
`segment_end` is the obvious candidate and would cost nothing measurable: no
other document in the 332 exercises the cross-boundary path.

### F2 — limit 1 is real, and fragile to reproduce

`sn20` reproduces the CRF-swallow shape of §8 limit 1:

```
นางสาวพิมพ์ใจ ศรีทอง เปลี่ยนมานับถือศาสนาฮินดู เมื่อปี 2566
```

The CRF emits `TB NAME (0, 46)` over the whole clause. The `NAME` span swallows
`ศาสนาฮินดู`, `merge_sensitive_spans` refuses to trim a `NAME`, and the RELIGION
span is suppressed. Gold annotates the value anyway (S6), so it scores as a
`RELIGION` miss — with its characters **covered**, which is why it is counted
separately from the 20 uncovered misses. Nothing leaks; the label is lost.

Reproducing it took three attempts, and that is worth recording. The same
sentence one line down inside a document, or preceded by
`บันทึกแจ้งเปลี่ยนแปลงข้อมูลสมาชิก`, produces a well-behaved
`NAME (34, 54)` and the RELIGION span fires normally. The swallow needs the
name at the start of the text. Limit 1 is therefore narrower on real documents
than the design record's flat "3 of 40 dev positives" suggests, and gold-v7 can
only pin one instance of it.

### F3 — a category collision the design record does not name

`sn13` annotates `ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน` as GENETIC, per the addendum's
own boundary table. The detector emits
`TB HEALTH (104, 133) 'ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน'` — the exact characters,
under the wrong category.

The cause is in §3's pattern table plus §4.4's merge rule 3. `HEALTH`'s
`ผล(?:การ)?ตรวจ` matches at `ผลตรวจ`, four characters before `GENETIC`'s
`ดีเอ็นเอ`; the earlier candidate is claimed first and the later one is
subtracted to nothing. So it costs a false positive on `HEALTH` and a miss on
`GENETIC`, while the characters are correctly masked.

This is not a boundary judgement and not an annotation question: the phrase is
genetic data by every reading, and the addendum's boundary table (inherited from
the design record's own dev set) already says so. It is a detector-side
precedence question — a lab-result cue should not outrank a named biological
category — and it is **reported, not fixed**, per this task's constraints. It is
the reason `GENETIC` reads 0.667 rather than 1.000.

`sn13` carries a second GENETIC value, `สารพันธุกรรมจากคราบเลือด`, precisely so
the category is not measured by the colliding case alone.

## Known limits of gold-v7

1. **Nine of the ten categories are below the reportable floor.** `HEALTH`
   reaches n=30; the other nine sit at 2 or 3. Their recall and precision are
   indicative and must not be published as headline numbers. The floor is
   exempted in `tests/test_benchmark_gold.py` for these ten types only, with the
   reason written at the exemption. Recorded as a limit of gold-v7, not as a
   permanent licence.
2. **`HEALTH` precision 0.588 is a floor, not an estimate.** Five of its seven
   false positives are the form-title and section-header class that R2 rules
   out on purpose. A cue-vocabulary that fires on labels is the design's §8
   limit 2, and gold-v7 now measures its cost instead of describing it.
3. **`HEALTH` recall 0.333 is dominated by the pre-v7 adjudication.** Of 30
   gold `HEALTH` spans, 27 are in documents written years before the family
   existed and never shaped to carry a cue word; the detector finds 8 of those
   27 and 2 of the 3 in the new slice. The number is honest and it is also not a
   measurement of what a ม.26-aware corpus would give.
4. **Document-level linkage is annotated, segment-level linkage is detected.**
   S1 makes a lab-result line the patient's data when the patient is named a
   line above; §4.1 requires the anchor in the same segment. `md06` and `md11`
   are misses by construction, not by failure. Closing that gap is a design
   change, not an annotation one.
5. **Zero blind-set coverage.** `benchmark/data/blind-*` was not read,
   decrypted, or scored, and carries no ม.26 annotations. Every ม.26 number in
   this repository is an open-corpus number.
6. **The `sensitive` slice is authored, so the register-veto check is a strong
   but not independent one.** The eight impersonal documents were written by the
   same person who read the veto vocabulary. They are better evidence than the
   30 dev near-misses because they are full documents in the corpus's own house
   style, and worse evidence than a held-out set would be.

## Authoring-side fallout

Five of the 28 new documents were reworded after measurement, in the same
category as the gold-v6 record's item 8: choosing between phrasings that serve
the document equally well, with the detector's response in hand. Recorded rather
than hidden, because the choice is an authoring decision and not neutral value
selection.

1. `sn02` — `ผู้ปกครองติดต่อได้ที่ <phone>` produced a spurious `NAME` span over
   ติดต่อได้ที่. Changed to `โทรศัพท์ผู้ปกครอง <phone>`.
2. `sn04` — `ผู้รับเรื่อง สุกัญญา ปิ่นแก้ว` was missed by the CRF as a bare full
   name after a role word, the same weakness gold-v6 recorded. A นางสาว title
   was added rather than swapping the name.
3. `sn06` — `โอนเข้าบัญชี <acct> ธนาคารออมสิน สอบถามที่ <phone>` on one line let
   the บัญชี cue reach the second number, making it a `BANK_ACCOUNT`. The phone
   moved to its own line. `gf17` carries the same shape and the same error, and
   is left alone: it is a pre-existing document and a real detector behaviour.
4. `sn25` — a legal clause ordered
   `ยื่นคำร้องคดีแพ่งเกี่ยวเนื่องคดีอาญาภายในกำหนดเวลาตามมาตรา 193` produced a
   spurious `NAME` over half the clause **and**, through it, a spurious
   `CRIMINAL_RECORD` — a tier-1 anchor conjured out of a CRF error, the same
   mechanism as `lf17` row 13 but in an impersonal document. Reordered to
   `ยื่นคำร้องในคดีแพ่งที่เกี่ยวเนื่องกับคดีอาญา ภายในกำหนดเวลาตามมาตรา 193`, which
   reads at least as naturally and does not. **The suppressed finding is the
   interesting one and is recorded here rather than shipped as a second gold
   false positive:** a CRF `NAME` false positive can create a ม.26 false
   positive in a document with no person in it at all.
5. `sn28` — an earlier wording put ดังกล่าว out of reach of the specificity
   window and the probe did not fire; and a `ฉุกเฉินวิกฤต` phrasing added a
   spurious `NAME`. The shipped wording fires the probe and carries no `NAME`
   error, so F1 is measured on its own.

## Consequences

- `docs/annotation-guidelines.md` gains the "Sensitive spans (มาตรา 26)" section
  (rules S1-S7, the boundary table, the per-category-n and value-reuse
  exemptions), a `sensitive` slice contract, and three new judgment-call
  precedents (11 unnamed third parties, 12 entitlements, 13 organization names).
- `shared_11` and the synthetic corpus are unchanged by design; `excluded`
  changes meaning as described above and should be read alongside the sensitive
  rows, not as a junk count.
- Two detector-side findings (F1, F3) are left open for a future task. Neither
  is a regression: F1 is the design record's own limit 9 with evidence attached,
  and F3 is new.
- The README's accuracy table still quotes gold-v5 and is Task 12's to update.

# Frozen specs for five new Thai PII types

Date: 2026-08-26
Status: accepted

## Context

The data-type expansion plan (`docs/superpowers/plans/2026-08-26-datatype-expansion-accuracy.md`)
adds five Thai structured PII types end to end. Task 1 of that plan is research
only: before any detector is written, three open questions have to be answered
with evidence rather than assumption.

1. Does the Thai juristic registration number (เลขทะเบียนนิติบุคคล, 13 digits
   starting `0`) carry the same mod-11 check digit as the citizen ID? If yes the
   detector may score 1.0 on checksum alone; if no it must ship cue-gated at 0.9.
2. Is the house registration code (เลขรหัสประจำบ้าน) 11 digits, and is there a
   verifiable checksum?
3. Is the modern Thai driving-licence number 8 digits?

The repo rule is honest labels. A verdict of `verified` requires both a stated
algorithm and test vectors that were actually run in this session; anything else
is `unverified` and the type ships on shape plus cue only.

## Verdicts

| Question | Verdict |
|---|---|
| `JURISTIC_CHECKSUM` | **verified** — citizen-ID mod-11, 8/8 real numbers pass |
| `HOUSE_REG_SHAPE` | **verified** — 11 digits |
| `HOUSE_REG_CHECKSUM` | **unverified** — a check digit is claimed by secondary sources, no algorithm and no obtainable vectors |
| `DRIVER_LICENSE_SHAPE` | **unverified (secondary sources only)** — 8 digits for the smart-card format; legacy alphanumeric form exists and is out of scope |

---

## 1. JURISTIC_ID check digit — verified

### Algorithm

Identical to the Thai citizen ID. For the 13 digits `d[0..12]`:

```
weights = [13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
total   = sum(d[i] * weights[i] for i in range(12))
check   = (11 - (total % 11)) % 10
valid   = (check == d[12])
```

This is byte-for-byte the function already in the repository,
`amphrang/engine/detectors/thai_id.py::is_valid_thai_id`, which takes any
13-digit string and does not care about the leading digit. **Task 2 does not
need a new checksum implementation.** `is_valid_juristic_id` may be a thin
wrapper that delegates to `is_valid_thai_id` after stripping separators; if the
plan's helper name is kept, keep the single implementation underneath.

### Sources

The published descriptions of the weight/mod-11 rule are written for the citizen
ID card. None of them is an official Department of Business Development
specification — the DBD does not publish one.

- Thai Server 101, "The Modulo 11 Checksum Algorithm" — states the weights
  `13..2`, `r = Sum mod 11`, check digit `11 - r` (two-digit results take the
  units digit, i.e. `(11 - r) % 10`), and scopes itself explicitly to
  "เลขบัตรประชาชน". <http://thaiserv.blogspot.com/2011/04/the-modulo-11-checksum-algorithm.html>
- salathaiit, "เลขประจำตัวประชาชน 13 หลักนั้นสำคัญไฉน" — same formula with a
  worked example (`1-2015-41462-23-4`, sum 205, 205 mod 11 = 7, 11-7 = 4).
  <http://www.salathaiit.com/article/2/> (HTTPS certificate is misconfigured on
  that host; content read through search extraction)
- ThaiCompanyCheck, "What Is a DBD Registration Number?" — describes the DBD
  13-digit layout (digit 1 juristic-person type, digits 2–5 registrar office,
  digits 6–9 Buddhist-era year of registration, digits 10–12 sequence, digit 13
  check digit computed modulo 11).
  <https://thaicompanycheck.com/blog/what-is-dbd-registration-number-thailand>
  (server returns 403 to direct fetch; content read through search extraction)

Because no primary source states the rule for juristic numbers, the verdict rests
on the test vectors below, not on the citations.

### Test vectors — 8 real, public juristic numbers

All are registration numbers of listed Thai companies, i.e. public record. Each
was confirmed against a source that names the company and the number together
before being used as a vector.

| # | Number | Entity | Source |
|---|---|---|---|
| 1 | `0107544000108` | บริษัท ปตท. จำกัด (มหาชน) | procurement notice on `procurement.pttplc.com` printing "ทะเบียนเลขที่ 0107544000108"; `dataforthai.com/company/0107544000108/` |
| 2 | `0107537000114` | บริษัท ปูนซิเมนต์ไทย จำกัด (มหาชน) | company memorandum & articles PDF on `scc-th.listedcompany.com`; `dataforthai.com/company/0107537000114/` |
| 3 | `0107536000315` | ธนาคารกสิกรไทย จำกัด (มหาชน) | prospectus PDF on `kasikornbank.com`; `dataforthai.com/company/0107536000315/` |
| 4 | `0107536000102` | ธนาคารไทยพาณิชย์ จำกัด (มหาชน) | ETDA Digital ID licence page `etda.or.th/DigitalID/022-2568.html`; `dataforthai.com/company/0107536000102/` |
| 5 | `0107542000011` | บริษัท ซีพี ออลล์ จำกัด (มหาชน) | ThaiBMA prospectus PDF; `dataforthai.com/company/0107542000011/` |
| 6 | `0107535000265` | บริษัท แอดวานซ์ อินโฟร์ เซอร์วิส จำกัด (มหาชน) | SEC filing on `market.sec.or.th`; `data.creden.co/company/general/0107535000265` |
| 7 | `0107545000292` | บริษัท ท่าอากาศยานไทย จำกัด (มหาชน) | `data.creden.co/company/general/0107545000292` |
| 8 | `0505532001265` | บริษัท เชียงใหม่โฮลดิ้ง จำกัด | `dataforthai.com/company/0505532001265/` |

Vector 8 is deliberately not a `0107` Bangkok public company — it is a private
limited company registered in Chiang Mai (`0505` registrar prefix). It passes,
so the rule is not an artefact of the `0107` prefix.

Note on vector 7. The plan's author-side guess for Airports of Thailand was
`0107545000390`; research returned `0107545000292` and that is the number used.
`0107545000390` was never validated and must not appear anywhere downstream.

### Calculations

Run with `./.venv/Scripts/python.exe`, weights `13..2`.

```
0107544000108  0*13 + 1*12 + 0*11 + 7*10 + 5*9 + 4*8 + 4*7 + 0*6 + 0*5 + 0*4 + 1*3 + 0*2 = 190
               190 mod 11 = 3   (11-3) mod 10 = 8   d13 = 8   PASS
0107537000114  0*13 + 1*12 + 0*11 + 7*10 + 5*9 + 3*8 + 7*7 + 0*6 + 0*5 + 0*4 + 1*3 + 1*2 = 205
               205 mod 11 = 7   (11-7) mod 10 = 4   d13 = 4   PASS
0107536000315  0*13 + 1*12 + 0*11 + 7*10 + 5*9 + 3*8 + 6*7 + 0*6 + 0*5 + 0*4 + 3*3 + 1*2 = 204
               204 mod 11 = 6   (11-6) mod 10 = 5   d13 = 5   PASS
0107536000102  0*13 + 1*12 + 0*11 + 7*10 + 5*9 + 3*8 + 6*7 + 0*6 + 0*5 + 0*4 + 1*3 + 0*2 = 196
               196 mod 11 = 9   (11-9) mod 10 = 2   d13 = 2   PASS
0107542000011  0*13 + 1*12 + 0*11 + 7*10 + 5*9 + 4*8 + 2*7 + 0*6 + 0*5 + 0*4 + 0*3 + 1*2 = 175
               175 mod 11 = 10  (11-10) mod 10 = 1  d13 = 1   PASS
0107535000265  (same weights)                                              = 204
               204 mod 11 = 6   (11-6) mod 10 = 5   d13 = 5   PASS
0107545000292  0*13 + 1*12 + 0*11 + 7*10 + 5*9 + 4*8 + 5*7 + 0*6 + 0*5 + 0*4 + 2*3 + 9*2 = 218
               218 mod 11 = 9   (11-9) mod 10 = 2   d13 = 2   PASS
0505532001265  (same weights)                                              = 215
               215 mod 11 = 6   (11-6) mod 10 = 5   d13 = 5   PASS
```

Result: **8 PASS, 0 FAIL**, run through the repo's own
`is_valid_thai_id`, not a throwaway reimplementation.

### Discrimination (how much the checksum is worth)

Measured in the same session, so the 1.0 score is priced honestly.

- Single-digit mutations of the eight vectors: 855 of 936 rejected (91.3%).
- Random `0`-leading 13-digit strings, n = 100 000, seed 7: acceptance rate
  **0.0997**.

The residual ~1/10 acceptance is inherent to the `(11 - r) % 10` fold, which
collapses `r = 0` and `r = 10` onto the same check digit. The citizen ID has
exactly the same property, so JURISTIC_ID at 1.0 is no weaker than THAI_ID at
1.0 and the existing precedence ordering stays coherent.

### Consequence — a correction the plan needs

The plan's precedence note says "THAI_ID first digit is 1–8, JURISTIC_ID starts
0 → disjoint". **That is false as implemented.** `_RE_THAI_ID`
(`fp_detector.py:250`) is `(\d{1}[-\s]?\d{4}…)` with no leading-digit
restriction, and step 1 accepts anything `is_valid_thai_id` accepts. Verified in
this session:

```
'เลขทะเบียนนิติบุคคล 0107536000102 ของบริษัทจดทะเบียน'   -> THAI_ID '0107536000102' 1.0
'เลขประจำตัวผู้เสียภาษี 0-1075-36000-10-2 ตามหนังสือรับรอง' -> THAI_ID '0-1075-36000-10-2' 1.0
```

**Superseded 2026-08-27.** The block above records behaviour *before* step 1 routed the
`0`-leading case. Since the PDPA-standard campaign's Task 2 landed, both strings yield
`JURISTIC_ID` at 1.0 — re-run and quoted in
`docs/decisions/2026-08-26-wave1-format-specs.md` §2.4.

Every real juristic number is therefore already emitted as THAI_ID at score 1.0.
Task 2 must make step 1 route the `0`-leading case, or the plan's
`test_juristic_id_with_cue_detected` can never pass (both candidates score 1.0
and `_deduplicate` is score-first).

The gate must be **first digit is not `0`**, not "1–8". Gold THAI_ID first-digit
histogram, counted from `benchmark/data/gold.jsonl` in this session:

```
{'1': 8, '2': 7, '3': 4, '4': 6, '5': 6, '6': 3, '7': 7, '8': 5, '9': 5}
0-leading gold THAI_ID spans: none
```

A `1–8` gate would drop five gold THAI_ID spans. A `!= 0` gate drops none, so
the reclassification is recall-neutral on gold. `_gen_thai_id`
(`fp_generator.py:24`) already draws its first digit from `1..9`, so the
synthetic corpus is consistent with the `!= 0` gate too.

---

## 2. HOUSE_REG_ID — 11 digits verified, checksum unverified

**Shape.** 11 digits, written `0000-000000-0`, printed in the top-left corner of
every page of the blue house-registration book (ทะเบียนบ้าน). Digits 1–4 are the
local registrar office code (province + district), digits 5–10 are the sequence
for that office, digit 11 is described as a check digit.

Sources.

- PPTV HD36, "วิธีดูรหัสประจำบ้าน" — "ลักษณะตัวเลขมีจำนวนทั้งหมดถึง 11 หลักด้วยกัน"
  and "ระบุไว้ทุกหน้าในเล่มสมุดทะเบียนบ้าน อยู่มุมบนซ้ายของทะเบียนบ้าน". Fetched
  and read in this session. It does **not** mention a check digit.
  <https://www.pptvhd36.com/news/%E0%B8%81%E0%B8%B2%E0%B8%A3%E0%B9%80%E0%B8%A1%E0%B8%B7%E0%B8%AD%E0%B8%87/193974>
- iLaw — "เลขรหัสประจำบ้าน คือเลขรหัส 11 หลัก (0000-000000-0)".
  <https://x.com/iLawclub/status/1642494451875713024>
- Bangkok Biznews, "วิธีดูรหัสประจำบ้าน 11 หลัก".
  <https://www.bangkokbiznews.com/news/news-update/1061749>
- nayoo.co, "รหัสประจําบ้าน คืออะไร" — the source that assigns digits 1–4 to the
  registrar office, 5–10 to the sequence, and calls digit 11 a check digit.
  <https://nayoo.co/khonkaen/blogs/what-is-house-number>

**Checksum verdict: unverified.** Only one secondary source claims a check digit
and none states an algorithm. Real house codes are not public record, so the
five-vector bar the plan sets for JURISTIC_ID cannot be met here — not "we did
not try", but "the evidence does not exist publicly". Attempting the citizen-ID
mod-11 on an 11-digit value is not even well-defined (the weights are specified
for 13 digits), and there is nothing to test it against.

Consequence: HOUSE_REG_ID ships **shape-only, cue-gated 0.9**, exactly as the
plan's table already says. No `is_valid_house_reg` helper is to be written, and
the generator emits 11 random digits with no checksum step.

Current behaviour, measured this session, confirms the plan's precedence claim —
a cued 11-digit run falls through to `ID_NUMBER` at 0.8 today, so a 0.9
HOUSE_REG_ID wins `_deduplicate` without any other change:

```
'เลขรหัสประจำบ้าน 10240012345 ตามทะเบียนบ้าน' -> ID_NUMBER '10240012345' 0.8
```

---

## 3. DRIVER_LICENSE — 8 digits kept, evidence is secondary

**Verdict: unverified (secondary sources only).** No Department of Land Transport
publication describing the licence-number format was found. What was found:

- Pantip 31353784, "เลขที่ใบขับขี่ดูตรงไหนคะ?" — the poster describes the
  new-format card as carrying "ฉบับที่ 12345678", an 8-digit number, and asks
  whether that or the 13-digit citizen ID is the licence number.
  <https://pantip.com/topic/31353784>
- Pantip 39754337, "เลขใบขับขี่สาธารณะดูตรงไหน" — "เว็บมันต้องการเลข 8 หลัก",
  i.e. downstream systems expect 8 digits.
  <https://pantip.com/topic/39754337>
- lemon8, "วิธีดูเลขใบอนุญาตขับรถ…เลข 8" — locates the number on the front of the
  card near the name and dates, and warns against using the 13-digit citizen ID
  instead. Fetched this session; gives no digit count of its own.
  <https://www.lemon8-app.com/@arfang222/7549561342651695637>
- Wikipedia, "Driving licence in Thailand" — describes the smart card and lists
  "licence number" among the printed fields, without giving a format.
  <https://en.wikipedia.org/wiki/Driving_licence_in_Thailand>

**Correction the research forces.** The 8-digit shape is the *smart-card era*
format only. Older and public-category (ท./บ.) licences use an alphanumeric form
with a slash — the sources show `กก.00000/00` and `กข.12345/53`. That form is
**explicitly out of scope for v1** and must not be added to the pattern: it
collides head-on with `_RE_VEHICLE_PLATE` (`[ก-ฮ]{1,3}\s*\d{1,4}`) and with the
document-numbering suppressions the negative slice depends on. Adding it is a
separate, evidence-first change with its own precision campaign.

The spec table value stays **8 digits, cue-gated only, 0.9** — the same value the
plan proposed, now with its limits written down rather than assumed. Because the
shape carries no self-validating structure, the cue gate is the whole of the
precision story; an uncued 8-digit run must never be labelled DRIVER_LICENSE.

Current behaviour, measured this session, confirms the plan's precedence claim:

```
'ใบขับขี่เลขที่ 63012345 ออกโดยกรมการขนส่งทางบก' -> ID_NUMBER '63012345' 0.8
```

LINE_ID and GPS_COORD produce nothing at all today, so no precedence conflict
exists for those two:

```
'ติดต่อทาง LINE ID @somchai_j99 ได้เลย'  -> (no entities)
'จุดนัดพบ 13.7563, 100.5018 หน้าตึก'      -> (no entities)
'ราคา 12.50, 100.75 บาท'                 -> (no entities)
```

---

## The frozen spec table

Copied from the implementation plan with the Step-1–3 corrections applied. This
table, not the plan, is the contract for Tasks 2–9.

| data_type | Thai token label | Shape | Score | Cue regex (30-char window before) | Surrogate |
|---|---|---|---|---|---|
| `JURISTIC_ID` | `ทะเบียนนิติบุคคล` | 13 digits starting `0`, plain or dashed `0-1075-36000-10-2` | **1.0 — checksum verified, so the cue-gated 0.9 fallback is dropped** | `นิติบุคคล\|ทะเบียนบริษัท\|ทะเบียนพาณิชย์\|เลข(?:ประจำตัว)?ผู้เสียภาษี\|tax\s*id\|juristic` | `0` + 12 digits, **checksum-valid** (weights `13..2`, `(11 - total % 11) % 10`) |
| `DRIVER_LICENSE` | `ใบขับขี่` | 8 digits, cue-gated ONLY (smart-card format; legacy `กก.00000/00` out of scope) | 0.9 | `ใบขับขี่\|ใบอนุญาตขับขี่\|ใบอนุญาตขับรถ\|driv(?:er'?s?\|ing)\s*licen[cs]e` | 8 digits |
| `LINE_ID` | `ไลน์ไอดี` | `@?[A-Za-z0-9._-]{4,24}` within 12 chars after cue, same line, cue-gated ONLY | 0.9 | `(?:LINE\|ไลน์)\s*(?:ID\|ไอดี)?` (cue BEFORE value) | lowercase letters+digits, length-preserving, keep leading `@` |
| `GPS_COORD` | `พิกัด` | `lat, lon` decimal pair, both with ≥4 decimals, lat∈[-90,90], lon∈[-180,180] | 0.95 (no cue needed) | — | `f"{rng.uniform(5.6, 20.5):.6f}, {rng.uniform(97.3, 105.6):.6f}"` |
| `HOUSE_REG_ID` | `รหัสประจำบ้าน` | 11 digits, cue-gated ONLY, **no checksum** | 0.9 | `รหัสประจำบ้าน\|เลขรหัสประจำบ้าน` | 11 digits, no checksum |

Shared rules for all five (unchanged from the plan except where marked).

- `redact_type="FP"` (the anonymizer routes FP → `generate_fp`; see
  `amphrang/engine/detectors/fn_scanner.py:16-17` for the trap).
- Alnum-boundary lookarounds `(?<![A-Za-z0-9_])…(?![A-Za-z0-9_])` for
  latin/digit shapes, `(?<!\d)…(?!\d)` for pure digit runs (glued-to-Thai
  recall; see `_RE_PASSPORT_TH`).
- Value in regex **group 1** (`_make_entity` uses group 1).
- Membership in `SAFE_OUTBOUND_LEAK_TYPES` and `_OBFUSCATED_STRUCTURED_TYPES`
  (all five are structured).
- `canonical_value` folding — digits-only fold for JURISTIC_ID / DRIVER_LICENSE /
  HOUSE_REG_ID; strip leading `@` + casefold for LINE_ID; whitespace-fold for
  GPS_COORD (default branch already does this — only the first four need code).
- **CORRECTED precedence fact.** THAI_ID and JURISTIC_ID are *not* disjoint
  today. `_RE_THAI_ID` has no leading-digit restriction and step 1 already emits
  every real juristic number as THAI_ID at 1.0. Task 2 must gate THAI_ID step 1
  on **first digit `!= '0'`** (not "1–8" — gold contains five `9`-leading
  THAI_IDs) and route the `0`-leading checksum-valid case to JURISTIC_ID.
- Unchanged precedence facts. DRIVER_LICENSE (8 digits, 0.9 cue-gated) outranks
  STUDENT_ID/ID_NUMBER (0.8) in `_deduplicate` by score; a doc with BOTH driver
  and student cues near one 8-digit run resolves by nearest cue
  (`_disambiguate_driver_student`, modelled on `_disambiguate_bank_student` at
  `fp_detector.py:162-195`). HOUSE_REG_ID (11 digits) overlaps `_RE_STUDENT_ID`
  (8–12); cue-gated 0.9 beats 0.8. Both were re-measured this session and both
  currently land on `ID_NUMBER` at 0.8, so 0.9 wins.
- **No new checksum module.** `is_valid_juristic_id` delegates to the existing
  `amphrang/engine/detectors/thai_id.py::is_valid_thai_id` after separator
  stripping. `_gen_juristic_id` mirrors `_gen_thai_id` with the first digit
  pinned to `0`.

## Blind set

Blind-v1 is frozen; these types enter the blind corpus only at the next rotation.

Nothing in this record was derived from `benchmark/data/blind-*`, and no blind
run was performed.

## Consequences

- Task 2 ships JURISTIC_ID at score 1.0 on checksum, and must land the THAI_ID
  `!= '0'` gate in the same change or the type is unreachable.
- Task 3's `_gen_juristic_id` produces checksum-valid values; Task 5's gold
  juristic values must also be checksum-valid, since the detector will reject
  invalid ones outright.
- HOUSE_REG_ID and DRIVER_LICENSE carry no validation beyond shape plus cue.
  Their precision floor is the cue regex, and Task 5's look-alike documents are
  the only thing policing it.
- The legacy alphanumeric driving-licence format is a known, deliberate gap.

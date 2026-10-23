# Blind evaluation set v3 (blind-v3)

- Date: 2026-10-24
- Status: accepted; pre-registration, written before any v3 document exists
- Extends: [2026-07-28 blind set protocol](2026-07-28-blind-set-protocol.md)
  and [2026-10-19 blind-v2 protocol](2026-10-19-blind-v2-protocol.md), whose
  storage, validation, aggregate-only scoring and audit-log rules apply
  unchanged unless this record says otherwise

## Problem

`blind-v2` reveal 1 (2026-10-19) measured the current detector at entity F2
0.799 with PHONE recall 0.69, CREDIT_CARD 0.65 and STUDENT_ID 0.36. A recall
campaign now changes the detector (`feat/recall-campaign`), so v2 stops being
held out for the new code the moment its aggregates steer the work. The
STT52/YRSS poster on 2026-11-24 needs a held-out number for the detector it
shows, and the product goal is Thai government use, where the failure that
cannot be accepted is a readable identity number.

A research pass on 2026-10-24 (`ai-guard/reports/หมวดข้อมูล PDPA รูปแบบ PII
และเครื่องมือ PDF.md`, outside this repository) found that most identity
numbers leaked from Thai government sites sit in tabular rosters from local
administrations, not in prose, and listed the real formats Thai documents use.
v1 and v2 had no roster slice.

Rotation reason (predeclared in the v1 protocol): the detector under test
changes and v2's aggregates are known to the development context.

## Decisions

### Authoring and isolation

- Same as v2: the draft is written by a different model family (OpenAI Codex
  via the `codex` CLI) than the one that writes detector rules, in
  `C:\Users\teera\aiguard-blind-v3\author\`, outside every repository. The
  author receives only the annotation guidelines, the brief, the value pools
  and the validator. It never receives detector source, gold, dev data,
  blind-v1/v2, or this campaign's research report.
- An independent reviewer context (a Claude subagent that has not seen the
  drafting) checks missed PII, wrong labels, span glitches and negative-slice
  purity under the v1 fix-only rule, in `C:\Users\teera\aiguard-blind-v3\review\`.
- No pre-freeze detector disagreement pass (as in v2).
- Neither context reports document text or values back to the development
  context; replies are counts and error kinds only.

### Composition (247 documents)

| slice | docs | layer |
|---|---|---|
| roster (new) | 40 | natural |
| gov_form | 20 | natural |
| finance | 14 | natural |
| medical | 12 | natural |
| education | 14 | natural |
| long_form | 12 | natural |
| messy | 18 | balanced |
| id_docs | 15 | balanced |
| bank_phone | 15 | balanced |
| student_id_varied | 15 | balanced |
| address_varied | 12 | balanced |
| name_no_cue | 10 | balanced |
| negative | 50 | negative |

Type floors are raised so the weak types clear `DESCRIPTIVE_N` (50):
NAME 120, ADDRESS 80, PHONE 80, THAI_ID 80, BANK_ACCOUNT 60,
DATE_OF_BIRTH 60, CREDIT_CARD 50, STUDENT_ID 50, EMAIL 40, PASSPORT 30,
VEHICLE_PLATE 30 (`TYPE_MINIMUMS_BY_VERSION` in `benchmark/blind.py`).

The 11 entity types are unchanged so v3 compares with v1 and v2. New
categories the research found (Laser ID, Section 26 sensitive fields) are out
of scope for v3 scoring.

### Realism brief

The brief asks for the writing conventions the research documented, stated
as how Thai documents look, not as detector weaknesses: phone numbers with
`+66`, `66`, `0066`, `(0)`, dashes after two or three digits, dots, spaces,
Thai digits and extensions; landlines; card numbers of 13 to 19 digits across
networks with grouping; bank accounts of 10 to 15 digits with bank-style
dashes; student IDs of several lengths with and without separators; Buddhist
and Gregorian dates in numeric, abbreviated and spelled-out forms; roster
tables flattened with spaces, tabs or pipes. The author is told the list is a
minimum, not a template.

Limitation, accepted: the same research informs both the brief and the
detector fixes, so v3 measures generalisation to unseen documents and values
written in documented real-world formats, not to formats nobody has
described.

### Validation changes (benchmark plumbing only)

- New `roster` slice (`natural` layer); gold tests exclude it.
- CREDIT_CARD values may be 13 to 19 digits (still Luhn-valid).
- THAI_ID values still must pass mod-11; corrupted IDs stay out of v3.

### New secondary metric

`full_leak_rate` and `partial_leak_rate` (added to `benchmark/scorer.py`
before any v3 document exists): a gold entity is a full leak when none of its
letters or digits is covered by any prediction of any type, and a partial
leak when some are not. Entity F2 stays the primary metric; full-leak rate is
the product's safety metric.

### System under test and reveal budget: 2

1. The campaign's final detector, frozen at a tagged commit on
   `feat/recall-campaign`, CRF default engine. Primary result.
2. The pre-campaign detector (`main` at `19fe9f0`), same engine, as the
   before/after baseline. Revealed only after reveal 1, so no v3 aggregate
   can steer the campaign.

Freezing the detector and spending reveal 1 requires the owner's approval.
No detector change may land between that freeze and the reveals.

## Known limitations

- Synthetic and agent-authored, as v1 and v2.
- The development context chose the composition and the realism brief.
- The draft and its authoring logs exist on local disk outside the repository.

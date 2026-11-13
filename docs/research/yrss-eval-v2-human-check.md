# YRSS evaluation v2: human annotation check

Protocol: [pre-registration](../decisions/2026-11-13-yrss-eval-v2.md), "Annotation
check". Rules: [annotation guide](yrss-eval-v2-annotation-guide.md). All text is synthetic.

## Who may annotate

One person who reads Thai and did **not** write or read the templates or the
documents. They get the guide ("What gets a label" is enough) and the packet,
and nothing else: no gold labels, no detector output, no hints from the owner.

## Owner: make the packet

```
python -m benchmark.yrss_v2.agreement export --split test --out ~/yrss-v2-human-check
```

This samples whole families (one document each) until about 10% of the split
is covered, keeping the split's share of documents without personal data. The
seed is fixed. The folder holds test text, so it must be outside the
repository (the command refuses a git work tree). Never commit or upload it.

- `documents.jsonl` (`doc_id` and `text` only) and `answers.csv` (empty sheet);
- `manifest.json`: seed, document ids, corpus hash. The owner keeps this one.

## Annotator: fill the answer sheet

For every piece of personal data, add one row to `answers.csv`: the document
id, the type, and the text **copied exactly** (paste it; do not retype it).

- Go in reading order. One row per mention: a name used twice is two rows.
- Copy the value only, not the field name or the title in front of it.
- A document with no personal data gets one row with type `NONE`.
- Allow about 2 to 3 minutes per document. Work alone; decide from the guide.
- Types: NAME, ADDRESS, DATE_OF_BIRTH, THAI_ID, PHONE, EMAIL, BANK_ACCOUNT,
  CREDIT_CARD, PASSPORT, VEHICLE_PLATE, DRIVER_LICENSE.

Invented example:

```
doc_id,type,text
demo-001-v0,NAME,มานี ใจดี
demo-001-v0,PHONE,02-555-0199
demo-001-v0,NAME,มานี ใจดี
demo-002-v0,NONE,
```

Use a text editor, or a spreadsheet with the `text` column set to "Text" first
(or long numbers change). Quote a value that has a comma. Save as UTF-8 CSV.

## Owner: score and report

```
python -m benchmark.yrss_v2.agreement score --manifest ~/yrss-v2-human-check/manifest.json \
    --answers ~/yrss-v2-human-check/answers.csv --report human-check-report.json
```

The report has no document text and no values. It gives Cohen's kappa over
character labels (all characters, and without whitespace) with a 95% bootstrap
interval over documents; exact-span and overlap agreement from the gold side
and the annotator side; counts by type pair; and the documents that disagree,
by kind (missing, extra, boundary, type). Rows whose text is not found are
listed by row number. Fix copy mistakes only and score again; never change a
labeling decision after seeing the report.

The kappa values, intervals, and span agreement are appended to the
pre-registration as a dated addendum with the sample seed; the record itself
is not edited. If this is not done before 24 November 2026, the poster says
the corpus is single-annotated.

# aiguard

Thai PII detection, anonymization, and PDF redaction for Python — mask
personal data before it reaches an external AI, restore it locally.

```
pip install aiguard
```

```python
import aiguard

text = "ผมชื่อสมชาย ใจดี เบอร์ 081-234-5678 บัตรประชาชน 1-2345-67890-12-3"

# Detect: spans index into your text
for entity in aiguard.detect(text):
    print(entity.data_type, entity.span)

# Mask -> send to an LLM -> restore
masked = aiguard.anonymize(text, mode="surrogate")
reply = call_your_llm(masked.text)          # only masked text leaves the process
restored = aiguard.restore(reply, masked.mapping)

# Multi-turn: the mapping never leaves the Session object
with aiguard.Session(mode="token") as session:
    turn1 = session.anonymize(text)
    answer = call_your_llm(turn1.text)
    print(session.restore(answer).text)

# PDPA risk analysis (no raw values in the result)
aiguard.analyze(text)

# Permanent PDF blackout (flattened; scanned PDFs need `pip install aiguard[ocr]`)
aiguard.redact_pdf("input.pdf", "redacted.pdf")
```

## What it detects

Structured Thai identifiers with checksum validation (national ID mod-11,
phone, bank account, credit card, passport, and more) plus names, addresses,
dates, and organizations via Thai NER (PyThaiNLP thainer-CRF, offline) with
context-cue recall boosters. Detection quality is measured against a
hand-authored, twice-adjudicated gold corpus (in `benchmark/`), including a
negative (no-PII) slice so the false-positive rate is a reported number, not
a guess.

## Design promises

- **Fail closed.** If a masked result would still carry residual PII
  (structured, text-based, or a bare 6+ digit run), `anonymize` raises
  `aiguard.LeakBlockedError` instead of returning a partial mask.
- **Local only.** Detection and masking run in-process. The library makes no
  network calls and keeps no state on disk.
- **The mapping is yours to guard.** `anonymize` returns the
  pseudonym→original mapping to you; keeping it out of logs and storage is
  your responsibility. Prefer `Session` when it can stay in process memory.
- **Honest labels.** Recall is preferred over precision, but a business date
  is labeled `DATE`, not a fake birthday, and an invoice number is not a
  passport.

## PDPA tooling (CLI)

The `aiguard` console command carries the PDPA artifact generators —
processing receipt (มาตรา 39), breach assessment (มาตรา 37(4)), and DSAR
locate (มาตรา 30) — each producing a value-free JSON + Thai PDF pair:

```
aiguard report document.txt
aiguard receipt issue document.txt -o receipt.json --pdf receipt.pdf
aiguard breach assess ./leaked_files -o breach.json --pdf breach.pdf
aiguard dsar locate ./documents --subject-file subject.txt -o dsar.json
```

## Extras

| Extra | Adds |
|---|---|
| `aiguard[server]` | Local FastAPI HTTP server (`app.server`) |
| `aiguard[ml]` | WangchanBERTa/union NER engines + semantic Section-26 detector |
| `aiguard[ocr]` | PaddleOCR pipeline for scanned/hybrid PDFs |

## Stability

Only the `aiguard` module surface follows semver. `pii_redactor.*` and
`app.*` are internal; import them at your own risk.

## Provenance

Extracted from [thai-pii-redaction](https://github.com/Teerapat-Vatpitak/thai-pii-redaction)
(AI Guard 3.0.0), keeping the detection engine, benchmark corpus, and PDPA
tooling; the browser-extension/desktop/native-broker storefronts stayed
behind. Apache-2.0.

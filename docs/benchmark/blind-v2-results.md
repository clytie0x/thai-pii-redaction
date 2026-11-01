# Blind-v2 comparison results

Measured 2026-11-01, then re-measured the same day after the surface and name
fixes. Neither run opened the sealed protocol corpus
`benchmark/data/blind-v2.enc`. Neither freeze is a real-document accuracy claim.

Two locked synthetic sets are scored below. The original freeze (seed
`20261101`, 82 documents, SHA-256
`ce0b88a3dd2281133f85ddbcdc38a5498f83865754e5bb77510bd12553ce8624`) is the
labeled-form set from the first comparison. The hard test split (seed
`20261103`, 60 documents, SHA-256
`90749a8891d42b924bbfbbb690f9637ab599867013f27c4a3ed459e8f3aaca11`) uses
different sentence frames and was not inspected while the detectors were
changed. A dev split (seed `20261102`, SHA-256
`b169fcb72add15dc46cdd62fcb3dac179a4d0b9aa467ad0fb29a40514c76273b`) was the
only split read during the fix. It is not in the tables.

Entity matching is type-aware overlap. Headline scores are micro precision,
recall, and F2, plus an unweighted macro over the twelve redaction types that
have gold spans. Peak memory is the tracemalloc peak during that document's
`predict` call, after one unscored warmup. It is not resident-set size. Cost
is zero: every system ran on CPU with no API call.

The first comparison, before these fixes, scored AI Guard at micro F2 0.920
(precision 0.906, recall 0.924) on the original freeze. The re-run below is
0.964. The gain is the obscured-digit and obscured-name recovery. Regex,
Presidio, PyThaiNLP, and WangchanBERTa entity scores on that freeze did not
move. Their latency moved by a few milliseconds, which is runner noise.

## Reproduce

Core install, from the repository root:

```bash
python -m pip install -r requirements.txt
python -m benchmark.blind_v2 --self-check
python -m benchmark.blind_v2
```

The hard locks are checked by `tests/test_hard_set.py`. The rendered text is
not committed.

Optional baselines are not product dependencies. Without them those rows are
`skipped`.

```bash
python -m pip install presidio-analyzer==2.2.360 'spacy==3.8.7'
python -m spacy download en_core_web_sm
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install transformers==4.46.3 sentencepiece
```

The prompt-only row needs a local model. This run used Ollama 0.40.13 and
`gemma3:1b` (about 806 MB) on CPU. A Typhoon model was not loaded: the 4B
builds do not fit the 4.8 GiB this process could see. No API key was read.
The full document set was scored, not a subset. One redaction call took about
1.2 seconds after the model was loaded.

Versions on this run: PyThaiNLP 5.4.0 (`thainer` and `thainer-v2`),
Presidio analyzer 2.2.360 with spaCy 3.8.7 / `en_core_web_sm` 3.8.0,
transformers 4.46.3, torch 2.15.0+cpu. Thai coverage in Presidio is the
pattern recognizers registered by the harness.

## Original freeze

Seed `20261101`, 82 documents.

| System | Status | P | R | F2 | macro F2 | p50 ms | p95 ms | p50 KiB | p95 KiB | cost USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aiguard | ok | 0.914 | 0.977 | 0.964 | 0.988 | 22.7 | 30.3 | 87201.2 | 87270.9 | 0.00 |
| regex | ok | 1.000 | 0.924 | 0.938 | 0.967 | 0.1 | 0.1 | 10.1 | 17.7 | 0.00 |
| presidio | ok | 0.892 | 0.882 | 0.884 | 0.921 | 13.0 | 21.0 | 11208.6 | 11424.8 | 0.00 |
| pythainlp-ner | ok | 0.368 | 0.176 | 0.196 | 0.058 | 6.0 | 9.9 | 58.4 | 78.3 | 0.00 |
| wangchanberta-ner | ok | 0.295 | 0.511 | 0.446 | 0.192 | 43.7 | 74.5 | 89.6 | 128.3 | 0.00 |
| llm | ok | 0.400 | 0.008 | 0.009 | 0.004 | 1625.1 | 2773.4 | 169.6 | 233.6 | 0.00 |

`gemma3:1b` almost never returned a JSON span that matched the source text.
Precision 0.400 is two hits and a handful of misses, not a usable redactor.
The regex baseline still shares this generator's field labels. On this freeze
AI Guard is now ahead of it (micro F2 0.964 versus 0.938) because the regex
still misses obscured national IDs (recall 0.714) and phones (0.864).

### Per entity, original freeze

| System | Type | n | P | R | F2 |
|---|---|---:|---:|---:|---:|
| aiguard | THAI_ID | 35 | 1.000 | 1.000 | 1.000 |
| aiguard | PHONE | 44 | 1.000 | 1.000 | 1.000 |
| aiguard | EMAIL | 28 | 1.000 | 1.000 | 1.000 |
| aiguard | BANK_ACCOUNT | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | CREDIT_CARD | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | PASSPORT | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | VEHICLE_PLATE | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | STUDENT_ID | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | DATE_OF_BIRTH | 22 | 1.000 | 1.000 | 1.000 |
| aiguard | NAME | 70 | 0.889 | 0.914 | 0.909 |
| aiguard | ADDRESS | 15 | 0.789 | 1.000 | 0.949 |
| aiguard | IBAN | 8 | 1.000 | 1.000 | 1.000 |
| regex | THAI_ID | 35 | 1.000 | 0.714 | 0.758 |
| regex | PHONE | 44 | 1.000 | 0.864 | 0.888 |
| regex | EMAIL | 28 | 1.000 | 1.000 | 1.000 |
| regex | BANK_ACCOUNT | 8 | 1.000 | 1.000 | 1.000 |
| regex | CREDIT_CARD | 8 | 1.000 | 1.000 | 1.000 |
| regex | PASSPORT | 8 | 1.000 | 1.000 | 1.000 |
| regex | VEHICLE_PLATE | 8 | 1.000 | 1.000 | 1.000 |
| regex | STUDENT_ID | 8 | 1.000 | 1.000 | 1.000 |
| regex | DATE_OF_BIRTH | 22 | 1.000 | 1.000 | 1.000 |
| regex | NAME | 70 | 1.000 | 0.943 | 0.954 |
| regex | ADDRESS | 15 | 1.000 | 1.000 | 1.000 |
| regex | IBAN | 8 | 1.000 | 1.000 | 1.000 |
| presidio | THAI_ID | 35 | 1.000 | 0.686 | 0.732 |
| presidio | PHONE | 44 | 0.973 | 0.818 | 0.845 |
| presidio | EMAIL | 28 | 1.000 | 0.929 | 0.942 |
| presidio | BANK_ACCOUNT | 8 | 1.000 | 1.000 | 1.000 |
| presidio | CREDIT_CARD | 8 | 1.000 | 1.000 | 1.000 |
| presidio | PASSPORT | 8 | 1.000 | 0.875 | 0.897 |
| presidio | VEHICLE_PLATE | 8 | 1.000 | 0.875 | 0.897 |
| presidio | STUDENT_ID | 8 | 1.000 | 1.000 | 1.000 |
| presidio | DATE_OF_BIRTH | 22 | 1.000 | 0.909 | 0.926 |
| presidio | NAME | 70 | 0.857 | 0.943 | 0.924 |
| presidio | ADDRESS | 15 | 1.000 | 0.867 | 0.890 |
| presidio | IBAN | 8 | 1.000 | 1.000 | 1.000 |
| pythainlp-ner | THAI_ID | 35 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | PHONE | 44 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | EMAIL | 28 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | BANK_ACCOUNT | 8 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | CREDIT_CARD | 8 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | PASSPORT | 8 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | VEHICLE_PLATE | 8 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | STUDENT_ID | 8 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | DATE_OF_BIRTH | 22 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | NAME | 70 | 0.958 | 0.657 | 0.701 |
| pythainlp-ner | ADDRESS | 15 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | IBAN | 8 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | THAI_ID | 35 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | PHONE | 44 | 0.326 | 0.955 | 0.689 |
| wangchanberta-ner | EMAIL | 28 | 0.444 | 1.000 | 0.800 |
| wangchanberta-ner | BANK_ACCOUNT | 8 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | CREDIT_CARD | 8 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | PASSPORT | 8 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | VEHICLE_PLATE | 8 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | STUDENT_ID | 8 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | DATE_OF_BIRTH | 22 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | NAME | 70 | 0.577 | 0.914 | 0.818 |
| wangchanberta-ner | ADDRESS | 15 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | IBAN | 8 | 0.000 | 0.000 | 0.000 |
| llm | THAI_ID | 35 | 0.250 | 0.029 | 0.035 |
| llm | PHONE | 44 | 0.000 | 0.000 | 0.000 |
| llm | EMAIL | 28 | 0.000 | 0.000 | 0.000 |
| llm | BANK_ACCOUNT | 8 | 0.000 | 0.000 | 0.000 |
| llm | CREDIT_CARD | 8 | 0.000 | 0.000 | 0.000 |
| llm | PASSPORT | 8 | 0.000 | 0.000 | 0.000 |
| llm | VEHICLE_PLATE | 8 | 0.000 | 0.000 | 0.000 |
| llm | STUDENT_ID | 8 | 0.000 | 0.000 | 0.000 |
| llm | DATE_OF_BIRTH | 22 | 0.000 | 0.000 | 0.000 |
| llm | NAME | 70 | 1.000 | 0.014 | 0.018 |
| llm | ADDRESS | 15 | 0.000 | 0.000 | 0.000 |
| llm | IBAN | 8 | 0.000 | 0.000 | 0.000 |

Negative-slice false positives are included in the micro score. Predictions
outside the twelve redaction types count as micro false positives only.

| System | Negative clean | False positives on negative docs | Other-scheme false positives |
|---|---:|---:|---:|
| aiguard | 7/12 | 5 | 12 |
| regex | 12/12 | 0 | 0 |
| presidio | 11/12 | 1 | 16 |
| pythainlp-ner | 8/12 | 4 | 77 |
| wangchanberta-ner | 10/12 | 2 | 152 |
| llm | 12/12 | 0 | 0 |

### Ablations, original freeze

Delta is the score with that layer removed minus the full AI Guard score. A
negative delta means the layer helped. Zero means this freeze did not move.

| Layer removed | micro F2 | delta F2 | delta recall |
|---|---:|---:|---:|
| full pipeline | 0.964 |  |  |
| fp | 0.550 | -0.414 | -0.458 |
| tb | 0.770 | -0.193 | -0.244 |
| fn | 0.964 | +0.000 | +0.000 |
| record_names | 0.964 | +0.000 | +0.000 |
| address_merge | 0.910 | -0.054 | +0.000 |
| facility_filter | 0.964 | +0.000 | +0.000 |
| student_relabel | 0.964 | +0.000 | +0.000 |

### Section 26, original freeze

Keyword scan micro recall 1.000 on 11 labeled documents (HEALTH 4, and one
each of the other seven categories). The phrases in this freeze contain the
keywords. The labels are warn/report, not redaction spans.

### Utility, original freeze

Eighteen questions (9 safe, 9 that need a value inside a gold span). An answer
counts when the expected text occurs in the reply after whitespace and case
folding. The answerer is `gemma3:1b`. Absolute accuracy is low because the
model is small. The comparison is raw text versus the same question after that
system's spans were replaced with `[REDACTED]`.

| System | Safe raw | Safe redacted | PII raw | PII redacted |
|---|---:|---:|---:|---:|
| aiguard | 0.556 | 0.333 | 0.556 | 0.111 |
| regex | 0.667 | 0.556 | 0.556 | 0.000 |
| presidio | 0.667 | 0.333 | 0.556 | 0.000 |
| pythainlp-ner | 0.778 | 0.333 | 0.667 | 0.222 |
| wangchanberta-ner | 0.556 | 0.556 | 0.556 | 0.000 |
| llm | 0.556 | 0.556 | 0.667 | 0.556 |

Redaction lowers PII-question accuracy, which is the point: the answer was the
masked value. It also lowers some safe-question accuracy, so the mask removes
context the small model was using. The llm row barely changes because that
system masked almost nothing.

## Hard test split

Seed `20261103`, 60 documents. Free-form prose, no field labels, with noise,
per-character spaces, zero-width characters, Thai digits, Arabic-Indic digits,
one OCR lookalike, mixed Thai and English, eight paraphrased Section 26
categories, and four clean negative documents.

| System | Status | P | R | F2 | macro F2 | p50 ms | p95 ms | p50 KiB | p95 KiB | cost USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aiguard | ok | 0.980 | 0.962 | 0.965 | 0.993 | 8.8 | 16.3 | 83.1 | 137.2 | 0.00 |
| regex | ok | 1.000 | 0.260 | 0.305 | 0.382 | 0.1 | 0.1 | 3.4 | 4.5 | 0.00 |
| presidio | ok | 0.607 | 0.490 | 0.510 | 0.609 | 7.9 | 12.0 | 352.9 | 552.0 | 0.00 |
| pythainlp-ner | ok | 0.444 | 0.231 | 0.255 | 0.057 | 2.6 | 4.9 | 32.1 | 48.0 | 0.00 |
| wangchanberta-ner | ok | 0.276 | 0.404 | 0.370 | 0.159 | 29.9 | 40.0 | 61.2 | 83.6 | 0.00 |
| llm | ok | 0.000 | 0.000 | 0.000 | 0.000 | 1295.7 | 2290.8 | 151.9 | 210.6 | 0.00 |

The regex row collapses here (recall 0.260) because its cues are field labels
this split does not use. Email, card, plate, and IBAN still match as patterns.
Names, addresses, bank accounts, passports, student ids, and birth dates do
not. That is the ceiling the first freeze could not show.

Tracemalloc peaks are lower than on the original freeze because these
documents are short. The NER weights were allocated during warmup.

### Per entity, hard test split

| System | Type | n | P | R | F2 |
|---|---|---:|---:|---:|---:|
| aiguard | THAI_ID | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | PHONE | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | EMAIL | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | BANK_ACCOUNT | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | CREDIT_CARD | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | PASSPORT | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | VEHICLE_PLATE | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | STUDENT_ID | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | DATE_OF_BIRTH | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | NAME | 38 | 1.000 | 0.895 | 0.914 |
| aiguard | ADDRESS | 6 | 1.000 | 1.000 | 1.000 |
| aiguard | IBAN | 6 | 1.000 | 1.000 | 1.000 |
| regex | THAI_ID | 6 | 1.000 | 0.167 | 0.200 |
| regex | PHONE | 6 | 1.000 | 0.333 | 0.385 |
| regex | EMAIL | 6 | 1.000 | 1.000 | 1.000 |
| regex | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 |
| regex | CREDIT_CARD | 6 | 1.000 | 1.000 | 1.000 |
| regex | PASSPORT | 6 | 0.000 | 0.000 | 0.000 |
| regex | VEHICLE_PLATE | 6 | 1.000 | 1.000 | 1.000 |
| regex | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 |
| regex | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 |
| regex | NAME | 38 | 0.000 | 0.000 | 0.000 |
| regex | ADDRESS | 6 | 0.000 | 0.000 | 0.000 |
| regex | IBAN | 6 | 1.000 | 1.000 | 1.000 |
| presidio | THAI_ID | 6 | 1.000 | 0.167 | 0.200 |
| presidio | PHONE | 6 | 0.833 | 0.833 | 0.833 |
| presidio | EMAIL | 6 | 1.000 | 1.000 | 1.000 |
| presidio | BANK_ACCOUNT | 6 | 1.000 | 1.000 | 1.000 |
| presidio | CREDIT_CARD | 6 | 1.000 | 1.000 | 1.000 |
| presidio | PASSPORT | 6 | 1.000 | 1.000 | 1.000 |
| presidio | VEHICLE_PLATE | 6 | 1.000 | 1.000 | 1.000 |
| presidio | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 |
| presidio | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 |
| presidio | NAME | 38 | 0.750 | 0.237 | 0.274 |
| presidio | ADDRESS | 6 | 0.000 | 0.000 | 0.000 |
| presidio | IBAN | 6 | 1.000 | 1.000 | 1.000 |
| pythainlp-ner | THAI_ID | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | PHONE | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | EMAIL | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | CREDIT_CARD | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | PASSPORT | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | NAME | 38 | 1.000 | 0.632 | 0.682 |
| pythainlp-ner | ADDRESS | 6 | 0.000 | 0.000 | 0.000 |
| pythainlp-ner | IBAN | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | THAI_ID | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | PHONE | 6 | 0.125 | 0.833 | 0.391 |
| wangchanberta-ner | EMAIL | 6 | 0.353 | 1.000 | 0.732 |
| wangchanberta-ner | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | CREDIT_CARD | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | PASSPORT | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | NAME | 38 | 0.674 | 0.816 | 0.783 |
| wangchanberta-ner | ADDRESS | 6 | 0.000 | 0.000 | 0.000 |
| wangchanberta-ner | IBAN | 6 | 0.000 | 0.000 | 0.000 |
| llm | THAI_ID | 6 | 0.000 | 0.000 | 0.000 |
| llm | PHONE | 6 | 0.000 | 0.000 | 0.000 |
| llm | EMAIL | 6 | 0.000 | 0.000 | 0.000 |
| llm | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 |
| llm | CREDIT_CARD | 6 | 0.000 | 0.000 | 0.000 |
| llm | PASSPORT | 6 | 0.000 | 0.000 | 0.000 |
| llm | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 |
| llm | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 |
| llm | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 |
| llm | NAME | 38 | 0.000 | 0.000 | 0.000 |
| llm | ADDRESS | 6 | 0.000 | 0.000 | 0.000 |
| llm | IBAN | 6 | 0.000 | 0.000 | 0.000 |

| System | Negative clean | False positives on negative docs | Other-scheme false positives |
|---|---:|---:|---:|
| aiguard | 4/4 | 0 | 2 |
| regex | 4/4 | 0 | 0 |
| presidio | 3/4 | 1 | 29 |
| pythainlp-ner | 4/4 | 0 | 30 |
| wangchanberta-ner | 4/4 | 0 | 49 |
| llm | 4/4 | 0 | 0 |

### Ablations, hard test split

| Layer removed | micro F2 | delta F2 | delta recall |
|---|---:|---:|---:|
| full pipeline | 0.965 |  |  |
| fp | 0.515 | -0.451 | -0.490 |
| tb | 0.685 | -0.281 | -0.327 |
| fn | 0.965 | +0.000 | +0.000 |
| record_names | 0.965 | +0.000 | +0.000 |
| address_merge | 0.912 | -0.053 | +0.000 |
| facility_filter | 0.965 | +0.000 | +0.000 |
| student_relabel | 0.965 | +0.000 | +0.000 |

The format layer matters more on this split than on the labeled freeze
(recall delta -0.490 versus -0.458). The NER layer matters more too
(-0.327 versus -0.244), which matches prose with no field labels.

### Section 26, hard test split

Keyword micro recall 0.000 on 8 paraphrases that were written without the
current keyword list. Policy is still warn/report, not redaction. The
category names now come from one module, `pii_redactor/pdpa_categories.py`.
The optional sentence-embedding detector was not installed, so it did not run.

### Utility, hard test split

Skipped. This split has no question set. Utility numbers are the original
freeze table above.

# Blind-v2 comparison results

Measured 2026-11-01. This is a local text run of the reproducible synthetic
freeze. It is not a score of the sealed protocol corpus
`benchmark/data/blind-v2.enc`, which was not opened. It is not a tuning set,
and it is not a real-document accuracy claim.

The freeze is seed `20261101`. The plaintext SHA-256 and the counts live in
`benchmark/data/blind-v2-repro.lock.json` (82 documents). Entity matching is
type-aware overlap. Headline scores are micro precision, recall, and F2, plus
an unweighted macro over the twelve redaction types that have gold spans.
Peak memory is the tracemalloc peak during that document's `predict` call,
after one unscored warmup call. It is not resident-set size. Cost is zero
because every system that ran did so on CPU with no API call.

Latency and memory will move on another machine. The entity scores are
determined by the seed and the code.

## Reproduce

Core install, from the repository root:

```bash
python -m pip install -r requirements.txt
python -m benchmark.blind_v2 --self-check
python -m benchmark.blind_v2
```

The measured table also installed optional baselines that are not product
dependencies. Without them, those rows are `skipped` and the reason is printed.

```bash
python -m pip install presidio-analyzer==2.2.360 'spacy==3.8.7'
python -m spacy download en_core_web_sm
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install transformers==4.46.3 sentencepiece
python -m benchmark.blind_v2
```

Versions on this run: PyThaiNLP 5.4.0 (`thainer` and `thainer-v2`),
Presidio analyzer 2.2.360 with spaCy 3.8.7 / `en_core_web_sm` 3.8.0,
transformers 4.46.3, torch 2.15.0+cpu. Thai coverage in Presidio is the
pattern recognizers registered by the harness. Presidio does not ship a Thai
spaCy model; those patterns run on the English pipeline.

## Systems

| System | Status | P | R | F2 | macro F2 | p50 ms | p95 ms | p50 KiB | p95 KiB | cost USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aiguard | ok | 0.906 | 0.924 | 0.920 | 0.965 | 22.9 | 30.4 | 87159.8 | 87231.6 | 0.00 |
| regex | ok | 1.000 | 0.924 | 0.938 | 0.967 | 0.1 | 0.1 | 9.3 | 16.9 | 0.00 |
| presidio | ok | 0.892 | 0.882 | 0.884 | 0.921 | 13.2 | 20.6 | 11213.3 | 11429.9 | 0.00 |
| pythainlp-ner | ok | 0.368 | 0.176 | 0.196 | 0.058 | 6.1 | 8.5 | 58.5 | 78.5 | 0.00 |
| wangchanberta-ner | ok | 0.295 | 0.511 | 0.446 | 0.192 | 38.1 | 57.6 | 91.1 | 129.4 | 0.00 |
| llm | skipped |  |  |  |  |  |  |  |  | n/a |

`llm` was skipped: no local Ollama model, no llama.cpp model file, and no
OpenRouter free-tier key. The platform credential was not read and no paid
call was made. Utility uses the same probe and was skipped for the same
reason, so there is no raw-versus-redacted accuracy number.

The regex row is a cue-and-pattern baseline in `benchmark/blind_v2/baselines.py`.
It is not `detect_fp`. Its field labels are the ordinary labels this generator
also writes, so a higher micro F2 on this freeze does not mean a regex beats
AI Guard on documents it did not see. AI Guard's Thai-ID recall is higher
(0.829 versus 0.714). AI Guard's negative slice is worse: 7 of 12 documents
clean, 5 false positives, plus 13 predictions outside the twelve-type scheme.
The regex baseline was clean on all 12 negative documents.

## Per entity

| System | Type | n | P | R | F2 |
|---|---|---:|---:|---:|---:|
| aiguard | THAI_ID | 35 | 1.000 | 0.829 | 0.858 |
| aiguard | PHONE | 44 | 1.000 | 0.864 | 0.888 |
| aiguard | EMAIL | 28 | 1.000 | 1.000 | 1.000 |
| aiguard | BANK_ACCOUNT | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | CREDIT_CARD | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | PASSPORT | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | VEHICLE_PLATE | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | STUDENT_ID | 8 | 1.000 | 1.000 | 1.000 |
| aiguard | DATE_OF_BIRTH | 22 | 1.000 | 1.000 | 1.000 |
| aiguard | NAME | 70 | 0.886 | 0.886 | 0.886 |
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

Negative-slice false positives are included in the micro score. Outside-scheme
predictions (for example a bare location or organization) count as micro false
positives and do not get a macro row.

| System | Negative clean | False positives on negative docs | Other-scheme false positives |
|---|---:|---:|---:|
| aiguard | 7/12 | 5 | 13 |
| regex | 12/12 | 0 | 0 |
| presidio | 11/12 | 1 | 16 |
| pythainlp-ner | 8/12 | 4 | 77 |
| wangchanberta-ner | 10/12 | 2 | 152 |

## Ablations

Delta is the score with that layer removed minus the full AI Guard score. A
negative delta means the layer helped on this freeze. Zero means this freeze
did not move; it does not mean the layer is unused on gold or on the sealed
blind corpus.

| Layer removed | micro F2 | delta F2 | delta recall |
|---|---:|---:|---:|
| full pipeline | 0.920 |  |  |
| fp | 0.543 | -0.378 | -0.412 |
| tb | 0.729 | -0.191 | -0.237 |
| fn | 0.920 | +0.000 | +0.000 |
| record_names | 0.920 | +0.000 | +0.000 |
| address_merge | 0.868 | -0.052 | +0.000 |
| facility_filter | 0.920 | +0.000 | +0.000 |
| student_relabel | 0.920 | +0.000 | +0.000 |

The format-preserving layer is the largest contributor. The text-based NER
layer is next. Address merging raises precision (F2 up, recall unchanged).
The false-negative scan, parallel-record names, facility filter, and student-id
relabel did not change this freeze.

## Section 26 warn path

AI Guard's keyword scan (`scan_section26`) flagged every labeled category on
this freeze: micro recall 1.000 on 11 labeled documents (HEALTH 4, and one
each of the other seven categories). Those labels are not redaction spans.
`detect_all` does not mask them. That is current policy, and it is also why
keyword recall of 1.000 is not coverage of Section 26.

## Utility

Skipped. Same reason as the prompt-only baseline: no free or local model was
available. The question set is in the freeze (18 questions) and is scored only
when a model answers. A fake answerer is covered by unit tests and is not a
result.

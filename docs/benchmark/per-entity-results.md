# Per-entity results on the blind-v2 locks

Measured 2026-11-03 on this machine. The three sections below are rendered from the JSON in `docs/benchmark/runs/` by `benchmark/blind_v2/present.py`. Scores use Python format `.3f`. The synthetic locks are the only corpus. `benchmark/data/blind-v2.enc` was not opened. Detectors were not changed. This is not a real-document accuracy claim and not a tuning set.

## How a cell is computed

Matching is type-aware overlap in `benchmark/blind_v2/score.py` (`score_predictions`, `prf`). One gold span matches at most one prediction of the same type. F1 is `2PR/(P+R)` and F2 is `5PR/(4P+R)`. Either score is 0 when its denominator is 0. Micro pools true positives, false positives, and false negatives across the twelve redaction types. A prediction whose type is outside that list counts as a micro false positive (`other_false_positives`) and does not get a macro row. Macro is the unweighted mean over types with at least one gold span.

The product row is `predict_ablated(text, None)`, the same assembly order as `detect_all`. `AIGUARD_NER_ENGINE` was unset, so the text layer is the default thainer CRF. Removing `tb` removes `detect_tb`, including the title and context pass inside that function. Removing `fp` removes `detect_fp`, the format and checksum rules. The regex row is the cue-and-pattern baseline in `benchmark/blind_v2/baselines.py`, not `detect_fp`. PyThaiNLP NER and WangchanBERTa NER return mapped tags only.

A NAME miss is cued when `prefix_name_cue` finds one of these tokens in the 16 characters before the gold start and the token is not glued to another letter: ผู้เสียหาย, ข้าพเจ้า, เด็กหญิง, เด็กชาย, นางสาว, น.ส., ด.ช., ด.ญ., ชื่อ, นาง, นาย. The count is `name_misses`.

`tests/test_blind_v2_harness.py` checks that each generated block in this file matches the JSON.

## Environment

Source file: `docs/benchmark/runs/environment.json`.

```json
{
  "cost_usd": 0,
  "date": "2026-11-03",
  "llm_probe": "no local Ollama model, llama.cpp model, or OpenRouter free-tier key is available",
  "llm_scored": false,
  "lock_file_sha256": {
    "freeze": "717b48ec6c3e33f7394d67b5b9698bafde5fc3d02d0ecc90a6486c24b48332fe",
    "hard-dev": "4b06224f475d306a4389781a96e073efc116a25370bf03658fb3a909652888e9",
    "hard-test": "21eda81a3b19e19531775a20b312a5b94405ccba5dbbe27f603f8c55bd5b36cd"
  },
  "ner_engine": "unset; product default is thainer",
  "packages": {
    "pythainlp": "5.4.0",
    "presidio-analyzer": "2.2.360",
    "spacy": "3.8.7",
    "torch": "2.15.0+cpu",
    "transformers": "4.46.3",
    "sentencepiece": "0.2.2",
    "click": "8.5.0"
  },
  "platform": "Linux-6.12.94+-x86_64-with-glibc2.39",
  "python": "3.12.3",
  "spacy_model": "en_core_web_sm 3.8.0",
  "systems": [
    "aiguard",
    "regex",
    "presidio",
    "pythainlp-ner",
    "wangchanberta-ner"
  ],
  "utility": "disabled"
}
```

Python 3.12.3 (3.12.3 is the same interpreter). Platform `Linux-6.12.94+-x86_64-with-glibc2.39`.

## Commands

From the repository root, after `python3 -m venv .venv` and the installs below. No API key was set. `gemma3` was not installed; the llm system was not in `--systems`.

```bash
export PYTHONUTF8=1
export PYTHONUNBUFFERED=1
export HF_HUB_DISABLE_TELEMETRY=1
unset AIGUARD_NER_ENGINE AIFORTHAI_API_KEY TOKENMIND_API_KEY OPENROUTER_API_KEY
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install 'presidio-analyzer==2.2.360' 'spacy==3.8.7'
.venv/bin/python -m pip install click
.venv/bin/python -m spacy download en_core_web_sm
.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install 'transformers==4.46.3' sentencepiece
SYS=aiguard,regex,presidio,pythainlp-ner,wangchanberta-ner
.venv/bin/python -m benchmark.blind_v2 --self-check
.venv/bin/python -m benchmark.blind_v2 --self-check --split hard-dev
.venv/bin/python -m benchmark.blind_v2 --self-check --split hard-test
.venv/bin/python -m benchmark.blind_v2 --systems "$SYS" --no-utility --json docs/benchmark/runs/freeze.json
.venv/bin/python -m benchmark.blind_v2 --split hard-dev --systems "$SYS" --no-utility --json docs/benchmark/runs/hard-dev.json
.venv/bin/python -m benchmark.blind_v2 --split hard-test --systems "$SYS" --no-utility --json docs/benchmark/runs/hard-test.json
```

`spacy download` on spaCy 3.8.7 failed until `click` was installed (`ModuleNotFoundError: click`). Out-of-scheme and negative-document label counts are in `docs/benchmark/runs/negative-labels.json`. They were counted in this session from `predict_ablated(text, None)` with the detector log at ERROR. The test checks that those counts sum to `other_false_positives` and `negative.false_positives`.

Lock files, and the SHA-256 of the file bytes: `benchmark/data/blind-v2-repro.lock.json` `717b48ec6c3e33f7394d67b5b9698bafde5fc3d02d0ecc90a6486c24b48332fe`, `benchmark/data/hard-dev.lock.json` `4b06224f475d306a4389781a96e073efc116a25370bf03658fb3a909652888e9`, `benchmark/data/hard-test.lock.json` `21eda81a3b19e19531775a20b312a5b94405ccba5dbbe27f603f8c55bd5b36cd`. The plaintext hash inside each lock is the `sha256` on the dataset line below.

## Hard test split

dataset `hard-test-v1` seed `20261103` documents 60 sha256 `90749a8891d42b924bbfbbb690f9637ab599867013f27c4a3ed459e8f3aaca11` official `true`

| System | P | R | F1 | F2 | macro P | macro R | macro F1 | macro F2 | p50 ms | cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aiguard | 0.980 | 0.962 | 0.971 | 0.965 | 1.000 | 0.991 | 0.995 | 0.993 | 8.9 | 0.00 |
| regex | 1.000 | 0.260 | 0.412 | 0.305 | 0.500 | 0.375 | 0.399 | 0.382 | 0.1 | 0.00 |
| presidio | 0.607 | 0.490 | 0.543 | 0.510 | 0.715 | 0.603 | 0.623 | 0.609 | 8.5 | 0.00 |
| pythainlp-ner | 0.444 | 0.231 | 0.304 | 0.255 | 0.083 | 0.053 | 0.065 | 0.057 | 2.8 | 0.00 |
| wangchanberta-ner | 0.276 | 0.404 | 0.328 | 0.370 | 0.096 | 0.221 | 0.123 | 0.159 | 30.7 | 0.00 |

| System | Type | n | P | R | F1 | F2 | fp | fn |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| aiguard | THAI_ID | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | PHONE | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | EMAIL | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | BANK_ACCOUNT | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | CREDIT_CARD | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | PASSPORT | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | VEHICLE_PLATE | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | STUDENT_ID | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | DATE_OF_BIRTH | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | NAME | 38 | 1.000 | 0.895 | 0.944 | 0.914 | 0 | 4 |
| aiguard | ADDRESS | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | IBAN | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | negative | 4 |  |  |  |  | clean 4/4; false_positives 0; other_fp 2; name_fn cued 0 uncued 4 | |
| regex | THAI_ID | 6 | 1.000 | 0.167 | 0.286 | 0.200 | 0 | 5 |
| regex | PHONE | 6 | 1.000 | 0.333 | 0.500 | 0.385 | 0 | 4 |
| regex | EMAIL | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | CREDIT_CARD | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | PASSPORT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | VEHICLE_PLATE | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | NAME | 38 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 38 |
| regex | ADDRESS | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | IBAN | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | negative | 4 |  |  |  |  | clean 4/4; false_positives 0; other_fp 0; name_fn cued 0 uncued 38 | |
| presidio | THAI_ID | 6 | 1.000 | 0.167 | 0.286 | 0.200 | 0 | 5 |
| presidio | PHONE | 6 | 0.833 | 0.833 | 0.833 | 0.833 | 1 | 1 |
| presidio | EMAIL | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | BANK_ACCOUNT | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | CREDIT_CARD | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | PASSPORT | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | VEHICLE_PLATE | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| presidio | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| presidio | NAME | 38 | 0.750 | 0.237 | 0.360 | 0.274 | 3 | 29 |
| presidio | ADDRESS | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| presidio | IBAN | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | negative | 4 |  |  |  |  | clean 3/4; false_positives 1; other_fp 29; name_fn cued 0 uncued 29 | |
| pythainlp-ner | THAI_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | PHONE | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | EMAIL | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | CREDIT_CARD | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | PASSPORT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | NAME | 38 | 1.000 | 0.632 | 0.774 | 0.682 | 0 | 14 |
| pythainlp-ner | ADDRESS | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | IBAN | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | negative | 4 |  |  |  |  | clean 4/4; false_positives 0; other_fp 30; name_fn cued 0 uncued 14 | |
| wangchanberta-ner | THAI_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | PHONE | 6 | 0.125 | 0.833 | 0.217 | 0.391 | 35 | 1 |
| wangchanberta-ner | EMAIL | 6 | 0.353 | 1.000 | 0.522 | 0.732 | 11 | 0 |
| wangchanberta-ner | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | CREDIT_CARD | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | PASSPORT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | NAME | 38 | 0.674 | 0.816 | 0.738 | 0.783 | 15 | 7 |
| wangchanberta-ner | ADDRESS | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | IBAN | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | negative | 4 |  |  |  |  | clean 4/4; false_positives 0; other_fp 49; name_fn cued 0 uncued 7 | |

Layer ablation (removed minus full). A negative delta means the layer helped.

| Layer removed | micro P | micro R | micro F1 | micro F2 | delta R | delta F2 |
|---|---:|---:|---:|---:|---:|---:|
| full | 0.980 | 0.962 | 0.971 | 0.965 |  |  |
| fp | 0.817 | 0.471 | 0.598 | 0.515 | -0.490 | -0.451 |
| tb | 1.000 | 0.635 | 0.776 | 0.685 | -0.327 | -0.281 |
| fn | 0.980 | 0.962 | 0.971 | 0.965 | +0.000 | +0.000 |
| record_names | 0.980 | 0.962 | 0.971 | 0.965 | +0.000 | +0.000 |
| address_merge | 0.758 | 0.962 | 0.847 | 0.912 | +0.000 | -0.053 |
| facility_filter | 0.980 | 0.962 | 0.971 | 0.965 | +0.000 | +0.000 |
| student_relabel | 0.980 | 0.962 | 0.971 | 0.965 | +0.000 | +0.000 |

Per-type recall with `tb` removed.

| Type | n | full R | removed R | delta R |
|---|---:|---:|---:|---:|
| THAI_ID | 6 | 1.000 | 1.000 | +0.000 |
| PHONE | 6 | 1.000 | 1.000 | +0.000 |
| EMAIL | 6 | 1.000 | 1.000 | +0.000 |
| BANK_ACCOUNT | 6 | 1.000 | 1.000 | +0.000 |
| CREDIT_CARD | 6 | 1.000 | 1.000 | +0.000 |
| PASSPORT | 6 | 1.000 | 1.000 | +0.000 |
| VEHICLE_PLATE | 6 | 1.000 | 1.000 | +0.000 |
| STUDENT_ID | 6 | 1.000 | 1.000 | +0.000 |
| DATE_OF_BIRTH | 6 | 1.000 | 1.000 | +0.000 |
| NAME | 38 | 0.895 | 0.000 | -0.895 |
| ADDRESS | 6 | 1.000 | 1.000 | +0.000 |
| IBAN | 6 | 1.000 | 1.000 | +0.000 |

Per-type recall with `fp` removed.

| Type | n | full R | removed R | delta R |
|---|---:|---:|---:|---:|
| THAI_ID | 6 | 1.000 | 0.500 | -0.500 |
| PHONE | 6 | 1.000 | 0.000 | -1.000 |
| EMAIL | 6 | 1.000 | 1.000 | +0.000 |
| BANK_ACCOUNT | 6 | 1.000 | 0.000 | -1.000 |
| CREDIT_CARD | 6 | 1.000 | 0.000 | -1.000 |
| PASSPORT | 6 | 1.000 | 0.000 | -1.000 |
| VEHICLE_PLATE | 6 | 1.000 | 0.000 | -1.000 |
| STUDENT_ID | 6 | 1.000 | 0.000 | -1.000 |
| DATE_OF_BIRTH | 6 | 1.000 | 0.000 | -1.000 |
| NAME | 38 | 0.895 | 0.895 | +0.000 |
| ADDRESS | 6 | 1.000 | 1.000 | +0.000 |
| IBAN | 6 | 1.000 | 0.000 | -1.000 |

ADDRESS with `address_merge` removed: precision 1.000 to 0.200, recall 1.000 to 1.000, fp 0 to 24.
Section 26 keyword micro recall 0.000 on n=8 (warn/report, not a redaction score).
Utility skipped: disabled.

## Hard dev split

dataset `hard-dev-v1` seed `20261102` documents 60 sha256 `b169fcb72add15dc46cdd62fcb3dac179a4d0b9aa467ad0fb29a40514c76273b` official `true`

| System | P | R | F1 | F2 | macro P | macro R | macro F1 | macro F2 | p50 ms | cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aiguard | 0.950 | 0.983 | 0.966 | 0.976 | 1.000 | 0.996 | 0.998 | 0.997 | 10.2 | 0.00 |
| regex | 0.958 | 0.198 | 0.329 | 0.236 | 0.417 | 0.292 | 0.315 | 0.299 | 0.1 | 0.00 |
| presidio | 0.477 | 0.353 | 0.406 | 0.373 | 0.617 | 0.390 | 0.436 | 0.404 | 8.3 | 0.00 |
| pythainlp-ner | 0.437 | 0.267 | 0.332 | 0.290 | 0.083 | 0.059 | 0.069 | 0.062 | 3.4 | 0.00 |
| wangchanberta-ner | 0.302 | 0.440 | 0.358 | 0.403 | 0.112 | 0.219 | 0.139 | 0.173 | 33.1 | 0.00 |

| System | Type | n | P | R | F1 | F2 | fp | fn |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| aiguard | THAI_ID | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | PHONE | 12 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | EMAIL | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | BANK_ACCOUNT | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | CREDIT_CARD | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | PASSPORT | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | VEHICLE_PLATE | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | STUDENT_ID | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | DATE_OF_BIRTH | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | NAME | 44 | 1.000 | 0.955 | 0.977 | 0.963 | 0 | 2 |
| aiguard | ADDRESS | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | IBAN | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | negative | 4 |  |  |  |  | clean 4/4; false_positives 0; other_fp 6; name_fn cued 0 uncued 2 | |
| regex | THAI_ID | 6 | 1.000 | 0.167 | 0.286 | 0.200 | 0 | 5 |
| regex | PHONE | 12 | 1.000 | 0.333 | 0.500 | 0.385 | 0 | 8 |
| regex | EMAIL | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | CREDIT_CARD | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | PASSPORT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | NAME | 44 | 0.000 | 0.000 | 0.000 | 0.000 | 1 | 44 |
| regex | ADDRESS | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| regex | IBAN | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | negative | 4 |  |  |  |  | clean 4/4; false_positives 0; other_fp 0; name_fn cued 0 uncued 44 | |
| presidio | THAI_ID | 6 | 1.000 | 0.167 | 0.286 | 0.200 | 0 | 5 |
| presidio | PHONE | 12 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | EMAIL | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | BANK_ACCOUNT | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | CREDIT_CARD | 6 | 1.000 | 0.833 | 0.909 | 0.862 | 0 | 1 |
| presidio | PASSPORT | 6 | 1.000 | 0.167 | 0.286 | 0.200 | 0 | 5 |
| presidio | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| presidio | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| presidio | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| presidio | NAME | 44 | 0.400 | 0.182 | 0.250 | 0.204 | 12 | 36 |
| presidio | ADDRESS | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| presidio | IBAN | 6 | 1.000 | 0.333 | 0.500 | 0.385 | 0 | 4 |
| presidio | negative | 4 |  |  |  |  | clean 3/4; false_positives 1; other_fp 33; name_fn cued 0 uncued 36 | |
| pythainlp-ner | THAI_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | PHONE | 12 | 0.000 | 0.000 | 0.000 | 0.000 | 1 | 12 |
| pythainlp-ner | EMAIL | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | CREDIT_CARD | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | PASSPORT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | NAME | 44 | 1.000 | 0.705 | 0.827 | 0.749 | 0 | 13 |
| pythainlp-ner | ADDRESS | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | IBAN | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| pythainlp-ner | negative | 4 |  |  |  |  | clean 4/4; false_positives 0; other_fp 39; name_fn cued 0 uncued 13 | |
| wangchanberta-ner | THAI_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | PHONE | 12 | 0.227 | 0.833 | 0.357 | 0.543 | 34 | 2 |
| wangchanberta-ner | EMAIL | 6 | 0.375 | 1.000 | 0.545 | 0.750 | 10 | 0 |
| wangchanberta-ner | BANK_ACCOUNT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | CREDIT_CARD | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | PASSPORT | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | VEHICLE_PLATE | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | STUDENT_ID | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | DATE_OF_BIRTH | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | NAME | 44 | 0.745 | 0.795 | 0.769 | 0.785 | 12 | 9 |
| wangchanberta-ner | ADDRESS | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | IBAN | 6 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 6 |
| wangchanberta-ner | negative | 4 |  |  |  |  | clean 4/4; false_positives 0; other_fp 62; name_fn cued 0 uncued 9 | |

Layer ablation (removed minus full). A negative delta means the layer helped.

| Layer removed | micro P | micro R | micro F1 | micro F2 | delta R | delta F2 |
|---|---:|---:|---:|---:|---:|---:|
| full | 0.950 | 0.983 | 0.966 | 0.976 |  |  |
| fp | 0.803 | 0.491 | 0.610 | 0.533 | -0.491 | -0.443 |
| tb | 1.000 | 0.621 | 0.766 | 0.672 | -0.362 | -0.304 |
| fn | 0.950 | 0.983 | 0.966 | 0.976 | +0.000 | +0.000 |
| record_names | 0.950 | 0.983 | 0.966 | 0.976 | +0.000 | +0.000 |
| address_merge | 0.760 | 0.983 | 0.857 | 0.928 | +0.000 | -0.048 |
| facility_filter | 0.950 | 0.983 | 0.966 | 0.976 | +0.000 | +0.000 |
| student_relabel | 0.950 | 0.983 | 0.966 | 0.976 | +0.000 | +0.000 |

Per-type recall with `tb` removed.

| Type | n | full R | removed R | delta R |
|---|---:|---:|---:|---:|
| THAI_ID | 6 | 1.000 | 1.000 | +0.000 |
| PHONE | 12 | 1.000 | 1.000 | +0.000 |
| EMAIL | 6 | 1.000 | 1.000 | +0.000 |
| BANK_ACCOUNT | 6 | 1.000 | 1.000 | +0.000 |
| CREDIT_CARD | 6 | 1.000 | 1.000 | +0.000 |
| PASSPORT | 6 | 1.000 | 1.000 | +0.000 |
| VEHICLE_PLATE | 6 | 1.000 | 1.000 | +0.000 |
| STUDENT_ID | 6 | 1.000 | 1.000 | +0.000 |
| DATE_OF_BIRTH | 6 | 1.000 | 1.000 | +0.000 |
| NAME | 44 | 0.955 | 0.000 | -0.955 |
| ADDRESS | 6 | 1.000 | 1.000 | +0.000 |
| IBAN | 6 | 1.000 | 1.000 | +0.000 |

Per-type recall with `fp` removed.

| Type | n | full R | removed R | delta R |
|---|---:|---:|---:|---:|
| THAI_ID | 6 | 1.000 | 0.500 | -0.500 |
| PHONE | 12 | 1.000 | 0.000 | -1.000 |
| EMAIL | 6 | 1.000 | 1.000 | +0.000 |
| BANK_ACCOUNT | 6 | 1.000 | 0.000 | -1.000 |
| CREDIT_CARD | 6 | 1.000 | 0.000 | -1.000 |
| PASSPORT | 6 | 1.000 | 0.000 | -1.000 |
| VEHICLE_PLATE | 6 | 1.000 | 0.000 | -1.000 |
| STUDENT_ID | 6 | 1.000 | 0.000 | -1.000 |
| DATE_OF_BIRTH | 6 | 1.000 | 0.000 | -1.000 |
| NAME | 44 | 0.955 | 0.955 | +0.000 |
| ADDRESS | 6 | 1.000 | 1.000 | +0.000 |
| IBAN | 6 | 1.000 | 0.000 | -1.000 |

ADDRESS with `address_merge` removed: precision 1.000 to 0.200, recall 1.000 to 1.000, fp 0 to 24.
Section 26 keyword micro recall 0.000 on n=8 (warn/report, not a redaction score).
Utility skipped: disabled.

## Original freeze

dataset `blind-v2-repro` seed `20261101` documents 82 sha256 `ce0b88a3dd2281133f85ddbcdc38a5498f83865754e5bb77510bd12553ce8624` official `true`

| System | P | R | F1 | F2 | macro P | macro R | macro F1 | macro F2 | p50 ms | cost USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| aiguard | 0.914 | 0.977 | 0.945 | 0.964 | 0.973 | 0.993 | 0.982 | 0.988 | 23.3 | 0.00 |
| regex | 1.000 | 0.924 | 0.960 | 0.938 | 1.000 | 0.960 | 0.978 | 0.967 | 0.1 | 0.00 |
| presidio | 0.892 | 0.882 | 0.887 | 0.884 | 0.986 | 0.908 | 0.943 | 0.921 | 14.0 | 0.00 |
| pythainlp-ner | 0.368 | 0.176 | 0.238 | 0.196 | 0.080 | 0.055 | 0.065 | 0.058 | 7.1 | 0.00 |
| wangchanberta-ner | 0.295 | 0.511 | 0.374 | 0.446 | 0.112 | 0.239 | 0.151 | 0.192 | 44.3 | 0.00 |

| System | Type | n | P | R | F1 | F2 | fp | fn |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| aiguard | THAI_ID | 35 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | PHONE | 44 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | EMAIL | 28 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | BANK_ACCOUNT | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | CREDIT_CARD | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | PASSPORT | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | VEHICLE_PLATE | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | STUDENT_ID | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | DATE_OF_BIRTH | 22 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | NAME | 70 | 0.889 | 0.914 | 0.901 | 0.909 | 8 | 6 |
| aiguard | ADDRESS | 15 | 0.789 | 1.000 | 0.882 | 0.949 | 4 | 0 |
| aiguard | IBAN | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| aiguard | negative | 12 |  |  |  |  | clean 7/12; false_positives 5; other_fp 12; name_fn cued 0 uncued 6 | |
| regex | THAI_ID | 35 | 1.000 | 0.714 | 0.833 | 0.758 | 0 | 10 |
| regex | PHONE | 44 | 1.000 | 0.864 | 0.927 | 0.888 | 0 | 6 |
| regex | EMAIL | 28 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | BANK_ACCOUNT | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | CREDIT_CARD | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | PASSPORT | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | VEHICLE_PLATE | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | STUDENT_ID | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | DATE_OF_BIRTH | 22 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | NAME | 70 | 1.000 | 0.943 | 0.971 | 0.954 | 0 | 4 |
| regex | ADDRESS | 15 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | IBAN | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| regex | negative | 12 |  |  |  |  | clean 12/12; false_positives 0; other_fp 0; name_fn cued 4 uncued 0 | |
| presidio | THAI_ID | 35 | 1.000 | 0.686 | 0.814 | 0.732 | 0 | 11 |
| presidio | PHONE | 44 | 0.973 | 0.818 | 0.889 | 0.845 | 1 | 8 |
| presidio | EMAIL | 28 | 1.000 | 0.929 | 0.963 | 0.942 | 0 | 2 |
| presidio | BANK_ACCOUNT | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | CREDIT_CARD | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | PASSPORT | 8 | 1.000 | 0.875 | 0.933 | 0.897 | 0 | 1 |
| presidio | VEHICLE_PLATE | 8 | 1.000 | 0.875 | 0.933 | 0.897 | 0 | 1 |
| presidio | STUDENT_ID | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | DATE_OF_BIRTH | 22 | 1.000 | 0.909 | 0.952 | 0.926 | 0 | 2 |
| presidio | NAME | 70 | 0.857 | 0.943 | 0.898 | 0.924 | 11 | 4 |
| presidio | ADDRESS | 15 | 1.000 | 0.867 | 0.929 | 0.890 | 0 | 2 |
| presidio | IBAN | 8 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0 |
| presidio | negative | 12 |  |  |  |  | clean 11/12; false_positives 1; other_fp 16; name_fn cued 4 uncued 0 | |
| pythainlp-ner | THAI_ID | 35 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 35 |
| pythainlp-ner | PHONE | 44 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 44 |
| pythainlp-ner | EMAIL | 28 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 28 |
| pythainlp-ner | BANK_ACCOUNT | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| pythainlp-ner | CREDIT_CARD | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| pythainlp-ner | PASSPORT | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| pythainlp-ner | VEHICLE_PLATE | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| pythainlp-ner | STUDENT_ID | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| pythainlp-ner | DATE_OF_BIRTH | 22 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 22 |
| pythainlp-ner | NAME | 70 | 0.958 | 0.657 | 0.780 | 0.701 | 2 | 24 |
| pythainlp-ner | ADDRESS | 15 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 15 |
| pythainlp-ner | IBAN | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| pythainlp-ner | negative | 12 |  |  |  |  | clean 8/12; false_positives 4; other_fp 77; name_fn cued 16 uncued 8 | |
| wangchanberta-ner | THAI_ID | 35 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 35 |
| wangchanberta-ner | PHONE | 44 | 0.326 | 0.955 | 0.486 | 0.689 | 87 | 2 |
| wangchanberta-ner | EMAIL | 28 | 0.444 | 1.000 | 0.615 | 0.800 | 35 | 0 |
| wangchanberta-ner | BANK_ACCOUNT | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| wangchanberta-ner | CREDIT_CARD | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| wangchanberta-ner | PASSPORT | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| wangchanberta-ner | VEHICLE_PLATE | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| wangchanberta-ner | STUDENT_ID | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| wangchanberta-ner | DATE_OF_BIRTH | 22 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 22 |
| wangchanberta-ner | NAME | 70 | 0.577 | 0.914 | 0.707 | 0.818 | 47 | 6 |
| wangchanberta-ner | ADDRESS | 15 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 15 |
| wangchanberta-ner | IBAN | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 8 |
| wangchanberta-ner | negative | 12 |  |  |  |  | clean 10/12; false_positives 2; other_fp 152; name_fn cued 4 uncued 2 | |

Layer ablation (removed minus full). A negative delta means the layer helped.

| Layer removed | micro P | micro R | micro F1 | micro F2 | delta R | delta F2 |
|---|---:|---:|---:|---:|---:|---:|
| full | 0.914 | 0.977 | 0.945 | 0.964 |  |  |
| fp | 0.720 | 0.519 | 0.603 | 0.550 | -0.458 | -0.414 |
| tb | 0.970 | 0.733 | 0.835 | 0.770 | -0.244 | -0.193 |
| fn | 0.914 | 0.977 | 0.945 | 0.964 | +0.000 | +0.000 |
| record_names | 0.914 | 0.977 | 0.945 | 0.964 | +0.000 | +0.000 |
| address_merge | 0.713 | 0.977 | 0.824 | 0.910 | +0.000 | -0.054 |
| facility_filter | 0.914 | 0.977 | 0.945 | 0.964 | +0.000 | +0.000 |
| student_relabel | 0.914 | 0.977 | 0.945 | 0.964 | +0.000 | +0.000 |

Per-type recall with `tb` removed.

| Type | n | full R | removed R | delta R |
|---|---:|---:|---:|---:|
| THAI_ID | 35 | 1.000 | 1.000 | +0.000 |
| PHONE | 44 | 1.000 | 1.000 | +0.000 |
| EMAIL | 28 | 1.000 | 1.000 | +0.000 |
| BANK_ACCOUNT | 8 | 1.000 | 1.000 | +0.000 |
| CREDIT_CARD | 8 | 1.000 | 1.000 | +0.000 |
| PASSPORT | 8 | 1.000 | 1.000 | +0.000 |
| VEHICLE_PLATE | 8 | 1.000 | 1.000 | +0.000 |
| STUDENT_ID | 8 | 1.000 | 1.000 | +0.000 |
| DATE_OF_BIRTH | 22 | 1.000 | 1.000 | +0.000 |
| NAME | 70 | 0.914 | 0.000 | -0.914 |
| ADDRESS | 15 | 1.000 | 1.000 | +0.000 |
| IBAN | 8 | 1.000 | 1.000 | +0.000 |

Per-type recall with `fp` removed.

| Type | n | full R | removed R | delta R |
|---|---:|---:|---:|---:|
| THAI_ID | 35 | 1.000 | 0.771 | -0.229 |
| PHONE | 44 | 1.000 | 0.000 | -1.000 |
| EMAIL | 28 | 1.000 | 1.000 | +0.000 |
| BANK_ACCOUNT | 8 | 1.000 | 0.000 | -1.000 |
| CREDIT_CARD | 8 | 1.000 | 0.000 | -1.000 |
| PASSPORT | 8 | 1.000 | 0.000 | -1.000 |
| VEHICLE_PLATE | 8 | 1.000 | 0.000 | -1.000 |
| STUDENT_ID | 8 | 1.000 | 0.000 | -1.000 |
| DATE_OF_BIRTH | 22 | 1.000 | 0.091 | -0.909 |
| NAME | 70 | 0.914 | 0.914 | +0.000 |
| ADDRESS | 15 | 1.000 | 1.000 | +0.000 |
| IBAN | 8 | 1.000 | 0.000 | -1.000 |

ADDRESS with `address_merge` removed: precision 0.789 to 0.181, recall 1.000 to 1.000, fp 4 to 68.
Section 26 keyword micro recall 1.000 on n=11 (warn/report, not a redaction score).
Utility skipped: disabled.

## Why NER

The bullets are the measured contrasts. The tables above are the same JSON.

- hard-test: AI Guard micro F1 0.971 F2 0.965 (P 0.980 R 0.962), macro F1 0.995 F2 0.993 over 12 types. Removing tb takes NAME recall from 0.895 to 0.000 (micro recall -0.327). Removing fp changes micro recall by -0.490 and drops THAI_ID, PHONE, BANK_ACCOUNT, CREDIT_CARD, PASSPORT, VEHICLE_PLATE, STUDENT_ID, DATE_OF_BIRTH, IBAN. NAME fn 4, cued 0, uncued 4. Regex NAME recall 0.000. PyThaiNLP NAME recall 0.632, other_fp 30. WangchanBERTa NAME recall 0.816, other_fp 49. ADDRESS precision 1.000, recall 1.000, fp 0. Negative clean 4/4, other_fp 2.
- hard-dev: AI Guard micro F1 0.966 F2 0.976 (P 0.950 R 0.983), macro F1 0.998 F2 0.997 over 12 types. Removing tb takes NAME recall from 0.955 to 0.000 (micro recall -0.362). Removing fp changes micro recall by -0.491 and drops THAI_ID, PHONE, BANK_ACCOUNT, CREDIT_CARD, PASSPORT, VEHICLE_PLATE, STUDENT_ID, DATE_OF_BIRTH, IBAN.
- freeze: AI Guard micro F1 0.945 F2 0.964 (P 0.914 R 0.977), macro F1 0.982 F2 0.988 over 12 types. Removing tb takes NAME recall from 0.914 to 0.000 (micro recall -0.244). Removing fp changes micro recall by -0.458 and drops THAI_ID, PHONE, BANK_ACCOUNT, CREDIT_CARD, PASSPORT, VEHICLE_PLATE, STUDENT_ID, DATE_OF_BIRTH, IBAN. NAME fn 6, cued 0, uncued 6. Regex NAME recall 0.943. PyThaiNLP NAME recall 0.657, other_fp 77. WangchanBERTa NAME recall 0.914, other_fp 152. ADDRESS precision 0.789, recall 1.000, fp 4. Negative clean 7/12, other_fp 12.
- hard-test label counts: out-of-scheme LOCATION 2; negative documents none.
- hard-dev label counts: out-of-scheme LOCATION 6; negative documents none.
- freeze label counts: out-of-scheme DATE 5, LOCATION 6, ORGANIZATION 1; negative documents LOCATION 2, NAME 2, ORGANIZATION 1.
Names move with the text layer. Removing `tb` is what takes NAME recall to zero on every split. Removing `fp` does not. `tb` is `detect_tb`: the default thainer CRF plus the title and context pass in that function. The PyThaiNLP and WangchanBERTa rows are the tagger alone. They recover some names, WangchanBERTa also tags some phones and emails, and both leave ADDRESS at zero recall. Their out-of-scheme counts are the `other_fp` figures in the bullets.

Identifiers move with the format layer. Removing `fp` drops the types named in the bullets. The regex baseline is a smaller cue list, so it is not that ablation. On the prose splits its NAME recall is zero. On the labeled freeze its NAME recall is higher than AI Guard's. The hard splits were generated without field labels.

The remaining errors are the NAME misses and the false positives in those bullets. On the hard splits every AI Guard NAME miss is uncued, and the negative documents are clean. The freeze is where NAME and ADDRESS precision fall and where negative documents are not all clean. Out-of-scheme labels there are DATE, LOCATION, and ORGANIZATION. On the hard test they are LOCATION only. Removing `address_merge` does not change ADDRESS recall. It adds ADDRESS false positives, which is the sentence under each ablation table. Macro weights the twelve types equally. Micro lets NAME dominate the prose splits. F2 weights recall more than F1. Both columns are in the summary.

## Limitations

`gemma3` was not on this machine (`ollama` is absent). The llm row was not scored, and utility was disabled. No API key was read and no paid call was made. GitHub Actions was not run; the minutes budget is exhausted. The full pytest suite was run locally and its summary is in the commit message and `WORKLOG.md`.

These locks are a synthetic generator. A rule that agrees with the generator can look stronger than it is on real documents. The sealed protocol corpus was not opened. Tracemalloc peaks in the JSON are not resident memory. The NAME cue count is the fixed window above, not a second run of the product cue matcher. Presidio's Thai hits come from the pattern recognizers registered in `baselines.py` plus `en_core_web_sm`. The product NER engine for the AI Guard row is thainer, not WangchanBERTa and not union. The label file is a second pass. The test checks that the counts add up to the score totals, so it would still pass if two label names were swapped and the sums stayed the same.

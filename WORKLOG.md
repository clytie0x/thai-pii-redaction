# WORKLOG — YRSS claim map and recovered per-entity run

Plan written before the recovery, the claim map, and the methods note.
This file is the audit trail for that work. It is not a paper and not a poster.

## In scope

- Recover closed, unmerged PR #15 (`bd18441ca3ed742382b393acc42cc8896ae81c3f`,
  `refs/pull/15/head`) onto current `main` (`52bd94a7b7dfac5bde8fe8a1cf5c2532051baec7`).
  Bring `docs/benchmark/per-entity-results.md`, `docs/benchmark/runs/*.json`,
  and the harness/tests in that commit. Resolve conflicts against the current
  tree. Do not reopen `benchmark/data/blind-v2.enc` or `benchmark/data/yrss-holdout-v1.enc`.
- Re-run the commands recorded in the recovered per-entity document. Compare
  entity scores with the recovered JSON. Latency and peak memory may move.
  A score change is a diff, not a silent replacement of the historical file.
- Write `research/yrss2026/CLAIM-MAP.md`: every required headline number with
  value, metric, dataset/split, held-out status, source path, commit, lock and
  plaintext hashes, reproducing command, and where it may and may not be cited.
  If a value is not in this repository, mark it UNVERIFIED and say what is missing.
- Write `research/yrss2026/METHODS-RESULTS.md` with methods, results, and
  limitations. Headline rows show precision, recall, F1, and F2 from stored
  counts. No new headline is invented.
- If an in-repo document still tells the comparative story with only gold-v4
  F2 0.947 and sealed blind-v2 F2 0.799, point it at the claim map. Leave
  historical ADRs as they were. If the poster or slides live in another
  repository, list the edit and do not touch that repository.
- Run the full pytest suite and the per-entity commands in this VM. GitHub
  Actions minutes are exhausted, so CI is not the evidence. Open a pull
  request. Do not merge.

## Out of scope

- Detector, threshold, model, or policy changes. No weakening of detection.
- Decrypting or rescoring sealed blind-v2 or yrss-holdout-v1.
- Paid APIs, external keys, deploys, GitLab, version bump, poster, or slides.
- Real PII. Fixtures and corpora stay synthetic.
- Rewriting historical ADRs so they describe the present.
- Copying a number forward when the file, commit, or command is missing.

## How each claim is verified

| Claim | Check |
|---|---|
| PR #15 bytes | `git fetch origin refs/pull/15/head` then `git rev-parse` equals `bd18441ca3ed742382b393acc42cc8896ae81c3f`. Cherry-pick onto this branch. |
| Per-entity tables | Recovered JSON is the source. `tests/test_blind_v2_harness.py` checks that the markdown tables match that JSON. |
| Reproduction | Same `python -m benchmark.blind_v2` commands as the recovered document, JSON written beside the historical files, then a field compare of micro/macro P, R, F1, F2, ablation deltas, and Section 26 recall. |
| gold-v4 F2 | Read `research/yrss2026/baseline.json` arm `full.metrics.overall`. Confirm the same value in `RESULTS.md`. Record whether the manifest commit object exists in this clone. |
| sealed blind-v2 F2 | Read `benchmark/data/blind-scores.jsonl` where `version` is `blind-v2`. Match `ciphertext_sha256` and `corpus_sha256` to `benchmark/data/blind-v2.lock.json`. Do not run the scorer. |
| yrss-holdout-v1 0.834 to 0.871 | Read `research/yrss2026/heldout-paired.json` baseline and candidate `metrics.overall`. Quote the stored floats. Rounding to three decimals is labeled as rounding. |
| hard-test F1 0.971 / F2 0.965 | Read recovered `docs/benchmark/runs/hard-test.json` system `aiguard` micro. Re-run and report equality or the diff. |
| F1 beside F2 | For gold, sealed blind-v2, and the holdout, F1 is the stored `f1` field, not a new fit. For the synthetic locks, F1 is the stored micro `f1`. |
| Section 26 paraphrase recall 0 | Read `section26` in the recovered hard-test JSON and the sentence in `docs/benchmark/gap-list.md`. |
| LLM baseline | Read `docs/benchmark/blind-v2-results.md` for the 2026-11-01 `gemma3:1b` row. This session scores `gemma` only if a local runtime already has it and no key is required. |
| `test_human_agreement` / `d93d10b` | Run the test. Record pass, fail, or skip. `git cat-file` the historical SHA. Do not invent a substitute score. |
| In-repo pointers | `rg` for `0.947` and `0.799` under this repo. Update only documents that still present those two figures as the whole comparative story. |

## Delivery notes

Current `main` already contains the parent of PR #15 (`38b235f`) plus
`52bd94a`. `pii_redactor/detectors/` changed after `38b235f`, including
`predict_ablated` (`benchmark/blind_v2/ablate.py`), which now always runs
source recovery. A re-run on this branch is therefore a current-tree check,
not a byte-identical replay of `bd18441` unless the scores happen to match.

The gold and holdout JSON files record measurement commits
`19fe9f0c209c587c7662ee5302edc752f0fd32c8` and
`ed01027f2e782b6f83d88520c7fe9d2547a84ba1`. The sealed reveal records
`4cc5eb17aa16f2df7d5e65576cd5ba61f0737540`. Those three objects were absent
from this clone when the plan was written. The claim map must say so.
Absence of the commit object does not delete a number that is present in a
file this clone does contain.

## What this session ran

On 2026-11-05, Python 3.12.3, from the repository root, with
`PYTHONUTF8=1`, telemetry disabled, and no API keys:

```bash
.venv/bin/python -m benchmark.blind_v2 --self-check
.venv/bin/python -m benchmark.blind_v2 --self-check --split hard-dev
.venv/bin/python -m benchmark.blind_v2 --self-check --split hard-test
SYS=aiguard,regex,presidio,pythainlp-ner,wangchanberta-ner
.venv/bin/python -m benchmark.blind_v2 --systems "$SYS" --no-utility --json /tmp/yrss-repro/freeze.json
.venv/bin/python -m benchmark.blind_v2 --split hard-dev --systems "$SYS" --no-utility --json /tmp/yrss-repro/hard-dev.json
.venv/bin/python -m benchmark.blind_v2 --split hard-test --systems "$SYS" --no-utility --json /tmp/yrss-repro/hard-test.json
.venv/bin/python -m pytest -q --tb=line
```

Self-checks printed the lock plaintext hashes. The score compare is
`docs/benchmark/runs/repro-2026-11-05.json`. JSON was written under `/tmp`
so the `bd18441` files were not overwritten.

Full pytest: 3467 passed, 318 skipped, 0 failed, 97.13s.
`tests/test_human_agreement.py` and `tests/test_yrss_claim_map.py` were
18 passed, 0 skipped, in a focused run before the full suite.
`tests/test_blind_v2_harness.py` was included in a later 24-passed run with
the claim-map tests. `ruff check` and `ruff format --check` passed on the
touched Python files. Repo-wide `ruff check .` still reports pre-existing
`RUF036` in `pii_redactor/detectors/finetuned_engine.py` and `UP042` in
`scripts/office_v2_composition.py`. Repo-wide `ruff format --check .` still
wants edits in `pii_redactor/governance/operations.py` and
`tests/test_desktop_native_package.py`. Those four files are not in this
diff. `git diff --check` was clean.

`sentencepiece` in this environment is 0.2.3. The recovered
`environment.json` records 0.2.2. WangchanBERTa micro scores still matched.

## Reproduction diffs

Hard-test and hard-dev AI Guard full micro matched `bd18441`, including
hard-test F1 0.970873786407767 and F2 0.9652509652509652. Every regex,
Presidio, PyThaiNLP, and WangchanBERTa micro row matched on all three splits.
Section 26 recall matched (hard-test and hard-dev 0.0 on n=8; freeze 1.0 on
n=11).

Labeled-freeze AI Guard full micro did not match: fp 24 to 22, F1
0.9446494464944649 to 0.9481481481481483, F2 0.9638554216867468 to
0.9653092006033182, recall unchanged. NAME fp 8 to 6, ADDRESS fp 4 to 0,
`other_false_positives` 12 to 16, negative clean documents 7/12 to 8/12.
The `.3f` text of that re-run F2 is 0.965, the same three decimals as the
hard-test F2, and a different float. The stored freeze headline stays 0.964.

The `fp`-removed ablation moved on every split. Hard-test F2
0.5147058823529411 to 0.570539419087137. The cause is recorded below.

## Drift root cause, 2026-11-05

The historical JSON has no git SHA. That metadata is absent. The blobs were
introduced by `bd18441ca3ed742382b393acc42cc8896ae81c3f`. `git diff 38b235f
bd18441 -- pii_redactor benchmark/blind_v2/ablate.py` is empty.
`score.py` at `bd18441` matches this branch. Re-scoring
`38b235ffb5cede349e51362049a03666b8637dc6` reproduces freeze full fp 24 and
the historical `fp`-removed tp/fn. `git rev-list --count 38b235f..52bd94a`
is 1. The only detector commit is
`52bd94a7b7dfac5bde8fe8a1cf5c2532051baec7`.

File swaps in a detached worktree, AI Guard only, same locks:

- Old detectors plus only the new `tb_detector.py`: freeze full fp 24 to 22.
  `fp`-removed counts stay historical.
- Disabling only `_spaceless_run_is_not_a_name` on the current tree: freeze
  full fp returns to 24.
- Old `ablate.py` plus new detectors: `fp`-removed counts stay historical.
  Freeze full fp is already 22 because `tb_detector.py` is new.
- Current `ablate.py` with `recover_structured` and without the address
  relabel: `fp`-removed counts match the re-run.

So (a) is the new length gate in `tb_detector.py`. The dropped spans are
NAME 0:27 on `b2r-0000` (gov_form) and NAME 0:42 on `b2r-0078` (negative).
Both are space-free runs longer than 25 characters. (b) is
`ablate.py` calling `recover_structured` when `fp` is disabled. The new true
positives are exact gold spans listed in `research/yrss2026/CLAIM-MAP.md`.
`_relabel_numberless_addresses` turns four ADDRESS false positives into
LOCATION and does not change the micro false-positive total.

After this write-up, `PYTHONUTF8=1 .venv/bin/python -m pytest -q --tb=line`
printed `3467 passed, 318 skipped` in 94.31s. Exit code 0. No failures.

## Ablation fix, not merged

`benchmark/blind_v2/ablate.py` now skips `recover_structured` and
`admit_recovery` when the disabled layer is `fp`. A unit test patches
`recover_structured` and requires that call, and its probe span, to be absent
when `fp` is off and present on the full path. Detector code was not changed.

Re-score command, AI Guard only, `--no-utility --no-section26`, compared with
`docs/benchmark/runs/{freeze,hard-dev,hard-test}.json` layer `disabled=fp`:

| Split | Historical micro | After the fix |
|---|---|---|
| hard-test | tp 49, fp 11, fn 55, F2 0.5147058823529411 | match |
| hard-dev | tp 57, fp 14, fn 59, F2 0.5327102803738318 | micro match |
| freeze | tp 136, fp 53, fn 126, F2 0.549717057396928 | tp 136, fp 51, fn 126, F2 0.5506072874493928 |

Freeze does not match. The two false positives are the `52bd94a` name-length
gate, which still runs in the `fp` ablation. Hard-test ADDRESS by-type fp is
2 in the historical JSON and 0 after the fix because numberless addresses are
relabeled LOCATION. Micro counts for that split still match. The branch was
not squash-merged.

Full suite after the fix: `3468 passed, 318 skipped` in 88.02s. Exit code 0.

## Self-review

- The hard-test headline reproduced. Freeze full fp 24 to 22 is the new
  spaceless-name gate in `52bd94a`. The `fp`-removed F2 move is recovery
  staying on in `ablate.py`. Historical JSON was left in place.
- Gold, holdout, and sealed-reveal commits recorded inside those artifacts
  are absent from this clone. The values stay file-backed. The sealed
  ciphertext was not opened. Gemma freeze F1 stays UNVERIFIED: the 2026-11-01
  table has no tp/fp/fn, and Ollama is not installed.
- `d93d10b` is still absent. `test_frozen_paper_gold_can_be_loaded_from_git`
  passed because the loader now uses `61cde3ba`, which this clone has. The
  2026-11-03 failure count is not this session's count.

## Recovered worklog from PR #15

The text below is the worklog committed in
`bd18441ca3ed742382b393acc42cc8896ae81c3f`. It describes that session, not
this one. Its pytest counts are not reused as this session's evidence.

# Per-entity blind-v2 report

## In scope

- Score AI Guard, the regex baseline, Presidio, PyThaiNLP NER, and WangchanBERTa
  NER on the three locked synthetic splits: the original freeze
  (`benchmark/data/blind-v2-repro.lock.json`, seed `20261101`), hard dev
  (seed `20261102`), and hard test (seed `20261103`).
- Reuse `python -m benchmark.blind_v2` and `score_predictions`. Add F1 next to
  the existing precision, recall, and F2. The per-entity table already exists;
  this adds the missing F1 column and a `--split` selector so the hard locks
  go through the same command.
- Keep the existing layer ablation (`fp`, `tb`, and the other assembly
  layers). Store per-type recall deltas for that ablation so the write-up can
  say which types move.
- Count NAME false negatives whose gold span is or is not preceded by a short
  title or label cue. Counts only. No document text in the report.
- Write `docs/benchmark/per-entity-results.md` from this session's JSON,
  including micro and macro averages and a Why NER section of at most one page.

## Out of scope

- No detector changes, no threshold changes, no new models, no paid or
  external API calls.
- `gemma3` is included only if Ollama or another local runtime already has it.
  It is not installed for this run.
- The sealed `benchmark/data/blind-v2.enc` corpus stays closed.
- No merge to `main`. CI minutes are exhausted, so the suite runs locally.
- No version bump, no deploy, no GitLab.

## How a number is measured

Matching stays type-aware overlap, one gold span to one prediction, the same
rule as `benchmark/blind_v2/score.py`. Precision, recall, F1, and F2 come from
that function's tp, fp, and fn. F1 is `2PR/(P+R)` and F2 is `5PR/(4P+R)`, both
zero when the denominator is zero. Micro pools every redaction type and counts
predictions outside the twelve-type scheme as false positives. Macro is the
unweighted mean over types that have at least one gold span.

The product path is `predict_ablated(text, None)`, which is `detect_all`'s
assembly order. The default NER engine is `thainer` unless
`AIGUARD_NER_ENGINE` is set. The `tb` ablation removes that whole text
detector, including the title and context name pass inside it. The `fp`
ablation removes the format and checksum detector. The regex, Presidio,
PyThaiNLP, and WangchanBERTa rows are separate systems, not ablations.

A NAME miss is "cued" only when a fixed cue token sits in the 16 characters
before the gold start and is not glued to another letter. The cue list is
titles plus `ชื่อ`, `ข้าพเจ้า`, and `ผู้เสียหาย`.

Every figure in the results document is transcribed from a JSON file this
session writes with `--json`. Lock hashes are checked before scoring.

## Self-review

- Scoring stays in `score.py`. `present.py` only formats that JSON. The hard
  splits go through `prepare_corpus` and the same `run_benchmark` path.
- `gemma3` is absent (`ollama` is not installed). The llm system was left out
  of `--systems`, utility was disabled, and no API key was set.
- `negative-labels.json` is a second `predict_ablated` pass. The test checks
  the sums against the score file, not the label-by-label pairing. That limit
  is stated in the results page.
- Local pytest: 2373 passed, 268 skipped, 1 failed.
  `test_frozen_paper_gold_can_be_loaded_from_git` cannot see commit
  `d93d10b`; this clone is not shallow, and `origin` does not have that
  object. The failure is outside this change.
- `ruff check .` with ruff 0.17.3 reports a pre-existing `UP042` in
  `scripts/office_v2_composition.py`, and `ruff format --check .` wants a
  parentheses change in `tests/test_desktop_native_package.py`. Neither file
  is part of this change. The files touched here pass `ruff check` and
  `ruff format --check`.

# WORKLOG — optional OpenThai2.0-OCR-Text engine

Written before the code, on 12 Nov 2026. This section is the plan for that
change. The sections above are an older audit and stay as they were.

## Requirements

Owner decision (Teerapat, 12 Nov 2026): Option A. Add
[iApp OpenThai2.0-OCR-Text](https://huggingface.co/iapp/OpenThai2.0-OCR-Text)
as an optional OCR engine for scanned or raster pages (`pdf_hybrid`), beside
PaddleOCR. The model card (revision `39fa41bdd49f067ba41b1d9de79c06ab506d67d4`,
Apache-2.0, v1.0.0) says:

- CPU ONNX, about 4 MB (`det.onnx` 1.8 MB, `rec.onnx` 2.4 MB), line boxes.
- Public call: `LineOCR(model_dir, threads=1).read(image)` returns
  `lines[]` with `text`, `confidence`, and `box`.
- Boxes are in the caller's image coordinates. The runtime deskews when the
  page leans more than 2.5 degrees, then maps boxes back.
- Dependencies named on the card: OpenVINO or ONNX Runtime,
  `opencv-python-headless`, `pyclipper`, numpy. An ndarray is BGR.

Repo rules this has to keep:

- `AGENTS.md`: preserve PDF bbox coordinates. Do not deskew unless the
  coordinates are transformed with it. Optional engines stay optional and
  fail clearly. No raw PII in logs, errors, or fixtures.
- `docs/architecture.md`: optional OCR is never silently installed or
  selected. OCR fragments get source spans. The coordinate system stays
  top-origin 72-pt points.
- `pii_redactor/ingest/ocr_processor.py`: PaddleOCR `lang="th"` is the
  current engine. Its own preprocess does not deskew (DET-3). Line boxes
  are scaled by `72 / dpi`.
- `requirements-ocr.txt`: PaddleOCR brings `opencv-contrib-python`. A second
  OpenCV wheel must not be installed beside it. There is no OCR engine
  selector in `CoreConfig` today, so Paddle stays the default.

Out of scope: OCR-Markdown, replacing pdfplumber/pdfium, any iApp API, bundling
weights, detector changes, and weakening PII detection.

## Acceptance

1. A faked OpenThai result whose quad is already in caller-image pixels
   (the card's post-deskew contract), including a skewed quad, converts to
   a top-origin 72-pt box on that region of the page. The adapter does not
   deskew again.
2. Each OCR fragment's `source_span` slices the extracted text to the box text.
3. `AIGUARD_OCR_ENGINE=openthai` is explicit. A missing package or model
   raises `ExplicitOCRUnavailableError` and does not call Paddle or fall
   back to the text layer. Unset still means Paddle, including today's
   text-layer fallback when Paddle is not installed. Text-layer `pdf_text`
   never calls OCR.
4. OpenThai has its own extra, `requirements-ocr-openthai.txt`, and the
   OpenCV clash is written next to both requirement files.
5. Default CI uses the fake engine. A real-model test skips when
   `AIGUARD_OCR_OPENTHAI_DIR` is unset. The download script is the only
   network path, and it checks pinned SHA-256 hashes.

## How done is measured

- `tests/test_ocr_openthai.py` and the existing OCR/ingest tests pass.
- `ruff check` and `ruff format --check` pass on the touched Python files.
- `git diff --check` is clean.
- `scripts/measure_perf.py` runs because `pii_redactor/` changes. The sample
  PDF is text-layer, so the gate does not time OCR. The commit records the
  numbers.
- An ADR records the owner decision. An independent review runs before the
  squash onto `main`.
- Docs that describe the OCR path (`architecture.md`, `ROADMAP.md`,
  install docs, `CODEMAP.md`, `NOTICE`) match the code. Live-model
  acceptance stays open.

## Self-review

- Unset `AIGUARD_OCR_ENGINE` still means Paddle, including the text-layer
  fallback. `openthai` and an explicit `paddle` that cannot run raise
  `ExplicitOCRUnavailableError` and do not call the other engine.
- `words_from_lines` only scales the caller-image quad into top-origin
  72-pt points. The upstream runtime deskews and maps boxes back before
  that. This code does not deskew again.
- `scripts/measure_perf.py` on this machine, with the OCR change:
  detect 7.11 ms, sanitize 17.42 ms, restore 0.47 ms, pdf_redact 114.77 ms.
  The same script without the change: detect 7.60 ms, sanitize 19.66 ms,
  restore 0.56 ms, pdf_redact 120.31 ms. Both miss `perf/baseline.json`
  by more than 20%. The sample PDF is text-layer, psutil is not installed,
  and the control is slower, so the baseline was not moved. Real OpenThai
  inference was not run.

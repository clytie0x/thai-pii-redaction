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

## Self-review

Filled after the runs. See the bottom of this file once the branch is ready.

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

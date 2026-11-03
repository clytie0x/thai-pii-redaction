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

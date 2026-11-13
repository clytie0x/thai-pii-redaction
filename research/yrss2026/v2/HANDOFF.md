# YRSS evaluation v2: handoff (2026-11-13)

Work moves from a cloud session to the owner's machine. This file is the
state at handoff. Protocol: `docs/decisions/2026-11-13-yrss-eval-v2.md`.
Poster day is 24 November 2026.

## Done, on branch `ccr-3d0dc422-lal6y0` (draft PR #25)

- Pre-registration with addenda (licence format, cluster bootstrap by family).
- Generator, annotation guide, and the dev split: 100 families, 300
  documents, 1,188 entities, locked in `benchmark/data/yrss-v2/dev.lock.json`.
- Harness: `python -m benchmark.yrss_v2` (systems, four views, family
  bootstrap, paired differences, Holm, ablations, test-split guard).
- LLM comparator for any OpenAI-compatible endpoint
  (`benchmark/yrss_v2/llm_openai.py`).
- Human annotation check (`benchmark/yrss_v2/agreement.py`,
  `docs/research/yrss-eval-v2-human-check.md`).
- Detector fixes from the dev error inventory, then an independent review,
  then fixes for what the review found. Root suite and SDK suite pass.

## Dev results so far (development set, not accuracy evidence)

Files in this folder. `dev-baseline.json` is the detector before any change.
`dev-after-fixes.json` is the detector at handoff. The two `dev-llm-*` files
were run one commit set earlier, so their `aiguard` row is slightly older
than `dev-after-fixes.json`; their `llm` rows are valid.

- AI Guard, all view F2: baseline 0.819, after fixes 0.905. Shared-11: 0.876
  to 0.967.
- AI Guard beats regex, CRF NER, WangchanBERTa NER and Presidio on dev by a
  wide margin, and each layer ablation costs F2.
- LLMs match or beat AI Guard on dev accuracy. `openai/gpt-6-luna` all-view
  F2 0.954; `PSU-LLM/psu-gemma` 0.994. Both leave every negative document
  clean. AI Guard leaves none clean because it masks generic dates,
  organisations, places and reference numbers on purpose.
- AI Guard is about 100 to 400 times faster (about 11 ms against 1.2 to 4 s
  per document) and needs no GPU or network.
- The size of `psu-gemma` and `psu-qwen` is unknown. Ask the dotBlue admins.
- Two more dev runs (`qwen/qwen3.8-27b`, `PSU-LLM2/psu-qwen`) were still
  running in the cloud session at handoff and are not saved here. Rerun them
  if wanted.

So "the hybrid is more accurate than an LLM" is not supported and must not be
written. The supported case for the hybrid is privacy (no data leaves the
machine), speed, cost, and no GPU. The owner is considering reframing the LLM
question as: how large must an LLM be to match the hybrid? That needs small
models of known size run locally through Ollama.

## Next steps, in order

1. Run small local LLMs on dev (1B, 4B, 12B, largest that fits) and record
   size, quantization, memory and latency for each.
2. Decide the LLM comparator(s) and add a pre-registration addendum naming
   model, digest and seeds before any test scoring.
3. Freeze the detector commit and record it in an addendum. No detector
   change after this, or the test split is spent.
4. Author the test split: 200 new families, 4 variants each. Authors read
   only the annotation guide. Use at least two model families. Add rules so
   the text reads like people wrote it: chat particles, uneven spacing,
   typos, unfinished sentences. Avoid the unrealistic forms found on dev
   (every mark stripped, every field glued, Thai digits with English
   months). Give documents opaque ids so a family name cannot hint at a
   negative. Test templates are git-ignored on purpose: lock them by hash
   and encrypt them, do not commit them in plain text.
5. Score the test split once, all systems and ablations, LLM with 5 seeds.
6. Human check on a 10% sample if an annotator is available.
7. Update CLAIM-MAP, then the poster and slides in `ai-guard-docs`.

## Owner decisions still open

- Keep masking generic labels and explain the low unrestricted precision on
  the poster (recommended), or change what the product masks.
- A checksum-failing 13-digit number with no cue is still labelled THAI_ID
  (three existing tests require it). Keep, or relabel ID_NUMBER.
- Which LLM is the registered comparator.
- Who annotates the 10% sample.

## Things that bit this session

- `packages/amphrang` aliases the root detector. After any detector change
  run both suites:
  `python -m pytest -q` and
  `cd packages/amphrang && PYTHONPATH=.:../.. python -m pytest tests -q`.
- `.gitignore` ignores `*.jsonl`. The dev templates have an explicit
  exception; `.gitattributes` pins them to LF because the lock hashes bytes.
- `tests/test_codex_project_setup.py` caps `AGENTS.md` below 180 lines.
- `scripts/measure_perf.py` reported REGRESSION against `perf/baseline.json`
  on the cloud machine before and after every change. Same-machine A/B runs
  showed no measurable slowdown. Rerun the gate on the owner's machine.
- Presidio and WangchanBERTa need the pinned optional packages in
  `docs/benchmark/per-entity-results.md`.
- The dotBlue gateway (`https://ai.psu.blue/v1`) streams unless asked not to;
  the adapter now sends `stream: false`. Locally, put the key in an
  environment variable and pass its name with `--llm-key-env`.
- Never run `--split test` before step 5, and never open
  `benchmark/data/*.enc`.

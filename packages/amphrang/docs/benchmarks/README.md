# Performance benchmarks

Results from `python -m benchmark.perf`, one file per run, named
`YYYY-MM-DD-perf-<machine>.md` (with the raw report next to it as `.json`).
Numbers are only comparable within one machine; commit a new pair rather than
overwriting an old one, so regressions stay visible in history.

## What is measured

- **Cold start** — a fresh Python process importing `amphrang` and running its
  first `detect()` (includes the thainer model load). Measured by subprocess,
  so in-process caches cannot flatter it.
- **Latency** — `detect()` and `anonymize(mode="token")` per size class
  (S 200 / M 2,000 / L 20,000 / XL 100,000 chars), p50/p95 by nearest rank
  with the sample count reported, warmup excluded. XL stays under the server's
  200k-char work cap.
- **Throughput** — a mixed batch (20 S + 5 M documents, the shape of
  interactive LLM traffic) through `detect()`, single-process and across a
  process pool whose workers are warmed before the clock starts.
- **Memory** — peak RSS sampled while detecting the largest measured class,
  against the after-model-load baseline (needs `psutil`, in the dev group).

The corpus is deterministic (seeded synthetic Thai documents from
`benchmark/corpus.py`, sliced to exact lengths, each guaranteed to contain
structured PII), so two runs on the same machine measure the same work.

## Profiles

- `python -m benchmark.perf` — the full run that produces these files.
- `python -m benchmark.perf --profile ci` — S/M subset with loose,
  catastrophic-only p95 ceilings (`CI_THRESHOLDS` in `benchmark/perf.py`);
  runs in CI as the `perf-smoke` job. It exists to catch a 10x regression,
  not to police single-digit percentages on shared runners.

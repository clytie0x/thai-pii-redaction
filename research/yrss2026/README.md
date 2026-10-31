# YRSS accuracy evidence

Follow [the research plan](../../docs/research/yrss-accuracy-plan.md) and
[held-out pre-registration](../../docs/decisions/2026-10-31-yrss-heldout.md).
All data are synthetic. No real-document accuracy or legal compliance is claimed.

## Preserved baseline

`baseline.json` contains gold-v4 metrics, source/corpus/dependency/model hashes,
prediction digests, component experiments, and value-free error diagnostics.
Two offline prediction passes matched; a subsequent identity-checked capture
reproduced the historical result. Source baseline:
`19fe9f0c209c587c7662ee5302edc752f0fd32c8`.
The matching v1 capture tool is preserved in checkpoint `b198c5c`; later tool
versions additionally bind runtime evaluator and paired-driver hashes.

The development inventory distinguishes 2 fully uncovered entities, 15 partly
uncovered, 17 fully covered but wrongly typed, and 36 fully covered with
imprecise boundaries. Coverage includes whitespace/punctuation; those counts
alone do not prove meaningful identifier leakage. Original gold annotations
and old blind files remain unchanged.

## Component interpretation

`format_only` runs the structured detector. `raw_crf` uses original model BIO
spans with only the label map: it has no context upgrades, windowing or hygiene,
and cannot express every full-system label. It is a standalone baseline, not
a same-capability model ranking. `without_name_context` removes three named
context/conjunction/parallel-record functions; it retains other CRF handling.
`without_fn` removes only second-pass recovery. `full` is real `detect_all`.
These conditional interventions are not additive causal allocations.
Identical gold predictions without FN recovery do not justify deleting it.

## Format checkpoint

The first patch extends cue-bearing Luhn-valid cards to 13-15 digits while
preserving existing 16-digit forms beside amounts and row numbers, resolves
checksum collisions without dropping card suffixes, and supports Thai-digit
phone prefixes at unchanged original source positions.

Short uncued Luhn numbers remain ambiguous: corrupted OCR IDs can also pass
Luhn, so the new card lengths require a card cue. Legacy 16-digit prefix
matching on longer grouped codes remains a known precision limit. No generic
date/quasi-identifier policy or exam-roster STUDENT_ID scope was changed.

Independent review exposed card adjacency, checksum-prefix and evaluator
binding defects outside gold. Each was reproduced by failing tests and fixed.
An existing OCR retry regression also drove a failing control before the cue
restriction. The corrected full Python run passed 2,749 tests, skipped 34
optional/host-dependent cases, and reported one existing dependency warning.
This proves source behavior, not physical OCR or installed/live-provider paths.

The legacy performance anchor was already red before the patch. Three
alternating baseline/candidate measurements in one environment showed all
operation medians within the repository's 20% time budget; the anchor was not
changed. See `format-performance.json` for values and memory evidence.

## Reproduction and held-out boundary

Use Python 3.13 (recorded interpreter 3.13.12), hash-verified
`requirements.lock`, and the recorded developer tools `ruff==0.14.2` and
`psutil==7.2.2`. Prewarm once with `scripts/prewarm_ner.py`. Then run:

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m benchmark.campaign --out benchmark/reports/new-run --ablations
```

The output directory must be new. `--expect <matching-version-evidence.json>`
rejects source, evaluator, model, corpus, dependency or interpreter drift.

`heldout-qa.json` records pre-freeze independent agent review, not human
agreement. Same-family authors, limited component pools, shared framing and
constructed negatives limit generalisation. Originals and the blinding key
intentionally remain outside every repository at
`C:/Users/teera/aiguard-yrss-holdout-v1/`; developer contexts must not open it.
The held-out set has not been scored. One paired disclosure is reserved for
the final development-selected candidate. No tuning may follow disclosure.

## Research extension: source-projected input recovery

The [source-backed alternatives report](reports/Thai%20PII%20research%20advances.md)
selected bounded input recovery rather than duplicating existing training or
introducing a heavyweight default. The shared scan view is reused, not claimed
as a new redaction principle. The contribution is its tested integration with
original positions, field boundaries, replacement and release behavior.

Input recovery never joins hard line/tab boundaries, performs no arbitrary
NFKC, and keeps raw source bytes/positions unchanged. It must preserve both
raw protection intervals and structured units found by the original guard.
Independent review proved that preserving raw intervals alone is insufficient:
a newly recognized phone inside an obfuscated IBAN can destroy the guard's
signature and expose the IBAN remainder. The generic original-unit admission
constraint, synthetic composed-obfuscation regressions, and unchanged final
guard close that newly introduced mechanism; ambiguous cases remain blocked.

`benchmark.recovery_study` measures visible, dependent synthetic variants from
60 seed/type families: original forms, format controls, width forms, repeated
separators, and combined controls/separators. It records complete source-span
protection, release/block outcomes, non-PII masking, a fixed non-sensitive
amount, and exact restoration for both token and surrogate modes. This is not
an independent population benchmark or proof of anonymity. An oracle-labelled
`unsafe_release` means annotated non-whitespace characters remain exposed;
it does not estimate linkage-attack success or legal risk.

Residual limits include irregularly spaced email/IBAN forms, semantic NER
misses, broader span arbitration, and real-document/human annotation evidence.
The installed and hosted binaries have not been updated by this source work.

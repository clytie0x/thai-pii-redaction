# YRSS research results

## Outcome

A local CPU-friendly source candidate improves detection on a separately authored, frozen synthetic held-out corpus and improves complete-protection release on controlled representation probes. The CRF default, model assets, original text, masking policy and submitted abstract remain unchanged. These are local synthetic results, not real-document accuracy or production acceptance.

## Frozen held-out experiment

185 documents, 714 annotated entities; baseline `19fe9f0c209c587c7662ee5302edc752f0fd32c8`; candidate `ed01027f2e782b6f83d88520c7fe9d2547a84ba1` (clean at freeze). One paired disclosure, two scored arms, offline; no subsequent tuning.

| Measure | Baseline | Candidate |
|---|---:|---:|
| Unrestricted entity F2 | 0.833563 | 0.870756 |
| Typed overlap recall | 0.845938 | 0.890756 |
| Character coverage recall | 0.830783 | 0.855937 |
| Character coverage precision | 0.875603 | 0.878815 |
| Exact typed-boundary recall | 0.623249 | 0.668067 |

F2 95% document-bootstrap intervals: baseline [0.812062, 0.855014], candidate [0.852011, 0.888639]. Paired F2 difference **+0.037192**, 95% CI **[+0.026076, +0.048260]**, 1,000 shared resamples, seed 0. The interval excludes zero on this constructed corpus; this is not a general Thai superiority claim.

Negative controls stayed unchanged: 23/52 clean when every output counts, 36 false positives; shared-11 view 42/52 clean and 10 false positives. Out-of-scheme outputs remain visible (89 per arm). PHONE typed true positives increased 72 to83 and CREDIT_CARD6 to27; no other type gained true positives, while THAI_ID false positives fell3 to0. This supports the combined patch, not attribution of the entire F2 gain to input recovery alone.

NER completed220/220 chunks per arm, no skips. Entirely uncovered entities 98 to 69; partly uncovered remained 129. Important misses remain. Coverage counts include whitespace/punctuation and do not measure identity-linkage attack risk.

## Controlled source-representation study

60 seed/type families, 300 dependent variants, separately measured in token and surrogate modes. Profiles include original forms, format controls, width forms, repeated separators and composed changes. Each arm uses the same strengthened final guard; raw means input recovery disabled, not the archived historical baseline.

| Mode | Completely protected releases, raw | Completely protected releases, recovery | Recovery blocks | Recovery oracle-uncovered releases |
|---|---:|---:|---:|---:|
| token | 64/300 | 252/300 | 48 | 0 |
| surrogate | 64/300 | 252/300 | 48 | 0 |

All released recovery cases restored exactly and preserved the fixed non-sensitive amount; no extra non-PII characters were masked in these probes. These are deliberately constructed development cases, not independent population samples. Repeated/combined email and IBAN shapes remain conservatively blocked. A zero observed oracle-exposure count is not a guarantee of anonymity or safe release on arbitrary inputs.

## What was built and checked

- Shared source-position views for format controls, Thai digits and one-character ASCII-width forms; no arbitrary NFKC or raw-text mutation.
- Same-line field cues for numeric separator recovery; hard Unicode line/tab boundaries; repeated occurrence and PDF interval mapping tests.
- Coverage admission preserves both raw detector intervals and original guard-detectable structured units. Independent review exposed a composed-obfuscation IBAN/PHONE signature-destruction regression; generic admission constraints and failing-then-passing tests fixed it.
- Model/corpus/source/parser/runner/loader/statistics/driver fingerprints and a one-use paired evaluation reservation. Scorer/model/dependencies match between arms. The only registered blind.py difference aligns freeze validation with the written maximal13-digit-token rule; other runtime evaluator files match.
- Frozen gold-v4 development F2 remains0.946924; conditional component experiments are in component-results.json. Raw CRF has a different label capability and must not be presented as a same-task engine ranking.

## Verification and delivery boundary

2,791 Python tests passed,34 skipped; one existing dependency warning. Lint, formatting, version consistency and diff checks passed. No optional-engine, physical OCR, installed app, live provider or hosted deployment acceptance is inferred from those checks.

| Local operation median (ms) | Baseline | Candidate | Ratio |
|---|---:|---:|---:|
| detect | 5.90 | 6.04 | 1.024 |
| sanitize | 15.82 | 15.82 | 1.000 |
| restore | 0.25 | 0.26 | 1.040 |
| pdf_redact | 80.99 | 71.87 | 0.887 |

Three alternating source-arm controls in one environment; RSS 151.3/151.5MiB. Relative repository budgets passed. Legacy anchors were already red before changes and were not moved. These are local medians, not production latency/SLO evidence.

## Decisions and remaining risks

- Keep the existing CRF default and avoid a heavyweight dependency until a project-specific comparator earns its cost. Consequence: contextual NAME/ADDRESS misses remain.
- Use same-family isolated synthetic author/reviewer contexts; no human or cross-family agreement claim. Consequence: shared-style/template bias remains.
- Keep the clean canonical checkout/feature branch, not another physical project copy; preserve originals and all old blind artifacts.
- Require context for new short-card lengths because corrupted OCR IDs also pass Luhn; retain existing16-digit compatibility and its known long-code precision limit.
- Keep generic-date/quasi-identifier policy and exam-roster STUDENT_ID scope unchanged; some typed errors are protected values rather than leaks.
- Prefer conservative blocking to ambiguous field joining, arbitrary fragments, or partial destruction of an original guard unit. Consequence: some useful inputs remain blocked.
- Repair old corpus references only after exact historical hash verification; do not rebind historical system scores.
- This held-out set is now closed to tuning. Any later candidate needs fresh independent evaluation.
- Delivery is a local reviewed source/research branch. No remote push, main merge, new installer, publication or deployment was performed.

## Artifacts

- [Research alternatives and sources](reports/Thai%20PII%20research%20advances.md)
- [Paired held-out evidence](heldout-paired.json)
- [Representation study](recovery-study.json)
- [Conditional component experiments](component-results.json)
- [Original baseline](baseline.json)
- [Current development capture](candidate-development.json)
- [Performance controls](recovery-performance.json)
- [Author/reviewer aggregate QA](heldout-qa.json)

Held-out report SHA-256: `d923e6af40b666724f077c787d00aae8ba300f6cf49b7a2427155507ee9df8c0`.

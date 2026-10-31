# PDPA coverage design and measured results

## Decision

**Use a hybrid-assisted human review workflow; do not claim complete automatic PDPA coverage.** The catalog represents 11 named sensitive families, 11 general navigation families and 2 open/unassessed slots. This is breadth of representation, not perfect detection, legal advice, a consent registry or a compliance certificate.

Contextual is the ordinary fast CLI default without new dependencies. Hybrid is the preferred available deep-assessment profile at cosine threshold0.40, with a real pinned local model and human review. Do not skip hybrid/human assessment solely because contextual has zero findings. An independent controller-confirmed data inventory is mandatory before any future processing approval, including unknown/unsupported data.

## Operational design

1. Intake and controller-confirmed inventory of sources, subjects, categories, modalities and purposes.
2. Model/rule assessment: separate category, personal attribution, topic-only and uncertainty; route unsupported/raw modalities to qualified review.
3. Confirm Section 24 route and separate Section 26 condition; review scoped consent, capacity, notice and recipients. Caller JSON flags are unverified declarations.
4. Use existing shared identifier masking and final guards where appropriate. Sensitive findings remain warn/review, not blanket automatic redaction.
5. Assign purpose-specific retention, holds and processor/backup handling; manage verified rights cases with the applicable clocks.
6. Require authenticated controller approval and verified execution evidence. The delivered prototype stops at non-executing proposals.

The complete proposed records/state machines are in [LIFECYCLE-DESIGN.md](LIFECYCLE-DESIGN.md). Actual consent ledgers, authority verification, data deletion, rights delivery and deployment are not implemented or claimed.

## Frozen three-method evaluation

210 records, 198 text and 12 unsupported-modality placeholders, independently authored/reviewed before scoring. The 70 calibration records are separate. One registered batch ran all 3 methods offline on identical records. Labels/IDs/scope never enter a detector; scope limits the adjudicated scoring view.

Source `65aedaf66a16f38d0eade138dc93f35b9757f521`; source SHA `5bcad757ba299823a87ca9d50bda49802658d4e3711f0e56b3d5d13ff3b728ab`. Model revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`; threshold 0.40. Source/scorer/helper/Python/package/model/NER/protocol/corpus identity was frozen before final evaluation. No post-disclosure classifier tuning.

| Metric | Keyword | Contextual | Hybrid |
|---|---:|---:|---:|
| Macro personal-attribution F2 | 0.3439 | 0.4051 | 0.5141 |
| Shared legacy-sensitive macro F2 | 0.4086 | 0.5497 | 0.6081 |
| Personal precision | 0.4588 | 0.8036 | 0.6413 |
| Personal recall | 0.3391 | 0.3913 | 0.5130 |
| Personal micro F2 | 0.3578 | 0.4360 | 0.5344 |
| Topic F2 | 0.3620 | 0.6238 | 0.7356 |
| Joint category+attribution F2 | 0.2046 | 0.3443 | 0.4082 |
| Topic-only false personal rate | 38.18% | 1.82% | 1.82% |
| Topic-only non-topic flag proxy | 38.18% | 45.45% | 58.18% |

Hybrid trades higher recall/F2 for lower precision and more alerts than contextual. The proxy counts predicted personal/ambiguous signals, not measured human time or actual case completion. A false-personal rate on 55 topic-only records is not overall false-positive probability. General findings in sensitive-scoped records are outside this corpus adjudication.

Small per-category counts are descriptive. There is no independent human/population validation or significance claim. Macro personal F2 is a different task/ontology from the earlier 11-type YRSS entity-overlap F2 and must not be compared as if it were the same score.

## Measured category gaps

| Category | Personal targets | Hybrid TP | Hybrid FN | Hybrid F2 |
|---|---:|---:|---:|---:|
| RACE | 6 | 4 | 2 | 0.606 |
| ETHNICITY | 6 | 3 | 3 | 0.500 |
| POLITICAL_OPINION | 6 | 1 | 5 | 0.200 |
| BELIEF | 6 | 4 | 2 | 0.667 |
| SEXUAL_BEHAVIOR | 6 | 5 | 1 | 0.862 |
| CRIMINAL_RECORD | 6 | 2 | 4 | 0.385 |
| HEALTH | 8 | 7 | 1 | 0.897 |
| DISABILITY | 6 | 4 | 2 | 0.690 |
| LABOR_UNION | 6 | 4 | 2 | 0.667 |
| GENETIC_DATA | 6 | 4 | 2 | 0.667 |
| BIOMETRIC_IDENTITY | 6 | 3 | 3 | 0.536 |
| IDENTITY | 8 | 3 | 5 | 0.357 |
| CONTACT | 4 | 3 | 1 | 0.789 |
| LOCATION | 4 | 2 | 2 | 0.556 |
| FINANCIAL | 3 | 3 | 0 | 1.000 |
| EDUCATION | 4 | 2 | 2 | 0.526 |
| EMPLOYMENT | 3 | 1 | 2 | 0.357 |
| ONLINE | 6 | 2 | 4 | 0.370 |
| ACTIVITY | 6 | 0 | 6 | 0.000 |
| RELATIONSHIPS | 3 | 1 | 2 | 0.385 |
| MEDIA | 3 | 1 | 2 | 0.294 |
| QUASI_IDENTIFIERS | 3 | 0 | 3 | 0.000 |

**ACTIVITY and QUASI_IDENTIFIERS had zero recovered personal targets in this sample.** Political-opinion and identity recall are also limited. A catalog entry or a model candidate is not demonstrated coverage. No model-generated zero finding can waive controller inventory review. Raw image/audio/video/genetic records were review-routed 12/12, but those were placeholders, not payload analyses.

## Compute cost

| Text evaluation latency | Keyword | Contextual | Hybrid |
|---|---:|---:|---:|
| Warm p50 ms | 3.28 | 3.17 | 26.81 |
| Warm p95 ms | 5.46 | 5.81 | 39.32 |

Resource probes below use separate processes and one fixed public synthetic input; they are not the same workload as the evaluation.

| Separate-process probe | Keyword | Contextual | Hybrid |
|---|---:|---:|---:|
| Cold start seconds | 0.38 | 0.36 | 7.73 |
| Peak working set MiB | 134.33 | 134.15 | 1664.76 |

The standard environment/lock stayed unchanged; model dependencies live in .venv-pdpa-ml. Approximately 117M-parameter model weights and actual local embeddings are used, not a stub/API. No real customer content was uploaded. Existing-path sanitizer anchor remained red before this additive change; existing detector/session/HTTP/native logic was not changed and the anchor was not moved.

## Lifecycle policy simulations

20 hand-authored functional requirements compare deliberately weak uniform consent, manual-only review and the basis/lifecycle planner. This is requirement conformance, not independent legal accuracy or actual fulfilment.

| Experimental policy | Satisfied scenarios | Missing required proposals | Forbidden suggestions |
|---|---:|---:|---:|
| uniform_consent | 1/20 | 26 | 3 |
| manual_only | 3/20 | 27 | 0 |
| basis_lifecycle | 20/20 | 0 | 0 |

No method executed any action. The planner distinguishes consent from other bases, Section 26 conditions from the general basis, withdrawal from erasure, holds from expiry, access from erasure clocks and other rights from a fabricated 30-day rule. Dates are indicative arithmetic; applicability/identity/evidence/holidays require controller review.

## Evidence and limitations

- All named statutory families are represented, but support is partial text assessment. Section 6 is open-ended; additional committee-prescribed categories remain unverified.
- Same-family AI authors/reviewers and fictional style cues limit external validity; see corpus-qa.json. Actual images, audio, video, biological sequences and natural organizational records were not tested.
- Initial calibration is preserved. Ordinary third-person/student parsing, full-catalog prototypes and independently reproduced review defects were fixed before final scoring. Those are development changes, not independent gains.
- Review corrections covered standalone sensitive context, no-value parser errors, consistent selected threshold, reported personal negative statements, scorer/decode/NER/runtime fingerprints and semantic relation/finite-score integrity.
- Full local Python gate: 2,840 passed, 34 skipped, one existing dependency warning; lint/format/version/diff checks passed. No remote CI, deployment, installed-host, legal certification or real rights execution is claimed.
- Existing HTTPv2/native/Hosted interfaces and legacy risk grades are not promoted into this comprehensive assessment. Use the new CLI for this prototype.
- The final evaluation set is closed to tuning; later changes need a fresh evaluation.

## Reproduction

Core commands: `python ai_guard.py pdpa coverage`, `pdpa assess input.txt --context context.json`, and `pdpa lifecycle --context context.json`. Optional hybrid uses the ML environment, explicit pinned snapshot and `--strategy hybrid --threshold 0.40`. Output paths must be new and cannot overwrite/alias input or context. No arbitrary context strings or rejected argument values are echoed.

Files: [evaluation-results.json](evaluation-results.json), [calibration-results.json](calibration-results.json), [resource-results.json](resource-results.json), [workflow-results.json](workflow-results.json), [validation-matrix.json](validation-matrix.json), [design/source report](reports/PDPA%20coverage%20and%20lifecycle.md).

Evaluation raw-file SHA-256: `cdbe4ed718c2ef1f80068f979aba895083f71145067cd05905db0254549db8dc`.

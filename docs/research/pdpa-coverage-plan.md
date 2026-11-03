# PDPA category and lifecycle implementation plan

Goal: represent the PDPA's open personal-data scope and all named sensitive
families; compare keyword, contextual and real local-semantic assessment; deliver
a shared-core CLI and non-executing consent/retention/rights planner.

Owner scope (2026-10-31): category coverage, design, real experiments and
evaluation, explicitly including consent, retention and subject rights.
Design/source synthesis: `research/pdpa-coverage/reports/PDPA coverage and lifecycle.md`.
Baseline: `b2761bd`; preserve all completed YRSS evidence and closed corpora.

## Contracts and limits

- Section 6 is open-ended, not a finite list. Catalog every family with actual
  capability state. All named Section 26 text families get assessment evidence;
  raw image/audio/video/genetic analysis and future prescribed categories stay
  explicitly unassessed. No complete-detection/compliance certification.
- Distinguish category, personal attribution, topic-only and uncertainty. Do not
  infer race from nationality, biometric identity from an ordinary photo, or
  absence of personal health information from negation or quotation.
- Section 26 remains warn/review only. Existing masking, HTTP v2, native IPC,
  provider and mapping rules remain intact. No new remote route or stored vault.
- New `pdpa assess`, `pdpa coverage`, `pdpa lifecycle` CLI verbs share root core.
  Reports/errors contain fixed codes/counts/spans, no text, values, source names,
  subject hashes, arbitrary purpose strings or exception messages. Output must
  not overwrite or alias input/context; no implicit recursive scanning.
- Workflow context is closed, strictly typed, and caller-declared. Output is a
  simulation/proposal, never authorization, consent evidence, identity proof,
  deletion or a rights response. No filesystem/database action executor.
- Consent is one basis. Sensitive processing needs its own reviewed condition.
  Withdrawal never silently switches basis; holds do not authorize indefinite
  unrestricted use. Minors/capacity require reviewed authority, not a fixed
  under-20 rule. Purpose-specific retention has no universal statutory period.
- Access uses 2026 notification clocks: initial check15 days; correction window
  at least10; fulfilment30 with conditional extension<=30 and required notice;
  required evidence retained>=2years. Erasure qualifying requests use90 days
  from receipt, not access completeness; unlawful33(4) cannot substitute
  anonymization. Other rights have no invented universal numeric deadline.
  Calendar dates are indicative anchors, not a legal holiday calculation.

## Implementation tasks

1. `pii_redactor/pdpa_catalog.py`: versioned statutory/general families, sources,
   capability states and closed context schema. Tests pin categories and limits.
2. `pii_redactor/pdpa_assessment.py`: value-free findings and attribution over
   original source intervals. Strategies `keyword`, `contextual`, `hybrid`.
   Reuse `detect_all`; explicitly selected semantics must fail if unavailable.
3. `pii_redactor/pdpa_semantic.py`: optional pinned real MiniLM; safe local
   safetensors only, CPU, token-aware offset windows, no silent truncation or
   automatic download. Keep production dependencies unchanged; experiments use
   `.venv-pdpa-ml` and ignored model cache with complete hashes.
4. `pii_redactor/pdpa_lifecycle.py`: purpose/basis/consent/capacity, retention,
   legal-hold, rights/identity/deadline plans. Return fixed proposal codes and
   human decisions still needed, never a compliance grade or action execution.
5. Extend `ai_guard.py` with real CLI dispatch and privacy/no-overwrite tests.
   Reuse receipt/DSAR/breach where applicable; do not call them fulfilment.
6. `benchmark/pdpa_study.py`: frozen corpus/strategy/config/model identity,
   category+attribution metrics, topic-only false alerts, review/availability,
   unsupported-modality handling, latency/RSS and workflow-policy simulations.
   Experimental weak consent-only/manual baselines never enter production.
7. One independent whole-change review, focused plus complete Python checks,
   lint/format/version/diff checks and proportional performance evidence.
   Record actual coverage and gaps; no deployment/publication implied.

## Experiment registration (before implementation/evaluation)

Independent synthetic authoring: `research/pdpa-coverage/annotation-guide.md`.
280 records: 176 sensitive (16 per named category), 88 general (8 per family),
16 declared raw-modality cases. Family-disjoint calibration70/evaluation210;
no related template/value family may cross split. Independent fix-only review;
no detector disagreement pass. Same-family AI annotations, not human labels.

Corpus/key intentionally outside repositories at
`C:/Users/teera/aiguard-pdpa-context-v1/`. Developer never reads evaluation text.
Encrypted final records and aggregate lock/QA may enter this repository.
Calibration can be scored for thresholds; independent final evaluation is one
registered batch of three frozen strategies, aggregate-only, with no tuning
after disclosure. Old YRSS/blind-v1/v2/yrss-holdout corpora remain closed.

MiniLM revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`; threshold selected
only on calibration from0.40/0.50/0.60/0.70. Compare shared legacy categories
and full catalog separately. Similarity is not a calibrated probability.
Default selection on calibration: macro personal-attribution F2 subject to
topic-only false-alert rate<=20%; ties within0.01 choose lower warm latency.
If none meets the constraint, retain contextual as a review-oriented candidate
with the failure explicit. Final test reports gains/nulls/regressions, never
changes selection. Small per-category counts are descriptive; family bootstrap
may quantify this constructed sample, not population legal accuracy.

Review focus: declaration spoofing/unknown fields, lost offsets/long truncation,
negated and quoted personal facts, media/future category blind spots, retention
hold contradictions and rights-clock misuse, sensitive output/error leakage,
and no mistaken action-execution/compliance claim.

## Ledger

- Clean source at `b2761bd`, branch `research/pdpa-coverage-lifecycle`.
- Primary legal/model/tool alternatives researched before design. Current Thai
  access2026 and erasure2024 notifications included; future catchall additions
  remain unverified rather than guessed.
- Optional model env isolated; app environment/lock unchanged. Actual public
  model safetensors downloaded anonymously at the pinned revision.
- Local source implementation/evaluation and complete gate remain pending.

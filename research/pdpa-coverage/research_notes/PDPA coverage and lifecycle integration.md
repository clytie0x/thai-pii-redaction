# PDPA coverage and lifecycle integration map

Read-only source inspection on 2026-10-31. This note proposes a bounded integration path; it does not change policy, contracts, detection, retention, or controller decisions. No tests, providers, network requests, held-out data, decryption, or scoring were run.

## Smallest complete caller path

Add a separate core assessment module under `pii_redactor/` and one `ai_guard.py pdpa assess <file>` caller. Keep the current `report`, `sanitize`, receipt, breach, DSAR, HTTP v2, and native IPC interfaces unchanged. A comprehensive category catalog means every family is represented with its evidence and limitations; it does not mean every family is reliably detected or every document is legally classified.

Suggested interfaces, subject to the controller's final design:

- `assess_pdpa(text, *, context=None) -> Assessment`: shared core, transient text, structural category findings, detector availability, unknown context, and review obligations.
- `Assessment.to_json_dict()`: an explicit allowlist projection with a new schema identifier. Export category IDs, counts, source kinds, capability/status codes, and fixed limitation/action codes. Never export original text, evidence excerpts, entity IDs, subject hashes, reversible tokens, source filenames, arbitrary exception messages, or caller free text.
- `plan_lifecycle(assessment, context) -> LifecyclePlan`: a pure planner for consent, retention, and rights review, with unknowns preserved. It does not record consent, delete a file, serve a rights response, or authenticate a requester.
- CLI ingest can follow `receipt.process_for_receipt()` (`detect_source_type -> extract -> clean -> detect_all`) and pass its existing text/entities to the assessment, avoiding duplicate detector work. The helper includes text and `Entity.original_text`, so it is an internal transient object, never a serializer input.

Represent observation and coverage separately: a category may have zero observed findings while its capability is `unsupported`, `metadata_only`, `not_run`, or `unavailable`. Do not collapse any of these into absent data. Contextual identifiability and Section 26 applicability require controller review. Preserve offsets internally if needed; document whether these are cleaned-text offsets rather than original-file coordinates. Preserve PDF bbox behavior.

Use explicit `--semantic` selection only with a clear unavailable failure. A deterministic, no-model default can still report semantic coverage as not run. Do not invoke `sensitive_detector._load()` during metadata assessment: it constructs `SentenceTransformer` and may fetch a model.

## Current callers and contracts

| Surface | Current implementation | Integration consequence |
| --- | --- | --- |
| `ai_guard.py:cmd_report` | Reads/cleans, `detect_all`, direct counts, count-based Low/Medium/High. It does not call `report.analyze_text`. | Do not describe extending `analyze_text` as automatically extending CLI report. Prefer a new verb. |
| `pii_redactor/report.py:generate_report` | Keyword Section 26, direct counts, heuristic re-identification/overall scores. | A heuristic grade is not a legal coverage verdict. |
| `pii_redactor/report.py:analyze_text` | Shared internal assembly for API/PDF/worker; detects once, adds optional semantic Section 26 findings. | Keep its schema and existing consumers stable initially. |
| `app/http_v2.py` | Strict extra-forbidden models, fixed recommendation templates, eight-category literal vocabulary/canonical ordering. | New categories or fields are not an additive safe change to strict v2. |
| `app/server.py:_section26_categories/_analyze_projection` | Allowlisted projection drops unknown categories and reconstructs recommendations from fixed templates. | Merely extending core keys would silently lose new categories at this adapter. |
| `native-broker/protocol-v1.json`, `native-broker/src/data_plane.rs` | Fixed category vocabulary, exact keys, fixed recommendation text. | Do not broaden native IPC in this research increment. A future adapter change needs coordinated contract review. |

`ai_guard.py:main` directly creates parsers and dispatches via `set_defaults(func=...)`. Existing command tests construct `SimpleNamespace` for handler tests and monkeypatch `sys.argv` for real parser coverage. Receipt uses stock argparse usage exit 2. Breach/DSAR locally bind usage exit 1 because exit 2 means partial file failure; preserve those sibling behaviors. Define the new verb's exit policy explicitly. Prefer stdout JSON without mixed summary lines, or `-o` JSON plus a count-only summary. Follow receipt's preflight and no-overwrite convention, but use fixed value-free errors rather than legacy arbitrary exception interpolation. Reject source/output identity before writing.

## Existing lifecycle features to reuse

| Feature | Existing interfaces and evidence files | What it does not provide |
| --- | --- | --- |
| Processing receipt | `receipt.build_receipt`, `verify_receipt`, `_claims`; schema `aiguard.processing-receipt/1`; CLI `receipt issue/verify`; `tests/test_receipt.py` | Per-run reproducibility evidence, not a consent record, complete RoPA, lawful-basis decision, or retention register. Optional purpose/controller fields are caller text and therefore outside an absolute value-free guarantee. |
| Breach assessment | `breach.assess_breach`, `BreachAssessment.to_json_dict`; schema `aiguard.breach-assessment/1`; CLI `breach assess`; three `test_breach*` files | Aggregates detected types and strong-identifier count bounds. Does not decide notification threshold, prepare/send an authoritative notification, identify people across types/documents, or establish actual affected-person totals. |
| DSAR locate | `dsar.locate_subject`, `DsarResult.to_json_dict`; schema `aiguard.dsar-locate/1`; CLI `dsar locate --subject-file`; three `test_dsar*` files | Locates only. No identity verification, delivery, completed rights response, portability, rectification, objection, restriction, or erasure execution. Exact canonical matching has OCR misses; names are weak; third-party indication is heuristic. |
| Corpus helpers | `scan_common.discover_files`, `canonical_value`, `path_spellings`, `short_reason` | Reuse discovery/canonical matching if a future corpus caller needs them. Discovery reports skipped non-TXT/PDF basenames. Existing basename/error-message exports are not a safe template for a stricter fully value-free assessment. |
| Technical session disposal | `SessionService` TTL, `drop`, `dispose_authenticated`, expiry cleanup | Removes service references/clears vault ownership; Python immutable strings cannot be guaranteed zeroized. It is not an organization-wide retention schedule or verified source/backup erasure. |
| Audit output | `pii_redactor/audit.py` disk/stdout writers | Disk log timed retention remains unaccepted per current status. Do not imply a new planner enforces it. |

No consent ledger, purpose-level consent state machine, retention-policy engine, legal-hold execution, or complete rights case-management workflow was found in the inspected root `pii_redactor/`, `app/`, and CLI paths. Independently maintained `packages/amphrang` and `apps/hosted/core` have their own copies/boundaries; do not implement a new root feature by modifying them implicitly.

## Consent, retention, and rights workflow design

These workflows should initially produce reviewable plans. Controller declarations are inputs, not detector conclusions. Use closed enums, bounded integer counts/relative durations where appropriate, and opaque review references. Avoid free-text names, subjects, purposes, URLs, document basenames, or attachments in the value-free exported plan.

**Consent:** select purpose and processing context, identify the ordinary lawful-basis review and any separate Section 26 condition review, record whether evidence was declared available, flag missing/expired/withdrawn evidence, require controller review before determining the next processing action. Absence of a supplied consent record must not be treated as unlawful processing, and a sensitive signal must not imply consent is always the only permitted condition. A future operational ledger would need versioned notices, granular purposes, evidence custody, withdrawal, minor/representative handling, and authorization design; this research plan should enumerate those requirements rather than invent a ledger or accounts.

**Retention:** inventory original files, transient ingest/OCR data, in-memory mappings, requested artifacts, logs, provider/platform copies, and backups as distinct surfaces. For each, collect purpose, owner, retention trigger, duration or review date, exception/hold, proposed disposal method, and evidence requirements. Unknown retention stays unknown. The planner can mark `decision_required` or `review_due`; it must not claim `deleted` or `compliant`, invoke cleanup, or modify session TTL. A controller must supply actual policy and legal requirements before operational deletion is designed.

**Rights:** intake a request type, verify identity and authority outside the detection engine, establish scope and relevant deadline review, locate relevant files through the existing DSAR helper where suitable, review third-party rights/exemptions, then prepare a response/action for controller approval and record outcome evidence. Include access, portability, objection, erasure/destruction/anonymization, restriction, and rectification as planning categories, with consent withdrawal handled in the consent workflow. Never label a locate result as fulfillment or a proposed deletion as performed. The exact legal deadlines/exceptions must come from the legal-source research, not from these code paths.

## Legacy category and claim hazards

`report._SECTION26_KEYWORDS` and `sensitive_detector._PROTOTYPES` each have eight categories. They lack explicit genetic and biometric families. `RACE_ETHNICITY` includes the Thai nationality keyword, which is insufficient by itself to conclude racial/ethnic data. Religion/belief, political, criminal, and other broad keywords can be mentions of a topic rather than data about a person. The semantic detector chooses one best category per sentence and emits input text/spans. It is a heuristic signal, not comprehensive multilabel detection or proof of a legal condition.

`sensitive_detector.detect_sensitive` returns `[]` when its dependency is missing. `report.analyze_text` catches all semantic exceptions and continues. Semantic-only findings are appended after `_generate_report` calculates score/grade, so a semantic sensitive finding may coexist with the earlier low grade. The new assessment must expose availability and category observation separately and must not reuse that score as a comprehensive verdict.

Unqualified explicit-consent wording exists in `report._generate_report`, `report.analyze_text`, `app/http_v2.RECOMMENDATION_TEMPLATES`, and the mirrored fixed native recommendation in `native-broker/src/data_plane.rs`. A change to this wording across public adapters is a separate coordinated contract decision. The new assessment should use qualified legal-review instructions from verified legal sources and explicitly preserve Section 26 warn/report-only behavior. Do not call the tool or a plan PDPA compliant.

## Verification and change rules

Root `AGENTS.md` requires tests first for new behavior; positive, failure, and privacy paths; current-state documentation only when truth changes; an ADR for costly-to-reverse architecture/public-contract/data-destruction decisions; and an independent separate-context review before such a decision lands. A reversible research note or implementation plan does not itself require a new ADR. Use one concise plan, preserve existing accepted ADRs, and do not create parallel historical truth.

Focused evidence to add for the new assessment/CLI:

- Every catalog family appears, including unsupported/metadata-only states; no-match differs from unavailable/not-run; direct detection runs once; no implicit network/provider calls.
- Sensitive topic vs personal attribution, nationality vs ethnicity, biometric input vs biometric identification, and absence of contextual facts yield review/unknown rather than invented certainty.
- Findings and all lifecycle plans remain value-free recursively, including Unicode/JSON parser errors, unknown labels, paths containing synthetic PII, invalid context, output failures, and retained exception objects. Reuse `safe_errors.discard_exception_graph` at fresh fixed-error translation boundaries.
- Controller consent/exception inputs do not cause automatic redaction/blocking; unknown retention never becomes a fabricated schedule; withdrawal/rights plans do not execute actions or claim completion.
- Real `main()` dispatch, explicit optional-engine unavailable behavior, stdout JSON parseability, no overwrite, input/output alias rejection, and unchanged sibling exit semantics.

Existing privacy/compatibility references: `tests/test_safe_errors.py`; `test_dsar_cli.py:test_dsar_locate_subject_values_never_leak_across_stdout_stderr_json`; DSAR missing-subject-file and failed-output tests; `test_dsar.py` error privacy tests; breach failed-path/partial-output tests; receipt forgery and output-preservation tests; `test_http_v2_contract.py` exact projection, unexpected endpoint error, Section 26 canonical order and explicit TNER failure tests; `test_native_broker_protocol.py` exact fields/fixed error/retained traceback tests. `test_step13_sensitive.py` skips the entire module without sentence-transformers, so a skipped module proves no unavailable-path behavior. `test_step12_report.py` verifies existing analysis assembly/detect-once, not broad PDPA coverage.

Before a product implementation lands, run the focused tests and affected complete lane gates from `.agents/skills/aiguard-change-workflow/references/check-matrix.md`, `git diff --check`, Ruff, and the required local `scripts/measure_perf.py` gate if `pii_redactor/` or `app/` changes. Research-only work does not justify a full suite. No acceptance state is advanced by this inspection.

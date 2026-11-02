# AI Guard Production Milestone Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task with tests first. The owner resumed execution and requested Astra review followed by Sol 6.1 implementation. Use the [current execution addendum](2026-11-02-astra-sol-execution-review.md), preserve existing work and obtain independent adversarial review at every stage. This plan does not authorize production actions or mark runtime gates passed.

**Goal:** Deliver a usable single-organization, self-hosted PDPA system and qualify each supported AI Guard delivery surface against its actual trust boundary.

**Architecture:** Reuse the root Python protection core. Add a separate enterprise FastAPI application, PostgreSQL-backed governance domain and staff/subject authentication boundaries. Keep governance records separate from the local in-memory reversible vault. Integrate imported Hosted and SDK implementations through reviewed compatibility adapters rather than silently replacing their contracts.

**Tech stack:** Existing Python/FastAPI, PostgreSQL 18, the Stage 1 psycopg/Authlib optional dependency set, and the existing browser UI stack. Desktop remains Tauri and Extension remains MV3/Native Messaging. No new frontend framework, queue service, ORM or model is selected by this plan.

**Spec:** [Accepted enterprise design](../decisions/2026-10-31-pdpa-enterprise-control-plane.md), [Stage 1 task plan](pdpa-enterprise-stage1.md), [monorepo decision](../decisions/2026-10-19-monorepo-import.md), and [version reset](../decisions/2026-10-19-version-reset.md).

**Planning snapshot:** 2026-11-02. Canonical checkout: `design/pdpa-enterprise` at `87c7125`. Separate implementation worktree: `.worktrees/pdpa-enterprise/`, branch `feat/pdpa-enterprise`, checkpoint `1677e60`. Both were clean when inspected. Re-resolve these identities before execution; they are observations, not permanent instructions to use a particular checkout.

**Execution authorization:** the owner subsequently requested M0-M12 and YRSS
completion on 2026-11-02, revoking the implementation pause. The owner clarified
that "anti-jobs" means independent adversarial subagent review at every stage.
Historical planning/pause statements below describe the planning snapshot;
current execution evidence and owner-only gates live in
[release scope](../enterprise/release-scope.md) and the milestone acceptance records.

## 1. Historical starting position and scope

The canonical design branch contains no enterprise web application. The separate implementation branch already contains foundation and registry work, so Stage 1 must be resumed from its evidence rather than rebuilt from an empty directory.

| Area | Observed starting position | What is still required |
|---|---|---|
| Core protection | Detection, sanitization, residual guards, restoration, PDF and local assessments exist | Cross-surface policy reconciliation, current-candidate regression and delivery acceptance |
| Enterprise persistence | `4d31d76` implements PostgreSQL authority, migrations and atomic audit | Reproduce its environment, review migrations and preserve the checkpoint |
| Enterprise registry | `03b8aa3` implements scoped activities, notices and membership/review commands | Authenticate real staff and expose a complete usable web/API path |
| Checkpoint evidence | Handoff records 44 real-database focused tests and 2,884 full-suite passes / 34 skips | Reproduce on the resumed candidate; these are recorded results, not tests run while writing this plan |
| Staff authentication | No accepted OIDC/web boundary; local IdP startup unresolved | Working real IdP, server sessions, CSRF, revocation and browser acceptance |
| Consent/retention/rights | Assessment/advisory tools and accepted workflow design | Durable authoritative records, approved execution and verified outcomes |
| Imported products | Hosted and SDK still have separate engine copies and check systems | Explicit policy/contract inventory, shared-core migration and CI coverage |
| Distribution | Root/source version is `0.1.0`; older evidence names archived releases | Exact new artifacts and separate release/host/platform evidence |

Checkpoint details are available on `feat/pdpa-enterprise` in `docs/implementation/pdpa-enterprise-handoff.md`. Do not copy its test totals into a new acceptance record without rerunning the relevant gates. The earlier development pause was revoked by the owner. The execution addendum records the clean post-privacy-rewrite checkout, preserved prerequisite candidate and outstanding gates; re-resolve those identities before further implementation.

The enterprise release includes staff inventory, notices, subject consent, managed-document retention, rights cases, processor/transfer records, incidents, responsibility and risk review, recovery and a supervised organizational pilot. Desktop, Extension, Hosted, SDK and Office have individual support decisions. An enterprise pilot does not require an unclaimed Office host, Web Store publication or PyPI publication. A product-wide release claiming all those surfaces must pass every corresponding surface gate.

## 2. Global constraints

- One self-hosted organization, multiple departments, authoritative staff roles. No multi-tenant SaaS claim.
- Keep existing HTTP v2/native contracts and local memory-only mapping intact. Persistent governance/evidence contains protected personal information and requires its own access, encryption and retention policy; it is not permission to persist reversible local vault mappings.
- Detection is evidence for review. A zero finding never authorizes processing; sensitive findings and prompt-injection signals do not cause blanket deletion or legal approval.
- Unknown category/modality coverage remains explicit. Preserve original source spans and PDF coordinates; optional engines fail clearly when explicitly unavailable.
- Every domain mutation checks current actor authority, organization/scope, record revision and idempotency. A business transition, required minimized audit and outbox write commit atomically.
- Separate staff and subject authorities. Administrators do not acquire legal approval rights from an IdP claim. Preserve two-person approval and one-time offline enrollment.
- No raw content, mappings, credentials, identity documents or provider bodies in general logs, error DTOs, screenshots or acceptance artifacts. Use synthetic values in all development fixtures and demonstrations.
- Reuse the accepted stack. Verify maintenance, license, advisories, compatibility and exact locks before installing a new dependency; keep enterprise dependencies optional and separately locked.
- Preserve existing commits, untracked work, the paused worktree and closed evaluation corpora. No history rewrite, implicit main merge or new held-out disclosure from planning.
- External messages, real data operations, production deployment, public releases and store/package publication require explicit owner authority for the exact action. A successful simulated or queued action is not fulfilment.
- Follow root `AGENTS.md` for the branch/CI/squash delivery loop; the repository uses no PRs for its own work. Reconcile checkpoint-specific preservation instructions before integration. Never squash unrelated or paused work as a side effect.

## 3. Verification rules used by every milestone

### 3.1 Task cycle

Each task below follows this sequence, including the named failure assertions:

1. Inspect the affected execution path, current branch/worktree status and inputs from the preceding milestone.
2. Write the focused positive and failure tests. Run them and record the expected failing assertion; environment setup failure is not a valid behavior-test RED.
3. Implement the smallest complete domain/API/UI path, including migration, errors, permissions and operational documentation.
4. Run the focused tests to GREEN, then the complete affected-lane gate from the [check matrix](../../.agents/skills/aiguard-change-workflow/references/check-matrix.md). An unavailable mandatory PostgreSQL/IdP/browser gate is blocked, never a passing skip.
5. Run the milestone's real-path exercise and a distinct adversarial review. Validate review findings before changing code. Review high-impact work independently before landing.
6. Save value-free evidence, review the diff and land only the intended change through the repository delivery loop. Rebind candidate evidence when a merge changes source/artifact identity.

### 3.2 Evidence levels and gate status

| Level | Evidence proves | Evidence does not prove |
|---|---|---|
| E1 | Unit/contract tests, synthetic injected failures | Real database, IdP, host or provider behavior |
| E2 | Real local PostgreSQL/IdP/worker/installed package integration | Production infrastructure, legal applicability or human usability |
| E3 | Real browser, Office host or declared OS installation on exact candidate bytes | Other hosts/OSs, Web Store installation or public deployment |
| E4 | Exact staging/live-provider/organization infrastructure acceptance | Broader scope or authorization for a real-data action |
| E5 | Approved representative pilot, recovery drills and owner release acceptance | A compliance certificate or a guarantee of anonymity |

Use `not_started`, `in_progress`, `blocked`, `passed` or `not_in_release` for each gate. `not_in_release` requires a named omitted capability and an honest disabled/unsupported product state. All required gates must be `passed`; a skipped security/host test is not equivalent. Mark a milestone `passed` only for its bounded result, never for the entire program.

For each milestone create one record under `docs/acceptance/enterprise/Mxx-<slug>.md` during execution. Keep detailed raw tool output in an ignored, access-controlled directory and reference its digest; do not commit raw browser/network/provider captures. The record contains:

- source commit/tree, parent baseline, build/image/package digests, dependency/model/schema/config identities and environment;
- numbered task/test IDs, exact commands, RED/GREEN observations, mandatory test execution counts and skipped-test reasons;
- expected and observed positive/failure results, evidence level, reviewer and finding disposition;
- measured performance/resource results, existing failures, limitations and release scope;
- no-go conditions, rollback/recovery result and the accountable accepting person.

An unchanged exact candidate may reuse still-applicable evidence with a documented impact check. Authentication, migrations, core policies, host packaging or changed dependencies invalidate the related evidence and require reruns. Test totals alone never establish coverage.

For every schema change, test a fresh database and an upgrade from the immediately preceding supported schema containing synthetic records. Verify concurrent migration locking, migration fingerprint checks, interruption rollback and old-client/schema incompatibility. Separate migration authority from the runtime database role; the application role must not acquire DDL privileges to make setup convenient. Rehearse recovery before any irreversible data conversion.

New module/interface names below are planning contracts inside the accepted architecture. Reconcile them against the actual checkpoint when the owning milestone starts; preserve already implemented signatures. A public contract or persistence change goes through the ADR gate rather than being justified solely by this file.

### 3.3 Standard commands

Existing root commands, run from the selected repository root:

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe scripts\check_version.py
git diff --check
```

For `pii_redactor/` or `app/` changes also run `scripts/measure_perf.py`. Preserve the 20% time / 15% resident-memory budgets and the known old sanitizer-anchor failure. Use paired unchanged-baseline/candidate runs to explain an existing red anchor; do not hide it or silently move the baseline. Real OCR requires its own measurements because the standard PDF fixture does not exercise OCR.

Enterprise tests run with the separately locked enterprise environment and a real configured PostgreSQL service. The checkpoint's database fixture reads `AIGUARD_TEST_DB_FILE`, an ignored secret-file reference; never print its DSN or file contents. Record the resolved interpreter and service configuration without secrets. M3 must provide a dedicated CI job that fails setup when its required database is missing; ordinary core-only optional skips do not satisfy that job. Root Vitest currently discovers only Extension/Desktop/Demo test directories; enterprise browser-unit tests require an explicit discovery addition and observed nonzero test execution.

Focused test file names in later milestones are **planned files**, not runnable commands today. Create them in the task that owns them. Do not execute deployment, publication or live-provider scripts merely to verify this document.

## 4. Milestone map and dependencies

| ID | Working result | Depends on | Accepted-design stage | Starting status |
|---|---|---|---|---|
| M0 | Reconciled evidence, scope, environments and release decisions | None | Program foundation | Not started |
| M1 | Shared-core compatibility and complete cross-product CI | M0 | Cross-product foundation | Not started |
| M2 | Qualified protection behavior and fresh evaluation protocol | M0; M1 for final cross-surface gate | Cross-product protection | Existing core; acceptance pending |
| M3 | Authenticated staff, durable inventory/notices and usable console | M0 | Stage 1 | Domain checkpoint partial; web/auth open |
| M4 | Verified subject linkage and actual consent/withdrawal | M3 | Stage 2 | Not started |
| M5 | Protected collection, execution boundary and recoverable worker | M3 | Stage 3 foundation | Not started |
| M6 | Retention, holds and evidence-backed disposal/restriction | M4, M5 | Stage 3 completion | Not started |
| M7 | Rights cases, secure delivery and evidence-based closure | M4, M5, M6 | Stage 4 | Not started |
| M8 | Organization governance and reviewed legal applicability | M3; M6/M7 for integrated gate | Stage 5 | Design only |
| M9 | Exact-candidate acceptance per supported client/delivery surface | M1, M2; M3 for enterprise console | Client qualification | Historical evidence only |
| M10 | Hardened deployment candidate and rehearsed recovery | M3-M8; M9 for every included surface | Stage 6 foundation | Not started |
| M11 | Supervised pilot on named organization infrastructure | M10, applicable M9 gates | Stage 6 pilot | Not started |
| M12 | Authorized production launch and repeatable operations | M11 | Stage 6 release/maintenance | Not started |

Execution order is by dependencies, not a blanket numeric lock. Continue M3 from the preserved checkpoint after M0; M1/M2 may proceed alongside it without blocking authenticated inventory delivery. M4 and M5 can then be implemented independently. M8 source/applicability review should start early; its end-to-end closure waits for M6/M7. M9 clients are separate qualifications, not instructions to spawn agents. Nothing auto-resumes the paused implementation.

## 5. Detailed milestones

### M0. Reconcile truth, preserve work and prepare verifiable execution

**Outcome:** An engineer can select the correct checkpoint, run the relevant environments and identify exactly which capabilities the first release will claim.

**Files:** Existing `AGENTS.md`, `ROADMAP.md`, `CODEMAP.md`, `docs/project-status.md`, `docs/architecture.md`, `docs/release-process.md`, `docs/decisions/README.md`; checkpoint handoff on `feat/pdpa-enterprise`; create `docs/enterprise/release-scope.md` and `docs/acceptance/enterprise/M00-baseline.md` during implementation.

**Inputs/outputs:** Consume inspected Git/worktree identities and current runtime manifests. Produce a source-bound capability matrix, environment reproduction instructions and a release-blocker register with owner/needed-by milestone.

- [ ] **M0.1 Preserve and reconcile:** Inspect `git worktree list`, all affected worktree statuses, checkpoint commits, current command/config files and the implementation handoff. Preserve its logical commits and stopped synthetic databases. Identify partial/merged/unmerged work before choosing a continuation branch. Do not start from `main` and discard the existing foundation.
- [ ] **M0.2 Repair current-state contradictions:** Reconcile `0.1.0` source versus archived versions, imported source versus deployed Hosted evidence, current Windows/macOS release targets versus retained Linux helpers, and root versus imported CI coverage. Update operating documents in one focused documentation change; leave historical ADR evidence intact. Acceptance test: every declared surface has one source/contract/support row and an exact evidence reference or an explicit open gate.
- [ ] **M0.3 Reproduce baseline:** Recreate the existing optional enterprise environment from its hash lock. Verify PostgreSQL startup/restart and inspect the unresolved IdP boot issue without altering system-wide Java/Python settings. Rerun the checkpoint's focused tests and then the relevant full gates; distinguish new failures from already red performance anchors.
- [ ] **M0.4 Freeze release assumptions:** Record the first organization, accountable controller/reviewer, departments, staff/subject IdPs, storage/key/backup operators, first external system, supported clients and prohibited uses. Development may use synthetic identities while those are unassigned; M11 cannot. Record proposed performance/recovery targets from Section 7 as proposals until accepted, with no release date invented from task count.

**Gate:** Correct checkpoint selected; reproducible baseline and known failures recorded; every missing external input has an owner and a blocking milestone. Mandatory setup failures stay visible. No evidence or unmerged work is deleted, and no runtime is called accepted from the existence of files.

**Demonstration/evidence:** Another operator follows the written setup and obtains the same bounded baseline classification. Record the commands, hashes and source/environment differences without secrets.

### M1. Establish one protection core without silent contract changes

**Outcome:** Fixes to the canonical engine reach included adapters, while caller contracts and deliberately different trust boundaries remain explicit.

**Files:** Root `pii_redactor/`, `pyproject.toml`, dependency/build scripts; `apps/hosted/core/`, `apps/hosted/sync/`, its Dockerfiles/CI; `packages/amphrang/amphrang/{engine,server,proxy}/`, package metadata/API-surface record; root `.github/workflows/`; planned `tests/test_shared_core_contract.py`, `tests/test_monorepo_ci_coverage.py`, `docs/enterprise/core-compatibility.md`.

**Interfaces:** Root `detect_all`, `sanitize_stateless`, `restore_stateless` and `SessionService` remain canonical. Keep the SDK facade's public signatures, HTTP v2 DTOs and native protocol v1 stable through adapters. New/changed public behavior requires a reviewed contract decision before migration.

The owner has now approved warn/report, direct first-party core consumption with
the larger footprint, distribution name `thai-pii-redaction-core`, and fixed
proxy errors/qualified rollback. Do not re-ask these resolved choices. Their
implementation, complete contract projections and artifact/CI gates remain open;
execute S0-S7 in the Astra/Sol addendum.

- [ ] **M1.1 Inventory differences before removal:** Compare imports, detectors, normalization, span units, supported types, sensitive-data policy, mappings, restoration, retries, PDF and failure DTOs across all three engines. Pin shared synthetic probes and adapter-specific expected results. Test `test_each_adapter_declares_policy_and_contract` rejects an unclassified difference. SDK sensitive-span masking is not silently replaced by the root warn/review policy; resolve the exposed behavior under an ADR before switching that path.
- [ ] **M1.2 Make the compatibility decision reviewable:** Write the smallest adapter/package proposal for consuming the root core in SDK installs and Hosted builds. Include distribution contents, namespace/import compatibility, model assets, dependency isolation and offline install behavior. Independently review the ADR and obtain the required owner decision for public-contract or packaging changes. Continue unrelated enterprise work if this decision remains open.
- [ ] **M1.3 Migrate one adapter at a time:** First write `test_adapter_preserves_source_spans_and_failure_contract`, `test_sdk_mapping_stays_in_explicit_python_boundary`, `test_http_and_mcp_never_expose_mapping` and `test_installed_wheel_contains_required_core`. Then implement the approved dependency/import arrangement. Build/install clean wheels and Hosted images outside the source tree; prove the imported core identity at runtime. Remove a duplicate only after import, entry-point, build, docs and test searches show no live consumer.
- [ ] **M1.4 Close CI blind spots:** Add explicit root, Hosted, SDK and optional enterprise jobs with their own working directories/locks. Use Hosted's existing non-deploy check inventory from `.gitlab-ci.yml`, including frontend tests; do not assume its script-style tests are collected by pytest. Test `test_ci_covers_each_shipped_subtree` and `test_check_pipeline_cannot_deploy`. All affected jobs must actually run and pass, not merely be configured or silently skipped.

**Gate:** Included adapters consume an identifiable canonical core, intentional policy differences are approved/tested, clean install/build succeeds, and complete per-project CI is green. No unresolved sensitive-policy change, unsupported fallback or undeclared engine copy can hide behind the phrase "one core."

**Recovery:** Use only immutable rollback artifacts qualified for the approved privacy/error and compatibility contract. A retained old package is provenance, not permission to restore unsafe provider-error behavior. If no safe fallback qualifies, keep the affected proxy path disabled. Use a tested versioned migration; do not overwrite an earlier artifact or silently force changed contracts on installed clients.

### M2. Qualify protection, restoration, PDF and detector limits

**Outcome:** The release candidate has reproducible protection behavior and a clear supported-input policy, with no claim of complete detection.

**Files:** Existing `pii_redactor/{detectors,anonymizer,leak_guard,session_service,stateless,reverse_mapper,redactor,ingest}/` as applicable; existing privacy/restore/PDF/provider tests; `benchmark/`, `research/yrss2026/`, `research/pdpa-coverage/`; planned `tests/test_release_protection_matrix.py`.

**Interfaces:** Preserve original Unicode source intervals, token/surrogate modes and local lifecycle semantics. Detection/report routes remain inspection paths; provider-bound sanitization enforces the outbound policy. No default model replacement is authorized.

- [ ] **M2.1 Pin end-to-end invariants:** Exercise `detect -> sanitize -> guard -> restore` for Thai/ASCII digits, repeated entities, long/multiline records, field boundaries, width/control/separator variants and overlapping structured units. Add `test_residual_rejects_before_each_provider_attempt`, `test_failed_render_does_not_publish_vault`, `test_expired_or_foreign_token_cannot_restore` and `test_restore_rejects_changed_output_integrity`. Assert no raw values in errors/audit and no partial unsafe answer release.
- [ ] **M2.2 Test failures with observable effects:** Inject model unavailability/incomplete chunks, provider timeout/429/5xx, audit write failure, session expiry/eviction and concurrency. Assert retry limits, immutable masked payload, no fallback, no premature vault publication and cleanup. Verify installed local profiles stay credential-free and do not accidentally activate remote TNER or a provider.
- [ ] **M2.3 Qualify each input mode:** Real text-layer PDF tests must verify covered source boxes and removal of covered text after flattening. Real scanned/hybrid OCR has separate inference, coordinate, cleanup and resource gates. Hosted's Protected Markdown flow does not become PDF redaction/OCR through this milestone. Unsupported media are routed to review or rejected with a clear reason.
- [ ] **M2.4 Measure without reusing closed holdouts:** Preserve all closed blind/held-out files and their historic results. Use development gold/probes for regressions. Before any new generalization claim, preregister a fresh independently authored/labelled evaluation with freeze hashes, type/span/character metrics, negatives, per-category errors and uncertainty; obtain allowed data/reviewer access without copying real content into the repo. Set the candidate's accepted recall/false-positive/block trade-off before disclosure. Do not convert an F2 target into an anonymity or legal guarantee.

**Gate:** Positive and privacy/failure tests pass; every supported input has exact-path evidence and an explicit limitation; performance is measured; unexplained recall, safety or latency regressions block the affected release. Human/real-document quality remains an M11 gate.

**Demonstration:** Show synthetic input review, approved masked outbound payload and exact restoration on the selected delivery path. A fake provider proves orchestration only; actual provider acceptance is recorded separately under M9.

### M3. Finish authenticated authority, registry and staff console

**Outcome:** Two independently authorized staff members can log in, maintain scoped activities/notices, submit and review changes, and inspect minimized audit history through a real application.

**Files:** Resume existing `pii_redactor/governance/{store,commands,authority,permissions,registry,models,errors}.py` and migrations from the implementation branch. Create `app/enterprise/{settings,auth,server,schemas,__main__}.py`, `static/` assets, session migration and packaging entries; extend `vitest.config.js` discovery. Reuse exact Tasks 1-5 from [Stage 1](pdpa-enterprise-stage1.md); planned `tests/test_enterprise_auth.py`, `tests/test_enterprise_api.py`, `tests/enterprise/enterprise_ui.test.js`, `tests/test_enterprise_packaging.py`.

**Interfaces:** Keep `Store(dsn, organization_id)`, `Principal(issuer, subject)`, `Authority.require(...)` and `Registry` commands from the checkpoint. `create_app(settings)` rejects incomplete production setup. Public errors expose only a fixed code/correlation ID. The `/api/enterprise/v1/` namespace is separate from existing HTTP v2.

- [ ] **M3.1 Accept the preserved domain checkpoint:** Reproduce focused PostgreSQL tests for organization binding, one-time enrollment, two-person grants, revocation, revisions, idempotency, audit/outbox rollback, immutable notices and simultaneous writers. Inspect current signatures rather than regenerating completed modules. Verify packaged SQL for the complete registry, not just the earlier foundation wheel.
- [ ] **M3.2 Deliver real staff login:** Resolve the actual local IdP startup problem; configure an exact issuer/client/redirect and synthetic users. Implement Authlib OIDC code flow with PKCE/state/nonce, bounded discovery/key handling and expiring single-use PostgreSQL login state. Tests reject wrong issuer/audience/signature, callback replay, expired state, forged identity headers and URL-controlled endpoints. A mock-only flow leaves this task blocked.
- [ ] **M3.3 Enforce server-side staff sessions:** Store only random session identifiers in HttpOnly/Secure/SameSite cookies; protect mutations with session-bound CSRF and same-origin checks. Tests `test_revoked_membership_denied_on_existing_session`, `test_logout_and_expiry_remove_authority`, `test_admin_cannot_self_approve` and `test_idempotent_replay_rechecks_scope` must pass against the real database. An IdP role claim cannot self-enroll or bypass independent approval.
- [ ] **M3.4 Complete the console:** First add `tests/enterprise/**/*.test.js` to root Vitest discovery and verify the new UI suite runs and fails on a real missing behavior, rather than returning zero collected tests. Implement login/setup guidance, activity/notice forms and detail, review/grant queues and role-filtered audit views. Exercise draft -> submit -> distinct review -> active/rejected with a department-scoped user and denied cross-department access. Provide pending/error/empty/loading/conflict states, Thai labels, keyboard navigation and responsive layout. Browser source assertions alone do not prove this task.
- [ ] **M3.5 Ship the bounded Stage 1 artifact:** Provide actual migrate/enroll/serve/readiness commands, least-privilege migration/runtime roles and an optional enterprise CI environment. Fresh-wheel installation must include SQL/static assets and boot the application without source-tree imports. Restart database and application; verify durable state and session behavior. Independently review the complete branch, run full affected gates and update status to Stage 1 only.

**Gate:** E2 real PostgreSQL/IdP and E3 real browser flows pass, with no staff auth bypass, self-approval, data-scope leak or lost audit write. At least two distinct enrolled principals complete the review demonstration. Stage 1 is usable inventory, not consent or disposal capability.

### M4. Deliver subject linkage, notice proof and actual consent

**Outcome:** A verified synthetic subject can view the exact notice, grant/refuse consent and withdraw it; staff cannot manufacture that act or infer identity from a matching name.

**Files:** Create `pii_redactor/governance/{subjects,consent}.py`, versioned migrations and `app/enterprise/subject_auth.py`, subject routes/UI. Extend scoped registry/permissions and evidence references. Planned `tests/test_governance_subjects.py`, `tests/test_governance_consent.py`, `tests/test_subject_portal.py`.

**Interfaces:** `SubjectLinks.propose/review(...)` bind reviewed source-system identity and versions. `Consent.record_subject_event(subject_actor, command_key, notice_version, purpose_scope, action)` accepts `grant|refuse|withdraw`; `Consent.effective(tx, subject_id, purpose_version)` returns current authority and reasons. Subject actor is a distinct verified type, never a staff principal or browser-declared ID.

- [ ] **M4.1 Prove identity boundaries:** Configure a separate subject OIDC client/audience and approved issuer. Test staff/subject token confusion, a stolen/stale session, unauthorized central-link enumeration, conflicting source IDs and name/phone similarity. Cross-department linkage needs distinct authorized review. A corrected link invalidates dependent approvals; unresolved identity blocks disclosure/destruction.
- [ ] **M4.2 Record genuine acts:** Show immutable notice text/digest and separate purpose choices. Persist append-only events with actor, scope, server receipt time, notice/purpose versions and capacity/representative evidence. Test absent/tampered notice, preselected/fabricated grants, changed purpose, missing representative authority and retry-payload conflicts. Make refusal/withdrawal as accessible as grant.
- [ ] **M4.3 Make withdrawal effective:** Race a grant retry with withdrawal and prove an old grant cannot reactivate authority. Atomically update effective state and propagation tasks; display each recipient's pending/failed/verified state. Enforce purpose/version-bound authority on enterprise processing entry points and recheck it when queued work actually runs; browser flags are never authorization. `test_withdrawal_blocks_affected_processing_without_silent_basis_switch`, `test_queued_processing_rechecks_withdrawal` and `test_failed_propagation_cannot_report_complete` must pass. Retention justified on another reviewed basis stays separately restricted; no blanket erasure is inferred. The local assessment planner advises and does not supply authoritative consent flags. Existing independent Desktop/Hosted tools do not become enterprise-policy-enforced without a separately tested integration.
- [ ] **M4.4 Handle evidenced offline cases:** Case managers can submit verified offline withdrawal/representative evidence for independent review, with source, scope and receipt recorded. This path must never claim a portal click occurred. Run real staff and subject browser sessions plus PostgreSQL restart to verify persistent event history and role separation.

**Gate:** Actual authenticated synthetic subject actions, immutable notices and replay/race protections pass E2/E3. Staff cannot impersonate the subject or widen consent scope. Missing identity/notice evidence and failed propagation remain blocking states.

### M5. Build protected collection and bounded execution infrastructure

**Outcome:** Approved actions can operate on an application-managed synthetic document collection with verifiable primary-store results and recoverable task state.

**Files:** Create `pii_redactor/governance/{collections,evidence,execution,outbox}.py`, `connectors/managed_documents.py`, migrations and `app/enterprise/worker.py`; planned `tests/test_governance_collection.py`, `tests/test_governance_execution.py`, `tests/test_governance_outbox.py`.

**Interfaces:** `Collection.put/read_version(...)` addresses configured collection/opaque document IDs. `Execution.propose/approve/reconcile(...)` binds exact target version, action, expiry and approver. `Worker.run_once(worker_id)` claims leased tasks; connector methods receive only server-resolved targets and approved instructions. This outbox worker is separate from the existing provisional AI-for-Thai queue emulator.

- [ ] **M5.1 Establish protected storage:** Store encrypted managed-document content/version and authoritative control records in the same PostgreSQL transaction boundary required by the accepted design. Keep key-store authority distinct from ciphertext access. Test unauthorized reads, tampered ciphertext, invalid key versions, department scope, evidence size/type limits, missing key service and unauthorized evidence references. Missing protection fails readiness, not plaintext fallback.
- [ ] **M5.2 Make dispatch durable:** Atomically write instruction/audit/outbox; implement bounded leases, ownership, retry classes, attempt limits, terminal/manual states and reconciliation. Tests cover duplicate claims, expired lease, changed idempotency payload, crash before/after commit, DB outage and audit failure. Same immutable instruction retries; unknown outcomes require reconciliation rather than an exactly-once claim.
- [ ] **M5.3 Bound execution authority:** Recheck principal/approver status, exact target revision, action scope and authorization expiry immediately before mutation. Tests `test_target_substitution_denied`, `test_expired_approval_cannot_execute` and `test_replayed_instruction_has_one_primary_outcome` run against real PostgreSQL. Browser-supplied URL/SQL/path never selects a connector target.
- [ ] **M5.4 Prove recovery before destructive use:** Build a synthetic collection snapshot, execute approved reversible/restriction/correction operations and restore into quarantine. Test suppressed/restricted objects cannot become readable before reconciliation. Expose pending, running, verified, failed and unknown outcomes in the staff UI; no dispatch-only success message may close an obligation.

**Gate:** E2 worker/database/crash/restart tests and the staff-facing action path pass. Protected storage is operational. Primary mutation/evidence is atomic for this connector only. Real-data destructive execution is disabled pending M6 and M10-M12 acceptance/authority.

### M6. Complete retention, holds and disposition

**Outcome:** Staff can review due assets, impose effective holds, approve scoped actions and distinguish primary-store completion from remaining backup/processor obligations.

**Files:** Create `pii_redactor/governance/{retention,holds}.py`, scheduler and migrations; extend execution/managed-document adapter and staff UI. Planned `tests/test_governance_retention.py`, `tests/test_governance_hold_races.py`, `tests/test_restore_suppression.py`.

**Interfaces:** `Retention.propose_due(as_of)` produces exact revision-bound proposals. `Holds.request/release(...)` returns `pending|effective|post_action_review` with receipt/commit times. Worker checks these records under the managed-asset guard lock inside the mutation transaction.

- [ ] **M6.1 Make policy executable:** Record purpose-specific trigger, due rule, justified restrictions, copies, processors, hold reason/expiry/review and reviewer. Tests reject missing trigger/evidence, invalid policy changes and activation by a proposer alone. Scheduler proposes; it does not silently delete because a date passed or consent was withdrawn.
- [ ] **M6.2 Serialize hold versus action:** In real concurrent PostgreSQL sessions, test hold commits before action, action commits before hold, hold arrives during locked transaction, stale approval and changed target/policy. A previously committed effective hold prevents action. A late hold returns actual post-action status and urgent review; it never claims an irreversible action was prevented.
- [ ] **M6.3 Verify and reconcile each target:** Use distinct approver and bounded instruction; recheck current policy, hold, consent/rights restrictions, approval and exact target under the asset guard, then perform managed mutation plus audit/outbox/outcome in one transaction. Kill/restart worker around commit and reconcile. Verify primary state from an independent connection. Corrupted evidence, withdrawn authorization or unresolved action outcome blocks closure.
- [ ] **M6.4 Track the entire obligation:** Maintain separate statuses for primary content, derived copies, processors, replicas/WAL/physical retention and backups. A primary logical removal is not physical erasure. Restore a synthetic pre-disposal backup into quarantine, replay suppression/withdrawal/restrictions and prove disposed content is not served. Outside systems remain named manual tasks unless an equivalent conditional/fencing boundary is accepted.

**Gate:** Deterministic race and crash tests pass E2; E3 UI correctly distinguishes pending/effective/post-action holds and partial disposition. Backup/processor uncertainty remains visible. No blanket "deleted everywhere" label is available from a primary-delete result.

### M7. Deliver rights cases and controlled fulfilment

**Outcome:** A case manager can receive a request, verify authority, discover scoped data, obtain review, execute permitted work and deliver or refuse with complete evidence.

**Files:** Create `pii_redactor/governance/{rights,delivery}.py`, case/delivery migrations and staff/subject UI; reuse `pii_redactor/dsar.py` for discovery advice and `pdpa_lifecycle.py` for advisory planning. Planned `tests/test_governance_rights.py`, `tests/test_rights_delivery.py`, `tests/test_rights_closure.py`.

**Interfaces:** `Rights.receive/verify/plan/review/close(...)` enforce explicit state transitions/revisions. `Delivery.issue(case_id, approved_export_version)` creates an audience-bound, encrypted, expiring artifact; `Delivery.consume(subject_actor, delivery_id)` rechecks identity, expiry and revocation.

- [ ] **M7.1 Preserve intake and clocks:** Store original receipt/channel, completeness decisions, identity/representative review, right types, legal/source versions and applicable deadlines/extensions/refusals. Tests separate access and erasure clocks, incomplete requests, changed scope, withdrawal, justified refusal and unknown legal applicability. Do not invent a single 30-day rule for all rights.
- [ ] **M7.2 Plan scoped fulfilment:** Discover only authorized assets/links; review third-party data before disclosure. Corrections/restrictions/erasure use exact approved target versions and M5/M6 execution. Tests cover identity mismatch, mixed-person documents, cross-department enumeration, changed subject links and unsupported external systems. Every unsupported system gets an accountable manual evidence task.
- [ ] **M7.3 Deliver safely:** Build purpose-scoped exports with third-party redaction, controlled encryption, expiring download authority and verified receipt/delivery state. Test wrong subject, link guessing, replay/expiry, revoked case authority, export revision changes, partial downloads and browser caches. No public unbounded file URL or raw export in audit/console logs.
- [ ] **M7.4 Enforce closure:** `test_case_cannot_close_on_worker_dispatch`, `test_backup_or_processor_pending_blocks_full_erasure`, `test_partial_delivery_remains_partial` and `test_justified_refusal_needs_reviewed_evidence` must pass. Run one end-to-end case each for access, correction, restriction, erasure and refusal through staff/subject browsers and restart recovery.

**Gate:** E2/E3 identity, execution, third-party protection, delivery and closure paths pass. Every in-scope obligation has verified outcome or a documented approved exception. Domain tests do not certify the organization's legal decisions.

### M8. Complete organization governance and legal-control traceability

**Outcome:** Reviewers can manage the wider organization obligations and trace each applicable control to current source, accountable decisions, implementation and operational evidence.

**Files:** Create `pii_redactor/governance/{processors,transfers,incidents,assessments,responsibilities,policy_register}.py` and corresponding records/routes/UI/tests. Reuse `pii_redactor/breach.py` as triage advice. Create `docs/enterprise/legal-control-register.md`; extend source reports only when their described facts change.

**Interfaces:** Each register uses draft -> submitted -> independently reviewed -> active/rejected/superseded transitions, exact revisions and scope. `LegalControls.release_findings(release_scope)` returns unresolved/required/not-applicable decisions with source/version, reviewer and evidence, never an automatic compliance score.

- [ ] **M8.1 Review authoritative applicability:** A qualified organization reviewer checks current Thai primary instruments and sector duties before real-person use. Cover every release-control row in the accepted design, including security, breach notification, processor records and Section 29 safeguards whose primary review remains open. Record source URLs/bytes/digests, effective/amended versions, applicability reasons and review date; search snippets alone do not close a legal-source gate.
- [ ] **M8.2 Deliver processor/transfer controls:** Record agreements/instructions, subprocessors, purposes, actual destination/access, safeguards/exception evidence, expiry and review. Tests reject a foreign-cloud label as complete transfer evidence, an unreviewed agreement, changed destination and a stale safeguard. Approval controls authoritative processing activation and surfaces unresolved obligations; no arbitrary automated legal verdict.
- [ ] **M8.3 Deliver incident and responsibility workflows:** Record awareness time, uncertainty, risk review, conditional clock/notification tasks, actual evidence and escalation. Cover DPO/responsibility applicability, independence/conflicting duties, policies, training/review attestations, risk assessments and complaints. Tests reject automatic exemption from a single size/SME checkbox, admin-as-legal-approver and closure based on a notification draft. External sending/submission stays a separately authorized action.
- [ ] **M8.4 Close traceability across modules:** Link controls to M3 activities/notices, M4 consent, M6 retention and M7 cases. Run permission-specific positive/negative workflows in the browser. `test_release_register_rejects_unknown_required_applicability` and `test_policy_revision_invalidates_affected_approval` must pass. If an area is genuinely inapplicable, retain the reason, source and reviewed decision rather than deleting the control.

**Gate:** All in-scope controls have reviewed applicability, accountable owner and implemented/operational evidence; unresolved mandatory sources or exceptions prevent release. This gate reports evidence and remaining risk, not certification of complete PDPA compliance.

### M9. Qualify every included client and delivery surface

**Outcome:** Each claimed client works from its exact install/build/image on its declared host, with honest availability and privacy statements.

**Files:** Existing `desktop/`, `extension/`, `office-addin/`, `apps/hosted/`, `packages/amphrang/`, demo/CLI/API paths and associated acceptance/build scripts. Follow subtree instructions and [functional acceptance](../acceptance/README.md); do not create a competing Hosted redesign brief.

**Interfaces:** Preserve client-specific session authority: broker handles for Desktop/Extension, existing opaque Office HTTP session boundary, explicit Python-only SDK mapping boundary, and request-scoped Hosted lifecycle. Do not widen one surface because another supports it.

- [ ] **M9.1 Desktop and Extension:** Run JS/Rust gates and exact Windows/macOS package install/start/mask/restore/isolation/disposal/upgrade/restart/uninstall tests. Verify production-ID Native Messaging, missing/invalid companion, wrong origin, tab/panel navigation, browser restart and simultaneous Desktop use. In-page raw DOM exposure and stronger side-panel entry must remain visible. Excluded Linux builds remain unclaimed. Unpacked exact-ID testing does not prove Web Store install/publication.
- [ ] **M9.2 SDK, CLI and API:** Build/install clean wheel/sdist with each promised optional extra. Verify stable facade, Session lifetime/clear, batch errors, proxy streaming/cancellation and MCP schemas/no-mapping boundary; test disconnects, malformed upstream and residual blocks. Run the SDK's own tests/lint/lock/API-surface checks and root CLI/API tests. Do not claim `pip install amphrang` availability before authorized PyPI publication.
- [ ] **M9.3 Hosted:** Run its complete existing check inventory, built-image source parity and public-route/CSP/auth/approval/queue/protected-payload/version contracts. Test preview changes invalidate approval, timeout/cancellation, restoration safety, explicit capacity/unsupported-PDF failures and value-free logs. Separate stub-provider, authorized live-provider, staging reverse-proxy and actual platform gates. Only owner-authorized credentials/quota and exact immutable candidates enter live checks. Do not invoke the deploy script as a check or describe historical `3.0.2` evidence as current-source acceptance.
- [ ] **M9.4 Office:** Run manifest/type/unit/build gates first. On exact host/package bytes exercise Word table and missing-key/provider/expired-session cases; Excel changed-value/formula cancellation and Copy-only provider flow; PowerPoint selection isolation, missing API 1.5 and Copy-only flow. Keep release manifest Word-only until the Excel/PowerPoint and exact promoted multi-host activation gates pass. Resolve or explicitly exclude the unaccepted fixed-port process-identity boundary before a production claim; a transport redesign needs its own ADR.
- [ ] **M9.5 Enterprise console and product usability:** Complete real browser staff/subject workflows on declared browsers, desktop widths 1280/1440 and mobile widths 360/390, plus relevant Hosted-specific viewport rules. Verify Thai typography, contrast, focus order/restoration, labels, keyboard-only actions, reduced motion, loading/empty/error/permission/conflict/session-expiry states and recovery without double submission. Use synthetic screenshots only. Independently review sensitive flows and applicable Hosted art/frontend/UX requirements.

**Gate:** A per-surface manifest links exact bytes, host/OS/browser, source identity, support scope and E3/E4 results. Only passed surfaces appear as available. One excluded optional storefront does not block an enterprise-only release, but its download/install/compatibility claims remain disabled.

### M10. Harden deployment and prove recovery before a pilot

**Outcome:** An exact private staging candidate survives restart, outage, backup restoration, key changes and tamper detection without re-enabling disposed/restricted data.

**Files:** Create enterprise deployment/runbook assets under `app/enterprise/`, `docs/enterprise/` and the selected deployment directory; extend migrations/readiness, package/image manifests and dedicated CI integration jobs. Planned `tests/test_enterprise_readiness.py`, `tests/test_enterprise_recovery.py`, `tests/test_audit_checkpoint.py`.

**Interfaces:** Separate process liveness from DB/schema/enrollment/IdP/key/audit/restore readiness. Add explicit operator commands for backup validation, restore quarantine and checkpoint verification. Production mutations are disabled while mandatory integrity/recovery prerequisites fail.

- [ ] **M10.1 Bind the artifact and deployment:** Build from a clean immutable source with locked dependencies and declared model/schema/assets; record software inventory, image/package digests and rollback compatibility. Configure exact TLS origin/proxy trust, secure cookies, body/rate/concurrency limits, least-privilege network/database/storage roles and protected secret files. No broad CORS or development auth bypass in production configuration.
- [ ] **M10.2 Prove audit integrity:** Publish minimized chain checkpoints to an independently controlled sink with separate credentials/access and retention. Test missing/reordered/altered events, a truncated DB chain, unreachable sink and divergent restored checkpoint. Define safe checkpoint lag and fail readiness on exceeded/unverifiable integrity; a local hash chain alone is only local tamper evidence.
- [ ] **M10.3 Rehearse failure and recovery:** Run backup+restore into an isolated/quarantined target; verify migrations, roles, consent/withdrawal, active holds, case/export revocation, suppression and outbox reconciliation before serving. Rehearse application/worker kill, disk-full, unavailable DB/IdP/key/sink, interrupted migration and safe rollback. Test that an older binary cannot run against an incompatible schema; use verified forward repair/restore rather than a blind downgrade.
- [ ] **M10.4 Rehearse key/session operations:** Rotate test keys using versioned decrypt/read/re-encrypt policy and verify older necessary content remains recoverable. Revoke staff/subject sessions and execution approvals as required. Drill loss/recovery with distinct key/ciphertext authorities. Do not rotate a real production credential during a synthetic drill.
- [ ] **M10.5 Measure and review:** Run the Section 7 workload on declared hardware and record p50/p95, failure rate, DB locks/storage growth, worker throughput/backlog age and resource ceilings. Independently review auth, scope, transactions, execution/holds, exports, logs, dependencies and deployment boundaries. Every confirmed critical/high-impact blocker requires reproduced RED/GREEN evidence and re-review of affected scope.

**Gate:** E4 exact staging/TLS/IdP/storage and independent sink pass; recovery meets the accepted RPO/RTO; no data is served before post-restore suppression/reconciliation; measured performance fits the frozen acceptance targets. No unresolved critical privacy, authorization, loss-of-data or integrity defect. Production environment access is not implied by this plan.

### M11. Run a supervised organization pilot and first external integration

**Outcome:** Named staff can complete representative work on the actual intended environment, with reviewed legal applicability, observed operational support and a justified deployment decision.

**Files:** Create `docs/enterprise/pilot-protocol.md`, `docs/acceptance/enterprise/M11-pilot.md`, training/support material and the exact first connector/manual-task adapter configuration. Adapt existing connectors only after source-system authority and evidence requirements are known.

**Interfaces:** Pilot protocol pins users/roles, departments, environment, data permissions, intended uses, workload, success/no-go criteria and release scope before observation. First external system is named and allowlisted; automatic irreversible execution is disabled unless its tested conditional/fencing guarantees satisfy the accepted design.

- [ ] **M11.1 Clear organizational prerequisites:** Obtain explicit owner authority for the pilot/environment and any real data; organization reviewer confirms applicable controls, retention, processor/transfer terms and notice handling. Assign two distinct approvers, service operator, incident lead, key/backup custodians and support route. Validate real TLS/IdP/source-system identities and safe rollback independently of local synthetic setup.
- [ ] **M11.2 Run scripted user acceptance:** With synthetic data first, ordinary staff complete inventory approval, actual subject consent/withdrawal, holds, due disposal, one access/correction/restriction/erasure/refusal case, incident escalation and review queues. Include revoked account, conflicting identity, interrupted work, manual fulfilment failure and expired delivery. Record task completion, assistance required, mistakes and unresolved states; do not replace participant behavior with agent-only browser automation.
- [ ] **M11.3 Assess representative document quality:** Under approved access, qualified independent reviewers label a representative permitted set, adjudicate disagreement and freeze the candidate/evaluation protocol before scoring. Report per-type/span/character errors, unsupported modalities, false positives and blocking burden with uncertainty. Keep raw real content out of Git/general artifacts and prohibit tuning on the disclosed holdout. If quality misses the pre-agreed intended-use threshold, narrow/review the workflow or fix and evaluate a fresh candidate; never relabel the miss as success.
- [ ] **M11.4 Accept the first external system:** Verify scoped discovery/export/manual fulfilment and outcome evidence on the real authorized system. Test target changes, auth revocation, partial failure, retry and reconciliation. If irreversible fencing is absent, keep human execution plus independent evidence review; this can pass only the documented manual mode, not an automatic-deletion claim.
- [ ] **M11.5 Observe operations and decide:** Use the agreed observation window, exercise alert/support/incident handling and one real-environment synthetic recovery drill. Summarize task outcomes, safety/quality/capacity results, unresolved obligations and operator training. Accept, extend or reject the pilot explicitly; queueing tasks and a green HTTP health endpoint do not substitute for outcome evidence.

**Gate:** E5 pilot report accepted by service owner and qualified organization reviewer, with no unresolved mandatory control, unmeasured intended-use quality or severe privacy/operational defect. Any retained limitation has an enforced scope restriction and accountable acceptance. Pilot approval does not itself publish a release or execute a real erasure.

### M12. Authorize production launch and sustain acceptance

**Outcome:** An explicitly authorized exact release is operable, recoverable and supportable; future changes repeat the relevant gates rather than inherit readiness forever.

**Files:** Update `docs/project-status.md`, `ROADMAP.md`, release/runbooks, support/privacy/terms pages, release-specific changelog/version targets and exact acceptance manifest. Update `VERSION` only through `scripts/bump_version.py` in a release-preparation task. Keep Hosted/SDK version sources and deployment identities explicit.

**Interfaces:** A release manifest binds source/tree, artifact/lock/model/schema/config digests, required gates, approved included/excluded surfaces, known limitations, approvers and rollback/recovery references. Promotion consumes that exact manifest, not a mutable branch name or a historical test total.

- [ ] **M12.1 Close release checks:** Reverify current primary legal/source applicability with the organization reviewer where required, exact dependency advisories/license inventory and unresolved defects. Require all CI jobs and included M9-M11 gates; metadata consistency alone is insufficient. Resolve conflicting old release instructions identified in M0 before using release automation. Do not infer production readiness solely from selecting `1.0.0`.
- [ ] **M12.2 Prepare concrete promotion:** Assemble immutable candidate artifacts, checksums/provenance, migration/backup/rollback steps, signed updater metadata where applicable, explicit unsigned/notarization status and release notes. Rehearse staging promotion from these exact bytes. Prepare store/PyPI/Office publication materials only for separately included and accepted distribution channels.
- [ ] **M12.3 Obtain action-specific authority and launch:** Present the exact candidate, evidence, remaining restrictions and rollback plan for owner approval. Only after authorization perform deployment/publication/submission. Verify live health/source/contract identity, staff/subject login, permissions, synthetic critical workflows, logs/resources and recovery controls; halt promotion or use the tested rollback path when the exact live gate fails. Never run a real destructive fulfilment as a release smoke.
- [ ] **M12.4 Operate and requalify:** Assign on-call/incident and customer-support ownership, alert on queue age/failures, integrity lag, key/session expiry, resource exhaustion and backup age. Review privileged access and unresolved consent/rights/retention tasks routinely. Rehearse restore/key operations on an agreed schedule and after material infrastructure changes. Record security patch policy, legal/model/dependency change review, evidence expiry and requalification triggers.

**Gate:** Exact production acceptance and owner launch sign-off are recorded, rollback/recovery is usable, support is staffed and only actually accepted capabilities are advertised. A future source/model/schema/IdP/connector/host change reopens affected gates. New real-data actions and outward notifications still require their appropriate organizational authorization.

### Focused verification inventory

This is a minimum task-to-suite map, not a replacement for the task assertions above or the complete affected-lane gate. Run from the owning checkout/project root with its recorded locked interpreter; new suite files are created with the owning task. For enterprise suites, a dedicated integration run must report actual real-database tests executed and zero environment-caused skips. Browser/host checks use the real-path protocol rather than a pytest-only substitute.

| Milestone | Focused suites or protocol | Required observed result |
|---|---|---|
| M0 | Existing `tests/test_governance_store.py`, `tests/test_governance_authority.py`, `tests/test_governance_registry.py` on implementation branch | Checkpoint reproducible; environment/old failures classified; PostgreSQL restart state intact |
| M1 | Planned `tests/test_shared_core_contract.py`, `tests/test_monorepo_ci_coverage.py`; each subtree's full existing checks | Approved adapter compatibility and every included subtree actually tested |
| M2 | Existing `tests/test_leak_guard.py`, `tests/test_session_lifecycle.py`, `tests/test_provider_orchestration.py`, `tests/test_structured_input_recovery.py`, `tests/test_step12_redact_pdf.py`; planned `tests/test_release_protection_matrix.py` | Negative controls block before side effects; source spans/restoration and declared inputs preserved |
| M3 | Existing governance suites; planned `tests/test_enterprise_auth.py`, `tests/test_enterprise_api.py`, `tests/test_enterprise_packaging.py`, `tests/enterprise/enterprise_ui.test.js`; real IdP/browser | No auth/scope bypass; durable two-person registry path works from installed package; UI tests actually collected |
| M4 | Planned `tests/test_governance_subjects.py`, `tests/test_governance_consent.py`, `tests/test_subject_portal.py`; real subject/staff browser sessions | Genuine scoped acts; withdrawal/replay/linkage failures remain denied after restart |
| M5 | Planned `tests/test_governance_collection.py`, `tests/test_governance_execution.py`, `tests/test_governance_outbox.py` | Protected content, bounded instructions, atomic audit and reconciled crash outcomes |
| M6 | Planned `tests/test_governance_retention.py`, `tests/test_governance_hold_races.py`, `tests/test_restore_suppression.py` | Exact race ordering honored; no false global-erasure claim or restored-data exposure |
| M7 | Planned `tests/test_governance_rights.py`, `tests/test_rights_delivery.py`, `tests/test_rights_closure.py`; staff/subject end-to-end cases | Correct scoped delivery and evidence-based partial/complete/refused states |
| M8 | Planned `tests/test_governance_processors.py`, `tests/test_governance_transfers.py`, `tests/test_governance_incidents.py`, `tests/test_governance_responsibilities.py`, `tests/test_governance_assessments.py`, `tests/test_legal_control_register.py`; qualified source review | Reviewed applicability, no unauthorized external action and traceable control evidence |
| M9 | Existing lane commands and exact host/package/provider/browser acceptance in `docs/acceptance/README.md` plus subtree protocols | Only each actually exercised host/surface is supported |
| M10 | Planned `tests/test_enterprise_readiness.py`, `tests/test_enterprise_recovery.py`, `tests/test_audit_checkpoint.py`; staging restore/rotation/load protocol | Mandatory integrity failures stop readiness; measured recovery/capacity meets frozen targets |
| M11 | Preregistered pilot, representative annotation and first-system acceptance protocols | Named human participants/reviewers accept outcomes within agreed scope |
| M12 | Existing version/release gates, exact release manifest and authorized live smoke/runbook protocol | Promoted bytes match reviewed candidate; live operation and recovery/support accepted |

Example command **after M3 has created these files**, with the separately locked enterprise interpreter resolved locally:

```powershell
# Run in the activated enterprise environment; never print its secret settings.
python -m pytest tests/test_enterprise_auth.py tests/test_enterprise_api.py tests/test_enterprise_packaging.py -q
npm run test:js -- tests/enterprise/enterprise_ui.test.js
```

The expected result is PASS for every required assertion with real mandatory dependencies available. Follow it with the full lane gate, actual OIDC/browser acceptance and package check; passing this single command does not complete M3.

## 6. Accepted-design coverage and stop conditions

| Design requirement | Owning milestone | Verification that closes it |
|---|---|---|
| Single organization, durable scope and two-person authority | M0, M3 | Real PostgreSQL + distinct staff OIDC users, immediate revocation and cross-department denial |
| Actual subject act, immutable notice and reviewed linkage | M4 | Separate subject session, notice tamper/replay/race and representative tests |
| Atomic records/audit/outbox and bounded worker | M3, M5 | Audit-failure rollback, lease/crash/duplicate reconciliation and independent DB verification |
| Storage/key protection and minimized evidence | M5, M10 | Real encrypted store, distinct authority, tamper/rotation/readiness drills |
| Effective holds and irreversible-action boundary | M6 | Concurrent before/during/after serialization tests; conditional remote execution or manual mode |
| Backups/processors/derived copies and restore suppression | M6, M10 | Per-copy obligations and quarantined restore/reconciliation before serving |
| Rights clocks, identity, third-party protection and delivery | M7 | End-to-end access/correction/restriction/erasure/refusal with blocked premature closure |
| Processor/transfer/DPO/security/incident/review/complaints | M8 | Current source/applicability record and role-specific reviewed workflows |
| Open categories, unsupported modalities and quality limits | M2, M8, M11 | Fail/review routing plus preregistered independent representative evaluation |
| Independent checkpoints, operations and first real system | M10, M11 | Actual sink/TLS/IdP/recovery/connector or reviewed manual evidence |
| Exact artifacts and truthful distribution | M9, M12 | Declared host/client acceptance, immutable manifest and authorized live promotion |

Stop the affected transition on identity/scope uncertainty, unexplained measured regression, unresolved hold/target revision, missing mandatory audit/outbox, unknown execution outcome, broken checkpoint/restore, unsupported claimed input or unknown required legal applicability. Continue independent local tasks only if they do not depend on that failed gate. Do not weaken a guard, hide a failure, silently change a legal basis or shift a baseline to make the milestone green.

Product-direction forks and expensive public-contract/architecture/data decisions require the owner under `AGENTS.md`. Routine implementation choices inside the accepted design do not. Missing organization/IdP/storage/external-system details block M11 and specific affected integration gates; they need not prevent synthetic local work.

## 7. Capacity, recovery and scheduling

These are planning acceptance proposals, not measured performance, production SLOs or already approved operating promises. Confirm or replace them in M0/M10 before the corresponding test; record changes before observing candidate results.

Engineering owns implementation and automated/local evidence for M0-M10. A separate qualified technical reviewer owns independent findings. The organization's privacy reviewer owns applicability/legal decisions in M4/M6-M8/M11; the service operator owns infrastructure/recovery acceptance in M10-M12; the owner accepts release scope, pilot and outward actions. Assign actual people and backups in M0/M11, preserve separation of duties, and do not let an agent self-sign an organizational or independent review gate.

| Measure | Proposed initial gate | Evidence required |
|---|---|---|
| Registry/case/consent workload | 20 concurrent staff, 10,000 synthetic records, as proposed in the accepted design | Declared hardware/config, mixed scoped reads/writes and p50/p95/error/resource/storage results |
| Interactive registry response | p95 read <= 500 ms and write <= 1,000 ms, excluding IdP/provider/document processing | Measured end-to-end server timing at the frozen workload; disclose contention and cold behavior |
| Unexpected request failure | <= 1% over a defined 30-minute synthetic workload; expected authorization/conflict rejections reported separately | Request counts, latency histogram, failure classes and no hidden retries |
| Worker capacity | Sustained completion rate above the declared arrival rate; backlog drains after outage without duplicate primary effects | Measured action mix, queue age/throughput, reconciliation and resource ceiling |
| Database recovery | Proposed RPO <= 15 minutes, RTO <= 4 hours for the pilot scope | Timed restore into isolated target, verified checkpoints, suppression, key access and actual recovered timestamp |
| Pilot observation | Proposed 5 working days after scripted acceptance | Named participants, support coverage, tasks/defects and organization-approved duration |
| Privacy/authority invariants | Zero observed unauthorized disclosure/action or successful unsafe-release regression in required tests | Named adversarial tests with exposure-free evidence; no universal zero-risk claim |

Provider, OCR, large export and remote-system latency have separate queues/timeouts and capacity evidence. Do not apply the interactive metadata response target to them or use a successful one-page PDF to advertise an unmeasured page/time limit. No availability percentage is promised before the actual environment and operator support are accepted.

Estimate work after M0 using remaining tasks rather than total milestone count: review each task's database/IdP/host dependencies, implement one complete vertical slice, measure actual throughput, then estimate a range and contingency. Re-estimate after M3, M6, M9 and M10. A calendar date cannot overrule an unmet safety or real-host gate.

## 8. Current execution sequence

1. Follow the [Astra/Sol addendum](2026-11-02-astra-sol-execution-review.md) from
   the clean checkout. S0/S1 preserves the prerequisite/proxy candidate with local
   Windows/Python 3.13 artifact evidence and a clear independent review. Continue
   from S2; do not rebuild the completed M3 staff path.
2. Finish actual SDK/Hosted canonical consumption and full adapter/artifact checks.
   Keep M0/M1/M3 acceptance held while executing CI and controlled performance are
   missing. The owner's performance hold and GitHub privacy purge remain in force.
3. Rebind M2/M3 regression, installed package and real local browser/IdP/database
   evidence to the combined exact candidate.
4. Build M4-M8 as complete subject-to-managed-document workflows using the accepted
   authority, transaction and recovery design, then qualify M9-M12 in dependency order.
5. Maintain separate implemented/verified/accepted facts and explicit owner inputs.
   Prepare concrete pilot/release actions before the required final authorization.

## 9. Planning-document verification

This plan is ready to execute only as a plan: verify its local links, repository paths, checkpoint identities and spec coverage. Uncreated files/commands are explicitly planned. The author must distinguish document validation from product test execution. No runtime milestone is passed by writing this file.

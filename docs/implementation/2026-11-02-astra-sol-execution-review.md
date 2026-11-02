# Astra Review and Sol 6.1 Execution Plan

> **For agentic workers:** Use `superpowers:executing-plans`. The owner subsequently
> requested parallel S and M units with disjoint file ownership, then integration.
> Every unit has a fresh independent
> adversarial subagent review. Reuse the accepted master plan and current code;
> this addendum does not authorize deployment, publication or real-data actions.

**Goal:** Complete the existing M0-M12 program as a usable single-organization,
self-hosted PDPA system with qualified AI Guard delivery surfaces, leaving only
explicit owner/participant decisions and actions to those people.

**Architecture:** One authored protection core under `pii_redactor/`, consumed by
adapters with explicit configuration and trust boundaries. A separate enterprise
FastAPI application uses PostgreSQL authority, governance and encrypted managed
documents; reversible local redaction mappings remain in memory. Shared code does
not require a shared process, server or deployment.

**Tech stack:** Preserve Python/FastAPI, PostgreSQL 18, psycopg/Authlib and the
existing UI, Tauri, MV3/native broker and Office adapters. No new frontend
framework, ORM, message broker, model or multi-tenant service is selected here.

**Spec:** [Master M0-M12 plan](aiguard-production-milestones.md),
[accepted enterprise architecture](../decisions/2026-10-31-pdpa-enterprise-control-plane.md),
[accepted shared-core decision](../decisions/2026-11-02-shared-core-compatibility.md),
[release scope](../enterprise/release-scope.md), and root `AGENTS.md`.

**Review date:** 2026-11-02. This is an execution addendum to the master plan,
not a replacement architecture or a claim that any unaccepted milestone passed.

**Independent plan gate:** CLEAR on 2026-11-02 after one completed read-only
Astra review. No material objection remained before Sol 6.1 starts S0. The
parent checked the report against the accepted decisions, current plans and
MCP success fields, reconfirmed HEAD `6f1e63f` and `origin/main` `38b235f`, and
matched all 38 runtime/configuration/test fingerprints recorded before review.
This is plan acceptance only. It adds no runtime, artifact, performance, CI,
main-integration or release acceptance; all corresponding holds remain open.

## 1. Direction confirmed

The accepted direction is coherent and should continue:

1. Deliver the complete organizational workflow: authoritative staff and subject
   identity, activities/notices, actual consent/withdrawal, managed collection,
   reviewed execution/holds/retention, rights fulfilment, governance and recovery.
2. Keep one authored protection core. SDK/Hosted canonical consumers are now
   implemented in source; shared module names alone do not prove installed
   identity or exact-image acceptance.
3. Keep each delivery boundary explicit. Local broker clients, Python callers,
   MCP hosts, Hosted requests and the enterprise database have different data
   lifecycles and authority. A result from one does not qualify another.
4. Preserve the finished frozen YRSS research/presentation lane. Current product
   changes do not inherit that study's score, nor require late changes to it.

The current parallel S2-S6/M4-M6 source wave needs a freeze, independent
integration review and reproducible combined qualification. Preserve the now-green
enterprise source gate, close remaining SDK and artifact/image/M3/CI gates, then complete absent
M7/M8 and unfinished operational recovery through complete user workflows.
Additional model training or detector expansion is not the next dependency.

### Owner decisions already settled

Do not ask these again:

- One self-hosted organization, multiple scoped departments; not a SaaS claim.
- SDK sensitive handling moves to warn/report with a versioned migration.
  There is no automatic-sensitive-masking compatibility exception.
- SDK consumes the first-party core directly and accepts its broader installed
  namespace/dependency footprint. The core distribution is
  `thai-pii-redaction-core`; imports remain `pii_redactor`/`app`.
- Proxy errors are fixed and value-free, including HTTP 200/SSE/late failures.
  Operational rollback requires qualified artifacts; otherwise keep that path
  disabled.
- M3 stays held until controlled-environment performance measurement. No timing
  exception or baseline update was approved.
- Screenshot-only history cleanup and public visibility were approved. The owner
  accepted disclosed retained-image risk and the repository is public.
  Server-side purge remains unconfirmed; do not reintroduce a visibility hold.
- Anti-jobs means a fresh independent adversarial subagent at each reviewable
  stage. AI review is engineering evidence, not independent human/legal review.

## 2. Authoritative working state

Use **`C:/Users/teera/dev/thai-pii-redaction/.worktrees/pdpa-enterprise-clean`**.
Its implementation branch is `feat/pdpa-enterprise`, observed HEAD
`85f1c32ecd565973fce99e753299f5d459b0c19a` before the uncommitted parallel wave.
The plan-review refs `6f1e63f`/`38b235f` above are historical. Revalidate current
refs before commands; do not substitute an old clone's local `main`.

The original canonical/design checkout and old implementation checkout retain
private old history and owner work. Their normal push URL is deliberately
disabled. Never push them, their bundles or replacement refs into the clean repo.
The T3 project view may still name the old design branch; all execution commands
must explicitly select the clean checkout above.

### Observed evidence, not accepted completion

| Area | Current evidence | Remaining gate |
| --- | --- | --- |
| M0 | Checkpoint reconciliation and privacy rewrite preserved; clean refs verified | Every required CI job must execute green |
| M1 prerequisites | S0/S1 Windows/Python 3.13 artifacts qualified for their exact earlier candidate | Rebuild/rebind artifacts after the current wave freezes |
| S2-S5.1 | Nine text profiles; SDK facade/Session/batch/CLI/HTTP/MCP/proxy canonical; exact dependency pin and 29 internal aliases; sensitive-span copy removed | Final full SDK/root gates, paired wheels/sdists, outside-source installs and exact image/CI qualification |
| S6 | Hosted copies removed; offline supplied-wheel/dependency/model preparation and source identities; review safety/scanner fixes have focused follow-up evidence | Independent integration review, complete artifact/image/no-egress/CI/platform qualification |
| Proxy dependency floor | 143 focused tests passed with locked AnyIO 4.14.2 and isolated 4.4.0 | Declared Python/platform/host matrix still requires qualification |
| Development regression | Gold-v4: 252 synthetic documents/648 annotations; control/candidate metrics unchanged, all 313 NER chunks executed | Not fresh blind/generalization evidence; new types lack labelled gold coverage |
| M3 | Earlier real synthetic PostgreSQL/IdP/browser, installed-wheel and restart evidence | Controlled performance, executing CI and rebinding to the new candidate |
| M4-M6 | Subject consent, protected managed execution, retention/holds and Thai caller paths implemented/local; corrected mandatory enterprise gate 298 passed/0 failed/0 skipped | Final global gate and fresh real IdP/browser/runtime-role/restart/artifact evidence pending |
| M7/M8 | Accepted design; rights/case/delivery and organization control-record implementations absent | Implement and qualify complete workflows with qualified organization inputs |
| M9-M12 | Historical surface evidence; partial M10 collection quarantine/reconciliation | Every declared storefront's exact artifacts/hosts; whole-DB recovery/checkpoints/rotation/operator/drills; real people and action-specific authority |
| YRSS | Reviewed 28-file packet, poster/slides/scripts/40 evidence-linked answers | Presenter approval, rehearsal, paper/phone proof, printing and event actions |

The [local-wave record](../acceptance/enterprise/M04-M06-local-wave.md) binds
the focused source results and retained failures. The complete mandatory
enterprise retry executed 286 passed/11 failed/0 skipped; after corrections the
complete gate passes 298/0 failed/0 skipped (2 warnings). Retain both runs and
the first full SDK negative result, 2,088 passed/52 failed/10 skipped. Root JS
178 and Office Node 22 manifest/type/129-test/build checks pass, without real
Office host acceptance. Final global qualification awaits both source workers'
freeze. Individual GREEN counts overlap and are not combined production proof.

At planning review the runtime patch was not committed. S0/S1 subsequently
qualified its Windows/Python 3.13 artifacts and preserved the source-bound
candidate as a feature-branch checkpoint; see the
[artifact record](../acceptance/enterprise/M01-prerequisites.md). Earlier test
totals describe that observed working candidate, not HEAD alone or a published
release. Preserve RED logs and
the prior SDK 2,037-test run rather than replacing them with the later result.

### Performance disposition

The valid local control/candidate pair measured restore 0.28/0.34 ms, a 21.4%
relative increase. Both arms also fail the existing sanitizer anchor. The
bounded FP component diagnostic is consistent with the additional eight-type
scan cost, but does not provide complete attribution or controlled acceptance.
The original M3 outlier remains unresolved. Keep all formal measurements and
`perf/baseline.json` unchanged; this addendum grants no performance waiver.

## 3. Review focus and architectural risks

Each item below has an owning task in Section 4:

1. **Configuration crosses every path:** initial detection, residual segments,
   restore validation, analysis, retries, batch children, boot and audit must use
   the same intended immutable snapshot. A convenient import replacement can
   silently inherit root TNER or audit settings. Owned by S2-S4.
2. **Migration preserves functionality:** source spans, eight additional types,
   numberless-address labels and valid prior mappings must not be lost while
   removing sensitive masking. Fail-closed is not a substitute for previously
   supported successful masking/restoration. Owned by S2-S3.
3. **Installed identity is real:** version/name equality, an editable checkout or
   configured CI jobs do not prove the supplied core was installed or tested.
   Missing root artifacts must not resolve through ambient source or PyPI.
   Owned by S1/S5-S7.
4. **Plaintext boundaries are honest:** MCP currently returns matched text from
   `detect_pii` and restored text from `reidentify`. No-mapping is not the same
   as no-plaintext. Preserve the documented success contract during integration;
   qualify the actual host boundary and limit claims. A change to those public
   success fields needs its own reviewed decision. Owned by S2/S4/M9.
5. **Authority survives time and races:** withdrawal, holds, revocation, target
   revisions and recovery must be rechecked at the actual mutation/disclosure
   boundary, not only when a task was queued. Owned by M4-M7/M10.

The current feature branch also carries earlier domain/research/M3 work absent
from `origin/main`. Do not squash its whole history because a small M1 subtask
passes. Isolation of any independent unit requires a dependency audit and fresh
evidence; it must not bypass the owner's hold on the affected candidate.

## 4. Immediate Sol 6.1 work packages

The owner subsequently authorized parallel S/M source implementation. The
original work-package checklists below retain their full qualification exits;
unchecked items do not mean their source path is absent. Use the current-state
table and local-wave record before repeating work. Each unit follows
RED -> implementation -> focused GREEN ->
complete affected gate -> independent adversarial review -> source-bound record.
Do not reopen an owner decision to avoid implementing its consequences.

### S0. Recover and freeze the current work safely

**Files:** Existing runtime diff, new tests, `.superpowers/sdd/m1-canonical/`
evidence, `docs/project-status.md`, `docs/enterprise/core-compatibility.md`.

- [x] Confirm checkout/ref/push destination and preserve all unrelated owner work.
- [x] Read current status, accepted decisions and this addendum; inventory tracked
  plus untracked patch files. The ignored `astra-runtime-before.json` records the
  pre-review runtime fingerprints for comparison, not a shipped artifact.
- [x] Record completed, pending and held work separately. Keep prior failed
  probes, original M3 timing pairs and interrupted review identities.
- [x] Reuse the completed replacement proxy recheck, not the cancelled old job.
- [x] Complete documentation and missing artifact evidence before signing a
  checkpoint. Split logical units only after checking cross-file dependencies.

**Exit:** A reviewer can identify the exact candidate, intended contracts and
remaining gates. No runtime edit or evidence was discarded to make a clean tree.

### S1. Qualify the implemented prerequisite artifacts

**Files:** Root/SDK `pyproject.toml`, SDK `uv.lock`,
`scripts/check_enterprise_wheel.py`, `scripts/check_sdk_installed.py`,
`docs/acceptance/enterprise/M01-prerequisites.md` and a source/evidence manifest.

- [x] Build direct wheels and sdists with the pinned backend/build constraints.
  Rebuild wheels from the archives outside the checkout with provisioned pinned
  tools and `--offline --no-index`; building both from source is insufficient.
- [x] Verify metadata, complete runtime/resource contents, licenses and absence
  of private resources. Root must contain `config.py` and required SQL/static
  assets. SDK's wheel itself remains namespace-scoped at this checkpoint.
- [x] Install into fresh outside-source targets/environments. Verify supplied
  bytes and loaded origins before synthetic detect/mask/restore and proxy checks.
- [x] Record dependencies/model assets and positive/error/cancellation evidence.
  A test in a provisioned dependency environment is labelled accordingly; do not
  call it a fully independent dependency install without proving that too.
- [x] Preserve the performance hold and every unavailable real-image/host gate.

**Exit:** Qualified engineering artifacts with bounded evidence. This does not
complete M1 or qualify a rollback for a different future contract.

### S2. Make the complete adapter contract matrix executable

**Files:** Create `tests/test_shared_core_contract.py` and a versioned,
non-secret qualification manifest under `config/`; update the compatibility
inventory. The manifest describes test expectations, not client-selectable
runtime policy or credentials.

- [ ] Enumerate root local/HTTP, SDK Python/CLI/HTTP/MCP/proxy and Hosted profiles:
  engine allowlist, model identity, supported inputs, type/span units, sensitive
  policy, mapping owner, success/error schema and lifecycle.
- [ ] Implement `test_each_adapter_declares_policy_and_contract`; an unclassified
  difference or missing profile fails rather than inheriting a permissive default.
- [ ] Pin matched synthetic vectors for all current supported structured types,
  source slices, numberless addresses, token/surrogate behavior and negative cases.
- [ ] Generate synthetic legacy mappings with the retained old artifact. Require
  supported prior mapping/restore behavior to survive, or obtain an explicit
  versioned contract decision before changing it. Never use real saved mappings.
- [ ] Separate MCP successful inspection/restoration plaintext from mapping/error
  restrictions. Add host-specific canary checks before any claim that tool output
  stays out of an external model.
- [ ] Freeze the warn/report projection for every surface before switching policy.
  Prefer existing Python/MCP warnings and HTTP `section26_categories`; the proxy
  must have an explicit, reviewed way for clients/operators to observe its signal.
  Do not add ad-hoc OpenAI body fields or silently drop the signal. Record any
  new public header/field in the contract decision and obtain the required approval
  before implementing a change beyond the already approved migration.

**Exit:** Every intentional difference is named, approved where needed and tested.

### S3. Migrate SDK Python facade, Session, batch and CLI

**Files:** `packages/amphrang/amphrang/__init__.py`, CLI and private adapter
configuration; canonical token/report helpers as required; SDK facade/batch tests.

**Private interface:** create `amphrang/_core_config.py` with
`sdk_core_config() -> CoreConfig` and `sdk_audit_config() -> AuditConfig`, using
the `AMPHRANG` prefix and `allow_remote=False`. Keep config-bound conversion
helpers in the facade so result dataclasses do not create circular imports:
`_detect_with_config`, `_anonymize_with_config`, `_restore_with_config` and
`_analyze_with_config`, each requiring a concrete keyword-only `config`.
Public functions retain their existing signatures and resolve once before
calling those helpers; no new public configuration export is implied.

```python
def sdk_core_config() -> CoreConfig: ...
def sdk_audit_config() -> AuditConfig: ...
def _detect_with_config(text: str, *, config: CoreConfig) -> list[Entity]: ...
def _anonymize_with_config(
    text: str, *, mode: str = "token", salt: str | None = None,
    prior_mapping: dict[str, str] | None = None, config: CoreConfig,
) -> AnonymizeResult: ...
def _restore_with_config(
    text: str, mapping: dict[str, str], *, mode: str | None = None,
    config: CoreConfig,
) -> RestoreResult: ...
def _analyze_with_config(text: str, *, config: CoreConfig) -> dict: ...
```

The first two definitions belong to `_core_config.py`; the other four belong
to the facade and return its existing public result types. These private
interfaces are now implemented in source; final installed qualification is open.

- [ ] Write canonical-identity tests before changing imports. Verify the public
  Entity and core operations come from the supplied `pii_redactor` distribution.
- [ ] Keep public function signatures/exports stable. Resolve `AMPHRANG_*` once
  per operation or Session lifecycle; never mutate process-global environment.
- [ ] Pass captured local-only config through initial/residual/restore/analyze
  paths. Send that same snapshot in process-pool jobs; verify Windows spawn and
  serial/parallel equivalence under conflicting child/root settings.
- [ ] Implement warn/report without sensitive entity emission or sensitive-only
  outbound blocking. Use the projection contract frozen in S2; retain separately
  detected identifier protection and public constructor/function compatibility.
- [ ] Preserve ten reporting categories. Add GENETIC/BIOMETRIC in canonical
  reporting, close root DTO/client allowlists, and bridge assessment taxonomy to
  GENETIC_DATA/BIOMETRIC_IDENTITY without renaming that existing schema.
- [ ] Preserve valid legacy restoration in the canonical implementation where
  required, without a sensitive auto-masking compatibility profile. Existing
  in-memory sessions are completed or closed across an upgrade, never exported.
- [ ] Exercise missing/unsupported engines, warm root remote cache, model-directory
  conflicts, mapping reuse, expiry, batch failure and exception graph controls.

**Exit:** The public Python/CLI path actually uses one core, preserves declared
functionality and applies the approved policy. No duplicate detector/vault remains
on that path. Any extra public contract change goes through the ADR/owner gate.

### S4. Migrate SDK HTTP, MCP and proxy callers

**Files:** SDK `server/`, `mcp.py`, `proxy/core.py`, `proxy/stream_restore.py` and
their focused contract/auth/ownership tests. Keep adapter-owned DTO/header layers.

**Consumes:** the S3 config factories, config-bound facade helpers and canonical
`SessionService(config=...)`. HTTP/MCP/proxy instances retain a snapshot;
standalone Python operations capture their own snapshot. A bound adapter must
not call an unbound helper that re-reads environment halfway through the flow.

- [ ] Bind core/audit config at each adapter's boundary. Boot writability checks
  and audit emission must agree; provider retries retain the operation's snapshot.
- [ ] Preserve `X-Amphrang-Contract-Version`, strict HTTP projections, caller-bound
  MCP handles and session ownership. No mapping appears on HTTP/MCP wires.
- [ ] Retain explicit MCP success behavior while documenting raw-text exposure;
  descriptions such as "present to user only" are not host-enforced guarantees.
- [ ] Route masking, release guards, restoration and provider registry/mechanics
  to canonical code. Streaming/wire-specific adaptation may stay adapter-owned;
  it must not become another detector, vault or provider-policy implementation.
- [ ] Retest all JSON/non-JSON/HTTP-200/SSE/EOF/late/cancellation cases and both
  product namespaces in exception-graph assertions. No held-tail flush on failure.
- [ ] Verify report/category propagation and separately selected optional engines.

**Exit:** All live SDK entry points use the intended canonical core/config and
retain their declared success/error/mapping boundary. A facade-only swap is not enough.

### S5. Complete direct dependency, version and container packaging

**Files:** SDK/root metadata, `scripts/_version_targets.py`,
`tests/test_version_source.py`, `scripts/check_sdk_installed.py`, SDK Dockerfile,
SDK lock and root imported-check workflow.

- [ ] Add the matching `thai-pii-redaction-core` dependency and explicit local
  development source. Test missing/wrong/unrelated core artifacts and namespace
  collisions. Never resolve an unqualified first-party name from public indexes.
- [ ] Extend version checks/bumping to SDK VERSION and the exact core pin;
  regenerate/check the lock when release preparation eventually bumps versions.
  Development remains at current VERSION until that authorized task.
- [ ] Adjust frozen sync so `--no-install-project` cannot implicitly build/install
  the new root dependency outside the pinned explicit install step.
- [ ] Build/rebuild both distributions, compare unpacked bytes/metadata and install
  the explicit pair offline in a clean environment. Verify both origins/pins/files.
- [ ] Replace the SDK-only Docker context's bare `pip install` with qualified
  first-party wheels and a trusted dependency wheelhouse, index disabled. Verify
  exact source labels, no-key refusal, keyed routes and no-egress runtime.
- [ ] Remove separately maintained SDK engine code only after import/entry/build/
  doc/test searches prove no live consumer. Any retained internal compatibility
  modules are thin canonical reexports, not generated or edited engine copies.

**Exit:** Installation and images cannot select the unrelated `aiguard`, an
ambient editable core or an unqualified registry artifact. Model/runtime identity
and every selected optional profile are proven, not assumed from package names.

### S6. Migrate the Hosted build without changing platform promises

**Files:** `apps/hosted/core/`, `apps/hosted/sync/`, Docker/build manifests and its
declared check inventory; canonical modules only where a reviewed gap requires it.

- [ ] Preserve the Hosted gateway/auth/Protected Markdown contract, source/service
  identities, locked security overlay and baked model asset verification.
- [ ] Consume the canonical core through a reproducible build arrangement. Verify
  source/module/model fingerprints and remove the maintained duplicate only after
  every image/sync/runtime consumer is accounted for.
- [ ] Run the full existing non-deploy check job, frontend tests and exact image
  offline/no-egress/failure checks. Root Docker smoke does not qualify this image.
- [ ] Keep wider participant-guide details unconfirmed until primary evidence is
  available. Do not turn the legacy queue emulator into the delivery path or
  describe Protected Markdown as accepted PDF/OCR processing.

**Exit:** The actual Hosted candidate consumes canonical protection while its
stateless remote trust boundary and deployment acceptance remain explicit.

### S7. Close common qualification and M3 holds

- [ ] Rebind root/SDK/Hosted artifacts, dependencies, models, schemas, config and
  reviews to the final candidate. Run each affected complete lane once after freeze.
- [ ] Use a declared controlled performance protocol: same interpreter/dependencies,
  source/model/input hashes, model warm-up, eligible host/window, serialized own
  workloads, fixed pair order and retained raw timings/outliers. Capture adequate
  precision for sub-millisecond restore and distinguish wall/CPU clock resolution.
- [ ] Define run eligibility and repetitions before observing results. Preserve
  invalid/noisy/failed runs with reasons; never discard a negative pair selectively.
  Do not change tolerance, baseline or harness in one arm only.
- [ ] Keep 20% time / 15% resident-memory budgets. A missing sampler is incomplete
  evidence. Do not use shared CI runner timings as local acceptance.
- [ ] After owner Support purge, verify removed objects/refs and apply the already
  authorized visibility change. Then inspect every actual CI job; configured or
  zero-step failed jobs are not passing jobs.
- [ ] Requalify the installed M3 staff artifact, real IdP/database/browser flows,
  migrations/runtime role and restart behavior against the combined candidate.

**Exit:** M1/M3 cross their own gates only when exact required evidence is green.
Preserve held code; do not promote the combined branch or infer a timing exception.

## 5. Detailed continuation through M12

The master plan owns full assertions/interfaces. The work packages below add
execution order and concrete proof obligations; planned files do not exist merely
because they are named here. Reconcile a small schema/API contract before each
new domain; use an ADR/owner decision when it changes accepted architecture,
public contracts or irreversible data behavior.

| Milestone | Complete working deliverable | Implementation/check sequence | Mandatory acceptance and owner boundary |
| --- | --- | --- | --- |
| M0 | Reconciled scope/source/evidence and safe execution environment | Keep current reconciliation; bind source maps and current release matrix; close CI infrastructure classification | Recorded baseline is not green CI; preserve old owner work and closed evaluations |
| M1 | One protection implementation reaches every included consumer | Execute S0-S7; maintain contract/profile and artifact matrices | Every included consumer/build/test and actual CI job qualified; no hidden engine copy |
| M2 | Qualified protection/input/restoration behavior | Pin `tests/test_release_protection_matrix.py`; test guard before each attempt, failed publication, expiry/foreign tokens, Unicode/source intervals, original PDF boxes and flattening; qualify real OCR separately | Development gold is regression evidence only; fresh generalization evaluation needs preregistration and independent permitted labels |
| M3 | Two real staff identities complete scoped inventory/review | Reuse existing authority/OIDC/console; complete source-bound package/browser/restart and controlled-performance/CI evidence; parameterize safe fixture bootstrap where reproducibility is missing | Real IdP/DB/browser E2/E3; production issuer/TLS/pilot are later gates |
| M4 | Separate verified subject authority, genuine consent/refusal/withdrawal | Add subjects/consent migrations and subject portal; separate OIDC client/audience; reviewed source links; immutable notice and purpose versions; race grant replay against withdrawal and queue execution | Staff cannot impersonate a subject; unresolved links/representatives block disclosure. Actual organization customer IdP configuration is owner-supplied |
| M5 | Protected managed collection and recoverable bounded execution | Add encrypted versioned content and controls in the same PostgreSQL transaction; independent key authority; outbox/leases/attempts; approve/recheck exact target and actor under guard lock; crash before/after commit and reconcile | Missing keys/protection fail readiness; no caller paths/SQL/URLs. Key custody/envelope/recovery decisions are review gates before real data |
| M6 | Reviewed retention actions and effective holds | Record purpose trigger/due rule/copies; propose then distinct approval; test hold commits before/during/after action; verify target outcome independently; replay suppression after quarantined restore | Logical primary deletion is not physical/WAL/replica/backup erasure. External irreversible execution requires equivalent fencing or remains manual |
| M7 | Complete scoped rights case and secure fulfilment | Verify subject/representative; discover exact scope; record case-specific clocks/review; execute through M5/M6; deliver recipient-bound expiring/revocable export; test third-party exposure, partial failure and refusal | A queued task or draft export never closes a case; every target/copy/delivery/refusal needs evidence |
| M8 | Reviewed organization control records linked to workflows | Deliver processors/transfers/incidents/responsibilities/policies/assessments; record instrument versions and reviewed applicability; link M3/M4/M6/M7; test stale agreements, unknown applicability and false notification closure | Qualified organization review remains required. No automatic exemption, DPO verdict, legal approval or outward notification from model output |
| M9 | Exact-candidate delivery matrix and usable caller paths | For each declared client run source/unit/build then installed/browser/real-host checks; cover Thai UI, 360/390 mobile and 1280/1440 desktop, keyboard/focus, conflicts, expiry, cancellation and recovery | Each host/OS/provider/profile needs its own E3/E4 record; historical 3.x evidence does not accept current 0.x bytes |
| M10 | Staging candidate with tested integrity/recovery | Bind exact artifacts/config; separate migration/runtime/key/checkpoint authority; fail readiness on bad schema/key/audit/checkpoint; restore quarantine, rotate test keys, reconcile workers; measure declared load and recovery targets | Operator defines infrastructure, custodians, RPO/RTO and capacities before pass/fail. Production keys/host are not changed by synthetic drills |
| M11 | Supervised representative organizational pilot | Freeze users/roles/data permissions/workloads/thresholds; ordinary people perform all critical workflows; independent representative quality review; qualify the first named external/manual system; observe support and recovery | Owner/qualified reviewers supply real participants, lawful data access and pilot acceptance; agent-only browser automation is not human usability evidence |
| M12 | Authorized exact launch and repeatable operations | Assemble source/artifact/model/schema/config manifest, migrations/rollback/runbooks and support roster; rehearse promotion; obtain exact approval; verify live identity and synthetic smoke; schedule owner-approved operational reviews | Deployment/publication/submission needs action-specific authority. Real destructive actions are not release smoke tests |

### Vertical acceptance story

Use the same synthetic organization throughout M4-M10:

1. Staff A creates an activity/notice; independent staff B reviews and activates it.
2. A separately authenticated subject views that exact notice and grants/refuses
   one purpose; staff cannot submit the same act through staff credentials.
3. Reviewed linkage binds an exact managed document version. Protected storage,
   scoped reads and authorized processing run through the common authority.
4. Withdrawal invalidates affected queued/current authority. It cannot silently
   select a different legal basis; separately reviewed retention stays explicit.
5. A due action is proposed, held/reviewed and executed only after current checks
   under the managed-asset serialization boundary. Race outcomes remain honest.
6. A rights case produces scoped delivery or an evidenced refusal/partial result,
   including processor/backup obligations. The UI never calls dispatch fulfilment.
7. A pre-action backup is restored into quarantine. Suppression, withdrawal,
   restrictions and reconciliation run before serving data or reopening readiness.
8. Audit/checkpoint and restart/outage drills prove both the normal path and
   denied/revoked/unknown outcomes on the exact candidate.

### Surface matrix to keep visible in M9

- Desktop and Extension: connection/scope/generation-owned broker handles,
  credential-free installed local profile and fixed local `thainer`; exact
  Windows/macOS package and browser identity evidence for each included surface.
- SDK/CLI/API: explicit Python mapping ownership versus opaque wire handles,
  both modes, batch/process and optional engine behavior, error/cancel lifecycle,
  outside-source artifact identity and versioned migration.
- MCP: no mapping output; qualify the host's treatment of successful matched and
  restored text. A descriptive warning is not a technical external-model barrier.
- Hosted: raw requests reach the service; use stateless/minimized projections,
  protected approval flow and exact reverse-proxy/provider/image evidence.
- Office: preserve the current Word-only release manifest until each other host
  qualifies. Resolve fixed-port server identity through an approved design before
  making the corresponding production claim.
- Enterprise: real staff/subject browsers and legal workflow state, with usable
  loading/empty/error/permission/conflict/expiry states and safe recovery.

Any approved `not_in_release` capability is named and disabled honestly. It does
not erase the original program obligation or authorize advertising that surface.

## 6. Anti-jobs, evidence and delivery discipline

For each bounded unit:

1. Pin outcome, affected caller path and exact base/tree/artifact identities.
2. Write positive and failure assertions first; observe a behavior RED, not only
   an import/setup error. Fault tests prove their intended fake actually ran.
3. Implement the complete caller/domain/UI path without broad unrelated refactors.
4. Run focused tests while iterating; freeze code, then run the complete affected
   lane once. Repeat only after changes, failures or new material concerns.
5. Give a fresh read-only reviewer the requirements, exact diff and evidence
   limits. The implementer never supplies their own independent approval.
6. Reproduce material findings; fix and rerun the owning test. Recheck while a
   material issue remains. Avoid unbounded style-only review loops.
7. Store minimized commands/results/digests and skip reasons. Python 3.13 graph
   checks handle Mapping-based frame locals; test both product namespaces after
   imports migrate. General logs/artifacts contain no private values or mappings.
8. Commit intended files with sign-off on a short-lived branch; push and inspect
   every CI job. Squash only the qualified unit into main. Preserve held/unrelated
   work and never treat a branch checkpoint as main/release acceptance.

Unit records use `implemented`, `locally_verified`, `artifact_verified`,
`held_owner_or_environment`, and `accepted` as separate facts. The master plan's
E1-E5 levels remain authoritative. Missing proof stays missing; no green checkbox
is inferred from a menu, schema, successful queue submission or old test count.

## 7. Owner-only gates and preparation

| Input/action | Agent prepares | Owner/participant supplies | First hard gate |
| --- | --- | --- | --- |
| GitHub privacy purge | Preserve reviewed rewrite, backups and retained-object disclosure | Sends Support request and provides purge confirmation | Purge remains unconfirmed; public visibility already accepted with disclosed risk |
| Controlled performance host/window | Frozen protocol, source/model/dependency hashes, sampler and retained results | Agrees/permits actual controlled environment where necessary | M3 and affected common runtime acceptance |
| Organization and identities | Synthetic realm/configuration and enrollment/check commands | Actual organization, departments, two approved staff, customer issuer/client | M4 real identity and M11 pilot |
| Storage/keys/backups/checkpoint | Concrete interfaces, dev fixtures, failure/recovery drills and reviewed candidate | Custodians, real key/sink/infrastructure policy and required decisions | M5/M10 real readiness |
| Legal applicability | Versioned source/control register and review workflow | Qualified organization review and accountable decisions | M8/M11 real-person use |
| Representative data/users/first system | Preregistered protocols, safe tooling, bounded connector/manual mode | Lawful access, independent labels, ordinary users, scoped system authority | M11 |
| Production/publication | Exact candidate, gates, rollback, runbooks and unsigned/notarization disclosures | Exact action approval and staffed operation | M12 |
| YRSS | Current reviewed packet and evidence-linked 40-answer preparation | Names/advisor approval, timed rehearsal, paper/phone proof, printing/event actions | Physical presentation/delivery |

Unknown owner inputs do not stop independent synthetic engineering. They prevent
the associated acceptance claim. Stop for the root AGENTS decision/ADR/outward
action/unexplained-regression cases, after preparing a concrete reviewable result.

## 8. Model and execution handoff

Astra reviews and writes this addendum. After its independent plan check is
resolved, set this existing thread's model to **`gpt-6.1-sol`** on the current
Codex provider. Preserve inherited reasoning/service options and permission modes;
do not create a new top-level thread or silently switch providers.

Sol completed the bounded S0/S1 unit in the clean checkout with local artifact
qualification and a clear independent review. S2-S6 and M4-M6 now have local
implementations; continue from remaining SDK corrections, source freeze and
qualification, then the remaining M7-M12 work. The old cancelled proxy reviewer is not a live handle;
its completed fresh replacement report remains distinct. Current artifact
qualification is limited to the exact Windows/Python 3.13 prerequisite candidate.

This sequence is already authorized by the owner. Routine task boundaries do
not need another approval question. New expensive architecture/public-contract
changes and owner-only actions keep their stated gates. The full M0-M12 goal
remains active; this planning review is not completion of that program.

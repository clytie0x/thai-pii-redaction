# M7 rights and delivery worker handoff

Base: `b4a8897edc277fcf6eb7f4e988b4bad83c5d6c55`.
Worker branch: `t3/m7-rights-delivery`.

This is a local implementation checkpoint, not production, legal, pilot or
independent-review acceptance. No provider, detector, scoring, corpus, production
dependency, deployment, publication, external message, push or merge is included.
The original checkout and migrations 004/005/006 were verified before writes.

## Implemented boundary

- Immutable original intake, staff or authenticated M4 subject intake, reviewed
  completeness, identity/capacity and representative/recipient linkage.
- Each requested right has its own reviewed applicability, law/source version,
  rationale, clock anchor and optional deadline. An extension requires evidence
  and actual notification-outcome reference. No universal deadline is supplied.
  Unknown applicability and incomplete cases block authoritative planning.
- Versioned exact collection/document plans require scope evidence and a distinct
  privacy reviewer. Access/portability bind protected redacted evidence to the
  document version; the approving reviewer must preview that exact plan.
  Candidate discovery and `pdpa_lifecycle` advice cannot establish identity,
  deadlines or execution authority. The existing DSAR method is explained as
  advice; its file-path scanner is not run on arbitrary caller paths.
- Rectification/restriction/logical suppression use existing M5 instructions and
  current M6 hold/retention fences. Bind an **unapproved** instruction to a plan,
  independently approve the plan, then approve/execute the M5 instruction.
  An instruction cannot be reused across case/plan versions.
- Consent-bound plans capture M4 consent revisions from PostgreSQL. Withdrawal
  blocks use; a genuine subsequent grant with verified propagation cannot revive
  the old export or plan. There is no consent override or silent basis switch.
  A future case-specific lawful-authority adapter needs explicit reviewed design
  and tests before it can authorize an exception here.
- Unsupported external work is an accountable manual task with separate evidence
  submission and independent review. Erasure carries separate derived, processor,
  replica/WAL, backup and physical-storage obligations. Physical erasure remains
  unavailable, including manual attempts to mark that obligation verified.
- AES-GCM delivery binds case, recipient, M4 link revision, export version and
  expiry. It uses the existing independent key-provider interface. No bearer URL
  authorizes access. Each consume/receipt rechecks actual M4 session/link,
  approval actors, current source versions, consent, restrictions and expiry.
  A download records `downloaded`, never fulfilment. A separate same-session
  receipt proves the recipient explicitly acknowledged the delivered response.
  An interrupted download remains unfulfilled; replay is denied. Recovery needs
  a reviewed new plan/export version rather than a plaintext replay cache.
- Closure checks committed M5 outcomes against current primary state, reviewed
  external results and explicit delivery receipts or reviewed refusal outcomes.
  Dispatch alone cannot close a case. Partial work stays partial. Reopening or
  withdrawing preserves history and revokes old delivery/execution authority.
- Thai staff/subject pages provide intake, per-right clocks, target/manual/refusal
  plans, protected preview, review, issue/revoke, evidence review, partial/full
  closure, reopening, subject download and explicit receipt. Private content uses
  text nodes and clears on lifecycle/session failure. Routes return no-store
  headers and value-free validation/domain errors.

## Required parent integration

Existing server/settings/permissions wiring was intentionally left to the parent.

1. Construct `Rights(store, collection, evidence, execution)` using the existing
   protected M5 services and production `consent_gate`, not a permissive callback.
2. Mount `build_rights_router(rights, staff_identity=..., subject_identity=...)`.
   Both hooks must enforce the existing distinct staff/subject BFF sessions,
   origin and CSRF checks when `mutation=True`. The API tests inject synthetic
   staff identity and resolve actual persisted synthetic M4 sessions; those tests
   do not establish real IdP/browser acceptance.
3. Call `rights.fence_instruction(tx, instruction)` from `Execution._recheck`
   inside the existing managed transaction and organization/asset serialization
   boundary, before approval, preview, execution or reconciliation can use the
   instruction. The PostgreSQL tests exercise this exact hook by wrapping that
   method. Omitting the hook leaves an M5 execution path outside M7 revocation.
4. `RIGHTS_ACTION_MAP` exposes operation-to-existing-permission aliases;
   `RIGHTS_ROLES` adds case-manager/privacy-reviewer restrictions. An identity
   steward or system administrator gains no case/legal authority from their name.
   Manual evidence submission currently requires a case-manager owner. Parent
   permission expansion must remain explicit and tested.
5. Existing static-file serving supplies the new `rights_*` assets. Staff entry
   is `/rights`, subject entry `/subject/rights`. Add navigation in the existing
   parent-owned pages and qualify the combined composition.
6. M7 privately adds `007_rights_delivery.sql`. M8 also privately uses 007:
   the parent must rename **M8** to 008 before integration and update the combined
   migration-count assertion from 7 to 8. Never rewrite an applied migration.
   The four M7 Python suites are registered in the mandatory enterprise runner.

## Evidence and limits

Evidence is generated only from this checkout using the read-only existing
enterprise Python/dependency cache, Node 22.23.2 and locked parent jsdom cache.
Source origins were asserted to be under this isolated checkout. PostgreSQL 18.6
uses an owned temporary loopback cluster and private reference whose purpose is
`synthetic_enterprise_tests`; no owner database or lab is used.

Focused RED/GREEN includes the timezone-sensitive encrypted envelope and the
actual M4 withdrawal/genuine-regrant stale-export regression. Earlier setup-only
failures are not counted as behavior RED evidence. Migration tests initially
failed because their old expected count was 6; the private M7 count is now 7 and
all three upgrade/race/rollback tests pass. The interrupted broad run is not a
passed gate. Final check results are recorded below before the scoped commit.

| Check | Observed result |
| --- | --- |
| Mandatory enterprise gate | **356 passed**, no failures or skips; includes all four M7 suites (**34 tests**) |
| Complete root JavaScript gate | **185 passed**, including 7 new M7 DOM tests, Node 22.23.2 |
| Broad root Python run | **3 failed, 3,612 passed, 34 skipped**; all three failures were the old schema-count-6 assertions |
| Corrected migration owning check | **3 passed**; also included in the green 356-test gate; complete root was not rerun after this test-only correction |
| Lint / format / version | `ruff check .`, `ruff format --check .` and `check_version.py` pass (VERSION remains 0.1.0) |
| Owned PostgreSQL restart | Approved encrypted access export and M4 session survive a real database restart; fresh runtime consumes, acknowledges, closes and verifies audit |
| Cleanup | Only the owned loopback server was stopped; its `postmaster.pid` is absent; other servers were not targeted |

Local evidence is retained in ignored `.superpowers/m7/`:
`enterprise-final.xml`, `enterprise-final.txt`, `root-final.xml`, `root-final.txt`
and `performance.json`, with owned restart/control logs. Private database
references remain ignored and are not included in the commit. Earlier negative
runs and the interrupted pre-freeze broad run remain distinct from final gates.

Performance remains held: detect **6.35 ms**, sanitize **16.41 ms**, restore
**0.42 ms**, PDF redaction **80.34 ms**. The script exits 1: sanitize **+63%** and
restore **+50%** exceed the existing baseline. RSS is unavailable because the
read-only cache lacks `psutil`; no package was installed and no baseline moved.
The cause of the budget miss is not established by this worker. These new
modules do not change detector/provider behavior, but that fact does not qualify
performance or authorize landing an unexplained regression.

Real IdP/browser/host, restricted production database role, production key service,
legal applicability, external outcome truth, independent adversarial review,
combined installed artifacts, controlled performance and pilot acceptance remain
separate parent/owner gates. The worker performs a distinct source self-review;
it does not self-sign an independent review and spawns no agents.

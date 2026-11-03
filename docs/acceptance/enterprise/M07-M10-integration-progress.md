# M7-M10 combined integration checkpoint

Observed 2026-11-03. This is an uncommitted local candidate based on `05d5d77`,
with migrations 007 rights, 008 organization controls, 009 operations,
010 processing controls, 011 runtime security, 012 restore cutover and
013 initial activation. No milestone, production deployment or main integration
is accepted by this record. The unchanged M3 performance hold remains.

## Implemented caller paths

- Rights intake, reviewed clocks, exact plans, encrypted subject delivery,
  explicit receipts and evidence-backed closure share the actual staff/subject
  BFF boundaries. Reviewed export renewal carries immutable same-case outcome
  chains; old exports and unrelated mutations do not regain authority.
- Organization registers and reviewed activity controls bind current source
  versions to processing and immutable instruction snapshots. Both consent and
  non-consent processing require these controls in the production profile.
  Supersession cancels unexecuted work without relabelling committed outcomes.
- Runtime-role checks and database fences separate operational authority from
  application credentials. Background verification uses a read-only MVCC view;
  request admission checks bounded current proof and actual configuration.
- Whole-database restore binds its authenticated snapshot, freezes the source
  durably before replay, preserves canonical audit lineage and verifies the
  target witness before release. Old sessions, exports and execution approvals
  do not revive. Historical key coverage is separate from the current serving
  key; audited version transitions permit old-backup recovery.
- Fresh organization activation is a separate protected offline procedure with
  two current authorities, exact reviewed database/runtime identities and live
  file authority. A restored target or previously quarantined source cannot
  use an old initial-activation receipt to enable service.
- Source and installed artifact identity cover canonical namespaces, assets,
  Thai fonts, schema and build inputs. Derived bytecode checks and build-resource
  residue guards close the reviewed identity gaps. Exact final artifacts still
  require rebuilding and qualification.

## Observed evidence and its limits

These results overlap. Do not add them together or call them a new global run.

| Scope | Observed result | Boundary |
| --- | --- | --- |
| Complete root core+web source profile | 3,351 passed, 80 skipped, 1 warning in 206.96 seconds | Python 3.13; all 184 source-manifest hashes match before/after; explicit dependency/database/platform/live skips are not passes |
| Complete root core+web V2 after final fixes | 3,352 passed, 80 skipped, 1 warning in 303.39 seconds | All 184 source hashes and both V2 freeze inventories unchanged; supersedes the earlier root snapshot for this profile |
| Complete SDK source profile | 2,145 passed, 10 skipped in 41.63 seconds | Source tests; does not qualify final installed artifacts, images or live providers |
| First complete mandatory enterprise run | 651 passed, 26 failed, no skips in 1,243.78 seconds across 52 suites | Retained negative; fixture-scope failures, not a green integrated gate |
| Complete mandatory enterprise V2 | 686 passed, no failures, errors or skips in 1,450.30 seconds across all 52 suites | Runtime/test 193-file and artifact 255-input freezes unchanged; two deprecation warnings |
| Complete fixture-aligned auth/collection files | 45 passed, no skips in 31.70 seconds; independent fixture-scope review CLEAR | Test-only corrections; does not replace the complete enterprise rerun |
| M7 domain, chain and pagination | 53 passed, no skips; independent chain review CLEAR | Precedes the parent historical-closure metadata delta |
| Parent case composition and historical metadata | 9 passed, no skips; separate static recheck CLEAR | Actual PostgreSQL; historical checks do not decrypt or authorize new processing |
| M8 processing and M5 compatibility | 70 passed, no skips; 7 DOM cases | Controlled identities and synthetic legal attestations, not qualified human decisions |
| Complete root JavaScript lane | 199 passed across 24 files, Node 22.23.2 | DOM/source tests, not real browser/Office host acceptance |
| M10 security repair | 74 passed; later request/ACL and key subsets passed | Overlapping intermediate results; later snapshot and credential parity deltas are separate |
| Read-only qualification snapshot | 51 passed; final affected subset 21 passed, no skips | Actual paused-verifier/session/route tests and signed localhost witness |
| Credential-file parity | 6 observed RED cases, then 8 passed including managed-key cases | Invalid or changed DB/OIDC/key files cannot be blessed by refresh against cached objects |
| Headless worker freshness | 14 passed, no skips; later final-input expiry regression observed RED then GREEN; separate static recheck CLEAR | Checks proof after public IdP I/O and at actual claim/execute transaction boundaries, including after final input I/O |
| Combined controlled recovery | 39 passed, no skips | Actual independent PostgreSQL databases and signed localhost witness; subsystem artifact identity is fixed per case |
| Initial activation and physical input binding | 44 passed, no skips; separate static recheck CLEAR | Includes clone-before-first-use, actual file/ACL drift and archived-receipt rejection |
| Artifact identity and packaging source checks | 75 passed | CPython 3.13 observed; other declared interpreter profiles still require CI |
| Build-resource residue | 4 passed | Stdlib resource-writer tests; final wheel archive remains a separate gate |
| Complete identity and residue files after isolated-build import fix | 61 passed on CPython 3.11.15 and 61 passed on 3.12.12, no skips | 56 identity plus five residue cases per interpreter; five helper/test hashes unchanged; source-format proof, not installed artifacts |
| Integrated V2 paired artifacts | Six artifacts, three fresh Python 3.13 profiles, 214 installed tests without skips; separate review CLEAR | Thirteen migrations; installed identity/cache format checks on 3.11/3.12 are separately bounded; no image/host/performance acceptance |

The root profile's 80 skips comprise 40 PostgreSQL and six enterprise-identity
collection skips, one `sentence_transformers`, 17 NumPy, five OpenCV, three
Transformers, four other ML, three OS and one live Tokenmind skip. Its source
comparison and report are `root-web-core-source-comparison.json` and
`root-web-core-current.*`; the SDK reports are `sdk-source-current.*` under the
ignored report directory below. Counts from different profiles are not
comparable acceptance totals.

All 26 failures in `enterprise-global-current.*` were fixture-scope mismatches.
The auth BFF/schema-audit fixture now explicitly sets
`production_operations_required=False`, and the collection fake store declares
the same fixture profile. No assertions were removed and no production guards
were weakened. The two complete files pass in
`enterprise-fixture-aligned-20261103T073623.*`; a separate review is CLEAR.
This follow-up does not make the first global run green. The headless-worker
freshness fix and its final-input expiry correction have passed scoped review.
The final V2 source passed the new complete 52-suite run without skips.
Affected source/Office gates, images and new exact-candidate CI remain pending.
The [integrated paired artifacts](M01-integrated-artifacts.md) now have their own
bounded installed-runtime qualification and independent review.

## Retained negatives and review disposition

Earlier root/SDK, artifact-batch1, performance and CI failures remain retained.
New review regressions include stale queued authority, staff late-response
privacy, omitted notification audiences, uncertain mutation retries, mixed-right
outcome chains, key rotation races, runtime grant and GUC bypass, unbounded
verification, credential-file drift, restore audit forks and stale source
authority, partial-unique replay ordering, initial target substitution, bytecode
identity and stale build resources. Separate read-only reviews checked the
corresponding corrected scopes; they did not rerun tests or accept production.

The first combined recovery attempt retained 33 setup failures and six passes:
the command used `PGBIN` instead of `AIGUARD_OPERATIONS_PG_BIN`. Correcting the
environment produced the separate 39-pass report without overwriting that
negative. A parent M7 run retained 60 passes and one advisory-lock timeout while
another worker deliberately paused the same organization lock in a different
schema of the same database. The failed pagination case subsequently passed in
isolation; final combined qualification must still pass. Distinct worker
databases now separate those test locks. No timeout or production lock key was
relaxed.

Local reports, commands, hashes and failed attempts remain under ignored
`.superpowers/sdd/parallel-s-m/`. The final V2 source freeze binds 193 runtime,
build and affected test files; a separate artifact inventory binds 255 inputs.
Both exclude preserved untracked file `1`. These counts are not acceptance
totals. Hash or runtime changes require rebinding affected evidence.

The first new integrated wheel build retained a real isolated-builder import
failure: manifest loading imported the runtime cache helper before the canonical
package was importable. Moving that import into actual cache verification keeps
manifest construction independent of runtime imports; the new isolated
regression observed RED then GREEN and scoped review is CLEAR. The just-started
global run was stopped before producing a summary or XML, with its unchanged
freeze and aborted evidence retained. Its forced termination did not verify
fixture teardown. The new V2 complete run uses fresh reports and fixtures.
Earlier 60-case floor results precede this correction and remain retained.

After source/artifact tests finished, the parent stopped its exact owned
PostgreSQL test cluster. One five-iteration checkpoint performance run measured
detect 5.65 ms, sanitize 15.33 ms, restore 0.36 ms, PDF 70.24 ms and RSS 151.9 MiB.
It exits 1: sanitize +52% and restore +29% exceed the unchanged time budget.
This is the existing held gate, not controlled-environment M3 acceptance or a
baseline/budget waiver. The report and stopped-cluster record remain retained.

Additional V2 installed PDF probes pass seven groups in each of two profiles,
including value-free report/receipt checks. They exposed incomplete installed
receipt version traceability: the receipt reports `unknown` although the wheel
contains the canonical `_artifact/VERSION`. Recompute verification still matches.
The original root CLI remains source only. The version lookup correction is the
next bounded unit; these observations do not accept receipt release or that CLI.

## Remaining acceptance

Retain the [old paired-artifact record](M01-combined-artifacts.md) and
[installed PDF evidence](M02-installed-pdf.md) as their exact older candidates;
they do not qualify the new governance/schema/artifact-identity code. The
development identity wheel proves its recorded packaging mechanism before the
final hardening deltas. The separate V2 pair above qualifies the final recorded
checkout inputs; it does not turn earlier artifacts into current evidence.

Complete the remaining source/host gates, controlled performance diagnosis,
remaining artifact/host profiles and all executing CI jobs. Rebind actual staff/subject
browser, IdP, restart, restricted-role, package/image and each declared storefront
host gate. Real TLS, independent witness/key/backup custody, accepted RPO/RTO,
capacity, legal applicability, named participants and pilot outcomes remain
separate. No owner deployment/publication or human acceptance is inferred.

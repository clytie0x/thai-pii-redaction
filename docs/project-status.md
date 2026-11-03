# Project status

Updated: 2026-11-03

The owner resumed engineering toward consolidating retained work into one main
branch. The stopped diagnostic WIP is now implemented: fixed, closed smoke
diagnostics preserve private errors, native marker compatibility and existing
feature admission. Hosted parity now verifies the declared generated resources
and license copies against the trusted source manifest. Enterprise test fixtures
create protected files before use and prove an actual ACL transition.

The resumed complete core/web run passes 3,429 tests with 80 explicit skips and
one warning; all 267 bound files and the 255 artifact inputs are unchanged
before/after. Root JavaScript passes 206 tests across 24 files. Native-package
Python tests pass 127 with one platform skip; Hosted owning checks pass 104
without skips; three enterprise owning suites pass 57 without skips on actual
Windows/PostgreSQL 18. Separate adversarial reviews are CLEAR for all three
units. These results overlap and are not added into one acceptance total.

Exact-candidate Linux/Hosted image, Rust compile and package CI remain required.
The current core artifact payload is unchanged from receipt V3. The stopped
WIP, all prior failures and the older results below remain retained. No main
merge, performance waiver or production acceptance is claimed.

Current local integration includes M7 rights/delivery, M8 organization and
processing controls, and M10 runtime/backup/restore/initial-activation paths.
The [combined progress record](acceptance/enterprise/M07-M10-integration-progress.md)
separates implemented callers, independent review fixes, retained negatives and
overlapping focused results. Governance V2 is committed locally as `2dec40d`;
the current receipt-only follow-up has separate source/artifact evidence. Its complete root
core+web V3 source gate passes 3,356 tests with 80 explicit optional/platform/live
skips and one warning in 214.40 seconds on Python 3.13, with all 184 source
hashes unchanged. SDK source passes 2,145 with
10 skips, and root JavaScript passes 199 tests. The final mandatory enterprise
V2 gate passed 686 tests across all 52 suites without skips, with the 193-file
source and 255-input artifact freezes unchanged. It was not rerun for the
receipt follow-up: only `receipt.py` and `receipt_pdf.py` change among artifact
inputs; governance modules remain unchanged. Its earlier 651-pass/26-failure run
and test-only fixture corrections remain retained. The headless-worker freshness fixes pass tests
and independent review. The [receipt V3 paired artifacts](acceptance/enterprise/M01-receipt-artifacts.md)
pass three fresh Python 3.13 profiles and 214 installed tests without skips,
with CLEAR source and exact-artifact reviews. The
[installed PDF follow-up](acceptance/enterprise/M02-receipt-installed-pdf.md)
verifies installed receipt version 0.1.0, recomputation and Python API/source-CLI
guidance in seven proof groups in each of two profiles; all ten rendered PNGs
were inspected. Earlier V2 artifacts and their `unknown` receipt-version proof
remain unchanged. Remaining artifact/host profiles, CI, controlled performance and
actual-host/pilot acceptance remain open.

Earlier protection checkpoint: the complete source profiles reached root 3,549 passed/
34 optional/platform/live skips, SDK 2,141 passed/10 such skips, JavaScript 178,
and Office Node 22 manifest/type checks, 129 tests and build. A subsequent real
production-composition test exposed queued approval resurrection after consent
withdrawal and genuine regrant. Atomic exact-scope invalidation now passes 27
integration cases and all 322 mandatory enterprise tests without skips, with a
clear independent review. It preserves immutable outcomes and non-consent work.

The first newly built paired artifacts are retained as negative evidence: an
installed mapping-reuse probe selected root TNER despite the SDK local snapshot.
No live provider call occurred. The config path through anonymization candidate
validation and the standalone pipeline is now fixed (root 200 and SDK 191 focused
tests, no skips); the preceding broad-suite totals are not new runs of this delta.
The earlier [frozen combined pair](acceptance/enterprise/M01-combined-artifacts.md)
was built and qualified outside source on Windows/Python 3.13: six artifacts,
three fresh profiles, 214 installed adapter tests without skips and six artifact
negatives. This evidence is bound to `b4a8897`; packaged runtime/config/locks
are unchanged through `b468592`. It does not qualify images or actual hosts.

The current V3 local five-iteration run after quiescence measures detect 5.90 ms,
sanitize 15.46 ms, restore 0.36 ms, PDF 75.53 ms and peak RSS 151.8 MiB. It exits
1: sanitization +53% and restoration +29% exceed the unchanged 20% time budget;
the 15% RSS budget and baseline are unchanged. The older V2 run remains retained.
This is a held feature checkpoint, not a
performance waiver, controlled-environment M3 acceptance, main integration or
production release. The later M7-M10 integration is implemented locally and
under combined qualification, not accepted.

Completed CI on `2c132f6` passed 15/26 jobs. Nine failures concern the stopped
diagnostic WIP/style; Hosted rejected generated wheel resources, and enterprise
reported private-file/ACL fixture failures. These three failure groups have the
local corrections and reviews above, pending the next exact-candidate CI run.
Windows and macOS packaged smoke passed on `2c132f6`. Earlier `20a9a45` passed
Imported 9/9 and root 16/16 but failed macOS smoke at `analyze` without inner
diagnostics. A later passing run does not establish that older failure's cause.
Historical public CI on `05d5d77` passed 24 of 26 jobs, including actual Windows/macOS
package smoke, all SDK profiles and the isolated SDK image. Its remaining
Windows Python-to-Node test timeout and Hosted nginx harness failures have local
test corrections awaiting a new exact-candidate run. Root/Hosted production
limits and assertions were retained. No all-green integrated CI is claimed.
Earlier CI on `b468592` passes all seven SDK profile jobs and the actual SDK
offline-image smoke. The downloaded image/API reports are bound in the
[SDK CI record](acceptance/enterprise/M09-sdk-ci.md). At that older checkpoint,
imported checks failed in the Hosted runner's shallow-path test before its image
build. Root CI exposed a separate QI test collection error in the bare profile.
The macOS cross-platform smoke also failed before package build: an immediate
health assertion received a valid nonterminal `broker_busy`. The test now uses
the existing bounded readiness helper and checks retry, deadline and
terminal-error behavior. Local Rust
execution is blocked by missing MSVC `link.exe`; formatting alone does not prove
the fix. The 24 passing jobs on `05d5d77` supersede the older pending statements
for their exact scopes. Its two remaining failures and subsequent integration
deltas still require a new exact-candidate CI run; no all-green result is claimed.

| Storefront | Current candidate evidence | Remaining gate |
| --- | --- | --- |
| Enterprise application | M4-M8 and M10 local callers; prior complete V2 52-suite run 686 passed/0 skipped; receipt V3 installed pair and PDF follow-up | Exact-source CI, new-candidate browser/IdP/restart, whole-environment recovery, performance and organization pilot |
| Hosted application | Canonical wheel source/build path, 16 execute contracts and source-bound safety checks | Exact offline image, complete CI and platform acceptance |
| Python SDK | Recorded source profile 2,145 passed/10 explicit skips; receipt V3 installed pair; historical SDK CI profiles and isolated image smoke on `05d5d77` | External hosts/live providers and remaining exact release/OS profiles; complete exact-source product CI |

Current parallel wave: SDK and Hosted source consumers now use the canonical
core, and M4 subject consent, M5 managed execution and M6 retention/holds have
domain/API/Thai UI implementations. They are **implemented locally; qualification
pending**, not accepted milestones. The
[local-wave record](acceptance/enterprise/M04-M06-local-wave.md) separates focused
candidate results, review fixes, retained failures and remaining gates. Its
298-pass result and first failed SDK run are historical; the later complete
source results and frozen artifact evidence above supersede their pending
statements for those exact scopes. No complete green CI, new real-browser/IdP/
restart acceptance or production readiness is claimed. M3's controlled-performance
hold remains unchanged.

SDK retains 29 internal canonical module aliases rather than maintained engine
copies; its sensitive-span implementation is removed. Hosted copies are removed
and its build prepares a supplied, source-bound first-party wheel/dependency/model
context offline. Source checks and build preparation do not qualify those images.
M7 rights/delivery and M8 organization records are in combined local integration,
including review corrections; combined qualification is pending.
The M10 [operations candidate](enterprise/operations.md) extends existing collection
recovery with encrypted whole-DB backup/isolated quarantine, a signed HTTP witness
adapter, production request/DB fences, additive key operations and operator assets.
The later controlled replay/cutover now includes current M3-M8 authority,
registry, consent, holds, outcomes, cases and processing controls. Initial
activation remains separate from restore; both require their exact proofs.
Whole-environment recovery acceptance, custody, load, RPO/RTO and Docker/TLS/IdP
qualification remain open. All declared
storefronts remain in scope, with their own exact-artifact and host gates.

The owner has not provided the pilot organization/departments, target host,
login, two testers or privacy-responsible person. These are owner inputs still
not provided, not inferred product choices. Synthetic engineering continues;
pilot, legal and actual-host gates remain open.

The accepted single-organization self-hosted design remains in force. The
[execution addendum](implementation/2026-11-02-astra-sol-execution-review.md)
assigns the current checkpoint/artifact work and detailed Sol 6.1 sequence.
Earlier candidate evidence is retained below; it does not supersede the current
qualification limits or qualify the new source wave.
Prerequisite source checks recorded before S0/S1 pass 3,297 root tests (34 skips), 156 mandatory
enterprise tests (zero skips) and 2,038 SDK tests (10 skips). Proxy focused checks
pass on locked AnyIO 4.14.2 and the declared 4.4.0 floor. These are local candidate
results, not current-main, installed-artifact or production acceptance.
Fresh S0/S1 root/SDK wheels and sdists are locally qualified on Windows/Python 3.13:
offline archive rebuilds match direct-wheel bytes, fresh offline installs pass
43 root configuration and 206 SDK proxy tests, and installed synthetic roundtrips
and source origins pass. The [artifact manifest](acceptance/enterprise/M01-prerequisite-artifacts.json)
binds these results to the unchanged candidate; its fresh S0/S1 adversarial review
is CLEAR. The [prerequisite record](acceptance/enterprise/M01-prerequisites.md) retains
consumer/host gaps and the restore performance budget miss. M1 is not complete;
M3's controlled-environment performance hold and executing-green-CI gate remain.

Repository privacy update: the owner approved screenshot-only history cleanup
before making this repository public. A reviewed, backed-up rewrite now matches
all 19 remote branches and one tag. Other file bytes are unchanged in every
verified commit. The owner subsequently accepted the retained-image risk after
explicit disclosure and instructed public visibility; GitHub now reports PUBLIC.
Server-side purge remains unconfirmed. Public reruns now execute; the first
actual attempt exposed Hosted provenance-fetch and core-only optional-import
failures. Continue from the clean checkout, not the preserved old-history clone.
See the [cleanup record](acceptance/enterprise/M00-public-visibility.md).

Hosted provenance repair preserves all 75 manifest source hashes and every Hosted
core byte. Its unavailable historical source commit has no certified rewrite
mapping. A new explicitly reconstructed source checkpoint is recorded in
`apps/hosted/sync/SOURCE_PROVENANCE.json`; it is not recovery of the original
commit. Verification still fetches an exact public SHA and compares every hash.
The corrected `--check --verify-upstream` passes anonymously with credential
helpers disabled; 26 host-level Hosted contracts pass. Nginx/Compose checks are
unavailable locally because Docker is absent, and remain actual CI requirements.
The core-only test collection guard is locally verified with 2,770 passed/303
optional skips; the same governance model tests pass 12/12 with Pydantic installed.
CI on the corrected candidate remains a separate gate.

Execution update (2026-11-02): the owner resumed M0-M12 and YRSS work and
requires independent adversarial subagent review at every stage. The preserved
implementation checkpoint was reconciled with main `2480757` in `9711d79`.
That M0 baseline passed 2,922 Python tests with 34 skips. The subsequent M3
candidate now passes 3,035 Python tests (34 optional/host/live skips), 156
mandatory enterprise tests without skips and 178 JavaScript tests. Actual
synthetic Chrome/Keycloak/PostgreSQL flows cover inventory/notices/review,
independent membership approval, suspension/reactivation and session cleanup.
Actual installed-wheel and graceful app/database restart checks also pass.
M3 acceptance remains held for an unexplained performance outlier and CI;
bounded diagnosis did not establish its cause. At that checkpoint GitHub jobs
could not start because of the account billing restriction; public CI now
executes, but the new combined candidate is not qualified. Local Windows Rust
lacks its MSVC linker.
See [M3 progress](acceptance/enterprise/M03-authority-progress.md),
[M0 evidence](acceptance/enterprise/M00-baseline.md) and the
[current release scope](enterprise/release-scope.md).

M1 preparation now has a reviewed [compatibility inventory](enterprise/core-compatibility.md)
and [owner-approved decision](decisions/2026-11-02-shared-core-compatibility.md).
The owner selected SDK warn/report migration, a direct first-party root dependency
with the broader footprint, and fixed proxy errors with qualified rollback.
The runtime migration is implemented in the current local wave; M1 acceptance
remains open. PyPI's existing `aiguard` is an
unrelated project. The owner selected distribution name `thai-pii-redaction-core`,
preserving existing imports and caller entry paths. The root metadata is renamed;
local Windows/Python 3.13 artifact checks cover an offline sdist rebuild, clean
installation and replacement of a verified old first-party core installation.
See the [artifact manifest](acceptance/enterprise/M01-core-distribution-manifest.json)
and [migration guide](enterprise/distribution-migration.md). The SDK now pins the
first-party dependency; final paired-artifact and platform gates remain open.
Public-index resolution
is prohibited for local qualification; no package publication/release is authorized.

The expanded CI candidate configures the existing Hosted checks, SDK Windows/
Python floor and optional profiles, API collection, catastrophic performance
guard and legacy Docker smoke. That CI-preparation checkpoint recorded 3,112 tests with
34 skips; mandatory enterprise 156 with no skips. SDK server-only passes 1,963
tests (11 skips); prior full/core profile counts remain 1,989/1,606. Actual owned
loopback collection checks cover 8 requests, 9 assertions and 4 script tests,
with fresh private audit storage. One prior CLI nonzero remains unexplained;
three diagnostic plus twenty bounded reruns passed, which does not explain or
erase that failure. Docker was unexecuted locally and Actions was billing-blocked
at that checkpoint; current image/CI qualification remains separate. M3 remains
held until controlled-environment performance measurement.

At the earlier distribution-rename/code-map checkpoint, the qualified local root
suite passes 3,118 tests with 34 skips. The earlier failed run is retained: it
caught the missing `tools` map entry and lacked the existing enterprise test DB
reference. The corrected run supplied that synthetic fixture; no integration
tests were weakened or skipped to obtain the result.

Current source versions are 0.1.0 under the accepted reset. Older 2.x/3.x
package/certification rows below describe their named historical candidates,
not a current 0.x release. `apps/hosted/STATE.md` records a 3.0.2 deployment;
that record is not fresh live verification. Hosted resides in the imported
subtree and now consumes the supplied canonical core wheel in source/build
preparation; exact installed-image and platform gates remain open. The release matrix includes
Windows/macOS only. These qualifications supersede conflicting older status
wording below until each exact current path is requalified.

Enterprise PDPA direction (2026-10-31): the owner requested work toward a full
organization system. The [proposed control-plane architecture](decisions/2026-10-31-pdpa-enterprise-control-plane.md)
has had an independent builder check; the owner confirmed a single self-hosted
organization. Implementation is in the managed `feat/pdpa-enterprise` worktree
originally at `.worktrees/pdpa-enterprise/`; that old-history checkout is now
preserved privately and current work uses the clean checkout named above. The
dedicated `app.enterprise` adapter now
calls shared PostgreSQL authority/registry commands using verified staff sessions;
it does not persist local reversible PII mappings. Synthetic real IdP/browser
and restricted-runtime-role evidence is stronger than the earlier trusted-domain-
principal checkpoint. Subject consent, protected managed execution and reviewed
retention/holds now have local implementations and bounded evidence in the wave
record. Combined qualification, rights fulfilment, wider governance, production
TLS/storage/checkpoint/recovery and human pilot remain open. The local assessment prototype and legacy HTTP/native acceptance
remain separate. Operational setup is in [the enterprise guide](enterprise/README.md).

Historical owner-requested checkpoint: development was paused; see the
[commit/evidence handoff](implementation/pdpa-enterprise-handoff.md). The latest
domain-source full local Python gate is 2,884 passed / 34 skipped. Task-owned test
services were stopped at that checkpoint. This is branch publication, not main/release promotion.

PDPA design update (2026-10-31): local `ai_guard.py pdpa assess/coverage/lifecycle`
adds category evidence and non-executing lifecycle plans. The
[measured three-way comparison](../research/pdpa-coverage/RESULTS.md) explicitly
reports partial coverage, unsupported modalities and remaining attribution
gaps. It does not change HTTP/native/Hosted acceptance or establish complete
legal compliance, consent/identity verification, deletion or rights fulfilment.

YRSS research update (2026-10-31): see
[the current campaign](../research/yrss2026/README.md) and
[research plan](research/yrss-accuracy-plan.md) for the local baseline,
structured input recovery and exact-version evidence. The source campaign is
separate from the historical acceptance records below; it does not certify a
new installer, Hosted deployment, live provider, or physical OCR pipeline.

This is the acceptance ledger for the current roadmap. It distinguishes code
existence from evidence on the real delivery path.

This document answers one question: **what is actually finished, and what is the
evidence**. It is not the code map ([CODEMAP.md](../CODEMAP.md)) and it does not set
priority or order ([ROADMAP.md](../ROADMAP.md)). Every storefront named in the
code map must have a row here; `tests/test_docs_coverage.py` enforces that.

Source version: `VERSION` is `0.1.0` after the 2026-10-19 reset
([decision](decisions/2026-10-19-version-reset.md)). Narrative below that
still says 3.0.0 certification describes the archived line, not this tree.
Hosted production still reports `3.0.2` until this source is deployed
(`apps/hosted/STATE.md`). That deployment was not repeated here.

Benchmark note: `blind-v1` is a closed historical evidence set. Its six-reveal
budget is exhausted, so it must not be described as an active blind evaluation
or used for further tuning. A reproducible synthetic comparison freeze now
exists (`benchmark/blind_v2`, seed `20261101`, hash in
`benchmark/data/blind-v2-repro.lock.json`), plus a harder prose split whose
test half (seed `20261103`, hash in `benchmark/data/hard-test.lock.json`) was
scored only after the detector change. Neither is a tuning set, and neither
replaces the sealed `benchmark/data/blind-v2.enc` protocol corpus, which stays
closed. The 2026-11-01 re-run, including a local `gemma3:1b` baseline and the
raw-versus-redacted utility check, is in
[benchmark/blind-v2-results.md](benchmark/blind-v2-results.md); the remaining
gaps are in [benchmark/gap-list.md](benchmark/gap-list.md). The exact WSL
candidate at commit `ded67d3` passed the
synthetic government-form privacy gate 9/9. That is historical
exact-candidate evidence, not a run of the current HTTP-v2/PDF composition;
physical scans, handwriting, and broader real-form annotation remain outside
it.

Latest detector campaign evidence (2026-08-04): commit `fcd3b0d` closed the
enumerated bug/mechanism inventory and added adversarial recall regressions.
The local gold run (`python -m benchmark --source gold`) measured overall F2
0.947, entity recall 0.969, character coverage recall 0.986, exact-boundary
recall 0.892, and 15 false positives in the 45-document negative slice. These
are gold/synthetic local measurements, not blind generalisation evidence:
`blind-v1` is exhausted and future measurement requires `blind-v2`. The
campaign's accepted owner decisions, known OCR rerun block, and performance
interpretation are recorded in
[the 2026-08-04 campaign record](decisions/2026-08-04-weakness-closure-campaign.md).

Performance-gate follow-up (2026-08-04): `scripts/measure_perf.py` now gives
each PDF-redaction measurement an isolated temporary output directory and
removes it afterward, so concurrent local runs cannot collide on one fixed
`tmp/perf-redacted.pdf`. This closes a harness defect found during the
campaign. The committed `perf/baseline.json` remains unchanged: an unmodified
`20a9a1d` run on the same machine was already above it, and repeated runs
varied widely; the campaign's controlled in-process detector comparison
remained +7.5%, inside the 20% budget. The baseline is a local comparison
anchor, not a production SLO; recalibration requires a deliberately controlled
measurement.

Hardening control (2026-08-05): the clean `93a7108` baseline passed 1,677
Python tests, 60 root JavaScript tests, 68 Office tests, 19 Rust tests, and a
newly built packaged-sidecar smoke. Five optional OpenCV tests skipped. The
formal performance command was red on unchanged `main` because the 0.28 ms
restore anchor measured 0.40 ms; repeated controls confirmed local timing
variance, so the baseline was not moved. Exact commands, warnings, and
unverified paths are in the
[dated baseline record](acceptance/2026-08-05-hardening-baseline.md).

That control freezes the pre-fix truth at `93a7108`. Current source now stages
local sanitization on a detached session/vault graph and publishes it once only
after core processing, Section 26, guard projection, response encoding, and a
correlation-only process-audit write succeed. Failure-injection coverage
preserves the published graph, token ordinals, capacity/LRU state, and
concurrent visibility. Known-session expiry remains lifecycle disposal outside
rollback; displaced-vault cleanup after publication is best effort. A clear
generation prevents a stale provider rollback snapshot from reviving disposed
mappings.

Caller-held stateless mappings are now re-admitted under opaque
`seed:<uuid4>` entity IDs with the internal `SEEDED` provenance marker. An
identical replay returns its existing immutable record without changing
lookup, audit, or access state; a conflicting original raises a constant
value-free error before mutation. New seeds add one structural `seed` audit
row, so the retained internal audit remains free of the caller's pseudonym and
original before and after `clear()`.

Current source now applies one fail-closed outbound policy to local-session and
stateless sanitization: structured FP findings, text-based TB findings,
detector-independent contiguous runs of six or more digits, anonymization
failures, and missing replacement records return no masked result. A
caller-seeded pseudonym is reused only when nonempty, original-free, absent
from the current source text, and free of independent FP/TB/digit residual
signals; token mode also requires the product token shape for the detected data
type. Identity, embedded-original, empty, cross-type residual, and
duplicate-occurrence laundering regressions are blocked. Local-session
rejection remains inside the existing atomic transaction. CLI, HTTP/hosted
roundtrip, and worker roundtrip now use one shared provider orchestration layer.
It repeats the scan immediately before every actual invocation, sends the same
immutable masked text, permits at most three 60-second attempts, and sleeps for
fixed one- then two-second delays. Only timeout, network, HTTP 429, and HTTP 5xx
failures retry. Tokenmind makes one HTTP request per invocation and does not
interpret `Retry-After`. HTTP returns 422 with a bounded `residual_pii` v2
error envelope and the version-1 worker envelope returns a value-free
`residual_pii` error.

This remains automated local evidence only. The
[dated Office v2 transport preflight](acceptance/2026-08-06-office-v2-composition.md)
covers the current packaged backend directly and through the HTTPS development
proxy. Historical installed Desktop, storefront, Office-host, live-provider,
and official-platform evidence still predates the current changes and requires
matching-strength reruns. Current HTTP v2 removes mapping-oriented fields, raw Section 26
matches, and prompt-guard excerpts/rationales; first-party clients validate
exact response schemas and safety state. Token mode now combines a random
vault-generation tag with an unpredictable per-token nonce. Regressions show
that stale and guessed tokens remain foreign in the exercised drop, restart,
expiry, eviction, and same-session preplay cases. The random 64-bit tag plus
approximately 94-bit nonce makes accidental identity reuse and future-token
preplay computationally impractical; this is probabilistic separation, not
impossibility. Phase 7 adds one backend-owned earliest-deadline timer, exact
half-open TTL semantics, target-bound single-use disposal authorization, and
deterministic cleanup for expiry, authenticated disposal, eviction, shutdown,
and lifecycle failure. The service fails closed and clears every registered
session if a required timer cannot start. Its actual session-owned resources
are in-memory vault/mapping state, entity/digest/salt state, timer state,
authorization-replay fingerprints, and hashed lifecycle tombstones; provider
clients, child processes, ports/listeners, and temporary paths are not owned by
a `SessionService` session in the current architecture. Client-driven disposal
remains unimplemented for Office because that fixed-port client cannot receive
the control credential. Phase 8 Slices 1--3 implement the
generic native protocol, authenticated admission/bootstrap, private backend,
and connection/scope/session-owned data plane. Slice 4 routes current Desktop
source through that boundary with broker-backed disposal and no direct
backend/data-plane HTTP or Python lifecycle authority. Slice 5 implements the
Extension's broker-backed disposal and Native Messaging boundary. Slice 6
completes installed package admission, maintenance drain, atomic replacement,
and cleanup. Slices 1--6 are integrated on `main`; the exact Slice 6 closure
tree, branch workflows, independent reviews, and post-main workflows are
recorded below. Office remains unchanged and outside broker v1.

Historical Phase 7 handoff status: **merged; main CI green; Phase 8 was then
deferred**. The
first independent merge review rejected original commit `f968833` with six
confirmed blockers: failed restore renewed retention, managed service/vault TTL
decisions could conflict, noncanonical base64url bypassed replay identity,
authorization could expire while waiting for the lifecycle lock, the disposal
URL exposed session authority through real Uvicorn/Desktop logs, and
current-state documentation incorrectly described behavior and approval.
Corrective commit `b9c0b745f07059850592977c904f22098c1e41b7` keeps
`f968833` intact and addresses all six with deterministic local regressions;
its branch CI
[passed 11/11](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31090571421).
The post-CI review then found an eager-callback fail-closed gap and stale status
text. Follow-up `6cd109d11478a05e711064d227a8241ecb38ea39` closes both,
and its branch CI
[passed 11/11](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31092753172).
Documentation evidence commit `2e1474810ea7b8fd729413ac1d2cc2fd713d2abf`
then passed the final branch CI
[11/11](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31093131935).
The two read-only reviewers, neither of whom edited code, inspected that exact
head in separate lifecycle/concurrency and authentication/secrecy passes and
reported no blocker. Main integrated the complete branch through
history-preserving merge `eb0c45c043883ec93ab56849d300d500e8061bf4`.
Post-merge
[CI passed 11/11](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31094033944)
and
[cross-platform smoke passed 2/2](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31094033956).

Phase 8 first-unit status:
**explicit-TNER source hardening integrated; branch CI green**.
Current source makes the opt-in remote engine fail the whole operation on any
failed request or incomplete ordered token stream. Configuration/dependency
and network/upstream unavailability become bounded `ner_unavailable` metadata;
malformed, unequal, misaligned, or truncated responses become
`ner_incomplete`. Earlier chunk candidates are discarded, later chunks and
providers are not called, no local session is published, and no PDF output is
retained. The shared BIO/chunk engines (`thainer`, WangchanBERTa, and union)
keep structural skip-and-continue behavior; the separate fine-tuned offset
engine is outside this change. The same fixed failure semantics are contained
across direct detection, analysis, local-session and stateless sanitize,
roundtrip, HTTP v2, the hosted allowlist, PDF cleanup, and the version-1 worker
envelope. This is automated source evidence using synthetic failures; no live
TNER credential or call was used, so fresh response-shape and end-to-end
mapping acceptance remains open.
The exact scope, commands, review findings, and limitations are in the
[dated record](acceptance/2026-08-07-phase-8-tner-fail-closed.md).
Exact branch head `a7e388257190527c3fc6ff29100e2f17af9abf94`
[passed all 11 CI jobs](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31126705388/attempts/2)
after the jobs canceled by the GitHub Actions incident were rerun. This main
integration contains that candidate; the record does not claim post-merge CI.
The accepted
[native-broker ADR](decisions/2026-08-07-native-broker.md) specifies the
owner-approved transport, admission, process, session, lifecycle, packaging,
and failure boundaries. Slice 1 protocol definition/conformance, Slice 2
authenticated transport/bootstrap/lifecycle, Slice 3 data/session boundary, and
Slice 4 Desktop migration are integrated. Branch checkpoint
`dc4aff6705e296890424b3fa4e88a8689300c7ed` fixed the installed profile to local
`thainer`/`fake`, closed the configuration P1, and passed CI 31393684276 (14/14),
cross-platform smoke 31393684282 (2/2), and independent review before squash
integration.

Phase 8 Slice 5 is a **production-qualified integration unit**. It migrates the
MV3
service worker to one registered Chrome Native Messaging port, with separate
broker scopes for each admitted tab and side-panel instance. Production
Extension code/manifest contains no localhost permission, HTTP client, port
probe, backend/native endpoint, credential, provider/TNER selection, replay, or
fallback. The thin adapter validates strict bounded stdio framing, exact
Extension origin, Chrome parent/process context, installed path/build/digest,
and broker role `extension`; it reserves stdout for frames. Desktop package
integration owns the adapter, manager, exact host manifest, and Windows/macOS/
DEB/AppImage registration. Chrome can start or join the shared broker without
the Desktop GUI. Installed Desktop/Extension remain local `thainer`; `fake` is
internal conformance only, with no credential store or provider command.

The repository-owned production identity is the owner-approved unpublished
Chrome Web Store item `kdjmkknedgmfphpkjhjdhmjadaelgggm`, exact origin
`chrome-extension://kdjmkknedgmfphpkjhjdhmjadaelgggm/`, recorded in
`config/chrome-extension-identity.json`. Its public DER key independently
derives the exact Item ID. The normal packager, with no synthetic override,
produced the exact-ID 22-entry ZIP with SHA-256
`785f94709ab55db6b340f7bff3805edd6057b3118416cd9d68cd9a5ed644d2bd`.
Synthetic identity remains test-only.

Real Chromium 145 loaded that production-keyed package and reported the exact
ID. The exact CI NSIS candidate then passed installed companion discovery,
health without the GUI, both Mask/Restore modes, reuse/isolation/disposal,
navigation/disconnect/restart failure handling, wrong-origin rejection, and
Desktop/Extension coexistence. Uninstall removed all four exact product HKCU
registrations, preserved unrelated keys, and left zero process delta. This is
exact-ID unpacked real-browser plus installed-companion evidence, not Chrome Web
Store installation or default-path NSIS evidence; the Web Store item remains
Draft/unpublished and no review/publication action occurred.
AppImage transient Desktop startup now
repairs and re-executes the manifest-verified stable Desktop, so Chrome and
Desktop share one exact admitted component root. Linux packaging also
preserves the frozen backend before linuxdeploy, restores it atomically after
linuxdeploy, and attests the restored bytes before AppImage replacement.
One private lock serializes complete AppImage stage+register and
unregister+remove transactions. Repeated exact repair leaves the verified
stable component inodes unchanged, preserving live-broker admission across
AppImage launches without allowing registration/component races.
Production candidate `cebf6eb` passed branch CI 31554602630 (14/14) and cross-
platform package smoke 31554602814 (2/2), including exact Windows, Linux, and
macOS production-origin manifests. The exact evidence and remaining Web Store
classification limitation are in the
[Slice 5 record](acceptance/2026-08-11-phase-8-slice-5-native-messaging.md).

The Phase 8 Slice 6 package/lifecycle work is integrated on `main` at
`21f921aa8edb7415551b76f6633ce52fc5e323c6`, tree
`a701eacfdbfce21a14e2c67c5bb492a0e5c7cb4c`. It was recovered from
preserved branch `codex/phase-8-native-broker-package-recertification`; exact
checkpoint `d1ee42557c2b620d37a07504aea9e33047599746` remains the pre-final local
executable/package record. Every installed client now admits only one complete
manifest-matched five-executable set. Admission verifies the fixed component IDs,
roles, relative names, SHA-256 digests, owner/mode/link state, Rust executable
build markers, and the identity of the already-opened executable before any PII
operation. The frozen Python backend is digest/file-identity bound rather than
claiming a Rust embedded marker.
A product-owned maintenance barrier stops new Desktop and Extension admission,
the least-authority maintenance client drains the broker and backend without
serializing or replaying mappings, and the repaired runtime starts with empty
scope/session state. Windows NSIS hooks, external Linux `dpkg`, and AppImage
stable-root transactions use that barrier/drain boundary before component
replacement or cleanup. The only enabled in-app updater path is Windows: Tauri
verifies the artifact and launches NSIS, which owns the transaction. macOS
relocation repair verifies the complete relocated set and repairs registration;
it is not component-replacement evidence. In-app macOS, DEB, and AppImage
updates are rejected before updater access; external/user package replacement
remains the supported path on those platforms.

Pre-final `d1ee425` installed evidence includes the production-keyed Extension in
Google Chrome for Testing 145, a normal-default-path NSIS companion,
Desktop-only, Extension-only, and simultaneous Desktop + Extension operation,
live upgrade, repair, interruption recovery, uninstall/reinstall, wrong-origin
rejection, restart invalidation, zero final candidate registration/process
delta, and real WSL lifecycle tests. That NSIS is 141,103,791 bytes with
SHA-256
`92b6840b53cbda6ee567a560dea70fbc59e651199391b94260b0797a313d8faa`.
The actual `a6318d8` predecessor also passed fail-closed live-Extension
transition and first-retry recovery. The pre-existing July installation was
restored byte-for-byte afterward. macOS relocation, real
DEB package-manager lifecycle, finalized AppImage extract-and-run/warm stable
`AppRun`, and normal FUSE when the runner supports it remain separately
classified workflow evidence. Recovery of the preserved exact head exposed a
shutdown-response race and an over-broad Windows process query. The final tree
accepts only boundedly proven endpoint inactivity after unavailable/timeout
drain results and queries only the five fixed package process names before exact
path validation. Review then closed AppImage drain reachability, extended-UNC
normalization, product-wide cross-session Windows transaction locking, fresh-
process NSIS receipt recovery with Windows PowerShell 5.1-compatible control-
file validation, and retry-idempotent partial DEB removal. The latest preserved-
head failures are also closed locally without weakening production checks:
Windows test copies explicitly receive destination ownership; the smoke release
marker is published only after complete pending-file write and flush; receipts
must be exactly 64 case-sensitive lower-hex bytes plus one LF; and the bounded
Linux lifecycle fixture nests a 45-second drain inside 55-second process and
75-second signal
deadlines. A later invalidated head exposed the separate Slice 6 full-package
fixture, uppercase PowerShell matching, and a live DEB harness that expected the
drained old Desktop to run the new package workflow. Those are closed locally by
setting every fixture destination owner, requiring case-sensitive receipt
matching, proving old-session invalidation in a bounded first phase, and then
re-attesting and fully smoking the newly installed Desktop. The earlier
obsolete run's NSIS tool download disconnected externally and still requires a
green exact-head replacement job. Later obsolete heads were invalidated when a
DEB assertion could overstate structured invalidation and when exact-head
execution exposed a bounded startup-busy transition, a maintenance handshake
deadline consumed by strict component hashing, and a Windows package failure
whose post-cleanup artifact retained only the exact marker without locating the
failing phase. A later final review invalidated its candidate because a late
maintenance connection could reset the request deadline and pre-request
operation timeouts were not retried. The current source requires explicit
second-operation invalidation, accepts startup busy only through bounded
readiness, prepares strict maintenance identity once, retries only pre-request
transient connections while the endpoint proves active, and threads one
absolute outer deadline through connect/hello, the single drain request, and
inactivity proof.

Candidate `854b6aba84cd7728cb0801fe4ed24b5cd206f783` was then invalidated:
CI run `31694499510` passed 13 of 14 jobs but failed the Windows installed
package, while cross-platform run `31694499478` passed macOS and failed Ubuntu.
Neither failed run is closure evidence. Local reproduction proved one real
pre-extraction failure mechanism: PowerShell 5.1 `Add-Type` resolved NSIS's
native `$PLUGINSDIR\System.dll` because that plugin directory was also the child
working directory. The hook now changes to `$INSTDIR` before executing the
embedded script. The executable regression reproduces the collision and the
corrected working directory, and an ordinary local Tauri NSIS candidate passed
the affected lifecycle. That evidence did not locate the hosted failure phase.
The Ubuntu log also lacked its final command, but review confirmed that the
workflow incorrectly required two concurrent AppImage repairs to both succeed
despite the deliberate nonblocking product lease. The replacement workflow
proves fixed status 75 and no component or registration mutation under a held
lease, then releases it and requires bounded release and repair. Once the Linux
package-layout step initializes its phase tracker, the `always()` artifact step
is configured to upload the latest-started coarse phase and any value-free
partial evidence; it does not guarantee an artifact for earlier failures or
runner loss.

Candidate `ea8eb7725bf6d31a95e4db03f99bca6bf46ef2e2` then passed all three
read-only reviews but was invalidated by exact-head execution. CI run
`31705549161` passed 13 of 14 jobs and failed only Windows installed-package
job `94465065578`; artifact `9183413143` records a full extracted payload plus
marker and uninstaller, absent registration, and failed primary/uninstall
cleanup, but no ACL or exact failing subcommand. Cross-platform run
`31705549230` passed macOS job `94465065913` and failed Ubuntu job
`94465065907`; artifact `9183764469` records
`deb-interrupted-remove-recovery` as the latest-started phase after completed
initial DEB, upgrade, remove, reinstall, and reinstall-smoke evidence, with no
AppImage evidence. Neither red run counts as closure evidence.

Source-path recovery found that elevated NSIS extraction can create the fixed
payload with process `TokenOwner` while strict installed admission requires
personal `TokenUser`; the obsolete artifact did not retain ACLs, so this is a
mechanism-consistent diagnosis rather than a retroactive ACL claim. The
post-install PowerShell 5.1 bootstrap now handle-validates only the marker,
optional exact receipt, fixed five components, component manifest, and
uninstaller; permits source ownership only from exact `TokenUser` or exact
process `TokenOwner`; rejects empty, reparse, or linked files; changes every
payload owner to `TokenUser`; and rechecks identity and owner before the
unchanged strict manager revalidates schema/build IDs/digests. Receipt-bearing
authority is never normalized, and ordinary admission still rejects group
ownership. The exact-head job records a privacy-safe owner-difference boolean.

The Ubuntu source path independently showed that `cleanup deb` required a
complete manifest before dispatch even though interrupted `prerm` had already
unlinked Desktop. Only that cleanup/shape pair now uses incomplete-removal
loading while still verifying the exact manager digest, build marker, path,
mode, owner, link, and identity; all other operations keep complete-set
admission. Fine-grained phase-start markers and 60-second bounds now surround
the manager and both retry calls. Actual PowerShell 5.1, WSL manager 22/22,
WSL Slice 6 10 active/4 expected ignores, both Windows native 167-active/14-
ignore matrices, and a fresh isolated local NSIS install/smoke/uninstall are
green. The affected Python selection collected 124 tests: 121 passed and three
platform checks skipped. These changes have local affected-lane evidence only
until the replacement head passes the protocol. Three exact-head read-only
reviews, branch and post-main CI/cross-platform smoke, reviewed-tree
equality, and deletion of only the integrated branch form the enforced closure
protocol. This text describes integrated truth only when that exact tree is on
`main` after those gates. See the
[Slice 6 record](acceptance/2026-08-12-phase-8-native-broker-package-recertification.md).

Candidate `097d41d4d7c141f0e001ded1cbb868c0c45ae7d7`, tree
`9d74a768814d18d064da11300de2da0e1428fe48`, passed its independent
correctness/security and package/deployment reviews but was invalidated by
exact-head execution. CI run `31713219318` passed 13 of 14 jobs; only Windows
package job `94491279795` failed. Artifact `9186697047` proves that the hosted
token had distinct `TokenOwner` and `TokenUser`, yet clean install, exact
inventory, four registrations, two-run installed smoke, and final cleanup all
succeeded. Failure occurred in the concurrent-lock phase. The generated Tauri
installer creates `$INSTDIR` through `SetOutPath` before the product preinstall
hook. The artifact did not retain each contender's exit status. Source ordering
and a local held-lock run of the exact custom-root artifact reproduced nonzero
exit plus only that empty directory, which the workflow incorrectly treated as
package state.

Cross-platform run `31713219299` passed macOS job `94491279822` and failed
Ubuntu job `94491280004`. Artifact `9186746050` contains complete DEB lifecycle
evidence and complete AppImage stable, contention, repair, reinstall, and
extract-and-run evidence. The job then emitted fixed failure stage
`appimage_repair` during normal FUSE launch. The pinned AppImage tool produces
root-owned SquashFS bytes; an exact pinned-runtime WSL probe confirmed that
normal FUSE presents them as UID 0 on a read-only mount, while extracted bytes
are effective-user-owned. Transient staging's additional effective-user-only
predicate therefore contradicted its already strict manifest admission. Both
failed workflows and their partial artifacts are historical diagnostics, not
closure evidence.

The replacement changes neither the production Windows lock nor workflow
success criteria. The lock probe accepts only an absent or exact empty,
non-reparse synthetic directory, still requires both installer exits to be
nonzero, re-attests installed digests and registrations, and deletes only that
verified-empty probe. AppImage transient staging accepts UID 0 only for the
exact canonical `$APPDIR/usr/bin` source on a read-only filesystem; it still
requires one owner/device, regular non-symlink one-link files, exact modes, and
the existing digest/build-ID checks. Stable published components remain
strictly effective-user-owned. Focused workflow checks and the updated 22-test
WSL manager suite pass. The replacement then passed all three independent
reviews, branch CI `31716919702` (14/14), branch cross-platform smoke
`31716919706` (2/2), reviewed-tree equality, and post-main CI `31719493359`
(14/14) plus cross-platform smoke `31719492934` (2/2). Slice 6 is integrated as
main commit `21f921aa`, tree `a701eacf`.

Authoritative PDF source-to-box
intervals are tracked as the separate third Phase 8 unit below.

The 2026-08-14 release-preparation branch audit began from exact clean `main`
`21f921aa8edb7415551b76f6633ce52fc5e323c6`, with 35 local and 35 live remote
branches. It recorded every tip, merge base, branch/main unique commit set,
content representation, completed-task mapping, PR state, protection state,
and ownership classification before mutation. No open PR, protected branch,
or unclear/meaningful unmerged work was found. Thirty-four fully represented
completed-task branches were classified SAFE TO DELETE and removed with normal
non-force remote deletion followed by local deletion; zero branches required
review. Cleanup left only `main` locally and remotely before
`codex/3.0.0-release-certification` was created from that exact clean commit.
The pre-deletion ledger is retained under `.git` with SHA-256
`B48C6E1229BE06744DEFF1E551989885572C973ED2659B2F44E5B9CB765E48DA`.

Phase 8 second-unit status:
**shared provider orchestration integrated; branch CI green; external
acceptance open**. CLI, HTTP/hosted, and worker roundtrip now delegate attempts
to the same protected-provider function. Every actual invocation gets a fresh
outbound-policy check, the same immutable masked text, and its own 60-second
timeout. The shared layer caps execution at three attempts, uses fixed one-
then two-second delays, and retries only timeout, network, HTTP 429, and HTTP
5xx failures. Tokenmind performs exactly one HTTP request per `complete()`
invocation, so there is no internal/outer stacked retry or provider-controlled
delay. CLI rollback, stateless mapping containment, fixed safe failures,
HTTP-v2/worker-v1 compatibility, and hosted allowlisting are covered by
synthetic automated regressions. The exact commands, evidence, and limitations
are tracked in the
[dated record](acceptance/2026-08-07-phase-8-provider-orchestration.md).
No live provider, installed/package, real-host, deployment, release, or
official-platform acceptance is claimed.
Exact reviewed code candidate `593b9d1e55ff0d1a20ef3117f29a5b7c0a5af7ca`
[passed all 11 branch CI jobs](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31177831416).
Final evidence branch head `4771abce475e6c43450d6dfa5729fa5e59d5715e`
also [passed all 11 branch CI jobs](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31178177864).
This record does not claim post-merge CI.

Phase 8 third-unit status:
**authoritative PDF source intervals integrated; local and branch CI gates
green; external acceptance open**. Every PDF `WordBbox` returned from
pdfplumber, the pdfium fallback, or hybrid/OCR assembly carries a half-open
source interval into the exact page-joined extraction text. pdfplumber uses its
character-to-text map; pdfium assigns offsets while consuming characters and
explicitly maps CRLF to LF; retained OCR fragments receive offsets when
assembled; and page joins shift local intervals by the exact separator length.
Redaction consumes
`Entity.span`, selects only intersecting boxes, validates source text,
non-whitespace coverage, page and geometry consistency, and fails before
output with one value-free error when mapping is missing or unsafe. No
document-wide, page-local, normalized, or fuzzy value search remains.

Adversarial source tests cover repeated identical values on one page and
across pages, independently selected occurrences, prefixes/suffixes,
overlapping and adjacent fragments, multi-box entities, newlines and page
separators, Thai combining characters, malformed/inconsistent/uncovered
intervals, invalid pages, missing provenance, retained exception graphs, fixed
HTTP-v2 containment, selected and unselected pixels, and existing
flattening/padding behavior. The full local matrix passed 2,331 Python tests,
123 JavaScript tests, 31 Rust tests, and 129 Office tests plus manifest,
TypeScript, and build gates. Ruff, version `2.5.0`, release readiness, and diff
checks are green. The formal performance command remains red against stale
sanitize and PDF anchors; three alternating 20-iteration comparisons against
exact base `37f1215` put the branch inside budget: candidate/base medians were
detect `9.39/8.74 ms` (`+7.4%`), sanitize `23.86/23.15 ms` (`+3.1%`),
restore `0.34/0.33 ms` (`+3.0%`), PDF `91.09/89.06 ms` (`+2.3%`), and
resident memory `155.4/155.9 MiB` (`-0.3%`). The committed baseline was not
moved. Exact commands and limitations are in the
[dated record](acceptance/2026-08-07-phase-8-pdf-source-intervals.md).
Corrected candidate `19b8b71b0c985f6a4939db0489a3300471fb2eaa`
[passed all 11 branch CI jobs](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31190057013).
Final evidence branch head `b3ff6059db2cbd72122dcb6436dde93f2be7437d`
also [passed all 11 branch CI jobs](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31190456107).
This record does not claim post-merge CI.
Optional live OCR, physical scans, handwriting, installed/browser/Office
hosts, hosted PDF resource/timeouts, deployment, and official-platform
acceptance remain open.

Phase 8 native-broker architecture status:
**ADR and Slices 1--6 integrated; release certification is in progress**. The owner
approved the hybrid per-user named-pipe/filesystem-UDS design, Chrome native
messaging, allowlisted Tauri bridge, broker-prebound authenticated loopback
backend, explicit unsigned-distribution limits, Desktop-companion
distribution, and Office exclusion from v1. Independent read-only review
passed exact architecture commit
`e8d62b3c4ce8c24bfc554149e1cb375e4db813a5`; its
[branch CI passed 11/11](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31197090383).
The Slice 1 candidate adds one machine-readable policy plus transport-free
Python/Rust implementations and shared exact-byte fixtures for canonical
framing, mandatory highest-common-version hello, immutable negotiated role
state, closed operation authorization and nested result schemas, fixed errors,
measured limits/deadlines, and no-data-replay semantics. Focused protocol gates
pass `146` Python tests and `20` Rust conformance groups plus two decoder
allocation regressions; the full Python suite passes `2,478` with five optional
OpenCV skips. Root JavaScript passes `123`, Desktop Rust `31`,
and Office passes schema/package/type/`129`-test/build gates. Independent
exact-index review passes with no unresolved finding, and reviewed
implementation commit `4ada40d203f98039c93b78d6fb0ab2a14df91f2d`
[passes all 11 branch CI jobs](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31216048119).
The Slice 2 candidate adds an on-demand single-instance Rust broker, a generic
control-only client, an explicit current-logon-SID Windows named-pipe DACL,
kernel PID/token/path inspection with held process handles, a Windows named
mutex, and an atomically assigned kill-on-close backend Job Object. macOS/Linux
use a private filesystem UDS with `0700` directory and `0600` lock/socket,
held `flock`, peer credentials, stable PID/audit identity, deadline-bounded
connects, and inode/symlink-safe stale cleanup. Central admission separates OS
context, package path/build/digest evidence, claimed role, and admitted role.
Those checks establish OS context and package consistency only; they do not
attest a publisher or claim protection from same-user malware, account
compromise, or replacement of unsigned binaries.

The broker prebinds one random loopback listener, passes a duplicate and two
independent per-boot credentials to the Python child only through inherited OS
state, and retains the listener/process-tree guard. Native publication exposes
only the pipe name or UDS path. Slice 2 enables hello, broker/backend health,
and maintenance-only drain/stop. Slice 3 adds all existing
protocol-v1 data operations through the broker-private authenticated HTTP-v2
child. It issues connection-owned scopes and broker session handles, binds
state to connection/scope/role/backend generation, disposes authority on scope
or connection teardown, never stores mappings, and never retries a data
operation. Unknown submitted work never escapes accounting: state-changing and
stateless uncertainty invalidate the affected authority and either confirm the
required authenticated disposal or terminate the backend and its complete
generation. Strict HTTP-v2 projection, operation-specific oversized-response
cleanup, fixed errors, authenticated Python detector budgets/watchdogs,
observable disconnect cancellation, and fixed global/per-role/per-connection
bounds are enforced through the final native response write. Windows pipe
backpressure is nonblocking and deadline-bounded in both directions. Slice 4
consumes these guarantees for Desktop without changing them. No Chrome Native
Messaging, Extension, Office, updater, upgrade, or uninstall architecture
changed; Slice 4 adds the native manifest to ordinary bundle layouts.

The integrated Slice 2 evidence passed `154` focused Python protocol/bootstrap tests
with two expected Unix-only skips and the full Python suite (`2,486` passed,
five optional OpenCV plus two Unix-only backend-bootstrap skips). The
Windows native matrix passes two decoder tests, 20 Slice 1 conformance groups,
33 Slice 2 runtime/resource tests, and five ignored subprocess fixtures. A
real WSL2 Linux run passes the Unix-specific permission, stale-path,
`SO_PEERCRED`/`pidfd`, descriptor inheritance, parent-death, control-client,
and lifecycle paths. Exact-head macOS CI passes 37 Slice 2 runtime/resource
tests, including audit-token identity, terminal-response retention, backend
lifeline, lifecycle, and cleanup. Root JavaScript passes `123`, Desktop Rust
passes `31`, and Office passes manifest/type/`129`-test/build gates. The formal
performance command remains red only against its stale sanitize anchor, but
three alternating exact-base pairs put candidate/base medians at detect
`5.72/5.83 ms`, sanitize `15.53/15.89 ms`, restore `0.24/0.25 ms`, PDF
`73.48/71.69 ms` (`+2.5%`), and resident memory `151.8/151.9 MiB`; every
branch-relative result is within the 20% time and 15%
memory budgets. A separate four-cycle backend test accumulates no broker
handles/file descriptors beyond its one-resource scheduling allowance. Exact
independent security review passes with no unresolved finding. All 14 jobs in
[implementation branch CI](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31251561221)
pass, including Windows, Ubuntu, and macOS native runtime jobs plus Windows
packaged-backend smoke.

Slice 3 local evidence passes 17 focused Python data-plane/context tests and
163 combined protocol/backend/data-plane tests with two expected Unix-only
skips, `2,495` full Python tests, and complete native
suites on Windows (`111` passed, five ignored fixtures) and real WSL2 Linux
(`110` passed, five ignored fixtures). The data-plane target adds 33
deterministic ownership/fault/race groups, eight private-backend executor unit
groups, and three real-backend lifecycle/cancellation/resource tests. Root
JavaScript `123`, Desktop Rust `31`, Office manifest/type/`129`-test/build,
Ruff over 229 files, rustfmt, warning-as-error Clippy, dependency/static,
synchronized-version, release, and documentation gates pass. Three alternating
exact-base performance pairs put candidate/base medians at detect `5.80/5.77
ms`, sanitize `15.63/15.61 ms`, restore `0.23/0.22 ms`, PDF `72.92/71.96 ms`,
and resident memory `154.8/153.9 MiB`; every branch-relative result is within
policy despite the pre-existing stale formal sanitize anchor. The expanded
real Windows forwarding loop (24 detect, 24 session lifecycles, eight
roundtrips, three PDFs) adds no handle and 12,288 bytes RSS after warmup; WSL2
adds no descriptor or RSS. The exact 70,953,644-byte frame passes on both
platforms, while repeated graceful and forced backend cycles stay bounded and
rotate generation. Slice 3 evidence is tracked in the
[current acceptance record](acceptance/2026-08-08-phase-8-native-broker-data-plane.md)
with a separate-context security review clear on the complete current diff.
Reviewed Slice 3 implementation commit `19b38392541bdb1c713a037799190409e71e61c1`
[passes all 14 branch CI jobs](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31262151884),
including Windows, Ubuntu, and macOS native runtime, Windows packaged-backend
smoke, and the core-only Python environment. Slices 1--3 are present in exact
integrated baseline `33989cac356330ff4efdb080c470b8bb63561c6a`.

Slice 4 Desktop local checkpoint: production webview requests now cross an
exact operation-specific Tauri allowlist into one typed Rust client admitted
under the existing protocol-v1 `desktop` role; hotkeys call that typed Rust
client directly. Each window owns a `desktop_ui` scope and hotkeys own a
separate `desktop_hotkey` scope. The webview retains only broker session
handles. Backend endpoints, ports, data/control credentials, native endpoint
details, mappings, provider/TNER credentials, and Python session identifiers
do not enter webview state. Production Desktop contains no direct backend/data-
plane HTTP client, port scan, Python launch, backend health/key storage,
provider implementation, or legacy localhost fallback. The updater remains a
separate Rust-side client for its fixed HTTPS release host. CSP contains no
backend origin, and the minimal webview capability grants only the event
listener needed for global authority invalidation.

The owner selected the credential-free installed-product option. The working
Slice 4 correction supports local `thainer` only, keeps `fake` solely as the
managed backend's internal conformance allowlist, and exposes no provider
command to the webview. Unsupported explicit engine/provider selectors fail
before broker connection or launch. Both native child seams construct their
environment by querying only a fixed allowlist of ordinary runtime-variable
names, never provider/TNER credential values, and pin `thainer`/`fake`.
Desktop and broker no longer snapshot remote configuration independently, and
non-`fake` Desktop roundtrip requests fail before backend submission. This
closes the identified configuration-ownership P1 in source without adding a
credential store or changing broader core, CLI, HTTP/hosted, or worker
capabilities. Exact branch full/package gates and independent review passed
before Slice 4 integration. Slice 5 now has its owner-approved production
identity plus exact-ID real-browser and installed-companion evidence. Slice 6
completes complete-set admission, maintenance drain, package replacement, and
owned cleanup; its exact-head review/CI, cross-platform, integration, and
post-main evidence classes are tracked in the current Slice 6 acceptance record.

Every Desktop product operation, including PDF, still runs through the Slice 3
private HTTP-v2 executor and shared Python core. Submitted requests are never
replayed. Bounded admission, renderer generations, out-of-band cancellation,
terminal restart-required state, and fail-closed connection teardown prevent
stale or unconfirmed work from publishing after close, reload, invalidation,
or cleanup failure. Clipboard, UI, and file publication occurs only after exact
result and safety validation; masked copy is reidentified and checked in native
code before the validated masked value reaches the clipboard.

The prior local implementation checkpoint passed 56
Desktop/native-package/backend Python
tests with two expected Unix-only skips on Windows, including 32 package-only
tests, and 145 root JavaScript tests across 20 files. The full Python suite
passed 2,544 tests with seven optional-platform skips. Desktop Rust all-feature
tests passed 23/23; native-broker library tests passed 13/13 on Windows and
14/14 on WSL2 Linux. The full Windows native-broker matrix passed 120 active tests with
eight intentional fixture ignores. The Slice 4
integration target passed the same nine active tests on both Windows and real
WSL2 Linux, with three subprocess fixtures ignored because the active tests
invoke them. Desktop/native Rust format and strict all-target/all-feature
Clippy gates were green. The Slice 4 live-test target covers
cold/existing/simultaneous broker
start, role/version admission, the complete native Desktop operation matrix,
UI/hotkey and cross-connection scope ownership, continuation/reidentify/
disposal, PDF, no replay, disconnect/timeout/uncertainty, malformed/oversized
responses, request-ID uniqueness, terminal limits, restart/stale generation,
and 24 repeated connect/scope/quit cycles without resource growth.

Historical dirty-tree evidence also installed an ordinary Windows NSIS
candidate with the component manifest beside the Desktop, broker, and backend.
That provisional installer's SHA-256 is
`7277341A62CEF70C8431BE4AEA51E9C0CA916E8C01ABDC8D0267C087869AE681`.
After installation into `artifacts/slice4-nsis-installed`, twelve total
launches exercised production package JavaScript through actual typed Tauri
commands: health, analyze, fresh/continuation sanitize,
native validated masked copy, reidentify, report, PDF, audit, and dispose/reset.
The harness did not exercise detect, guard, roundtrip, a fake-provider
roundtrip, a live provider, or live TNER. Five-run cold process time was
5,058.208 ms and warm median was 994.843 ms; cold Desktop ready was 4,121.709
ms and warm readiness ranged from 631.752 to 669.630 ms. Broker and backend
process deltas were zero. Peak resources were Desktop 34.812 MiB/538 handles,
broker 7.469 MiB/108, and backend 195.898 MiB/317.

This is exact dirty-tree installed-Windows evidence, not evidence for any clean
executable checkpoint. Clean predecessor
`c6dcad168395e44cc52a72674f0ff9d72483cbcf`
[passed all 14 CI jobs](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31325662048),
including two launches from a fresh isolated NSIS installation. Later
predecessor `0424716aabe5dcdbe07e79c9cd070879e6c7a44a` had a green macOS job in
[cross-platform run 31326610316](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31326610316):
it built and twice smoked an exact app copied to a new path. The overall run
failed on Linux, and that macOS job is relocated-app evidence, not installer,
DMG, notarization, or `/Applications` evidence.

Earlier predecessor `8be9523` passed all 14 jobs in
[CI run 31327288545](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31327288545)
including two launches from the exact isolated Windows NSIS installation. The
tested installer SHA-256 was
`dfa777757ec9961679dcd5074fa48cffb446166fb2b229d418e1f5eb816ebc6c`.
Its macOS job built, relocated, and twice smoked the app successfully in
[cross-platform package run 31327288595](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31327288595).
Its tested-app archive SHA-256 is
`5ec08f3d0d2ab051fa4f1b43d33fc31bd1770b86d33d06a402993c689335b96b`;
the two runs left zero broker/backend process delta. Cross-platform run
31327288595 is nevertheless red: Linux job `93279571732` failed before Desktop
launch because process inspection treated an unrelated protected same-UID
process as fatal. That is a diagnostic harness failure and supplies no Linux
DEB/AppImage result. Installed Windows NSIS, relocated macOS app, extracted
DEB, and finalized outer-AppImage plus verified warm-`AppRun` smoke are separate
evidence classes. Relocation and extraction are not installation evidence, and
the AppImage path is not normal FUSE/double-click or installation evidence.

Predecessor `6ad3422` repairs that Linux harness with
a process-name prefilter followed by exact `/proc` path and fail-closed
inspection for actual component candidates. Independent review found no new
blocker; 56 focused
package/workflow tests, Ruff, format, diff-check, and a real WSL clean-parser
probe pass locally. Checkpoint
[CI run 31328047804](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31328047804)
passes all 14 jobs, including the two-run installed Windows NSIS smoke.
[Cross-platform package run 31328047802](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31328047802)
is red. Its relocated macOS job passes with tested-app
archive SHA-256
`8d22957bba783737df954dee5c2a76a012ebeb1bb6f4c1f04886e93916245939`;
the extracted DEB also completes both runs, but AppImage component digest
verification fails before AppImage Desktop launch because packaging mutates the
component bytes after the pre-bundle hashes. No AppImage or full Linux pass is
claimed from that predecessor.

Predecessor `3836024` leaves the AppImage pre-manifest invalid until it can hash
the actual post-linuxdeploy AppDir components and repack with a checksum-pinned
plugin.
[CI run 31329794579](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31329794579)
passed all 14 jobs, but
[cross-platform package run 31329794568](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31329794568)
is red: macOS passed and Linux failed finalization before package smoke because
the first prefix guard did not allow appimagetool's defined `.digest_md5`
rewrite.

Predecessor executable checkpoint `73dcca4` copies the trusted original runtime
prefix before repacking. For the pinned, scrubbed no-sign/no-update invocation,
it parses both little-endian x86-64 ELF64 prefixes, permits mutation only in the
single non-executable, non-overlapping 16-byte `.digest_md5` section, rejects
executable load-segment overlap, and requires every other prefix byte to match.
Its 76 focused package/workflow tests and exact-delta independent review passed
with no P0/P1/P2.
[CI run 31345691672](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31345691672)
passed 14/14 including installed Windows NSIS. Its
[cross-platform package run 31345691667](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31345691667)
is red: relocated macOS and extracted DEB passed, but the AppImage harness
bypassed the outer runtime/`AppRun` and produced no marker.

Predecessor `8194c23` adds a separate precreated canonical private evidence
directory for AppImage native-start and every fixed marker, rejects an invalid
supplied root without a package-directory fallback, and creates marker files
without overwrite. An independent extraction attests finalized bytes;
repetition one executes the exact outer AppImage with
`--appimage-extract-and-run`, and the warm repetition re-attests the retained
live root before launching its `AppRun`.
[CI run 31348501253](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31348501253)
is red, 10/14, only because the new canonical-root test used non-portable path
spellings. Its installed-NSIS job nevertheless passed two launches and uploaded
artifact `9048319122`; the published
`545833b2d71d0cd8d77036e62da7a310a7e4cbc0dd272c6a6f3bbc10fbac71f6`
digest belongs to the GitHub artifact ZIP, not the installer payload. Separate
[cross-platform package run 31348501256](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31348501256)
passed 2/2. Its relocated macOS tested archive SHA-256 is
`48881bf929258fe980ff43b2dc4fa948b0a122e55cbb1508bdf9e817a533a624`;
the Linux artifact contains a directly smoked DEB with SHA-256
`5f6dde7aed7335ccb6944560fc4aecc993c09a6c6f5cbd18964b0ae2074ca127`
and finalized AppImage with SHA-256
`0b139d9f03d88d1a2984445de8d2e08d29fe42ce6120072524dd9ed5ed8cc17d`.
The latter passed with
`execution_mode=outer_appimage_extract_and_run_then_verified_apprun`.

Current exact checkpoint `492dad34361b09d7ffa58fa192a2447de7414418`
retains that production contract and repairs only portable canonical-path test
construction. Focused package/workflow Python tests pass 100 with one expected
Windows Unix-mode skip. Full local Rust runs of 19 default and 26 all-feature
tests preceded the final portability-only edit; afterward the exact private-root
test passed on Windows and real WSL, and exact CI confirms all 26 Desktop tests
on Ubuntu, Windows, and macOS. Affected Ruff, Python format, rustfmt, strict
Clippy, and diff checks pass. Exact CI source matrices recorded Ubuntu Python
2,574 passed, 32 skipped,
and one warning; Windows Python 2,571 passed, 35 skipped, and one warning; and
core-only 2,200 passed and 289 skipped. Root JavaScript passed 148 in 20 files,
Office passed 129 in 12 files, and combined Cargo source jobs passed 90
native-broker plus 26 Desktop tests with no failures or ignored tests.
[CI run 31349781519](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31349781519)
and
[cross-platform package run 31349781518](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/actions/runs/31349781518)
passed 14/14 and 2/2 respectively. CI includes two launches from the exact
isolated Windows NSIS installation and artifact `9048710352`; its published
installer payload is 70,500,529 bytes with SHA-256
`6ca6f5dc3fcdfc3dfc51c210ace1734bcede7f77298d1e3ea7019d9d8b5a425c`.
The separately published 70,501,963-byte size and
`961f9e8e25e150e0e5ad7e7124d56569b100e4fb671adfa7f5c51b3f4f8ab4ee`
SHA-256 describe the GitHub artifact ZIP.
The package run's relocated macOS artifact `9048609980` has internal tested
archive SHA-256
`15a64e25af00f30e288f62c837725cccb9e9588fc0f90d668a57d6d1164f0de8`.
Linux artifact `9048696066` contains the directly smoked DEB with SHA-256
`7411b1c976d66a7e4e4a48f757ad751eb69ac0a8a4105d318559ab64fc30bfb7`
and finalized AppImage with SHA-256
`915d4ebb139ee69a1d9514d6fdb306ab7e2bbd02e12a858bb4deaedcf5a1f5f7`.
The AppImage passed exact outer `--appimage-extract-and-run` plus verified warm
`AppRun`; every current package path left zero broker/backend process delta.

The package harness pins the offline `thainer` engine and fake provider and
does not exercise live provider or live TNER because the installed product
supports neither. It also does not establish manual
visual behavior or a public updater install. Slice 6 separately completes
supported-path relocation, upgrade/drain, interrupted-upgrade recovery, stale
cleanup, broad uninstall/reinstall recertification, and exact package-manager
evidence. Slice 5 has its owner-approved identity and production installed-
companion acceptance. Release publication remains blocked until a separately
authorized store/release action occurs. The detailed fault and evidence map is
in the
[Slice 4 record](acceptance/2026-08-09-phase-8-native-broker-desktop.md).

Final separate-context review of executable checkpoint `6ad3422` found no
additional P0/P1 in the complete Slice 4 diff or Linux candidate-filter repair.
Independent review of the `3836024` finalizer delta found no P0/P1/P2; exact
`73dcca4` review found and then closed executable-`PT_LOAD` overlap before
reporting no remaining P0/P1/P2. Review of the `8194c23` marker-root/AppImage
boundary and final `492dad3` portability re-review found no additional
P0/P1/P2. At those historical checkpoints the provider/TNER ownership decision
remained the sole confirmed P1. The owner subsequently selected the
credential-free installed profile, and branch checkpoint `dc4aff6` passed its
exact CI/package gates and independent review before integration. Separate
manual/lifecycle evidence classes remain open.

Provider-orchestration local checkpoint: the final Python suite passed 2,314
tests with five optional OpenCV skips and the existing Starlette/httpx
deprecation warning. The focused provider-path matrix passed 186, the broader
core/HTTP/hosted/worker contract matrix passed 383, root JavaScript passed 123,
Desktop Rust passed 31, and Office passed manifest, upstream-manifest,
package-manifest, type, 129-test, and build gates. Ruff, synchronized version
`2.5.0`, release-readiness, documentation, and `git diff --check` are green.
The formal performance command measured detect `6.82 ms`, sanitize `21.48 ms`,
restore `0.33 ms`, PDF `82.20 ms`, and resident memory `151.8 MiB`; it remained
red on the stale sanitize and PDF anchors. Three alternating exact-base pairs
measured candidate/base medians of detect `6.98/7.45 ms` (`-6.3%`), sanitize
`17.72/20.15 ms` (`-12.1%`), restore `0.26/0.28 ms` (`-7.1%`), PDF
`78.83/79.94 ms` (`-1.4%`), and memory `155.3/154.4 MiB` (`+0.6%`). The branch
itself is inside the 20% time and 15% memory budgets; the committed baseline
was not moved.

Phase 8 local checkpoint: the final Python suite passed 2,299 tests with five
optional OpenCV skips and the existing Starlette/httpx deprecation warning.
The focused TNER/core/adapter matrix passed 411, the local span/window matrix
passed 179, documentation passed 6, and Ruff, version `2.5.0`,
release-readiness, and `git diff --check` are green. A read-only
privacy/correctness review found whitespace-shortened spans, fail-open
malformed/unknown BIO streams, retry-category drift, provider-controlled label
logging, and unpinned populated-stage cleanup; all were fixed and the exact
current diff re-review found no remaining blocker. The formal performance
command remains red only on the older sanitize anchor: detect `6.01 ms`,
sanitize `15.76 ms`, restore `0.25 ms`, PDF `73.17 ms`, and resident memory
`152.9 MiB`. Three alternating exact-base pairs measured candidate/base
medians of detect `6.07/5.96 ms` (`+1.8%`), sanitize `16.13/15.96 ms`
(`+1.1%`), restore `0.25/0.24 ms` (`+4.2%`), PDF `73.61/74.36 ms` (`-1.0%`),
and resident memory `153.5/153.3 MiB` (`+0.1%`). The branch itself is inside
the 20% time and 15% memory budgets; the unchanged committed baseline and the
previously recorded sanitize-anchor explanation remain unchanged.

Corrective local checkpoint: the focused lifecycle/core/authentication/API set
passed 312; the hosted/API/shutdown/cleanup matrix passed 526; the full Python
suite passed 2,255 with five optional OpenCV skips; documentation passed 6;
JavaScript passed 123; and Desktop Rust passed 31. Ruff, version `2.5.0`,
release-readiness, and `git diff --check` are green. The formal performance
command remains red. Two consecutive follow-up runs measured detect
`5.70/7.50 ms`, sanitize `15.12/19.16 ms`, restore `0.24/0.27 ms`, PDF
`74.58/84.23 ms`, and resident memory `151.4/151.5 MiB`; the first was red only
on the established sanitize anchor, while the repeat was also over the stale
detect and PDF anchors. The timer-callback correction is unreachable in the
harness because it constructs the service without a timer factory, and it does
not change detection, sanitization, restoration, or PDF logic. The established
sanitize explanation still applies, machine variability is recorded rather
than suppressed, and the baseline remains unchanged. Two
read-only corrective reviewers found a scheduler-prerequisite fail-closed gap
and a Uvicorn record-shape drift gap; both were corrected with deterministic
regressions. The post-CI review additionally found the eager-callback failure
path fixed in `6cd109d1`. Their final exact-head review found no remaining
blocker, and the branch and post-merge workflows above are green. This closes
Phase 7 source integration only; it does not close any installed, real-host,
live-provider, official-platform, or Phase 8 trust-boundary gate.

The fixed localhost data plane used by Office still does not authenticate the
process that owns the port; current Desktop and Extension source no longer use
that path. Explicit TNER whole-operation failure has automated source
coverage but no fresh live response/mapping evidence, and shared provider
orchestration has no fresh live or packaged/real-host evidence. PDF boxes now
carry authoritative source intervals and are selected only by interval
intersection, with fail-closed mapping and negative-pixel regressions. That is
current-source automated evidence, not optional live OCR, physical-scan,
browser, installed Desktop, Office-host, hosted-resource, or official-platform
acceptance.

The 2026-08-06 exact-current formal performance command is red against the
stale committed anchors: detect `7.95 ms` versus `5.73 ms` (`+39%`), sanitize
`23.63 ms` versus `10.08 ms` (`+134%`), PDF `83.86 ms` versus `67.67 ms`
(`+24%`), restore `0.28 ms` versus `0.28 ms`, and resident memory `151.4 MiB`
versus `151.4 MiB`. Because unchanged code is also variable on this machine, a
three-pair alternating comparison against exact base `c533ec9`, using 20
iterations per process, compared the medians of the three process medians.
Candidate versus base was detect `9.78/9.49 ms` (`+3.1%`), sanitize
`28.69/18.37 ms` (`+56.2%`), restore `0.38/0.64 ms` (`-40.6%`), PDF
`131.22/111.28 ms` (`+17.9%`), and resident memory `153.8/154.7 MiB`
(`-0.6%`). Profiling attributes the sanitize delta to the approved longer
token identity crossing the 500-character outbound TB-NER chunk boundary; the
full original sanitized text is still scanned, and masking trusted ranges was
rejected because it hid adjacent residual PII. The exact-candidate sanitize
delta exceeds the repository's 20% time budget. The owner explicitly accepted
this measured privacy/security trade on 2026-08-06 so full original-text
residual scanning remains intact; this is not evidence that the performance
budget passed. The committed baseline remains unchanged, and formal and
same-environment results are kept separate.

The Phase 7 branch reran the formal gate on 2026-08-06: detect `5.74 ms`,
sanitize `15.01 ms`, restore `0.24 ms`, PDF `70.92 ms`, and resident memory
`153.3 MiB`. Only sanitize remained red against the committed anchor
(`10.08 ms`, `+49%`). This is lower than the exact-current result above but
does not convert the stale-anchor gate into a pass. Phase 7 does not change the
sanitize detection, replacement, or residual-policy algorithm, and the
performance harness constructs `SessionService` without a timer factory, so
the established owner-accepted privacy/security explanation remains the
applicable trade. The baseline was not moved.

## Status vocabulary

- **Verified** - implemented and covered on its intended automated/runtime path.
- **Verified locally** - passed a repeatable local runtime or emulator check,
  but is not evidence from the release transport or hosted platform.
- **Acceptance pending** - implemented, but a real provider, browser, package,
  or platform run is still required.
- **Hardening open** - dated evidence remains valid for its exact candidate,
  but a verified current gap blocks treating the affected path as accepted
  until the fix and its required recertification pass.
- **Blocked externally** - the remaining step needs a third-party contract,
  provider/platform state, or another change outside owner control. Owner-gated
  outward actions are labeled separately.
- **Optional** - supported only when an explicit extra is installed/configured;
  absence must fail clearly.
- **Documented** - a document deliverable, not code: the claims were checked
  against their sources and the codebase; there is no runtime path to verify.
- **Deferred** - intentionally out of current scope; the list lives in
  [ROADMAP.md](../ROADMAP.md).

## Core and API

| Feature | Status | Evidence / remaining gate |
|---|---|---|
| Structured + Thai NER detection | Verified | Shared `detect_all` path, regression tests, a dated pre-current-candidate Docker smoke, and Issue #82 coverage for malformed default-CRF cross-line/nested spans. Existing name hygiene and cue recovery produce bounded `NAME` spans while preserving independent following addresses; the Issue #82 fix required no value-specific rule or engine change. The later Track A weakness-closure campaign added bounded detector safeguards; its latest metrics and limitations are recorded above. |
| Detection benchmark | Verified | `python -m benchmark` scores synthetic and hand-authored gold corpora (including a negative slice) at entity, character, and exact-boundary level, plus an engine/strategy comparison and an external LLM baseline. Gold is at v4: adjudicated 2026-07-28 by two independent reviewers against [annotation-guidelines.md](annotation-guidelines.md) ([record](decisions/2026-07-28-gold-adjudication.md)). The latest local gold result is recorded above; reports are generated locally and gitignored. |
| Blind-v2 comparison | Verified locally | `python -m benchmark.blind_v2` scores the seeded synthetic freeze (seed `20261101`, hash in `benchmark/data/blind-v2-repro.lock.json`) for AI Guard, a regex baseline, optional Presidio, PyThaiNLP NER, and WangchanBERTa NER. A harder prose split is locked beside it (`benchmark/data/hard-dev.lock.json`, `benchmark/data/hard-test.lock.json`); only the dev half was read while detectors changed. The 2026-11-01 re-run of both scored sets, the ablations, the local `gemma3:1b` baseline, and the 18-question utility check are in [benchmark/blind-v2-results.md](benchmark/blind-v2-results.md). Gaps that block a best-in-Thailand claim are in [benchmark/gap-list.md](benchmark/gap-list.md). The sealed `blind-v2.enc` protocol corpus was not opened. These freezes are not a tuning set. |
| Government-form phase-2 probe harness | Verified locally | Source and sanitized-artifact hashes are pinned for official blank คร.1, ภ.ง.ด.91 and สปส.1-03; raw downloads are not committed, and tests reject metadata or hidden payload structures in the page-only copies. The strict runner builds and checks all nine synthetic inputs in one process, including real OCR, pixel coverage, residual, declared-decoy extraction, cardinality, unique-alignment, repository-state, dependency, and PII-free evidence checks. A current-tree WSL rerun at commit `ded67d3` completed all 9/9 inputs with 0 gate failures: 45/45 values removed, 0 exposed, 0 unmeasurable, residual OCR measured on 9/9, and no decoy false hits. The runner summary was conservatively labeled `functional_pass_repository_dirty` during the WSL run; immediately afterward both Windows and WSL `git status` were clean at the same commit. This is current-tree functional evidence, not general-form accuracy: synthetic expectations remain developer-authored and not independently adjudicated; ท.ร.6, physical scans, handwriting, and broader real-form annotation remain outside this evidence. Runtime remains a limitation: the WSL run took about 34 minutes and peaked near 8 GiB RSS, while the Windows run still has a 30-minute timeout/access-violation history. Exact sources, commands, results and limitations: [gov-doc-phase2.md](research/gov-doc-phase2.md) (2026-08-04 addenda), the superseded [dated failed-gate record](acceptance/2026-07-31-government-form-synthetic-run.md), and the gitignored run directory `benchmark/reports/gov-forms-2026-08-04-wsl-current-60m`. |
| Blind evaluation set | Verified | `blind-v1` frozen 2026-07-28: 185 documents / 479 entities across the 11 types plus a 52-document negative slice, authored and reviewed in isolated contexts and committed only as an authenticated blob + lock (counts pinned in `benchmark/data/blind-v1.lock.json`). Scoring is aggregate-only under a 6-reveal budget with a hash-chained committed audit log. Reveals used — the freeze baseline; campaign 1 (PRs #90-#91), which generalized (F2 0.837 to 0.903, non-overlapping CIs); campaign 2 (PR #93, NAME cues), which did NOT generalize (blind F2 flat, NAME precision 0.748 to 0.700) and pointed at engine-level work; campaign 3 (PR #97 + the fine-tune), which answered campaign 2's open question — blind NAME precision 0.700 to 0.922 at recall 1.000, overall F2 0.914, negative clean rate 0.346 to 0.423 ([results](decisions/2026-07-28-finetuned-ner-results.md)); and campaign 4 (the gov-form OCR detection gaps, main `553c8af`, owner-approved reveal on 2026-08-02, default CRF engine), which was generalization-neutral by design expectation — overall F2 0.8977 to 0.8981 (flat, within the 0.877-0.916 CI), precision and both family macros unchanged, negative slice byte-identical (54 FP, clean rate 0.346) — while character coverage recall rose 0.914 to 0.929 and exact-boundary recall 0.614 to 0.639 with one fewer false positive: no overfit to gold, no regression, and the campaign's OCR-specific gains are not expressible on a prose corpus (they are evidenced by the gov-form gate instead). Reveal 6 (same day, also owner-approved) spent the final reveal re-certifying the fine-tuned opt-in engine on the same code, since the campaign changed rule layers that engine shares: overall F2 0.914 to 0.916, exact-boundary recall 0.647 to 0.666, coverage recall 0.919 to 0.931, NAME precision 0.922 to 0.915 at recall 1.000 (within noise), negative slice identical (54 FP, clean rate 0.423) — the reveal-4 certification stands on current main. The budget is EXHAUSTED at 6 of 6; any future blind measurement requires a frozen blind-v2. Protocol: [2026-07-28 ADR](decisions/2026-07-28-blind-set-protocol.md). |
| Token and surrogate sanitization | Hardening open | New and existing sessions have automated coverage across core, Section 26, guard, response-render, audit-write, and outbound-policy failure seams; a separate cap-full regression preserves the selected victim and LRU state. For non-expiry pre-publication failures, published state, ordinals, timestamps, and concurrent restore/drop visibility remain unchanged. Current source returns no result for structured FP, text-based TB, detector-independent contiguous 6+ digit, anonymization, or missing-replacement failures. Caller mappings cannot reuse empty, identity, embedded-original, source-pre-existing, independently residual-looking, or wrong-token-type pseudonyms. Token mode mints `[<label>_<generation-tag>_<token-nonce>_<ordinal>]`; the non-secret tag carries 64 random bits and each newly minted token adds an approximately 94-bit nonce. This makes accidental identity reuse and preplay computationally impractical rather than impossible. The tag and complete tokens survive transaction clone/snapshot and are invalidated by `clear()`. Strict HTTP-v2 projection/client behavior has automated source evidence; package recertification remains open. |
| Local multi-turn re-identification | Hardening open | The backend vault, TTL/LRU, collision, and concurrency behavior have automated coverage. Shared-vault seed hardening rejects conflicting caller-held mappings and retains only opaque seed IDs in its structural audit; those seed paths serve stateless prior mappings rather than normal `SessionService` sessions. Direct restore defects surface as a fixed `RestoreTransactionError`, and expiry translation has no retained exception context. Current v2 sanitize/reidentify responses expose no explicit mapping DTO or original/token pairs. Namespaced-token regressions cover drop, restart, expiry, and eviction under token and surrogate replacement modes: stale text remains unchanged with zero replacements and one count-only foreign warning in the exercised cases. A separate regression shows a guessed future token remains foreign after the corresponding ordinal is later minted. Phase 7 gives each process one backend-owned earliest-deadline timer and makes `SessionService` the sole TTL authority for managed vaults: a session becomes unavailable at `age >= TTL` without a later request, while a request admitted before the deadline completes under the lifecycle lock. Successful sanitize/restore refresh once at commit; failed or repeated failed restore leaves the original access time, deadline, and timer unchanged. Standalone vaults retain exact-boundary idle expiry. Expiry, authenticated disposal, eviction, shutdown, and lifecycle failure clear the target vault and session-owned references idempotently; stale callbacks and restarted services cannot revive them. |
| Stateless core and worker sanitization | Hardening open | The in-process stateless result returns a transient mapping to its adapter for immediate restoration; the version-1 worker wire result omits it unless `include_mapping` is the exact JSON boolean `true`. Current-source regressions cover exact seed replay, conflict rejection, opaque IDs, audit retention after clear, detached cloning, every outbound residual class, missing replacement records, fixed value-free direct-core processing errors, throwaway-vault cleanup, and value-free `residual_pii` worker errors. Fresh stateless token calls use independent generation tags and per-token nonces; an explicit prior mapping with one admissible tag can continue that chain and reuse complete tokens. Exact grammar plus the residual policy must pass before a seeded token can be reused or select the minting namespace. Worker roundtrip now uses the shared protected-provider policy without exporting its transient mapping. The worker remains a local emulator, not official hosted delivery; official acceptance remains open. |
| Protected provider roundtrip | Hardening open | The 2026-07-23 live Pathumma run remains historical evidence for that exact candidate: raw synthetic PII stayed out of provider-visible text and every returned token restored. Current source gives CLI, HTTP/hosted, and worker one protected-provider choke point. Every actual invocation gets a fresh outbound-policy check and the same immutable masked text. The shared layer allows at most three attempts, passes a 60-second timeout to each, sleeps for fixed one- then two-second delays, and retries only timeout, network, HTTP 429, and HTTP 5xx failures. Other 4xx, malformed/non-text responses, validation, restore, and response-tail failures do not retry. Tokenmind performs exactly one HTTP request per `complete()` invocation and ignores `Retry-After`; no provider owns retries or fallback. CLI snapshot/rollback, HTTP v2, worker envelope v1, stateless mapping containment, fixed safe errors, and hosted allowlisting have automated regressions. This is source-level evidence only: the changed path needs fresh live-provider and packaged/real-host acceptance, and official hosted deployment remains a separate platform gate. |
| PDPA JSON analysis | Verified | Shared analyzer and API tests. |
| PDPA section 39 processing receipt | Verified | `ai_guard.py receipt issue\|verify` plus `pii_redactor/receipt.py`; 41 tests covering the digest contract, the PII-free property of both the JSON and the PDF, and the five verify outcomes. An independent adversarial review in a separate context (2026-07-29) found that the first implementation verified only the two digests, leaving every figure a reader actually looks at — entity/FP/TB counts, per-type counts, file size, source type — editable with no effect on the verdict; both sides now derive from one `_claims()` builder and a parametrised test forges each field in turn. The determinism claim is measured, not asserted: three subprocesses under `PYTHONHASHSEED` 0, 1 and `random` return one digest, and the test fails if that digest is the empty-result one. Note what that does *not* show: it varies the hash seed only, so machine- and dependency-independence remains unproven — which is why the receipt now records the PyThaiNLP version, the loose `>=` floor being the likeliest real cause of a mismatch. No HTTP endpoint by design ([record](decisions/2026-07-29-processing-receipt.md)). |
| PDPA section 37(4) breach assessment | Verified | `ai_guard.py breach assess` plus `pii_redactor/breach.py` and `pii_redactor/breach_pdf.py`; 42 tests across `tests/test_breach_assessment.py` (19), `tests/test_breach_cli.py` (15), and `tests/test_breach_pdf.py` (8) covering the affected-subject estimate's min/max bounds on crafted overlaps (all four strong identifier types, including `PASSPORT`), id/phone/email normalization (including a `+66` mobile or landline form folding to its domestic digits), exit codes 0/2/1, and the PII-free property of both the JSON and the PDF. No new retention: the distinct-value sets behind the estimate are plain in-memory sets dropped with the process, and the estimate itself is a range with a stated method and assumption, never a point estimate — no cross-document or cross-type person linkage is attempted. A review round found the first cut's failed-file reason leaked the full input path via stdlib exception messages (e.g. `FileNotFoundError`'s own text); every spelling of the path is now scrubbed to a bare basename before it reaches either artifact, and the same scrub now covers a corpus-level failure that escapes `assess_breach` itself. A second review round (2026-08-01) found and closed three gaps: a directory scan dropped non-`.txt`/`.pdf` files with no signal that anything was skipped (`files.skipped` now reports the count and basenames in the JSON, the PDF, and the CLI summary, and `files.total` counts everything the scan found rather than just what survived that filter); a failed `-o` JSON write after a successful `--pdf` write left a complete assessment PDF on disk for a run reporting a hard failure (the PDF this run wrote is now deleted, and the error message says so); and a corpus with no strong identifier rendered a literal "0-0 คน" headline, which reads as "nobody affected" rather than "no strong identifier found" (`subjects.no_strong_identifiers` now drives distinct wording in both the CLI and the PDF). No HTTP endpoint by design ([record](decisions/2026-08-01-breach-assessment.md)). |
| PDPA มาตรา 30 DSAR helper | Verified | `ai_guard.py dsar locate` plus `pii_redactor/dsar.py` and `pii_redactor/dsar_pdf.py`; 57 tests across `tests/test_dsar.py` (27), `tests/test_dsar_cli.py` (20), and `tests/test_dsar_pdf.py` (10) covering subject-line classification by shape, id/phone/email/name canonical matching (spaced/hyphenated ids, a `+66` or domestic phone form, case-insensitive email, a name with or without its title), value-based matching that ignores the detector's own type label for an entity (a phone the detector tags `BANK_ACCOUNT`, a name it tags `ORGANIZATION`, both still match, with a negative control confirming an unrelated value under the same label does not), one precision guard on that label-independence (a bare digit run merely starting `66`, e.g. an unrelated bank account, is never folded into a false phone match — only an entity whose own raw text still carries an explicit `+66` marker gets the international-to-domestic fold), the `weak_only` flag on a NAME-only match, the `third_party_possible` flag (including its own fixed note stating the flag is heuristic), exit codes 0/2/1, and the PII-free property of both the JSON and the PDF. This helper LOCATES, nothing more: it never copies, quotes, or excerpts a matched file's content, and the artifact never claims the access request is satisfied — the controller still serves it from the located files themselves. Subject identifiers are read only from a `--subject-file`, never accepted inline on the command line, so no value can enter shell history; no value or masked/hashed form of an identifier reaches stdout, stderr, the JSON, or the PDF on any tested path, including error paths (a whole-branch review found and closed the one exception that had skipped the path scrub other error paths already used). Matching is exact canonical equality only, no fuzzy matching, so an OCR misread of a scanned identifier will not match even where a human reader would recognize it as the same value — a known Track A limitation the artifact states rather than papering over. Reuses breach's own scan chain (`extract`/`clean`/`detect_all`/`assess_reid_risk`); its file-discovery and canonicalization helpers are now a pure move into shared `pii_redactor/scan_common.py` (the module's own `path_spellings` helper was extended afterward, which is not the same claim), with breach's own test files passing unmodified. A fix that came out of this work — repr-escaped doubled-backslash path spellings slipping past the existing scrub in a real stdlib `OSError` message — also hardened breach's own failed-file reason. No HTTP endpoint by design ([record](decisions/2026-08-01-dsar-helper.md)). |
| Thai PDPA PDF report | Verified | Whitelisted PII-free renderer and end-to-end tests. A second Windows font defect was found and fixed on 2026-07-29: `FONT_CANDIDATES` carried exactly one Windows entry, a Sarabun path no Windows edition ships, so every Windows machine except the developer's fell through to Helvetica and rendered Thai as black boxes — the packaged exe bundles no font at all, so that was every packaged user. Leelawadee UI (shipped with every Windows edition) is now a second candidate, which in turn exposed a reportlab defect: `PDFTextObject.setRise`'s "optimize out r0 Ts r1 Ts" branch rewrites the emitted operator without storing the new rise, stranding runs of text above the baseline for any font that positions marks by offset rather than glyph substitution. Repaired in `thai_pdf_text._install_rise_fix()`, applied conditionally via a behavioural probe so an upstream fix stops the patch cleanly. Measured on "รายงานความเสี่ยงข้อมูลส่วนบุคคล" at 26pt: 15 distinct glyph baselines before, 11 after, and the visible span "ยงข้อมูลส" returns to the baseline. The underlying exposure — that the product shipped no font and depended on whatever the machine had — is closed: `pii_redactor/fonts/IBMPlexSansThaiLooped-Regular.ttf` (OFL-1.1, converted from the WOFF2 already vendored for the UI, container change only) is now the first candidate and ships in both the wheel and the exe, so a report renders identically wherever it was produced. Thai text shaping had been broken from the renderer's introduction until earlier the same day: reportlab draws glyphs in code-point order unless HarfBuzz shaping is enabled, so every tone mark stacking on an upper vowel was dropped or misplaced — 23 literals in this report, including its own title and the `ADDRESS` label. Fixed by enabling reportlab's built-in shaping (`uharfbuzz`, now a core dependency) and drawing through `pii_redactor/thai_pdf_text.draw_text`, which pairs an invisible real-character layer with the visible shaped glyphs so the page stays searchable. Verified against headless Chrome as a reference renderer: mark positions match on every test word. Two accepted limitations: copying a whole page repeats each shaped line, and `pdfminer`/`pdfplumber` cannot reconstruct stacked Thai marks from any producer (measured — headless Chrome output fails the same way), so extraction-based tooling should use the `.txt` export instead. |
| PDF redaction and preview | Hardening open; authoritative mapping verified locally | Every returned PDF `WordBbox` now carries an exact half-open source interval assigned by the pdfplumber character map, pdfium character stream, or hybrid/OCR assembly and shifted with page separators. Redaction consumes `Entity.span`, selects only intersecting boxes, checks length-preserving Thai-digit equivalence plus non-whitespace coverage/page/geometry consistency, and fails before output on missing or unsafe provenance. Adversarial tests cover same-value and cross-page isolation, independent/overlapping/adjacent/multi-box entities, Thai combining characters, whitespace/CRLF/page joins, malformed/uncovered intervals, fixed safe errors, negative pixels, and existing flattening/padding. No value-search fallback or one-character exclusion remains. Current-source regressions also clear swallowed and translated extraction/mapping exception graphs. Historical optional OCR evidence predates this composition; physical scans, handwriting, broader real-form accuracy, browser/installed-host evidence, and hosted PDF resource/timeouts remain open. |
| Prompt-injection signals | Verified | Thai/English explicit rules plus a bounded normalization/intent layer; the five previously recorded bypasses are now passing regressions with ordinary-language negative controls. Canonical behavior remains warn-only. |
| Local HTTP authentication | Desktop and Extension broker-backed; Office hardening open | Current v2 separates optional data-plane API-key authority from the boot/control boundary. Target-bound single-use session disposal remains internal and is never given to storefront JavaScript. Desktop and current Extension source use authenticated broker connections, scoped handles, confirmed cleanup or generation teardown, and a broker-private backend; neither has a fixed-port fallback. Office still uses fixed-port HTTP and does not authenticate the process owning localhost port 8000 when its optional API key is unset. Installed Desktop/Extension construct safe child environments without querying provider/TNER credential values and pin local `thainer`/internal `fake`. OS peer and installed path/build/digest checks establish user/process context and package consistency, not publisher attestation. The Extension additionally requires the owner-approved exact Chrome origin and browser-process admission; exact-ID unpacked Chromium plus installed-companion evidence passes, while the unpublished Draft is not Web Store installation. Slice 6 lifecycle status follows the exact-tree closure condition above. Hosted caller authentication is separate. |
| Public errors and audit logs | Hardening open | Current-source API process-audit callers use fresh non-authorizing operation UUIDs for sanitize, reidentify, and roundtrip; local disk/stdout regressions reject live session IDs, originals, and pseudonyms. Bounded real-Uvicorn regressions send actual successful and rejected disposal requests through both launcher-configured and default CLI logging. They prove session IDs, derived authorization, control secret, request PII, and query authority are absent from captured stdout/stderr while a health access row and fixed `/api/session/[redacted]` row remain useful. Recognized access records discard queries; unknown record shapes are suppressed fail-closed. Desktop forwarding preserves backend redaction without reconstructing removed values. Successful sanitize records `prepared` before publication, while a safe blocked-attempt record may remain after rejection. HTTP endpoint and pre-response-start JSON-render containment, fixed request-validation responses, direct stateless/local-session sanitize and restore translation, provider translation, PDF/OCR swallowed-error disposal, and worker handler/runner barriers sever retained ordinary exception graphs and common mutable payload fields before emitting fixed failures or continuing a fallback. Ordinary `ExceptionGroup` members are recursively scrubbed, while the read-only group shell is dropped without logging/export rather than corrupted; direct or grouped process signals may propagate. Otherwise-unhandled downstream HTTP exceptions that reach the endpoint decorator become a fixed 500 rather than exporting their detail; provider and PDF boundaries retain their explicit safe 5xx/422 translations. Internal seed audit rows use opaque `seed:<uuid4>` entity IDs, exact replay adds no row, and conflict errors carry no values; retained rows remain structural after `clear()`. Current HTTP v2 uses exact stable-code envelopes without exception messages, provider bodies, excerpts, mappings, or credentials. Protected worker provider failures use fixed v1 errors after discarding the shared-call graph; some generic worker poison-envelope/log paths still expose reduced exception type names, so their cleanup remains separate hardening work. The process-audit schema retains the legacy `session_id` field name, operation-specific files still have no timed retention policy, and published 2.5.0 predates these current hardening changes. Official platform-visible logging remains open. |

## Compliance documents

| Deliverable | Status | Evidence / remaining gate |
|---|---|---|
| Standards mapping (ISO/IEC 20889 + มรด. 6:2566) | Documented | [docs/standards-mapping.md](standards-mapping.md), delivered 2026-08-01: a correspondence document, explicitly not a conformance claim. Grounded in what was actually readable: a publicly served ISO/IEC 20889 preview covering the complete terms clause (3.1-3.39), Clauses 1 through the start of 7.2, and the full table of contents — clauses 8-12 and the annexes are cited by title only, and the document says so; and the full 103-page มรด. 6:2566 PDF from the DGA standards site, read end to end, which defines no de-identification technique and references neither ISO/IEC 20889 nor any de-identification standard (the only ISO citations are 27001 and 11179) — so the มรด. mapping is at governance-practice level (classification, security/privacy dimension, breach-as-risk, the Data Agents processing-record duty), each row naming what the tool supports rather than claiming the practice is thereby satisfied. Every technique family the tool does NOT implement is listed by clause title, and the re-identification risk score is explicitly disclaimed as a heuristic, not a Clause-10 formal model. An adversarial review checked every ISO term number, every มรด. page citation, the negative claims, and every code claim against the repository before this row was written. |

## Integrations and storefronts

Enterprise staff application: local functional candidate with source, real
PostgreSQL/Keycloak and synthetic Chrome evidence. This is not production or
all-milestone acceptance; see the M3 progress and operator guide above.

| Feature | Status | Evidence / remaining gate |
|---|---|---|
| Pathumma provider | Hardening open | Repeatable live completion and protected-roundtrip checks passed for the dated 2026-07 candidate; marker preservation remains quality telemetry because a generative response need not repeat every entity. The current outbound-policy source path postdates that live run and must be rerun against Pathumma. |
| AI for Thai TNER engine | Hardening open | The live parallel `words`/`POS`/`tags` shape and end-to-end `PER/LOC/ORG/DTM` mapping passed on 2026-07-23. Current source now treats any failed explicitly selected TNER chunk as whole-operation `ner_unavailable` and any malformed, unequal, misaligned, or truncated token stream as whole-operation `ner_incomplete`; earlier results are discarded and later remote/provider/PDF/session publication is stopped. Fixed value-free metadata is covered across core, local-session/stateless, HTTP v2, hosted, PDF, and worker-v1 boundaries. The shared BIO/chunk engines (`thainer`, WangchanBERTa, and union) retain skip-and-continue behavior; the separate fine-tuned offset engine is outside this change. This changed path still needs a fresh live response-shape and end-to-end mapping run; historical live evidence does not certify it. |
| Browser extension | Slices 5--6 integrated; 3.0.0 publication candidate | Current source uses one service-worker-owned Chrome Native Messaging port to `th.ac.psu.aiguard.native_host`, separate broker scopes per admitted tab/panel, memory-only handles, strict sender/result validation, confirmed disposal or connection teardown, and no PII-bearing replay. Production manifest/code has no loopback permission, HTTP client/fallback, backend ID/credential, provider command, or remote TNER. The installed boundary is local `thainer`; `fake` is internal conformance only. Owner-approved production ID `kdjmkknedgmfphpkjhjdhmjadaelgggm` and its exact one-origin host manifest passed production packaging, exact-ID unpacked Chromium 145, installed NSIS companion, wrong-origin, scope/lifecycle, coexistence, upgrade, restart, repair, uninstall/reinstall, and simultaneous Desktop + Extension operation. Exact branch and post-main Slice 6 workflows are green. The 3.0.0 candidate adds a deterministic production-ID ZIP retained as a separate CI artifact for Chrome Web Store review; it is not a GitHub Desktop release asset. The Web Store item remains unpublished Draft until an exact reviewed ZIP is submitted and the store reports a later state. Raw text typed into provider-controlled DOM can still be observed before in-page Mask; the side panel is the stronger entry boundary. See the [Slice 5 record](acceptance/2026-08-11-phase-8-slice-5-native-messaging.md), [Slice 6 record](acceptance/2026-08-12-phase-8-native-broker-package-recertification.md), and [3.0.0 certification record](acceptance/2026-08-14-release-3.0.0-certification.md). |
| Desktop app | Slices 4--6 integrated; 3.0.0 release candidate | The published Windows `2.5.0` installer passed its exact historical checklist and Issue #69 revalidation; the [dated record](acceptance/2026-08-02-desktop-2.5.0-issue-69-run.md) remains valid only for that pre-broker artifact. Current source routes webview operations through typed Tauri commands and hotkeys through the authenticated `desktop` role, ships the production-keyed Chrome adapter and package registration, and implements strict complete-set admission, maintenance drain, updater ordering, atomic AppImage stable-root repair, DEB/NSIS lifecycle hooks, safe stale-endpoint cleanup, and package install/upgrade/remove/reinstall workflows. Exact Slice 6 branch and post-main workflows are green. The 3.0.0 release workflow is being certified for unsigned Windows x64 NSIS, unsigned/unnotarized macOS arm64 DMG plus updater archive, Linux amd64 DEB and finalized AppImage, updater signatures, checksums, and provenance. Updater signatures authenticate bytes but do not replace platform publisher signing. See the [Slice 6 record](acceptance/2026-08-12-phase-8-native-broker-package-recertification.md) and [3.0.0 certification record](acceptance/2026-08-14-release-3.0.0-certification.md). |
| Microsoft 365 Add-in | Acceptance pending | The shared task pane, host adapters, memory-only session state, writeback guards, and Word-only release-manifest gate remain in source. Current Office code validates exact v2 health/operation DTOs, gates readiness only on `api_key_required`, accepts control-plane protection without asking JavaScript for that credential, and blocks malformed/incomplete/unsafe Apply, Insert, or Copy paths. Automated manifest/type/build/unit gates cover the source. A dated exact-candidate local runner separately built and booted the packaged backend, validated strict-v2 health/token-sanitize/reidentify directly, and repeated that API flow through the Office HTTPS development proxy using pre-existing trusted certificate files that remained unchanged. This was not an Office JavaScript, Office-host, sideload, installed-package, provider, release, or deployment run. Office is outside broker v1; its web-add-in architecture is unchanged, and any future native host/bridge requires a separate ADR. The eight real-host/package gates remain unchanged: Word table and missing-key/provider/expired-session; Excel changed-value/formula cancellation and Pathumma Copy-only; PowerPoint unselected-content isolation, missing API 1.5, and Pathumma Copy-only; then the exact promoted three-host unified-package activation run. |
| CLI | Verified | Sanitize/report/receipt and end-to-end pipeline tests pass. Current source uses the shared protected-provider policy, rescans before every actual attempt, caps retries at three, and preserves its stateful snapshot/rollback semantics. This has automated evidence, while the changed provider path still needs the fresh live run tracked under Protected provider roundtrip. |
| Demo playground | Hardening open | The exact 2026-07-23 browser candidate passed token/surrogate roundtrip, protected Pathumma, guard warning, responsive layouts, report download/open, and positive PDF preview/download checks; that dated evidence remains historical and predates the current backend residual/v2/token changes. Current source validates strict v2 health/operation responses, fails residual or malformed results closed, reaches providers through the shared orchestration layer, and uses authoritative PDF source intervals behind the redaction route. Fresh browser/live PDF evidence remains open. |
| Scanned-PDF OCR | Optional | Dated pre-current-candidate evidence covers a Python 3.13 full environment, focused OCR/PDF tests, and real Thai PaddleOCR inference. The extra remains excluded from the packaged exe and hosted core image; the current HTTP-v2/PDF composition has not rerun that real inference. |
| WangchanBERTa/union and semantic detector | Optional | Requires ML extras; never selected silently. |
| Fine-tuned NER engine | Optional | `AIGUARD_NER_ENGINE=finetuned` + `AIGUARD_FINETUNED_MODEL_DIR`; weights and dev-calibrated thresholds live outside the repo, reproducible from `training/` (seeded, gold-disjoint, contamination-checked). Certified as the heavyweight opt-in by blind reveal 4: overall F2 0.914, NAME precision 0.700 to 0.922 at recall 1.000 ([results record](decisions/2026-07-28-finetuned-ner-results.md)). The CRF remains the default on latency. |

## Platform and delivery

| Feature | Status | Evidence / remaining gate |
|---|---|---|
| Docker image | Hardening open | The 2026-07-24 main-repository image remains historical. The selected sibling pins current core `8c6efef`; immutable port commit `e075ca4` passed exact provider-free local BusyBox `check` in 28.0 seconds and `deploy` in 244.3 seconds. Web, API, and core were healthy with matching source-revision labels. Local image IDs were `ff8d654a...` (26,020,221 bytes), `2df7e1ac...` (26,006,890 bytes), and `2d938778...` (809,367,137 bytes); these are local content IDs, not registry digests. Independent review found no remaining static blocker. Exact live acceptance, official runner build/digest, and platform evidence remain separate gates. |
| Resource profile | Hardening open; PDF gate red | The official Participant Guide lists 2 GiB/2 CPU for frontend and 4 GiB/4 CPU for API as adjustable examples below an approximately 13 GiB team total; it states no 1 GiB or 10 GB platform allocation. The sibling declares 256 MiB/0.5 CPU web, 256 MiB/0.5 CPU nginx API, and 6 GiB/2 CPU internal core, for 6.5 GiB/3 CPU total, with no bind mount. An exact local 100-request detect profile after warmup passed 100/100 at p50 6.02 ms, p95 7.58 ms, and max 12.57 ms. The exact one-page scanned-PDF route passed in 221.0 seconds but averaged about 1.93/2 cores and reached the 6 GiB memory ceiling (`memory.events max=8247`, no OOM/restart). This is a red deploy-readiness signal: the declared 20-page/300-second surface is not proven and is implausible under the current synchronous execution model. Platform p50/p95, disk, and resource evidence remain open. |
| Queue worker operations (provisional) | Verified locally | Detect, sanitize, analyze, restore, and roundtrip contract tests pass through the internal version-1 envelope. Current sanitize/roundtrip source rejects residuals with a bounded, value-free `residual_pii` error. Roundtrip now uses the shared three-attempt provider policy, reruns its outbound check before each actual invocation, keeps the same immutable masked text, and retains the existing v1 success/error projection without publishing the transient mapping. This remains a local emulator/compatibility boundary, not the official participant delivery path. |
| Provisional queue transport/envelope | Deferred | The HTTP-poll transport and job envelope are retained for local failure/retry evidence only. The official participant guide selects HTTP frontend/API containers behind a same-origin reverse proxy; it does not mandate FastAPI. Queue polling is not being promoted into the platform adapter. |
| Official platform HTTP adapter | Acceptance pending | The 2026-07-28 ADR selects the separate `aiguard-aift` nginx shell; main `app.hosted` remains a generic strict-v2 reference. The sibling has no independent service-version source: public unversioned and `/v1` aliases proxy strict contract 2. It pins current core `8c6efef`, returns minimized non-reconstructable projections, and implements the accepted signed-cookie caller boundary with separate caller, signing, core-proxy and provider secrets. Immutable port commit `e075ca4` passes exact provider-free local check/deploy, and independent review is complete. Current core now has authoritative PDF source-to-box coverage, but the sibling has not incorporated or exercised it. Public HTTPS routing, trusted proxy client identity for rate limiting, the PDF capability/resource decision, exact live acceptance, and official platform behavior remain unaccepted. |
| Official AI for Thai deployment | Acceptance pending | GitLab sign-in and Maintainer rights in the `team08` subgroup are verified; the guide and selected port agree on the assigned URL/ports and deployment template. Dated working-tree evidence covers auth failure paths, minimized responses, PII/secret log scans, a 10-minute fake-provider soak with restart, a 60-second live Tokenmind soak, OCR, and browser behavior. The final immutable code commit has exact provider-free check/deploy plus detect/PDF resource evidence, but no exact live acceptance. Its live acceptance waits for rotation/reissue of the Tokenmind credential exposed during a local Compose probe; the ignored local `.env` copy was removed. The PDF resource gate is red. Protected-runner confirmation, public HTTPS/proxy evidence, and the separately owner-gated GitLab project creation/push remain. See the [tokenmind detector + port ADR](decisions/2026-07-28-tokenmind-detector-and-aift-port.md). |
| Platform LLM endpoint | Acceptance pending | The platform issued an endpoint, model identifier, and secret out of band. No secret or account identifier is stored here. A dated pre-final sibling protected roundtrip passed and a two-worker 60-second live soak recorded 50 successes and no failures. The credential was later exposed in agent transcript output by a read-only Compose expansion and must be rotated/reissued before any further use; the residual ignored `.env` file was removed without reading it. Exact final-candidate live acceptance and a roundtrip originating from platform infrastructure remain open, together with quota, acceptable-use, logging policy, and timeout ownership. The model was separately scored as a detector on gold v4 ([ADR](decisions/2026-07-28-tokenmind-detector-and-aift-port.md)). |
| Retry/failure emulator | Verified locally | The repeatable local runner passes duplicate/conflict, failed submit, same-process provider idempotency, malformed/version/size, provider-timeout, handler-crash, concurrency, and honeytoken cases. It does not claim cross-process exactly-once or official ack/nack semantics. |
| Load/soak and official failure acceptance | Hardening open; official acceptance externally gated | Dated local current-core fake-provider and live-provider soaks are green, including restart recovery and zero observed failures in the recorded runs. Independent review, final local image identification, and exact provider-free check/deploy are complete. Exact live acceptance waits for credential rotation. Core PDF source-to-box correctness now has local automated evidence; public HTTPS/browser behavior, proxy-aware login limiting, sibling composition, and the red PDF resource/capability decision remain pre-push gates. Cold-build timing, outbound connectivity, platform-visible logs/resources, real proxy behavior, and sign-off require the owner-gated GitLab project creation/push and platform evidence. |
| Version/tag/release pipeline | 3.0.0 certification in progress | v2.5.0 remains the published Latest release from exact merge commit `24914ab`; its evidence applies only to that pre-broker artifact. The owner authorized 3.0.0 release preparation on 2026-08-14 from exact clean `main` `21f921aa`. `VERSION`, Desktop/Tauri, Extension, Native Broker, Office source metadata, lockfiles, and the deliberate server fallback now agree on `3.0.0`; the changelog and readiness checks agree. The first 3.0.0 workflow candidate was invalidated before tagging because review found mutable draft provenance, unpinned Tauri Linux helpers, missing execution of final production macOS/Linux package bytes, and inaccurate side-panel retention wording. The replacement workflow creates a draft only, pre-pins all five Tauri Linux helpers, finalizes/re-signs the exact AppImage, black-box smokes every final production package class, binds the closed draft byte set to a current-run source/run manifest, regenerates canonical updater metadata, redownloads and rechecks the final set, then attaches checksums/provenance. No `v3.0.0` tag or 3.0.0 GitHub Release exists yet, and the Chrome Web Store item remains separate. Windows stays unsigned under the accepted policy; macOS is unsigned and not notarized; Tauri updater signatures are required but are not publisher code signing. Distribution remains release assets rather than package-manager manifests ([record](decisions/2026-07-29-store-distribution-and-signing.md); [certification](acceptance/2026-08-14-release-3.0.0-certification.md)). |

## Internal-plan differences resolved here

- `block_on_guard=true` appeared in a working design but is not part of the
  submitted proposal or current API contract. Warn-only is the accepted design.
- Local `/api/reidentify` remains stateful by design. Hosted HTTP roundtrip is
  the preferred restoration flow because it consumes the mapping within one
  request and does not export it.
- The hosted service does not claim raw PII remains on the user's device.
- Detection accuracy remains the roadmap's declared normal Track A priority.
  The owner-approved eight-phase privacy/security/correctness hardening campaign
  is an explicit temporary exception, not a claim that Track A is complete.
  Remaining Office and platform items are acceptance gates tracked above, not
  deferred scope.

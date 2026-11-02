# M1 combined artifact qualification

Frozen source: `b4a8897edc277fcf6eb7f4e988b4bad83c5d6c55`. Qualification date:
2026-11-03. Result: **passed for the bounded Windows x64/Python 3.13 installed
profiles below**. This does not complete M1, M3 or production acceptance.

The test worker first verified its tool-prepared checkout, exact HEAD and
migrations 004/005/006 plus `governance/consent.py`, then read root/SDK rules,
masterplan M1 and verification rules, and addendum S1/S7. Its checkout was
`C:/Users/teera/.t3/worktrees/pdpa-enterprise-clean/t3-6791df77`; historical parent
paths were read-only references. No production code, lock, model, corpus or
performance baseline was changed. No push, merge or publication occurred.

## Observed checks

| Check | Observed result |
| --- | --- |
| Direct core/SDK wheels and sdists | Four artifacts from two successful offline build commands using uv 0.10.4, Python 3.13.12, setuptools 83.0.0 and `requirements-build.lock` |
| Archive-to-wheel rebuilds | Both rebuilt outside the checkout, offline/no-index/no-build-isolation; every unpacked byte including metadata and RECORD matches the direct wheel |
| Payload | All 136 core and 50 SDK runtime/resource files match checkout bytes; six migrations, connectors, enterprise assets/fonts, licenses and 29 canonical SDK aliases verified |
| Fresh enterprise pair | 46 hashlocked third-party packages; dependency check, actual three-argument installed checker, runtime probes and 13 enterprise module imports pass |
| Fresh SDK core-only pair | 26 hashlocked third-party packages; same checks pass; FastAPI and MCP are absent |
| Fresh SDK server/MCP/proxy pair | 56 hashlocked third-party packages; same checks pass before adding test tools |
| Packaged adapter and snapshot gate | Seven copied test files, **214 passed, zero failed/skipped/collection errors**, using six explicitly locked dev-tool pins |
| Artifact negatives | Six actual checker calls reject wrong core/SDK wheels, missing core/SDK wheels, missing installed core despite an ambient installed pair, and a colliding namespace owner |
| Package/source checks | Both enterprise wheel-resource checks, version check, pinned offline SDK lock check and diff check pass |

Runtime probes use real preprovisioned local thainer, conflicting root TNER
settings with an in-memory synthetic credential and fake engine only, and deny
socket connects. They cover token/surrogate roundtrips and prior mappings,
Session snapshots after environment changes, serial/Windows-spawn batches,
standalone pipeline config, warn/report, fail-closed errors, all canonical
aliases and installed origins. The copied snapshot tests also check exact
config-object forwarding and conflicting child settings. MCP tests exercise
actual in-process tools and Streamable HTTP ASGI caller binding; proxy tests
exercise fake upstream HTTP/SSE/late/transport/cleanup/cancellation failures.
These are synthetic transport checks, not external MCP host/provider acceptance.
Successful MCP detect/reidentify output can contain plaintext.

## Provenance and retained negatives

[The manifest](M01-combined-artifacts.json) records all six artifact digests,
39 exact expanded-command records through path variables, working directories,
exit codes, output digests, dependency/profile/model bindings and retained
evidence locations. The private temporary workspace is
`C:/Users/teera/AppData/Local/Temp/aiguard-combined-final-b8hsc1p7`.
The command output files contain fixed summaries or output digests; no request,
mapping, restored answer, provider body or credential was serialized.

All 206 inventoried build inputs match the frozen Git blobs after newline
normalization: 133 have only Windows CRLF versus Git LF differences; no other
source delta was found. Artifacts intentionally contain the observed checkout
bytes, not a claim of Git-blob-byte identity or identical compressed wheels.
Dependency wheelhouses were copied from existing caches and checked against
the current declared hashlocks. No registry fetch or editable install was used.
The thainer model/database files were copied and hashed from preprovisioned
assets; this is not independent model provisioning.

Batch1 remains immutable **negative** evidence. Its six artifact hashes were
rechecked against its original manifest, and its mapping-reuse/TNER failure
record was retained, not rerun or overwritten. The frozen snapshot-closure fix
was qualified only through the new pair. Two setup failures are retained:
the pinned builder lacked the driver's `packaging` dependency, and an unpinned
offline lock check selected Python 3.14.9 with no cached setuptools metadata.
The read-only enterprise interpreter ran the driver; builds and the successful
lock check used the pinned 3.13 builder. Neither setup failure was a behavior RED.

## Limits and next gate

No full source suites were rerun. PostgreSQL/IdP/browser/restart, other Python/OS
profiles, external hosts, live providers, Docker images, legal review and pilot
acceptance were not exercised here. Docker is absent. No database server was
started. M3's existing performance hold, original baseline and 20% time/15% RSS
budgets remain unchanged, with no exception or fresh measurement. Parent owns
independent integration review and CI; this worker performed its own evidence
and privacy review without spawning another agent. Retain this pair for that
review; any production-source change requires rebinding its affected evidence.

## Independent review disposition

The parent obtained a separate read-only adversarial review on 2026-11-03:
**CLEAR**, with no material finding. It independently checked all six artifact
hashes/sizes, both pairs' unpacked bytes including metadata/RECORD, all three
installed payloads, 12 evidence hashes, five driver hashes, 39 command/log
bindings, seven copied test hashes and the retained batch1 negatives. The
214-pass/zero-skip summary and its counter/origin assertions matched the
retained driver. This review did not rerun tests or upgrade the evidence level.

The reviewer confirmed 206 inputs match the frozen Git base after newline
normalization and no runtime/config/lock delta from `b4a8897` through `b468592`.
The parent checkout has 28 newline-only differences from the frozen child;
the byte-identical claim above remains limited to that child's observed build
inputs. Docker, database/IdP/host, performance and production gates remain open.

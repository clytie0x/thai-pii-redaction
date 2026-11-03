# M1 integrated M7-M10 paired artifacts

Observed 2026-11-03 on Windows x64. The [machine record](M01-integrated-artifacts.json)
binds one uncommitted source snapshot based on `05d5d77`, with 255 exact checkout
inputs and binding `303f0006f47d6930a05e762eab245218fadab6d9822537dc04d8cbb90a85503f`.
The [input hash map](M01-integrated-artifact-inputs.json) preserves the 255
checkout-byte hashes referenced by the machine record. It includes the combined
M7-M10 callers, migrations 001-013 and the isolated-build
import correction. This is bounded installed-artifact qualification, not main
integration, production acceptance or a release authorization.

## Observed results

| Scope | Result |
| --- | --- |
| Core and SDK direct wheels, sdists and rebuilt wheels | Six artifacts; direct and sdist-rebuilt wheels match every byte, including compressed bytes, under fixed `SOURCE_DATE_EPOCH` |
| Fresh enterprise, SDK core and SDK server/MCP/proxy profiles | Offline hash-locked dependencies, dependency check, supplied-pair checker, installed runtime identity and public runtime all pass on Python 3.13.12 |
| Installed compatibility tests | 214 passed, no failures, errors or skips |
| Negative artifacts | Six checker rejections and 20 runtime identity/cache rejections |
| Installed identity on Python 3.11.15 and 3.12.12 | Cache modes and optimization levels pass with semantic negatives; stdlib identity/cache scope only |
| Resources and provenance | Thirteen migrations, canonical runtime/assets, Thai fonts and private build-input resources checked; source and preserved earlier evidence unchanged |

The 67 expanded command records include working directories, exit codes and
output/log hashes. New environments and artifacts are under
`C:/Users/teera/AppData/Local/Temp/aiguard-integrated-v2-5c0fd80f0f824eaab4da890bced1e406`.
The copied machine record has SHA256
`75fa54779fdfbf67f73d6232fcd86f38306a5d8081a8e1eaacca1d20bb79455e`.
Builds use the existing pinned builder; dependency/model caches are read only.
No public-index fallback, model download, provider call or source fallback was used.

## Retained negatives and review

The earlier integrated build failed because standalone manifest loading eagerly
imported the runtime cache helper without an importable canonical package. That
failure, its source freeze and diagnostic artifacts remain retained separately.
The corrected lazy import preserves actual runtime cache verification; its
isolated regression observed RED then GREEN and its scoped source review is CLEAR.

Two V2 harness failures also remain retained with their original drivers. The
archive audit initially compared generated egg-info against stale ignored source
metadata. Its correction compares frozen source inputs and an explicit generated
metadata allowlist, retaining unknown/private-path rejection, metadata checks and
direct/rebuilt equivalence. The final aggregator initially counted uv output
control files as distributions. It now inventories the four control files
separately from the six distribution artifacts. Neither correction changed the
product or rebuilt its artifacts. Old batch1 negatives, the old b4 positive pair
and the first integrated build failure are unchanged.

A separate read-only review of this exact artifact/evidence set is CLEAR. It
recomputed all 255 source inputs, six artifact digests, 67 command/log records,
installed payloads, explicit archive allowlists and 262 preserved earlier
evidence files. It checked 85 evidence JSON/log files without finding serialized
sample PII, mappings, restored text or credentials. This review did not rerun
tests or expand the accepted platform/runtime scope.

## Remaining gates

The [combined record](M07-M10-integration-progress.md) separately records the
complete enterprise/source gates. Executing exact-candidate CI, images,
browser/IdP/restart and declared storefront host acceptance remain open.
The Python floor identity checks do not qualify full dependency/model
profiles there. MCP/proxy checks use in-process or controlled transports; they
do not establish external-host or live-provider acceptance. No PostgreSQL,
custody, real TLS, RPO/RTO, capacity, legal or organization pilot acceptance is
provided here. M3's controlled-performance hold and the unchanged baseline and
budgets remain in force.

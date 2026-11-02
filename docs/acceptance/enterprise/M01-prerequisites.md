# M1 prerequisites: current candidate evidence

Date: 2026-11-02. State: **implemented/local checks passed; S1 artifacts locally
verified; full M1 integration remains open**. Base HEAD is `6f1e63f`; runtime
candidate was uncommitted at artifact freeze and is preserved by the accompanying
feature-branch checkpoint. Main integration remains held.

This record supports the [Astra/Sol execution plan](../../implementation/2026-11-02-astra-sol-execution-review.md).
It is not M1 acceptance or a release/rollback certificate.

## Implemented and checked locally

- Canonical support for the SDK's eight additional structured types, generators,
  token labels, canonical matching and outbound labels; root vocabulary19->27.
- Juristic fullwidth/separator recovery regression reproduced then corrected.
  Other obfuscated new types may remain fail-closed rather than releasable.
- Immutable core/audit configuration, operation/lifecycle propagation, local
  cache initialization locking, directory-specific finetuned caches and uncached
  remote clients. SDK consumers are not yet rewired to those primitives.
- Config/credential traceback findings and Native cap/phase passthrough findings
  reproduced and fixed while preserving control marker type/identity/metadata
  and previously published sessions. Reference removal is not string zeroization.
- SDK proxy fixed metadata, strict successful text/SSE projection, held-tail
  disposal, joined cancellation cleanup and ASGI 2.3/2.4 cancellation behavior.
- Proxy AnyIO floor4.4 explicitly declared and capability-checked before startup.
  The lock adds only the corresponding metadata; existing package versions and
  artifact pins are unchanged.

## Observed results

| Gate | Result | Limit |
| --- | --- | --- |
| Root full suite | 3,297 passed,34 skipped,exit0 | Optional/host/live skips remain |
| Mandatory enterprise | 156 passed,zero skips,exit0 | Real local synthetic DB, not production |
| SDK qualified full suite | 2,038 passed,10 skipped,exit0 | Python3.13/locked local environment |
| Proxy focused | 143 passed on AnyIO4.14.2;143 on isolated4.4.0 | No Trio/live network/provider claim |
| Replacement proxy adversarial recheck | 78 assigned tests passed plus synthetic bridge probe; no actionable finding | Replaced a cancelled review; bounded source/ASGI scope |
| Gold-v4 regression | 252 synthetic documents/648 annotations;TP628 FP96 FN20 unchanged;313/313NERchunks | Development regression, not fresh blind or new-type accuracy |

Logs/XML/exit files and RED evidence are retained in ignored
`.superpowers/sdd/m1-canonical/`. The S0/S1 manifest below now binds the current
artifacts to source; these earlier totals alone do not bind a wheel.

## S0/S1 artifact qualification

The [prerequisite artifact manifest](M01-prerequisite-artifacts.json) binds six
fresh artifacts to the base HEAD, 171 runtime/build file digests, the original
tracked/untracked patch inventory and minimized evidence digests. All 38 runtime,
configuration and test fingerprints recorded before Astra's review still match.
The full 1,294-file inventory and ordered 26-step command record remain in the
ignored external workspace named by `artifact-workspace.txt`.

Both distributions were built directly as wheels and sdists with setuptools
83.0.0, uv 0.10.4 and the existing build constraints. Wheels rebuilt from those
archives outside source with `--offline --no-index --no-build-isolation` contain
identical unpacked bytes: root 113 members/106 runtime resources, SDK 57/50.
All runtime/resource files match source, including `config.py`, SQL, static assets,
fonts and license texts; private paths and unexpected wheel namespaces are denied.

Fresh outside-source venvs installed the exact root enterprise and SDK proxy
wheels through an offline resolver using the 46 cached dependency wheels whose
hashes match the earlier trusted manifest. Dependency checks pass. Each installed
package passed nine synthetic detection/span vectors and 18 token/surrogate
roundtrips. Product module origins and every installed runtime resource were
checked against the supplied wheel. The local thainer 1.4 model was reused and
hashed; this is not an independently provisioned model environment.

Fresh installed root configuration tests pass 43/43; the five installed SDK proxy
test modules pass 206/206, zero skips, including synthetic failure/cancellation
paths. The SDK run retains one upstream Starlette deprecation warning. These
checks do not replace the earlier full source suites or qualify a live provider.
An absent valid first-party wheel path and offline resolution in an empty venv
both fail. The initial helper's incorrect corpus name and malformed negative-test
filename are retained and distinguished from the corrected qualifying runs.

S0 also recovered the completed replacement proxy review: 78 assigned tests plus
a synthetic ASGI 2.3/2.4 bridge probe, no actionable finding, AnyIO 4.14.2 only.
The cancelled predecessor remains distinct. A fresh read-only S0/S1 adversarial
review is CLEAR after correcting the cached-wheel count from 47 to 46. Its hash
is recorded in the manifest; neither approval nor these artifacts grants M1/main
acceptance. The runtime patch is preserved together because configuration,
detector, leak-guard and test changes do not have a qualified partial-file split.

## Performance hold

A valid same-interpreter five-iteration control/candidate pair observed
detect5.31/5.25ms, sanitize13.86/13.98ms, restore0.28/0.34ms and PDF67.09/67.22ms;
sampled resident memory151.5/151.2MiB. Restore is21.4% slower in that pair.
Both arms also exceed the pre-existing sanitizer anchor. The earlier incomplete
control lacking psutil is retained and is not presented as full memory evidence.

The reverse mapper performs an informational FP scan. A bounded, balanced
component diagnostic measured215.733/272.967 microseconds per call on the same
fixture with identical entity semantics, consistent with much of the observed
restore cost. It does not establish complete attribution or controlled acceptance.
Formal negative results remain; baseline/tolerances are unchanged. M3's separate
unexplained outlier and the owner's controlled-environment hold remain open.

## Remaining acceptance work

- Current Windows/Python 3.13 artifacts are locally qualified with a clear
  independent S0/S1 review and source-bound checkpoint; other platforms,
  optional engines, MCP hosts and actual images still need their own evidence.
- Complete executable adapter contracts and preserve prior mapping/restore
  behavior, correct reporting projections and honest MCP plaintext boundaries.
- Migrate SDK Python/CLI/HTTP/MCP/proxy and Hosted to the canonical core, then
  remove separately maintained engine copies after all consumer checks.
- Finish direct dependency/version/lock and offline container arrangements.
- Obtain controlled performance and every actually executing green CI job;
  GitHub privacy purge/public visibility and real image/host gates are separate.

No package publication, deployment, main integration or operational proxy
enablement is accepted by this prerequisite record.

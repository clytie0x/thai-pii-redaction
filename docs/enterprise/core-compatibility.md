# M1 compatibility inventory and decision boundary

Date: 2026-11-02. Inventory baseline: `a5b6f64`; runtime source in the imported
subtrees remains unchanged. Subsequent CI/test-only changes are recorded below.
State: **inventory reviewed; implementation/acceptance open**.

Source/test/artifact fingerprints and bounded qualification counts are in the
[M1 CI manifest](../acceptance/enterprise/M01-ci-manifest.json).

The owner requested one shared protection core and independent adversarial
checks at every milestone. Source inspection confirms that the three existing
implementations have public policy and packaging differences. A direct import
replacement cannot satisfy M1. This inventory does not authorize a contract
change, establish equivalent accuracy, or certify an installed artifact.

## Current implementation and caller contracts

| Boundary | Root | Hosted | SDK |
| --- | --- | --- | --- |
| Maintained source/import | `pii_redactor/`; local/API/native callers | `apps/hosted/core/pii_redactor/`; Hosted gateway/Protected Markdown | `packages/amphrang/amphrang/engine/`; `amphrang` facade, local server, MCP and proxy |
| Sensitive findings | Report/warn; not automatic Section 26 masking | Imported root-derived behavior; must retain explicit Hosted qualification | Accepted frozen SDK ADR adds person-linked sensitive spans and residual checks |
| Detection differences | Structured recovery admission | Imported detector ends before root's newer structured recovery | Numberless-address relabel, wider token labels and sensitive merge |
| Engine selection | `AIGUARD_NER_ENGINE`; TNER is an explicit supported selector on its path | Core revision plus Hosted configuration; do not inherit local credential policy | `AMPHRANG_NER_ENGINE`; no equivalent TNER selector in the inspected implementation |
| Source offsets | Source-slice spans; Thai-digit normalization retains length | Source spans/bbox provenance retained in the imported core | Public `Entity.original_text` uses the original source slice; normalization retains length |
| Mapping ownership | Explicit Python API or local in-memory session service; HTTP/native project opaque references | Hosted stateless request processing; raw PII reaches the Hosted service; not an on-device claim | Explicit Python `anonymize` returns a mapping; MCP projects an opaque handle; proxy restores successful replies locally |
| Provider failures | HTTP provider errors become fixed contract errors | Must qualify exact gateway/core path; root HTTP tests do not establish Hosted behavior | Proxy currently restores original values into JSON/non-JSON/streaming error bodies; existing tests assert that behavior |
| HTTP metadata | HTTP v2 root header/DTO renderer | Hosted caller/auth gateway is separate | HTTP v2 uses its own header name; facade renderer must remain adapter-owned |
| Distribution | `aiguard` installs `pii_redactor` and `app`, including broader dependencies/assets | Digest-pinned image, hash-locked base and security overlay, verified baked NER assets, offline runtime | Metadata promises an `amphrang` namespace without generic `app`/`pii_redactor`; base dependency footprint is smaller |
| CI inventory baseline | Root Python/JS/native/Office/container jobs plus mandatory enterprise job | Script-style contracts/Node tests declared in nested GitLab CI | Nested GitHub workflow exists but is not discovered as a root workflow |

Source offsets and mappings must be tested at their named boundaries. Sharing a
version number, HTTP protocol number or detector filename proves no equivalence.
The SDK's explicit Python mapping return is not permission to expose it over
HTTP/MCP. Hosted request memory is not the local reversible vault.

## Verified evidence locations

- Sensitive policy: SDK `amphrang/engine/detectors/aggregate.py:321-328`,
  `anonymizer/anonymizer.py:395-396`, `engine/leak_guard.py:465-479` and its
  accepted `docs/decisions/2026-08-27-section26-span-masking.md`; root
  `pii_redactor/report.py:24` and `detectors/aggregate.py:328-350`.
- Error behavior: SDK `amphrang/proxy/server.py:166-198` and
  `tests/test_proxy_server.py:269-303`; root `app/server.py:1479-1490`.
  The parent inspected both the current renderer and its existing test. This
  is a pre-existing contract conflict, not a newly introduced M3 regression.
- Packaging: SDK `pyproject.toml:27-32,77-93`; root `pyproject.toml:47-58` and
  `requirements.txt`. The parent verified the namespace/dependency declaration.
- Coverage: root `pyproject.toml` test paths/lint exclusions, root CI, SDK's nested
  workflow, Hosted `.gitlab-ci.yml:42-70`, Compose's `./core` build and the
  monorepo import ADR. Hosted contracts include direct Python scripts and Node
  checks; `pytest apps/hosted/tests` alone would not run the declared inventory.
- Provenance/offline behavior: Hosted `core/Dockerfile:23-37`,
  `sync/sync_from_upstream.py:35-49,132-146`, and SDK `Dockerfile:18-27`.
  Image build/import tests remain required; these source lines are not an
  observed no-egress runtime acceptance.

The separate-context adversarial reviewer inspected live callers/imports,
metadata, Dockerfiles, sync and CI without opening private fixtures, changing
source, installing dependencies, or claiming runtime equivalence. Parent
inspection confirmed the material sensitive-policy, error-contract,
namespace/dependency and workflow-inventory findings before drafting the
[proposed decision](../decisions/2026-11-02-shared-core-compatibility.md).

## Required adapter qualification

Before replacing any engine, record an adapter's explicit policy identifier,
selected engine, supported types/labels, source-span convention, mapping boundary,
error projection, optional assets and source fingerprint. Test the following:

1. Each declared policy/contract difference has a named expected result; an
   unclassified difference fails the compatibility matrix.
2. Thai digits, width/control/separator variants, repeated/overlapping entities
   and structured field boundaries preserve exact source slices and type labels.
3. Missing/unsupported explicitly selected engines fail; no adapter changes
   process-global environment variables temporarily to select its policy.
4. Success restoration follows the explicit Python/proxy boundary. HTTP/MCP,
   errors, audit and logs cannot emit mappings, raw/provider error bodies or
   restored sensitive values.
5. Clean SDK wheels preserve the approved namespace/dependency surface and run
   outside the checkout. Hosted images retain separately reviewed configuration,
   model digests, offline behavior and deployment identity.
6. Root, Hosted and SDK checks each run from their own directory and locked
   environment. Root Docker smoke is not Hosted image acceptance. CI must
   actually execute every relevant job; configured jobs are not passing jobs.

No detection score from a closed holdout transfers automatically to a new
adapter/profile. Use regression/development probes and retain independent M2/M11
quality gates.

## Work that can continue before an owner decision

- Add explicit, non-deploy root CI jobs for existing SDK/Hosted checks; retain
  each subtree's locks/build inputs and classify local/environment failures.
- Add synthetic matrix probes that record the current differences without
  changing default policy or marking them desirable.
- Prepare clean wheel/image import and provenance checks and bounded rollback.

Changing SDK sensitive behavior, restoring provider errors, replacing imports,
adding the root wheel as an SDK runtime dependency, or removing engine copies
must wait for the reviewed compatibility decision. M1 remains open.

## CI qualification work in progress

The new root `subtree-checks.yml` candidate calls Hosted's existing simulator
only with `--job check --gitlab-network`, which retains its complete declared
Python/Node check inventory. It separately builds the actual Hosted core context,
binds/verifies the OCI source revision and exercises baked model assets/detection
with container networking disabled. This is a Docker-executor approximation,
not the organizer's runner or a deployment. Local Docker is unavailable.

SDK jobs pin uv 0.10.4 and use the unchanged `uv.lock` in bare-core and server/MCP
profiles on Python 3.11/3.13. Frozen dependency sync excludes the project, then
installation constrains the build backend with the existing root build lock.
This avoids inventing an unsupported `uv sync --build-constraints` flag; the
actual installed CLI/tagged source were checked. The bare profile explicitly
asserts optional FastAPI/MCP are absent. A built wheel is installed into a fresh
target, its source bytes/namespace/import origins checked, and a synthetic public
detect/anonymize/restore roundtrip runs offline. The check uses `RestoreResult.text`.

An independent CI review found the initial restore-result type mismatch and
private `.env`/wheel install-scheme blind spots. Executable positive/negative
controls reproduced those findings, then passed after correction. Root coverage
guards started with four failing cases; the bare-profile gap also had a failing
case before it was added. Actual SDK Python 3.13 Windows full-extras tests now pass
**1,989 cases with 10 skips**. Two Git
audit guards had incorrectly skipped because they required a `.git` directly
inside the imported SDK. A real `git rev-parse` guard now runs both in the parent
worktree; both passed without opening/revealing a held-out corpus. The actual
SDK 3.13 installed-wheel offline roundtrip also passed (wheel SHA-256
`96842dd42b1d15034d06e5ccbd5cbde3a50bb40bf38f52e047d0d6d18caf8664`).

The separately installed bare profile proves FastAPI/MCP are absent and passes
**1,606 tests with 229 optional-feature/ML/host/live skips**. Its first full run
found two proxy CLI test failures: feature-present cases imported uvicorn or
expected server validation without the optional proxy dependencies. Parent
verified that the CLI already returns the fixed install-extra guidance before
starting a server. Those feature-present tests now require the extra, remain
executed by the full profile, and an added forced-missing-extra test executes in
both profiles. This changes test qualification, not the proxy's runtime/error
contract. Original failing logs are retained. Git audit guards execute in both
profiles. No closed corpus is revealed or edited.

The final parent control-flow review caught an image-smoke false positive:
running the asset validator as `__main__` through `runpy` raises `SystemExit(0)`
and would exit before detection. A failing executable control reproduced it.
The smoke now checks the validator as a subprocess before detection, and tests
prove both that successful assets reach inference and failed assets stop it.
These are control-flow unit tests; Docker execution remains unverified locally.

The CI candidate is **partial coverage**, not complete M1.4 acceptance: executing
GitHub jobs is billing-blocked; Hosted runner/image checks need Docker; SDK's
declared Windows CI, API collection, performance and Docker checks have not yet
all been moved to the root workflow. The checked source/subtree contracts stay
separate from proposed core/profile/export changes. No engine implementation,
public facade, frozen evaluation data, SDK lock or deployed service was changed.

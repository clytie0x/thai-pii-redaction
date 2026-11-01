# Shared-core compatibility and SDK boundaries

Date: 2026-11-02. Status: **proposed, not owner-approved or implemented**.

## Problem and existing alternatives

The [M1 inventory](../enterprise/core-compatibility.md) identifies three live
engine copies with different policies, install surfaces and provider-error
behavior. The root operating rule keeps Section 26 as warn/report. The SDK has
a separate accepted/frozen person-linked sensitive-masking ADR. Its metadata
also promises no generic top-level `app`/`pii_redactor` imports. Direct root-wheel
dependency or import replacement changes those contracts. Keeping independently
maintained copies retains drift and does not satisfy one-core M1.

This decision concerns expensive-to-reverse public behavior and packaging.
It needs separate adversarial/builder review and owner approval under AGENTS.md.
General M0-M12 execution authorization does not decide these alternatives.

## Proposed boundaries

The canonical authored implementation remains under root `pii_redactor/`.
Storefronts keep their public DTO/error renderer, lifecycle and trust boundary;
they cannot create separate detector/vault/provider implementations. Changes
are adapter-by-adapter, with synthetic source-span, privacy/failure, clean-wheel
and exact-image tests. No old implementation is removed before every live
consumer/build entry and rollback path is accounted for.

Each adapter resolves its existing configuration names into an immutable core
configuration and retains its approved engine/credential allowlist. The same
configuration governs detection, sanitization, residual checks and output
validation. Import transformation cannot silently rename public configuration
or enable previously unsupported remote engines. Test conflicting root/SDK
settings and concurrent profile isolation; never temporarily mutate global
environment variables. In particular, root TNER support must not enable remote
processing merely because an SDK artifact now contains the corresponding code.

### Choice 1: sensitive policy

**A. Preserve the SDK's documented behavior through an explicit compatibility
profile in the canonical implementation.** Root/local/Hosted defaults retain
their reviewed report/warn behavior. Only the SDK's existing public entry points
select the SDK profile through explicit configuration, never a process-global
environment mutation. Profile-sensitive detection, labeling and residual checks
live in the canonical core, not a second SDK detector. This requires the owner
to approve a narrow SDK policy exception to the current root Section 26 rule;
it is not implicit in the frozen SDK ADR or this proposal.

**B. Migrate the SDK deliberately to root report/warn policy.** A versioned,
documented public behavior change replaces its frozen sensitive-masking policy.
Migration examples, explicit warnings and matched per-category/protection tests
must explain the loss of automatic masking; the release cannot silently claim
the old SDK protection. Do not change root defaults to mask sensitive findings
everywhere as an incidental consequence of consolidation.

Builder recommendation: **A**, subject to the explicit policy exception and
tests. It preserves existing SDK behavior while keeping one authored engine.
This recommendation is not the owner's decision or a measured-equivalence claim.

### Choice 2: SDK distribution

**A. Build a namespace-preserving SDK artifact from the canonical source.** Keep
the public `amphrang` facade and its approved dependency/optional-asset boundary.
A deterministic build export of an explicitly reviewed core module set maps
internal absolute imports into `amphrang.engine`, records canonical revision,
file digests and transform rules, and fails on unclassified imports/dependencies.
Exported engine code is generated build input, never separately edited source.
SDK source distributions must contain the complete pinned export so offline
builds do not fetch GitHub or depend on a checkout outside the sdist. Runtime
imports use the installed artifact only, with no checkout/fallback path.

Pin the canonical source tree, export manifest and generator revision. CI must
regenerate the export and fail on any missing, extra or differing generated file.
Direct-wheel and sdist-built-wheel packaged source manifests must match. Offline
sdist builds assume provisioned, pinned build tools and dependency artifacts;
they must not retrieve canonical source over the network. Owner approval of this
option explicitly accepts one authored implementation with generated namespaced
runtime copies, not one runtime module, shared caches or policy/accuracy
equivalence. Recorded provenance alone is insufficient without this enforced
regeneration relationship.

The implementation must first prove the required module/dependency closure in a
small clean-wheel spike. This proposal does not claim that today's root modules
already fit the smaller SDK footprint or choose unverified module exclusions.
If closure requires broader dependencies or changes facade outputs, stop and
bring the concrete conflict back to the owner rather than silently widening it.

**B. Depend on the existing root `aiguard` distribution.** This is mechanically
simpler, but explicitly changes SDK installed top-level namespaces and dependency
footprint. It needs a documented migration/compatibility policy and clean
environment collision/optional-dependency tests. No project that installs only
the current minimal SDK may inherit this new footprint without notice.

Builder recommendation: **A**, conditional on the closure/spike and reproducible
wheel/sdist tests. It preserves the existing namespace promise. It adds build
maintenance and needs an exact manifest/import-transform audit; it is not
automatically safer merely because it avoids a new generic namespace.

### Required provider-error migration

Replace SDK proxy restoration of upstream error bodies with fixed, value-free
error metadata. Preserve a documented safe status/error classification, not
provider strings, arbitrary headers or a nested JSON error object. Apply the
same rule to JSON, non-JSON and streaming failures. Restore only the explicitly
supported successful response path. Classify success by the supported response
schema as well as status. Project HTTP 2xx error envelopes, malformed success
bodies, in-band SSE errors and transport failures after headers into fixed
value-free failures. Once headers are committed, terminate safely under the
documented stream failure contract; never pass through provider error frames,
malformed/non-data content or stringified exceptions. The new tests must fail on the current
renderer and prove no mapping/token/provider body/original value escapes in
error content, logs, exception graphs or queued diagnostics, for every listed
failure class.

This is a deliberate public error-contract correction. Do not preserve the
current sensitive echo as a compatibility mode. The owner must approve the
documented contract migration before it lands; no error renderer is changed by
this proposal. Existing affected artifacts are not newly certified for release.

## Hosted preservation and staged rollout

Keep Hosted's reviewed gateway/auth/Protected Markdown contracts, hash-locked
security overlay, verified model layer and no-egress runtime acceptance.
Core revision and Hosted deployment `VERSION` remain distinct identities.
Consolidation does not deploy to AI for Thai, expand supported modalities,
inherit platform credentials, or claim local on-device privacy.

First close explicit non-deploy CI coverage and pin current differences. After
owner decisions, implement the namespace/profile spike; review the resulting
module/dependency and policy changes before migrating one consumer. Build/install
the SDK wheel/sdist outside source, build the exact Hosted image, qualify its
offline/no-egress/failure path, then re-run the full affected gates and independent
review. Retain previous immutable artifacts for provenance. Operational rollback
requires qualification against the approved privacy/error contract; artifacts
that retain provider-error restoration are not eligible automatic rollback
targets. If no safe candidate exists, disable the affected proxy path. Remove
old maintained copies only after import/entry/build/doc/test checks and the new
artifacts prove there is no live consumer of them.

## Acceptance and decision record

M1 is complete only when adapters consume an identifiable canonical core,
approved policy/packaging/error decisions are tested, clean artifacts pass and
all required CI jobs actually run green. M3's performance/CI holds remain in
force; this proposal grants no main/release promotion.

Owner disposition: **pending** for sensitive policy, distribution boundary and
the fixed-error contract migration. Silence and elapsed time do not approve a
choice. Separate-context review findings and any owner response must be recorded
before accepting this ADR. Historical accepted SDK ADRs remain unchanged; their
status is updated only through the decision index after an approved replacement.

Independent proposal review: a fresh separate-context adversarial/builder review
identified in-band/2xx/late-stream failure handling, immutable adapter config and
remote-engine isolation, enforced export regeneration and unsafe rollback as
missing requirements. Parent verified the affected renderer/config source and
incorporated those corrections. The review was static and did not prove a build
export, equivalent protection or a production-ready adapter.

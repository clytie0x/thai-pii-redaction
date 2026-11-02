# Canonical Hosted core build

Status: source candidate, 3 November 2026. Not deployed; exact-image acceptance
has not run on the local host because Docker is unavailable. Product versions
remain unchanged. This document does not accept M1 or promote prior detector
evaluation results to the new artifact.

Source compatibility evidence: the real-detector execute contract initially
passed 12/14. Safe offset propagation in the shared core fixed template-prose
span masking, giving 13/14. The remaining failure was two extra NAME spans in
the exact-token Markdown regression. Porting exactly the prior Hosted fixed
answer-label filter and glued-role NAME boundary guard now gives 14/14 with
unchanged assertions. No model tuning or detector-accuracy claim is made.
The initial failures remain part of this migration record. The exact-image,
installed/offline and complete affected gates still require qualification.

The subsequent full SDK alias check retained nine additional common-core parity
failures in `sdk-full-retry-1.log`. The approved compatibility port now relabels
numberless, non-administrative ADDRESS spans as LOCATION without unmasking or
changing their source intervals; numbered addresses and administrative chains
remain ADDRESS. It also restores the prior SDK driver-license/assignment name
cues, spaceless form-label exclusions and land-document abbreviation guard.
Real person-title forms and nearby full names remain protected. Existing root
WARNING-level value-free recovery logging remains unchanged. These are bounded
functional compatibility tests, not a corpus, training or accuracy result.

The runtime installs the supplied first-party `thai-pii-redaction-core==0.1.0`
wheel. The wheel owns `app` and `pii_redactor`; Hosted owns `aift_gateway`, auth,
the `aift_hosted3` overlay, its fixed public projection/route fence, security
overlay, model verifier and deployment version. Hosted stays remote processing
with transient request-local mappings. No local-only privacy claim is added.
`LEGACY_HOSTED_SECTION26_CATEGORIES` names the preserved eight-category Hosted
wire projection. The canonical root/SDK ten-category report does not silently
widen this legacy Hosted public surface.

The old `core/app` and `core/pii_redactor` authored copies have no live consumer
and are removed. `sync/PORT_MANIFEST.json` and `SOURCE_PROVENANCE.json` preserve
the earlier reconstructed checkpoint and unavailable historical identity.
They are inactive provenance. `sync_from_upstream.py --from` refuses to copy
source; `--check --verify-upstream` still verifies the historical Git object
and retained support files while rejecting a new independent runtime copy.

## Supplied inputs

After the canonical source is frozen and reviewed, build its wheel with pinned
build tools. Supply its exact SHA-256, canonical source revision and source-tree
SHA-256. Prepare a Linux/Python 3.13 wheelhouse using the exact hashes in both
`core/requirements.lock` and `core/requirements-aift-security.lock`. No index
resolution of the first-party distribution is allowed. Prepare the thainer
model separately and verify it with `core/verify_thainer_assets.py`; the fixed
tree SHA-256 remains
`bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315`.

From the monorepo root, use explicit absolute artifact paths:

```text
python scripts/prepare_hosted_core.py --source . --print-source-digest
python scripts/prepare_hosted_core.py --source . --core-wheel <qualified-wheel> --core-wheel-sha256 <wheel-sha256> --source-revision <commit> --source-tree-sha256 <source-tree-sha256> --wheelhouse <locked-linux-wheels> --models <verified-thainer-tree> --output <new-context-directory>
docker build --network none --build-arg AIFT_BUILD_COMMIT=<commit> --file <new-context-directory>/Dockerfile --tag <candidate-image> <new-context-directory>
```

The preparer compares every wheel source/resource under `app` and
`pii_redactor` against the canonical checkout, verifies exact wheel identity,
rejects unexpected or unpinned dependency artifacts, and verifies the certified
model tree. It creates a new allowlisted context and `CORE_BUILD_IDENTITY.json`
with source/wheel/model identities plus context file hashes. It never writes
artifacts into the source tree or downloads inputs. Missing Linux dependency
closure fails the offline pip install; it cannot resolve through an index.

The Dockerfile performs offline hash-required dependency installs, applies the
existing security overlay, installs only the supplied wheel with `--no-deps`,
runs `pip check`, verifies installed source/resources and import origins, and
checks the baked thainer tree. The canonical wheel supplies the preferred Thai
font and OFL license; the build needs no unpinned OS font installation.
The application remains under `/app`; installed canonical imports must resolve
from the installed distribution outside `/app`.

Compose accepts the prepared context through `AIFT_CORE_BUILD_CONTEXT`.
Without supplied artifacts, the default `./core` build fails closed. Production
deployment is separately owner-gated; its exact prior-stack rollback, secret
handling, proxy/auth/public routes and acceptance requirements still apply.

## Contract and image evidence

Source-only Hosted contracts select this checkout's canonical package through
the test harness, never through a runtime checkout fallback. Approval bindings
hash the complete canonical `app`/`pii_redactor` source and resource tree from
the actual resolved package instead of retaining the old partial file list or
vendored-code literal. This matches the wheel's source-tree identity. A fixed
cryptographic test vector remains frozen separately. Model binding is unchanged.
New artifacts require new exact-image/offline/failure qualification; historical
evaluation baselines and production versions retain their original scope.

The shared validator reports only integer offsets outside the union of
validated authoritative restored ranges. Adjacent or overlapping ranges may
jointly cover a finding, but a one-character gap still blocks. A repeated known
value outside those ranges remains untrusted. Count/verdict metadata and safe
offsets agree on full union coverage; stateless restoration bounds the offsets
to its output and scrubs the caught exception graph. The Hosted adapter alone
owns its existing policy of masking only those generated-output spans.
This projection requires `generated_pii_spans_complete is True`, propagated
from the actual validator's `PIILeakError.spans_complete` proof. Every finding
must have valid offsets. Missing, malformed, out-of-bounds or legacy metadata
withholds the whole answer; keeping a valid subset is unsafe. Entity count and
segment count are different because range subtraction can split a finding and
merging can combine overlapping findings. The proof never relies on equal
counts. The existing internal three-value scanner interface remains compatible.

The runner simulator generates a schema-2 tracked-file inventory from host Git
plus the exact allowlisted canonical package inventory used by the wheel
preparer, and mounts the inventory read-only into the check container. It binds
canonical file hashes and the same complete source-tree digest as the artifact.
The release scanner verifies revision, inventory digest, all files, exact
canonical closure and source-tree digest before scanning for secret patterns.
The preparer also scans the exact source byte snapshot it hashes and compares
against the wheel; those operations cannot accidentally inspect different
source revisions. Synthetic secret markers in a canonical module fail the gate
without printing matched values. The exact wheel archive, including metadata
and license payloads, is scanned too. Missing, extra or modified canonical files
fail verification. There is no permissive filesystem fallback when Git metadata
is absent. Canonical source directories are mounted read-only for source-only
checks; the built runtime receives no checkout mount.

`tests/hosted_canonical_image_contract.py` is a source-authored offline image
probe. Mount only that probe, set `PYTHONPATH=/app` and run it inside the exact
image with `--network none --read-only`. It calls both installed/model verifiers,
the actual Hosted `ProtectionService`, canonical restoration and Hosted offset
admission/masking helpers. It checks exact-token restoration, generated-prose
masking and refusal of incomplete metadata. It prints no content or mapping.
The local host has not executed this image probe.

Required before acceptance: every Hosted declared source/Node contract, the
exact prepared Docker image, installed identity, no-egress model/detection and
Hosted gateway/approval/provider-failure paths. Real organizer/provider/deploy
acceptance remains distinct. No release, registry publication or provider call
is authorized by context preparation.

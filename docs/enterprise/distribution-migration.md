# First-party core distribution migration

State: local M1 candidate, not a publication or release. The owner approved the
name `thai-pii-redaction-core` on 2 November 2026. Product `VERSION` remains
`0.1.0`; acceptance work does not bump it.

## What changes

Only the Python distribution identity changes from the old first-party
`aiguard` name. Existing `pii_redactor` and `app` import paths and repository
entry paths remain. No installed CLI command is introduced. Product branding,
desktop executable names, HTTP headers and configuration names are unchanged.

PyPI's `aiguard`, including `0.1.0`, is the unrelated SyntaxSama project that
depends on `ollama`. Never use that public package as this project's core.
The new name's availability check is not registration or proof of ownership;
public publication requires separate owner authorization and a fresh check.

## Qualified installation and replacement

Use explicit, provenance-verified first-party wheels with recorded SHA-256
digests and a complete trusted dependency wheelhouse. Qualification disables
index access with `--no-index` and runs outside the source checkout. A version
pin or a local editable import alone does not establish artifact identity.

Prefer a fresh isolated environment. Verify the wheel metadata is
`Name: thai-pii-redaction-core`, its version matches the supplied manifest, its
runtime/resource hashes match that artifact, and imports resolve inside the
new environment. Run dependency consistency, synthetic detect/mask/restore and
the affected enterprise/web entry paths before switching an application.

An in-place replacement needs a separate local qualification. First establish
that any installed `aiguard` is the old first-party artifact by comparing its
installed metadata and files against the retained verified wheel. Stop if that
identity cannot be established. Never remove an unrelated package by name.
Stop only the application's own processes, retain the verified old artifact and
environment snapshot, remove the verified old distribution, then install and
verify the new artifact before restarting the application. Do not install both
overlapping namespace owners and later uninstall one: uninstalling either can
remove files that the other still needs.

Do not modify an operator's existing environment automatically. A failed
qualification leaves the application on its previous environment or disabled;
it does not trigger public-index fallback.

## Observed local artifact evidence

The [source-bound manifest](../acceptance/enterprise/M01-core-distribution-manifest.json)
records a setuptools 83.0.0 build on Windows/Python 3.13.12. An sdist copied
outside the checkout rebuilt with a provisioned backend and both `--offline`
and `--no-index`. All 112 unpacked wheel members, including metadata, matched
the direct wheel; their ZIP container hashes differ. All 105 `app`/
`pii_redactor` runtime/resource files also matched the retained M3 first-party
wheel, so the rename did not replace those implementations.

Two fresh environments outside source used explicit first-party wheels and a
hash-locked dependency wheelhouse, with index access disabled. The clean install
and an isolated old-owner removal/new-owner installation both passed dependency
consistency (47 packages), installed byte/origin checks, synthetic token/surrogate
roundtrips, HTTP health and enterprise entry imports. The old installation's
metadata and every runtime file were checked against the retained artifact
before removal. A missing first-party wheel was rejected without index fallback.
These checks do not qualify other platforms, a real enterprise login, a Docker
image, SDK rollback or an operator's existing environment.

## SDK and rollback gates

The SDK's approved target is a direct dependency on the matching qualified
`thai-pii-redaction-core` artifact. This additionally brings the generic `app`
and `pii_redactor` namespaces and the root dependency/assets footprint. M1 must
still implement the adapter migration, version-pin synchronization, frozen lock,
explicit paired wheel/sdist installation and index-free container build.
Adding dependency metadata alone does not consolidate the current engine copies.

The same SDK migration changes Section 26 automatic masking to warn/report and
uses fixed value-free proxy errors, including HTTP 200/SSE/late-stream failures.
A future release must include matched before/after examples and warn callers
that sensitive findings are no longer automatically masked. Those behavior
changes are not yet implemented by the distribution rename alone.

Retained artifacts establish provenance, not permission to roll back. An SDK
proxy rollback artifact must pass the approved privacy/error contract. If none
qualifies, keep that path disabled. M3 controlled-performance hold and every
executing CI job remain mandatory before main promotion; no release/deploy is
authorized by the rename.

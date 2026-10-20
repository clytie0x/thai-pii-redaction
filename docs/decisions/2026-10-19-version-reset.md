# Version reset to 0.1.0

- Date: 2026-10-19
- Status: accepted by the owner
- Supersedes: the "do not reset" recommendation in
  [versioning-proposal.md](../versioning-proposal.md)

## Decision

- The product `VERSION` (Desktop, Extension, Office add-in, native broker)
  restarts at `0.1.0`; the `amphrang` SDK is already `0.1.0`.
- The hosted app source also restarts at `0.1.0` (owner decision the same
  day), and its public pages stop linking to the archived 3.0.0 downloads.
  This is a source change only: production keeps reporting `3.0.2` until a
  protected release of this source is deployed, which `apps/hosted/STATE.md`
  records.
- The line stays below `1.0.0` until the owner judges the product ready for
  production users. `1.0.0` means a release that can go to production; it is
  not a date or a feature count.
- Before `1.0.0`, an incompatible change bumps the minor version and anything
  else bumps the patch version.
- The `v1.0.0`-`v3.0.0` tags are removed from this repository. They, their
  releases and their assets remain in the private archive
  `clytie0x/thai-pii-redaction-archive`.

## Why the earlier advisory no longer blocks this

The advisory's objection was that a lower number on the same product line looks
like a downgrade to installed clients. That still holds: an installed 3.0.0
Desktop will not offer a `0.x` build as an update and must be reinstalled. The
owner accepted this because the public repository is a fresh start with a
rewritten history and no published `0.x` build, and the product is due to be
renamed (KhumKrong platform, Amphrang engine) after YRSS 2026, which is when a
new application identifier and updater feed should replace
`th.ac.psu.aiguard` and the current endpoint.

## Consequences

- `scripts/bump_version.py` and `scripts/check_version.py` remain the single
  path for the product version; the hosted app and `amphrang` keep their own
  `VERSION` files.
- Recorded evidence and decision records that mention `2.x` or `3.0.0` describe
  the archived line and are not rewritten.

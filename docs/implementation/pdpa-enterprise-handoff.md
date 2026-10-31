# Enterprise PDPA development checkpoint

Development is paused at the owner's request. This branch preserves work in
progress; it is not a complete enterprise product, a release or a deployment.
Single-organization self-hosting is confirmed. Do not ask that choice again.

## Commit groups

| Work | Commits |
|---|---|
| Reproducible YRSS experiments and detection/input recovery | `b198c5c` through `b2761bd` |
| PDPA category assessment, local semantic experiment and frozen results | `eb60891` through `d745e81` |
| Enterprise architecture, legal applicability and confirmed implementation plan | `20fa614` through `87c7125` |
| PostgreSQL authority, versioned migrations, enrollment and atomic audit | `4d31d76` |
| Scoped processing registry, immutable notices and independent membership/review commands | `03b8aa3` |

Keep these existing logical commits. No history rewrite, squashing, main merge
or release is part of this checkpoint publication.

## Observed evidence

- Exact domain source `03b8aa3`: full local Python suite **2,884 passed,
  34 skipped**, with one existing FastAPI/Starlette deprecation warning.
- **44 focused tests** use real PostgreSQL 18.6 and synthetic identities/data.
  They cover organization binding, one-time enrollment, current roles/scopes,
  independent approval, suspension/reactivation, stale revisions and proposer
  authority, idempotency, concurrent updates, audit rollback and immutable notices.
- A real PostgreSQL stop/start preserved enrolled members and audit history.
- The earlier foundation wheel from the Task 1 source successfully initialized
  PostgreSQL through packaged SQL under isolated Python. The complete registry
  wheel and final enterprise application have not received package acceptance.
- Lint, format and version checks passed. The ordinary dependency lock, existing
  HTTP/native handlers and closed evaluation data were not changed by enterprise
  development. The enterprise dependency set has a separate hash lock.
- Existing-path performance at the Task 2 checkpoint: detect 5.29 ms, sanitize
  13.99 ms, restore 0.24 ms, PDF 68.09 ms, RSS 151.4 MiB. The old sanitizer
  anchor remains red, as it was before this additive work; it was not moved.
- These are local results. The ordinary GitHub CI dependency set does not itself
  prove the optional real-PostgreSQL enterprise tests ran.

## Not implemented or accepted

OIDC staff authentication, server-side browser sessions, the enterprise web/API
caller path, real subject consent, retention/rights execution, protected evidence
storage, wider governance modules, independent whole-branch review and pilot/
deployment/recovery acceptance remain open. Domain tests pass trusted synthetic
principals directly; they do not prove an authenticated staff boundary.

Processing review currently records a permitted human reviewer's attestation to
external evidence references. It does not independently inspect those external
documents or issue legal clearance. Open/unresolved categories remain activation
blockers pending the wider legal-control work.

## Local continuation

The implementation branch is `feat/pdpa-enterprise`. On the current machine its
managed worktree is `<canonical-repository>/.worktrees/pdpa-enterprise/`; a normal
checkout of this branch elsewhere uses that checkout root as its entry point.

Plan: [Stage 1](pdpa-enterprise-stage1.md).
Architecture: [enterprise control plane](../decisions/2026-10-31-pdpa-enterprise-control-plane.md).
The ignored execution ledger is `.superpowers/sdd/pdpa-enterprise-stage1/progress.md`.
Tasks 1 and 2 are complete; Task 3 is next. Follow the parent architecture's full
six-stage scope rather than calling Stage 1 the whole enterprise objective.

Task-owned PostgreSQL is stopped and its synthetic database files are preserved.
No task-owned identity-provider runtime remains. Publisher-digest-verified
Keycloak 26.8.1 and Temurin 25 development tools are retained in the ignored
workspace. Initial Keycloak startup failed at class loading; an explicit boot
classpath loaded CLI help, but no real OIDC flow or realm acceptance was achieved.
Inspect authoritative process state before any restart; this is unresolved setup,
not working authentication.

Runtime credentials, database files, environments, model caches and downloaded
tool binaries stay ignored. Never stage the private runtime key files or the
execution workspace. No real organization/customer credentials were used.

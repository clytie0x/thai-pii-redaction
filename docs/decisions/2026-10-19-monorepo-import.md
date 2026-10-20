# Monorepo import of the hosted app and the amphrang SDK

- Date: 2026-10-19
- Status: accepted by the owner; implemented on branch `chore/monorepo-import`, not yet merged to `main`
- Supersedes, for where source lives: the "separate port repo" choice in
  [2026-07-28 tokenmind detector + AIFT port](2026-07-28-tokenmind-detector-and-aift-port.md)
- Pre-merge record: `C:/Users/teera/dev/_catalog/ai-guard-monorepo-precheck-2026-10-19.md`
  (outside this repository)

## Problem

AI Guard lived in three repositories: this desktop repository, the hosted AI
for Thai application (`aiguard-aift`) and the `amphrang` SDK. On 2026-10-19
the owner confirmed that the `aiguard-aift` and `amphrang` GitHub
repositories no longer exist, so their 76 and 92 commits existed only on one
local disk. The hosted app also carries its own copy of `pii_redactor`
(`core/pii_redactor`), which differs from the root package in 8 files plus 1
file present on one side only (compared with trailing CR stripped), so a
detector fix on one side does not reach the other. The project is also
growing into a wider Thai PDPA platform whose parts should share one
detector, one set of agent instructions and one CI.

## Decision

- This repository becomes the single source. The hosted app is imported at
  `apps/hosted/` from `aiguard-aift` `main` `10431fc`, and the SDK at
  `packages/amphrang/` from `amphrang` `main` `e548964`, each with
  `git subtree add` (no squash) so every original commit stays reachable.
  The imported trees are byte-identical to the source HEAD trees
  (`31835cea` and `c2954405`).
- The branch is based on `benchmark/blind-v2`, which already contains the
  unmerged `chore/drop-appimage-deb` work; nothing is merged to `main` until
  the owner reviews the diff.
- Nothing is unified yet. Each imported part keeps its own README,
  `AGENTS.md`, tests and dependencies. Replacing the vendored
  `apps/hosted/core/pii_redactor` with the root package is separate work.
- If AI for Thai deployment needs a standalone repository again (the earlier
  record names a GitLab port), `git subtree split --prefix=apps/hosted`
  produces one from this history.

## Consequences

- Root CI and the root pytest suite (`testpaths = ["tests"]`) do not run the
  imported tests, and `packages/amphrang/.github/workflows` do not run from a
  subdirectory. Until root CI covers them, their checks are manual.
- The local checkouts `C:/Users/teera/dev/ai-guard/current` and
  `C:/Users/teera/dev/ai-guard/packages/amphrang`, and the mirrors under
  `_history/github/`, are left untouched; retiring them is a separate,
  owner-authorized step after this branch merges.
- The product rename to KhumKrong (platform) and Amphrang (engine) is
  deferred until after YRSS 2026, which uses the submitted name AI Guard.

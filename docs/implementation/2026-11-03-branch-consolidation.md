# Reviewed branch preservation and consolidation

The owner requested one active branch, `main`. Preserve the production candidate
and every unique historical/study/worker head before deleting branch metadata.
The [exact preservation map](2026-11-03-branch-preservation.json) records 21
annotated non-release archive tags whose remote peeled commits were verified.
Creating these tags did not delete or move any branch.

| Group | Disposition |
| --- | --- |
| Enterprise feature | Integrate only its reviewed, exact-CI-qualified tree after the performance condition is satisfied; retain the raw pre-squash history separately. |
| Design and two research planning branches | Their work is represented in feature ancestry; retain exact raw heads. |
| Broker hello and hard-PII branches | Existing main patch/tree equivalence was verified; retain raw history. |
| Old restore fix | Superseded by the owner-approved strict bulk/streaming contract, not copied unchanged. |
| History-map fix | Superseded by the current frozen-paper provenance path; do not restore old provenance. |
| Recall, blind-v3 baseline and per-entity blind-v2 | Archive as distinct studies, including revealed/reverted study tips; no accuracy claim, detector merge, corpus access or new experiment follows. |
| Five Dependabot branches | Retain superseded proposals; do not merge old-base major upgrades for cleanup. |
| Four raw worker branches | Preserve original commits alongside the corrected combined integration, including migration/composition changes. |
| Hosted 75-file source checkpoint | Retain exact SHA `cf50512a043b54ca28f4264d8c103dcc25da1a6d` under its archive tag; the live checker fetches SHA, not branch name. Never merge that snapshot as an engine. |

The existing `blind-v3-freeze` tag remains unchanged. It alone does not preserve
later reveal/revert study heads, so the two raw study-tip tags are separate.
The late `cursor/per-entity-blind-v2-7c3b` proposal adds benchmark/reporting files,
not production runtime; it is retained without opening its locked corpora.

Archive tag pushes do not match the checked branch-only CI or `v*` release
triggers. No release, deployment, external comment or Support message is sent.
Closing/removing superseded proposal branches is metadata cleanup, not merging
their code or claiming their experiments passed.

For promotion, create a short-lived integration branch whose squash commit has
the current main as parent and exactly the reviewed candidate tree. Run every
CI job on that exact commit, then update main by a normal fast-forward push.
No force push, old-history clone push or rewrite is needed. Preserve any later
final feature tip before removing its branch as well.
That additional pre-squash checkpoint is retained as
`archive/2026-11-03/final-feature`, separately from the initial 21-head map.

Revalidate every remote head before deletion and stop on drift. Detach clean
worker worktrees at their same raw commits before removing their local branch
names. Keep all worktree directories, ignored negative evidence and the owner's
untracked `1` file. Do not reset, clean or delete their contents. Verify one
remote branch and one local branch only after the complete operation.

Main integration is engineering consolidation. It does not accept M11/M12,
production/pilot identities, TLS, legal applicability, external providers or
GitHub hidden PR/cache purge. The raw archive tags retain reviewable work rather
than turning unqualified studies into production code.

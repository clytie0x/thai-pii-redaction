# Public repository transition: privacy cleanup

Date: 2026-11-02. State: **writable remote history cleaned; public visibility held**.

The owner authorized a private backup, removal of only two private screenshots
from every branch/tag, reviewed force-push and then public visibility to enable
standard public CI. This does not authorize package publication, deployment,
M3 acceptance or merging the feature implementation into main.

## Verified cleanup

The [manifest](M00-public-cleanup-manifest.json) records the full source-ID map,
backup/evidence digests and independent review scope. The private mirror and
verified bundle preserve the original 681-commit snapshot, including signed
objects. A separate `git-filter-repo 2.47.0` mirror removed the exact two image
blobs from all reachable commits. The filter preserved all other recursive tree
entries, file modes, authors, dates, messages and ordered parent topology.

Independent review checked all 85 rewritten commits. Across their historical
snapshots 150 image entries were removed; all other file bytes remain identical.
Standard history rewriting removed 32 commit signature headers. The old signed
objects remain in the private backup; signatures are not claimed valid on the
rewritten identities. The annotated tag retains its other metadata.

An atomic push with explicit old-SHA leases updated all 19 branches and one tag.
Remote ref sets and SHA values matched the reviewed candidate afterward. The
rewritten main is `38b235ffb5cede349e51362049a03666b8637dc6`; the implementation
checkpoint is `1d802b5721e8a5256c4ab68e5f04efa623f88a65`. This is an identity/privacy
rewrite, not a squash of the held M3 implementation into main.

A fresh independent checkout has no removed image blobs, PR/original/replace
refs, alternates or grafts, and passes `git fsck`. The original worktrees,
branches, indexes and four owner planning files remain preserved; their normal
origin push URL is disabled to prevent stale-history reintroduction. Further
engineering uses the clean checkout. Private attachments are ignored for future
source work. Backups must not be pushed or published.

## Remaining GitHub gate

After the successful rewrite, authenticated Git Blobs API requests still
returned the two removed objects, sized 60,752 and 66,407 bytes. This verifies
retention for an authorized caller, not public accessibility while private.
The live repository remains private with zero forks. The separate YRSS
documentation repository also remains private.

There are 14 affected PRs and 21 head/merge refs. GitHub read-only PR refs,
cached views and unreachable objects need server-side cleanup. The owner has a
prepared Support request in the ignored private audit workspace; no Support
message was sent. Do not expose the repository while waiting for the purge.
This follows [GitHub's sensitive-data removal procedure](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

After Support confirms removal, recheck the PR/cache/object state and repository
identity, then perform the already authorized visibility change. Run every
required CI job on the exact clean candidate and inspect actual results. Public
visibility alone is not green CI. M3's controlled-environment performance hold
and the remaining M0-M12 milestone gates stay in force.

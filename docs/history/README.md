# History rewrite (2026-10-19)

This repository's history was rewritten before it was prepared for public
release. The original history, including its pull requests and releases, is
kept in the private repository `clytie0x/thai-pii-redaction-archive`.

## What changed

- Private documents were removed from every commit: submission and paper
  drafts, competition templates, pitch decks and scripts, signed and unsigned
  proposal forms, third-party reference PDFs, and bundled third-party tool
  archives. The owner keeps them outside git.
- Commit author and committer e-mail addresses were replaced with the GitHub
  noreply address.
- Only `main`, `chore/monorepo-import` and the `v*` release tags were carried
  over. Migration-recovery tags, stale branches and pull-request refs were not.

Every commit therefore has a new SHA. File contents outside the removed paths
are unchanged.

## Old SHAs in documents and evidence

Commit SHAs recorded before the rewrite (in decision records, evidence JSON and
reports) refer to the archive. [`commit-map.txt`](commit-map.txt) maps each old
SHA to its new one, one `old new` pair per line after the header. A new SHA of
all zeros means that commit only touched removed paths and no longer exists.

`benchmark.human_review.load_gold_at_commit` reads this map, so the frozen
gold-v3 corpus recorded as `d93d10b17be6783d5c684cb47f25d4156ed6fb4b` still
loads, and its provenance still reports the recorded SHA.

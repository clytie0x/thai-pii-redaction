# Pre-publication Readiness Plan

- **Status:** Complete locally; no release or remote mutation performed
- **Scope:** Make the local repository truthful and safe to publish without creating a release.
- **Timer origin:** 2026-08-29T18:00:40.774Z (first task tool action)
- **Explicit exclusions:** no `VERSION` change, no `Unreleased` rollover, no release tag,
  no commit, no remote creation, no push, and no PyPI publication.

## Baseline and preservation

The security-hardening work is intentionally uncommitted. Preserve every existing change,
the user-owned `.claude/` tree, and the untracked `AGENTS.md`. The local `v0.1.0` tag exists,
but no Git remote is configured.

## Work packages

### 1. Repository truth

- Record `v0.1.0` as a local internal preview that was never publicly distributed.
- State when the public deprecation/stability promise begins without weakening it for future
  public releases.
- Accept the newer LLM-gateway direction and mark the overlapping portions of ADR 0002 as
  superseded.
- Add outcome banners to completed historical execution plans instead of rewriting their
  original unchecked task instructions.
- Publish a concise README performance snapshot from the committed benchmark report, including
  the slower four-worker result rather than presenting only favorable numbers.

### 2. Secret exposure audit

- Scan the working tree, untracked task files in scope, every commit, and every local ref.
- Prefer a dedicated scanner; report only redacted identifiers, paths, and classifications.
  Never print candidate secret values into logs or this plan.
- Distinguish synthetic fixtures/documented placeholders from real credentials and record any
  unverified scanner limitation.

### 3. Verification

- Run Markdown/file hygiene, `scripts/check_release.py`, `uv lock --check`, and `git diff --check`.
- Run tests only if documentation or audit tooling touches executable paths; otherwise retain the
  already-verified security suite evidence and run proportionate document gates.
- Assign an independent adversarial reviewer and resolve every material finding.
- Remove every task-created scanner/cache/temp artifact before handoff.

## Timing log

| Phase | Start (UTC) | End (UTC) | Duration | Evidence |
|---|---|---|---:|---|
| Baseline and plan | 2026-08-29T18:00:40.774Z | 2026-08-29T18:01:33.168Z | 52.4 s | Complete |
| Documentation truth | 2026-08-29T18:02:26.626Z | 2026-08-29T18:17:26.750Z | 15 m 00.1 s | Eight docs aligned; release gate and scoped pre-commit passed |
| Secret audit | 2026-08-29T18:03:00.781Z | 2026-08-29T18:12:55.984Z | 9 m 55.2 s | Gitleaks v8.30.1: zero candidates; temp artifacts removed |
| Verification and review | 2026-08-29T18:18:06.700Z | 2026-08-29T18:26:07.343Z | 8 m 00.6 s | Gates passed; tag-push finding fixed; re-review clean |

## Documentation outcome

- README installation now uses a source checkout and says PyPI is not yet
  available. The committed Win11 performance snapshot exposes cold start, S/M
  p50 and p95, one-versus-four-worker throughput, RSS, environment, date, and
  source reports without hiding the slower parallel result.
- The local `v0.1.0` tag is recorded as an unpublished internal preview at
  commit `cff373ef383330a554808149c6800a6c818788bf`. The binding semver and
  deprecation promise begins with the first public release; no release was
  created in this work.
- The gateway direction is accepted and explicitly supersedes the overlapping
  product-positioning and fixed-keep-list portions of ADR 0002. Phase 1/2 are
  implemented locally but their public/adoption exit criteria remain unmet;
  Phase 3 remains unbuilt and adoption-gated.
- Both completed campaign plans carry evidence-backed historical banners while
  retaining their original unchecked execution instructions.
- `SECURITY.md` now supports pre-public `main` instead of claiming a nonexistent
  public 0.1.x line. `.claude/settings.local.json` is narrowly ignored without
  changing or deleting it.

## Future public-repository handoff, not executed here

The local `v0.1.0` tag is lightweight and points to the internal-preview commit,
whose historical `release.yml` publishes on every `v*` tag. The first remote
upload must therefore be branch-only:

```sh
git push -u origin main
```

Do not use `git push --tags`, `git push --mirror`, or explicitly push
`v0.1.0`; `--mirror` would also publish local Codex refs that do not belong on
the remote. Before configuring any package publisher, run
`git ls-remote --tags origin` and require empty output, then require GitHub CI
on `main` to be green. Creating the remote, pushing `main`, configuring a
publisher, and making any release remain separate owner-authorized actions.

## Secret-audit evidence

The official Windows x64 Gitleaks v8.30.1 binary was verified against its
published SHA-256 checksum before use. The final redacted audit found zero
candidates in all of the following scopes:

- a refreshed 239-file publication snapshot, including the explicitly scanned
  but now ignored `.claude/settings.local.json`;
- all 109 commit objects (91 reachable from refs plus 18 otherwise unreachable);
- all five local refs (`main`, `v0.1.0`, and three Codex tree refs representing
  two unique trees); and
- 899 unique historical paths checked for credential-like filenames.

No file exceeded the scanner's 100 MiB cap. The encrypted blind corpus was not
decrypted, and PDF-rendered text was not OCR-extracted; PDFs were raw-byte
scanned. Archive traversal was disabled after `.bru` text was misclassified as
Brotli, then every raw file was scanned without errors. The 46.7 MiB temporary
scanner directory and reports were removed. The audit changed no repository
files.

## Final verification

- Ruff check and format check passed across the repository; 195 Python files
  were already formatted.
- `scripts/check_release.py`, `uv lock --check`, and `git diff --check` passed.
- The documentation worker's scoped pre-commit run passed. Parent checks also
  confirmed final newlines, LF line endings, no trailing whitespace, no merge
  markers, and no changed file over 1 MiB across all 20 changed/new files.
- The prior security-hardening full suite remains the executable baseline:
  1,989 passed and 9 skipped. It was not repeated for this documentation,
  ignore-rule, and read-only audit-only follow-up because no executable file
  changed in this phase.
- Independent review found one material publication hazard: pushing the local
  `v0.1.0` tag would execute the historical `v*` release workflow. The future
  handoff instructions now require a branch-only push and prohibit tag/mirror
  pushes. Re-review found no remaining material disagreement.
- Final state remained `HEAD=ad60551f3aee6c66fe1962b155f88a15bffbb35c`,
  `VERSION=0.1.0`, no configured remote, and the original local `v0.1.0` tag.
  No task-created scanner, cache, report, or pytest artifact remained.

Total observed wall time through final handoff validation was 25 m 26.6 s.
Documentation and secret scanning ran in parallel, so their individual
durations must not be summed.

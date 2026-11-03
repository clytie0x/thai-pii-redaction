# Version, tag, and release process

This process applies to the desktop installers, extension version, API version,
and public GitHub Release. The hosted API contract has its own
`contract_version`; a product release does not automatically break that
contract.

**Current source line:** product, Hosted source and SDK are 0.1.0 under the
[accepted reset](decisions/2026-10-19-version-reset.md). Archived 2.x/3.x assets
are historical. Recorded Hosted production remains a separately verified
deployment identity, not a source-version inference. The M0-M12 authorization
allows preparation, not an unspecified production promotion or public release.

**Current platform scope.** The release matrix builds Windows and macOS
only. `desktop/src-tauri/tauri.conf.json` no longer lists `deb` or `appimage`
as bundle targets, `latest.json` carries no `linux-x86_64` entry, and
`scripts/check_release_assets.py` no longer requires the Linux assets. The
Linux sections further down still describe live, tested code: the bundling
helpers, the AppImage finalizer, and the DEB maintainer scripts were kept so
Linux packaging can be evaluated again. They do not run for a release today;
re-enabling Linux requires fresh candidate-specific packaging/lifecycle evidence.

## Sources of truth

- `VERSION` - product version.
- `scripts/_version_targets.py` - every file that must carry the same product
  version.
- `CHANGELOG.md` - human-readable shipped scope.
- immutable Git tag `v<VERSION>` - exact source commit used to build artifacts.
- GitHub Release for that tag - downloadable artifacts, checksums, Tauri updater
  signature files, and attestations. Updater signatures are separate from OS
  code signing; the installers remain unsigned by the accepted distribution
  decision.

Release assets are the distribution surface. The repository carries no package-
manager manifest, so nothing downstream needs a version bump after publication.
The automated tag workflow publishes Desktop artifacts only. The browser
extension remains outside the GitHub Release asset set: branch CI builds the
exact production-ID ZIP as a retained workflow artifact for separate Chrome Web
Store review/submission. The Office add-in is likewise outside the automated
GitHub Release asset set.

## Current release authorization

The owner authorized the `3.0.0` release-preparation task on 2026-08-14 after
Slices 5 and 6 reached `main`. That task removed the earlier intentional
preflight stop through a tested release-workflow change. A version tag now
creates only a draft release; it does not bypass exact-candidate review,
installed-package evidence, OS signing/notarization classification, updater
signature verification, Chrome Web Store review, or the publish gate below.
Future releases still require a separate owner-authorized preparation task.

`python scripts/check_release_readiness.py` is a metadata-consistency check
only: it verifies synchronized version targets plus the changelog, and with
`--expect-tag` also checks tag identity and an empty `Unreleased` section. A
green result does not certify architecture, security, packages, installed
hosts, signing, notarization, or release readiness.

Branch CI can build unpublished package candidates and exercise bounded smoke
paths. Those jobs do not create or publish a GitHub Release. The Release
workflow also has a manual pre-tag mode: it accepts only an exact 40-character
commit SHA, checks out and verifies that commit, builds the same updater-signed
production artifact set on the current Windows/macOS matrix, and retains the packages plus a
closed machine-readable source/tree/run-bound manifest as workflow artifacts. It does not create a
tag or Release. The same build jobs now black-box the non-feature-gated final
packages before staging them: NSIS is silently installed and removed and both
macOS payload forms are launched. Each launch must observe the manifest-matched production
Desktop, broker, and backend process chain and clean it up. These bounded
release checks complement, rather than replace, the deeper feature-gated Slice
6 install/repair/upgrade/interruption lifecycle. Treat every result according
to the exact evidence class recorded for it.

The following retained Linux helper requirements are historical and apply only
if Linux packaging is explicitly re-enabled and requalified. A distributable AppImage must pass the
checksum-pinned post-`linuxdeploy` finalizer before smoke, hashing, signing, or
upload. For the pinned no-sign/no-update build, that gate permits only the
single non-executable, non-overlapping 16-byte `.digest_md5` rewrite defined by
appimagetool, requires every other x86-64 ELF64 runtime-prefix byte to match,
then confirms the runtime offset and re-extracts the image to verify the native
components and manifest. The raw Tauri AppImage intentionally carries an
invalid manifest and is not a release candidate. Automated AppImage smoke must
independently attest the extracted bytes, start the exact finalized outer file
with `--appimage-extract-and-run`, re-attest the retained root, and exercise its
verified `AppRun` warm. Record that separately from normal FUSE/double-click.
The Slice 6 package workflow attempts normal FUSE only when the runner can
mount it and otherwise records the exact unavailable condition; extract-and-run
never substitutes for FUSE evidence.

## Semantic version policy

- **Patch** (`x.y.Z`) - compatible bug/security fixes and operational fixes.
- **Minor** (`x.Y.0`) - additive user-facing capability, new endpoint/operation,
  or a materially new supported integration that preserves existing contracts.
- **Major** (`X.0.0`) - a deliberate breaking change to a supported public
  contract, persisted user data, or installer/update compatibility.

Docs-only commits do not require a tag. Development commits after a release stay
under `Unreleased` until the next release-preparation branch chooses the version.

The owner accepted restarting source versions at `0.1.0`; the prior recommendation
against reset is superseded by the accepted decision above. Before 1.0.0, an
incompatible change bumps the minor version; other changes bump the patch.
Development/acceptance work does not bump versions. Archived 3.x clients do not
automatically downgrade to 0.x; distribution identity/update migration remains
explicit. Imported Hosted and SDK keep their own VERSION sources. Source
metadata does not change production without a separately accepted deployment.

## Release preparation branch

1. Freeze the intended scope, ensure every item meets the roadmap definition of
   done, and confirm that the release has explicit owner authorization.
2. Pull the latest `main` and create a short-lived release-preparation branch.
3. Run `python scripts/bump_version.py X.Y.Z` rather than editing version strings.
4. Move the relevant `Unreleased` entries into
   `## [X.Y.Z] - YYYY-MM-DD`; leave a fresh empty `Unreleased` section.
5. Run `python scripts/check_release_readiness.py` as the metadata-only check;
   complete the separate architecture, package, installed-host, security, and
   external gates required by the candidate.
6. Run the full local checks appropriate to the change, push the branch, and
   wait for every GitHub Actions job to pass.
7. Review the diff for installer names, updater configuration, API contract,
   documentation, and the release notes - not only tests.
8. Push the immutable branch commit and run `.github/workflows/release.yml`
   manually with that exact full SHA as `candidate_sha`. Download its exact
   candidate manifest and platform artifacts for review before tagging.
9. Squash the reviewed branch into `main` as one commit, push `main`, and wait
   for every `main` CI job to pass before tagging.

## Tag and build

The commands below apply only after the release-preparation branch is squashed
into a green `main`:

```bash
git switch main
git pull --ff-only origin main
git tag -a vX.Y.Z -m "AI Guard vX.Y.Z"
git push origin vX.Y.Z
```

Rules:

- The tag must be placed on the exact reviewed `main` commit.
- Never move, delete/recreate, or reuse a published version tag.
- A failed release is fixed with a new commit and new version, not a retag.
- Do not create the GitHub Release by hand before the tag workflow runs.

In tag mode, the release workflow verifies the tag/version/changelog
relationship (including an empty `Unreleased` section), builds each platform
artifact, production-smokes it, and creates a draft release. The checksums job
downloads the exact expected Desktop files from the same workflow run, binds their names,
sizes, SHA-256 digests, source commit/tree, run ID, and attempt in a closed build
manifest, then resolves exactly one draft by tag. It regenerates `latest.json`
from that draft's exact asset IDs, rejects every extra or missing asset, and
requires the downloaded draft bytes to match the current-run manifest before
and after uploading `SHA256SUMS`. Only that redownloaded closed set receives
GitHub provenance. A same-version filename or reused draft is not evidence.

Retained Linux path (not in the current release matrix): five Tauri bundling helpers are fetched through immutable URLs,
verified by size and SHA-256, normalized for Tauri's documented three-byte
`linuxdeploy` header patch, and preseeded into a closed cache. The cache must be
unchanged after bundling. The action then runs through
`scripts/release_tauri_build.py`: it preserves the pre-`linuxdeploy` backend,
finalizes the post-`linuxdeploy` AppDir with the pinned output plugin, deletes
the raw AppImage signature, and signs the exact finalized AppImage before the
action can discover or upload it. Release notes come from the exact dated
`CHANGELOG.md` section.

## Publish gate

The draft remains unpublished until the maintainer verifies:

- all expected Windows/macOS assets and every expected updater/signature
  file are present, with no additional draft asset outside the closed set;
- the tag workflow's current-run build manifest matches every downloadable
  Desktop byte and canonical `latest.json` matches the uploaded copy;
- the exact final NSIS and both macOS payload production-package smoke checks
  pass; Linux checks apply only to an explicitly re-enabled Linux release;
- the workflow is green on the tag;
- checksums match downloaded artifacts;
- `gh attestation verify` succeeds for representative artifacts;
- release notes match the changelog and make no unsupported claim; and
- an install/launch smoke has passed on the maintainer's primary platform.

The Chrome Web Store candidate has a separate gate: download the exact branch-CI
artifact, verify its SHA-256 and production extension ID, complete the listing
and privacy review, and submit those unchanged ZIP bytes. A Web Store review or
publication state is never inferred from unpacked Chromium acceptance.

Only then publish the draft and mark it Latest. Delete stale duplicate **drafts**
after verifying a published release for that tag already exists; never delete a
published release as routine cleanup.

## After publication

1. Verify README's Latest link and updater `latest.json` resolve correctly.
2. Update wherever the installer is linked for download; the repository
   publishes release assets and does not push to any package manager.
3. Record the Chrome Web Store submission/publication state separately and link
   the live listing only after the store reports it available.
4. Return new work to `CHANGELOG.md` under `Unreleased`.

## Hotfix

Branch from the latest supported tag only when `main` contains unrelated work
that cannot safely ship. Apply the smallest compatible fix, bump the patch
version, add the changelog entry, run the same release gates, and integrate the
hotfix into `main` with the repository's normal squash workflow. Security fixes
do not bypass artifact verification.

## GitHub repository controls

Recommended controls for `main`:

- require green CI on the short-lived branch before the owner-controlled squash
  into `main`, then require green `main` CI before tagging;
- include version drift, release metadata, Python, JS, Rust, Docker, and packaged
  smoke checks as required checks;
- block force pushes and branch deletion;
- delete short-lived branches after their squash commit is on `main`;
- enable Dependabot security updates and public-repository secret scanning where
  GitHub makes them available; and
- keep default workflow-token permissions read-only, granting write only inside
  the release jobs that need it.

Apply branch rules only after checking the exact status-check names, so the
owner is not locked out by a misspelled or obsolete required check.

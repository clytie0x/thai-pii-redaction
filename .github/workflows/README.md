# CI cost policy

Linux checks still run on every branch push. That is the day-to-day gate,
because short-lived branches are squashed to `main` without a pull request.
macOS and Windows jobs do not. The macOS smoke workflow does not start on
other branch pushes. Those jobs run only when one of these is true:

- push to `main`
- push of a `v*` tag
- `workflow_dispatch`
- pull request label `full-ci` (adding the label starts those jobs)

A diff that only touches `docs/**`, `*.md`, or `LICENSE*` skips compile, test,
package, and image jobs. Lint, JS syntax, and the version check still run.
Tags and manual runs ignore that filter. A new branch whose base SHA is
unknown runs the heavy lane.

A pull request from this repository does not repeat the Linux lane. The branch
push already ran it. A fork has no push event here, so the Linux lane stays on
`pull_request`. Adding `full-ci` does not rerun Linux jobs that already ran
for that pull request.

Each workflow cancels an older run of the same ref when a new push or
synchronize arrives. A `labeled` run does not cancel the in-progress code run.
The release workflow does not cancel itself.

## Self-hosted Linux

Linux jobs use:

```yaml
runs-on: ${{ vars.LINUX_RUNNER || 'ubuntu-latest' }}
```

Leave the `LINUX_RUNNER` repository variable unset to stay on `ubuntu-latest`.
Set it to one label when the self-hosted runner should take those jobs. The
runner that is being added is labeled `self-hosted`, `linux`, `x64`, and
`clytie-server`. GitHub picks a runner that has every requested label, so the
unique label is enough:

```text
clytie-server
```

Matrix jobs keep `windows-latest` and `macos-latest` on GitHub-hosted runners.
Only the `ubuntu-latest` cell reads `LINUX_RUNNER`.

The SDK matrix in `subtree-checks.yml` is the exception. Its `runs-on` stays
`${{ matrix.os }}` with `ubuntu-latest` and `windows-latest`, because
`tests/test_monorepo_ci_coverage.py` pins that shape. Windows cells in that
matrix still wait for the full lane. Moving the SDK Linux cells to the
self-hosted runner means changing that test.

The self-hosted machine has to provide what those jobs already use: `bash`,
`curl`, and `python3` for the cost-policy job; Docker for the PostgreSQL
service, image builds, and container smoke; `sudo` plus the WebKitGTK packages
the Rust jobs install. If a selected engine or service is missing, the job
fails instead of falling back to `ubuntu-latest`.

## What still runs on a branch push

Linux: ruff, extension package (heavy), pytest, enterprise PostgreSQL, core-only
pytest, version check, cargo test, native broker runtime, JS syntax, vitest,
Office add-in, and the Docker smoke, plus the hosted and SDK Linux checks.
macOS packaged Desktop smoke, macOS and Windows native broker runtime, Windows
pytest, the Windows packaged Desktop smoke, and the Windows SDK cells wait for
`main`, a `v*` tag, a manual run, or the `full-ci` label.

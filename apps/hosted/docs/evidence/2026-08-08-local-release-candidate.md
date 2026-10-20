# Local release-candidate acceptance — 8 Aug 2026

This is local evidence for release-content commit
`71c20b37b1bf2be8f34b67294bc75137931ad3cb`. The evidence commit that contains
this file is necessarily a descendant of the tested content; it does not
retroactively change the revision labels below. A final descendant must repeat
the exact-revision build/acceptance gate before local `main` is advanced.

No real credential and no live provider was used. Four distinct synthetic
values were derived in memory from the candidate SHA, passed through a private
temporary env file, excluded from Docker child argv, and never written here.
No repository `.env` file was read. No push, deploy, or remote mutation occurred.

## Source and CI checks

- `python tests/run_ci_local.py --job check`: pass in 25.7 s in the
  digest-pinned `docker:27.3.1` BusyBox image.
- 75 vendored files matched upstream commit
  `44ef30b0e8ea2021fc4ceec9d3b12dc9f64c750f`.
- 11 caller-auth tests and 9 hosted-provider/internal-PDF provenance tests
  passed. Frontend, 16-route/public-PDF, nginx, Compose, build-context,
  secret-argv, source-secret/documentation, and GitLab contracts passed.
- `python -m compileall -q core sync tests`, `git diff --check`, core
  `python -m pip check`, and the internal runner route probe passed.
- Tracked secret-pattern scan reported no candidate; only path/classification
  would have been printed on failure.

## Exact Docker build

`docker compose ... build --no-cache --pull` completed in 230.8 s. All builds
used digest-pinned bases and the three revision labels equaled the tested SHA.

| Image | Local image identifier |
|---|---|
| web | `sha256:5ba79750f70f2c96ada31fbe8128ee817e32d4f27bf8b1ecd5ae1897eaea39e7` |
| api | `sha256:998e3fc9b36ca4e243b76710778439d22a76c23ee0e1c583e40cc2fc05a0f913` |
| core | `sha256:974852b8470687c5e45bb99736d2d4d0cf3acf67d94ad6c5f9e18ed9ba275548` |

Image config/history contained none of the synthetic values. Runtime copies
contained no `.env`, VCS, credential, test-output, private-key, or build-output
sentinel. Core dependency consistency passed.

## Local provider-free acceptance

`python tests/local_release_acceptance.py --restart` completed in 28.7 s.
It passed public health/root, security headers, valid/invalid authentication,
missing/tampered cookies, cross-site denial, logout, Privacy Scan (2 synthetic
entities), PDPA Report (score 30.0, grade B), exact allowlist, both public PDF
aliases denied, deterministic fake Safe AI, log-marker scan, and stateless
restart recovery. Expiry/rotation behavior is covered deterministically by the
caller-auth unit contract.

The short 48-request concurrency sample returned 11 successful responses and
37 fixed `429` responses; it produced no unexpected status. This is bounded
local behavior, not a platform quota or SLA.

The independent in-container fault harness exercised timeout, network, 429,
and 5xx at exactly 3 shared attempts; non-retryable 4xx, malformed, non-text,
and empty responses at exactly 1. Every actual attempt had one fresh outbound
scan. Provider-bound text excluded the synthetic name and phone, errors were
fixed, and the successful public response projected no mapping/entities.

`python tests/run_ci_local.py --job deploy` then passed in the pinned BusyBox
runner image in 63.5 s and left the deployment-shaped (Tokenmind-only) local
stack healthy without calling Tokenmind.

## Runtime configuration and resources

- Published ports: only `127.0.0.1:20070→3000` and
  `127.0.0.1:20071→8000`; core `8000` was internal only.
- Limits: web/api 256 MiB and 0.5 CPU each; core 6 GiB and 2 CPU.
- Tmpfs: API cache 64 MiB; core `/tmp` 1 GiB. Restart policy
  `unless-stopped`; logging `json-file`, `50m`, 3 files.
- Idle memory: web 20.65 MiB, API 21.36 MiB, core 53.89 MiB.
- After detect/report/fake flow: web 20.51 MiB, API 22.05 MiB,
  core 162.7 MiB.
- After short load: web 20.51 MiB, API 23.41 MiB, core 163.2 MiB.

Public PDF/OCR was not exercised and cannot fail this release: both aliases
are quarantined. Internal implementation/provenance tests passed, but public
PDF remains a future correctness/resource gate.

## Evidence boundary and external gates

This session does **not** claim GitLab runner evidence, AI for Thai platform
evidence, public HTTPS/proxy behavior, or live Pathumma/Tokenmind evidence.
Those require owner configuration, a newly issued provider credential, first
real `check → deploy → acceptance`, and manual platform/log/restart verification.
The previously exposed Tokenmind credential must not be reused.

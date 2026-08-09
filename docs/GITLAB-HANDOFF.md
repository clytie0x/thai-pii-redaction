# GitLab handoff (do not execute from the local release session)

## Official requirement vs AI Guard hardening

The official Participant Guide requires non-main branches to run `check`,
deployment from `main`, the organizer-provided team runner, the displayed runner
tag when one is present, and Masked backend-only `APP_*` secrets.

AI Guard additionally pins every job to `team-08`, makes every ordinary push
check-only, requires a UI-created pipeline on protected `main` for
deploy/acceptance/ops, validates the current remote SHA, serializes production
through `team08-production`, and recommends Protected/Hidden/scoped variables.
The guide does not require a Protected runner, Protected Environment,
`newest_first`, automatic rollback, or Protected variables.

## Current GitLab facts

- Project: `ai4thai-service-hackathon/08/aiguard-aift`; repository now contains
  first-publication SHA `298401552726a0cfbe977d23d5ee3d7f7cda66ed`.
- GitLab auto-protected the first remote `main` when it became the default
  branch. Review its push/merge/force-push permissions before production.
- Runner #227: organizer-provided team-08 group runner, online, Docker
  amd64/Linux, tag `team-08`, accepts untagged jobs, not Protected.
- Runner #227's missing Protected flag alone is not a guide or publication
  blocker. Organizer confirmation of project scope and Docker-daemon isolation
  remains desirable platform evidence; tag pinning is not isolation proof.
- Auto DevOps: disabled.
- Pipeline #35715 ran on runner #227 and failed `check` at
  `python3 tests/nginx_contract.py` with exit 2 because the test job could not
  reach host-loopback-published test services from the Docker executor network.
- Deploy, acceptance, logs, ps, and restart were all `skipped`; no application
  secret was consumed and no production service was changed.
- Environment `team08` now has skipped deployment metadata from job #136360,
  not a successful deployment. Protected Environments are not required by the
  guide and are unavailable in the current GitLab CE UI.

## Corrective publication — check only

The original first-publication SHA is historical evidence. Do not create the
four application variables yet and do not use `ci.skip`. Executable rules now
make **Ordinary pushes are check-only**, including pushes to protected `main`.
The correction uses a normal push and must create exactly one tagged `check`
job. `check` consumes no application secret, makes no provider request, and
contains no production-mutating Compose command.

## After the corrective check is green

1. Open **Settings → Repository → Branch rules** and review the automatically
   created `main` protection; disable force push and restrict push/merge
   appropriately if the current rule is weaker than owner policy.
2. Create exactly these CI/CD variable names—never place values in source:
   - `APP_AIGUARD_API_KEY`
   - `APP_AIFT_ACCESS_CODE`
   - `APP_AIFT_COOKIE_SIGNING_KEY`
   - `APP_TOKENMIND_API_KEY`
3. Set each secret **Masked** as the official guide requires.
4. As AI Guard hardening, also set Protected, Hidden where supported, variable
   expansion off, environment scope `team08`, and use four distinct values.
5. Confirm the Tokenmind credential was reissued/rotated; do not reuse the old
   credential.

Do not require or claim a Protected Environment. The job environment remains
`team08`. `resource_group: team08-production` and exact-remote-SHA checks remain
the repository's serialization/stale-deployment controls. `newest_first` and
automatic rollback are not guide requirements.

## First protected-main production pipeline

Do not retry pipeline #35715; it refers to the historical SHA and old rules.

Open **Build → Pipelines → Run pipeline**, select `main`, add no temporary
variables, confirm the displayed SHA equals local `main`, and create a **new**
pipeline. The `web` pipeline source is explicitly allowed only to run production
jobs when the branch is protected `main`.

Expected jobs:

```text
check → deploy → acceptance → manual logs/ps/restart
```

Feature-branch pushes, merge requests, and all ordinary pushes run `check` only.
Tag pushes, schedules, and API-triggered pipelines cannot create production
jobs under the checked-in rules.

## First real acceptance

Require check, deploy, and acceptance to refer to the same exact SHA. Then
verify public root/health, organizer `/api` prefix stripping,
login/session/logout, authenticated Privacy Scan and PDPA Report, live Safe AI,
both PDF aliases denied, exact 404 surface, rate limiting, fixed errors,
Dozzle/platform logs, restart recovery, resources, and image revision labels.
Keep local, GitLab-runner, platform, and live-provider evidence separate.

## Ready-to-paste next-session prompt

> Work only in `aiguard-aift`. Verify clean local/remote `main`, VERSION 2.5.0,
> the green exact-SHA check-only pipeline, and the historical #35715 failure.
> Do not create the four application variables yet. Review the automatic `main`
> protection in GitLab with the owner. After the owner supplies four rotated,
> distinct Masked plus Protected/Hidden/scoped variables and explicitly
> authorizes production, use Build → Pipelines → Run pipeline on the same
> protected `main` SHA; do not retry #35715. Monitor exact-SHA
> `check → deploy → acceptance`. Do not use the old Tokenmind credential and do
> not treat runner tag pinning as proof of Docker-daemon isolation.

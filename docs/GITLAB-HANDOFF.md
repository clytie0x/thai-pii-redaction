# GitLab handoff (do not execute from the local release session)

## Official requirement vs AI Guard hardening

The official Participant Guide requires non-main branches to run `check`,
deployment from `main`, the organizer-provided team runner, the displayed runner
tag when one is present, and Masked backend-only `APP_*` secrets.

AI Guard additionally pins every job to `team-08`, requires protected `main` for
deploy/acceptance/ops, validates the current remote SHA, serializes production
through `team08-production`, and recommends Protected/Hidden/scoped variables.
The guide does not require a Protected runner, Protected Environment,
`newest_first`, automatic rollback, or Protected variables.

## Current GitLab facts

- Project: `ai4thai-service-hackathon/08/aiguard-aift`; currently empty.
- Remote `main`: absent and cannot currently be protected before first
  publication through the available UI.
- Runner #227: organizer-provided team-08 group runner, online, Docker
  amd64/Linux, tag `team-08`, accepts untagged jobs, not Protected.
- Runner #227's missing Protected flag alone is not a guide or publication
  blocker. Organizer confirmation of project scope and Docker-daemon isolation
  remains desirable platform evidence; tag pinning is not isolation proof.
- Auto DevOps: disabled.
- Environment `team08`: not created yet. Protected Environments are not required
  by the guide and are unavailable in the current GitLab CE UI.

## First publication — check only

This step needs separate owner authorization. Verify the SSH URL from
**Code → Clone**; do not rely on the expected URL without checking the UI.

Do not create the four application variables yet. Do not use `ci.skip`.

```text
git remote add origin <UI-verified SSH URL>
git push -u origin main
```

The first unprotected-main push creates a normal branch pipeline. Executable
rules include `check` and exclude deploy, acceptance, and manual production ops.
`check` consumes no application secret, makes no provider request, and contains
no production-mutating Compose command.

Require the first pipeline to contain `check` only. Stop if its job set differs.

## Immediately after first push

1. Open **Settings → Repository → Branch rules**.
2. Protect `main`, disable force push, and restrict push/merge appropriately.
3. Create exactly these CI/CD variable names—never place values in source:
   - `APP_AIGUARD_API_KEY`
   - `APP_AIFT_ACCESS_CODE`
   - `APP_AIFT_COOKIE_SIGNING_KEY`
   - `APP_TOKENMIND_API_KEY`
4. Set each secret **Masked** as the official guide requires.
5. As AI Guard hardening, also set Protected, Hidden where supported, variable
   expansion off, environment scope `team08`, and use four distinct values.
6. Confirm the Tokenmind credential was reissued/rotated; do not reuse the old
   credential.

Do not require or claim a Protected Environment. The job environment remains
`team08`. `resource_group: team08-production` and exact-remote-SHA checks remain
the repository's serialization/stale-deployment controls. `newest_first` and
automatic rollback are not guide requirements.

## First protected-main pipeline

Do not retry the first-push pipeline; its rules were evaluated while `main` was
unprotected.

Open **Build → Pipelines → Run pipeline**, select `main`, add no temporary
variables, confirm the displayed SHA equals local `main`, and create a **new**
pipeline. The `web` pipeline source is explicitly allowed only to run production
jobs when the branch is protected `main`.

Expected jobs:

```text
check → deploy → acceptance → manual logs/ps/restart
```

Feature-branch pushes, merge requests, and unprotected main run `check` only.
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

> Work only in `aiguard-aift`. Verify clean local `main`, VERSION 2.5.0, no
> remote, and the exact local acceptance record. After my explicit approval,
> verify the SSH URL from GitLab Code → Clone, add `origin`, and push exact
> `main` normally without application variables or `ci.skip`. Confirm the first
> pipeline contains only the tagged `check` job. Stop and ask me to protect
> remote `main` and create the four Masked plus Protected/Hidden/scoped variables.
> After I confirm, use Build → Pipelines → Run pipeline on the same protected
> `main` SHA; do not retry the first pipeline. Monitor exact-SHA
> `check → deploy → acceptance`. Do not use the old Tokenmind credential and do
> not treat runner tag pinning as proof of Docker-daemon isolation.

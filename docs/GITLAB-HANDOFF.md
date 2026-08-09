# GitLab production recovery handoff

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

- Project: `ai4thai-service-hackathon/08/aiguard-aift`; GitLab auto-protected
  the first remote `main` when it became the default branch. Force push is off
  and push/merge are restricted to Maintainers.
- Runner #227: organizer-provided team-08 group runner, online, Docker
  amd64/Linux, tag `team-08`, accepts untagged jobs, not Protected.
- Runner #227's missing Protected flag alone is not a guide or publication
  blocker. Organizer confirmation of project scope and Docker-daemon isolation
  remains desirable platform evidence; tag pinning is not isolation proof.
- Auto DevOps: disabled.
- Check-only pipeline #35718 passed exact SHA
  `5ae77ad25eb9b97a08812a7ec9571e5434de9eaa` on runner #227.
- Exactly four project variables are configured: `APP_AIGUARD_API_KEY`,
  `APP_AIFT_ACCESS_CODE`, `APP_AIFT_COOKIE_SIGNING_KEY`, and
  `APP_TOKENMIND_API_KEY`. Their values were not inspected. GitLab metadata
  shows all four Protected, Masked, Hidden, and scoped to `team08`.
- Pipeline #35722 was the production attempt on the same SHA and runner.
  `check` passed;
  Compose built and started web/api/core and all became healthy. Deploy then
  failed because its job container curled host-loopback ports 20070/20071.
  Acceptance and manual ops did not execute. The running stack is therefore a
  partial deployment, not successful production acceptance evidence.
- Protected Environments are not required by the guide and are unavailable in
  this GitLab CE UI.

## Corrective behavior

Executable rules keep **Ordinary pushes are check-only**, including pushes to
protected `main`. The corrective push must therefore create only `check` and
cannot mutate production. Do not use `ci.skip` and do not retry #35722.

The corrected production path:

- separates Compose build from `up`, rechecks current remote main immediately
  before mutation, and uses `up --no-build`;
- probes health from inside the api/web containers rather than assuming runner
  job loopback reaches host-published ports;
- resolves the acceptance build container and Compose default network by exact
  Docker labels, attaches only that job temporarily, uses `http://api:8000`
  with `Host: team08.aiforthai.in.th`, disables ambient proxies, and always
  disconnects;
- keeps `check` interruptible while deploy, acceptance, and ops are
  non-interruptible;
- declares environment `team08` only on deploy and acceptance. Manual ops use
  direct Docker commands and declare no environment, so the four scoped
  application variables are not intentionally injected there.

`resource_group: team08-production` and exact-remote-SHA checks remain the
repository's serialization/stale-deployment controls. `newest_first`, automatic
rollback, Protected runners, and Protected Environments are not Participant
Guide requirements.

## Resume procedure

1. Push the reviewed corrective descendant to `main` normally. Require its
   check-only pipeline to pass and confirm no production job exists in it.
2. Open **Build → Pipelines → Run pipeline**, select that same exact protected
   `main` SHA, add no temporary variables, and create a new pipeline.
3. Require `check → deploy → acceptance` all green on runner #227 before using
   any manual ops job.
4. Do not treat internal Compose-network acceptance as proof of the organizer
   edge. Separately verify public HTTPS/root, `/api` prefix stripping, Host and
   client-IP behavior, real-browser login/session/logout, Privacy Scan, the
   minimum live Safe AI call, PDPA Report, fixed failures/rate limit, PDF and
   internal-route denial, Dozzle/log privacy, resources, restart/recovery, and
   exact revision labels.

Feature branches, merge requests, and all ordinary pushes run `check` only.
Tag pushes, schedules, and API-triggered pipelines cannot create production
jobs. Keep local, GitLab-runner, platform, and live-provider evidence separate.

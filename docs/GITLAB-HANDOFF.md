# GitLab competition enhancement handoff

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
- Production rollback evidence preserved for Sprint 2 is exact
  `9d38c6753aa0242bc35d09ec3332e90fe3f90079`: Pipeline #35736 passed
  `check → deploy → acceptance` on runner #227. Public HTTPS, prefix stripping,
  auth, synthetic Privacy Scan, live Tokenmind Safe AI, PDPA Report, route
  denial, log privacy, resources, revision labels, restart/recovery, and live
  visual acceptance passed. Pipeline #35727 remains historical evidence of the
  first successful runner-network correction.
- Exactly four project variables are configured: `APP_AIGUARD_API_KEY`,
  `APP_AIFT_ACCESS_CODE`, `APP_AIFT_COOKIE_SIGNING_KEY`, and
  `APP_TOKENMIND_API_KEY`. Their values were not inspected. GitLab metadata
  shows all four Protected, Masked, Hidden, and scoped to `team08`.
- Pipeline #35722 was the historical failed production attempt on an earlier SHA.
  `check` passed;
  Compose built and started web/api/core and all became healthy. Deploy then
  failed because its job container curled host-loopback ports 20070/20071.
  Acceptance and manual ops did not execute. It remains incident evidence only;
  #35727 superseded that failure; #35736 is the newer rollback evidence.
- Protected Environments are not required by the guide and are unavailable in
  this GitLab CE UI.

## Release behavior

Executable rules keep **Ordinary pushes are check-only**, including pushes to
protected `main`. A feature-branch push and later fast-forward main push must
therefore create only `check` and cannot mutate production. Do not use
`ci.skip`, do not retry #35736 for a descendant, and do not treat the rollback
baseline as evidence for changed frontend code.

The production path:

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

## Competition-enhancement procedure

1. Push the dedicated enhancement branch normally. Require its check-only
   pipeline to pass on runner #227 and confirm deploy/acceptance/ops do not run.
2. Require exact fake-provider local acceptance plus Product/Judge,
   accessibility, security, and reliability reviews with no P0/P1 finding.
3. Fast-forward the reviewed branch into local `main`, push normally, and
   require the new main push pipeline to remain check-only.
4. Open **Build → Pipelines → Run pipeline**, select that same exact protected
   `main` SHA, add no temporary variables, and create a new pipeline.
5. Require `check → deploy → acceptance` all green on runner #227 before using
   any manual ops job.
6. Do not treat internal Compose-network acceptance as proof of the organizer
   edge. Separately verify public HTTPS/root, `/api` prefix stripping, Host and
   client-IP behavior, real-browser login/session/logout, Guided Demo exact
   sequence, Privacy Scan, one live Safe AI invocation with sanitized-input
   proof, PDPA Report, fixed failures/rate limit, PDF-redaction/OCR and
   internal-route denial, Dozzle/log privacy, resources, restart/recovery,
   exact revision labels, and visual QA at the required viewports.

Sprint 2 adds only client-rendered evidence and presentation surfaces from the
existing 16-route contract: Executive Result Summary, Raw-vs-Protected,
Sensitive Data Map, warning-only Prompt Risk, request-scoped non-cryptographic
Protection Receipt, Presenter/fullscreen, and glossary/mode guidance. These must
not create an extra `/roundtrip`, expose mapping or raw entity values, or revive
public PDF redaction/OCR. The exact Sprint 2 SHA therefore needs new local fake,
feature-branch, protected-main pipeline, live-provider, log, resource/restart,
and responsive visual evidence before replacing rollback SHA `9d38c675...`.

Feature branches, merge requests, and all ordinary pushes run `check` only.
Tag pushes, schedules, and API-triggered pipelines cannot create production
jobs. Keep local, GitLab-runner, platform, and live-provider evidence separate.

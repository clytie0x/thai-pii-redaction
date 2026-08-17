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
- Current known-good production is exact
  `72e18bbe723adaf54c847e4b17c2177dfa60dd68`: Pipeline #35744 passed
  `check → deploy → acceptance` on runner #227. Public HTTPS, prefix stripping,
  auth, synthetic Privacy Scan, live Tokenmind Safe AI, PDPA Report, route
  denial, log privacy, resources, revision labels, restart/recovery, and live
  visual acceptance passed. `9d38c6753aa0242bc35d09ec3332e90fe3f90079`
  remains the pre-Sprint-2 rollback; Pipeline #35727 remains historical evidence
  of the first successful runner-network correction.
- Historical production used four project variables: `APP_AIGUARD_API_KEY`,
  `APP_AIFT_ACCESS_CODE`, `APP_AIFT_COOKIE_SIGNING_KEY`, and
  `APP_TOKENMIND_API_KEY`. Their values were not inspected. Hosted 3.0.0 also
  requires `APP_AIFT_PRIORITY_INVITES_JSON`; deployment must fail before
  mutation unless all five protected, masked, environment-scoped values exist.
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

- calls the reviewed `scripts/deploy_production.sh`, which retains one exact
  previous image/Compose set, separates build from `up`, rechecks current remote
  main before and after mutation, health/revision-gates all four services, and
  restores the previous stack if a post-mutation gate fails;
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
- runs credential-free public-edge acceptance after internal platform
  acceptance. Plain HTTP must return fixed-host 308 (without reflected query),
  HTTPS must emit HSTS, product/docs pages must resolve, unknown/PDF/OCR/internal
  paths must remain 404, and public health must report VERSION 3.0.0.

`resource_group: team08-production` and exact-remote-SHA checks remain the
repository's serialization/stale-deployment controls. `newest_first`, automatic
rollback, Protected runners, and Protected Environments are not Participant
Guide requirements. Automatic rollback is now AI Guard repository hardening;
it must not be described as an organizer feature or as proof of host recovery.

## Production Web Launch delta

- Starting evaluation/main is
  `c02ec1c82e22d0e200fbfad68556c169eba68007`; deployed rollback evidence remains
  `72e18bbe723adaf54c847e4b17c2177dfa60dd68` / Pipeline #35744 until a new exact
  protected-main acceptance completes.
- Hosted 3.0.0 provides Standard signed-browser access and issued Priority
  Invite access in one application. Neither is a user account or database, and
  neither bypasses preview, approval, queue, provider, or output gates. Session
  fingerprints are bounded in Core process memory; ending authority revokes
  replay and restart invalidates prior cookies.
- API request/cost controls are global plus signed-session keyed; provider lanes
  are stricter than ordinary text work. Application logs no longer include
  client IP or request target.
- The hosted image removes disabled Paddle OCR dependencies, verifies the exact
  Sprint 3 thainer tree hash, and keeps `/redact-pdf` + `/v1/redact-pdf` at
  proxy-level 404. This is a runtime change and therefore requires a new
  protected-main deployment rather than docs-only integration.
- A live baseline check on 13 Aug found HTTP root/API served 200 and HTTPS lacked
  HSTS. The repository candidate fixes forwarded-scheme requests, but public
  launch remains blocked if the organizer edge does not preserve that header or
  perform its own redirect. `tests/public_web_acceptance.py` is the executable
  gate; do not bypass it.

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

Sprint 2 added only client-rendered evidence and presentation surfaces from the
existing 16-route contract: Executive Result Summary, Raw-vs-Protected,
Sensitive Data Map, warning-only Prompt Risk, request-scoped non-cryptographic
Protection Receipt, Presenter/fullscreen, and glossary/mode guidance. These must
not create an extra `/roundtrip`, expose mapping or raw entity values, or revive
public PDF redaction/OCR. That runtime is now production at exact `72e18bbe...`
with Pipeline #35744 and live/platform acceptance complete.

Sprint 3 adds only `evaluation/`, one mandatory check contract, and documentation.
Its committed 138-case Thai synthetic/adversarial corpus and 32-case Section 26
signal suite run provider-free against the exact `72e18bbe...` detector image.
Feature-branch and main pushes remain check-only. If the final diff still has no
`core/`, `web/`, `api/`, Compose, or public-route change, integrate the reviewed
evaluation SHA but do not create a pointless production deployment: report the
evaluation HEAD separately while deployed runtime stays `72e18bbe...`.

Feature branches, merge requests, and all ordinary pushes run `check` only.
Tag pushes, schedules, and API-triggered pipelines cannot create production
jobs. Keep local, GitLab-runner, platform, and live-provider evidence separate.

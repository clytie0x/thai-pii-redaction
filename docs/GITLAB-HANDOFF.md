# GitLab handoff (do not execute from the local release session)

## Owner preflight

1. In the existing project
   `https://gitlab.nectec.or.th/ai4thai-service-hackathon/08/aiguard-aift`,
   protect `main`, disable force push, and restrict merge/push appropriately.
2. Confirm the production-capable organizer runner is online, **Protected**,
   and accepts protected refs only. Do not publish if its Docker daemon is
   shared with untrusted branch jobs.
3. Protect environment `team08`; allow deployment only for Maintainer/Owner.
4. Enable prevent-outdated-deployments. Set resource group
   `team08-production` to `newest_first` if supported.
5. Disable Auto DevOps or confirm it cannot override this repository's
   `.gitlab-ci.yml`.
6. Rotate/reissue the Tokenmind credential exposed previously. Never reuse it.

Create exactly these CI/CD variable names—no values belong in source or this
handoff:

- `APP_AIGUARD_API_KEY`
- `APP_AIFT_ACCESS_CODE`
- `APP_AIFT_COOKIE_SIGNING_KEY`
- `APP_TOKENMIND_API_KEY`

Set each to Masked, Hidden where supported, Protected, variable expansion off,
and environment scope `team08`. Values must be distinct.

## First publication (owner-authorized session only)

Verify the SSH URL from **Code → Clone**. It is expected, but not assumed, to
be `git@gitlab.nectec.or.th:ai4thai-service-hackathon/08/aiguard-aift.git`.
After every preflight item is confirmed:

```text
git remote add origin <UI-verified SSH URL>
git push -u origin main
```

Preserve history; never force push. Do not use `ci.skip`: the first publication
should execute `check → deploy → acceptance` only after protections, runner,
environment, and variables are ready.

If this GitLab version cannot protect a branch before it exists, an
owner-authorized normal first push is fail-safe at the repository layer:
all jobs use runner tag `team-08`, `check` runs, and deploy/acceptance/ops are
excluded unless `CI_COMMIT_REF_PROTECTED` is true. Protect `main` and the
environment, complete runner/variable controls, then create a **new** pipeline
on protected `main` (or push a reviewed follow-up). Retrying the first pipeline
does not re-evaluate its rules. Runner tag and rules do not replace a Protected
or isolated production runner.

## First real acceptance

Require all three stages to refer to the exact same candidate SHA. Then verify
public root/health, organizer `/api` prefix stripping, login/session/logout,
authenticated Privacy Scan and PDPA Report, live Safe AI via Pathumma,
both PDF aliases denied, exact 404 surface, rate limiting, fixed failures,
Dozzle/platform logs, restart recovery, resource use, and image revision labels.
Keep local, GitLab-runner, platform, and live-provider evidence separate.

## Ready-to-paste next-session prompt

> Work only in `aiguard-aift`. First verify local `main`, clean status,
> VERSION 2.5.0, no remote, and the exact local acceptance record. Ask me to
> confirm that GitLab `main`/runner/environment protections, outdated-deploy
> prevention, Auto DevOps setting, all four protected/hidden/masked scoped
> variables, and Tokenmind rotation are complete. Only after my explicit
> confirmation, verify the SSH URL from the GitLab UI, add `origin`, push local
> `main` without force, confirm the `team-08` tag, and monitor exact-SHA
> `check → deploy → acceptance` (or check-only first publication when GitLab
> cannot pre-protect an absent branch, followed by a new protected-ref pipeline).
> Do not reuse any old Tokenmind credential. Record GitLab, platform, and live
> provider evidence separately and stop on any SHA, route, secret, or log leak.

# First protected-main production attempt — historical failure evidence

Date: 2026-08-09 (Asia/Bangkok)

This record is intentionally value-free. No CI/CD variable value, access code,
cookie, provider body, request body, or raw user data was retrieved or recorded.

## Exact GitLab execution

- Pipeline: `#35722`, UI-created on protected `main`
- Commit: `5ae77ad25eb9b97a08812a7ec9571e5434de9eaa`
- Runner: organizer group runner `#227`, Docker amd64/Linux, tag `team-08`
- Check job `#136439`: passed
- Deploy job `#136440`: failed with exit 7
- Acceptance job `#136441`: did not execute
- Manual logs/ps/restart: did not execute

No temporary pipeline variable was supplied. GitLab listed exactly the four
expected project variable names with Protected, Masked, Hidden, `team08`-scope
metadata; their values were not opened or inspected.

## First real failure

Compose built and started `team08-web-1`, `team08-api-1`, and `team08-core-1`.
Docker health inspection reported the API and web healthy and `docker compose
ps` showed all three containers up. The next two redundant commands tried to
reach host-published ports 20071 and 20070 through `127.0.0.1` from the GitLab
Docker-executor job container. The captured job trace recorded a connection
failure for each port. That loopback belongs to the job container, not the
runner host, and deploy exited 7.

Classification: repository CI network-assumption defect after production
mutation. This was not a missing-variable, provider, Tokenmind, organizer proxy,
or transient runner failure. Acceptance never started, so #35722 is not live
provider or platform acceptance evidence.

## Corrective contract

The descendant correction:

- probes API/web from inside their service containers;
- separates image build from container mutation and rechecks remote main before
  `up --no-build`;
- resolves the acceptance job container and Compose default network by exact
  Docker labels, connects only that job temporarily, uses service DNS with the
  public Host header, disables ambient HTTP proxies, and disconnects in all
  success/failure paths;
- makes deploy and acceptance non-interruptible;
- removes the `team08` environment from manual ops jobs so environment-scoped
  application credentials are not injected where they are not needed;
- makes restart reject stale remote/image revisions and wait for all three
  health checks.

The corrective push must first pass its ordinary check-only pipeline. A new
UI-created protected-main pipeline on that exact descendant—not a retry of
#35722—must then pass check, deploy, and acceptance before production is called
accepted.

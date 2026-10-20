# First GitLab check recovery — 9 Aug 2026

This is sanitized CI evidence only. It is not deployment, platform, or live
provider acceptance evidence. No application variable existed, no real
Tokenmind credential was used, and no secret value was observed or recorded.

## Historical pipelines

- Pipeline `#35715`, SHA
  `298401552726a0cfbe977d23d5ee3d7f7cda66ed`, ran on runner #227. The check
  reached `tests/nginx_contract.py` and exited 2 because the Docker-executor
  job could not reach services published on host loopback. Deploy, acceptance,
  logs, ps, and restart were skipped.
- Pipeline `#35716`, SHA
  `f0359dc7b71fa5563db9ea9f6670e6fd19e789ee`, ran on runner #227 with exactly
  one job. The check reached `tests/nginx_contract.py` and exited 2 because the
  runner's friendly job hostname was not a container identity known to the
  Docker daemon. No production job was created.

Neither pipeline consumed an application secret, called Tokenmind, or changed
the production application. GitLab created skipped environment/deployment
metadata for #35715; that is not a successful deployment.

## Repository correction

The nginx contract continues to prove the test proxy and web containers publish
only on `127.0.0.1`. In Docker-executor mode it then resolves the current build
container by GitLab's `com.gitlab.gitlab-runner.job.id` Docker label, attaches
only that container to the uniquely named contract network, uses Docker DNS for
the checks, and disconnects/removes all test resources in `finally`. A local
hostname-inspection fallback supports the simulator without inspecting
container environments.

The simulator labels its job container with the same GitLab job label. The full
digest-pinned check passed through this path, and the ordinary local loopback
nginx contract also passed. Branch-rule contracts prove every ordinary push is
check-only; production jobs require a UI-created pipeline on protected `main`.

The descendant containing this evidence must still pass a new exact-SHA GitLab
check-only pipeline. A future production pipeline and platform acceptance remain
separate gates.

"""Regression checks for value-free process arguments and CI materialization."""

from __future__ import annotations

import importlib.util
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
CI = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
DEPLOY = "\n".join(
    (ROOT / "scripts" / name).read_text(encoding="utf-8")
    for name in ("deploy_production.sh", "rollback_production.sh")
)
FRONTEND = "\n".join(
    path.read_text(encoding="utf-8", errors="ignore")
    for path in (ROOT / "web").rglob("*")
    if path.is_file() and path.suffix in {".html", ".js", ".css"}
)
INTENDED = {
    "APP_AIGUARD_API_KEY",
    "APP_AIFT_ACCESS_CODE",
    "APP_AIFT_COOKIE_SIGNING_KEY",
    "APP_TOKENMIND_API_KEY",
}
SYNTHETIC = {
    name: f"synthetic-{index}-value-not-real"
    for index, name in enumerate(sorted(INTENDED), start=1)
}


def load_simulator():
    path = ROOT / "tests" / "run_ci_local.py"
    spec = importlib.util.spec_from_file_location("run_ci_local_contract", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load local CI simulator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    simulator = load_simulator()
    pipeline = {"variables": {"TEAM": "team08"}, "default": {"image": "docker:27.3.1"}}
    synthetic_env = {**SYNTHETIC, "APP_UNINTENDED_SECRET": "must-not-materialize"}
    with patch.dict(os.environ, synthetic_env, clear=False):
        child_environment = simulator.value_free_child_environment()
        if any(name in child_environment for name in synthetic_env):
            raise AssertionError("application value survived in a child environment")
        environment = simulator.docker_environment(pipeline)
        if not INTENDED.issubset(environment):
            raise AssertionError("intended application variables were not forwarded")
        if "APP_UNINTENDED_SECRET" in environment:
            raise AssertionError("local simulator forwarded a broad APP_* variable")
        success_path = None
        with simulator.private_env_file(environment) as env_file:
            success_path = env_file
            if os.name != "nt":
                mode = stat.S_IMODE(env_file.stat().st_mode)
                if mode != 0o600:
                    raise AssertionError(f"temporary env file mode is {mode:o}, not 600")
            command = simulator.docker_command(pipeline, env_file)
            flattened = "\0".join(command)
            if any(value in flattened for value in SYNTHETIC.values()):
                raise AssertionError("a secret value reached docker child argv")
        if success_path is None or success_path.exists():
            raise AssertionError("temporary env file survived successful cleanup")

        failure_path = None
        try:
            with simulator.private_env_file(environment) as env_file:
                failure_path = env_file
                raise RuntimeError("synthetic failure")
        except RuntimeError:
            pass
        if failure_path is None or failure_path.exists():
            raise AssertionError("temporary env file survived failure cleanup")

    materialized = set(re.findall(r"printf '([A-Z0-9_]+)=%s\\n'", CI + DEPLOY))
    if materialized != INTENDED:
        raise AssertionError(f"deploy materializes unexpected variable names: {materialized}")
    for forbidden in (
        "printenv | grep '^APP_'",
        "--arg code \"$APP_AIFT_ACCESS_CODE\"",
        '-H "Cookie: $COOKIE"',
        'grep -Fq -e "$APP_',
    ):
        if forbidden in CI + DEPLOY:
            raise AssertionError(f"credential-bearing CI argv pattern remains: {forbidden}")
    for server_name in (*INTENDED, "AIGUARD_API_KEY", "TOKENMIND_API_KEY"):
        if server_name in FRONTEND:
            raise AssertionError(f"server credential name reached frontend: {server_name}")

    child_env = os.environ.copy()
    child_env.update(SYNTHETIC)
    child_env["TEAM"] = "aiguard-contract-no-such-stack"
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "platform_acceptance.py")],
        env=child_env,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    if any(value in output for value in SYNTHETIC.values()):
        raise AssertionError("acceptance error output disclosed a secret value")
    print("secret hygiene contract ok: argv value-free, mode/cleanup pinned, four-name allowlist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

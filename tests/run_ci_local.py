#!/usr/bin/env python3
"""Run this repo's GitLab jobs locally, before the first push to a real runner.

Why this exists: `.gitlab-ci.yml` has never been executed by any runner. Every
piece of evidence in `docs/evidence/` comes from `tests/smoke.py`, which runs
on Windows with the upstream venv and issues commands *equivalent* to what CI
does. Equivalent is not the same, and the gap hides a whole class of bug — the
S0 spike (`tests/out/s0-runner-simulation.json`) found the job script runs
under BusyBox ash with no bash present, which nothing in the local harness
would ever have shown.

The cost of that gap is higher here than usual: deploying on this platform
*replaces* the running service, so a mistake found after deploy is a mistake
users have already seen.

**This is an approximation, and the ways it differs matter.** GitLab runs each
item of a job's `script` list as its own command and stops at the first
failure. This joins them into one text and runs it under `sh -e`, which is
close but not identical — a failure inside a pipeline or a subshell can be
reported differently. It also ignores `rules:`, running the job as if the
branch were `main`, and it knows nothing about the runner's tags, caches or
artifacts. The optional `--gitlab-network` mode reproduces a Docker executor's
job-container network for `check`; the default host-network mode supports
deployment-shaped local jobs. Neither mode proves the organizer runner.

This file is deliberately NOT referenced by `.gitlab-ci.yml`: it is a local
tool, and a tool that CI depends on is another thing that can fail on the
runner.

Usage (from this repo, with the upstream venv's python for pyyaml):

    python tests/run_ci_local.py --job check
    python tests/run_ci_local.py --job check --gitlab-network
    python tests/run_ci_local.py --all
    python tests/run_ci_local.py --job deploy --cold

Only the four intended application variables are forwarded from the machine
environment through a restricted temporary env file. Values never enter
`docker run` argv, are never printed, and are replaced with a placeholder
before any output is written to disk.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CI_FILE = REPO / ".gitlab-ci.yml"
OUT_DIR = REPO / "tests" / "out"

# Kept in step with `default.image` in .gitlab-ci.yml. Read from the file
# rather than hardcoded, so the two cannot drift.
TAIL_LINES = 50
REDACTED = "<redacted>"

# Job order for --all: the pipeline's own stage order. deploy must precede
# acceptance because acceptance probes what deploy brought up.
ALL_JOBS = ["check", "deploy", "acceptance"]
INTENDED_APP_VARIABLES = (
    "APP_AIGUARD_API_KEY",
    "APP_AIFT_ACCESS_CODE",
    "APP_AIFT_COOKIE_SIGNING_KEY",
    "APP_TOKENMIND_API_KEY",
)


def value_free_child_environment() -> dict[str, str]:
    """Do not leak application values through unrelated child environments."""

    return {
        name: value
        for name, value in os.environ.items()
        if name not in INTENDED_APP_VARIABLES and not name.startswith("APP_")
    }


def load_pipeline() -> dict:
    import yaml

    return yaml.safe_load(CI_FILE.read_text(encoding="utf-8"))


def secret_values() -> list[str]:
    """Every value that must never reach stdout or a result file.

    Taken from the environment rather than a list of names, so a variable
    added to the machine later is redacted without editing this file.
    """
    values = []
    for name, value in os.environ.items():
        if (name.startswith("APP_") or name.endswith("_API_KEY")) and len(value) >= 8:
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, REDACTED)
    return text


def build_script(pipeline: dict, job: str) -> str:
    if job not in pipeline:
        raise SystemExit(f"run_ci_local: no job named {job!r} in {CI_FILE.name}")
    before = pipeline.get("default", {}).get("before_script", [])
    script = pipeline[job].get("script", [])
    # The first line answers "which shell am I actually in" on every run, so a
    # future image change that swaps the shell shows up in the log rather than
    # as a mystery failure.
    lines = ['echo "[sim] shell=$(readlink /proc/$$/exe)"']
    lines += [str(item) for item in (*before, *script)]
    return "\n".join(lines) + "\n"


def docker_environment(pipeline: dict) -> dict[str, str]:
    """Return the value map written to a private Docker env file."""

    environment = {
        str(name): str(value)
        for name, value in (pipeline.get("variables") or {}).items()
    }
    revision = os.environ.get("CI_COMMIT_SHA")
    if not revision:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO,
            env=value_free_child_environment(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        revision = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO,
                env=value_free_child_environment(),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            if not status.strip()
            else "local-working-tree"
        )
    environment["CI_COMMIT_SHA"] = revision
    for name in INTENDED_APP_VARIABLES:
        if name in os.environ:
            environment[name] = os.environ[name]
    return environment


@contextmanager
def private_env_file(environment: dict[str, str]):
    """Create a mode-0600 env file and remove it on every exit path."""

    descriptor, raw_path = tempfile.mkstemp(prefix="aiguard-ci-env-", suffix=".tmp")
    path = Path(raw_path)
    try:
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            for name, value in environment.items():
                if "\n" in value or "\r" in value:
                    raise ValueError(f"environment value for {name} contains a newline")
                handle.write(f"{name}={value}\n")
        yield path
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def docker_command(
    pipeline: dict, env_file: Path, *, gitlab_network: bool = False
) -> list[str]:
    image = pipeline.get("default", {}).get("image", "docker:27.3.1")
    network_args = [] if gitlab_network else ["--network", "host"]
    contract_env = []
    if gitlab_network:
        contract_env = ["-e", "CI_JOB_ID=local-gitlab-network"]
    elif sys.platform == "win32":
        network_args += ["--add-host", "host.docker.internal:host-gateway"]
        contract_env = ["-e", "AIFT_CONTRACT_CONNECT_HOST=host.docker.internal"]
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        *network_args,
        "--env-file",
        str(env_file),
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{REPO}:/w",
        "-w",
        "/w",
        *contract_env,
        image,
        "sh",
        "-e",
        "-s",
    ]


def run_job(
    pipeline: dict, job: str, secrets: list[str], *, gitlab_network: bool = False
) -> dict:
    script = build_script(pipeline, job)
    print(f"[sim] === {job} ===", flush=True)
    started = time.monotonic()
    # Bytes, not text=True. On Windows a text-mode stdin pipe rewrites "\n" to
    # "\r\n", the shell then hands every argument a trailing carriage return,
    # and the container reports things like `unrecognized arguments: --check`
    # for a flag that plainly exists. That was a defect in this simulator
    # masquerading as a defect in the pipeline, which is the exact failure
    # mode a simulator has to be trusted not to invent.
    with private_env_file(docker_environment(pipeline)) as env_file:
        command = docker_command(pipeline, env_file, gitlab_network=gitlab_network)
        result = subprocess.run(
            command,
            input=script.encode("utf-8"),
            capture_output=True,
            env=value_free_child_environment(),
        )
    elapsed = time.monotonic() - started

    output = redact(
        result.stdout.decode("utf-8", "replace")
        + result.stderr.decode("utf-8", "replace"),
        secrets,
    )
    print(output, flush=True)
    status = "pass" if result.returncode == 0 else "FAIL"
    print(
        f"[sim] {job}: {status} in {elapsed:.1f}s (exit {result.returncode})",
        flush=True,
    )

    return {
        "job": job,
        "exit_code": result.returncode,
        "seconds": round(elapsed, 1),
        "gitlab_network": gitlab_network,
        "tail": output.splitlines()[-TAIL_LINES:],
    }


def prune_build_cache() -> None:
    print("[sim] docker builder prune -af (cold build measurement)", flush=True)
    subprocess.run(
        ["docker", "builder", "prune", "-af"],
        capture_output=True,
        text=True,
        env=value_free_child_environment(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", help="run one job by name")
    parser.add_argument(
        "--gitlab-network",
        action="store_true",
        help="run check in a Docker-executor-style job network (check only)",
    )
    parser.add_argument(
        "--all", action="store_true", help=f"run {', '.join(ALL_JOBS)} in order"
    )
    parser.add_argument(
        "--cold",
        action="store_true",
        help=(
            "prune this machine's ENTIRE build cache first, then time the job. "
            "Destroys cached layers for every other project too — if you only "
            "need the core image's build time, `docker build --no-cache -t "
            "team08-core:coldtime ./core` measures the dominant cost without "
            "taking anything away from anyone else"
        ),
    )
    args = parser.parse_args()

    if bool(args.job) == bool(args.all):
        parser.error("pass exactly one of --job or --all")
    # Refused rather than quietly ignored: a prune slows every later build on
    # this machine, including other projects', so it is a deliberate one-job
    # measurement and never a side effect of asking for the whole pipeline.
    if args.cold and args.all:
        parser.error("--cold works with a single --job only; run --all warm first")
    if args.gitlab_network and (args.all or args.job != "check"):
        parser.error("--gitlab-network is supported only with --job check")

    if not subprocess.run(
        ["docker", "info"],
        capture_output=True,
        env=value_free_child_environment(),
    ).returncode == 0:
        print(
            "run_ci_local: the docker daemon is not reachable — start Docker Desktop",
            file=sys.stderr,
        )
        return 2

    pipeline = load_pipeline()
    secrets = secret_values()
    jobs = ALL_JOBS if args.all else [args.job]

    if args.cold:
        prune_build_cache()

    results = []
    for job in jobs:
        result = run_job(
            pipeline, job, secrets, gitlab_network=bool(args.gitlab_network)
        )
        result["cold"] = bool(args.cold)
        results.append(result)
        if result["exit_code"] != 0:
            break  # the pipeline would stop here too

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"ci-local-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "simulated_at": stamp,
                "note": "local approximation of a GitLab runner — see this script's docstring for how it differs",
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[sim] wrote {path.relative_to(REPO)}", flush=True)

    return 0 if all(r["exit_code"] == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

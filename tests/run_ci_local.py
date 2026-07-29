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
artifacts. It proves the shell, the network shape and the commands. It does
not prove the runner.

This file is deliberately NOT referenced by `.gitlab-ci.yml`: it is a local
tool, and a tool that CI depends on is another thing that can fail on the
runner.

Usage (from this repo, with the upstream venv's python for pyyaml):

    python tests/run_ci_local.py --job check
    python tests/run_ci_local.py --all
    python tests/run_ci_local.py --job deploy --cold

Secrets are read from the machine environment only (APP_-prefixed, as the
platform's CI variables are), never printed, and replaced with a placeholder
before any output is written to disk.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

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


def load_pipeline() -> dict:
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
    lines = ["echo \"[sim] shell=$(readlink /proc/$$/exe)\""]
    lines += [str(item) for item in (*before, *script)]
    return "\n".join(lines) + "\n"


def docker_env_args(pipeline: dict) -> list[str]:
    args = []
    for name, value in (pipeline.get("variables") or {}).items():
        args += ["-e", f"{name}={value}"]
    for name, value in os.environ.items():
        if name.startswith("APP_"):
            args += ["-e", f"{name}={value}"]
    return args


def run_job(pipeline: dict, job: str, secrets: list[str]) -> dict:
    image = pipeline.get("default", {}).get("image", "docker:27.3.1")
    script = build_script(pipeline, job)
    command = [
        "docker", "run", "--rm", "-i",
        "--network", "host",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{REPO}:/w",
        "-w", "/w",
        *docker_env_args(pipeline),
        image,
        "sh", "-e", "-s",
    ]
    print(f"[sim] === {job} ===", flush=True)
    started = time.monotonic()
    # Bytes, not text=True. On Windows a text-mode stdin pipe rewrites "\n" to
    # "\r\n", the shell then hands every argument a trailing carriage return,
    # and the container reports things like `unrecognized arguments: --check`
    # for a flag that plainly exists. That was a defect in this simulator
    # masquerading as a defect in the pipeline, which is the exact failure
    # mode a simulator has to be trusted not to invent.
    result = subprocess.run(command, input=script.encode("utf-8"), capture_output=True)
    elapsed = time.monotonic() - started

    output = redact(
        result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace"),
        secrets,
    )
    print(output, flush=True)
    status = "pass" if result.returncode == 0 else "FAIL"
    print(f"[sim] {job}: {status} in {elapsed:.1f}s (exit {result.returncode})", flush=True)

    return {
        "job": job,
        "exit_code": result.returncode,
        "seconds": round(elapsed, 1),
        "tail": output.splitlines()[-TAIL_LINES:],
    }


def prune_build_cache() -> None:
    print("[sim] docker builder prune -af (cold build measurement)", flush=True)
    subprocess.run(["docker", "builder", "prune", "-af"], capture_output=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", help="run one job by name")
    parser.add_argument("--all", action="store_true", help=f"run {', '.join(ALL_JOBS)} in order")
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

    if not subprocess.run(["docker", "info"], capture_output=True).returncode == 0:
        print("run_ci_local: the docker daemon is not reachable — start Docker Desktop", file=sys.stderr)
        return 2

    pipeline = load_pipeline()
    secrets = secret_values()
    jobs = ALL_JOBS if args.all else [args.job]

    if args.cold:
        prune_build_cache()

    results = []
    for job in jobs:
        result = run_job(pipeline, job, secrets)
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

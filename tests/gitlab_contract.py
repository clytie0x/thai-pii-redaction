#!/usr/bin/env python3
"""Fast contract for branch checks and protected-main production jobs."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".gitlab-ci.yml"
BRANCH_PIPELINES = [
    {"if": '$CI_PIPELINE_SOURCE == "merge_request_event"'},
    {"if": '$CI_PIPELINE_SOURCE == "push" && $CI_COMMIT_BRANCH'},
    {"if": '$CI_PIPELINE_SOURCE == "web" && $CI_COMMIT_BRANCH'},
]
PROTECTED_MAIN_ONLY = [
    {
        "if": (
            '$CI_PIPELINE_SOURCE == "push" '
            '&& $CI_COMMIT_BRANCH == "main" '
            '&& $CI_COMMIT_REF_PROTECTED == "true"'
        )
    },
    {
        "if": (
            '$CI_PIPELINE_SOURCE == "web" '
            '&& $CI_COMMIT_BRANCH == "main" '
            '&& $CI_COMMIT_REF_PROTECTED == "true"'
        )
    },
]
PRODUCTION_JOBS = ("deploy", "acceptance", "logs", "ps", "restart")
PUBLIC_JOBS = ("check", *PRODUCTION_JOBS)
APP_VARIABLES = {
    "APP_AIGUARD_API_KEY",
    "APP_AIFT_ACCESS_CODE",
    "APP_AIFT_COOKIE_SIGNING_KEY",
    "APP_TOKENMIND_API_KEY",
}
EXPECTED_CHECKS = {
    "python3 sync/sync_from_upstream.py --check --verify-upstream",
    "python3 tests/auth_contract.py",
    "node tests/frontend_session_contract.mjs",
    "python3 tests/public_surface_contract.py",
    "python3 tests/hosted_core_contract.py",
    "python3 tests/build_context_contract.py",
    "python3 tests/secret_hygiene_contract.py",
    "python3 tests/release_source_contract.py",
    "python3 tests/gitlab_contract.py",
    "python3 tests/nginx_contract.py",
    "python3 tests/compose_contract.py",
}


def _evaluate(expression: str, context: dict[str, str]) -> bool:
    """Evaluate the deliberately small rules vocabulary used by this file."""

    for raw_atom in expression.split(" && "):
        atom = raw_atom.strip()
        bare = re.fullmatch(r"\$([A-Z0-9_]+)", atom)
        if bare:
            if not context.get(bare.group(1), ""):
                return False
            continue
        equality = re.fullmatch(r'\$([A-Z0-9_]+) == "([^"]*)"', atom)
        if equality:
            if context.get(equality.group(1), "") != equality.group(2):
                return False
            continue
        raise AssertionError(f"unsupported CI rule atom: {atom}")
    return True


def _matches(rules: list[dict[str, str]], context: dict[str, str]) -> bool:
    return any(_evaluate(rule["if"], context) for rule in rules)


def _included_jobs(
    pipeline: dict, *, source: str, branch: str = "", protected: bool = False
) -> set[str]:
    context = {
        "CI_PIPELINE_SOURCE": source,
        "CI_COMMIT_BRANCH": branch,
        "CI_COMMIT_REF_PROTECTED": "true" if protected else "false",
    }
    if not _matches(pipeline["workflow"]["rules"], context):
        return set()
    return {
        name for name in PUBLIC_JOBS if _matches(pipeline[name]["rules"], context)
    }


def main() -> int:
    pipeline = yaml.safe_load(CI.read_text(encoding="utf-8"))
    assert pipeline["stages"] == ["check", "deploy", "acceptance", "ops"]
    assert pipeline["workflow"]["rules"] == BRANCH_PIPELINES
    image = pipeline["default"]["image"]
    assert image.startswith("docker:27.3.1@sha256:")
    assert len(image.rsplit("@sha256:", 1)[1]) == 64
    assert pipeline["default"]["tags"] == ["team-08"]

    assert pipeline["check"]["rules"] == BRANCH_PIPELINES
    for name in PRODUCTION_JOBS:
        job = pipeline[name]
        assert job["rules"] == PROTECTED_MAIN_ONLY, name
        assert "only" not in job and "except" not in job, name

    for name in PUBLIC_JOBS:
        job = pipeline[name]
        assert job.get("tags", pipeline["default"]["tags"]) == ["team-08"], name

    check_only = {"check"}
    release = set(PUBLIC_JOBS)
    scenarios = {
        "feature push": (
            {"source": "push", "branch": "feature/demo"},
            check_only,
        ),
        "feature UI run": (
            {"source": "web", "branch": "feature/demo"},
            check_only,
        ),
        "merge request": (
            {"source": "merge_request_event"},
            check_only,
        ),
        "unprotected main first push": (
            {"source": "push", "branch": "main"},
            check_only,
        ),
        "protected main push": (
            {"source": "push", "branch": "main", "protected": True},
            release,
        ),
        "protected main UI pipeline": (
            {"source": "web", "branch": "main", "protected": True},
            release,
        ),
        "tag push": ({"source": "push"}, set()),
        "schedule": (
            {"source": "schedule", "branch": "main", "protected": True},
            set(),
        ),
        "API trigger": (
            {"source": "api", "branch": "main", "protected": True},
            set(),
        ),
    }
    for label, (context, expected) in scenarios.items():
        assert _included_jobs(pipeline, **context) == expected, label

    assert set(pipeline["check"]["script"]) == EXPECTED_CHECKS
    check_commands = "\n".join(
        [*pipeline["default"]["before_script"], *pipeline["check"]["script"]]
    )
    assert not APP_VARIABLES.intersection(re.findall(r"APP_[A-Z0-9_]+", check_commands))
    assert "TOKENMIND" not in check_commands.upper()
    assert "tests/platform_acceptance.py" not in check_commands
    for production_mutation in (
        "docker compose up",
        "docker compose down",
        "docker compose build",
        "docker compose restart",
        "docker restart",
        "docker stop",
        "docker rm",
    ):
        assert production_mutation not in check_commands
    assert pipeline["acceptance"]["needs"] == ["deploy"]
    for name in PRODUCTION_JOBS:
        assert pipeline[name]["resource_group"] == "team08-production", name
        assert pipeline[name]["environment"]["name"] == "$TEAM", name

    deploy_commands = "\n".join(pipeline["deploy"]["script"])
    for name in APP_VARIABLES:
        assert name in deploy_commands, name
    validation = deploy_commands.index("required protected application variables")
    mutation = deploy_commands.index('docker compose --env-file "$ENV_FILE"')
    assert validation < mutation

    raw = CI.read_text(encoding="utf-8")
    assert "docker compose --env-file \"$ENV_FILE\"" in raw
    assert 'LATEST_MAIN=$(git ls-remote origin refs/heads/main' in raw
    assert "tests/platform_acceptance.py" in raw
    assert "include:" not in raw
    assert "AUTO_DEVOPS" not in raw.upper()
    assert "--no-cache" not in "\n".join(pipeline["check"]["script"])

    handoff = (ROOT / "docs" / "GITLAB-HANDOFF.md").read_text(encoding="utf-8")
    for documented_bootstrap in (
        "first unprotected-main push",
        "Do not retry the first-push pipeline",
        "does not require a Protected runner",
        "Do not create the four application variables yet",
        "Build → Pipelines → Run pipeline",
        "Protected Environments are not required",
    ):
        assert documented_bootstrap in handoff, documented_bootstrap
    print(
        "gitlab contract ok: branch/MR check only; protected-main push/UI release; "
        "team-08 tagged and first-push safe"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

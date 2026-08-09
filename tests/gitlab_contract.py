#!/usr/bin/env python3
"""Fast contract for tagged main checks and protected-main releases."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
CI = ROOT / ".gitlab-ci.yml"
MAIN_ONLY = [{"if": '$CI_COMMIT_BRANCH == "main"'}]
PROTECTED_MAIN_ONLY = [
    {
        "if": (
            '$CI_COMMIT_BRANCH == "main" '
            '&& $CI_COMMIT_REF_PROTECTED == "true"'
        )
    }
]
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


def main() -> int:
    pipeline = yaml.safe_load(CI.read_text(encoding="utf-8"))
    assert pipeline["stages"] == ["check", "deploy", "acceptance", "ops"]
    assert pipeline["workflow"]["rules"] == MAIN_ONLY
    image = pipeline["default"]["image"]
    assert image.startswith("docker:27.3.1@sha256:")
    assert len(image.rsplit("@sha256:", 1)[1]) == 64
    assert pipeline["default"]["tags"] == ["team-08"]

    assert pipeline["check"]["rules"] == MAIN_ONLY
    jobs = ("deploy", "acceptance", "logs", "ps", "restart")
    for name in jobs:
        job = pipeline[name]
        assert job["rules"] == PROTECTED_MAIN_ONLY, name
        assert "only" not in job and "except" not in job, name

    for name in ("check", *jobs):
        job = pipeline[name]
        assert job.get("tags", pipeline["default"]["tags"]) == ["team-08"], name

    assert set(pipeline["check"]["script"]) == EXPECTED_CHECKS
    assert pipeline["acceptance"]["needs"] == ["deploy"]
    assert pipeline["deploy"]["resource_group"] == "team08-production"
    assert pipeline["acceptance"]["resource_group"] == "team08-production"

    raw = CI.read_text(encoding="utf-8")
    assert "docker compose --env-file \"$ENV_FILE\"" in raw
    assert 'LATEST_MAIN=$(git ls-remote origin refs/heads/main' in raw
    assert "tests/platform_acceptance.py" in raw
    assert "--no-cache" not in "\n".join(pipeline["check"]["script"])
    print("gitlab contract ok: team-08 tagged check; protected-main release and ops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

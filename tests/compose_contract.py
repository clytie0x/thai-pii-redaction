#!/usr/bin/env python3
"""Validate normalized Compose policy without exposing live secrets."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REVISION = "0123456789abcdef0123456789abcdef01234567"
SAFE_ENV = {
    "APP_AIGUARD_API_KEY": "synthetic-core-key-000000000000",
    "APP_TOKENMIND_API_KEY": "synthetic-provider-key-000000000000",
    "APP_AIFT_ACCESS_CODE": "synthetic-access-code-000000000000",
    "APP_AIFT_COOKIE_SIGNING_KEY": ("synthetic-cookie-signing-key-000000000000000000"),
    "CI_COMMIT_SHA": REVISION,
}


def rendered_config() -> dict:
    passthrough = {
        "COMSPEC",
        "APPDATA",
        "DOCKER_CERT_PATH",
        "DOCKER_CONTEXT",
        "DOCKER_HOST",
        "DOCKER_TLS_VERIFY",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "PATH",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
    }
    environment = {
        key: value for key, value in os.environ.items() if key in passthrough
    }
    environment.update(SAFE_ENV)
    environment["COMPOSE_DISABLE_ENV_FILE"] = "true"
    with tempfile.TemporaryDirectory(prefix="aift-compose-contract-") as temp_dir:
        env_file = Path(temp_dir) / "synthetic.env"
        env_file.write_text(
            "".join(f"{key}={value}\n" for key, value in SAFE_ENV.items()),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                str(env_file),
                "--project-directory",
                str(REPO),
                "config",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            env=environment,
        )
    if result.returncode != 0:
        raise AssertionError(
            "docker compose could not render the deployment: " + result.stderr.strip()
        )
    return json.loads(result.stdout)


def check_port(service: dict, *, published: str, target: int) -> None:
    assert service.get("ports") == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": target,
            "published": published,
            "protocol": "tcp",
        }
    ]


def check_common(name: str, service: dict) -> None:
    assert service.get("restart") == "unless-stopped", name
    assert service.get("healthcheck"), name
    assert service.get("logging") == {
        "driver": "json-file",
        "options": {"max-file": "3", "max-size": "50m"},
    }, name
    limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
    assert float(limits.get("cpus", 0)) > 0, name
    assert int(limits.get("memory", 0)) > 0, name
    assert not service.get("privileged", False), name
    assert not service.get("devices"), name
    assert service.get("network_mode") != "host", name
    assert service.get("read_only") is True, name
    assert "no-new-privileges:true" in (service.get("security_opt") or []), name
    assert limits.get("pids") in {128, 256}, name
    assert service.get("stop_grace_period") == "3m30s", name
    for mount in service.get("volumes") or []:
        assert mount.get("type") != "bind", name
        assert mount.get("source") != "/var/run/docker.sock", name
    build = service.get("build", {})
    assert build.get("args", {}).get("AIFT_BUILD_COMMIT") == REVISION, name
    assert Path(build.get("context", "")).resolve() == (REPO / name).resolve(), name


def main() -> int:
    try:
        services = rendered_config().get("services", {})
        assert set(services) == {"web", "api", "core"}
        for name, service in services.items():
            check_common(name, service)

        check_port(services["web"], published="20070", target=3000)
        check_port(services["api"], published="20071", target=8000)
        assert not services["core"].get("ports")
        assert services["web"].get("tmpfs") == [
            "/var/cache/nginx:size=32m",
            "/var/run:size=4m",
            "/tmp:size=4m",
        ]
        assert services["api"].get("tmpfs") == [
            "/var/cache/nginx:size=64m",
            "/var/run:size=4m",
            "/tmp:size=4m",
            "/etc/nginx/conf.d:size=4m",
        ]
        assert services["core"].get("tmpfs") == ["/tmp:size=128m,mode=1777"]
        assert services["core"].get("cap_drop") == ["ALL"]
        assert services["web"]["healthcheck"]["test"] == [
            "CMD",
            "/usr/local/bin/aift-healthcheck",
        ]
        assert services["api"]["healthcheck"]["test"] == [
            "CMD",
            "/usr/local/bin/aift-healthcheck",
        ]
        assert services["core"]["healthcheck"]["test"] == [
            "CMD",
            "python",
            "/app/healthcheck.py",
        ]

        api_environment = services["api"].get("environment", {})
        core_environment = services["core"].get("environment", {})
        assert api_environment.get("AIGUARD_API_KEY") == SAFE_ENV["APP_AIGUARD_API_KEY"]
        assert (
            core_environment.get("AIGUARD_API_KEY") == SAFE_ENV["APP_AIGUARD_API_KEY"]
        )
        assert (
            core_environment.get("TOKENMIND_API_KEY")
            == SAFE_ENV["APP_TOKENMIND_API_KEY"]
        )
        assert (
            core_environment.get("AIFT_ACCESS_CODE") == SAFE_ENV["APP_AIFT_ACCESS_CODE"]
        )
        assert (
            core_environment.get("AIFT_COOKIE_SIGNING_KEY")
            == SAFE_ENV["APP_AIFT_COOKIE_SIGNING_KEY"]
        )
        assert "AIGUARD_PDF_MAX_PAGES" not in core_environment
        assert services["core"]["deploy"]["resources"]["limits"]["memory"] == str(
            2 * 1024 * 1024 * 1024
        )
        for relative, signal in (
            ("web/healthcheck.sh", "kill -QUIT 1"),
            ("api/healthcheck.sh", "kill -TERM 1"),
            ("core/healthcheck.py", "os.kill(1, 15)"),
        ):
            source = (REPO / relative).read_text(encoding="utf-8")
            assert signal in source, relative
            assert "3" in source, relative
    except (
        AssertionError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(
            f"compose contract failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1
    print(
        "compose contract ok: loopback ports, per-service health/resources/logging, "
        "volatile storage, safe build identity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

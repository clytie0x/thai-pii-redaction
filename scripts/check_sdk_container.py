"""Smoke the existing SDK image using only owned, network-isolated containers."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

if __package__:
    from .probe_sdk_container import EXPECTED
    from .run_sdk_api_collection import CheckFailed, child_environment, controlled_interrupts
else:
    from probe_sdk_container import EXPECTED
    from run_sdk_api_collection import CheckFailed, child_environment, controlled_interrupts

LABEL = "org.aiguard.sdk-ci"
REVISION_LABEL = "org.opencontainers.image.revision"
ID = re.compile(r"[0-9a-f]{64}")


def validate_probe(raw):
    parsed = None
    try:
        parsed = json.loads(raw)
    except ValueError:
        pass
    if (
        not isinstance(parsed, dict)
        or set(parsed) != set(EXPECTED)
        or any(
            type(parsed[key]) is not type(value) or parsed[key] != value
            for key, value in EXPECTED.items()
        )
    ):
        raise CheckFailed("image_http_probe_failed")
    return parsed


class Docker:
    def __init__(self, executable, owner):
        self.executable, self.owner = executable, owner
        self.created, self.uncertain = {}, set()

    def call(self, arguments, *, allow_error=False, input=None, timeout=20):
        result = subprocess.run(
            [self.executable, "--host", "unix:///var/run/docker.sock", *arguments],
            env=child_environment(os.environ),
            input=input,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode and not allow_error:
            raise CheckFailed("docker_command_failed")
        return result

    def image(self, reference, revision):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._/:@-]{0,200}", reference) or not re.fullmatch(
            r"[0-9a-f]{40}", revision
        ):
            raise CheckFailed("image_reference_invalid")
        image = self.call(["image", "inspect", "--format", "{{.Id}}", reference]).stdout.strip()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise CheckFailed("image_identity_invalid")
        actual = self.call(
            [
                "image",
                "inspect",
                "--format",
                '{{index .Config.Labels "' + REVISION_LABEL + '"}}',
                image,
            ]
        ).stdout.strip()
        if actual != revision:
            raise CheckFailed("image_revision_mismatch")
        return image

    def create(self, image, env_file=None):
        name = "aiguard-sdk-ci-" + uuid.uuid4().hex
        self.created[name] = None
        self.uncertain.add(name)
        arguments = [
            "create",
            "--name",
            name,
            "--label",
            LABEL + "=" + self.owner,
            "--network",
            "none",
        ]
        if env_file is not None:
            arguments.extend(["--env-file", str(env_file)])
        identifier = self.call([*arguments, image]).stdout.strip()
        if not ID.fullmatch(identifier):
            raise CheckFailed("container_identity_invalid")
        self.created[name] = identifier
        self.uncertain.discard(name)
        return identifier

    def require_refusal(self, identifier):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = (
                self.call(
                    [
                        "container",
                        "inspect",
                        "--format",
                        "{{.State.Running}} {{.State.ExitCode}}",
                        identifier,
                    ]
                )
                .stdout.strip()
                .split()
            )
            if state and state[0] == "false":
                logs = self.call(["logs", "--tail", "20", identifier])
                if (
                    state == ["false", "1"]
                    and "without AMPHRANG_API_KEY" in logs.stdout + logs.stderr
                ):
                    return
                raise CheckFailed("missing_key_refusal_invalid")
            time.sleep(0.1)
        raise CheckFailed("missing_key_refusal_timeout")

    def cleanup(self):
        clean = True
        for name, saved in self.created.items():
            try:
                metadata = self.call(
                    [
                        "container",
                        "inspect",
                        "--format",
                        '{{.Id}} {{index .Config.Labels "' + LABEL + '"}}',
                        name,
                    ],
                    allow_error=True,
                )
                if metadata.returncode:
                    absent = self.call(
                        [
                            "container",
                            "ls",
                            "--all",
                            "--no-trunc",
                            "--filter",
                            "name=^/" + name + "$",
                            "--format",
                            "{{.ID}}",
                        ],
                        allow_error=True,
                    )
                    clean = (
                        clean
                        and absent.returncode == 0
                        and not absent.stdout.strip()
                        and name not in self.uncertain
                    )
                    continue
                fields = metadata.stdout.strip().split()
                if (
                    len(fields) != 2
                    or not ID.fullmatch(fields[0])
                    or fields[1] != self.owner
                    or (saved and fields[0] != saved)
                ):
                    clean = False
                    continue
                identifier = fields[0]
                self.call(["container", "rm", "--force", identifier], allow_error=True)
                remaining = self.call(
                    [
                        "container",
                        "ls",
                        "--all",
                        "--no-trunc",
                        "--filter",
                        "id=" + identifier,
                        "--format",
                        "{{.ID}}",
                    ],
                    allow_error=True,
                )
                if remaining.returncode or remaining.stdout.strip():
                    clean = False
                else:
                    self.uncertain.discard(name)
            except (OSError, subprocess.TimeoutExpired, CheckFailed):
                clean = False
        return clean and not self.uncertain


def run_check(engine, image, revision, directory):
    result = {"passed": False, "keyless_refused": False, "failure": None}
    env_file = None
    try:
        image_id = engine.image(image, revision)
        result.update(image_id=image_id, source_revision=revision)
        keyless = engine.create(image_id)
        engine.call(["start", keyless])
        engine.require_refusal(keyless)
        result["keyless_refused"] = True
        descriptor, name = tempfile.mkstemp(prefix=".sdk-ci-key-", dir=directory)
        env_file = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(
                "AMPHRANG_API_KEY="
                + secrets.token_urlsafe(32)
                + "\nAMPHRANG_NER_ENGINE=thainer\nPYTHAINLP_OFFLINE=1\n"
            )
        keyed = engine.create(image_id, env_file)
        engine.call(["start", keyed])
        program = Path(__file__).with_name("probe_sdk_container.py").read_text(encoding="utf-8")
        raw = engine.call(
            ["exec", "--interactive", keyed, "python", "-"], input=program, timeout=40
        )
        result["probe"] = validate_probe(raw.stdout)
        result["passed"] = True
    except CheckFailed as error:
        result["failure"] = str(error)
    except Exception:
        result["failure"] = "sdk_image_check_failed"
    finally:
        try:
            result["owned_containers_removed"] = engine.cleanup()
        except Exception:
            result["owned_containers_removed"] = False
        try:
            if env_file is not None:
                env_file.unlink(missing_ok=True)
            result["private_key_file_removed"] = True
        except OSError:
            result["private_key_file_removed"] = False
        if not result["owned_containers_removed"] or not result["private_key_file_removed"]:
            result["passed"] = False
            result["failure"] = result["failure"] or "owned_cleanup_unverified"
    result["limits"] = (
        "Existing SDK Dockerfile, floating build inputs; isolated container HTTP only. Not host-port, live-provider, reproducible-build or production acceptance."
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--owner", default=uuid.uuid4().hex)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    executable = shutil.which("docker")
    if (
        sys.platform != "linux"
        or executable is None
        or args.report.exists()
        or not re.fullmatch(r"[a-zA-Z0-9_-]{8,80}", args.owner)
    ):
        print(
            "SDK image gate requires local Linux Docker and a fresh report path.", file=sys.stderr
        )
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with controlled_interrupts("sdk_image_check_interrupted"):
        result = run_check(
            Docker(executable, args.owner), args.image, args.revision, args.report.parent
        )
    with args.report.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(
        "Owned SDK image checks passed."
        if result["passed"]
        else "SDK image gate failed; see the minimized report."
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Use the job's pinned PostgreSQL service tools for synthetic CI backup drills."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = {"pg_dump", "pg_restore"}
DATABASE = re.compile(r"postgres|aig_restore_[0-9a-f]{32}")
PG_ENV = (
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
    "PGSSLMODE",
    "PGCONNECT_TIMEOUT",
)


def command(container, tool, arguments, environment):
    if (
        not re.fullmatch(r"[0-9a-f]{64}", container)
        or tool not in TOOLS
        or environment.get("PGHOST") not in {"127.0.0.1", "localhost"}
        or environment.get("PGPORT") != "5432"
        or not DATABASE.fullmatch(environment.get("PGDATABASE", ""))
        or not environment.get("PGUSER")
        or environment.get("PGSSLROOTCERT")
    ):
        raise ValueError("synthetic_postgres_service_configuration_invalid")
    for argument in arguments:
        if not isinstance(argument, str) or len(argument) > 4096 or "\0" in argument:
            raise ValueError("synthetic_postgres_service_argument_invalid")
        if argument.startswith("--dbname=") and not DATABASE.fullmatch(argument.split("=", 1)[1]):
            raise ValueError("synthetic_postgres_service_database_invalid")
        common = {"--no-owner", "--no-privileges"}
        allowed = (
            (
                argument in common | {"--format=custom"}
                or re.fullmatch(r"--snapshot=[0-9A-F]{8}-[0-9A-F]{8}-[0-9]+", argument)
                or re.fullmatch(
                    r"--exclude-table-data=\*\.governance_(operations|restore_sessions|restore_journal)",
                    argument,
                )
            )
            if tool == "pg_dump"
            else (
                argument in common | {"--single-transaction", "--exit-on-error"}
                or argument.startswith("--dbname=")
            )
        )
        if not allowed:
            raise ValueError("synthetic_postgres_service_argument_invalid")
    result = ["docker", "exec", "--interactive"]
    for name in PG_ENV:
        if name in environment:
            # Docker inherits these values; credentials never enter argv.
            result.extend(["--env", name])
    return [*result, container, tool, *arguments]


def run_tool(container, tool, arguments):
    try:
        arguments = command(container, tool, arguments, os.environ)
    except ValueError:
        print("Synthetic PostgreSQL service tool refused invalid configuration.", file=sys.stderr)
        raise SystemExit(2) from None
    os.execvpe(arguments[0], arguments, os.environ)


def prepare(container, output, runner=subprocess.run):
    if not re.fullmatch(r"[0-9a-f]{64}", container) or output.exists():
        raise ValueError("synthetic_postgres_tools_target_invalid")
    result = runner(
        ["docker", "exec", container, "pg_dump", "--version"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode or not re.fullmatch(
        r"pg_dump \(PostgreSQL\) 18\.[^\n]+\n?", result.stdout
    ):
        raise ValueError("synthetic_postgres_tools_version_invalid")
    output.mkdir(mode=0o700)
    output.chmod(0o700)
    source = str(Path(__file__).resolve())
    for tool in sorted(TOOLS):
        path = output / tool
        path.write_text(
            f"#!{sys.executable}\nimport runpy,sys\n"
            f"runpy.run_path({source!r})['run_tool']({container!r},{tool!r},sys.argv[1:])\n",
            encoding="utf-8",
        )
        path.chmod(0o700)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    args = parser.parse_args()
    if (
        sys.platform != "linux"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or not shutil.which("docker")
    ):
        parser.error("This helper requires the Linux Actions job's own PostgreSQL service.")
    root = Path(os.environ["RUNNER_TEMP"]).resolve()
    output = prepare(args.container, root / "enterprise-postgres-tools")
    private = root / "enterprise-operations"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env:
        env.write(f"AIGUARD_OPERATIONS_PG_BIN={output}\nAIGUARD_OPERATIONS_PRIVATE_DIR={private}\n")
    print("Pinned service PostgreSQL 18 tools prepared for isolated synthetic recovery drills.")


if __name__ == "__main__":
    main()

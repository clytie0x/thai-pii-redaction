"""Run synthetic gates in a new owned loopback PostgreSQL 18 cluster; always stop it."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def private_directory(path):
    path.mkdir(parents=True, exist_ok=False)
    if os.name == "nt":
        import getpass

        result = subprocess.run(
            [
                "icacls",
                str(path),
                "/inheritance:r",
                "/grant:r",
                getpass.getuser() + ":(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F",
                "*S-1-5-32-544:(OI)(CI)F",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode:
            raise RuntimeError("private_directory_failed")
    else:
        path.chmod(0o700)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", required=True, type=Path)
    parser.add_argument("--full-enterprise", action="store_true")
    args = parser.parse_args()
    root = ROOT / ".superpowers" / ("m10-" + uuid4().hex)
    private_directory(root)
    suffix = ".exe" if os.name == "nt" else ""

    def tool(name, *params):
        result = subprocess.run(
            [str(args.pg_bin / (name + suffix)), *map(str, params)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError("owned_postgres_command_failed")

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    started = False
    try:
        tool(
            "initdb",
            "-D",
            root / "data",
            "-U",
            "synthetic_operator",
            "-A",
            "trust",
            "--encoding=UTF8",
        )
        tool(
            "pg_ctl",
            "-D",
            root / "data",
            "-l",
            root / "postgres.log",
            "-o",
            f"-h 127.0.0.1 -p {port} -c max_connections=24",
            "-w",
            "start",
        )
        started = True
        file = root / "database.json"
        file.write_text(
            json.dumps(
                {
                    "purpose": "synthetic_enterprise_tests",
                    "dsn": f"host=127.0.0.1 port={port} dbname=postgres user=synthetic_operator",
                }
            ),
            encoding="utf-8",
        )
        env = {
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONPATH": str(ROOT),
            "AIGUARD_TEST_DB_FILE": str(file),
            "AIGUARD_OPERATIONS_PG_BIN": str(args.pg_bin),
            "AIGUARD_OPERATIONS_PRIVATE_DIR": str(root),
            "PYTEST_ADDOPTS": "",
        }
        origin = subprocess.run(
            [
                sys.executable,
                "-c",
                "import pathlib,pii_redactor,app.enterprise; "
                "assert pathlib.Path(pii_redactor.__file__).resolve().is_relative_to(pathlib.Path.cwd()); "
                "assert pathlib.Path(app.enterprise.__file__).resolve().is_relative_to(pathlib.Path.cwd())",
            ],
            cwd=ROOT,
            env=env,
        )
        if origin.returncode:
            raise RuntimeError("source_origin_mismatch")
        suites = [
            "tests/test_enterprise_readiness.py",
            "tests/test_enterprise_recovery.py",
            "tests/test_audit_checkpoint.py",
            "tests/test_enterprise_operations.py",
        ]
        if args.full_enterprise:
            sys.path.insert(0, str(ROOT))
            from scripts.run_enterprise_tests import REQUIRED

            suites = list(dict.fromkeys([*REQUIRED, *suites]))
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                *suites,
                "-q",
                "--tb=short",
                "-o",
                "addopts=",
                "--junitxml=" + str(root / "results.xml"),
            ],
            cwd=ROOT,
            env=env,
        )
        print("Minimized local report: " + str(root / "results.xml"))
        if result.returncode:
            return result.returncode
        cases = list(ET.parse(root / "results.xml").iter("testcase"))
        if not cases or any(c.find("skipped") is not None for c in cases):
            print("mandatory_operations_suite_skipped", file=sys.stderr)
            return 1
        return 0
    finally:
        if started:
            tool("pg_ctl", "-D", root / "data", "-m", "immediate", "-w", "stop")
            print("Owned synthetic cluster stopped; no owner database was selected.")


if __name__ == "__main__":
    raise SystemExit(main())

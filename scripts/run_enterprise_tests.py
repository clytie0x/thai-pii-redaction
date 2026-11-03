"""Mandatory real-PostgreSQL gate; missing setup or skipped suites are failures."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "tests/test_governance_models.py",
    "tests/test_governance_store.py",
    "tests/test_governance_authority.py",
    "tests/test_governance_registry.py",
    "tests/test_governance_audit_view.py",
    "tests/test_enterprise_identity.py",
    "tests/test_enterprise_sessions.py",
    "tests/test_enterprise_settings.py",
    "tests/test_enterprise_oidc.py",
    "tests/test_enterprise_api.py",
    "tests/test_enterprise_cli.py",
    "tests/test_enterprise_migrations.py",
    "tests/test_enterprise_test_gate.py",
    "tests/test_governance_subjects.py",
    "tests/test_governance_consent.py",
    "tests/test_subject_portal.py",
    "tests/test_governance_collection.py",
    "tests/test_governance_execution.py",
    "tests/test_governance_outbox.py",
    "tests/test_managed_ui.py",
    "tests/test_governance_holds.py",
    "tests/test_governance_retention.py",
    "tests/test_governance_integration.py",
    "tests/test_enterprise_integrated_routes.py",
    "tests/test_governance_rights.py",
    "tests/test_rights_delivery.py",
    "tests/test_rights_closure.py",
    "tests/test_rights_api.py",
    "tests/test_governance_organization_controls.py",
    "tests/test_governance_organization_domains.py",
    "tests/test_governance_controls_routes.py",
    "tests/test_governance_controls_ui.py",
    "tests/test_governance_processing_controls.py",
    "tests/test_processing_control_routes.py",
    "tests/test_processing_controls_ui.py",
    "tests/test_rights_renewal.py",
    "tests/test_enterprise_rights_composition.py",
    "tests/test_enterprise_operator_cli.py",
    "tests/test_enterprise_worker_runtime.py",
    "tests/test_enterprise_operations.py",
    "tests/test_enterprise_readiness.py",
    "tests/test_enterprise_recovery.py",
    "tests/test_audit_checkpoint.py",
    "tests/test_enterprise_key_fences.py",
    "tests/test_enterprise_runtime_role.py",
    "tests/test_enterprise_request_gate.py",
    "tests/test_enterprise_audit_bounds.py",
    "tests/test_enterprise_verifier_snapshot.py",
    "tests/test_enterprise_artifact_identity.py",
    "tests/test_artifact_build_residue.py",
    "tests/test_enterprise_control_recovery.py",
    "tests/test_enterprise_initial_activation.py",
]


def report_valid(path):
    try:
        cases = list(ET.parse(path).iter("testcase"))
        if not cases or any(
            any(c.find(tag) is not None for tag in ("failure", "error", "skipped")) for c in cases
        ):
            return False
        modules = {part for c in cases for part in c.get("classname", "").split(".")}
        return all(Path(name).stem in modules for name in REQUIRED)
    except (OSError, ET.ParseError):
        return False


def preflight():
    filename = os.environ.get("AIGUARD_TEST_DB_FILE")
    if not filename:
        return "mandatory_database_configuration_missing"
    try:
        file = Path(filename)
        if file.stat().st_size > 65536:
            return "mandatory_database_configuration_invalid"
        settings = json.loads(file.read_text(encoding="utf-8"))
        if (
            not isinstance(settings, dict)
            or settings.get("purpose") != "synthetic_enterprise_tests"
        ):
            return "test_database_not_marked_synthetic"
        if not isinstance(settings.get("dsn"), str):
            return "mandatory_database_configuration_invalid"
    except (ValueError, TypeError, OSError):
        return "mandatory_database_configuration_invalid"
    if any(
        importlib.util.find_spec(name) is None
        for name in ("pytest", "psycopg", "authlib", "joserfc", "fastapi")
    ):
        return "enterprise_dependency_unavailable"
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    try:
        info = conninfo_to_dict(settings["dsn"])
        if info.get("host") not in {"127.0.0.1", "localhost", "::1"} or info.get(
            "hostaddr"
        ) not in {None, "127.0.0.1", "::1"}:
            return "test_database_not_loopback"
        with psycopg.connect(settings["dsn"], connect_timeout=5) as connection:
            if not 180000 <= connection.info.server_version < 190000:
                return "test_database_version_unsupported"
            connection.execute("SELECT 1")
    except psycopg.Error:
        return "mandatory_database_unavailable"
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    problem = preflight()
    if problem:
        print(problem, file=sys.stderr)
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *REQUIRED,
            "-q",
            "-rs",
            "--tb=short",
            "-o",
            "addopts=",
            "--junitxml=" + str(args.report.resolve()),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1", "PYTEST_ADDOPTS": ""},
    )
    if result.returncode:
        return result.returncode
    if not report_valid(args.report):
        print("mandatory_suite_missing_skipped_or_failed", file=sys.stderr)
        return 1
    print("Every mandatory enterprise suite executed without skips.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

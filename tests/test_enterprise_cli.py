"""Operator commands fail closed and never echo credential-file contents."""

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from app.enterprise.__main__ import main


def test_unconfigured_serve_fails_without_traceback_or_private_values(monkeypatch, capsys):
    for name in list(__import__("os").environ):
        if name.startswith("AIGUARD_ENTERPRISE_"):
            monkeypatch.delenv(name)
    assert main(["serve"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.strip() == "configuration_invalid"


def test_enrollment_file_error_does_not_echo_its_contents(tmp_path, monkeypatch, capsys):
    path = tmp_path / "enrollment.key"
    path.write_text("private-enrollment-marker")
    monkeypatch.delenv("AIGUARD_ENTERPRISE_ORGANIZATION_ID", raising=False)
    assert main(["enroll", "--file", str(path)]) == 1
    output = capsys.readouterr()
    assert "private-enrollment-marker" not in output.out + output.err

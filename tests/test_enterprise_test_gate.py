"""The dedicated gate must execute every named suite, never silently skip it."""

import json
from pathlib import Path

from scripts.run_enterprise_tests import REQUIRED, main, report_valid


def report(tmp_path, *, missing=None, skipped=None):
    rows = []
    for name in REQUIRED:
        stem = Path(name).stem
        if stem == missing:
            continue
        child = "<skipped/>" if stem == skipped else ""
        rows.append(f'<testcase classname="tests.{stem}" name="synthetic">{child}</testcase>')
    p = tmp_path / "report.xml"
    p.write_text("<testsuites><testsuite>" + "".join(rows) + "</testsuite></testsuites>")
    return p


def test_required_report_rejects_missing_or_skipped_suite(tmp_path):
    stem = Path(REQUIRED[0]).stem
    assert not report_valid(report(tmp_path, missing=stem))
    assert not report_valid(report(tmp_path, skipped=stem))
    assert report_valid(report(tmp_path))


def test_gate_rejects_missing_database_without_starting_pytest(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("AIGUARD_TEST_DB_FILE", raising=False)
    assert main(["--report", str(tmp_path / "unused.xml")]) == 2
    assert not (tmp_path / "unused.xml").exists()
    assert "database" in capsys.readouterr().err


def test_gate_rejects_unmarked_secret_file_without_echoing_it(tmp_path, monkeypatch, capsys):
    key = tmp_path / "database.key"
    key.write_text(json.dumps({"dsn": "host=127.0.0.1 password=private-marker"}))
    monkeypatch.setenv("AIGUARD_TEST_DB_FILE", str(key))
    assert main(["--report", str(tmp_path / "unused.xml")]) == 2
    output = capsys.readouterr()
    assert "private-marker" not in output.out + output.err

"""Tests for CLI: cli.py and demo_cli.py."""

import pytest


def test_ai_guard_sanitize_nonexistent_file(tmp_path, capsys):
    """sanitize with nonexistent file should print error and exit 1."""
    from amprang import cli

    args_ns = type(
        "Args",
        (),
        {
            "file": str(tmp_path / "nonexistent.txt"),
            "output": None,
            "fmt": "txt",
            "provider": "fake",
            "overwrite": False,
        },
    )()
    with pytest.raises(SystemExit) as exc:
        cli.cmd_sanitize(args_ns)
    assert exc.value.code == 1


def test_ai_guard_sanitize_real_file(tmp_path, capsys):
    """sanitize with real file should print session id."""
    from amprang import cli

    infile = tmp_path / "input.txt"
    infile.write_text("Hello world.", encoding="utf-8")

    args_ns = type(
        "Args",
        (),
        {
            "file": str(infile),
            "output": None,
            "fmt": "txt",
            "provider": "fake",
            "overwrite": False,
        },
    )()
    cli.cmd_sanitize(args_ns)
    captured = capsys.readouterr()
    assert "Session:" in captured.out


def test_ai_guard_sanitize_with_output(tmp_path, capsys):
    """sanitize with --output writes file."""
    from amprang import cli

    infile = tmp_path / "input.txt"
    infile.write_text("Call 081-234-5678 please.", encoding="utf-8")
    outfile = tmp_path / "output.txt"

    args_ns = type(
        "Args",
        (),
        {
            "file": str(infile),
            "output": str(outfile),
            "fmt": "txt",
            "provider": "fake",
            "overwrite": False,
        },
    )()
    cli.cmd_sanitize(args_ns)
    assert outfile.exists()


def test_ai_guard_report_nonexistent_file(tmp_path, capsys):
    """report with nonexistent file should exit 1."""
    from amprang import cli

    args_ns = type("Args", (), {"file": str(tmp_path / "nonexistent.txt")})()
    with pytest.raises(SystemExit) as exc:
        cli.cmd_report(args_ns)
    assert exc.value.code == 1


def test_ai_guard_report_real_file(tmp_path, capsys):
    """report with real file should print risk report."""
    from amprang import cli

    infile = tmp_path / "input.txt"
    infile.write_text("Call 081-234-5678 please.", encoding="utf-8")

    args_ns = type("Args", (), {"file": str(infile)})()
    cli.cmd_report(args_ns)
    captured = capsys.readouterr()
    assert "Risk Level:" in captured.out


def test_ai_guard_argparse_help():
    """Parser should include both subcommands."""

    from amprang import cli

    # Verify the module has the required functions
    assert hasattr(cli, "main")
    assert hasattr(cli, "cmd_sanitize")
    assert hasattr(cli, "cmd_report")


def test_demo_cli_imports():
    """demo_cli.py should import cleanly."""
    import demo_cli

    assert hasattr(demo_cli, "main")
    assert callable(demo_cli.main)


def test_ai_guard_sanitize_with_phone_number(tmp_path, capsys):
    """sanitize should detect and anonymize Thai phone numbers."""
    from amprang import cli

    infile = tmp_path / "input.txt"
    infile.write_text("My phone: 081-234-5678", encoding="utf-8")

    args_ns = type(
        "Args",
        (),
        {
            "file": str(infile),
            "output": None,
            "fmt": "txt",
            "provider": "fake",
            "overwrite": False,
        },
    )()
    cli.cmd_sanitize(args_ns)
    captured = capsys.readouterr()
    assert "Entities detected:" in captured.out
    # Should detect at least 1 entity (phone number)
    assert "FP=" in captured.out


def test_ai_guard_report_with_multiple_entities(tmp_path, capsys):
    """report should count multiple entity types."""
    from amprang import cli

    infile = tmp_path / "input.txt"
    # Include both phone and date patterns
    infile.write_text(
        "Contact: 081-234-5678 or email test@example.com. Born 1990-05-15", encoding="utf-8"
    )

    args_ns = type("Args", (), {"file": str(infile)})()
    cli.cmd_report(args_ns)
    captured = capsys.readouterr()
    assert "Risk Level:" in captured.out
    assert "Total entities detected:" in captured.out


def test_ai_guard_sanitize_prints_masked_not_original(tmp_path, capsys):
    """Without --output, the 'Sanitized Output' section must show the MASKED
    text, not the re-identified original (which equals the input under the
    fake LLM). It used to print reverse_result.text — the un-redacted original."""
    from amprang import cli

    infile = tmp_path / "input.txt"
    infile.write_text("โทร 081-234-5678 นะครับ", encoding="utf-8")
    args_ns = type(
        "Args",
        (),
        {
            "file": str(infile),
            "output": None,
            "fmt": "txt",
            "provider": "fake",
            "overwrite": False,
        },
    )()
    cli.cmd_sanitize(args_ns)
    out = capsys.readouterr().out
    assert "--- Sanitized Output ---" in out
    # the real phone must NOT surface under the "Sanitized" header
    assert "081-234-5678" not in out


def test_ai_guard_report_dedupes_fp_tb_overlap(tmp_path, capsys, monkeypatch):
    """report must not double-count a value matched by BOTH detectors (an ID or
    phone the NER also tags). It used to sum len(fp)+len(tb) with no dedupe."""
    import amprang.engine.detectors.tb_detector as tbd
    from amprang import cli

    phone = "081-234-5678"

    class FakeNER:
        def tag(self, chunk):
            # force a TB span over the phone → overlaps the FP PHONE hit
            return [(phone, "B-PERSON")] if phone in chunk else []

    monkeypatch.setitem(tbd._ner_cache, "thainer", FakeNER())
    monkeypatch.setenv("AMPRANG_NER_ENGINE", "thainer")

    infile = tmp_path / "input.txt"
    infile.write_text(f"เบอร์ {phone}", encoding="utf-8")
    args_ns = type("Args", (), {"file": str(infile)})()
    cli.cmd_report(args_ns)
    out = capsys.readouterr().out
    assert "Total entities detected: 1" in out


def test_ai_guard_report_no_pii(tmp_path, capsys):
    """report with clean text should show Low risk."""
    from amprang import cli

    infile = tmp_path / "input.txt"
    infile.write_text("This is just some random text with no PII.", encoding="utf-8")

    args_ns = type("Args", (), {"file": str(infile)})()
    cli.cmd_report(args_ns)
    captured = capsys.readouterr()
    assert "Risk Level: Low" in captured.out


def test_ai_guard_report_uses_the_canonical_fallback_detector(tmp_path, capsys):
    from amprang import cli

    infile = tmp_path / "input.txt"
    infile.write_text("รหัส 1234567890123", encoding="utf-8")

    cli.cmd_report(type("Args", (), {"file": str(infile)})())
    out = capsys.readouterr().out

    assert "Total entities detected: 1" in out
    assert "Structured PII (FP): 1" in out
    assert "Name/Address/Date (TB): 0" in out

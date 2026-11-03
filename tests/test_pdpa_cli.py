import json
import sys

import pytest


def run_cli(monkeypatch, *args):
    import ai_guard

    monkeypatch.setattr(sys, "argv", ["ai_guard", "pdpa", *map(str, args)])
    ai_guard.main()


def test_real_assess_dispatch_returns_value_free_lifecycle(monkeypatch, tmp_path, capsys):
    path = tmp_path / "synthetic.txt"
    path.write_text("ข้อมูลของฉันมีผลตรวจ DNA", encoding="utf-8")
    run_cli(monkeypatch, "assess", path)
    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == "aiguard.pdpa-assessment/1"
    assert result["lifecycle"]["execution"] == "none"
    assert path.read_text(encoding="utf-8") not in json.dumps(result, ensure_ascii=False)


def test_output_cannot_overwrite_input(monkeypatch, tmp_path, capsys):
    path = tmp_path / "original.txt"
    path.write_text("preserve", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        run_cli(monkeypatch, "assess", path, "--output", path)
    assert error.value.code == 1
    assert path.read_text() == "preserve"
    assert "Traceback" not in capsys.readouterr().err


def test_unknown_context_and_duplicate_keys_do_not_echo_values(monkeypatch, tmp_path, capsys):
    source = tmp_path / "source.txt"
    source.write_text("synthetic")
    context = tmp_path / "context.json"
    for data in ('{"private_name":"sensitive-marker"}', '{"basis":"consent","basis":"contract"}'):
        context.write_text(data)
        with pytest.raises(SystemExit):
            run_cli(monkeypatch, "assess", source, "--context", context)
        out = capsys.readouterr()
        assert "sensitive-marker" not in out.out + out.err
        assert "private_name" not in out.out + out.err


def test_raw_image_is_explicitly_not_assessed(monkeypatch, tmp_path, capsys):
    path = tmp_path / "image.png"
    path.write_bytes(b"synthetic-binary-not-an-image")
    run_cli(monkeypatch, "assess", path)
    result = json.loads(capsys.readouterr().out)
    assert result["engine"]["status"] == "not_assessed"
    assert "review_modality" in result["review_reasons"]


def test_coverage_and_lifecycle_commands_are_executable(monkeypatch, capsys):
    run_cli(monkeypatch, "coverage")
    assert len(json.loads(capsys.readouterr().out)["coverage"]) == 24
    run_cli(monkeypatch, "lifecycle")
    assert json.loads(capsys.readouterr().out)["execution"] == "none"


@pytest.mark.parametrize(
    "arguments", [("--threshold", "PRIVATE_SENTINEL"), ("--unknown-option", "PRIVATE_SENTINEL")]
)
def test_pdpa_argument_errors_never_echo_rejected_values(monkeypatch, capsys, arguments):
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "assess", "synthetic.txt", *arguments)
    assert "PRIVATE_SENTINEL" not in capsys.readouterr().err


def test_standalone_lifecycle_preserves_sensitive_consent_review(monkeypatch, tmp_path, capsys):
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "basis": "contract",
                "s26_condition": "explicit_consent",
                "s26_reviewed": True,
                "consent": "withdrawn",
            }
        )
    )
    run_cli(monkeypatch, "lifecycle", "--context", context)
    assert "stop_sensitive_consent_processing" in json.loads(capsys.readouterr().out)["actions"]

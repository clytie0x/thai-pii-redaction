"""Evidence integrity and diagnostics for the YRSS accuracy campaign."""

import json

import pytest

from benchmark.types import GoldSpan, Sample


def sample():
    return Sample("0123456789", [GoldSpan(2, 8, "PHONE")], "synthetic-1", "core")


def test_inventory_distinguishes_wrong_type_partial_and_uncovered():
    from benchmark.campaign import error_inventory

    s = sample()
    wrong = error_inventory([s], [[(2, 8, "ID_NUMBER")]])
    assert wrong["gold_errors"][0]["kind"] == "wrong_type_fully_covered"
    assert wrong["summary"]["uncovered_entities"] == 0
    partial = error_inventory([s], [[(2, 5, "PHONE")]])
    assert partial["gold_errors"][0]["kind"] == "partial_coverage"
    assert partial["gold_errors"][0]["uncovered_characters"] == 3
    missed = error_inventory([s], [[]])
    assert missed["summary"]["uncovered_entities"] == 1
    assert s.text not in json.dumps([wrong, partial, missed])


def test_inventory_unions_coverage_and_does_not_count_overlap_twice():
    from benchmark.campaign import error_inventory

    result = error_inventory([sample()], [[(2, 6, "PHONE"), (4, 8, "PHONE")]])
    assert result["gold_errors"][0]["kind"] == "boundary_fully_covered"
    assert result["summary"]["uncovered_characters"] == 0
    assert result["summary"]["overmasked_characters"] == 0


def test_inventory_reports_out_of_scheme_separately():
    from benchmark.campaign import error_inventory

    result = error_inventory([sample()], [[(0, 2, "DATE"), (2, 8, "PHONE")]])
    assert result["summary"]["out_of_scheme_predictions"] == 1
    assert result["summary"]["overmasked_characters"] == 2
    assert result["gold_errors"] == []


@pytest.mark.parametrize("predictions", [[], [[(-1, 3, "PHONE")]], [[(2, 20, "PHONE")]]])
def test_inventory_rejects_incomplete_or_invalid_predictions(predictions):
    from benchmark.campaign import error_inventory

    with pytest.raises(ValueError):
        error_inventory([sample()], predictions)


def test_prediction_digest_ignores_order_but_binds_corpus_and_offsets():
    from benchmark.campaign import prediction_digest

    s = sample()
    a = [(2, 8, "PHONE"), (0, 2, "DATE")]
    assert prediction_digest([s], [a]) == prediction_digest([s], [a[::-1]])
    assert prediction_digest([s], [a]) != prediction_digest([s], [[(2, 7, "PHONE")]])
    other = Sample("abcdefghij", s.spans, s.template_id, s.slice)
    assert prediction_digest([s], [a]) != prediction_digest([other], [a])


def test_ablation_restores_function_references_on_failure(monkeypatch):
    from benchmark import campaign, runner
    from pii_redactor.detectors import aggregate, name_context

    original_fn = aggregate.scan_fn
    original_name = name_context.detect_name_context

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(runner, "predict_samples", fail)
    for arm in ("without_fn", "without_name_context"):
        with pytest.raises(RuntimeError):
            campaign.predict_arm([sample()], arm)
        assert aggregate.scan_fn is original_fn
        assert name_context.detect_name_context is original_name


def test_ablation_rejects_skipped_ner(monkeypatch):
    from benchmark import campaign, runner
    from benchmark.runner import BenchmarkIntegrityError

    def skipped(samples, engine, *, diagnostics):
        diagnostics.attempted = 1
        diagnostics.skipped = 1
        return [[]]

    monkeypatch.setattr(runner, "predict_samples", skipped)
    with pytest.raises(BenchmarkIntegrityError):
        campaign.predict_arm([sample()], "full")


def test_canonical_digest_handles_line_endings(tmp_path):
    from benchmark.campaign import file_digest

    p = tmp_path / "source.py"
    p.write_bytes(b"a\r\nb\r\n")
    first = file_digest(p)
    p.write_bytes(b"a\nb\n")
    assert file_digest(p) == first


def test_output_directory_refuses_overwrite(tmp_path):
    from benchmark.campaign import create_output

    p = tmp_path / "run"
    create_output(p)
    (p / "original").write_text("preserve")
    with pytest.raises(FileExistsError):
        create_output(p)
    assert (p / "original").read_text() == "preserve"


@pytest.mark.parametrize(
    "field",
    [
        "model_sha256",
        "source_sha256",
        "scorer_sha256",
        "corpus_sha256",
        "requirements_sha256",
        "packages",
        "python",
        "pythainlp_assets_sha256",
        "evaluator_sha256",
    ],
)
def test_reproduction_refuses_identity_drift(field):
    from benchmark.campaign import verify_identity

    reference = dict.fromkeys(
        (
            "model_sha256",
            "source_sha256",
            "scorer_sha256",
            "corpus_sha256",
            "requirements_sha256",
            "packages",
            "python",
            "pythainlp_assets_sha256",
            "evaluator_sha256",
        ),
        "original",
    )
    current = {**reference, field: "changed"}
    with pytest.raises(ValueError, match="identity mismatch"):
        verify_identity(reference, current)


def test_paired_bootstrap_uses_same_resampled_document_indices():
    from benchmark.campaign import paired_f2_interval

    identical = [(1, 0, 0), (0, 2, 1), (2, 1, 0)]
    result = paired_f2_interval(identical, identical, iterations=100)
    assert result["delta"] == result["lower"] == result["upper"] == 0
    assert result == paired_f2_interval(identical, identical, iterations=100)


def test_paired_bootstrap_includes_negative_document_false_positives():
    from benchmark.campaign import document_counts, paired_f2_interval

    s = [sample(), Sample("fiction", [], "negative-1", "negative")]
    baseline = document_counts(s, [[(2, 8, "PHONE")], [(0, 3, "NAME")]])
    candidate = document_counts(s, [[(2, 8, "PHONE")], []])
    assert baseline == [(1, 0, 0), (0, 1, 0)]
    result = paired_f2_interval(baseline, candidate, iterations=100)
    assert result["delta"] == pytest.approx(1 - 5 / 6)
    assert result["unit"] == "document"


def test_paired_bootstrap_rejects_incomplete_pairs():
    from benchmark.campaign import paired_f2_interval

    with pytest.raises(ValueError):
        paired_f2_interval([(1, 0, 0)], [])


def test_blind_negative_validator_matches_maximal_digit_token_guideline():
    from benchmark.blind import validate_draft

    record = {
        "doc_id": "negative-code",
        "slice": "negative",
        "layer": "negative",
        "annotated": "เลขอ้างอิงสินค้า " + "7" * 20,
    }
    assert validate_draft([record], type_minimums={}) == []
    record["annotated"] = "เลขอ้างอิง " + "7" * 13
    assert ("negative-code", "negative-contains-13-digit-run") in validate_draft(
        [record], type_minimums={}
    )

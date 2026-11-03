"""Harness tests use fakes and one short detector call. They do not print values."""

from __future__ import annotations

import json
import random

from benchmark.blind_v2.__main__ import main, prepare_corpus
from benchmark.blind_v2.ablate import predict_ablated
from benchmark.blind_v2.baselines import align_ner_tags, regex_predict
from benchmark.blind_v2.corpus import _thai_id, generate_corpus
from benchmark.blind_v2.hard_set import public_lock
from benchmark.blind_v2.harness import build_systems, layer_delta, render_report, run_benchmark
from benchmark.blind_v2.llm import parse_redaction, probe_llm
from benchmark.blind_v2.present import contrast_lines, render_split_markdown
from benchmark.blind_v2.score import name_miss_census, percentile, prf, score_predictions
from benchmark.blind_v2.types import REDACTION_TYPES
from benchmark.blind_v2.utility import answer_correct, redact, score_utility
from benchmark.scorer import _prf, score
from benchmark.types import GoldSpan, Sample


class _Doc:
    def __init__(self, doc_id, text, spans, questions=(), section26=()):
        self.doc_id = doc_id
        self.text = text
        self.spans = spans
        self.questions = questions
        self.slice = "unit"
        self.style = "unit"
        self.section26 = section26


class _Span:
    def __init__(self, start, end, entity_type):
        self.start = start
        self.end = end
        self.entity_type = entity_type


class _Question:
    def __init__(self, question, answer, needs_pii):
        self.question_id = "q"
        self.question = question
        self.answer = answer
        self.needs_pii = needs_pii


class _Fake:
    name = "fake"
    cost_usd = 0.0

    def __init__(self, spans):
        self._spans = spans

    def prepare(self):
        return None

    def predict(self, text):
        return [span for span in self._spans if span[1] <= len(text)]


class _Skip:
    name = "skipped-system"
    cost_usd = None

    def prepare(self):
        return "not installed"

    def predict(self, text):
        raise AssertionError("predict should not run")


def test_percentile_uses_nearest_rank():
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([1, 2, 3, 4], 95) == 4
    assert percentile([], 50) is None


def test_prf_reports_f1_with_the_same_formula_as_the_product_scorer():
    # One hit, one extra span, no miss: precision 0.5, recall 1.
    row = prf(1, 1, 0)
    product = _prf(1, 1, 0)
    assert row["precision"] == product["precision"]
    assert row["recall"] == product["recall"]
    assert row["f1"] == product["f1"]
    assert row["f2"] == product["f2"]
    assert abs(row["f1"] - (2 / 3)) < 1e-12
    assert abs(row["f2"] - (5 / 6)) < 1e-12
    assert prf(0, 0, 0)["f1"] == 0.0


def test_layer_delta_is_the_removed_score_minus_the_full_score():
    documents = [_Doc("d", "abcd", [_Span(0, 2, "NAME"), _Span(2, 4, "PHONE")])]
    full = score_predictions(documents, [[(0, 2, "NAME"), (2, 4, "PHONE")]])
    removed = score_predictions(documents, [[(2, 4, "PHONE")]])
    row = layer_delta(full, removed, "tb")
    assert row["disabled"] == "tb"
    assert row["delta_by_type_recall"]["NAME"] == -1.0
    assert row["delta_by_type_recall"]["PHONE"] == 0.0
    assert row["delta_micro_recall"] == removed["micro"]["recall"] - full["micro"]["recall"]
    assert "abcd" not in json.dumps(row)


def test_macro_averages_f1_over_types_that_have_gold():
    documents = [_Doc("d", "abcd", [_Span(0, 2, "NAME"), _Span(2, 4, "PHONE")])]
    scored = score_predictions(documents, [[(0, 2, "NAME")]])
    assert scored["by_type"]["NAME"]["f1"] == 1.0
    assert scored["by_type"]["PHONE"]["f1"] == 0.0
    assert scored["micro"]["f1"] == _prf(1, 0, 1)["f1"]
    assert scored["macro"]["types"] == 2
    assert scored["macro"]["f1"] == 0.5


def test_name_miss_census_counts_prefix_cues_and_stores_no_text():
    documents = [
        _Doc("a", "นายสมชาย ใจดี", [_Span(3, 13, "NAME")]),
        _Doc("b", "ไปเจอสมหญิงที่ตลาด", [_Span(5, 11, "NAME")]),
        _Doc("c", "นายกสมศักดิ์พูด", [_Span(4, 12, "NAME")]),
    ]
    predictions = [[], [], []]
    census = name_miss_census(documents, predictions)
    assert census["gold"] == 3
    assert census["false_negatives_with_prefix_cue"] == 1
    assert census["false_negatives_without_prefix_cue"] == 2
    blob = json.dumps(census, ensure_ascii=False)
    assert "สมชาย" not in blob
    assert "สมหญิง" not in blob
    caught = name_miss_census(documents, [[(3, 13, "NAME")], [], []])
    assert caught["false_negatives_with_prefix_cue"] == 0
    assert caught["false_negatives_without_prefix_cue"] == 2


def test_render_report_includes_f1_and_name_miss_counts():
    by_type = {
        entity_type: {
            "n": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "f2": 0.0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
        }
        for entity_type in REDACTION_TYPES
    }
    by_type["NAME"] = {
        "n": 1,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
        "f2": 1.0,
        "tp": 1,
        "fp": 0,
        "fn": 0,
    }
    report = {
        "ablations": {"status": "skipped", "reason": "disabled"},
        "dataset": {
            "documents": 1,
            "official": True,
            "plaintext_sha256": "abc",
            "seed": 1,
            "version": "unit",
        },
        "section26": {"status": "skipped"},
        "systems": [
            {
                "by_type": by_type,
                "cost_usd": 0.0,
                "latency_ms": {"p50": 1.0, "p95": 2.0},
                "macro": {"f1": 1.0, "f2": 1.0, "precision": 1.0, "recall": 1.0},
                "micro": {"f1": 1.0, "f2": 1.0, "precision": 1.0, "recall": 1.0},
                "name": "fake",
                "name_misses": {
                    "false_negatives_with_prefix_cue": 0,
                    "false_negatives_without_prefix_cue": 2,
                    "gold": 2,
                },
                "negative": {"clean_docs": 1, "documents": 1, "false_positives": 0},
                "other_false_positives": 0,
                "peak_memory_bytes": {"p50": 1024, "p95": 2048},
                "reason": "",
                "status": "ok",
            }
        ],
        "utility": {"status": "skipped", "reason": "disabled"},
    }
    rendered = render_report(report)
    header = rendered.splitlines()[1]
    assert "F1" in header
    assert "macroF1" in header
    assert "name_fn cued=0 uncued=2" in rendered


def test_prepare_hard_splits_match_their_locks():
    expected = {
        "hard-dev": (20261102, "b169fcb72add15dc46cdd62fcb3dac179a4d0b9aa467ad0fb29a40514c76273b"),
        "hard-test": (20261103, "90749a8891d42b924bbfbbb690f9637ab599867013f27c4a3ed459e8f3aaca11"),
    }
    for split, (seed, digest) in expected.items():
        corpus, error = prepare_corpus(split)
        assert error is None
        assert corpus.seed == seed
        assert public_lock(corpus)["plaintext_sha256"] == digest
        report = run_benchmark(
            corpus,
            systems=[_Fake([(0, 1, "NAME")])],
            ablate=False,
            utility=False,
            section26=False,
            limit=1,
        )
        assert report["dataset"]["plaintext_sha256"] == digest
        assert report["dataset"]["seed"] == seed
        assert report["dataset"]["limited"] is True
        blob = json.dumps(report, ensure_ascii=False)
        assert corpus.documents[0].text[:12] not in blob


def test_self_check_hard_test_stays_quiet(capsys):
    assert main(["--self-check", "--split", "hard-test"]) == 0
    captured = capsys.readouterr()
    assert "seed=20261103" in captured.out
    assert "90749a8891d42b924bbfbbb690f9637ab599867013f27c4a3ed459e8f3aaca11" in captured.out
    assert "@" not in captured.out
    try:
        main(["--self-check", "--split", "nope"])
    except SystemExit as exc:
        assert exc.code == 2
        return
    raise AssertionError("unknown-split")


def test_overlap_score_matches_the_product_scorer_on_shared_types():
    text = "xxxx"
    sample = Sample(text, [GoldSpan(0, 2, "NAME"), GoldSpan(2, 4, "PHONE")], "t", "unit")
    documents = [_Doc("d", text, [_Span(0, 2, "NAME"), _Span(2, 4, "PHONE")])]
    predictions = [[(0, 2, "NAME"), (2, 3, "EMAIL")]]
    ours = score_predictions(documents, predictions)
    product = score([sample], predictions, bootstrap_iters=0)
    assert ours["by_type"]["NAME"]["tp"] == product["by_type"]["NAME"]["tp"]
    assert ours["by_type"]["PHONE"]["fn"] == product["by_type"]["PHONE"]["fn"]
    assert ours["by_type"]["EMAIL"]["fp"] == product["by_type"]["EMAIL"]["fp"]


def test_regex_baseline_accepts_checksum_ids_and_rejects_non_ascii_digits():
    digits = _thai_id(random.Random(2))
    assert any(entity_type == "THAI_ID" for _, _, entity_type in regex_predict("เลข " + digits))
    corrupted = digits[:4] + "O" + digits[5:]
    assert not any(
        entity_type == "THAI_ID" for _, _, entity_type in regex_predict("เลข " + corrupted)
    )
    assert any(entity_type == "PHONE" for _, _, entity_type in regex_predict("โทร 081-234-5678"))
    assert not any(
        entity_type == "PHONE" for _, _, entity_type in regex_predict("โทร ๐๘๑-๒๓๔-๕๖๗๘")
    )


def test_presidio_dedupe_keeps_a_redaction_type_over_a_generic_label():
    from benchmark.blind_v2.baselines import _dedupe_prefer_scheme

    assert _dedupe_prefer_scheme([(0, 13, "OTHER"), (0, 13, "THAI_ID")]) == [(0, 13, "THAI_ID")]


def test_ner_alignment_merges_bio_without_leaving_the_text():
    text = "aa bb cc"
    spans = align_ner_tags(text, [("aa", "B-PERSON"), ("bb", "I-PERSON"), ("cc", "O")])
    assert spans == [(0, 5, "NAME")]
    assert text[spans[0][0] : spans[0][1]] == "aa bb"


def test_redaction_removes_a_covered_answer_only():
    text = "ชื่อ สมชาย ใจดี เรื่องประชุม"
    masked = redact(text, [(3, 14, "NAME")])
    assert "สมชาย" not in masked
    assert "ประชุม" in masked
    assert answer_correct("ประชุม", "คำตอบคือ ประชุม")
    assert not answer_correct("สมชาย ใจดี", masked)


def test_utility_fake_answerer_drops_pii_questions_after_redaction():
    document = _Doc(
        "d",
        "ชื่อ สมชาย ใจดี เรื่องประชุม",
        [_Span(3, 14, "NAME")],
        (
            _Question("ชื่ออะไร", "สมชาย ใจดี", True),
            _Question("เรื่องอะไร", "ประชุม", False),
        ),
    )

    def complete_fn(prompt: str) -> str:
        if "สมชาย ใจดี" in prompt and "Question: ชื่ออะไร" in prompt:
            return "สมชาย ใจดี"
        if "ประชุม" in prompt and "Question: เรื่องอะไร" in prompt:
            return "ประชุม"
        return "ไม่ทราบ"

    report = score_utility([document], {"fake": [[(3, 14, "NAME")]]}, complete_fn)
    row = report["systems"]["fake"]
    assert row["pii_raw_accuracy"] == 1
    assert row["pii_redacted_accuracy"] == 0
    assert row["safe_raw_accuracy"] == 1
    assert row["safe_redacted_accuracy"] == 1


def test_llm_parser_and_platform_refusal(monkeypatch):
    spans = parse_redaction("mail a@example.com", '[{"type":"EMAIL","text":"a@example.com"}]')
    assert spans == [(5, 18, "EMAIL")]
    monkeypatch.setenv("AIGUARD_BLIND_LLM", "tokenmind")
    monkeypatch.setenv("TOKENMIND_API_KEY", "super-secret-value")
    probe = probe_llm()
    assert probe.available is False
    assert "super-secret-value" not in probe.reason
    assert "platform" in probe.reason


def test_harness_report_omits_document_text(tmp_path):
    corpus = generate_corpus()
    report = run_benchmark(
        corpus,
        systems=[_Fake([(0, 1, "NAME")]), _Skip()],
        ablate=False,
        utility=False,
        section26=True,
        limit=2,
    )
    rendered = render_report(report)
    blob = json.dumps(report, ensure_ascii=False)
    assert corpus.documents[0].text[:12] not in blob
    assert corpus.documents[0].text[:12] not in rendered
    assert "@" not in blob
    assert report["dataset"]["official"] is False
    assert report["systems"][1]["status"] == "skipped"
    assert report["section26"]["status"] == "ok"
    destination = tmp_path / "report.json"
    destination.write_text(blob, encoding="utf-8")
    assert "plaintext_sha256" in destination.read_text(encoding="utf-8")


def test_full_ablation_matches_detect_all():
    from pii_redactor.detectors.aggregate import detect_all

    samples = ["นายสมชาย ใจดี", generate_corpus().documents[0].text]
    for text in samples:
        expected = [
            (entity.span[0], entity.span[1], entity.data_type) for entity in detect_all(text)
        ]
        assert predict_ablated(text, None) == expected


def _unit_report(scored, misses):
    def system(name):
        return {
            "by_type": scored["by_type"],
            "cost_usd": 0.0,
            "latency_ms": {"p50": 1.25, "p95": 2.0},
            "macro": scored["macro"],
            "micro": scored["micro"],
            "name": name,
            "name_misses": misses,
            "negative": scored["negative"],
            "other_false_positives": scored["other_false_positives"],
            "status": "ok",
        }

    layers = [
        layer_delta(scored, scored, name)
        for name in (
            "fp",
            "tb",
            "fn",
            "record_names",
            "address_merge",
            "facility_filter",
            "student_relabel",
        )
    ]
    return {
        "ablations": {
            "full_by_type": scored["by_type"],
            "full_macro": scored["macro"],
            "full_micro": scored["micro"],
            "full_micro_f2": scored["micro"]["f2"],
            "layers": layers,
            "status": "ok",
        },
        "dataset": {
            "documents": 1,
            "official": True,
            "plaintext_sha256": "abc",
            "seed": 1,
            "version": "unit",
        },
        "section26": {"micro_recall": 0.0, "n": 0, "status": "ok"},
        "systems": [
            system(name)
            for name in ("aiguard", "regex", "presidio", "pythainlp-ner", "wangchanberta-ner")
        ],
        "utility": {"reason": "disabled", "status": "skipped"},
    }


def test_split_markdown_formats_f1_and_omits_text():
    documents = [_Doc("d", "abcd", [_Span(0, 2, "NAME"), _Span(2, 4, "PHONE")])]
    scored = score_predictions(documents, [[(0, 2, "NAME"), (2, 4, "PHONE")]])
    misses = name_miss_census(documents, [[(0, 2, "NAME"), (2, 4, "PHONE")]])
    report = _unit_report(scored, misses)
    rendered = render_split_markdown(report)
    assert "abcd" not in rendered
    assert "| F1 |" in rendered.splitlines()[2]
    contrasts = contrast_lines({"hard-test": report, "hard-dev": report, "freeze": report})
    assert contrasts
    assert all("abcd" not in line for line in contrasts)


def test_committed_run_markdown_matches_the_json_files():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    runs = root / "docs" / "benchmark" / "runs"
    reports = {
        split: json.loads((runs / f"{split}.json").read_text(encoding="utf-8"))
        for split in ("hard-test", "hard-dev", "freeze")
    }
    labels = json.loads((runs / "negative-labels.json").read_text(encoding="utf-8"))
    document = (root / "docs" / "benchmark" / "per-entity-results.md").read_text(encoding="utf-8")
    for split, report in reports.items():
        assert render_split_markdown(report) in document
        guard = next(system for system in report["systems"] if system["name"] == "aiguard")
        assert sum(labels[split]["other"].values()) == guard["other_false_positives"]
        assert sum(labels[split]["negative"].values()) == guard["negative"]["false_positives"]
    for line in contrast_lines(reports, labels):
        assert line in document
    env = json.loads((runs / "environment.json").read_text(encoding="utf-8"))
    assert env["python"] in document
    assert env["llm_probe"] in document
    assert env["lock_file_sha256"]["hard-test"] in document
    assert "@" not in document


def test_unknown_system_is_rejected():
    try:
        build_systems(["missing"])
    except ValueError:
        return
    raise AssertionError("unknown-system")

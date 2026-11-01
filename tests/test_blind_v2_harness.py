"""Harness tests use fakes and one short detector call. They do not print values."""

from __future__ import annotations

import json
import random

from benchmark.blind_v2.ablate import predict_ablated
from benchmark.blind_v2.baselines import align_ner_tags, regex_predict
from benchmark.blind_v2.corpus import _thai_id, generate_corpus
from benchmark.blind_v2.harness import build_systems, render_report, run_benchmark
from benchmark.blind_v2.llm import parse_redaction, probe_llm
from benchmark.blind_v2.score import percentile, score_predictions
from benchmark.blind_v2.utility import answer_correct, redact, score_utility
from benchmark.scorer import score
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


def test_unknown_system_is_rejected():
    try:
        build_systems(["missing"])
    except ValueError:
        return
    raise AssertionError("unknown-system")

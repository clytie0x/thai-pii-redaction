"""Harness checks for the YRSS evaluation v2. Fixtures are tiny and synthetic."""

from __future__ import annotations

import json

import pytest

from benchmark.blind_v2.score import score_predictions
from benchmark.blind_v2.types import REDACTION_TYPES
from benchmark.yrss_v2 import harness, stats, systems
from benchmark.yrss_v2.__main__ import main
from benchmark.yrss_v2.corpus import Corpus, Document, Span, Template, render
from benchmark.yrss_v2.types import CONTEXTUAL_TYPES, SCHEME_TYPES, STRUCTURED_TYPES

_TEMPLATES = (
    Template("fam-a", "unit", False, "ผู้ติดต่อ คุณ{{name}} โทร {{phone}} อีเมล {{email}}"),
    Template("fam-b", "unit", False, "ชื่อ {{name}} เกิดวันที่ {{dob}} เลขบัตร {{thai_id}}"),
    Template("fam-c", "unit", False, "ใบขับขี่เลขที่ {{licence}} ของ {{name}}"),
    Template("fam-n", "unit", True, "คำสั่งซื้อ {{order_code}} ยอด {{amount}}"),
)


def _corpus(variants: int = 2, split: str = "unit") -> Corpus:
    documents = tuple(
        render(template, variant, seed=11) for template in _TEMPLATES for variant in range(variants)
    )
    return Corpus("yrss-eval-v2", split, 11, "0" * 64, documents)


def _gold(document: Document) -> list[tuple[int, int, str]]:
    return [(span.start, span.end, span.entity_type) for span in document.spans]


def _oracle(corpus: Corpus, keep=lambda document, span: True):
    """A fake predictor that returns chosen gold spans, looked up by text."""
    table = {
        document.text: [item for item in _gold(document) if keep(document, item)]
        for document in corpus.documents
    }
    return lambda text: list(table.get(text, []))


def _doc(family: str, index: int, spans: list[tuple[int, int, str]]) -> Document:
    return Document(f"{family}-v{index}", family, "unit", "x" * 40, tuple(Span(*s) for s in spans))


# --- scorer parameter -------------------------------------------------------


def test_score_predictions_default_scheme_is_unchanged():
    corpus = _corpus()
    predictions = [_gold(document) for document in corpus.documents]
    default = score_predictions(corpus.documents, predictions)
    assert default == score_predictions(corpus.documents, predictions, types=None)
    assert default == score_predictions(corpus.documents, predictions, types=REDACTION_TYPES)
    assert tuple(default["by_type"]) == REDACTION_TYPES
    # DRIVER_LICENSE is outside the older scheme, so it is an "other" false positive there.
    assert default["other_false_positives"] == 2


def test_score_predictions_accepts_the_v2_scheme():
    corpus = _corpus()
    predictions = [_gold(document) for document in corpus.documents]
    scored = score_predictions(corpus.documents, predictions, types=SCHEME_TYPES)
    assert tuple(scored["by_type"]) == SCHEME_TYPES
    assert scored["other_false_positives"] == 0
    assert scored["by_type"]["DRIVER_LICENSE"]["tp"] == 2
    assert scored["micro"]["f2"] == 1.0


# --- views ------------------------------------------------------------------


def test_view_types():
    assert stats.view_types("all") == SCHEME_TYPES
    assert stats.view_types("structured") == STRUCTURED_TYPES
    assert stats.view_types("contextual") == CONTEXTUAL_TYPES
    with pytest.raises(ValueError):
        stats.view_types("shared")


def test_all_view_counts_out_of_scheme_prediction_as_false_positive():
    document = _doc("f", 0, [(0, 5, "NAME"), (10, 18, "PHONE")])
    predicted = [(0, 5, "NAME"), (10, 18, "PHONE"), (20, 28, "STUDENT_ID"), (30, 34, "LOCATION")]
    assert stats.view_counts([document], [predicted], "all") == [(2, 2, 0)]


def test_group_view_ignores_other_types_instead_of_counting_them():
    document = _doc("f", 0, [(0, 5, "NAME"), (10, 18, "PHONE")])
    predicted = [(0, 5, "NAME"), (20, 28, "STUDENT_ID"), (30, 34, "EMAIL"), (35, 38, "ADDRESS")]
    # Contextual: NAME hit, ADDRESS is a false positive, PHONE gold is not in view.
    assert stats.view_counts([document], [predicted], "contextual") == [(1, 1, 0)]
    # Structured: PHONE missed, EMAIL false positive, STUDENT_ID and NAME ignored.
    assert stats.view_counts([document], [predicted], "structured") == [(0, 1, 1)]


def test_wrong_type_on_the_right_span_is_a_miss_and_a_false_positive():
    document = _doc("f", 0, [(0, 5, "NAME")])
    assert stats.view_counts([document], [[(0, 5, "ADDRESS")]], "all") == [(0, 1, 1)]


def test_f2_formula_and_zero_denominator():
    assert stats.f2(0, 0, 0) == 0.0
    assert stats.f2(0, 3, 0) == 0.0
    # P = 0.5, R = 1.0 -> 5 * 0.5 / (2 + 1)
    assert stats.f2(2, 2, 0) == pytest.approx(2.5 / 3)


# --- cluster bootstrap ------------------------------------------------------


def test_resamples_are_deterministic_and_draw_whole_families():
    families = ["a", "a", "a", "b", "b", "b", "c", "c", "c"]
    first = stats.family_resamples(families)
    assert first == stats.family_resamples(families)
    assert first != stats.family_resamples(families, seed=1)
    assert len(first.draws) == 1000
    assert first.members == ((0, 1, 2), (3, 4, 5), (6, 7, 8))
    assert all(len(draw) == 3 and set(draw) <= {0, 1, 2} for draw in first.draws)
    assert len(stats.family_resamples(families, n_resamples=50).draws) == 50


def test_one_all_wrong_family_gives_a_wide_interval():
    families = [f"f{index // 3}" for index in range(30)]
    # Family f0 misses everything. The other nine are perfect.
    clustered = [(0, 0, 4) if index < 3 else (4, 0, 0) for index in range(30)]
    # Same number of bad documents, but each family is all-good or all-bad already;
    # the document-level view would spread them. Here we compare with no errors.
    perfect = [(4, 0, 0)] * 30
    resamples = stats.family_resamples(families)
    low, high = stats.f2_interval(clustered, resamples)
    assert high == 1.0
    assert low < 0.80
    assert stats.f2_interval(perfect, resamples) == (1.0, 1.0)
    # Whole families move together: every resampled recall is a multiple of 1/10.
    for value in stats.bootstrap_metric(clustered, resamples, stats.recall):
        assert round(value * 10, 9) == round(value * 10)


def test_counts_must_cover_the_resampled_documents():
    resamples = stats.family_resamples(["a", "b"])
    with pytest.raises(ValueError):
        stats.f2_interval([(1, 0, 0)], resamples)


# --- paired difference ------------------------------------------------------


def test_paired_difference_sign_interval_and_p_value():
    families = [f"f{index // 2}" for index in range(20)]
    resamples = stats.family_resamples(families)
    strong = [(4, 0, 0)] * 20
    weak = [(2, 0, 2)] * 20
    better = stats.paired_difference(strong, weak, resamples)
    # F2 of the weak system: P = 1, R = 0.5 -> 2.5 / 4.5
    assert better["difference"] == pytest.approx(1 - 2.5 / 4.5)
    assert better["ci_low"] > 0
    assert better["ci_low"] <= better["difference"] <= better["ci_high"]
    assert better["p_value"] == pytest.approx(1 / 1001)
    worse = stats.paired_difference(weak, strong, resamples)
    assert worse["difference"] == pytest.approx(-better["difference"])
    assert worse["ci_high"] < 0
    same = stats.paired_difference(strong, strong, resamples)
    assert same["difference"] == 0.0
    assert (same["ci_low"], same["ci_high"]) == (0.0, 0.0)
    assert same["p_value"] == 1.0


def test_paired_difference_that_flips_by_family_is_not_significant():
    families = [f"f{index}" for index in range(10)]
    resamples = stats.family_resamples(families)
    left = [(4, 0, 0) if index % 2 else (2, 0, 2) for index in range(10)]
    right = [(2, 0, 2) if index % 2 else (4, 0, 0) for index in range(10)]
    result = stats.paired_difference(left, right, resamples)
    assert result["difference"] == pytest.approx(0.0)
    assert result["ci_low"] < 0 < result["ci_high"]
    assert result["p_value"] > 0.5


def test_paired_difference_can_use_recall():
    resamples = stats.family_resamples(["a", "b", "c"])
    result = stats.paired_difference(
        [(4, 4, 0)] * 3, [(2, 0, 2)] * 3, resamples, metric=stats.recall
    )
    assert result["difference"] == pytest.approx(0.5)


# --- Holm -------------------------------------------------------------------


def test_holm_known_example_keeps_input_order():
    adjusted = stats.holm([0.01, 0.04, 0.03, 0.005])
    assert adjusted == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_holm_caps_at_one_and_handles_empty():
    assert stats.holm([]) == []
    assert stats.holm([0.6, 0.7]) == pytest.approx([1.0, 1.0])
    assert stats.holm([0.2]) == pytest.approx([0.2])


# --- regex licence pattern --------------------------------------------------


@pytest.mark.parametrize(
    "prefix",
    [
        "ใบขับขี่เลขที่ ",
        "ใบอนุญาตขับขี่ เลขที่ ",
        "เลขที่ใบอนุญาตขับรถ: ",
        "Driving licence no. ",
        "driver's license number ",
    ],
)
def test_regex_licence_pattern_hits_a_cued_eight_digit_number(prefix):
    text = f"{prefix}51234567 ออกให้ที่กรุงเทพ"
    start = text.index("51234567")
    assert (start, start + 8, "DRIVER_LICENSE") in systems.build("regex")(text)


def test_regex_licence_pattern_ignores_uncued_and_wrong_length_numbers():
    predict = systems.build("regex")
    for text in (
        "หมายเลขคำสั่งซื้อ 51234567 จัดส่งแล้ว",
        "ใบขับขี่เลขที่ 512345678",
        "ใบขับขี่เลขที่ 5123456",
        "ใบขับขี่ของผู้สมัครหมดอายุแล้ว กรุณาติดต่อเจ้าหน้าที่ที่เคาน์เตอร์ รหัสคิว 51234567",
    ):
        assert not [item for item in predict(text) if item[2] == "DRIVER_LICENSE"]


def test_regex_system_still_runs_the_older_baseline_and_dedupes():
    text = "ติดต่อ somchai@example.com ใบขับขี่เลขที่ 51234567"
    found = systems.build("regex")(text)
    assert [item[2] for item in found] == ["EMAIL", "DRIVER_LICENSE"]
    assert found == sorted(found)


# --- system registry --------------------------------------------------------


def test_registry_names_and_unknown_system():
    assert set(systems.COMPARATORS) == {"regex", "crf-ner", "wangchanberta-ner", "presidio", "llm"}
    assert set(systems.ABLATIONS) == {
        "aiguard-no-fp",
        "aiguard-no-tb",
        "aiguard-no-address_merge",
    }
    assert set(systems.system_names()) == {"aiguard", *systems.COMPARATORS, *systems.ABLATIONS}
    with pytest.raises(ValueError):
        systems.build("gpt")


def test_missing_optional_package_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(systems, "_importable", lambda module: False)
    with pytest.raises(systems.SystemUnavailable, match="presidio-analyzer"):
        systems.build("presidio")
    with pytest.raises(systems.SystemUnavailable, match="transformers"):
        systems.build("wangchanberta-ner")
    with pytest.raises(systems.SystemUnavailable, match="pythainlp"):
        systems.build("crf-ner")
    with pytest.raises(systems.SystemUnavailable, match="pythainlp"):
        systems.build("aiguard")


def test_llm_needs_explicit_options():
    with pytest.raises(ValueError):
        systems.build("llm")
    with pytest.raises(ValueError):
        systems.build("llm", llm_options={"model": "m"})


def test_llm_predictor_is_imported_lazily_and_deduped(monkeypatch):
    import sys
    import types

    calls = {}

    def make_predictor(*, base_url, model, api_key_env, seed, timeout=120.0):
        calls.update(base_url=base_url, model=model, api_key_env=api_key_env, seed=seed)
        return lambda text: [(0, 4, "NAME"), (2, 6, "PHONE"), (8, 8, "EMAIL")]

    fake = types.ModuleType("benchmark.yrss_v2.llm_openai")
    fake.make_predictor = make_predictor
    monkeypatch.setitem(sys.modules, "benchmark.yrss_v2.llm_openai", fake)
    predict = systems.build(
        "llm", llm_options={"base_url": "http://localhost:1/v1", "model": "m", "seed": 3}
    )
    assert calls == {
        "base_url": "http://localhost:1/v1",
        "model": "m",
        "api_key_env": None,
        "seed": 3,
    }
    assert predict("abcdefghij") == [(0, 4, "NAME")]


# --- report -----------------------------------------------------------------


def _report(corpus: Corpus | None = None, extra: dict | None = None) -> dict:
    corpus = corpus or _corpus()
    predictors = {
        "aiguard": _oracle(corpus),
        "regex": _oracle(corpus, lambda document, span: span[2] in STRUCTURED_TYPES),
        "crf-ner": _oracle(corpus, lambda document, span: span[2] == "NAME"),
        "aiguard-no-tb": _oracle(corpus, lambda document, span: span[2] != "NAME"),
    }
    predictors.update(extra or {})
    return harness.evaluate(corpus, predictors)


def test_report_scores_each_system_in_each_view():
    report = _report()
    assert report["protocol"] == "docs/decisions/2026-11-13-yrss-eval-v2.md"
    assert report["split"] == "unit"
    assert len(report["corpus"]["plaintext_sha256"]) == 64
    assert report["corpus"]["documents"] == 8
    assert report["corpus"]["families"] == 4
    full = report["systems"]["aiguard"]
    assert set(full["views"]) == set(stats.VIEWS)
    for view in full["views"].values():
        assert view["f2"] == 1.0 and view["fp"] == 0 and view["fn"] == 0
        assert view["f2_ci"] == [1.0, 1.0]
    regex = report["systems"]["regex"]["views"]
    assert regex["structured"]["f2"] == 1.0
    assert regex["contextual"]["recall"] == 0.0
    assert 0 < regex["all"]["f2"] < 1
    assert regex["all"]["f2_ci"][0] <= regex["all"]["f2"] <= regex["all"]["f2_ci"][1]
    assert tuple(full["by_type"]) == SCHEME_TYPES
    assert set(full["by_type"]["NAME"]) == {
        "n",
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
        "f2",
    }
    assert full["by_type"]["NAME"]["n"] == 6
    assert full["negative"] == {"documents": 2, "clean_docs": 2, "false_positives": 0}
    assert full["out_of_scheme_false_positives"] == 0
    assert full["latency_ms"]["p50"] >= 0
    assert full["latency_ms"]["p95"] >= full["latency_ms"]["p50"]


def test_report_counts_negative_and_out_of_scheme_false_positives():
    corpus = _corpus()
    gold = _oracle(corpus)

    def noisy(text):
        return [*gold(text), (0, 2, "STUDENT_ID")] if not gold(text) else gold(text)

    row = _report(corpus, {"presidio": noisy})["systems"]["presidio"]
    assert row["negative"] == {"documents": 2, "clean_docs": 0, "false_positives": 2}
    assert row["out_of_scheme_false_positives"] == 2
    assert row["views"]["all"]["fp"] == 2
    assert row["views"]["structured"]["fp"] == 0


def test_report_pairs_every_other_system_against_aiguard():
    report = _report()
    paired = report["paired"]
    assert paired["reference"] == "aiguard"
    assert paired["direction"] == "aiguard minus system"
    assert paired["holm_family"] == ["regex", "crf-ner"]
    assert paired["holm_view"] == "all"
    assert set(paired["comparisons"]) == {"regex", "crf-ner", "aiguard-no-tb"}
    regex = paired["comparisons"]["regex"]
    assert set(regex) == set(stats.VIEWS)
    assert regex["all"]["f2_difference"] > 0
    assert regex["all"]["f2_ci"][0] <= regex["all"]["f2_difference"] <= regex["all"]["f2_ci"][1]
    assert regex["structured"]["f2_difference"] == 0.0
    assert regex["structured"]["p_value"] == 1.0
    raw = [paired["comparisons"][name]["all"]["p_value"] for name in paired["holm_family"]]
    adjusted = [paired["comparisons"][name]["all"]["p_holm"] for name in paired["holm_family"]]
    assert adjusted == pytest.approx(stats.holm(raw))
    # Holm covers the comparators in the all view only.
    assert regex["structured"]["p_holm"] is None
    ablation = paired["comparisons"]["aiguard-no-tb"]
    assert ablation["all"]["p_holm"] is None
    assert ablation["all"]["recall_difference"] > 0


def test_report_without_aiguard_has_no_paired_rows():
    corpus = _corpus()
    report = harness.evaluate(corpus, {"regex": _oracle(corpus)})
    assert report["paired"]["comparisons"] == {}
    assert report["paired"]["holm_family"] == []


def test_report_is_json_and_carries_no_text_or_surfaces():
    corpus = _corpus()
    report = _report(corpus)
    dumped = json.dumps(report, ensure_ascii=False)
    assert json.loads(dumped) == report
    for document in corpus.documents:
        assert document.text not in dumped
        assert document.doc_id not in dumped
        for span in document.spans:
            assert document.text[span.start : span.end] not in dumped


def test_report_records_the_run_environment():
    environment = _report()["environment"]
    assert environment["git_commit"]
    assert environment["python"]
    assert environment["platform"]
    assert isinstance(environment["packages"], dict)
    assert len(environment["file_sha256"]["benchmark/blind_v2/score.py"]) == 64
    bootstrap = _report()["bootstrap"]
    assert bootstrap == {
        "interval": "95% percentile",
        "resamples": 1000,
        "seed": 0,
        "unit": "family",
    }


def test_git_commit_is_unknown_when_git_fails(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no git")

    monkeypatch.setattr(harness.subprocess, "run", broken)
    assert harness.git_commit() == "unknown"


# --- guards -----------------------------------------------------------------


def test_test_split_is_refused_without_the_explicit_argument(monkeypatch):
    def forbidden(split):
        raise AssertionError("the corpus must not be built")

    monkeypatch.setattr(harness, "build_corpus", forbidden)
    with pytest.raises(harness.TestSplitRefused):
        harness.run("test", ["regex"])
    with pytest.raises(harness.TestSplitRefused):
        harness.run("test", ["regex"], llm_options=None, allow_test=False)


def test_unknown_split_and_unknown_system_are_rejected_before_any_work(monkeypatch):
    monkeypatch.setattr(harness, "build_corpus", lambda split: pytest.fail("built"))
    with pytest.raises(ValueError):
        harness.run("holdout", ["regex"])
    with pytest.raises(ValueError):
        harness.run("dev", ["nope"])
    with pytest.raises(ValueError):
        harness.run("dev", [])


def test_run_refuses_a_corpus_that_does_not_match_its_lock(monkeypatch):
    corpus = _corpus(split="dev")
    monkeypatch.setattr(harness, "build_corpus", lambda split: corpus)
    monkeypatch.setattr(harness, "load_templates", lambda split: list(_TEMPLATES))
    monkeypatch.setattr(harness, "_read_lock", lambda split: {"plaintext_sha256": "f" * 64})
    with pytest.raises(harness.CorpusLockError):
        harness.run("dev", ["regex"])


def test_run_scores_a_locked_corpus_with_real_regex(monkeypatch):
    corpus = _corpus(split="dev")
    monkeypatch.setattr(harness, "build_corpus", lambda split: corpus)
    monkeypatch.setattr(harness, "load_templates", lambda split: list(_TEMPLATES))
    monkeypatch.setattr(harness, "_read_lock", lambda split: harness.public_lock(corpus))
    report = harness.run("dev", ["regex"])
    assert list(report["systems"]) == ["regex"]
    assert report["corpus"]["plaintext_sha256"] == harness.public_lock(corpus)["plaintext_sha256"]
    assert report["systems"]["regex"]["by_type"]["DRIVER_LICENSE"]["tp"] == 2


def test_cli_refuses_the_test_split_without_the_long_flag(monkeypatch, capsys):
    monkeypatch.setattr(harness, "build_corpus", lambda split: pytest.fail("built"))
    assert main(["--split", "test", "--systems", "regex"]) == 2
    assert "--i-understand-this-spends-the-test-split" in capsys.readouterr().err


def test_cli_writes_the_report(monkeypatch, tmp_path, capsys):
    seen = {}

    def fake_run(split, names, *, llm_options=None, allow_test=False):
        seen.update(split=split, names=names, llm_options=llm_options, allow_test=allow_test)
        return _report()

    monkeypatch.setattr(harness, "run", fake_run)
    out = tmp_path / "nested" / "out.json"
    code = main(
        [
            "--split",
            "dev",
            "--systems",
            "aiguard, regex",
            "--json",
            str(out),
            "--llm-base-url",
            "http://localhost:1/v1",
            "--llm-model",
            "m",
            "--llm-key-env",
            "LOCAL_KEY",
            "--llm-seed",
            "4",
        ]
    )
    assert code == 0
    assert seen["names"] == ["aiguard", "regex"]
    assert seen["allow_test"] is False
    assert seen["llm_options"] == {
        "base_url": "http://localhost:1/v1",
        "model": "m",
        "api_key_env": "LOCAL_KEY",
        "seed": 4,
    }
    assert json.loads(out.read_text(encoding="utf-8"))["split"] == "unit"
    assert "aiguard" in capsys.readouterr().out


def test_shared11_view_ignores_out_of_scheme_predictions():
    doc = render(Template("t-p-900", "test", False, "ติดต่อ {{name}} โทร {{phone}}"), 0, seed=2)
    name, phone = doc.spans
    predictions = [[(name.start, name.end, "NAME"), (phone.start, phone.end, "ORGANIZATION")]]
    assert stats.total(stats.view_counts([doc], predictions, "all")) == (1, 1, 1)
    assert stats.total(stats.view_counts([doc], predictions, "shared11")) == (1, 0, 1)


def test_report_keeps_the_counters_of_a_remote_predictor():
    doc = render(Template("t-p-901", "test", False, "โทร {{phone}}"), 0, seed=2)
    corpus = Corpus("yrss-eval-v2", "dev", 0, "0" * 64, (doc,))

    class Remote:
        def __init__(self):
            self.stats = {"requests": 1, "http_errors": 1}

        def __call__(self, text):
            return []

    report = harness.evaluate(corpus, {"aiguard": lambda text: [], "llm": Remote()})
    assert report["systems"]["llm"]["predictor_stats"] == {"requests": 1, "http_errors": 1}
    assert "predictor_stats" not in report["systems"]["aiguard"]


def test_dedupe_wrapper_keeps_a_remote_predictors_counters():
    class Remote:
        def __init__(self):
            self.stats = {"requests": 0}

        def __call__(self, text):
            self.stats["requests"] += 1
            return [(0, 2, "NAME"), (1, 3, "NAME")]

    remote = Remote()
    wrapped = systems._deduped(remote)
    assert wrapped("abcd") == [(0, 2, "NAME")]
    assert wrapped.stats is remote.stats
    assert wrapped.stats["requests"] == 1

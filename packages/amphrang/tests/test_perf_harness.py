"""Performance harness (benchmark/perf.py): the measurement logic itself.

Everything here is deterministic — timing loops take an injected timer and
run() takes injected measure functions, so no test depends on wall-clock
speed or on the NER model. One integration test at the bottom runs a real
detect() once to prove the default wiring works.
"""

from benchmark.perf import (
    SIZE_CLASSES,
    anonymize_outcome,
    build_perf_documents,
    evaluate_ci_thresholds,
    measure_callable,
    percentile,
    render_markdown,
    run,
    summarize,
)

# ── percentile / summarize ──────────────────────────────────────────────


def test_percentile_nearest_rank():
    samples = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    assert percentile(samples, 50) == 50.0
    assert percentile(samples, 95) == 100.0
    assert percentile(samples, 100) == 100.0


def test_percentile_single_sample_is_that_sample():
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 95) == 42.0


def test_percentile_is_order_independent():
    assert percentile([30.0, 10.0, 20.0], 50) == percentile([10.0, 20.0, 30.0], 50)


def test_summarize_reports_milliseconds_and_count():
    # seconds in, milliseconds out
    stats = summarize([0.010, 0.020, 0.030])
    assert stats["n"] == 3
    assert stats["p50_ms"] == 20.0
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 30.0


# ── deterministic corpus ────────────────────────────────────────────────


def test_perf_documents_cover_every_size_class():
    docs = build_perf_documents(seed=42)
    assert set(docs) == set(SIZE_CLASSES)


def test_perf_documents_hit_size_targets_within_tolerance():
    docs = build_perf_documents(seed=42)
    for name, target in SIZE_CLASSES.items():
        assert 0.8 * target <= len(docs[name]) <= 1.2 * target, (name, len(docs[name]))


def test_perf_documents_are_deterministic():
    assert build_perf_documents(seed=42) == build_perf_documents(seed=42)


def test_perf_documents_never_cut_a_corpus_line_in_half():
    """A mid-line slice leaves a partial name/value that detection cannot see
    but the residual scanner can — anonymize() then fails closed and the
    whole perf run aborts. Every body line must be a complete corpus line."""
    from benchmark.corpus import build_corpus

    whole_lines = {sample.text for sample in build_corpus(seed=42, size=200)}
    docs = build_perf_documents(seed=42)
    for name, text in docs.items():
        body_lines = text.split("\n")[1:]  # line 0 is the fixed header
        for line in body_lines:
            assert line in whole_lines, (name, line[-80:])


def test_perf_documents_contain_detectable_pii():
    # A perf doc with nothing to find would time an empty pipeline.
    from amphrang.engine.detectors.fp_detector import detect_fp

    docs = build_perf_documents(seed=42)
    for name, text in docs.items():
        assert detect_fp(text), f"{name} document has no structured PII"


# ── timing loop with injected timer ─────────────────────────────────────


def test_measure_callable_returns_one_duration_per_iteration():
    ticks = iter(range(100))

    def fake_timer():
        return float(next(ticks))

    calls = []
    durations = measure_callable(lambda: calls.append(1), iterations=5, timer=fake_timer)
    assert len(durations) == 5
    assert all(d == 1.0 for d in durations)


def test_measure_callable_excludes_warmup_from_results():
    calls = []
    durations = measure_callable(
        lambda: calls.append(1), iterations=3, warmup=2, timer=__import__("time").perf_counter
    )
    assert len(calls) == 5  # warmup ran the callable too
    assert len(durations) == 3  # but only timed iterations are reported


# ── anonymize outcome: a fail-closed block is still a completed timing ──


def test_anonymize_outcome_false_on_clean_text():
    assert anonymize_outcome("สวัสดีครับ วันนี้อากาศดี") is False


def test_anonymize_outcome_true_when_leak_guard_blocks(monkeypatch):
    import amphrang

    def blocked(_text, mode):
        raise amphrang.LeakBlockedError(["NAME"], policy_categories=[])

    monkeypatch.setattr(amphrang, "anonymize", blocked)
    assert anonymize_outcome("อะไรก็ได้") is True


def test_run_reports_leak_blocked_flag_per_class():
    report = run(profile="ci", measure=_fake_measure, cold_start_fn=lambda: [0.5])
    for stats in report["latency"].values():
        assert stats["anonymize"]["leak_blocked"] is False  # fake measure never calls fn


def test_render_markdown_marks_leak_blocked_classes():
    report = run(profile="ci", measure=_fake_measure, cold_start_fn=lambda: [0.5])
    report["latency"]["M"]["anonymize"]["leak_blocked"] = True
    text = render_markdown(report)
    assert "fail-closed" in text


# ── CI regression guard ─────────────────────────────────────────────────


def _report_with_p95(class_name, op, p95_ms):
    return {
        "latency": {class_name: {op: {"n": 5, "p50_ms": p95_ms / 2, "p95_ms": p95_ms}}},
    }


def test_ci_thresholds_pass_under_ceiling():
    report = _report_with_p95("S", "detect", 100.0)
    failures = evaluate_ci_thresholds(report, {("S", "detect"): 200.0})
    assert failures == []


def test_ci_thresholds_fail_over_ceiling_with_numbers_in_message():
    report = _report_with_p95("S", "detect", 500.0)
    failures = evaluate_ci_thresholds(report, {("S", "detect"): 200.0})
    assert len(failures) == 1
    assert "500" in failures[0] and "200" in failures[0]


def test_ci_thresholds_ignore_classes_absent_from_report():
    report = _report_with_p95("S", "detect", 100.0)
    failures = evaluate_ci_thresholds(report, {("XL", "detect"): 1.0})
    assert failures == []


# ── orchestration with injected measurers ───────────────────────────────


def _fake_measure(fn, iterations, warmup=1, timer=None):
    return [0.001] * iterations


def test_run_ci_profile_reports_small_classes_only():
    report = run(profile="ci", measure=_fake_measure, cold_start_fn=lambda: [0.5])
    assert set(report["latency"]) == {"S", "M"}
    assert "multi_worker" not in report["throughput"]


def test_run_report_carries_environment_and_cold_start():
    report = run(profile="ci", measure=_fake_measure, cold_start_fn=lambda: [0.5, 0.6])
    assert report["environment"]["python"]
    assert report["environment"]["amphrang"]
    assert report["cold_start"]["n"] == 2


def test_run_full_profile_covers_all_classes_and_both_ops():
    report = run(profile="full", measure=_fake_measure, cold_start_fn=lambda: [0.5])
    assert set(report["latency"]) == set(SIZE_CLASSES)
    for stats in report["latency"].values():
        assert set(stats) == {"detect", "anonymize"}


# ── markdown rendering ──────────────────────────────────────────────────


def test_render_markdown_has_a_row_per_measured_class():
    report = run(profile="ci", measure=_fake_measure, cold_start_fn=lambda: [0.5])
    text = render_markdown(report)
    assert "| S |" in text and "| M |" in text
    assert report["environment"]["python"] in text


# ── report files are written LF regardless of platform ─────────────────


def test_write_text_lf_never_writes_crlf(tmp_path):
    from benchmark.perf import write_text_lf

    target = tmp_path / "report.md"
    write_text_lf(target, "line1\nline2\n")
    assert b"\r" not in target.read_bytes()


# ── integration: default wiring really measures amphrang ────────────────


def test_real_detect_measurement_on_small_document():
    docs = build_perf_documents(seed=42)
    import amphrang

    durations = measure_callable(lambda: amphrang.detect(docs["S"]), iterations=1, warmup=0)
    assert len(durations) == 1
    assert durations[0] > 0

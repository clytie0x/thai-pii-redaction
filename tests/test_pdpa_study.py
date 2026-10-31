def test_joint_score_counts_unsupported_positive_as_miss_and_topic_alert():
    from benchmark.pdpa_study import score_predictions

    rows = [
        {
            "scope": "sensitive",
            "modality": "text",
            "targets": [{"category": "HEALTH", "attribution": "topic"}],
        },
        {
            "scope": "sensitive",
            "modality": "text",
            "targets": [{"category": "GENETIC_DATA", "attribution": "personal"}],
        },
    ]
    reports = [
        {
            "findings": [{"category": "HEALTH", "attribution": "personal"}],
            "engine": {"status": "ok"},
        },
        {"findings": [], "engine": {"status": "ok"}},
    ]
    result = score_predictions(rows, reports)
    assert result["personal"]["tp"] == 0
    assert result["personal"]["fp"] == 1
    assert result["personal"]["fn"] == 1
    assert result["topic_only_false_alert_rate"] == 1
    assert result["by_category"]["GENETIC_DATA"]["fn"] == 1


def test_joint_score_requires_the_correct_attribution_not_just_topic():
    from benchmark.pdpa_study import score_predictions

    row = {
        "scope": "sensitive",
        "modality": "text",
        "targets": [{"category": "HEALTH", "attribution": "personal"}],
    }
    report = {
        "findings": [{"category": "HEALTH", "attribution": "topic"}],
        "engine": {"status": "ok"},
    }
    result = score_predictions([row], [report])
    assert result["topic"]["recall"] == 1
    assert result["joint"]["recall"] == 0


def test_score_refuses_missing_records():
    import pytest

    from benchmark.pdpa_study import score_predictions

    with pytest.raises(ValueError):
        score_predictions([{"scope": "modality", "modality": "image", "targets": []}], [])


def test_selected_hybrid_threshold_follows_eligibility_not_unconstrained_score():
    from benchmark.pdpa_study import select_configuration

    results = {
        "contextual": {
            "macro_personal_f2": 0.1,
            "topic_only_false_alert_rate": 0,
            "warm_ms": {"p50": 1},
        },
        "hybrid_0.40": {
            "macro_personal_f2": 0.9,
            "topic_only_false_alert_rate": 0.6,
            "warm_ms": {"p50": 10},
        },
        "hybrid_0.50": {
            "macro_personal_f2": 0.8,
            "topic_only_false_alert_rate": 0.1,
            "warm_ms": {"p50": 10},
        },
    }
    selected = select_configuration(results)
    assert selected["recommended_available_strategy"] == "hybrid_0.50"
    assert selected["hybrid_threshold"] == 0.5


def test_study_identity_includes_metric_and_decode_dependencies():
    from benchmark.pdpa_study import source_identity

    files = source_identity()["source_files"]
    assert {
        "benchmark/scorer.py",
        "benchmark/campaign.py",
        "benchmark/blind.py",
        "benchmark/gold.py",
    } <= set(files)


def test_study_identity_binds_the_local_ner_asset_and_runtime():
    from benchmark.pdpa_study import source_identity

    identity = source_identity()
    assert len(identity["ner_asset_sha256"]) == 64
    assert identity["python"]
    assert len(identity["protocol_sha256"]) == 64

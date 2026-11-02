"""Synthetic shared-core policy and value-free adapter projections."""

import json
from pathlib import Path

import pytest

from pii_redactor import report
from pii_redactor.config import CoreConfig
from pii_redactor.pdpa_categories import SECTION26_CATEGORIES


def test_each_adapter_declares_policy_and_contract():
    path = Path(__file__).resolve().parents[1] / "config/shared-core-qualification.json"
    assert path.is_file(), "Every live text adapter needs an explicit contract"
    matrix = json.loads(path.read_text(encoding="utf-8"))
    assert matrix["schema"] == 1
    profiles = matrix["profiles"]
    assert set(profiles) == {
        "root_python",
        "root_http",
        "local_broker",
        "sdk_python",
        "sdk_cli",
        "sdk_http",
        "sdk_mcp",
        "sdk_proxy",
        "hosted",
    }
    fields = {
        "config_prefix",
        "engines",
        "default_engine",
        "remote_detection",
        "inputs",
        "span_units",
        "mapping_owner",
        "warning_projection",
        "sensitive_policy",
        "success_plaintext",
        "errors",
        "core",
        "qualification",
    }
    for profile in profiles.values():
        assert fields <= profile.keys()
        assert profile["sensitive_policy"] == "warn_report"
        assert profile["default_engine"] in profile["engines"]
        assert profile["core"] == "pii_redactor"
        assert profile["inputs"] == ["text"]
        assert profile["qualification"] == "pending_combined_artifact_and_host_gates"
    assert profiles["sdk_mcp"]["success_plaintext"] == ["matched_text", "restored_text"]
    assert profiles["sdk_proxy"]["warning_projection"] == "static_operator_warning_codes"
    assert profiles["hosted"]["wire_section26_categories"] == list(SECTION26_CATEGORIES[:8])
    assert set(matrix["assessment_aliases"]) == {"GENETIC", "BIOMETRIC"}


@pytest.mark.parametrize(
    "category,keyword",
    [
        ("GENETIC", "จีโนม"),
        ("GENETIC", "โครโมโซม"),
        ("GENETIC", "ยีน"),
        ("BIOMETRIC", "ไบโอเมตริก"),
        ("BIOMETRIC", "สแกนนิ้ว"),
        ("BIOMETRIC", "จดจำใบหน้า"),
    ],
)
def test_legacy_sdk_reporting_keywords_keep_their_category(category, keyword):
    assert report.section26_warnings(keyword) == [f"section26:{category}"]


def test_gene_keyword_does_not_flag_jeans():
    assert report.section26_warnings("กางเกงยีนส์") == []


def test_http_response_categories_accept_the_complete_shared_taxonomy():
    pytest.importorskip("fastapi", reason="optional web dependency")
    from pydantic import TypeAdapter

    from app import http_v2

    checked = 0
    for model in vars(http_v2).values():
        fields = getattr(model, "model_fields", {})
        if "section26_categories" in fields:
            checked += 1
            assert TypeAdapter(fields["section26_categories"].annotation).validate_python(
                ["GENETIC", "BIOMETRIC"]
            ) == ["GENETIC", "BIOMETRIC"]
    assert checked >= 4


def test_ten_section26_categories_remain_warning_signals():
    assert set(SECTION26_CATEGORIES) == {
        "RACE_ETHNICITY",
        "POLITICAL_OPINION",
        "RELIGION",
        "HEALTH",
        "SEXUAL_BEHAVIOR",
        "CRIMINAL_RECORD",
        "DISABILITY",
        "LABOR_UNION",
        "GENETIC",
        "BIOMETRIC",
    }


def test_section26_warnings_never_contain_matched_values():
    warnings = getattr(report, "section26_warnings", lambda text: [])
    assert warnings("ข้อมูลพันธุกรรมและข้อมูลชีวภาพ") == [
        "section26:GENETIC",
        "section26:BIOMETRIC",
    ]


def test_public_analysis_projection_drops_raw_semantic_or_keyword_text():
    original = {
        "direct_pii_count": 0,
        "section26": [
            {"category": "HEALTH", "text": "synthetic-private-hit", "start": 2, "end": 9},
            {"category": "GENETIC", "text": "synthetic-semantic-hit", "source": "semantic"},
        ],
    }
    project = getattr(report, "project_analysis", lambda result: result)
    result = project(original)
    assert result == {
        "direct_pii_count": 0,
        "section26": [
            {"category": "HEALTH", "start": 2, "end": 9},
            {"category": "GENETIC", "source": "semantic"},
        ],
    }
    assert original["section26"][0]["text"] == "synthetic-private-hit"


@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_sensitive_signal_is_reported_without_automatic_masking(mode):
    from pii_redactor.stateless import sanitize_stateless

    text = "ข้อมูลพันธุกรรมและข้อมูลชีวภาพ"
    result = sanitize_stateless(
        text,
        mode=mode,
        salt="synthetic-section26-policy",
        config=CoreConfig(engine="thainer", allow_remote=False),
    )
    assert result.sanitized_text == text
    assert result.mapping == {}
    assert result.warnings == ["section26:GENETIC", "section26:BIOMETRIC"]

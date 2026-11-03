import json
from typing import ClassVar

import pytest


def test_catalog_represents_every_named_sensitive_family_and_open_limits():
    from pii_redactor.pdpa_catalog import coverage_catalog

    rows = coverage_catalog()
    sensitive = {r["category"] for r in rows if r["section"] == "26" and r["named"]}
    assert sensitive == {
        "RACE",
        "ETHNICITY",
        "POLITICAL_OPINION",
        "BELIEF",
        "SEXUAL_BEHAVIOR",
        "CRIMINAL_RECORD",
        "HEALTH",
        "DISABILITY",
        "LABOR_UNION",
        "GENETIC_DATA",
        "BIOMETRIC_IDENTITY",
    }
    assert any(r["capability"] == "open_scope_not_assessed" for r in rows)
    assert all(r["capability"] != "complete" for r in rows)


def test_semantic_candidates_cover_the_same_explicit_catalog_as_rules():
    from pii_redactor.pdpa_catalog import GENERAL, SENSITIVE
    from pii_redactor.pdpa_semantic import PROTOTYPES

    assert set(PROTOTYPES) == set(GENERAL) | set(SENSITIVE)


def test_contextual_attribution_distinguishes_personal_and_topic():
    from pii_redactor.pdpa_assessment import assess_text

    personal = assess_text("ฉันมีผลตรวจยืนยันว่าเป็นเบาหวาน", strategy="contextual")
    topic = assess_text("บทความอธิบายโรคเบาหวานสำหรับการเรียน", strategy="contextual")
    assert any(
        f["category"] == "HEALTH" and f["attribution"] == "personal" for f in personal["findings"]
    )
    assert any(f["category"] == "HEALTH" and f["attribution"] == "topic" for f in topic["findings"])
    assert "เบาหวาน" not in json.dumps(personal, ensure_ascii=False)
    assert personal["legal_clearance"] is False


def test_negative_health_statement_still_concerns_a_person():
    from pii_redactor.pdpa_assessment import assess_text

    result = assess_text("ผลตรวจของฉันไม่พบ HIV", strategy="contextual")
    assert any(
        f["category"] == "HEALTH" and f["attribution"] == "personal" for f in result["findings"]
    )


def test_reported_personal_negative_fact_is_not_dismissed_as_topic():
    from pii_redactor.pdpa_assessment import assess_text

    result = assess_text("The article reports that my HIV test is negative.")
    assert any(
        f["category"] == "HEALTH" and f["attribution"] in {"personal", "ambiguous"}
        for f in result["findings"]
    )


def test_semantic_photo_similarity_cannot_override_biometric_relation_check():
    from pii_redactor.pdpa_assessment import assess_text

    class Backend:
        identity: ClassVar[dict] = {"kind": "test_double"}

        def topics(self, text, **kwargs):
            return [
                {"category": "BIOMETRIC_IDENTITY", "start": 0, "end": len(text), "similarity": 0.8}
            ]

    result = assess_text("My photo is in the album.", strategy="hybrid", semantic_backend=Backend())
    assert not any(
        f["category"] == "BIOMETRIC_IDENTITY" and f["attribution"] == "personal"
        for f in result["findings"]
    )


def test_invalid_semantic_scores_fail_instead_of_emitting_nan_json():
    from pii_redactor.pdpa_assessment import assess_text

    class Backend:
        identity: ClassVar[dict] = {"kind": "test_double"}

        def topics(self, text, **kwargs):
            return [
                {"category": "HEALTH", "start": 0, "end": len(text), "similarity": float("nan")}
            ]

    with pytest.raises(RuntimeError, match="integrity"):
        assess_text("My health record.", strategy="hybrid", semantic_backend=Backend())


def test_nationality_gender_and_ordinary_photo_do_not_infer_sensitive_types():
    from pii_redactor.pdpa_assessment import assess_text

    result = assess_text("ฉันมีสัญชาติไทย เพศหญิง และมีรูปถ่ายสมัครงาน", strategy="contextual")
    assert not {"RACE", "ETHNICITY", "SEXUAL_BEHAVIOR", "BIOMETRIC_IDENTITY"} & {
        f["category"] for f in result["findings"]
    }


def test_all_new_sensitive_types_have_actual_text_evidence():
    from pii_redactor.pdpa_assessment import assess_text

    result = assess_text(
        "ข้อมูลของฉัน: ผลตรวจ DNA และแม่แบบลายนิ้วมือสำหรับยืนยันตัวตน", strategy="contextual"
    )
    assert {"GENETIC_DATA", "BIOMETRIC_IDENTITY"} <= {f["category"] for f in result["findings"]}


def test_raw_modalities_are_not_reported_as_clean_text():
    from pii_redactor.pdpa_assessment import assess_text

    result = assess_text("", modality="image")
    assert result["engine"]["status"] == "not_assessed"
    assert "review_modality" in result["review_reasons"]
    assert result["findings"] == []


def test_explicit_semantic_selection_never_silently_falls_back():
    from pii_redactor.pdpa_assessment import assess_text

    with pytest.raises(RuntimeError, match="semantic"):
        assess_text("ข้อความ", strategy="hybrid", model_dir="missing-model-directory")


def test_report_keeps_original_offsets_and_no_source_values():
    from pii_redactor.pdpa_assessment import assess_text

    text = "🛡 ข้อมูลของฉัน: ศาสนา: พุทธ\nข้อมูลชีวภาพ: แม่แบบใบหน้าใช้ยืนยันตัวตน"
    result = assess_text(text)
    assert result["findings"]
    for finding in result["findings"]:
        assert 0 <= finding["start"] < finding["end"] <= len(text)
        assert "text" not in finding and "value" not in finding
    assert text not in json.dumps(result, ensure_ascii=False)


def test_assessment_validates_untrusted_input_without_echoing_it():
    from pii_redactor.pdpa_assessment import assess_text

    with pytest.raises(ValueError):
        assess_text("x" * 20001)


def test_pseudonymous_record_and_subject_specific_negation_remain_linkable():
    from pii_redactor.pdpa_assessment import assess_text

    result = assess_text("พนักงานรหัส E017: ผลตรวจไม่พบ HIV")
    assert any(
        f["category"] == "HEALTH" and f["attribution"] == "personal" for f in result["findings"]
    )


def test_semantic_assets_reject_tampering_before_optional_model_loading(tmp_path):
    from pii_redactor.pdpa_semantic import REVISION, SemanticModel

    path = tmp_path / REVISION
    path.mkdir()
    (path / "model.safetensors").write_bytes(b"synthetic-not-real-weights")
    with pytest.raises(RuntimeError, match="identity mismatch"):
        SemanticModel(str(path))


def test_assessment_rejects_skipped_ner_instead_of_reporting_clean(monkeypatch):
    from pii_redactor import pdpa_assessment

    def skipped(text, *, ner_diagnostics=None):
        if ner_diagnostics is not None:
            ner_diagnostics.attempted = 1
            ner_diagnostics.skipped = 1
        return []

    monkeypatch.setattr(pdpa_assessment, "detect_all", skipped)
    with pytest.raises(RuntimeError, match="incomplete"):
        pdpa_assessment.assess_text("synthetic input")


@pytest.mark.parametrize(
    "text,category",
    [
        ("เขาระบุว่าเป็นเบาหวาน", "HEALTH"),
        ("เธอแจ้งว่านับถือศาสนาพุทธ", "BELIEF"),
        ("She has a medical diagnosis.", "HEALTH"),
        ("ฉันเป็นนักศึกษา รหัสนักศึกษา 6220012345", "EDUCATION"),
    ],
)
def test_ordinary_third_person_and_student_labels_are_not_lost(text, category):
    from pii_redactor.pdpa_assessment import assess_text

    result = assess_text(text)
    assert any(
        f["category"] == category and f["attribution"] == "personal" for f in result["findings"]
    )


def test_unrelated_first_person_does_not_attribute_article_health_to_speaker():
    from pii_redactor.pdpa_assessment import assess_text

    result = assess_text("ฉันเป็นนักศึกษากำลังอ่านบทความอธิบายโรคเบาหวาน")
    assert not any(
        f["category"] == "HEALTH" and f["attribution"] == "personal" for f in result["findings"]
    )


def test_local_assessment_missing_asset_fails_before_detector_download(monkeypatch):
    from pythainlp import corpus

    from pii_redactor import pdpa_assessment

    monkeypatch.setattr(corpus, "get_corpus_default_db", lambda *a, **k: None)
    monkeypatch.setattr(corpus, "get_corpus_db_detail", lambda *a, **k: {})
    called = []
    monkeypatch.setattr(pdpa_assessment, "detect_all", lambda *a, **k: called.append(True) or [])
    with pytest.raises(RuntimeError, match="local NER"):
        pdpa_assessment.assess_text("synthetic")
    assert called == []

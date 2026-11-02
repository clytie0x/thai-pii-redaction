"""Approved warn/report migration replaces the historical automatic-mask policy.

The retired private assertions and their replacements are listed in the shared
core migration guide. These use only fabricated inputs and mappings.
"""

import importlib
import time
import uuid

import pytest
from pii_redactor import leak_guard, sensitive_detector
from pii_redactor.detectors import aggregate
from pii_redactor.models import EntityRegistry, ReverseResult, VaultRecord
from pii_redactor.output_validator import PIILeakError, _layer1_pii_scan, validate_output
from pii_redactor.pdpa_categories import SECTION26_CATEGORIES
from pii_redactor.session_vault import SessionVault

import amphrang
from amphrang._core_config import sdk_core_config

CATEGORIES = [
    ("RACE_ETHNICITY", "เชื้อชาติ", "เชื้อชาติ"),
    ("POLITICAL_OPINION", "ความคิดเห็นทางการเมือง", "ความเห็นการเมือง"),
    ("RELIGION", "ศาสนา", "ศาสนา"),
    ("HEALTH", "โรค", "ข้อมูลสุขภาพ"),
    ("SEXUAL_BEHAVIOR", "เพศวิถี", "พฤติกรรมทางเพศ"),
    ("CRIMINAL_RECORD", "คดี", "ประวัติคดี"),
    ("DISABILITY", "ความพิการ", "ความพิการ"),
    ("LABOR_UNION", "สหภาพแรงงาน", "สหภาพแรงงาน"),
    ("GENETIC", "พันธุกรรม", "ข้อมูลพันธุกรรม"),
    ("BIOMETRIC", "ลายนิ้วมือ", "ข้อมูลชีวภาพ"),
]


@pytest.fixture(autouse=True)
def local_keyword_profile(monkeypatch):
    original_tb = aggregate.detect_tb
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    monkeypatch.setattr(aggregate, "detect_tb", lambda *args, **kwargs: [])
    monkeypatch.setattr(leak_guard, "detect_tb", lambda *args, **kwargs: [])
    monkeypatch.setattr(sensitive_detector, "detect_sensitive", lambda text: [])
    return original_tb


def test_migration_covers_every_canonical_sensitive_category():
    assert [category for category, _, _ in CATEGORIES] == list(SECTION26_CATEGORIES)


def test_obsolete_private_sensitive_detector_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("amphrang.engine.detectors.sensitive_span")


@pytest.mark.parametrize(("category", "keyword", "label"), CATEGORIES)
@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_sensitive_only_never_blocks_or_masks(category, keyword, label, mode):
    text = f"ข้อมูลสังเคราะห์ {keyword}"
    assert amphrang.detect(text) == []
    result = amphrang.anonymize(text, mode=mode)
    assert result.text == text
    assert result.mapping == {} and result.entities == []
    assert result.warnings == [f"section26:{category}"]


@pytest.mark.parametrize(("category", "keyword", "label"), CATEGORIES)
@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_identifier_roundtrip_preserves_sensitive_text_and_warns(category, keyword, label, mode):
    text = f"{keyword} โทร 081-234-5678"
    result = amphrang.anonymize(text, mode=mode, salt="synthetic-migration")
    assert keyword in result.text and "081-234-5678" not in result.text
    assert result.entity_type_counts == {"PHONE": 1}
    assert all(text[item["start"] : item["end"]] == "081-234-5678" for item in result.entities)
    assert result.warnings == [f"section26:{category}"]
    assert amphrang.restore(result.text, result.mapping).text == text


@pytest.mark.parametrize(("category", "keyword", "label"), CATEGORIES)
def test_report_projects_categories_without_direct_sensitive_entities(category, keyword, label):
    result = amphrang.analyze(keyword)
    assert result["direct_pii_count"] == 0 and result["breakdown"] == []
    assert [hit["category"] for hit in result["section26"]] == [category]
    assert all("text" not in hit for hit in result["section26"])


@pytest.mark.parametrize(("category", "keyword", "label"), CATEGORIES)
def test_session_warns_and_withholds_its_mapping(category, keyword, label):
    with amphrang.Session() as session:
        text = f"{keyword} โทร 081-234-5678"
        result = session.anonymize(text)
        assert result.mapping == {}
        assert keyword in result.text and "081-234-5678" not in result.text
        assert result.warnings == [f"section26:{category}"]
        assert session.restore(result.text).text == text


@pytest.mark.parametrize(("category", "keyword", "label"), CATEGORIES)
@pytest.mark.parametrize("mode", [None, "token", "surrogate"])
def test_synthetic_legacy_sensitive_tokens_restore(category, keyword, label, mode):
    token = f"[{label}_{'a' * 25}_{'b' * 20}_1]"
    result = amphrang.restore(token, {token: "ข้อมูลสังเคราะห์"}, mode=mode)
    assert result.text == "ข้อมูลสังเคราะห์"
    assert result.replaced_count == 1 and result.leftover_pseudonyms == []


def test_legacy_mapping_reuse_does_not_enable_new_sensitive_masking():
    token = f"[ข้อมูลสุขภาพ_{'a' * 25}_{'b' * 20}_1]"
    result = amphrang.anonymize("โรค โทร 081-234-5678", prior_mapping={token: "โรค"})
    assert result.mapping[token] == "โรค"
    assert "โรค" in result.text and token not in result.text
    assert "081-234-5678" not in result.text
    assert result.warnings == ["section26:HEALTH"]


def test_generated_identifier_validation_remains_fail_closed():
    with pytest.raises(amphrang.LeakBlockedError) as caught:
        amphrang.anonymize("ค่าที่เหลือ 6801234")
    assert caught.value.leak_types == ["ORPHAN_DIGITS"]


def test_proxy_uses_operator_warning_without_sensitive_masking():
    from amphrang.proxy.core import sanitize_chat_request

    with pytest.warns(UserWarning, match="^section26:HEALTH$"):
        result, mapping = sanitize_chat_request(
            {"messages": [{"role": "user", "content": "โรค โทร 081-234-5678"}]},
            salt="synthetic-migration",
        )
    text = result["messages"][0]["content"]
    assert "โรค" in text and "081-234-5678" not in text
    assert amphrang.restore(text, mapping).text == "โรค โทร 081-234-5678"


def test_surrogate_mode_still_fakes_the_name_realistically(monkeypatch, local_keyword_profile):
    monkeypatch.setattr(aggregate, "detect_tb", local_keyword_profile)
    monkeypatch.setattr(leak_guard, "detect_tb", local_keyword_profile)
    text = "นายสมชาย ใจดี ป่วยเป็นโรคเบาหวาน"
    result = amphrang.anonymize(text, mode="surrogate", salt="synthetic-migration")
    assert "สมชาย" not in result.text and "โรคเบาหวาน" in result.text
    assert result.entity_type_counts.get("NAME", 0) >= 1
    assert amphrang.restore(result.text, result.mapping).text == text


def test_a_pseudonym_containing_its_own_real_value_is_still_untrusted():
    vault = SessionVault()
    for index, (data_type, original, pseudonym) in enumerate(
        [
            ("NAME", "สมชาย", "คุณสมชาย"),
            ("RELIGION", "อิสลาม", "[ศาสนาอิสลาม]"),
            ("HEALTH", "1101700230708", "[ข้อมูลสุขภาพ_1101700230708]"),
        ]
    ):
        vault.write(
            VaultRecord(
                str(index),
                original,
                pseudonym,
                "TB",
                data_type,
                (0, len(original)),
                time.monotonic(),
            )
        )
    assert vault.trusted_pseudonyms() == set()


_L1_TEXT = "ติดต่อ 081-234-5678 ได้ทุกวัน"
_L1_SPLIT = 10


def _l1_vault(ranges):
    vault = SessionVault()
    for start, end in ranges:
        vault.write(
            VaultRecord(
                str(uuid.uuid4()),
                _L1_TEXT[start:end],
                f"PSEUDO_{start}_{end}",
                "TB",
                "NAME",
                (start, end),
                time.monotonic(),
            )
        )
    return vault


def test_layer1_excuses_a_span_covered_by_two_contiguous_restored_ranges():
    ranges = ((0, _L1_SPLIT), (_L1_SPLIT, len(_L1_TEXT)))
    result = ReverseResult(text=_L1_TEXT, restored_ranges=ranges)
    clean, flags, spans = _layer1_pii_scan(result, _l1_vault(ranges), config=sdk_core_config())
    assert clean and flags == [] and spans == ()


def test_layer1_still_halts_when_one_character_was_not_restored():
    ranges = ((0, _L1_SPLIT), (_L1_SPLIT + 1, len(_L1_TEXT)))
    result = ReverseResult(text=_L1_TEXT, restored_ranges=ranges)
    clean, flags, spans = _layer1_pii_scan(result, _l1_vault(ranges), config=sdk_core_config())
    assert not clean
    assert any(flag.startswith("unexpected_pii_count:") for flag in flags)
    assert spans == ((_L1_SPLIT, _L1_SPLIT + 1),)


def test_validate_output_raises_pii_leak_error_on_the_uncovered_character():
    ranges = ((0, _L1_SPLIT), (_L1_SPLIT + 1, len(_L1_TEXT)))
    result = ReverseResult(text=_L1_TEXT, restored_ranges=ranges)
    with pytest.raises(PIILeakError):
        validate_output(
            result, EntityRegistry([], 0, 0), _l1_vault(ranges), config=sdk_core_config()
        )

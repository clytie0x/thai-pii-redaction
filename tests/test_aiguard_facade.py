"""The public `aiguard` facade — the only import surface with a semver contract.

All PII values here are fabricated (checksum-valid where the type requires it),
same policy as every other test in this repository.
"""

import aiguard

SAMPLE = "ผมชื่อสมชาย ใจดี เบอร์โทร 081-234-5678 เลขบัตรประชาชน 1-1017-00230-70-8"


def test_detect_returns_entities_with_caller_spans():
    entities = aiguard.detect(SAMPLE)
    types = {entity.data_type for entity in entities}
    assert "THAI_ID" in types
    assert "PHONE" in types
    for entity in entities:
        start, end = entity.span
        assert SAMPLE[start:end] == entity.original_text


def test_anonymize_restore_roundtrip_token_mode():
    masked = aiguard.anonymize(SAMPLE, mode="token")
    assert "1-1017-00230-70-8" not in masked.text
    assert "081-234-5678" not in masked.text
    assert masked.mapping
    restored = aiguard.restore(masked.text, masked.mapping)
    assert "1-1017-00230-70-8" in restored.text
    assert "081-234-5678" in restored.text
    assert not restored.leftover_pseudonyms


def test_anonymize_restore_roundtrip_surrogate_mode():
    masked = aiguard.anonymize(SAMPLE, mode="surrogate", salt="facade-test-salt")
    assert "1-1017-00230-70-8" not in masked.text
    restored = aiguard.restore(masked.text, masked.mapping)
    assert "1-1017-00230-70-8" in restored.text


def test_anonymize_same_salt_is_reproducible():
    first = aiguard.anonymize(SAMPLE, mode="surrogate", salt="fixed-salt")
    second = aiguard.anonymize(SAMPLE, mode="surrogate", salt="fixed-salt")
    assert first.text == second.text


def test_session_multiturn_roundtrip_without_exposing_mapping():
    with aiguard.Session(mode="token") as session:
        masked = session.anonymize(SAMPLE)
        assert "1-1017-00230-70-8" not in masked.text
        assert masked.mapping == {}  # the vault owns it
        restored = session.restore(masked.text)
        assert "1-1017-00230-70-8" in restored.text


def test_session_keeps_pseudonyms_consistent_across_turns():
    with aiguard.Session(mode="token") as session:
        first = session.anonymize("เลขบัตร 1-1017-00230-70-8 ครับ")
        second = session.anonymize("ยืนยันอีกครั้ง เลขบัตร 1-1017-00230-70-8")
        token = next(
            entity["token"] for entity in first.entities if entity["data_type"] == "THAI_ID"
        )
        assert token in second.text


def test_analyze_returns_pdpa_dict_without_raw_values():
    report = aiguard.analyze(SAMPLE)
    assert isinstance(report, dict)
    flattened = repr(report)
    assert "1-1017-00230-70-8" not in flattened
    assert "11017002307" not in flattened.replace("-", "")


THAI_NUMERAL_SAMPLE = "เบอร์โทรผมคือ ๐๘๑-๒๓๔-๕๖๗๘"


def test_detect_finds_thai_numeral_phone_with_caller_slice():
    entities = aiguard.detect(THAI_NUMERAL_SAMPLE)
    phones = [e for e in entities if e.data_type == "PHONE"]
    assert phones, "Thai-numeral phone must be detected"
    start, end = phones[0].span
    assert phones[0].original_text == THAI_NUMERAL_SAMPLE[start:end]


def test_anonymize_masks_thai_numeral_phone():
    """Regression: the first facade cut skipped detection_text normalization,
    so a Thai-numeral phone number sailed through anonymize unmasked with no
    error and no warning — the exact silent fail-open the engine forbids."""
    masked = aiguard.anonymize(THAI_NUMERAL_SAMPLE, mode="token")
    assert "๐๘๑" not in masked.text
    assert "๒๓๔" not in masked.text
    assert masked.mapping, "the masked phone must be in the mapping"
    restored = aiguard.restore(masked.text, masked.mapping)
    # The engine stores the raw slice as the original, so the exact
    # Thai-numeral text comes back.
    assert "๐๘๑-๒๓๔-๕๖๗๘" in restored.text


def test_session_masks_thai_numeral_phone():
    with aiguard.Session(mode="token") as session:
        masked = session.anonymize(THAI_NUMERAL_SAMPLE)
        assert "๐๘๑" not in masked.text
        restored = session.restore(masked.text)
        # The vault stores the raw slice, so the exact Thai-numeral original
        # comes back (the stateless path restores the normalized form instead).
        assert "๐๘๑-๒๓๔-๕๖๗๘" in restored.text


def test_analyze_counts_thai_numeral_pii():
    report = aiguard.analyze(THAI_NUMERAL_SAMPLE)
    assert report["direct_pii_count"] >= 1


def test_restore_reports_generated_and_foreign_counters():
    masked = aiguard.anonymize(SAMPLE, mode="token")
    restored = aiguard.restore(masked.text, masked.mapping)
    assert restored.generated_pii_count == 0
    assert restored.foreign_replacement_count == 0
    assert "ai_generated_pii" not in restored.warnings


def test_leak_blocked_error_is_exported():
    assert issubclass(aiguard.LeakBlockedError, Exception)
    assert issubclass(aiguard.SessionExpiredError, Exception)


def test_public_surface_is_exactly_the_documented_set():
    documented = {
        "AnonymizeResult",
        "Entity",
        "LeakBlockedError",
        "RedactionResult",
        "RestoreResult",
        "Session",
        "SessionExpiredError",
        "analyze",
        "anonymize",
        "detect",
        "redact_pdf",
        "restore",
    }
    assert set(aiguard.__all__) == documented

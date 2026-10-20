"""Batch facade: detect_batch / anonymize_batch.

Each item is processed independently and must behave exactly like its
single-call counterpart; the batch is a convenience plus an opt-in
process-parallel path, never a semantic change.
"""

import pytest

import amphrang

TEXTS = [
    "ผมชื่อ นายสมชาย ใจดี โทร 081-234-5678",
    "อีเมลติดต่อ somchai@example.com ครับ",
    "ข้อความธรรมดาไม่มีข้อมูลส่วนตัว",
]

# Undetected 7-digit run -> ORPHAN_DIGITS residual -> deterministic fail-closed.
LEAKY_TEXT = "ค่าที่เหลือ 6801234"


# ── detect_batch ────────────────────────────────────────────────────────


def _comparable(entities):
    # entity_id is a fresh UUID per detection; compare the meaningful fields.
    return [(e.span, e.data_type, e.redact_type, e.original_text) for e in entities]


def test_detect_batch_matches_single_detect_per_item():
    batched = amphrang.detect_batch(TEXTS)
    singles = [amphrang.detect(text) for text in TEXTS]
    assert [_comparable(row) for row in batched] == [_comparable(row) for row in singles]


def test_detect_batch_empty_list():
    assert amphrang.detect_batch([]) == []


# ── anonymize_batch ─────────────────────────────────────────────────────


def test_anonymize_batch_roundtrips_every_item():
    results = amphrang.anonymize_batch(TEXTS, mode="token")
    assert len(results) == len(TEXTS)
    for text, result in zip(TEXTS, results):
        assert isinstance(result, amphrang.AnonymizeResult)
        restored = amphrang.restore(result.text, result.mapping)
        assert restored.text == text


def test_anonymize_batch_masks_pii_per_item():
    results = amphrang.anonymize_batch(TEXTS, mode="token")
    assert "081-234-5678" not in results[0].text
    assert "somchai@example.com" not in results[1].text


def test_anonymize_batch_same_salt_is_reproducible():
    first = amphrang.anonymize_batch(TEXTS[:2], mode="surrogate", salt="fixed-salt")
    second = amphrang.anonymize_batch(TEXTS[:2], mode="surrogate", salt="fixed-salt")
    assert [r.text for r in first] == [r.text for r in second]


def test_anonymize_batch_fails_closed_and_names_the_item():
    with pytest.raises(amphrang.LeakBlockedError) as excinfo:
        amphrang.anonymize_batch([TEXTS[0], LEAKY_TEXT], mode="token")
    assert excinfo.value.batch_index == 1


def test_single_anonymize_error_has_no_batch_index():
    with pytest.raises(amphrang.LeakBlockedError) as excinfo:
        amphrang.anonymize(LEAKY_TEXT, mode="token")
    assert not hasattr(excinfo.value, "batch_index")


# ── process-parallel path ───────────────────────────────────────────────


def test_detect_batch_with_workers_matches_serial():
    serial = amphrang.detect_batch(TEXTS)
    parallel = amphrang.detect_batch(TEXTS, workers=2)
    assert [_comparable(row) for row in parallel] == [_comparable(row) for row in serial]


def test_anonymize_batch_with_workers_roundtrips():
    results = amphrang.anonymize_batch(TEXTS, mode="token", workers=2)
    for text, result in zip(TEXTS, results):
        assert amphrang.restore(result.text, result.mapping).text == text

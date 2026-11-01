"""Format-preserving detection still sees obscured digits."""

from __future__ import annotations

import random

from benchmark.blind_v2.corpus import _mobile, _thai_id
from pii_redactor.detectors.fp_detector import detect_fp


def _surfaces(value: str) -> dict[str, str]:
    thai = value.translate({ord("0") + offset: ord("๐") + offset for offset in range(10)})
    arabic = value.translate({ord("0") + offset: 0x0660 + offset for offset in range(10)})
    return {
        "zero_width": "\u200b".join(value),
        "thai_digits": thai,
        "arabic_digits": arabic,
        "per_character_space": " ".join(value),
    }


def _found(text: str, entity_type: str) -> bool:
    return any(entity.data_type == entity_type for entity in detect_fp(text))


def test_obscured_checksum_ids_stay_visible():
    digits = _thai_id(random.Random(3))
    for surface in _surfaces(digits).values():
        assert _found(f"เขาท่อง {surface} ให้ฟัง", "THAI_ID")
    ocr = digits.replace("0", "O", 1)
    assert _found(f"เขาท่อง {ocr} ให้ฟัง", "THAI_ID")


def test_obscured_mobile_numbers_stay_visible():
    phone = _mobile(random.Random(4))
    for surface in _surfaces(phone).values():
        assert _found(f"ฝากเบอร์ {surface} ไว้", "PHONE")


def test_word_spaces_stay_and_letter_spaces_collapse():
    from pii_redactor.detectors.surface_norm import normalize_prose

    words, origins = normalize_prose("ไป ที่ บ้าน")
    assert origins is None and words == "ไป ที่ บ้าน"
    folded, origins = normalize_prose("ส ม ช า ย")
    assert folded == "สมชาย"
    assert origins is not None


def test_zero_width_name_is_one_span():
    from pii_redactor.detectors.aggregate import detect_all

    name = "สม\u200bชาย ใจ\u200bดี"
    text = f"เมื่อวาน {name} เล่าว่ากำลังจะย้าย"
    start = text.index(name)
    hits = [
        entity
        for entity in detect_all(text)
        if entity.data_type == "NAME"
        and entity.span[0] <= start
        and entity.span[1] >= start + len(name)
    ]
    assert hits


def test_per_character_spaced_name_is_one_span():
    from pii_redactor.detectors.aggregate import detect_all

    name = " ".join("สมชายใจดี")
    text = f"เมื่อวาน {name} เล่าว่ากำลังจะย้าย"
    start = text.index(name)
    hits = [
        entity
        for entity in detect_all(text)
        if entity.data_type == "NAME"
        and entity.span[0] <= start
        and entity.span[1] >= start + len(name)
    ]
    assert hits


def test_glued_surname_split_still_counts_as_a_name():
    from pii_redactor.detectors.name_context import detect_name_context, is_glued_name_run

    assert is_glued_name_run("ขอแสดงความนับถือ") is False
    assert is_glued_name_run("มาลีทองอยู่") is True
    text = "รถคันนี้เป็นของ มาลีทองอยู่ ที่จอดไว้"
    names = [entity.original_text for entity in detect_name_context(text)]
    assert "มาลีทองอยู่" in names
    assert detect_name_context("เป็นของขวัญวันเกิด") == []


def test_unchanged_surface_avoids_python_character_folding(monkeypatch):
    from pii_redactor.detectors import surface_norm

    def unnecessary_fold(_char):
        raise AssertionError("Unchanged source should not need per-character folding")

    monkeypatch.setattr(surface_norm, "_fold", unnecessary_fold)
    text = "เอกสารทั่วไป มีรายการ 123456 และข้อมูลติดต่อในระบบ"
    normalized, origins = surface_norm.normalize_surface(text)
    assert normalized == text
    assert origins == list(range(len(text)))


def test_surface_shortcut_keeps_unicode_digit_padding_semantics():
    from pii_redactor.detectors.surface_norm import normalize_surface

    for text, expected in [
        ("²  ³", "²³"),
        ("१२ - ३४", "१२-३४"),
        (" 12  ", " 12  "),
        ("12  -  34", "12-34"),
        ("ข้อความ ทั่วไป", "ข้อความ ทั่วไป"),
    ]:
        normalized, origins = normalize_surface(text)
        assert normalized == expected
        assert len(origins) == len(normalized)
        assert all(text[source] == char for char, source in zip(normalized, origins))

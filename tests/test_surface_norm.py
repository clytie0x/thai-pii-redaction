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

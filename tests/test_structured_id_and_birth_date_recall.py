"""Recall and honest labels for plates, birth dates, licences, accounts.

Each group pins one mechanism found on the YRSS v2 dev split:

- a plate written with a hyphen between the letters and the number;
- a birth date with an English or abbreviated Thai month, or behind a cue
  the detector did not know (born, mark-stripped OCR of วันเกิด);
- a licence number that sits a clause away from its cue;
- an account in the 3-6-1 layout, or behind the short cue บช.;
- a phone number glued in front of an e-mail address.

Every value is invented. The controls keep the generic label, or stay
unflagged, when the cue or the shape is missing.
"""

from __future__ import annotations

import pytest

from pii_redactor.detectors.fp_detector import detect_fp


def _found(text: str) -> set[tuple[str, str]]:
    return {(e.data_type, e.original_text) for e in detect_fp(text)}


def _of(text: str, data_type: str) -> set[str]:
    return {e.original_text for e in detect_fp(text) if e.data_type == data_type}


def _type_at(text: str, value: str) -> set[str]:
    start = text.index(value)
    end = start + len(value)
    return {e.data_type for e in detect_fp(text) if e.span[0] < end and start < e.span[1]}


# ── VEHICLE_PLATE: hyphen between letters and number ───────────────────────


@pytest.mark.parametrize(
    ("text", "plate"),
    [
        ("รถกระบะสีเทา ทะเบียน 3ขฬ-2716 จอดอยู่หน้าโกดัง", "3ขฬ-2716"),
        ("มอเตอร์ไซค์ทะเบียน ฌต-41 หายจากลานจอด", "ฌต-41"),
        ("เช่ารถตู้ ป้าย งพ-905 สามวัน", "งพ-905"),
        ("คันของน้องคือ 7ธว-6602 ครับ", "7ธว-6602"),
        ("มีรถ ชฎ-3350 ขับตามมาตลอดทาง", "ชฎ-3350"),
        ("ทะเบียนรถผฆ-118", "ผฆ-118"),
    ],
)
def test_hyphenated_plate_is_found(text, plate):
    assert _of(text, "VEHICLE_PLATE") == {plate}


@pytest.mark.parametrize(
    "text",
    [
        "ประชุมที่ห้อง ก-12 ชั้นสอง",
        "ยื่นแบบ ภงด-53 ภายในวันที่เจ็ด",
        "รหัสสินค้า กข-1234 หมดสต็อก",
        "เครื่องปรับอากาศรุ่น ทส-450 ราคาพิเศษ",
        "SKU AB-1234 พร้อมส่ง",
        "เอกสารเลขที่ นร-0507 ลงรับแล้ว",
        "คะแนนกลุ่ม ขค-12 สูงสุด",
        "งวด ตค-2568 จ่ายแล้ว",
    ],
)
def test_plate_like_code_is_not_a_plate(text):
    assert _of(text, "VEHICLE_PLATE") == set()


def test_spaced_plate_is_unchanged():
    assert _of("รถทะเบียน 2ฒษ 7140 สีขาว", "VEHICLE_PLATE") == {"2ฒษ 7140"}

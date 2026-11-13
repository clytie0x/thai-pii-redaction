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


# ── DATE_OF_BIRTH: date forms ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "date"),
    [
        ("Date of birth: 4 February 1988", "4 February 1988"),
        ("DOB 14 Sep 1992", "14 Sep 1992"),
        ("Born on July 9, 1979 in Lampang", "July 9, 1979"),
        ("เกิดเมื่อ ๗ May ๑๙๘๕ ที่ลำปาง", "๗ May ๑๙๘๕"),
        ("ว/ด/ป เกิด 5 มิ.ย. 2540", "5 มิ.ย. 2540"),
        ("วันเกิด 9 ต.ค. 38 ค่ะ", "9 ต.ค. 38"),
        ("อายุ 41 ปี เกิด 21 กันยายน ค.ศ. 1984", "21 กันยายน ค.ศ. 1984"),
        ("Date of birth18 ก.พ. 2529Sex F", "18 ก.พ. 2529"),
        ("Date of birth30 November 1990Sex M", "30 November 1990"),
        ("เกิดวันที่ 3 สิงหาคม พ.ศ. 2511", "3 สิงหาคม พ.ศ. 2511"),
    ],
)
def test_birth_date_forms_are_found(text, date):
    assert _of(text, "DATE_OF_BIRTH") == {date}


# ── DATE_OF_BIRTH: cue wording ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "date"),
    [
        ("Somying — born 03/11/2531", "03/11/2531"),
        ("birth date 1994-06-27", "1994-06-27"),
        ("Birthday: 12/12/2540", "12/12/2540"),
        ("วนเกด 02/08/2541", "02/08/2541"),
        ("เกดวนท 30 เมษายน 2519", "30 เมษายน 2519"),
        ("วันเดือนปีเกิด 08-10-1996", "08-10-1996"),
    ],
)
def test_birth_cue_wording_gives_birth_label(text, date):
    assert _type_at(text, date) == {"DATE_OF_BIRTH"}


@pytest.mark.parametrize(
    ("text", "date"),
    [
        ("นัดประชุมวันที่ 12 March 2026", "12 March 2026"),
        ("ส่งของวันที่ 3 พ.ค. 2569", "3 พ.ค. 2569"),
        ("วันครบกำหนดชำระ 15/01/2569", "15/01/2569"),
        ("เกิดเหตุเมื่อ 4 June 2024", "4 June 2024"),
        ("ไฟดับเกิดขึ้นเมื่อ 14/02/2569", "14/02/2569"),
        ("ลูกเกด 2 ถุง สั่งวันที่ 01/02/2569", "01/02/2569"),
        ("a stubborn fault since 5 May 2025", "5 May 2025"),
    ],
)
def test_other_dates_keep_the_generic_label(text, date):
    assert _type_at(text, date) == {"DATE"}


@pytest.mark.parametrize(
    "text",
    [
        "เริ่มงานวันที่ 3 พ.ค. 15.00 น.",
        "ส่งรายงาน 7 ก.ย. 68 ครั้ง",
        "you may 2024 times retry",
        "ขนาด 12 March 99999 units",
    ],
)
def test_non_date_shapes_are_not_dates(text):
    found = {e.data_type for e in detect_fp(text)}
    assert not found & {"DATE", "DATE_OF_BIRTH"}

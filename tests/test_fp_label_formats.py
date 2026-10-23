"""Labelled student IDs, spaced passports and hyphenated plates.

Recall campaign, 2026-10-24: student IDs grouped with dashes or spaces, short
school pupil numbers, passports written "AB 1234567" and plates written
"กข-4471", "7หล-3332" or as numeric truck plates "70-4418" were left readable.
"""

import pytest

from pii_redactor.detectors.fp_detector import detect_fp


def _covered(text: str, value: str, etype: str) -> bool:
    start = text.index(value)
    chars = [k for k in range(start, start + len(value)) if text[k].isalnum()]
    spans = [e.span for e in detect_fp(text) if e.data_type == etype]
    return all(any(s <= k < t for s, t in spans) for k in chars)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("รหัสนักศึกษา 67-102-1015 คณะวิทยาศาสตร์", "67-102-1015"),
        ("รหัสนักศึกษา 6710 210 157 ชั้นปีที่ 2", "6710 210 157"),
        ("รหัสนักศึกษา 6636012 ชั้นปีที่ 2", "6636012"),
        ("เลขประจำตัวนักเรียน 12345 ชั้น ม.5/2", "12345"),
        ("เลขประจำตัวนักเรียน 5012874 ชั้นมัธยมศึกษาปีที่ 3", "5012874"),
        ("Borrower Student No. 66 0102 1190 has 2 overdue items", "66 0102 1190"),
        ("Student ID: 66 0204 2117\nEmail: a@b.co", "66 0204 2117"),
        ("รหัสนศ. 6810-310-427 ห้อง 4", "6810-310-427"),
    ],
)
def test_labelled_student_ids_of_any_grouping_are_masked(text, value):
    assert _covered(text, value, "STUDENT_ID")


def test_student_label_does_not_swallow_a_date():
    ents = detect_fp("รหัสนักศึกษา วันที่ 01-02-2568 ยื่นคำร้อง")
    assert not any(e.data_type == "STUDENT_ID" for e in ents)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("หนังสือเดินทางเลขที่ AB 1234568", "AB 1234568"),
        ("| Mr. Marco Fitzgerald | AA 7843804 | 0812345678", "AA 7843804"),
    ],
)
def test_spaced_passports_are_masked(text, value):
    assert _covered(text, value, "PASSPORT")


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("ทะเบียนรถ กข-4471 รถกระบะ", "กข-4471"),
        ("นำรถกระบะทะเบียน 3มก-7686 มาจอด", "3มก-7686"),
        ("ขับรถบรรทุกทะเบียน 70-4418 กรุงเทพมหานคร", "70-4418"),
        ("| น.ส.ละออง ขวัญประเสริฐ | 7หล-3332 | 0812345678", "7หล-3332"),
    ],
)
def test_hyphenated_and_numeric_plates_are_masked(text, value):
    assert _covered(text, value, "VEHICLE_PLATE")


def test_uncued_numeric_pair_is_not_a_plate():
    assert not any(e.data_type == "VEHICLE_PLATE" for e in detect_fp("ห้อง 70-4418 ชั้น 3"))

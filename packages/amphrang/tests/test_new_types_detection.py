"""Detection contract for the five types added 2026-08-26 (see the spec ADR)."""

import pytest

from amphrang.engine.detectors.fp_detector import detect_fp, is_valid_juristic_id


def _types(text):
    return {(e.data_type, e.original_text) for e in detect_fp(text)}


# The eight real, public registration numbers verified 8/8 in the spec ADR.
_JURISTIC_VECTORS = [
    "0107544000108",
    "0107537000114",
    "0107536000315",
    "0107536000102",
    "0107542000011",
    "0107535000265",
    "0107545000292",
    "0505532001265",
]


@pytest.mark.parametrize("value", _JURISTIC_VECTORS)
def test_juristic_checksum_accepts_real_registration_numbers(value):
    assert is_valid_juristic_id(value)


def test_juristic_checksum_rejects_mutation_and_citizen_id():
    assert not is_valid_juristic_id("0107544000107")  # last digit mutated
    assert not is_valid_juristic_id("1101700230708")  # 1-leading citizen id
    assert is_valid_juristic_id("0-1075-36000-10-2")  # separators stripped first


# JURISTIC_ID — use a checksum-VALID number from Task 1's vectors if verified,
# else any 0-leading 13-digit value with the cue.
def test_juristic_id_with_cue_detected():
    found = _types("เลขทะเบียนนิติบุคคล 0107536000102 ของบริษัทจดทะเบียน")
    assert ("JURISTIC_ID", "0107536000102") in found


def test_juristic_dashed_form_detected():
    found = _types("เลขประจำตัวผู้เสียภาษี 0-1075-36000-10-2 ตามหนังสือรับรอง")
    assert any(t == "JURISTIC_ID" for t, _ in found)


def test_thai_id_never_becomes_juristic():
    # a checksum-valid citizen id with a citizen cue must stay THAI_ID
    found = _types("เลขบัตรประชาชน 1101700230708")
    assert ("THAI_ID", "1101700230708") in found
    assert not any(t == "JURISTIC_ID" for t, _ in found)


def test_zero_leading_id_without_juristic_cue_stays_thai_id():
    # 0-leading checksum-valid runs are ambiguous (stateless-person ids exist);
    # without a juristic cue the personal label wins — recall-safe default.
    found = _types("เลขประจำตัว 0107536000102 ของผู้ยื่นคำร้อง")
    assert any(t == "THAI_ID" for t, _ in found)
    assert not any(t == "JURISTIC_ID" for t, _ in found)


def test_driver_license_with_cue_detected():
    found = _types("ใบขับขี่เลขที่ 63012345 ออกโดยกรมการขนส่งทางบก")
    assert ("DRIVER_LICENSE", "63012345") in found


def test_bare_8_digits_without_cue_is_not_driver_license():
    found = _types("เอกสารอ้างอิง 63012345 ลงวันที่วันนี้")
    assert not any(t == "DRIVER_LICENSE" for t, _ in found)


def test_driver_vs_student_nearest_cue_wins():
    found = _types("รหัสนักศึกษา 63012345 และใบขับขี่ 71234568 ของนักศึกษาคนเดียวกัน")
    assert ("DRIVER_LICENSE", "71234568") in found
    assert ("STUDENT_ID", "63012345") in found


def test_line_id_after_cue_detected():
    found = _types("ติดต่อทาง LINE ID @somchai_j99 ได้เลย")
    assert ("LINE_ID", "@somchai_j99") in found


def test_line_word_without_id_value_is_clean():
    assert not any(t == "LINE_ID" for t, _ in _types("เดินข้ามเส้น line กลางถนน"))


def test_gps_pair_detected_without_cue():
    found = _types("จุดนัดพบ 13.7563, 100.5018 หน้าตึก")
    assert ("GPS_COORD", "13.7563, 100.5018") in found


def test_money_pair_with_two_decimals_is_not_gps():
    assert not any(t == "GPS_COORD" for t, _ in _types("ราคา 12.50, 100.75 บาท"))


def test_house_reg_with_cue_detected():
    found = _types("เลขรหัสประจำบ้าน 10240012345 ตามทะเบียนบ้าน")
    assert ("HOUSE_REG_ID", "10240012345") in found


def test_bare_11_digits_without_cue_not_house_reg():
    assert not any(t == "HOUSE_REG_ID" for t, _ in _types("รายการเลขที่ 10240012345"))

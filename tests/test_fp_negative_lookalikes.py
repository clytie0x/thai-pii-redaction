"""Government look-alikes that are not personal data (dev negatives 2026-10-24)."""

import pytest

from pii_redactor.detectors.fp_detector import detect_fp


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("โปรโมชันเดือนตุลาคม ลด 30% ทุกรายการ", "VEHICLE_PLATE"),
        ("แผนงานระยะเวลา รอบ 6 เดือน", "VEHICLE_PLATE"),
        ("รหัสบัญชี 5101020102 ค่าตอบแทน", "BANK_ACCOUNT"),
        ("โครงการก่อสร้างถนนคอนกรีตเสริมเหล็ก งบประมาณ 500,000 บาท", "ADDRESS"),
        ("ปรับปรุงถนนลาดยางแอสฟัลต์ติกคอนกรีต ความยาว 400 เมตร", "ADDRESS"),
        ("ระยะร่นจากแนวเขตที่ดินไม่น้อยกว่า 6 เมตร", "ADDRESS"),
    ],
)
def test_lookalike_is_not_flagged(text, kind):
    assert not any(e.data_type == kind for e in detect_fp(text))


def test_a_real_road_address_is_still_masked():
    ents = detect_fp("ที่อยู่ 88 ถนนสุขุมวิท แขวงคลองตัน")
    assert any(e.data_type == "ADDRESS" and "สุขุมวิท" in e.original_text for e in ents)


def test_a_real_bank_account_after_the_word_account_is_still_masked():
    ents = detect_fp("เลขที่บัญชี 123-4-56789-0 ธนาคารกรุงไทย")
    assert any(e.data_type == "BANK_ACCOUNT" for e in ents)

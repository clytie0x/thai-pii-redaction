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


@pytest.mark.parametrize(
    "text",
    [
        "ประกาศสำนักงานบริหารงานทั่วไปจังหวัดลำปาง เรื่อง กำหนดช่วงเวลา",
        "ส่วนราชการ ศูนย์บริการร่วมจังหวัดนครสวรรค์ ที่ ศบร. 38/2569",
        "ตารางเปิดให้บริการห้องสมุดชุมชน จังหวัดมหาสารคาม ช่วงวันที่ 1-30",
    ],
)
def test_a_province_standing_alone_is_not_an_address(text):
    # A province alone is a quasi-identifier, not a locatable address
    # (annotation guidelines); agency names are full of them.
    assert not any(e.data_type == "ADDRESS" for e in detect_fp(text))


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("ที่อยู่ 12 หมู่ 3 ตำบลบ้านโคก อำเภอเมืองจังหวัดขอนแก่น", "ขอนแก่น"),
        ("ภูมิลำเนา อ.เมือง จ.ขอนแก่น", "ขอนแก่น"),
    ],
)
def test_a_province_inside_an_address_chain_is_kept(text, value):
    ents = detect_fp(text)
    assert any(e.data_type == "ADDRESS" and value in e.original_text for e in ents)


@pytest.mark.parametrize(
    "text",
    [
        "เอกสารเบิกจ่ายต้องมีใบตรวจรับ แบบ บก-07 และหลักฐานราคา",
        "ตีเส้นจราจรตามแบบ รท-27 วงเงินงบประมาณ 3,480,000 บาท",
        "เมื่อจบรอบ รอ 15 นาทีจึงเปิดประตู",
    ],
)
def test_form_codes_and_durations_are_not_plates(text):
    assert not any(e.data_type == "VEHICLE_PLATE" for e in detect_fp(text))


def test_a_real_road_address_is_still_masked():
    ents = detect_fp("ที่อยู่ 88 ถนนสุขุมวิท แขวงคลองตัน")
    assert any(e.data_type == "ADDRESS" and "สุขุมวิท" in e.original_text for e in ents)


def test_a_real_bank_account_after_the_word_account_is_still_masked():
    ents = detect_fp("เลขที่บัญชี 123-4-56789-0 ธนาคารกรุงไทย")
    assert any(e.data_type == "BANK_ACCOUNT" for e in ents)

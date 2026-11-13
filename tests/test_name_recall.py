"""Names the thainer CRF leaves untagged: Latin script and untitled Thai names.

Every sentence here is invented for this file and every person is synthetic.
The negative controls are the look-alikes each rule must leave alone:
company, place, product and brand names, job titles, shared mailboxes, and
ordinary capitalised English.
"""

from __future__ import annotations

import pytest

from pii_redactor.detectors.aggregate import detect_all
from pii_redactor.detectors.name_recall import detect_name_recall


def names(text: str) -> set[str]:
    """NAME spans from the full product path."""
    return {e.original_text for e in detect_all(text) if e.data_type == "NAME"}


def recall_names(text: str) -> set[str]:
    """Spans from the new passes alone, so a control cannot pass by luck."""
    return {e.original_text for e in detect_name_recall(text)}


# ── Latin names after a label that says a person follows ───────────────────


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("ใบยืนยันห้องพัก\nGuest name: Wanchai Thongdee\nRoom 1204", "Wanchai Thongdee"),
        ("Name (as in passport): Nipaporn Saelim\nสัญชาติ ไทย", "Nipaporn Saelim"),
        ("Surname/Given name ARTHIT BUAKAEW\nNationality THAI", "ARTHIT BUAKAEW"),
        ("Name – Surname Kamonwan Rattanakul\nเพศ หญิง", "Kamonwan Rattanakul"),
        ("ส่งเอกสารแล้ว Applicant: Preecha Yodrak / โทร 02-555-0147", "Preecha Yodrak"),
        ("Insured person Suda Meesuk\nแผนประกัน เดินทางรายปี", "Suda Meesuk"),
        ("Passenger 2: Wanchai Thongdee ที่นั่ง 14C", "Wanchai Thongdee"),
        ("ผู้เข้าพัก ๒: Nipaporn Saelim เช็กอินเวลาบ่ายสอง", "Nipaporn Saelim"),
        ("ชื่อบนบัตร (ภาษาอังกฤษ): Arthit Buakaew", "Arthit Buakaew"),
        ("รบกวนพิมพ์ชื่อบนตั๋วว่า Kamonwan Rattanakul ให้ด้วยนะคะ", "Kamonwan Rattanakul"),
        ("เรียน คุณ Preecha Yodrak ตามที่นัดหมายไว้", "Preecha Yodrak"),
        ("Dear Suda Meesuk,\nขอบคุณที่ใช้บริการ", "Suda Meesuk"),
        ("หมอที่ดูแลคือ Dr. Wanchai Thongdee ประจำวันพุธ", "Wanchai Thongdee"),
    ],
)
def test_latin_name_after_a_person_label(text: str, name: str) -> None:
    assert name in names(text)


def test_latin_name_in_a_table_row_before_a_personal_email() -> None:
    text = (
        "รายชื่อผู้ติดต่อ\n"
        "Nipaporn Saelim — n.saelim@example.com — ฝ่ายบัญชี\n"
        "2. Arthit Buakaew | arthit.b@example.org"
    )
    assert {"Nipaporn Saelim", "Arthit Buakaew"} <= names(text)


@pytest.mark.parametrize(
    "text",
    [
        "Company name: Siam Orchid Trading",
        "Hotel name: Golden Lotus Resort",
        "Product name: Jasmine Gold Rice",
        "ชื่อบริษัทภาษาอังกฤษ Blue Mango Studio",
        "ตั้งชื่อโครงการว่า Green Valley Residence",
        "แบรนด์ชื่อดัง Royal Orchid เปิดสาขาใหม่ที่เชียงใหม่",
        "ทีมเราใช้ Google Sheets กับ Microsoft Teams ทุกวัน",
        "ตำแหน่ง Senior Accountant ประจำสาขา Chiang Mai",
        "Please Note that the office is closed on Monday.",
        "Thank You for your order. Best Regards",
        "Customer Support — help@example.com",
        "Blue Mango — info@example.com",
        "Driver License Number 12345678",
        "Contact: Sales Team",
        "Guest: Standard Room",
        "Dear Customer Service,",
        "ผู้ผลิต: Siam Orchid Foods",
        "ผู้ให้บริการ: True Fibre Online",
        "ลูกค้าย้ายไปใช้ Toyota Hilux กับ Honda Civic แล้ว",
        "The Guest House on Sukhumvit Road is full.",
    ],
)
def test_latin_look_alikes_stay_unflagged(text: str) -> None:
    assert recall_names(text) == set()


# ── Thai names by word list ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("ช่วงบ่ายให้ สุดารัตน์ ทองดี ไปรับเอกสารที่สำนักงานเขต", "สุดารัตน์ ทองดี"),
        ("รถกระบะคันนั้นขับโดย วีรชัย แสงทอง เมื่อคืนวันศุกร์", "วีรชัย แสงทอง"),
        ("ยอดค้างชำระงวดนี้เป็นของ นงลักษณ์ บุญมา ทั้งหมด", "นงลักษณ์ บุญมา"),
        ("พยานอีกคนคือ ศิริชัย ทองสุข ซึ่งอยู่ในเหตุการณ์", "ศิริชัย ทองสุข"),
        # The family name is not in the list; ชื่อ before the pair vouches for it.
        ("ช่างที่มาซ่อมแอร์ชื่อ วรวุฒิ พรมแดง นัดไว้วันเสาร์", "วรวุฒิ พรมแดง"),
    ],
)
def test_untitled_thai_name_is_found(text: str, name: str) -> None:
    # The new pass finds the exact name. The product output covers it; the
    # CRF may own a wider span there, and a wider span is never replaced.
    assert name in recall_names(text)
    assert any(name in found for found in names(text))


@pytest.mark.parametrize(
    "text",
    [
        # Both words are in the name lists, and both are everyday Thai.
        "กำไร สุทธิ ไตรมาสสาม",
        "ผล รักษา เป็นที่น่าพอใจ",
        "ยอด สุทธิ หลังหักส่วนลด",
        # One word is a listed name, the other is not.
        "ประเภท บัญชี ออมทรัพย์",
        "บริษัท มั่นคง จำกัด",
        "จังหวัด เชียงใหม่",
        "ราคา พิเศษ เฉพาะสมาชิก",
        "ร้านชื่อ ครัวคุณยาย อยู่ปากซอย",
        "กรุณา ติดต่อ เจ้าหน้าที่",
    ],
)
def test_thai_word_pairs_stay_unflagged(text: str) -> None:
    assert recall_names(text) == set()


# ── the new spans only add coverage ───────────────────────────────────────


def test_new_spans_never_replace_an_older_span() -> None:
    # The cue pass already owns this name. The new pass must add nothing.
    text = "นางสาว สุดารัตน์ ทองดี มารับบัตรแล้ว"
    found = [e for e in detect_all(text) if e.data_type == "NAME"]
    assert len(found) == 1
    assert "สุดารัตน์ ทองดี" in found[0].original_text

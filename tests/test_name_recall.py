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


# ── spaced ordinary Thai is not a name ─────────────────────────────────────

_ORDINARY_SPACED_THAI = [
    # Pairs where the first word is also an everyday word.
    "ประเภท ออมทรัพย์",
    "กำไร เพิ่มขึ้น 12% จากปีก่อน",
    "ผล เพิ่มขึ้น ต่อเนื่อง",
    "คะแนน ปานกลาง",
    "คุณภาพ ปานกลาง",
    "กุหลาบ สีแดง ช่อละ 350 บาท",
    "ต้มยำ กุ้ง ปลาทอง ผัดไทย",
    "ตะวัน ส่องแสง ยามเช้า",
    "ดวงจันทร์ ส่องสว่าง",
    # Place names and wishes written with a space.
    "อุดร ธานี หนองคาย",
    "อุทัย ธานี และ ชัยนาท",
    "สาขา อุทัย ธานี โทร 02-000-0000",
    "สาทร ธานี อาคาร 2",
    "ขอให้ สมหวัง สมใจ",
    "โชคดี มีชัย ตลอดปี",
    # Menus, headers, headlines, product attributes, greetings.
    "ข้าว ผัดกะเพรา ไข่ดาว",
    "ส้มตำ ไทย ปูปลาร้า",
    "กาแฟ เย็น หวานน้อย",
    "ชา เขียว ไม่ใส่น้ำแข็ง",
    "รายการ สินค้า คงเหลือ",
    "ยอด ขาย รวม",
    "ค่า ธรรมเนียม ธนาคาร",
    "อัตรา ดอกเบี้ย สูงสุด",
    "ข่าว ด่วน วันนี้",
    "เศรษฐกิจ ไทย ฟื้นตัว",
    "หุ้น ไทย ปิดบวก",
    "ราคา ทอง ปรับขึ้น",
    "น้ำมัน ดีเซล ลดราคา",
    "สี ขาว ไซส์ L",
    "วัสดุ ผ้า ฝ้าย",
    "น้ำหนัก สุทธิ 500 กรัม",
    "ขนาด ใหญ่ พิเศษ",
    "รสชาติ เข้มข้น ถูกปาก",
    "สวัสดี ปีใหม่ ครับ",
    "ขอบคุณ ครับ ผม",
    "ยินดี ต้อนรับ สู่เชียงใหม่",
    "อวยพร ปีใหม่ สุขสันต์",
    "เชียงราย เมือง งาม",
    "นครปฐม เมือง เก่า",
    "ประจวบ คีรีขันธ์ หัวหิน",
    "สมุทร ปราการ บางพลี",
    "สมุทร สาคร มหาชัย",
    "พระ นคร ศรีอยุธยา",
    "บาง กะปิ ห้วยขวาง",
    "แสง จันทร์ ส่องฟ้า",
    "เงิน เดือน ขึ้น ปีหน้า",
    "สุขภาพ ดี ทุกวัน",
    "บ้าน สวย ราคาถูก",
    "ห้อง พัก รายวัน",
    "เวลา ทำการ จันทร์ ถึง ศุกร์",
    "กำหนด ส่ง งาน พรุ่งนี้",
    "ประกาศ ผล สอบ",
    "คะแนน เฉลี่ย สูงสุด",
    "ผลงาน ดีเด่น ประจำปี",
    "เทศกาล ลอยกระทง งาม",
    "ดอกไม้ สด ช่อละ 200",
]


@pytest.mark.parametrize("text", _ORDINARY_SPACED_THAI)
def test_ordinary_spaced_thai_is_not_a_name(text: str) -> None:
    assert recall_names(text) == set()


@pytest.mark.parametrize(
    "text",
    [
        "คะแนน ปานกลาง",
        "ดวงจันทร์ ส่องสว่าง เต็มดวง",
        "อุทัย ธานี และ ชัยนาท",
        "ขอให้ สมหวัง สมใจ",
    ],
)
def test_ordinary_spaced_thai_is_not_a_name_in_the_product(text: str) -> None:
    assert "NAME" not in {e.data_type for e in detect_all(text)}


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("ให้ สมชาย ใจดี มารับของที่เคาน์เตอร์", "สมชาย ใจดี"),
        ("ส่งพัสดุถึง กาญจนา แก้วมณี ภายในวันศุกร์", "กาญจนา แก้วมณี"),
        ("ผู้ขับขี่คือ ธนากร วงศ์สวัสดิ์ ตามที่แจ้งไว้", "ธนากร วงศ์สวัสดิ์"),
        ("เอกสารฉบับนี้ของ ปิยะพงษ์ สุขสวัสดิ์ ครบแล้ว", "ปิยะพงษ์ สุขสวัสดิ์"),
        ("ติดต่อ อรุณี จันทร์เพ็ญ ได้ทุกวัน", "อรุณี จันทร์เพ็ญ"),
        ("แพทย์ผู้ตรวจคือ สุชาติ มั่นคง เมื่อเช้า", "สุชาติ มั่นคง"),
        ("เจ้าของรถคือ ประยุทธ แสนสุข ตามเล่ม", "ประยุทธ แสนสุข"),
        ("ผู้สมัครคือ อนุชา ทับทิม ครบถ้วน", "อนุชา ทับทิม"),
        ("บัญชีนี้เปิดโดย รัตนา สิงห์ทอง เมื่อปีก่อน", "รัตนา สิงห์ทอง"),
        ("ยืนยันตัวตน พิชิต ทองสุข แล้ว", "พิชิต ทองสุข"),
        ("พนักงานขายชื่อ จิราพร วงศ์ใหญ่ ประจำสาขา", "จิราพร วงศ์ใหญ่"),
        ("ขอสายตรงถึง พัชรี ดวงแก้ว หน่อย", "พัชรี ดวงแก้ว"),
        ("ผู้ป่วยรายนี้ชื่อ ทิพวรรณ ศรีวงษ์ อายุ 45", "ทิพวรรณ ศรีวงษ์"),
        ("พี่ชายของฉันคือ อดิศักดิ์ ทองคำ", "อดิศักดิ์ ทองคำ"),
        # Name evidence in front keeps a pair whose words are everyday.
        ("ลูกค้าชื่อ สมหวัง สมใจ มารับสินค้า", "สมหวัง สมใจ"),
        ("คุณ ประเสริฐ ศรีสุข ได้รับอนุมัติแล้ว", "ประเสริฐ ศรีสุข"),
    ],
)
def test_untitled_thai_names_survive_the_everyday_word_guard(text: str, name: str) -> None:
    assert name in recall_names(text)


# ── a recall span never displaces another layer's span ────────────────────


def test_recall_span_never_displaces_or_shortens_an_existing_span() -> None:
    text = "ดวงจันทร์ ส่องสว่าง เต็มดวง"
    found = detect_all(text)
    assert not any(e.data_type == "NAME" for e in found)
    # The earlier span keeps its label and its full extent.
    assert any(e.data_type == "LOCATION" and e.original_text == "ดวงจันทร์" for e in found)


def test_overlapping_recall_candidates_are_dropped_at_the_call_site() -> None:
    from pii_redactor.detectors.name_context import _make_name
    from pii_redactor.detectors.tb_detector import _without_overlap

    text = "ดวงจันทร์ ส่องสว่าง เต็มดวง"
    existing = [_make_name(text, 9 + 1, 19, 0.9)]  # a span starting inside the pair
    earlier = _make_name(text, 0, 19, 0.84)
    apart = _make_name(text, 20, 26, 0.84)
    assert _without_overlap([earlier, apart], existing) == [apart]
    assert _without_overlap([earlier], []) == [earlier]

"""Name shapes the dev set showed leaking in full, 2026-10-24.

Recall campaign, names: role words with no title in front of the name
(ผู้ร้อง, ผู้เช่าซื้อ, ผู้รับ, ผู้ประสานงาน, พนักงานขับรถ, คู่กรณี), the
transfer-slip and letter lines (ไปยัง, เรียน, ชื่อ after an account number),
Latin-script names after English cues, police/military ranks and
medical/academic titles written glued or spaced, and rosters that keep the
title, first name and surname in separate table cells. The positive cases
use the same shapes with different people; the negative controls are the
prose each new cue could misfire on.
"""

from __future__ import annotations

import pytest

from pii_redactor.detectors.aggregate import detect_all
from pii_redactor.detectors.name_context import detect_name_context


def ctx_names(text: str) -> set[str]:
    return {e.original_text for e in detect_name_context(text)}


def _masked_as_name(text: str, value: str, entities) -> bool:
    start = text.index(value)
    chars = [k for k in range(start, start + len(value)) if text[k].isalnum()]
    spans = [e.span for e in entities if e.data_type == "NAME"]
    return all(any(s <= k < t for s, t in spans) for k in chars)


# ── role words with no title ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, name",
    [
        ("คำร้องขอคืนเงิน\nผู้ร้อง วิไลวรรณ ศรีสุข โทร 089 112 3344", "วิไลวรรณ ศรีสุข"),
        ("ผู้เช่าซื้อ ประภัสสร ทองคำ วันเกิด 02/03/2530", "ประภัสสร ทองคำ"),
        ("ผู้โอน สมศรี ใจงาม\nผู้รับ ณัฐวุฒิ แก้วกาญจนา บัญชีปลายทาง", "ณัฐวุฒิ แก้วกาญจนา"),
        ("ผู้ประสานงาน กัลยา บุญประเสริฐ finance@example.ac.th", "กัลยา บุญประเสริฐ"),
        ("ใบกำกับสินค้า พนักงานขับรถ ไพโรจน์ ศรีวงศ์ เลขใบขับขี่", "ไพโรจน์ ศรีวงศ์"),
        ("ข้าพเจ้า นพ.ธีระ ใจดี ได้ตรวจ สุดารัตน์ พรหมสุวรรณ เกิด 2540", "สุดารัตน์ พรหมสุวรรณ"),
    ],
)
def test_untitled_role_words_introduce_names(text, name):
    assert name in ctx_names(text), text


def test_party_letter_after_counterparty_cue():
    # "คู่กรณีฝ่าย ข. <name>" -- the party letter sits between cue and name.
    text = "คู่กรณีฝ่าย ข. อารีรัตน์ ทองสุข รถทะเบียน 1กข 2345"
    assert "อารีรัตน์ ทองสุข" in ctx_names(text)


def test_transfer_slip_destination_line():
    text = "จาก มานพ ศรีทอง บัญชี 123-4-56789-0\nไปยัง ชุติมา แสงทอง พร้อมเพย์ 0812345678"
    assert "ชุติมา แสงทอง" in ctx_names(text)


@pytest.mark.parametrize(
    "text, name",
    [
        ("บ/ช ธ.ก.ส. 012345678901 ชื่อ จิราพร หาญณรงค์", "จิราพร หาญณรงค์"),
        ("พร้อมเพย์ 081-234-5678 ชื่อ ธนพล วงศ์ใหญ่", "ธนพล วงศ์ใหญ่"),
    ],
)
def test_account_holder_name_after_number(text, name):
    assert name in ctx_names(text)


def test_letter_salutation_names_the_reader():
    text = "แจ้งคืนเงินมัดจำ\nเรียน อรวรรณ สมบัติทอง\nโอนคืน 2,000 บาท"
    assert "อรวรรณ สมบัติทอง" in ctx_names(text)


def test_classified_ad_contact_glued_to_name_and_phone():
    text = "ขายบ้าน ติดต่อประยุทธ บุญมีเบอร์ 089 123 4567 ตลอดวัน"
    assert "ประยุทธ บุญมี" in ctx_names(text)


@pytest.mark.parametrize(
    "text",
    [
        "เรียน ผู้ปกครองนักเรียน ทุกท่าน",
        "เรียน ท่านผู้ถือหุ้น บริษัท",
        "เรียน คณะกรรมการ สหกรณ์",
        "โปรดส่งเอกสารไปยัง สำนักงานเขต บางรัก",
        "ผู้รับผิดชอบ โครงการ ฝ่ายบุคคล",
        "ผู้รับ ต้องลงนาม ทุกครั้ง",
        "ติดต่อสอบถาม ฝ่ายบุคคล ได้ทุกวัน",
        "ติดต่อฝ่าย บุคคล ชั้น 3",
        "ห้อง 301 ชื่อ ห้องประชุม ใหญ่",
        "แพทย์ได้ตรวจ แล้ว พบว่า ปกติ",
    ],
)
def test_new_cues_stay_quiet_on_prose(text):
    assert ctx_names(text) == set(), text


# ── Latin-script names after English or Thai cues ─────────────────────────


@pytest.mark.parametrize(
    "text, name",
    [
        ("Credit Card Statement\nCard holder: Wanchai Srisuk\nCard No.", "Wanchai Srisuk"),
        ("Discharge summary\nPatient: Napat Chaiwong  Birth date: 01/02/1990", "Napat Chaiwong"),
        ("Boarding record: passenger Thanawat Somboon, Passport No. K123456", "Thanawat Somboon"),
        ("ใบสมัครงาน ผู้สมัคร Pimchanok Saelee เลขหนังสือเดินทาง", "Pimchanok Saelee"),
        ("ผู้รับ Anucha Wongsa บัญชีปลายทาง 123456789", "Anucha Wongsa"),
    ],
)
def test_latin_names_after_cues(text, name):
    assert name in ctx_names(text), text


def test_borrower_label_before_student_number_is_not_a_name():
    assert ctx_names("Library fine notice. Borrower Student No. 66 0102 1190") == set()


# ── ranks and professional titles ─────────────────────────────────────────


@pytest.mark.parametrize(
    "text, name",
    [
        ("4 พลทหารอนุชา ทองดี 1 4004 95315 94 4 มหาสารคาม", "อนุชา ทองดี"),
        ("1 | จ.ส.ต.สมพร ปานทอง | 3-9021-18271-91-0", "สมพร ปานทอง"),
        ("2 | ด.ต.ชัยวัฒน์ ใจเย็น | 2-9013-30607-16-1", "ชัยวัฒน์ ใจเย็น"),
        ("3 | ส.ต.อ.ประวิทย์ บุญนาค | 3-9019-35338-16-8", "ประวิทย์ บุญนาค"),
        ("พนักงานสอบสวน ร.ต.อ. ธีรวัฒน์ แสงเพชร รับแจ้ง", "ธีรวัฒน์ แสงเพชร"),
        ("ผู้กำกับ พ.ต.อ.วิรัช สุขสวัสดิ์ อนุมัติ", "วิรัช สุขสวัสดิ์"),
        ("รอง ผกก. พ.ต.ท.สมชาย กล้าหาญ ลงนาม", "สมชาย กล้าหาญ"),
        ("ผู้บังคับหมวด ร.อ.ณรงค์ ศักดิ์ดี", "ณรงค์ ศักดิ์ดี"),
        ("ช่างอากาศ จ.อ.ปิยะพงษ์ มีสุข", "ปิยะพงษ์ มีสุข"),
        ("แพทย์ผู้ตรวจ นพ. กิตติ วงศ์สวัสดิ์", "กิตติ วงศ์สวัสดิ์"),
        ("แพทย์ผู้ตรวจ พญ.อรุณี ทองประเสริฐ", "อรุณี ทองประเสริฐ"),
        ("ทันตแพทย์ ทพ.วีระ ชัยมงคล", "วีระ ชัยมงคล"),
        ("อาจารย์ที่ปรึกษา ผศ.ดร.สุภาพร มีชัย", "สุภาพร มีชัย"),
        ("กรรมการ รศ. ประสิทธิ์ เก่งงาน", "ประสิทธิ์ เก่งงาน"),
        ("วิทยากร ดร.มาลินี ศรีอุดม", "มาลินี ศรีอุดม"),
        ("69905701535\tเด็กชายธนา สมบูรณ์ผล\tป่าไผ่วิทยา", "ธนา สมบูรณ์ผล"),
    ],
)
def test_rank_and_professional_titles(text, name):
    names = ctx_names(text)
    assert any(name in n for n in names), (text, names)


@pytest.mark.parametrize(
    "text",
    [
        "ที่อยู่ 12 ม.3 ต.บ้านใหม่ อ.เมือง จ.อุดรธานี",
        "การทางพิเศษ (กทพ.) ประกาศ ปิดถนน ชั่วคราว",
        "ประกาศ ณ วันที่ 1 ต.ค. พ.ศ. 2569 เป็นต้นไป",
        "ทุนสำหรับเด็กชายและครอบครัว ในชุมชน",
    ],
)
def test_rank_titles_need_a_two_group_name(text):
    assert ctx_names(text) == set(), text


def test_rank_wins_over_tambon_reading_of_its_last_letter():
    # "จ.ส.ต.วัฒนา" also reads as ต.วัฒนา (a tambon), and the FP address
    # pattern claims it -- the whole name must still come out masked.
    text = (
        "บัญชีรายชื่อข้าราชการตำรวจ\nลำดับ | ยศ-ชื่อ-สกุล | เลขประจำตัวประชาชน\n"
        "1 | จ.ส.ต.วัฒนา ปานงาม | 3-9021-18271-91-0\n"
        "2 | ส.ต.อ.ประเสริฐ สมบูรณ์นิล | 3-9019-35338-16-8\n"
    )
    ents = detect_all(text)
    assert _masked_as_name(text, "วัฒนา ปานงาม", ents)
    assert _masked_as_name(text, "ประเสริฐ สมบูรณ์นิล", ents)


def test_real_tambon_after_moo_is_still_an_address():
    text = "ที่อยู่ 205 ม.8 ต.วัฒนา อ.สะเดา จ.สงขลา"
    ents = detect_all(text)
    assert not any(e.data_type == "NAME" for e in ents)
    assert any(e.data_type == "ADDRESS" and "วัฒนา" in e.original_text for e in ents)


# ── rosters with title, first name and surname in separate cells ──────────


def test_roster_title_cell_then_name_cells():
    text = (
        "แบบรายงานข้อมูลนักเรียนรายบุคคล\n"
        "ที่ | คำนำหน้า | ชื่อ | นามสกุล | เลขประจำตัวประชาชน\n"
        "1 | เด็กชาย | ภาคิน | ศรีสวัสดิ์ | 1-3426-95376-78-8\n"
        "2 | ด.ญ. | กชกร | แก้วมณี | 5341812276808\n"
    )
    names = ctx_names(text)
    for value in ("ภาคิน", "ศรีสวัสดิ์", "กชกร", "แก้วมณี"):
        assert value in names, (value, names)


def test_title_cell_without_surname_column_keeps_next_cell_unclaimed():
    # No สกุล column in the header: the cell after the first name is a
    # province or a school, not a surname.
    text = "ลำดับ | คำนำหน้า | ชื่อ | จังหวัด\n1 | นาย | สมคิด | ขอนแก่น\n"
    names = ctx_names(text)
    assert "สมคิด" in names
    assert "ขอนแก่น" not in names


# ── surnames newmm splits onto a stop word ────────────────────────────────


@pytest.mark.parametrize(
    "text, name",
    [
        ("แจ้งโอนคืน\nเรียน ธนพร ศรีมา\nโอนคืน 3,000 บาท", "ธนพร ศรีมา"),
        ("5 พลทหารอาหมัด สาและ 5 4021 49236 17 3 นราธิวาส", "อาหมัด สาและ"),
        ("ผู้เช่าซื้อ ประภัสสร ทองมา วันเกิด 02/03/2530", "ประภัสสร ทองมา"),
        ("ผู้ป่วย ชลธิชา ทองอยู่ เลขประจำตัวผู้ป่วย 1234", "ชลธิชา ทองอยู่"),
    ],
)
def test_glued_stop_word_tail_stays_in_the_surname(text, name):
    names = ctx_names(text)
    assert any(name in n for n in names), (text, names)


def test_conjunction_glued_to_a_surname_still_introduces_the_next_person():
    names = ctx_names("ผู้ปกครอง สมชาย ใจดีและ สมศรี รักไทย")
    assert "สมชาย ใจดี" in names, names

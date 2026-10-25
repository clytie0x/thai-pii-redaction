"""More untitled-name cues from the second dev file (2026-10-24).

Lease, lab, referral, arrest and witness paperwork, and English forms and
notes, each named a person with a role word or a labelled field that the
name passes did not know.
"""

import pytest

from pii_redactor.detectors.aggregate import detect_all
from pii_redactor.detectors.name_context import detect_name_context


def _name_covered(text: str, value: str) -> bool:
    start = text.index(value)
    chars = [k for k in range(start, start + len(value)) if text[k].isalnum()]
    spans = [e.span for e in detect_all(text) if e.data_type == "NAME"]
    return all(any(s <= k < t for s, t in spans) for k in chars)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("สัญญาเช่าฉบับนี้ ผู้ให้เช่า มาลินี สมบัติทอง และผู้เช่าตกลงกัน", "มาลินี สมบัติทอง"),
        ("ผู้รายงานผล เกศินี โพธิ์ทอง นักเทคนิคการแพทย์", "เกศินี โพธิ์ทอง"),
        ("แผนกอายุรกรรม\nขอส่งตัว ศิริพร ราชพฤกษ์ เกิดวันที่ 4 ธันวาคม พ.ศ. 2530", "ศิริพร ราชพฤกษ์"),
        ("ได้ตรวจร่างกาย ยุทธนา ราชพฤกษ์ เลขประจำตัวประชาชน", "ยุทธนา ราชพฤกษ์"),
        ("ได้จับกุม ผู้ต้องหา สุรเชษฐ์ พรหมมา เกิด 2 พ.ค. 2527", "สุรเชษฐ์ พรหมมา"),
        ("พยานปากที่ 2 อรรถพล โพธิ์ทอง\nพยานปากที่ 3", "อรรถพล โพธิ์ทอง"),
        ("คู่กรณีฝ่ายที่ 2 พัชราภรณ์ ธรรมรงค์ ขับรถยนต์", "พัชราภรณ์ ธรรมรงค์"),
    ],
)
def test_thai_role_cues(text, value):
    assert _name_covered(text, value)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("Attending physician: Dr. Kamonwan Thongkham", "Kamonwan Thongkham"),
        ("Full name: Wipawee Srisuwan\nDate of birth: 21 Mar 1990", "Wipawee Srisuwan"),
        ("Applicant: Theerapat Phromma Passport No. AC1072594", "Theerapat Phromma"),
        ("Emergency contact: Nattapong Sitthichok, brother.", "Nattapong Sitthichok"),
        ("Customer Suthida Chaimongkol called the support line", "Suthida Chaimongkol"),
        ("Delivery note for Siriporn Homchan: please leave it", "Siriporn Homchan"),
        ("ผู้เช่าห้อง 305 Sasithorn Inkaew ส่งอีเมล", "Sasithorn Inkaew"),
    ],
)
def test_latin_cues(text, value):
    assert _name_covered(text, value)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("Accepted 20 October 2026\nSender: Faridah Saelao\nCollection address", "Faridah Saelao"),
        ("For corrections contact the office.\nRegistrar: Wiyada Suthipong", "Wiyada Suthipong"),
        ("Certified by Patcharee Ruangrit, International Office", "Patcharee Ruangrit"),
        ("Certified copy, signed by holder: Isabel Noor Marelle", "Isabel Noor Marelle"),
    ],
)
def test_english_sender_registrar_and_signature_labels(text, value):
    assert _name_covered(text, value)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (
            "No. | Student code | Student | Programme\n1 | 67124-10583 | Narin Chaiyapruk | Data Science\n",
            "Narin Chaiyapruk",
        ),
        ("ลำดับ | ชื่อ-สกุล | ตำแหน่ง\n1 | บุญทัน ศรีบัว | เหรัญญิก\n", "บุญทัน ศรีบัว"),
    ],
)
def test_untitled_names_in_a_name_column(text, value):
    assert _name_covered(text, value)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("ส่งคืนเงินประกันภายใน 15 วัน\nพยาน อธิป ชูเกียรติ  ลงวันที่ 21 กันยายน 2569", "อธิป ชูเกียรติ"),
        ("อุณหภูมิ 37.2 องศา\nผู้ซักประวัติ วิศรุต นาคคำ นัดติดตามวันที่ 9 ตุลาคม", "วิศรุต นาคคำ"),
        ("เจ้าหน้าที่รับเรื่อง เมธินี รัตนพงษ์  หน้า 1 จาก 1", "เมธินี รัตนพงษ์"),
        ("ผู้รับเรื่อง กาญจนา ศรีสุข วันที่ 3 มีนาคม 2569", "กาญจนา ศรีสุข"),
        ("ชื่อผู้ได้รับอนุญาต Omar Farid Halden\nสัญชาติ", "Omar Farid Halden"),
    ],
)
def test_signature_block_roles_and_person_labels(text, value):
    assert _name_covered(text, value)


def test_minutes_recorder_cue_finds_the_name():
    # Checked on the cue pass alone: end to end, the CRF span "การประชุม
    # จิราภา" starts earlier and wins the overlap (a known dedupe limit).
    names = {e.original_text for e in detect_name_context("ผู้บันทึกการประชุม จิราภา ทองดี")}
    assert "จิราภา ทองดี" in names


@pytest.mark.parametrize(
    "text",
    ["พยานหลักฐานทั้งหมดอยู่ในสำนวน", "พยาน บุคคล ทั้งสองฝ่ายมาให้ถ้อยคำ", "ชื่อโครงการ Smart Farming"],
)
def test_role_and_label_cues_do_not_mint_names_from_prose(text):
    assert not any(e.data_type == "NAME" for e in detect_name_context(text))


def test_a_project_name_column_holds_no_person():
    # Only the cue passes are checked: the CRF has its own view of this row.
    text = "ลำดับ | ชื่อโครงการ | งบประมาณ\n1 | ปรับปรุงถนนลาดยาง สายบ้านนา | 500,000\n"
    assert not any(e.data_type == "NAME" for e in detect_name_context(text))


def test_attendee_lists_continue_past_the_first_name():
    text = "Meeting attendees: Thanakorn Ruangsri (Finance), Sasithorn Panyadee (Legal), and two observers"
    assert _name_covered(text, "Thanakorn Ruangsri")
    assert _name_covered(text, "Sasithorn Panyadee")


@pytest.mark.parametrize(
    "text",
    [
        "Customer Service Center opens at 8.30",
        "Patient Information Form",
        "Dr. Office Hours: Monday",
    ],
)
def test_headings_and_services_are_not_names(text):
    assert not any(e.data_type == "NAME" for e in detect_all(text))

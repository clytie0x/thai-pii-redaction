"""More untitled-name cues from the second dev file (2026-10-24).

Lease, lab, referral, arrest and witness paperwork, and English forms and
notes, each named a person with a role word or a labelled field that the
name passes did not know.
"""

import pytest

from pii_redactor.detectors.aggregate import detect_all


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

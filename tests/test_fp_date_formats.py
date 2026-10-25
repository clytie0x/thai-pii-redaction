"""Birth-date shapes from Thai paperwork (recall campaign, 2026-10-24).

Abbreviated months (ม.ค. ก.พ.), clipped months (มกรา กุมภา), English months,
the "วันที่ ... เดือน ... พ.ศ. ..." form, two-digit Buddhist years and dotted
numeric dates were left readable. Each value must be fully inside a
DATE_OF_BIRTH span when a birth cue precedes it.
"""

import pytest

from pii_redactor.detectors.fp_detector import detect_fp


def _covered(text: str, value: str, etype: str) -> bool:
    start = text.index(value)
    chars = [k for k in range(start, start + len(value)) if text[k].isalnum()]
    spans = [e.span for e in detect_fp(text) if e.data_type == etype]
    return all(any(s <= k < t for s, t in spans) for k in chars)


@pytest.mark.parametrize(
    "value",
    [
        "6 ม.ค. 40",
        "5 ม.ค. 2540",
        "19 ก.พ. พ.ศ. 2520",
        "๒๔ ก.ย. ๒๔๘๕",
        "10 มกรา 2540",
        "24 กุมภา 2485",
        "9 เดือน มกราคม พ.ศ. 2540",
        "11 Jan 1997",
        "14 March 1991",
        "14 Feb 2535",
        "02.02.2505",
        "5 มี.ค. 56",
    ],
)
def test_cued_birth_dates_of_every_documented_shape_are_masked(value):
    text = f"ผู้ยื่นคำร้อง เกิดวันที่ {value} สัญชาติไทย"
    assert _covered(text, value, "DATE_OF_BIRTH")


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("Patient: Chanon P.  Birth date: 03/11/1994", "03/11/1994"),
        ("Born 5 Jan 1997 in Khon Kaen", "5 Jan 1997"),
        ("Birthdate 14 March 1991, nationality Thai", "14 March 1991"),
    ],
)
def test_english_birth_labels_are_birth_cues(text, value):
    assert _covered(text, value, "DATE_OF_BIRTH")


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("D.O.B.12/03/1987 Nationality: Thai", "12/03/1987"),
        ("ว.ด.ป.เกิด.12/03/2530 อายุ 39 ปี", "12/03/2530"),
    ],
)
def test_birth_date_glued_after_an_abbreviation_dot_is_masked(text, value):
    assert _covered(text, value, "DATE_OF_BIRTH")


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("ผู้โดยสาร น.ส.มะลิวัลย์ DOB March 12, 1996 หนังสือเดินทาง", "March 12, 1996"),
        ("Date of birth: Jan 5 1997\nNationality: Thai", "Jan 5 1997"),
    ],
)
def test_month_first_english_birth_dates_are_masked(text, value):
    assert _covered(text, value, "DATE_OF_BIRTH")


def test_month_first_date_without_a_birth_cue_is_a_plain_date():
    ents = detect_fp("Meeting on March 12, 2026 at the district office")
    assert any(e.data_type == "DATE" for e in ents)
    assert not any(e.data_type == "DATE_OF_BIRTH" for e in ents)


@pytest.mark.parametrize(
    "text",
    [
        "ประจำเดือนกันยายน 2568 ทุกหน่วยงาน",
        "ตามมาตรฐาน มอก. 2540-2555",
        "ระหว่างวันที่ 1 เมษายน ถึง 30 เมษายน",
        "ราคา 12.50 บาท",
    ],
)
def test_non_dates_stay_unmasked(text):
    assert not any(e.data_type in ("DATE", "DATE_OF_BIRTH") for e in detect_fp(text))


def test_uncued_date_is_a_plain_date():
    ents = detect_fp("ประชุมวันที่ 5 ม.ค. 2569 ณ ห้องประชุม")
    assert any(e.data_type == "DATE" for e in ents)
    assert not any(e.data_type == "DATE_OF_BIRTH" for e in ents)

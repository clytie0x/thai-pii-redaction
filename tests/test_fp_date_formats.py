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

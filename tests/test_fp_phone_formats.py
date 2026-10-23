"""Phone shapes Thai documents really use (recall campaign, 2026-10-24).

Each case is a documented way Thai paperwork writes a phone number that the
detector used to leave fully readable. The assertion is the redaction one:
every digit of the number sits inside a PHONE span.
"""

import pytest

from pii_redactor.detectors.fp_detector import detect_fp


def _phone_covers(text: str, value: str) -> bool:
    start = text.index(value)
    digits = [k for k in range(start, start + len(value)) if text[k].isalnum()]
    spans = [e.span for e in detect_fp(text) if e.data_type == "PHONE"]
    return all(any(s <= k < t for s, t in spans) for k in digits)


@pytest.mark.parametrize(
    "value",
    [
        "08-1234-5678",
        "(081) 234-5678",
        "+66 (0) 81 234 5678",
        "0066 81 234 5678",
        "๐๘๑-๒๓๔-๕๖๗๘",
        "081.234.5678",
        "081–234–5678",
        "+66 2 123 4567",
        "๐๒-๑๒๓-๔๕๖๗",
    ],
)
def test_documented_phone_shapes_are_fully_masked(value):
    text = f"ติดต่อเจ้าหน้าที่ โทร {value} ในวันทำการ"
    assert _phone_covers(text, value)


@pytest.mark.parametrize(
    "value",
    [
        "088 - 809 - 3765",
        "(+66) 90-392-0616",
        "02-835-5322 ext. 105",
        "038-421145 ต่อ 17",
        "๐๒-๔๓๑-๕๑๑๔ ต่อ ๑๒",
    ],
)
def test_spaced_dashes_bracketed_prefix_and_extensions_are_masked(value):
    text = f"สอบถามเพิ่มเติม {value} ในเวลาราชการ"
    assert _phone_covers(text, value)


def test_bare_66_prefix_needs_a_phone_cue():
    assert _phone_covers("เบอร์มือถือ 66812345678 ค่ะ", "66812345678")
    text = "รหัสนักศึกษา 66101102345 สาขาบัญชี"
    assert not any(e.data_type == "PHONE" for e in detect_fp(text))


@pytest.mark.parametrize(
    "text",
    [
        "ยอดรวม 1.234.567 บาท",
        "อัตรา 0.81 ต่อหน่วย",
        "สายด่วน 1669 ตลอด 24 ชั่วโมง",
    ],
)
def test_amounts_and_hotlines_are_not_phones(text):
    assert not any(e.data_type == "PHONE" for e in detect_fp(text))


def test_original_text_keeps_the_document_digits():
    text = "โทร ๐๘๑-๒๓๔-๕๖๗๘"
    phones = [e for e in detect_fp(text) if e.data_type == "PHONE"]
    assert phones and phones[0].original_text == "๐๘๑-๒๓๔-๕๖๗๘"

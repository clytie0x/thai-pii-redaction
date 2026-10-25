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


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("โทร.0812345678 ในเวลาราชการ", "0812345678"),
        ("Tel.081-234-5678 (office)", "081-234-5678"),
        ("ติดต่อ โทร.02-123-4567 ในวันทำการ", "02-123-4567"),
        ("มือถือ.๐๘๙-๘๗๖-๕๔๓๒", "๐๘๙-๘๗๖-๕๔๓๒"),
    ],
)
def test_phone_glued_after_an_abbreviation_dot_is_masked(text, value):
    # "โทร." and "Tel." end in a dot. Only a dot after a digit is a decimal
    # point that the number must not start behind.
    assert _phone_covers(text, value)


@pytest.mark.parametrize(
    "text",
    [
        "ISBN 0-736-19582-3 ราคา 250 บาท",
        "3      แผนที่กลิ่นของสวนหลังฝน      0-736-19582-3       1",
    ],
)
def test_a_trailing_single_check_digit_is_not_a_phone_grouping(text):
    # ISBN-10 and bank numbers end in one check digit; phones never do.
    assert not any(e.data_type == "PHONE" for e in detect_fp(text))


@pytest.mark.parametrize("value", ["+66 (0) 84 215 2932", "0066 84 301 4970", "084 215 2932"])
def test_a_phone_ending_a_roster_row_stops_at_the_line_break(value):
    # The next row starts with its row number; a phone must not reach into it.
    text = f"3 | Mr. Victor Whitaker | {value}\n4 | Ms. Chloe Petrov | 090-839-8967\n"
    assert _phone_covers(text, value)
    next_row = text.index("\n4") + 1
    assert not any(
        e.data_type == "PHONE" and e.span[0] < next_row < e.span[1] for e in detect_fp(text)
    )


@pytest.mark.parametrize("value", ["+66 81 234 5678", "0812345678", "02 123 4567"])
def test_a_tab_ends_the_phone_cell(value):
    # Tabs separate table cells, never the digits of one number.
    text = f"1\tนางสมศรี ใจดี\t{value}\t1,000.00\n2\tนายสมชาย ใจดี\t0898765432\t600.00\n"
    assert _phone_covers(text, value)
    cell_end = text.index(value) + len(value)
    assert not any(
        e.data_type in ("PHONE", "BANK_ACCOUNT") and e.span[0] < cell_end < e.span[1]
        for e in detect_fp(text)
    )


def test_boxed_phone_digits_still_count():
    assert _phone_covers("โทร 0 8 1 2 3 4 5 6 7 8 (มือถือ)", "0 8 1 2 3 4 5 6 7 8")


def test_a_phone_shape_inside_a_cued_longer_account_is_not_cut_out():
    text = "ธ.ก.ส. บ/ช 086-2-457891-34 ชื่อบัญชี นายคำแพง อินทร์อุทัย"
    start = text.index("086")
    digits = [k for k in range(start, start + 15) if text[k].isdigit()]
    spans = [e.span for e in detect_fp(text) if e.data_type == "BANK_ACCOUNT"]
    assert all(any(s <= k < t for s, t in spans) for k in digits)


def test_digits_after_a_decimal_point_are_not_a_phone():
    assert not any(e.data_type == "PHONE" for e in detect_fp("ค่าที่วัดได้ 3.0812345678 หน่วย"))


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

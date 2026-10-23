"""Values broken across lines by OCR or PDF copy (recall campaign, 2026-10-24).

A number wrapped after a hyphen ("064-307-" / "0653"), an email split before
its "@", a cued passport split after its letters, and labels whose sara am
was split off ("ต าบล", "อ าเภอ") left values readable.
"""

import pytest

from pii_redactor.detectors.aggregate import detect_all
from pii_redactor.detectors.fp_detector import detect_fp


def _uncovered(text: str, value: str, ents) -> str:
    start = text.index(value)
    return "".join(
        text[k]
        for k in range(start, start + len(value))
        if text[k].isalnum() and not any(e.span[0] <= k < e.span[1] for e in ents)
    )


@pytest.mark.parametrize(
    "value",
    [
        "064-307-\n0653",
        "๐๙๒-๙๓๐-\n๙๒๐๐",
        "091-180-\n  2328",
    ],
)
def test_phone_wrapped_after_a_hyphen(value):
    text = f"ติดต่อกลับที่เบอร์ {value} ในวันทำการ"
    assert _uncovered(text, value, detect_fp(text)) == ""


@pytest.mark.parametrize("value", ["579-6-\n31684-2", "702-\n2-21707-5"])
def test_bank_account_wrapped_after_a_hyphen(value):
    text = f"โอนเงินเข้าบัญชีเลขที่ {value} ภายในวันนี้"
    assert _uncovered(text, value, detect_fp(text)) == ""


def test_email_split_before_the_at_sign():
    text = "ส่งเอกสารมาที่ k.wipada\n@example.ac.th ภายในวันศุกร์"
    assert _uncovered(text, "k.wipada\n@example.ac.th", detect_fp(text)) == ""


def test_cued_passport_split_after_its_letters():
    text = "หนังสือเดินทางเลขที่ EL\n1999999 ออกให้ ณ กรุงเทพ"
    assert _uncovered(text, "EL\n1999999", detect_fp(text)) == ""


def test_address_labels_with_split_sara_am():
    value = "ต าบลโคกมะตูม อ าเภอเมืองลพบุรี จังหวัดลพบุรี 15000"
    text = f"ที่อยู่ 12 หมู่ 3 {value}"
    assert _uncovered(text, value, detect_all(text)) in ("", "ตาบลอาเภอ", "ตาบล", "อาเภอ")
    assert "15000" not in _uncovered(text, value, detect_all(text))
    assert "โคกมะตูม" not in _uncovered(text, value, detect_all(text))


def test_two_table_rows_do_not_fuse_without_a_trailing_hyphen():
    text = "โทร 0812345678\n1234 รายการ"
    phones = [e for e in detect_fp(text) if e.data_type == "PHONE"]
    assert phones and all("\n" not in e.original_text for e in phones)

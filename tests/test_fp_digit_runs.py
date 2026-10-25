"""Long identifier runs written the way Thai documents write them.

Recall campaign, 2026-10-24: card numbers of 13-19 digits, Amex 4-6-5
grouping, dotted or doubly spaced groups, bank accounts of 11-15 digits
(GSB, GH Bank, BAAC, TISCO, Kiatnakin) and national IDs grouped by dots or
spaced digit by digit all left digits readable. Every assertion is the
redaction one: each digit of the value is inside a span of the given type.
"""

import pytest

from pii_redactor.detectors.fp_detector import detect_fp

AMEX = "375260181590834"
UNIONPAY_19 = "6201661318609139096"
VISA_13 = "4960308246280"
VISA_19 = "4194821993518190939"
MASTERCARD = "5178657975432313"
JCB = "3530948757491181"
ID_5 = "5625276018958"
ID_0 = "0559797114711"
DUAL_13 = "4374847771834"


def _covered(text: str, value: str, etype: str) -> bool:
    start = text.index(value)
    digits = [k for k in range(start, start + len(value)) if text[k].isalnum()]
    spans = [e.span for e in detect_fp(text) if e.data_type == etype]
    return all(any(s <= k < t for s, t in spans) for k in digits)


def _group(value: str, *sizes: int, sep: str = " ") -> str:
    out, i = [], 0
    for n in sizes:
        out.append(value[i : i + n])
        i += n
    return sep.join(out)


@pytest.mark.parametrize(
    "value",
    [
        _group(AMEX, 4, 6, 5),
        _group(AMEX, 4, 6, 5, sep="-"),
        UNIONPAY_19,
        _group(UNIONPAY_19, 4, 4, 4, 4, 3),
        VISA_13,
        _group(VISA_19, 4, 4, 4, 4, 3),
        _group(MASTERCARD, 4, 4, 4, 4, sep="."),
        _group(JCB, 4, 4, 4, 4, sep="  "),
        _group(MASTERCARD, 4, 2, 4, 2, 4),
    ],
)
def test_card_numbers_of_every_documented_shape_are_masked(value):
    text = f"ชำระด้วยบัตรหมายเลข {value} ยอด 1,250 บาท"
    assert _covered(text, value, "CREDIT_CARD")


@pytest.mark.parametrize(
    "value",
    [
        "020123456789",
        "12345678901234",
        "123456789012345",
        "021-30-140079-3",
        "113-8-00805-79589",
        "058 - 22 - 240998 - 1",
        "217 1 954 943",
    ],
)
def test_cued_bank_accounts_of_10_to_15_digits_are_masked(value):
    text = f"โอนเข้าเลขที่บัญชี {value} ภายในวันนี้"
    assert _covered(text, value, "BANK_ACCOUNT")


@pytest.mark.parametrize(
    "value",
    [
        _group(ID_5, 1, 4, 5, 2, 1, sep="."),
        " ".join(ID_0),
        _group(ID_0, 1, 4, 5, 2, 1, sep="  "),
    ],
)
def test_irregularly_grouped_national_ids_are_masked(value):
    text = f"เลขประจำตัวประชาชน {value} ผู้ยื่นคำร้อง"
    assert _covered(text, value, "THAI_ID")


def test_table_columns_split_by_double_spaces_are_classified_separately():
    dotted = _group(ID_5, 1, 4, 5, 2, 1, sep=".")
    text = f"สมจิต เพชรงาม  24 กุมภา 2485  {dotted}  222/54 ถนนเพชรเกษม"
    assert _covered(text, dotted, "THAI_ID")
    text = f"นาง ก ข  ต.ท่าข้าม  {_group(ID_0, 1, 4, 5, 2, 1)}  2569  3.5"
    assert _covered(text, _group(ID_0, 1, 4, 5, 2, 1), "THAI_ID")


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("โอนให้ ธ.ออมสิน | 25986056263335 | ยอด 500", "25986056263335"),
        ("A/C No. 059-02-704553-1 (GSB) please transfer", "059-02-704553-1"),
        ("Account number 10120499276380 Kiatnakin Phatra", "10120499276380"),
        ("บ/ช ธ.ก.ส. 059552598307 ชื่อผู้รับ", "059552598307"),
    ],
)
def test_bank_abbreviations_and_english_cues_count(text, value):
    assert _covered(text, value, "BANK_ACCOUNT")


def test_an_english_bank_cue_beats_student_evidence():
    text = (
        "Student number 66-208-147-39\nRefund account: Government Savings Bank A/C 020145783962.\n"
        "Student correspondence: Phitsanulok"
    )
    assert _covered(text, "020145783962", "BANK_ACCOUNT")


def test_bank_dash_layout_is_an_account_without_a_cue():
    text = "จ.สุราษฎร์ธานี  022-4-0998198-8  3.5"
    assert _covered(text, "022-4-0998198-8", "BANK_ACCOUNT")


def test_cued_id_with_a_mistyped_check_digit_is_still_masked():
    bad = ID_5[:-1] + str((int(ID_5[-1]) + 1) % 10)
    text = f"เลขบัตรประชาชน {bad} ตามสำเนาที่แนบ"
    assert _covered(text, bad, "THAI_ID")


def test_card_after_an_abbreviation_dot_is_masked_whole():
    # The dot closes "no.", it does not start a decimal number; the run used
    # to start mid-number and leave the last group readable.
    value = _group(AMEX, 4, 6, 5)
    text = f"AMEX no.{value} ยอดค้าง 12,345 บาท"
    assert _covered(text, value, "CREDIT_CARD")


def test_cued_account_glued_after_an_abbreviation_dot_is_masked():
    text = "โอนเข้า บ/ช.020123456789 ธ.ออมสิน"
    assert _covered(text, "020123456789", "BANK_ACCOUNT")


def test_card_cue_wins_a_13_digit_number_valid_as_card_and_id():
    # DUAL_13 passes both Luhn and the national-ID check digit.
    text = f"ชำระผ่านบัตรเครดิต {DUAL_13} เรียบร้อยแล้ว"
    assert _covered(text, DUAL_13, "CREDIT_CARD")
    text = f"เลขบัตรประชาชน {DUAL_13} ผู้ยื่นคำร้อง"
    assert _covered(text, DUAL_13, "THAI_ID")


def test_bank_dash_layout_led_by_06_to_09_is_an_account_not_a_phone():
    text = "ค่าจ้าง 12,500 065-3-76137-1"
    assert _covered(text, "065-3-76137-1", "BANK_ACCOUNT")


def test_phone_and_account_one_space_apart_do_not_fuse_into_an_id():
    # "0812345678 065" happens to pass the national-ID check digit.
    text = "นายสมชาย ใจดี 0812345678 065-3-76137-1"
    assert _covered(text, "0812345678", "PHONE")
    assert _covered(text, "065-3-76137-1", "BANK_ACCOUNT")
    assert not any(e.data_type == "THAI_ID" for e in detect_fp(text))


@pytest.mark.parametrize(
    "text",
    [
        "พัสดุเลขที่ 12345678901234 จัดส่งแล้ว",
        "ใบแจ้งหนี้ 2569 0001 0002 0003 ยอด 500 บาท",
        "เลขที่โครงการ 6701 2345 6789 012",
    ],
)
def test_uncued_number_runs_without_checksums_stay_unmasked(text):
    kinds = {e.data_type for e in detect_fp(text)}
    assert not kinds & {"CREDIT_CARD", "BANK_ACCOUNT", "THAI_ID"}

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


def test_cued_id_with_a_mistyped_check_digit_is_still_masked():
    bad = ID_5[:-1] + str((int(ID_5[-1]) + 1) % 10)
    text = f"เลขบัตรประชาชน {bad} ตามสำเนาที่แนบ"
    assert _covered(text, bad, "THAI_ID")


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

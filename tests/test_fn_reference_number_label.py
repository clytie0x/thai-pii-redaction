"""Label of a 13-digit number that fails the national-ID check digit.

The fallback scan keeps such a number masked. It calls it THAI_ID by default,
because one OCR digit error on a real card gives the same shape. When a
document-number word (order, payment code, request number) introduces it, the
honest label is the generic ID_NUMBER. Nothing may become unmasked.
"""

from __future__ import annotations

import pytest

from pii_redactor.detectors.aggregate import detect_all
from pii_redactor.detectors.fn_scanner import scan_fn
from pii_redactor.detectors.thai_id import is_valid_thai_id

# Invented values. Each fails the mod-11 check digit.
BAD_A = "4410933127652"
BAD_B = "9038814465127"
BAD_C = "7715206694831"


def _valid_id(first_twelve: str) -> str:
    total = sum(int(d) * (13 - i) for i, d in enumerate(first_twelve))
    return first_twelve + str((11 - total % 11) % 10)


def _label(text: str, value: str) -> str:
    hits = [e for e in scan_fn(text, []) if e.original_text == value]
    assert len(hits) == 1, [(e.data_type, e.original_text) for e in scan_fn(text, [])]
    assert hits[0].redact_type == "FP"
    return hits[0].data_type


def test_fixture_values_fail_the_check_digit():
    assert not any(is_valid_thai_id(value) for value in (BAD_A, BAD_B, BAD_C))


@pytest.mark.parametrize(
    "text",
    [
        f"หมายเลขคำสั่งซื้อ: {BAD_A}",
        f"ชำระแล้ว เลขที่ใบเสร็จ {BAD_A} ขอบคุณค่ะ",
        f"รหัสชำระเงิน {BAD_A}",
        f"หมายเลขอ้างอิงการชำระ {BAD_A}",
        f"เลขที่คำขอ {BAD_A}",
        f"เลขที่คำร้อง {BAD_A}",
        f"หมายเลขพัสดุ {BAD_A}",
        f"Order ID: {BAD_A}",
        f"Invoice no. {BAD_A}",
        f"booking reference {BAD_A}",
    ],
)
def test_reference_cue_gives_the_generic_label(text):
    assert _label(text, BAD_A) == "ID_NUMBER"


@pytest.mark.parametrize(
    "text",
    [
        # No cue at all: the default stays, as before.
        f"ตัวเลข {BAD_B} อยู่ท้ายหน้า",
        f"her id is {BAD_B} and more",
        # A personal-ID word introduces the number.
        f"เลขบัตรประชาชน {BAD_B}",
        f"เลขประจำตัวประชาชน {BAD_B}",
        f"บัตร ปชช. {BAD_B}",
        f"national id {BAD_B}",
        # A personal taxpayer number is the national ID.
        f"เลขประจำตัวผู้เสียภาษี {BAD_B}",
        f"Tax ID {BAD_B}",
        # The ID word is nearer than the order word.
        f"คำสั่งซื้อของลูกค้า เลขบัตรประชาชน {BAD_B}",
        # The reference word is on another line.
        f"หมายเลขคำสั่งซื้อ\n{BAD_B}",
        # The reference word comes after the number, so it does not introduce it.
        f"{BAD_B} คือเลขที่ลูกค้าแจ้งมา ไม่ใช่หมายเลขคำสั่งซื้อ",
    ],
)
def test_default_and_personal_id_cues_keep_thai_id(text):
    assert _label(text, BAD_B) == "THAI_ID"


def test_reference_cue_must_be_close():
    text = "หมายเลขคำสั่งซื้อของท่านจะแสดงในอีเมลยืนยัน ส่วนตัวเลขที่ลูกค้าแจ้งทางโทรศัพท์คือ " + BAD_C
    assert _label(text, BAD_C) == "THAI_ID"


def test_valid_id_stays_thai_id_after_a_reference_cue():
    # A number that passes the check digit never reaches the fallback.
    value = _valid_id("310090451267")
    assert is_valid_thai_id(value)
    found = [e for e in detect_all(f"หมายเลขคำสั่งซื้อ: {value}") if e.original_text == value]
    assert [e.data_type for e in found] == ["THAI_ID"]


@pytest.mark.parametrize(
    "text",
    [
        f"หมายเลขคำสั่งซื้อ: {BAD_C} สถานะ: รอจัดส่ง",
        f"รหัสชำระเงิน {BAD_C}",
        f"เลขบัตรประชาชน {BAD_C}",
        f"ตัวเลข {BAD_C} อยู่ท้ายหน้า",
    ],
)
def test_the_number_is_masked_under_every_label(text):
    start = text.index(BAD_C)
    covering = [
        e for e in detect_all(text) if e.span[0] <= start and e.span[1] >= start + len(BAD_C)
    ]
    assert covering, "the 13-digit number must stay masked"
    assert covering[0].data_type in {"THAI_ID", "ID_NUMBER"}


def test_relabelled_number_gets_a_digit_surrogate_of_the_same_length():
    from pii_redactor.anonymizer.fp_generator import generate_fp

    fake = generate_fp("ID_NUMBER", BAD_A, salt="test-salt")
    assert fake.isdigit() and len(fake) == len(BAD_A)


def test_one_reference_number_does_not_relabel_a_later_number():
    text = f"หมายเลขคำสั่งซื้อ: {BAD_A}\nตัวเลขอีกชุดหนึ่ง {BAD_B}"
    assert _label(text, BAD_A) == "ID_NUMBER"
    assert _label(text, BAD_B) == "THAI_ID"

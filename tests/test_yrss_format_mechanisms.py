"""New synthetic format probes, authored before detector changes."""

import pytest

from pii_redactor.detectors.fp_detector import _luhn_check, detect_fp


def card(length):
    prefix = "4" + "2" * (length - 2)
    return prefix + next(str(i) for i in range(10) if _luhn_check(prefix + str(i)))


@pytest.mark.parametrize("length", [13, 14, 15, 16])
@pytest.mark.parametrize("separator", ["", " ", "-"])
def test_checksum_valid_card_lengths_have_complete_spans(length, separator):
    digits = card(length)
    value = separator.join(digits[i : i + 4] for i in range(0, length, 4))
    text = "ชำระด้วยบัตรเครดิต " + value + " เรียบร้อย"
    start = text.index(value)
    assert any(
        e.data_type == "CREDIT_CARD" and e.span == (start, start + len(value))
        for e in detect_fp(text)
    )


@pytest.mark.parametrize("length", [13, 14, 15, 16])
def test_bad_card_checksum_is_not_accepted_as_card(length):
    digits = card(length)
    value = digits[:-1] + str((int(digits[-1]) + 1) % 10)
    assert not any(e.data_type == "CREDIT_CARD" for e in detect_fp("บัตรเครดิต " + value))


@pytest.mark.parametrize("value", ["๐๘๑-๒๓๔-๕๖๗๘", "๐๒-๓๔๕-๖๗๘๙", "+๖๖ ๘๑ ๒๓๔ ๕๖๗๘", "๐๗๔-๒๑๓-๕๘๖"])
def test_thai_digit_phones_preserve_original_spans(value):
    text = "โทร " + value + " ค่ะ"
    assert any(
        e.data_type == "PHONE" and e.original_text == value and e.span == (4, 4 + len(value))
        for e in detect_fp(text)
    )


def test_phone_trunk_prefix_cannot_join_unrelated_rows():
    assert not any(e.data_type == "PHONE" for e in detect_fp("ยอดคงเหลือ ๐\n๘๑๒๓๔๕๖๗๘"))


@pytest.mark.parametrize("length", [17, 18, 20])
def test_new_short_card_support_does_not_claim_partial_longer_grouped_code(length):
    digits = card(16) + "7" * (length - 16)
    value = " ".join(digits[i : i + 4] for i in range(0, length, 4))
    assert not any(
        e.data_type == "CREDIT_CARD" and sum(c.isdigit() for c in e.original_text) < 16
        for e in detect_fp("เลขอ้างอิง " + value)
    )


@pytest.mark.parametrize(
    "text",
    [
        "บัตรเครดิต 4222222222222220 100 บาท",
        "บัตรเครดิต 4222222222222220\n100 บาท",
        "ลำดับ 1 4222222222222220",
        "บัตรเครดิต 4222 2222 2222 2220 100 บาท",
    ],
)
def test_existing_card_is_not_lost_next_to_other_numeric_fields(text):
    from pii_redactor.detectors.aggregate import detect_all

    for detector in (detect_fp, detect_all):
        assert any(
            e.data_type == "CREDIT_CARD" and e.original_text.replace(" ", "") == "4222222222222220"
            for e in detector(text)
        )


@pytest.mark.parametrize("value", ["4100122222221", "4-1001-22222-22-1-7", "4100122222221-7"])
def test_card_cue_and_complete_span_win_against_thai_id_collision(value):
    from pii_redactor.detectors.aggregate import detect_all

    text = "บัตรเครดิต " + value
    for detector in (detect_fp, detect_all):
        assert any(
            e.data_type == "CREDIT_CARD" and e.original_text == value for e in detector(text)
        )


def test_personal_id_keeps_its_type_when_checksum_also_passes_luhn():
    assert any(e.data_type == "THAI_ID" for e in detect_fp("เลขบัตรประชาชน 4100122222221"))


def test_uncued_short_luhn_number_does_not_promote_a_corrupted_id_read():
    # An OCR retry appended one digit to a higher-quality valid ID read.
    assert not any(e.data_type == "CREDIT_CARD" for e in detect_fp("11017002307081"))


@pytest.mark.parametrize("mode", ["token", "surrogate"])
@pytest.mark.parametrize("kind", ["card13", "card14", "card15", "thai_phone"])
def test_new_formats_complete_mask_guard_and_restore(mode, kind):
    from pii_redactor.stateless import restore_stateless, sanitize_stateless

    value = "๐๘๑-๒๓๔-๕๖๗๘" if kind == "thai_phone" else card(int(kind[-2:]))
    cue = "โทร " if kind == "thai_phone" else "ชำระด้วยบัตรเครดิต "
    text = cue + value
    masked = sanitize_stateless(text, mode=mode, salt="synthetic-yrss-probe")
    assert value not in masked.sanitized_text
    assert value in masked.mapping.values()
    restored = restore_stateless(masked.sanitized_text, mapping=masked.mapping, mode=mode)
    assert restored.restored_text == text
    assert restored.leftover_pseudonyms == []

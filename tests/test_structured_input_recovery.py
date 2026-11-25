"""Source-preserving input recovery, with exact synthetic value oracles."""

import pytest

from pii_redactor.detectors.aggregate import detect_all
from pii_redactor.stateless import restore_stateless, sanitize_stateless

CASES = [
    ("โทร ", "081\u200b-234-5678", "PHONE"),
    ("เลขบัตรประชาชน ", "1101\ufeff700230708", "THAI_ID"),
    ("อีเมล ", "synthetic.user\u200d@example.com", "EMAIL"),
    ("โทร ", "081  234  5678", "PHONE"),
    ("เลขบัตรประชาชน ", "1101  7002  30708", "THAI_ID"),
    ("IBAN ", "GB82 WEST 1234 5698 7654 32", "IBAN"),
    ("โทร ", "０８１－２３４－５６７８", "PHONE"),
]


@pytest.mark.parametrize("cue,value,label", CASES)
def test_recovery_maps_exact_original_occurrence(cue, value, label):
    text = "🛡 " + cue + value + " จบ"
    start = text.index(value)
    assert any(
        e.data_type == label and e.span == (start, start + len(value)) and e.original_text == value
        for e in detect_all(text)
    )


def _separator_cases():
    import random
    import re

    from pii_redactor.anonymizer import fp_generator as fg

    card = re.sub(r"\D", "", fg._gen_credit_card(random.Random(1)))
    groups = [card[i : i + 4] for i in range(0, 16, 4)]
    cases = []
    # Hyphen, non-breaking hyphen, en dash, minus sign, small hyphen-minus.
    for dash in "‐‑–−﹣":
        cases.append(("บัตรเครดิต ", dash.join(groups), "CREDIT_CARD"))
        cases.append(("โทร ", f"081{dash}234{dash}5678", "PHONE"))
    # No-break, thin, narrow no-break and ideographic space.
    for space in "   　":
        cases.append(("โทร ", f"081{space}234{space}5678", "PHONE"))
        cases.append(("โทร ", f"02{space}618{space}0337", "PHONE"))
    return cases


SEPARATOR_CASES = _separator_cases()


@pytest.mark.parametrize("cue,value,label", SEPARATOR_CASES)
def test_unicode_separators_map_exact_original_occurrence(cue, value, label):
    text = "🛡 " + cue + value + " จบ"
    start = text.index(value)
    assert any(
        e.data_type == label and e.span == (start, start + len(value)) and e.original_text == value
        for e in detect_all(text)
    )


@pytest.mark.parametrize("mode", ["token", "surrogate"])
@pytest.mark.parametrize("cue,value,label", SEPARATOR_CASES)
def test_unicode_separator_inputs_are_masked_and_restore_exactly(mode, cue, value, label):
    text = cue + value + " จบ"
    result = sanitize_stateless(text, mode=mode, salt="synthetic-recovery")
    assert value not in result.sanitized_text
    # An earlier, wider span may own the value; recovery never narrows it.
    assert any(value in original for original in result.mapping.values())
    restored = restore_stateless(result.sanitized_text, mapping=result.mapping, mode=mode)
    assert restored.restored_text == text


@pytest.mark.parametrize("cue,value,label", SEPARATOR_CASES)
def test_unicode_separators_are_also_caught_by_the_release_guard(cue, value, label):
    from pii_redactor.leak_guard import OutboundGuardContext, scan_outbound_leaks

    leaks = scan_outbound_leaks(cue + value + " จบ", OutboundGuardContext())
    assert (label, (len(cue), len(cue) + len(value))) in _spans(leaks)


def _separator_characters():
    import sys
    import unicodedata

    dashes, spaces = ["−"], []
    for code in range(0x80, sys.maxunicode + 1):
        category = unicodedata.category(chr(code))
        if category == "Pd":
            dashes.append(chr(code))
        elif category == "Zs":
            spaces.append(chr(code))
    return dashes, spaces


DASHES, SPACES = _separator_characters()


def _ascii_twin(text):
    return text.translate({**{ord(c): "-" for c in DASHES}, **{ord(c): " " for c in SPACES}})


def _spans(entities):
    return [(e.data_type, e.span) for e in entities]


# One line per behaviour a Unicode separator used to change: cue collisions,
# types outside bounded recovery, signed coordinates, repeated gaps, plain ranges.
TWIN_TEXTS = [
    "เรื่องทั่วไป เลขทะเบียนนิติบุคคล 0–5425–98747–17–3 จบ",
    "ข้อมูล ปชช 1–4505–28559–66–9 ครับ",
    "เรื่องทั่วไป เลขบัตรประชาชน 1–4505–28559–66–9 จบ",
    "ข้อมูล ทะเบียนบัตร 6209–6654–2870–7224 ครับ",
    "ข้อมูล ลงทะเบียนโทร 089–710–2822 ครับ",
    "โอนเงินเข้า 4292–47411–6 ภายในวันนี้",
    "วันที่ 12–03–2567 ประชุม",
    "เกิดวันที่ 12‑03‑2530",
    "MAC address AA‐BB‐CC‐DD‐EE‐FF",
    "พิกัด −13.7563, 100.5018",
    "ยอด 544﹣000 บาท﹣LINE ID user256﹣ขอบคุณ",
    "เรื่องทั่วไป เลขที่บัญชี 429  2  47411  6 จบ",
    "ปีงบประมาณ 2565–2566 หน้า 10–20 ราคา 1,000−2,500 บาท 3 ชิ้น",
    "โทร 081​–234–5678 จบ",
    "โทร ０８１–２３４–５６７８ จบ",
    "เลขที่ 1234–5678–9012",
    "อีเมล frank.4789@mail.example.org—644",
    # Only the guard's single-spaced IBAN view reads this one.
    "IBAN DE31 6773 7319 7686 3353 86 จบ",
]


@pytest.mark.parametrize("text", TWIN_TEXTS)
def test_unicode_separators_detect_what_the_ascii_form_detects_at_source_offsets(text):
    found = detect_all(text)
    assert _spans(found) == _spans(detect_all(_ascii_twin(text)))
    assert all(e.original_text == text[e.span[0] : e.span[1]] for e in found)


@pytest.mark.parametrize("text", TWIN_TEXTS)
def test_plain_detectors_read_unicode_separators_like_the_ascii_form(text):
    from pii_redactor.detectors.fp_detector import detect_fp
    from pii_redactor.detectors.tb_detector import detect_tb

    twin = _ascii_twin(text)
    for detector in (detect_fp, detect_tb):
        found = detector(text)
        assert _spans(found) == _spans(detector(twin))
        assert all(e.original_text == text[e.span[0] : e.span[1]] for e in found)


def _release(text, mode):
    from pii_redactor.stateless import StatelessLeakError

    try:
        result = sanitize_stateless(text, mode=mode, salt="synthetic-recovery")
    except StatelessLeakError:
        return "blocked", None
    return sorted((e["start"], e["end"]) for e in result.entities), result


@pytest.mark.parametrize("mode", ["token", "surrogate"])
@pytest.mark.parametrize("text", TWIN_TEXTS)
def test_unicode_separators_release_or_block_exactly_like_the_ascii_form(mode, text):
    outcome, result = _release(text, mode)
    twin_outcome, twin_result = _release(_ascii_twin(text), mode)
    assert outcome == twin_outcome
    if result is not None:
        if mode == "surrogate":  # same surrogates, so the same released text
            assert _ascii_twin(result.sanitized_text) == twin_result.sanitized_text
        restored = restore_stateless(result.sanitized_text, mapping=result.mapping, mode=mode)
        assert restored.restored_text == text


@pytest.mark.parametrize("text", TWIN_TEXTS)
def test_release_guard_sees_unicode_separators_like_the_ascii_form(text):
    from pii_redactor.leak_guard import (
        OutboundGuardContext,
        scan_outbound_leaks,
        scan_residual_signals,
    )

    twin = _ascii_twin(text)
    context = OutboundGuardContext()
    assert scan_residual_signals(text, context) == scan_residual_signals(twin, context)
    leaks = scan_outbound_leaks(text, context)
    assert _spans(leaks) == _spans(scan_outbound_leaks(twin, context))
    assert all(e.original_text == text[e.span[0] : e.span[1]] for e in leaks)


def test_every_unicode_dash_and_space_separator_is_covered():
    card = SEPARATOR_CASES[0][1].replace("‐", "-")
    # Two spaces between digit groups: only the folded form reaches gap recovery.
    account = "429  2  47411  6"
    expected_card = _spans(detect_all("บัตรเครดิต " + card + " จบ"))
    expected_account = _spans(detect_all("เลขที่บัญชี " + account + " จบ"))
    assert "CREDIT_CARD" in [t for t, _ in expected_card]
    assert "BANK_ACCOUNT" in [t for t, _ in expected_account]
    for dash in DASHES:
        text = "บัตรเครดิต " + card.replace("-", dash) + " จบ"
        assert _spans(detect_all(text)) == expected_card, hex(ord(dash))
    for space in SPACES:
        text = "เลขที่บัญชี " + account.replace(" ", space) + " จบ"
        assert _spans(detect_all(text)) == expected_account, hex(ord(space))


@pytest.mark.parametrize("mode", ["token", "surrogate"])
@pytest.mark.parametrize("cue,value,label", CASES)
def test_recovered_inputs_are_usable_and_restore_exactly(mode, cue, value, label):
    text = cue + value
    result = sanitize_stateless(text, mode=mode, salt="synthetic-recovery")
    assert value not in result.sanitized_text
    assert value in result.mapping.values()
    restored = restore_stateless(result.sanitized_text, mapping=result.mapping, mode=mode)
    assert restored.restored_text == text
    assert restored.leftover_pseudonyms == []


@pytest.mark.parametrize(
    "text", ["ยอด 0\n812345678", "โทร 0\n812345678", "โทร 081\t234\t5678", "ยอด 081  234  5678"]
)
def test_recovery_does_not_join_rows_or_unlabelled_numeric_fields(text):
    from pii_redactor.detectors.structured_views import recover_structured

    assert recover_structured(text) == []


def test_repeated_obfuscated_values_keep_their_own_source_occurrences():
    value = "081\u200b-234-5678"
    text = "โทร " + value + " และโทร " + value
    hits = [e for e in detect_all(text) if e.data_type == "PHONE"]
    assert {e.span for e in hits} == {(4, 4 + len(value)), (text.rindex(value), len(text))}


def test_recovery_cannot_uncover_existing_broader_protection():
    from pii_redactor.detectors.structured_views import admit_recovery
    from pii_redactor.models import Entity

    def entity(start, end, label):
        return Entity("id" + str(start), "FP", label, (start, end), 1.0, "x" * (end - start))

    raw = [entity(0, 12, "ADDRESS")]
    recovered = [entity(3, 10, "PHONE")]
    assert admit_recovery(raw, recovered) == raw


@pytest.mark.parametrize(
    "value,label",
    [
        ("０８１－２３４－５６７８", "PHONE"),
        ("ｓｙｎｔｈｅｔｉｃ＠ｅｘａｍｐｌｅ．ｃｏｍ", "EMAIL"),
        ("ＧＢ８２ ＷＥＳＴ １２３４ ５６９８ ７６５４ ３２", "IBAN"),
    ],
)
def test_width_forms_are_also_caught_by_independent_release_guard(value, label):
    from pii_redactor.leak_guard import OutboundGuardContext, scan_residual_signals

    assert "obfuscated_structured:" + label in scan_residual_signals(value, OutboundGuardContext())


@pytest.mark.parametrize("boundary", ["\r", "\v", "\u0085", "\u2028", "\u2029"])
def test_recovery_treats_unicode_line_boundaries_as_hard_fields(boundary):
    from pii_redactor.detectors.structured_views import recover_structured

    assert recover_structured("โทร ０８１" + boundary + "２３４" + boundary + "５６７８") == []
    assert recover_structured("โทร" + boundary + "081  234  5678") == []


def test_admission_preserves_original_guard_units_even_without_raw_hits():
    from pii_redactor.detectors.structured_views import admit_recovery
    from pii_redactor.models import Entity

    full = Entity("whole", "FP", "IBAN", (0, 20), 1.0, "x" * 20)
    partial = Entity("part", "FP", "PHONE", (5, 15), 1.0, "x" * 10)
    assert admit_recovery([], [partial], required=[full]) == []


@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_combined_obfuscation_cannot_destroy_an_original_guard_signature(mode):
    import random
    import re

    from pii_redactor.anonymizer import fp_generator as fg
    from pii_redactor.stateless import StatelessLeakError

    mobile = re.sub(r"\D", "", fg._gen_phone(random.Random(1)))
    bban = "WEST" + mobile + "0" * 4
    numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in bban + "GB00")
    header = "GB" + str(98 - int(numeric) % 97).zfill(2)
    value = "  ".join([header, "WEST", mobile[:5] + "\u200b" + mobile[5:], "0" * 4])
    text = "IBAN " + value
    try:
        result = sanitize_stateless(text, mode=mode, salt="synthetic-composition")
    except StatelessLeakError:
        return
    covered = {i for e in result.entities for i in range(e["start"], e["end"])}
    assert {i for i in range(5, len(text)) if not text[i].isspace()} <= covered


def test_recovered_source_intervals_select_the_right_pdf_word_boxes():
    from pii_redactor.models import EntityRegistry, WordBbox
    from pii_redactor.redactor import _map_entities_to_boxes

    value = "081\u200b-234-5678"
    text = "โทร " + value + " และโทร " + value
    entities = [e for e in detect_all(text) if e.data_type == "PHONE"]
    boxes = []
    for x, start in enumerate((4, text.rindex(value))):
        box = WordBbox(value, 1, float(x * 100), 10.0, 80.0, 10.0)
        box.source_span = (start, start + len(value))
        boxes.append(box)
    registry = EntityRegistry(entities=entities, fp_count=2, tb_count=0)
    assert _map_entities_to_boxes(registry, boxes) == [[boxes[0]], [boxes[1]]]

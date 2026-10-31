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

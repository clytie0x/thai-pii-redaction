"""Synthetic contracts for the SDK's additional canonical structured types."""

import re
from pathlib import Path

import pytest

from pii_redactor.anonymizer.anonymizer import anonymize
from pii_redactor.anonymizer.fp_generator import generate_fp
from pii_redactor.anonymizer.token_generator import TOKEN_LABEL, is_token_for_data_type
from pii_redactor.detectors.aggregate import detect_all
from pii_redactor.detectors.fp_detector import detect_fp
from pii_redactor.detectors.scan_views import original_guard_entities
from pii_redactor.detectors.thai_id import is_valid_thai_id
from pii_redactor.leak_guard import (
    OutboundGuardContext,
    OutboundPolicyError,
    enforce_outbound_policy,
    scan_obfuscated_structured_entities,
)
from pii_redactor.models import AIResponse, EntityRegistry
from pii_redactor.reverse_mapper import reverse_map
from pii_redactor.scan_common import canonical_value
from pii_redactor.session_vault import SessionVault
from pii_redactor.stateless import restore_stateless, sanitize_stateless


def _synthetic_juristic():
    prefix = "000000042424"
    check = (11 - sum(int(d) * (13 - i) for i, d in enumerate(prefix)) % 11) % 10
    return prefix + str(check)


JURISTIC = _synthetic_juristic()


def test_juristic_private_validator_preserves_checksum_and_type_honesty():
    from pii_redactor.detectors.fp_detector import is_valid_juristic_id

    assert is_valid_juristic_id(JURISTIC)
    assert is_valid_juristic_id(
        f"{JURISTIC[0]}-{JURISTIC[1:5]}-{JURISTIC[5:10]}-{JURISTIC[10:12]}-{JURISTIC[12]}"
    )
    assert not is_valid_juristic_id(JURISTIC[:-1] + str((int(JURISTIC[-1]) + 1) % 10))
    assert not is_valid_juristic_id("1101700230708")


def test_juristic_private_validator_delegates_to_existing_checksum(monkeypatch):
    from pii_redactor.detectors import fp_detector

    calls = []
    monkeypatch.setattr(fp_detector, "is_valid_thai_id", lambda raw: calls.append(raw) or True)
    assert fp_detector.is_valid_juristic_id("0-0000-00000-00-1")
    assert calls == ["0000000000001"]
    assert not fp_detector.is_valid_juristic_id("1-0000-00000-00-1")
    assert calls == ["0000000000001"]


CASES = [
    ("JURISTIC_ID", "ทะเบียนนิติบุคคล ", JURISTIC),
    ("DRIVER_LICENSE", "ใบขับขี่ ", "42424242"),
    ("LINE_ID", "LINE ID: ", "@synthetic_demo"),
    ("GPS_COORD", "พิกัด ", "0.123456, 0.654321"),
    ("HOUSE_REG_ID", "รหัสประจำบ้าน ", "42424242424"),
    ("IP_ADDRESS", "IP ", "192.0.2.17"),
    ("MAC_ADDRESS", "MAC ", "02:42:00:00:00:17"),
    ("LAND_DEED_ID", "โฉนดเลขที่ ", "42424"),
]


def _fullwidth_juristic():
    parts = [JURISTIC[0], JURISTIC[1:5], JURISTIC[5:10], JURISTIC[10:12], JURISTIC[12]]
    return "－".join(parts)


def test_actual_ensemble_keeps_whole_juristic_fullwidth_separator_unit():
    value = _fullwidth_juristic()
    text = "🛡 juristic " + value + " จบ"
    start = text.index(value)
    expected = ("JURISTIC_ID", (start, start + len(value)), value)
    assert expected in [
        (e.data_type, e.span, e.original_text) for e in original_guard_entities(text)
    ]
    assert expected in [(e.data_type, e.span, e.original_text) for e in detect_all(text)]


@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_actual_stateless_roundtrip_keeps_fullwidth_juristic_unit(mode):
    value = _fullwidth_juristic()
    text = "juristic " + value
    result = sanitize_stateless(text, mode=mode, salt="synthetic-source-recovery")
    assert value in result.mapping.values()
    assert result.entity_type_counts == {"JURISTIC_ID": 1}
    assert [(e["data_type"], e["start"], e["end"]) for e in result.entities] == [
        ("JURISTIC_ID", len("juristic "), len(text))
    ]
    enforce_outbound_policy(result.sanitized_text, guard_context=result.guard_context)
    restored = restore_stateless(result.sanitized_text, mapping=result.mapping, mode=mode)
    assert restored.restored_text == text
    assert restored.leftover_pseudonyms == []


def test_repeated_gap_recovery_keeps_juristic_cue_and_hard_boundaries():
    from pii_redactor.detectors.structured_views import recover_structured

    value = JURISTIC[:5] + "  " + JURISTIC[5:]
    text = "juristic " + value
    hits = recover_structured(text)
    assert [(e.data_type, e.span, e.original_text) for e in hits] == [
        ("JURISTIC_ID", (len("juristic "), len(text)), value)
    ]
    assert recover_structured("reference " + value) == []
    for boundary in ("\n", "\r", "\t", "\u0085", "\u2028", "\u2029"):
        assert recover_structured("juristic" + boundary + value) == []
        split = JURISTIC[:5] + boundary + JURISTIC[5:]
        assert recover_structured("juristic " + split) == []


@pytest.mark.parametrize("kind,cue,value", CASES, ids=[row[0] for row in CASES])
@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_actual_ensemble_and_stateless_type_closure(kind, cue, value, mode):
    text = cue + value
    assert any(e.data_type == kind and e.original_text == value for e in detect_all(text))
    result = sanitize_stateless(text, mode=mode, salt="synthetic-type-closure")
    assert result.entity_type_counts.get(kind) == 1
    assert value in result.mapping.values()
    assert value not in result.sanitized_text
    restored = restore_stateless(result.sanitized_text, mapping=result.mapping, mode=mode)
    assert restored.restored_text == text
    assert restored.leftover_pseudonyms == []


@pytest.mark.parametrize("kind,cue,value", CASES, ids=[row[0] for row in CASES])
@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_actual_sdk_facade_type_closure(kind, cue, value, mode, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "packages/amphrang"))
    import amphrang

    text = cue + value
    assert any(e.data_type == kind and e.original_text == value for e in amphrang.detect(text))
    masked = amphrang.anonymize(text, mode=mode, salt="synthetic-facade-closure")
    assert masked.entity_type_counts.get(kind) == 1
    assert value in masked.mapping.values()
    assert value not in masked.text
    restored = amphrang.restore(masked.text, masked.mapping, mode=mode)
    assert restored.text == text
    assert restored.leftover_pseudonyms == []


@pytest.mark.parametrize("kind,cue,value", CASES, ids=[row[0] for row in CASES])
def test_additional_types_preserve_exact_source_span(kind, cue, value):
    text = cue + value + "\nจบ"
    hits = [e for e in detect_fp(text) if e.data_type == kind]
    assert len(hits) == 1
    assert hits[0].span == (len(cue), len(cue) + len(value))
    assert hits[0].original_text == value


@pytest.mark.parametrize("kind,cue,value", CASES, ids=[row[0] for row in CASES])
@pytest.mark.parametrize("style", ["thai", "fullwidth", "zero_width"])
def test_obscured_additional_types_map_back_to_source(kind, cue, value, style):
    if style == "thai":
        obscured = value.translate(str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙"))
    elif style == "fullwidth":
        obscured = "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in value)
    else:
        obscured = "\u200b".join(value)
    text = cue + obscured
    # These scan-only paths fold characters but retain source coordinates.
    scans = [original_guard_entities(text)]
    if style != "thai":
        scans.append(scan_obfuscated_structured_entities(text))
    for hits in scans:
        matches = [e for e in hits if e.data_type == kind]
        assert any(e.span == (len(cue), len(text)) and e.original_text == obscured for e in matches)


@pytest.mark.parametrize(
    "kind,text",
    [
        ("DRIVER_LICENSE", "reference 42424242"),
        ("LINE_ID", "online synthetic_demo"),
        ("LINE_ID", "LINE\nsynthetic_demo"),
        ("GPS_COORD", "12.50, 100.75"),
        ("GPS_COORD", "91.12345, 0.12345"),
        ("HOUSE_REG_ID", "reference 42424242424"),
        ("IP_ADDRESS", "v1.2.3.4"),
        ("IP_ADDRESS", "รุ่น 10.15.7.2"),
        ("IP_ADDRESS", "ตามข้อ 1.2.3.4"),
        ("IP_ADDRESS", "ตามมาตรา 26.1.2.3"),
        ("IP_ADDRESS", "IP 256.0.2.17"),
        ("IP_ADDRESS", "IP 1.2.3.4.5"),
        ("IP_ADDRESS", "10:15:20"),
        ("IP_ADDRESS", "::"),
        ("MAC_ADDRESS", "02:42-00:00:00:17"),
        ("LAND_DEED_ID", "reference 42424"),
    ],
)
def test_additional_types_require_their_evidence(kind, text):
    assert not any(e.data_type == kind for e in detect_fp(text))


def test_juristic_uses_cue_and_retains_folded_digit_recovery():
    assert is_valid_thai_id(JURISTIC)
    assert [e.data_type for e in detect_fp(JURISTIC)] == ["THAI_ID"]
    dashed = f"{JURISTIC[0]}-{JURISTIC[1:5]}-{JURISTIC[5:10]}-{JURISTIC[10:12]}-{JURISTIC[12]}"
    for raw in (
        dashed,
        " ".join(JURISTIC),
        JURISTIC.translate(str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")),
    ):
        text = "ทะเบียนนิติบุคคล " + raw
        hits = detect_fp(text)
        assert [(e.data_type, e.original_text) for e in hits] == [("JURISTIC_ID", raw)]


def test_invalid_juristic_checksum_does_not_earn_the_label():
    invalid = JURISTIC[:-1] + str((int(JURISTIC[-1]) + 1) % 10)
    assert not any(e.data_type == "JURISTIC_ID" for e in detect_fp("นิติบุคคล " + invalid))


def test_ocr_recovery_keeps_the_repaired_identifier_category():
    prefix = "100000042424"
    check = (11 - sum(int(d) * (13 - i) for i, d in enumerate(prefix)) % 11) % 10
    personal = prefix + str(check)
    text = "นิติบุคคล I" + personal[1:]
    hits = detect_fp(text)
    assert [(e.data_type, e.original_text) for e in hits] == [("THAI_ID", "I" + personal[1:])]
    juristic_text = "นิติบุคคล O" + JURISTIC[1:]
    assert [e.data_type for e in detect_fp(juristic_text)] == ["JURISTIC_ID"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("รหัสนักศึกษา ใบขับขี่ 42424242", "DRIVER_LICENSE"),
        ("ใบขับขี่ รหัสนักศึกษา 42424242", "STUDENT_ID"),
        ("ใบขับขี่ 42424242 รหัสนักศึกษา", "DRIVER_LICENSE"),
        ("ใบขับขี่ 42424242นักศึกษา", "DRIVER_LICENSE"),
    ],
)
def test_driver_student_uses_nearest_cue(text, expected):
    assert [e.data_type for e in detect_fp(text)] == [expected]


def test_one_digit_land_deed_keeps_its_source_span():
    text = "โฉนดเลขที่ 7"
    hit = next(e for e in detect_fp(text) if e.data_type == "LAND_DEED_ID")
    assert hit.span == (len(text) - 1, len(text))
    assert hit.original_text == "7"


@pytest.mark.parametrize(
    "kind,cue,value",
    [
        ("IP_ADDRESS", "IP ", "2001:db8::17"),
        ("IP_ADDRESS", "IP ", "2001:0db8:0000:0000:0000:0000:0000:0017"),
        ("IP_ADDRESS", "หมายเลขเครื่อง ", "192.0.2.17"),
        ("IP_ADDRESS", "ตามมาตรา 5 อุปกรณ์ ", "192.0.2.17"),
        ("MAC_ADDRESS", "MAC ", "02-42-aa-00-00-17"),
        ("LAND_DEED_ID", "น.ส.4จ เลขที่ ", "7"),
    ],
)
def test_network_and_land_variants_preserve_source_spans(kind, cue, value):
    text = cue + value + "."
    hits = [e for e in detect_fp(text) if e.data_type == kind]
    assert len(hits) == 1
    assert hits[0].span == (len(cue), len(cue) + len(value))
    assert hits[0].original_text == value


@pytest.mark.parametrize("kind,cue,value", CASES, ids=[row[0] for row in CASES])
@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_additional_types_roundtrip_and_reuse(kind, cue, value, mode):
    text = cue + value
    entities = detect_fp(text)
    assert any(e.data_type == kind for e in entities)
    registry = EntityRegistry(entities, len(entities), 0)
    vault = SessionVault()
    first = anonymize(text, registry, vault, salt="synthetic-sdk-compat", mode=mode)
    second = anonymize(text, registry, vault, salt="other-salt", mode=mode)
    assert first.text == second.text
    record = vault.get_by_original(value, data_type=kind)
    assert record is not None and record.pseudonym != value
    if mode == "token":
        assert TOKEN_LABEL[kind] in record.pseudonym
        assert is_token_for_data_type(record.pseudonym, kind)
    restored = reverse_map(AIResponse(first.text, "synthetic", 0.0), registry, vault, mode=mode)
    assert restored.text == text
    enforce_outbound_policy(first.text, guard_context=vault)


@pytest.mark.parametrize(
    "kind,left,right",
    [
        ("JURISTIC_ID", "0-0000-00424-24-1", "0000000424241"),
        ("DRIVER_LICENSE", "4242-4242", "42424242"),
        ("HOUSE_REG_ID", "42424 242424", "42424242424"),
        ("LAND_DEED_ID", "42 424", "42424"),
        ("MAC_ADDRESS", "02:42:AA:00:00:17", "02-42-aa-00-00-17"),
        ("LINE_ID", "@Synthetic_Demo", "synthetic_demo"),
    ],
)
def test_additional_canonical_matching(kind, left, right):
    assert canonical_value(kind, left) == canonical_value(kind, right)


@pytest.mark.parametrize("kind,cue,value", CASES, ids=[row[0] for row in CASES])
def test_untrusted_additional_types_fail_closed_without_values(kind, cue, value):
    text = cue + value
    with pytest.raises(OutboundPolicyError) as caught:
        enforce_outbound_policy(text, guard_context=OutboundGuardContext())
    assert kind in caught.value.leak_types
    assert value not in str(caught.value)
    generated = generate_fp(kind, value, salt="synthetic-generated")
    with pytest.raises(OutboundPolicyError):
        enforce_outbound_policy(cue + generated, guard_context=OutboundGuardContext())
    obscured = "\u200b".join(value)
    with pytest.raises(OutboundPolicyError) as hidden:
        enforce_outbound_policy(cue + obscured, guard_context=OutboundGuardContext())
    assert kind in hidden.value.leak_types
    assert obscured not in str(hidden.value)


@pytest.mark.parametrize("kind,cue,value", CASES, ids=[row[0] for row in CASES])
def test_surrogate_shapes(kind, cue, value):
    generated = generate_fp(kind, value, salt="synthetic-shape")
    patterns = {
        "JURISTIC_ID": r"0\d{12}",
        "DRIVER_LICENSE": r"\d{8}",
        "LINE_ID": r"@[a-z0-9]{14}",
        "GPS_COORD": r"\d{1,2}\.\d{6}, \d{2,3}\.\d{6}",
        "HOUSE_REG_ID": r"\d{11}",
        "IP_ADDRESS": r"10\.(?:\d{1,3}\.){2}\d{1,3}",
        "MAC_ADDRESS": r"(?:[a-f0-9]{2}:){5}[a-f0-9]{2}",
        "LAND_DEED_ID": r"\d{5}",
    }
    assert re.fullmatch(patterns[kind], generated)
    if kind == "JURISTIC_ID":
        assert is_valid_thai_id(generated)

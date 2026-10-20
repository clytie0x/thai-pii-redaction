"""Every wave-1 type must round-trip the full facade in both modes."""

import pytest

import amphrang
from amphrang.engine.anonymizer.fp_generator import generate_fp
from amphrang.engine.anonymizer.token_generator import TOKEN_LABEL
from amphrang.engine.leak_guard import _OBFUSCATED_STRUCTURED_TYPES, SAFE_OUTBOUND_LEAK_TYPES
from amphrang.engine.scan_common import canonical_value

NEW_TYPES = ["IP_ADDRESS", "MAC_ADDRESS", "LAND_DEED_ID"]

TEXTS = {
    "IP_ADDRESS": "เชื่อมต่อจาก IP 192.168.1.44 เมื่อเวลา 10.30 น.",
    "MAC_ADDRESS": "อุปกรณ์ MAC 00:1B:44:11:3A:B7 ลงทะเบียนแล้ว",
    "LAND_DEED_ID": "โฉนดที่ดินเลขที่ 12345 ตำบลบางรัก อำเภอเมือง",
}


@pytest.mark.parametrize("dtype", NEW_TYPES)
def test_registered_everywhere(dtype):
    assert dtype in TOKEN_LABEL
    assert dtype in SAFE_OUTBOUND_LEAK_TYPES
    assert dtype in _OBFUSCATED_STRUCTURED_TYPES


@pytest.mark.parametrize("dtype", NEW_TYPES)
def test_token_mode_round_trip(dtype):
    text = TEXTS[dtype]
    masked = amphrang.anonymize(text, mode="token", salt="s")
    assert dtype in masked.entity_type_counts, masked.entity_type_counts
    assert amphrang.restore(masked.text, masked.mapping).text == text


@pytest.mark.parametrize("dtype", NEW_TYPES)
def test_surrogate_mode_round_trip_and_shape(dtype):
    text = TEXTS[dtype]
    masked = amphrang.anonymize(text, mode="surrogate", salt="s")
    assert amphrang.restore(masked.text, masked.mapping).text == text
    # the surrogate itself must re-detect as the same type (shape preserved)
    remasked = amphrang.detect(masked.text)
    assert any(e.data_type == dtype for e in remasked), masked.text


def test_mac_dash_form_round_trip_preserves_separator():
    text = "หมายเลขเครื่อง 00-1b-44-11-3a-b7 ตรวจพบในระบบ"
    masked = amphrang.anonymize(text, mode="surrogate", salt="s")
    assert amphrang.restore(masked.text, masked.mapping).text == text
    remasked = amphrang.detect(masked.text)
    matches = [e for e in remasked if e.data_type == "MAC_ADDRESS"]
    assert matches, masked.text
    assert "-" in matches[0].original_text and ":" not in matches[0].original_text


def test_ipv6_surrogate_is_ipv4_shaped():
    text = "บันทึกจาก 2001:0db8:85a3:0000:0000:8a2e:0370:7334 เข้าระบบ"
    masked = amphrang.anonymize(text, mode="surrogate", salt="s")
    assert amphrang.restore(masked.text, masked.mapping).text == text
    remasked = amphrang.detect(masked.text)
    assert any(e.data_type == "IP_ADDRESS" for e in remasked), masked.text


def test_canonical_value_folds_mac_separators_and_case():
    assert canonical_value("MAC_ADDRESS", "00:1B:44:11:3A:B7") == canonical_value(
        "MAC_ADDRESS", "00-1b-44-11-3a-b7"
    )


def test_canonical_value_land_deed_digits_only():
    assert canonical_value("LAND_DEED_ID", "123 45") == canonical_value("LAND_DEED_ID", "12345")


def test_ip_address_surrogate_shape():
    value = generate_fp("IP_ADDRESS", "203.154.77.9", salt="s")
    parts = value.split(".")
    assert len(parts) == 4
    assert parts[0] == "10"
    assert all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def test_mac_address_surrogate_preserves_separator_style():
    colon_value = generate_fp("MAC_ADDRESS", "00:1B:44:11:3A:B7", salt="s")
    dash_value = generate_fp("MAC_ADDRESS", "00-1b-44-11-3a-b7", salt="s")
    assert colon_value.count(":") == 5 and "-" not in colon_value
    assert dash_value.count("-") == 5 and ":" not in dash_value


def test_land_deed_surrogate_length_preserving():
    value = generate_fp("LAND_DEED_ID", "12345", salt="s")
    assert len(value) == 5 and value.isdigit()

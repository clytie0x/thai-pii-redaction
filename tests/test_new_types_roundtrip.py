"""Every new type must round-trip the full facade in both modes."""

import pytest

import amphrang
from amphrang.engine.anonymizer.fp_generator import generate_fp
from amphrang.engine.anonymizer.token_generator import TOKEN_LABEL
from amphrang.engine.leak_guard import _OBFUSCATED_STRUCTURED_TYPES, SAFE_OUTBOUND_LEAK_TYPES
from amphrang.engine.scan_common import canonical_value

NEW_TYPES = ["JURISTIC_ID", "DRIVER_LICENSE", "LINE_ID", "GPS_COORD", "HOUSE_REG_ID"]

TEXTS = {
    "JURISTIC_ID": "เลขทะเบียนนิติบุคคล 0107536000102 ของบริษัท",
    "DRIVER_LICENSE": "ใบขับขี่เลขที่ 63012345 หมดอายุปีหน้า",
    "LINE_ID": "ติดต่อ LINE ID @somchai_j99 หลังเลิกงาน",
    "GPS_COORD": "พบกันที่ 13.7563, 100.5018 ตอนเที่ยง",
    "HOUSE_REG_ID": "เลขรหัสประจำบ้าน 10240012345 ตามทะเบียนบ้าน",
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


def test_juristic_surrogate_starts_with_zero():
    value = generate_fp("JURISTIC_ID", "0107536000102", salt="s")
    assert value.startswith("0") and len(value) == 13 and value.isdigit()


def test_canonical_value_folds_dashes_for_juristic():
    assert canonical_value("JURISTIC_ID", "0-1075-36000-10-2") == "0107536000102"


def test_canonical_value_line_id_case_and_at():
    assert canonical_value("LINE_ID", "@Somchai_J99") == canonical_value("LINE_ID", "somchai_j99")

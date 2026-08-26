"""Detection contract for the wave-1 types (see the PDPA ontology ADR)."""

from amphrang.engine.detectors.fp_detector import detect_fp


def _types(text):
    return {(e.data_type, e.original_text) for e in detect_fp(text)}


def _score(text, data_type):
    """The score of the single surviving entity of ``data_type``."""
    scores = [e.score for e in detect_fp(text) if e.data_type == data_type]
    assert len(scores) == 1, f"expected exactly one {data_type}, got {scores}"
    return scores[0]


def test_ipv4_with_cue_detected():
    found = _types("เชื่อมต่อจาก IP 192.168.1.44 เมื่อเวลา 10.30 น.")
    assert ("IP_ADDRESS", "192.168.1.44") in found


def test_ipv4_bare_catch_all_detected():
    found = _types("พบการเข้าถึงจาก 203.154.77.9 ในบันทึกระบบ")
    assert ("IP_ADDRESS", "203.154.77.9") in found


def test_version_string_is_not_an_ip():
    found = _types("อัปเดตเป็น v1.2.3.4 และรุ่น 10.15.7.2 แล้ว")
    assert not any(t == "IP_ADDRESS" for t, _ in found)


def test_octet_over_255_rejected():
    assert not any(t == "IP_ADDRESS" for t, _ in _types("ค่าคือ 300.1.2.3 หน่วยทดสอบ"))


def test_five_group_run_is_not_an_ip():
    assert not any(t == "IP_ADDRESS" for t, _ in _types("รหัสรุ่น 1.2.3.4.5 ตามคู่มือ"))


def test_ipv6_detected_without_cue():
    found = _types("บันทึกจาก 2001:0db8:85a3:0000:0000:8a2e:0370:7334 เข้าระบบ")
    assert any(t == "IP_ADDRESS" for t, _ in found)


def test_ipv6_compressed_detected():
    found = _types("ที่อยู่ 2001:db8::8a2e:370:7334 ปรากฏใน log")
    assert any(t == "IP_ADDRESS" for t, _ in found)


def test_mac_colon_form_detected():
    found = _types("อุปกรณ์ MAC 00:1B:44:11:3A:B7 ลงทะเบียนแล้ว")
    assert ("MAC_ADDRESS", "00:1B:44:11:3A:B7") in found


def test_mac_dash_form_detected():
    found = _types("หมายเลขเครื่อง 00-1b-44-11-3a-b7 ตรวจพบในระบบ")
    assert ("MAC_ADDRESS", "00-1b-44-11-3a-b7") in found


def test_time_range_is_not_a_mac():
    assert not any(t == "MAC_ADDRESS" for t, _ in _types("เวลา 10:15-11:30 น. ประชุม"))


def test_land_deed_with_cue_detected():
    found = _types("โฉนดที่ดินเลขที่ 12345 ตำบลบางรัก อำเภอเมือง")
    assert ("LAND_DEED_ID", "12345") in found


def test_bare_digits_without_deed_cue_not_land_deed():
    assert not any(t == "LAND_DEED_ID" for t, _ in _types("ใบสั่งซื้อเลขที่ 12345 ลงวันนี้"))


def test_land_deed_leaves_the_admin_area_masked():
    """The deed digits become LAND_DEED_ID while the ตำบล/อำเภอ chain stays masked.

    Overlap dedupe drops any span an earlier keeper covers, so the emitted deed span
    must cover the digits ONLY or the whole address tail disappears with it.
    """
    found = _types("โฉนดที่ดินเลขที่ 12345 ตำบลบางรัก อำเภอเมือง")
    assert ("LAND_DEED_ID", "12345") in found
    assert ("ADDRESS", "บางรัก") in found or ("LOCATION", "บางรัก") in found
    assert ("ADDRESS", "เมือง") in found or ("LOCATION", "เมือง") in found


def test_land_deed_outranks_the_address_claim_on_the_deed_digits():
    """A 4-digit deed number before ตำบล is claimed by ADDRESS at 0.85 — 0.9 must win it."""
    found = _types("โฉนดเลขที่ 2086 ตำบลบางเสาธง")
    assert ("LAND_DEED_ID", "2086") in found
    assert ("ADDRESS", "2086") not in found
    assert ("ADDRESS", "บางเสาธง") in found or ("LOCATION", "บางเสาธง") in found


def test_single_digit_land_deed_survives_the_two_char_floor():
    """Deed numbering starts at 1, so a 1-digit deed is a real value, not noise.

    _deduplicate drops sub-2-char spans unless they are exempted; without the exemption
    this value ships unmasked.
    """
    found = _types("โฉนดเลขที่ 5 ตำบลบางรัก")
    assert ("LAND_DEED_ID", "5") in found
    assert ("ADDRESS", "บางรัก") in found or ("LOCATION", "บางรัก") in found


# --- Sentence-final punctuation. A trailing "." must not kill the match; a fifth dotted
# --- group still must. These are leak regressions: the whole value was dropped.


def test_ipv4_at_end_of_sentence_detected():
    found = _types("เข้าถึงจาก IP 192.168.1.44.")
    assert ("IP_ADDRESS", "192.168.1.44") in found


def test_ipv6_at_end_of_sentence_detected():
    found = _types("บันทึกจาก 2001:db8::8a2e:370:7334.")
    assert ("IP_ADDRESS", "2001:db8::8a2e:370:7334") in found


def test_mac_at_end_of_sentence_detected():
    found = _types("อุปกรณ์ MAC 00:1B:44:11:3A:B7.")
    assert ("MAC_ADDRESS", "00:1B:44:11:3A:B7") in found


def test_five_group_run_still_rejected_after_the_boundary_fix():
    """The trailing-period fix must not reopen the five-group hole it sits next to."""
    for text in ("รหัสรุ่น 1.2.3.4.5 ตามคู่มือ", "ค่า 192.168.1.44.5 ในตาราง"):
        assert not any(t == "IP_ADDRESS" for t, _ in _types(text)), text


# --- Score contract. These are what the dedupe precedence rests on.


def test_scores_match_the_wave1_spec():
    assert _score("เชื่อมต่อจาก IP 192.168.1.44 เมื่อเวลา 10.30 น.", "IP_ADDRESS") == 0.9
    assert _score("พบการเข้าถึงจาก 203.154.77.9 ในบันทึกระบบ", "IP_ADDRESS") == 0.8
    assert _score("บันทึกจาก 2001:db8::8a2e:370:7334 เข้าระบบ", "IP_ADDRESS") == 0.9
    assert _score("อุปกรณ์ MAC 00:1B:44:11:3A:B7 ลงทะเบียนแล้ว", "MAC_ADDRESS") == 0.9
    assert _score("โฉนดเลขที่ 2086 ตำบลบางเสาธง", "LAND_DEED_ID") == 0.9

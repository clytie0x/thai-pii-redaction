"""One address must stay one span when it names a soi, a road or an estate.

Three split causes, each counted as extra ADDRESS (or NAME) predictions:
the short labels "ซ." and "ถ." were not address glue, a housing-estate name
made the gap longer than the bridge limit, and the CRF tagged the estate name
as a person, which cut the chain. The anti-merge cases keep two parties'
addresses apart.
"""

from __future__ import annotations

from pii_redactor.detectors.aggregate import (
    _relabel_numberless_addresses,
    detect_all,
    merge_address_spans,
)
from pii_redactor.models import Entity


def _entities(text: str, *parts: tuple[str, str] | tuple[str, str, str]) -> list[Entity]:
    """Build sorted entities from (value, type[, redact_type]) found left to right."""
    out = []
    cursor = 0
    for index, part in enumerate(parts):
        value, data_type = part[0], part[1]
        redact_type = part[2] if len(part) == 3 else "FP"
        start = text.index(value, cursor)
        cursor = start + len(value)
        out.append(Entity(f"e{index}", redact_type, data_type, (start, cursor), 0.85, value))
    return out


def _merged(text: str, *parts) -> list[tuple[str, str]]:
    merged = merge_address_spans(text, _entities(text, *parts))
    return [(e.data_type, e.original_text) for e in merged]


# ── short soi / road labels ────────────────────────────────────────────────


def test_short_soi_and_road_labels_are_address_glue():
    text = "จัดส่งที่ 71/5 ซ.ร่มเกล้า 14 ถ.ร่มเกล้า แขวงคลองสามประเวศ"
    got = _merged(
        text,
        ("71/5", "ADDRESS"),
        ("ร่มเกล้า 14", "ADDRESS"),
        ("ร่มเกล้า", "ADDRESS"),
        ("คลองสามประเวศ", "ADDRESS"),
    )
    assert got == [("ADDRESS", "71/5 ซ.ร่มเกล้า 14 ถ.ร่มเกล้า แขวงคลองสามประเวศ")]


def test_short_soi_address_is_one_span_end_to_end():
    text = "ที่อยู่ 71/5 ซ.ร่มเกล้า 14 ถ.ร่มเกล้า แขวงคลองสามประเวศ เขตลาดกระบัง กรุงเทพมหานคร 10520"
    addresses = [e.original_text for e in detect_all(text) if e.data_type == "ADDRESS"]
    assert len(addresses) == 1, addresses
    assert addresses[0].startswith("71/5") and addresses[0].endswith("10520")


def test_letter_before_a_full_stop_is_not_a_road_label():
    # "รถ." ends a word. It is not the road label "ถ.".
    text = "บ้านเลขที่ 12 จอดรถ. 99 ซอยเจริญ"
    got = _merged(text, ("12", "ADDRESS"), ("99", "ADDRESS"))
    assert got == [("ADDRESS", "12"), ("ADDRESS", "99")]


# ── housing-estate name in the gap ─────────────────────────────────────────


def test_estate_name_after_the_house_number_bridges_to_the_moo():
    text = "อยู่ที่ 63/8 หมู่บ้านสวนสราญรมย์ หมู่ 4 ถนนเลียบคลอง ตำบลบางรักน้อย"
    got = _merged(text, ("63/8", "ADDRESS"), ("4", "ADDRESS"), ("เลียบคลอง", "ADDRESS"))
    assert got == [("ADDRESS", "63/8 หมู่บ้านสวนสราญรมย์ หมู่ 4 ถนนเลียบคลอง")]


def test_estate_gap_with_short_moo_and_road_labels():
    text = "ส่งที่ 502/17 หมู่บ้านสวนสราญรมย์ ม.6 ถ.เลียบคลอง ต.บางรักน้อย"
    got = _merged(text, ("502/17", "ADDRESS"), ("เลียบคลอง", "ADDRESS"), ("บางรักน้อย", "ADDRESS"))
    assert got == [("ADDRESS", "502/17 หมู่บ้านสวนสราญรมย์ ม.6 ถ.เลียบคลอง ต.บางรักน้อย")]


def test_estate_address_is_one_span_end_to_end():
    text = "ที่อยู่ 63/8 หมู่บ้านสวนสราญรมย์ หมู่ 4 ถนนเลียบคลอง ตำบลบางรักน้อย อำเภอเมืองนนทบุรี จังหวัดนนทบุรี 11000"
    found = detect_all(text)
    addresses = [e.original_text for e in found if e.data_type == "ADDRESS"]
    assert len(addresses) == 1, [(e.data_type, e.original_text) for e in found]
    assert addresses[0].startswith("63/8") and addresses[0].endswith("11000")
    assert not [e for e in found if e.data_type == "NAME"]


def test_long_gap_without_an_estate_keeps_the_old_limit():
    # 26 characters, an address word inside, but no estate name at the start.
    text = "บ้านเลขที่ 12 และมีโกดังเก็บของอยู่ในซอย 99 ถนนเจริญ"
    gap = text[text.index("12") + 2 : text.index("99")]
    assert len(gap) > 25 and "ซอย" in gap
    got = _merged(text, ("12", "ADDRESS"), ("99", "ADDRESS"))
    assert got == [("ADDRESS", "12"), ("ADDRESS", "99")]


def test_estate_gap_still_obeys_every_other_rule():
    for gap in (
        " หมู่บ้านสวนสราญรมย์ ผู้ขาย หมู่ ",  # another party
        " หมู่บ้านสวนสราญรมย์ โทร 0812 หมู่ ",  # digit run longer than 3
        " หมู่บ้านสวนสราญรมย์\nหมู่ ",  # line break
        " หมู่บ้านสวนสราญรมย์ที่มีสระว่ายน้ำและสวนขนาดใหญ่ หมู่ ",  # over 40
    ):
        text = f"เลขที่ 63/8{gap}4 ถนนเลียบคลอง"
        got = _merged(text, ("63/8", "ADDRESS"), ("4", "ADDRESS"))
        assert got == [("ADDRESS", "63/8"), ("ADDRESS", "4")], gap


# ── estate name tagged as a person ─────────────────────────────────────────


def test_estate_name_tagged_as_person_joins_the_address():
    text = "พักอยู่ที่ 63/8 หมู่บ้านสวนสราญรมย์ หมู่ 4 ถนนเลียบคลอง"
    got = _merged(
        text,
        ("63/8", "ADDRESS"),
        ("หมู่บ้านสวนสราญรมย์", "NAME", "TB"),
        ("4", "ADDRESS"),
        ("เลียบคลอง", "ADDRESS"),
    )
    assert got == [("ADDRESS", "63/8 หมู่บ้านสวนสราญรมย์ หมู่ 4 ถนนเลียบคลอง")]


def test_estate_name_tagged_as_location_joins_the_address():
    text = "พักอยู่ที่ 63/8 หมู่บ้านสวนสราญรมย์ หมู่ 4 ถนนเลียบคลอง"
    got = _merged(
        text,
        ("63/8", "ADDRESS"),
        ("หมู่บ้านสวนสราญรมย์", "LOCATION", "TB"),
        ("4", "ADDRESS"),
    )
    assert got == [("ADDRESS", "63/8 หมู่บ้านสวนสราญรมย์ หมู่ 4")]


def test_other_location_between_fragments_still_splits_the_chain():
    text = "เลขที่ 63/8 เชียงใหม่ 4 ถนนเลียบคลอง"
    got = _merged(text, ("63/8", "ADDRESS"), ("เชียงใหม่", "LOCATION", "TB"), ("4", "ADDRESS"))
    assert got == [("ADDRESS", "63/8"), ("LOCATION", "เชียงใหม่"), ("ADDRESS", "4")]


def test_estate_name_before_the_first_fragment_joins_too():
    text = "พักอยู่ที่ 27 หมู่บ้านสวนสราญรมย์ ซอยเลียบคลอง 9"
    got = _merged(text, ("หมู่บ้านสวนสราญรมย์", "NAME", "TB"), ("ซอยเลียบคลอง 9", "ADDRESS"))
    assert got == [("ADDRESS", "หมู่บ้านสวนสราญรมย์ ซอยเลียบคลอง 9")]


def test_real_person_name_still_splits_the_chain():
    text = "บ้านเลขที่ 12 ซอยพัฒนา 3 สมหญิง รักดี ตำบลบางพระ"
    got = _merged(
        text,
        ("12", "ADDRESS"),
        ("สมหญิง รักดี", "NAME", "TB"),
        ("บางพระ", "ADDRESS"),
    )
    assert ("NAME", "สมหญิง รักดี") in got
    assert len([g for g in got if g[0] == "ADDRESS"]) == 2


def test_estate_word_glued_to_more_words_is_not_absorbed():
    # A span with a space may carry a real name after the estate. Keep it.
    text = "เลขที่ 12 หมู่บ้านสวนสราญรมย์ สมหญิง ตำบลบางพระ"
    got = _merged(
        text,
        ("12", "ADDRESS"),
        ("หมู่บ้านสวนสราญรมย์ สมหญิง", "NAME", "TB"),
        ("บางพระ", "ADDRESS"),
    )
    assert ("NAME", "หมู่บ้านสวนสราญรมย์ สมหญิง") in got


def test_estate_name_alone_is_left_as_it_was():
    text = "นัดเจอกันหน้า หมู่บ้านสวนสราญรมย์ ตอนเย็น"
    got = _merged(text, ("หมู่บ้านสวนสราญรมย์", "NAME", "TB"))
    assert got == [("NAME", "หมู่บ้านสวนสราญรมย์")]


def test_estate_name_and_postal_code_alone_do_not_make_an_address():
    text = "หมู่บ้านสวนสราญรมย์ 11000"
    got = _merged(text, ("หมู่บ้านสวนสราญรมย์", "NAME", "TB"), ("11000", "POSTAL_CODE"))
    assert got == [("NAME", "หมู่บ้านสวนสราญรมย์"), ("POSTAL_CODE", "11000")]


# ── numberless estate mention ──────────────────────────────────────────────


def _relabelled(value: str) -> str:
    entity = Entity("e0", "FP", "ADDRESS", (0, len(value)), 0.85, value)
    return _relabel_numberless_addresses([entity])[0].data_type


def test_numberless_estate_mention_is_a_location_not_an_address():
    # "หมู่" inside "หมู่บ้าน" is not the village-number label.
    assert _relabelled("ซอยข้างโรงสีและหมู่บ้านจัดสรรริมคลอง") == "LOCATION"


def test_numberless_admin_area_and_numbered_estate_stay_address():
    assert _relabelled("หมู่ที่สาม ตำบลบางรักน้อย") == "ADDRESS"
    assert _relabelled("ตำบลบางรักน้อย อำเภอเมืองนนทบุรี") == "ADDRESS"
    assert _relabelled("63/8 หมู่บ้านสวนสราญรมย์") == "ADDRESS"

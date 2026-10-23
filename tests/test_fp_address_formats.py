"""Rural roster addresses (recall campaign, 2026-10-24).

Local-administration rosters write "261 หมู่ 8 ตำบลหาดใหญ่ ..." or
"189/38 ม.6 ต.ทุ่งหมอ อ.สะเดา จ.สงขลา 90120": the house number has no label
and the postcode follows abbreviated labels. Both stayed readable.
"""

import pytest

from pii_redactor.detectors.aggregate import detect_all


def _uncovered_digits(text: str, value: str) -> str:
    start = text.index(value)
    spans = [e.span for e in detect_all(text)]
    return "".join(
        text[k]
        for k in range(start, start + len(value))
        if text[k].isdigit() and not any(s <= k < t for s, t in spans)
    )


@pytest.mark.parametrize(
    "value",
    [
        "261 หมู่ 8 ตำบลหาดใหญ่ อำเภอหาดใหญ่ จังหวัดสงขลา 90110",
        "189/38 ม.6 ต.ทุ่งหมอ อ.สะเดา จ.สงขลา 90120",
        "203 หมู่ที่ 7 ตำบลนาหนองทุ่ม อำเภอชุมแพ จังหวัดขอนแก่น 40130",
        "40/9 ถนนสุขุมวิท ต.ตลาดไชยา อ.ไชยา จ.สุราษฎร์ธานี 84110",
        "๔๘ ม.๕ ต.ตลาดไชยา อ.ไชยา จ.สุราษฎร์ธานี ๘๔๑๑๐",
    ],
)
def test_every_digit_of_a_rural_address_is_masked(value):
    text = f"1 | นางสมใจ ใจดี | {value} | 1,000"
    assert _uncovered_digits(text, value) == ""


def test_a_quantity_before_moo_words_needs_a_moo_number():
    ents = detect_all("แบ่งเป็น 30 หมู่บ้านในเขตอำเภอ")
    assert not any(e.data_type == "ADDRESS" and "30" in e.original_text for e in ents)

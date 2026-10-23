"""Leak rates: did any character of the PII value stay readable?

Recall asks whether an entity was flagged with the right type. A redaction
tool fails differently: a value can be flagged under the wrong type and still
be fully masked, or flagged with the right type and still leave digits
readable. These tests pin the type-agnostic leak view. A gold entity is a
full leak when no alphanumeric character of it is covered by any prediction,
and a partial leak when some but not all of them are.
"""

from benchmark.scorer import score
from benchmark.types import GoldSpan, Sample


def _sample(text, spans, slice_="s", template_id="t"):
    return Sample(
        text=text,
        spans=[GoldSpan(a, b, t) for a, b, t in spans],
        template_id=template_id,
        slice=slice_,
    )


def test_unflagged_value_is_a_full_leak():
    text = "โทร 081-234-5678"
    samples = [_sample(text, [(4, len(text), "PHONE")])]
    report = score(samples, [[]], bootstrap_iters=0)
    leak = report["overall"]
    assert leak["full_leak_entities"] == 1
    assert leak["full_leak_rate"] == 1.0
    assert leak["partial_leak_entities"] == 0
    assert report["by_type"]["PHONE"]["full_leak"] == 1


def test_wrong_type_that_masks_everything_is_not_a_leak():
    text = "เลข 1234567890"
    samples = [_sample(text, [(4, len(text), "BANK_ACCOUNT")])]
    report = score(samples, [[(4, len(text), "PHONE")]], bootstrap_iters=0)
    overall = report["overall"]
    assert overall["fn"] == 1, "entity recall still counts the wrong type as a miss"
    assert overall["full_leak_entities"] == 0
    assert overall["partial_leak_entities"] == 0


def test_digits_left_readable_are_a_partial_leak_but_separators_are_not():
    text = "บัตร 3714 496353 98431"
    start = 5
    samples = [_sample(text, [(start, len(text), "CREDIT_CARD")])]
    # Covers everything except the last five digits.
    report = score(samples, [[(start, len(text) - 5, "CREDIT_CARD")]], bootstrap_iters=0)
    assert report["overall"]["partial_leak_entities"] == 1
    assert report["overall"]["full_leak_entities"] == 0
    # Leaving only the separating spaces uncovered is not a leak.
    pieces = [(5, 9, "CREDIT_CARD"), (10, 16, "CREDIT_CARD"), (17, 22, "CREDIT_CARD")]
    report = score(samples, [pieces], bootstrap_iters=0)
    assert report["overall"]["partial_leak_entities"] == 0
    assert report["overall"]["partial_leak_rate"] == 0.0


def test_negative_documents_report_no_leak_fields_crash():
    samples = [_sample("ใบเสร็จเลขที่ 001", [], slice_="negative")]
    report = score(samples, [[]], bootstrap_iters=0)
    assert report["by_slice"]["negative"]["gold_entities"] == 0

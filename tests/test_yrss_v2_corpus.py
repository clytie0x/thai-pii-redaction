"""Generator checks for the YRSS evaluation v2 corpus."""

from __future__ import annotations

import random

import pytest

from benchmark.yrss_v2 import values
from benchmark.yrss_v2.corpus import (
    Template,
    render,
    validate_templates,
)
from benchmark.yrss_v2.types import CONTEXTUAL_TYPES, SCHEME_TYPES, STRUCTURED_TYPES


def _template(text: str, *, negative: bool = False, family: str = "t-p-001") -> Template:
    return Template(family=family, genre="test", negative=negative, text=text)


def test_scheme_swaps_student_id_for_driver_licence():
    assert len(SCHEME_TYPES) == 11
    assert "DRIVER_LICENSE" in SCHEME_TYPES
    assert "STUDENT_ID" not in SCHEME_TYPES
    assert set(STRUCTURED_TYPES) | set(CONTEXTUAL_TYPES) == set(SCHEME_TYPES)
    assert not set(STRUCTURED_TYPES) & set(CONTEXTUAL_TYPES)


def test_render_records_source_spans_for_each_labeled_placeholder():
    doc = render(_template("ผู้ติดต่อ คุณ{{name}} โทร {{phone}} สั่งซื้อ {{order_code}}"), 0, seed=1)
    assert [span.entity_type for span in doc.spans] == ["NAME", "PHONE"]
    for span in doc.spans:
        assert doc.text[span.start : span.end].strip() == doc.text[span.start : span.end]
    assert "{{" not in doc.text
    assert doc.text.startswith("ผู้ติดต่อ คุณ")


def test_keyed_placeholder_repeats_one_value_and_labels_every_mention():
    doc = render(_template("{{name:a}} แจ้งว่า {{name:a}} จะมาแทน {{name}}"), 0, seed=3)
    surfaces = [doc.text[span.start : span.end] for span in doc.spans]
    assert len(surfaces) == 3
    assert surfaces[0] == surfaces[1]
    assert surfaces[2] != surfaces[0]


def test_render_is_deterministic_and_variants_differ():
    template = _template("เลขบัตร {{thai_id}} บัญชี {{bank}}")
    assert render(template, 0, seed=7) == render(template, 0, seed=7)
    assert render(template, 0, seed=7).text != render(template, 1, seed=7).text


def test_unknown_placeholder_is_rejected():
    with pytest.raises(ValueError, match="unknown-placeholder"):
        render(_template("รหัส {{student_id}}"), 0, seed=1)


def test_checksummed_values_are_valid_and_decoys_are_not():
    rng = random.Random(5)
    for _ in range(200):
        assert values.thai_id_valid(values.digits(values.thai_id(rng)))
        assert values.luhn_valid(values.digits(values.card(rng)))
        assert not values.thai_id_valid(values.bad_id13(rng))
        ref = values.ref_no(rng)
        assert ref.isdigit()
        assert len(ref) not in (8, 10, 13, 16)
        assert len(values.digits(values.licence(rng))) == 8


def test_template_validation_reports_kinds_without_text():
    bad = [
        _template("โทร 0812345678 คุณ{{name}}"),
        _template("สั่งซื้อ {{order_code}} ของ {{name}}", negative=True, family="t-n-001"),
        _template("ไม่มีข้อมูลบุคคล", family="t-p-002"),
        _template("ซ้ำ {{name}}", family="t-p-002"),
    ]
    errors = validate_templates(bad)
    assert "long-digit-run-in-fixed-text" in errors
    assert "negative-has-labeled-placeholder" in errors
    assert "positive-without-labeled-placeholder" in errors
    assert "duplicate-family" in errors
    assert all("0812345678" not in error for error in errors)

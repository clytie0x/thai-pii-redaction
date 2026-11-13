"""Generator checks for the YRSS evaluation v2 corpus."""

from __future__ import annotations

import json
import random

import pytest

from benchmark.yrss_v2 import values
from benchmark.yrss_v2.corpus import (
    Template,
    build_corpus,
    check_targets,
    load_templates,
    lock_path,
    public_lock,
    render,
    templates_path,
    validate_corpus,
    validate_realism,
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


def test_dev_split_matches_its_lock():
    templates = load_templates("dev")
    assert validate_templates(templates) == []
    corpus = build_corpus("dev")
    assert validate_corpus(corpus) == []
    lock = json.loads(lock_path("dev").read_text(encoding="utf-8"))
    assert public_lock(corpus) == lock
    assert lock["documents"] == 300
    assert lock["negative_documents"] / lock["documents"] == pytest.approx(0.2)
    assert set(lock["type_counts"]) == set(SCHEME_TYPES)
    assert templates_path("dev").name == "dev-templates.jsonl"


def test_dev_lock_carries_no_document_text_or_values():
    corpus = build_corpus("dev")
    blob = lock_path("dev").read_text(encoding="utf-8")
    for doc in corpus.documents[:40]:
        for span in doc.spans:
            assert doc.text[span.start : span.end] not in blob


def _mixed(text: str) -> bool:
    return any("๐" <= c <= "๙" for c in text) and any(c.isascii() and c.isalpha() for c in text)


def test_dev_corpus_still_matches_its_lock():
    assert public_lock(build_corpus("dev")) == json.loads(
        lock_path("dev").read_text(encoding="utf-8")
    )


def test_strict_never_mixes_thai_digits_with_latin_letters():
    template = _template("เกิด {{dob}}")
    loose, strict = [], []
    for variant in range(400):
        loose.append(render(template, variant, seed=5).text)
        strict.append(render(template, variant, seed=5, strict=True).text)
    assert any(_mixed(text) for text in loose)  # the bug is real without strict
    assert not any(_mixed(text) for text in strict)


def _lock(**over) -> dict:
    lock = {
        "documents": 800,
        "families": 200,
        "variants_per_family": 4,
        "negative_documents": 160,
        "type_counts": dict.fromkeys(SCHEME_TYPES, 150),
    }
    lock.update(over)
    return lock


def test_check_targets_accepts_the_registered_size():
    assert check_targets(_lock()) == []


@pytest.mark.parametrize(
    ("over", "kind"),
    [
        ({"documents": 799}, "documents-not-800"),
        ({"families": 199}, "families-not-200"),
        ({"variants_per_family": 3}, "variants-not-4"),
        ({"negative_documents": 159}, "negative-documents-not-160"),
        (
            {"type_counts": {**dict.fromkeys(SCHEME_TYPES, 150), "PASSPORT": 149}},
            "type-below-150:PASSPORT",
        ),
    ],
)
def test_check_targets_flags_each_shortfall(over, kind):
    assert check_targets(_lock(**over)) == [kind]


_THAI = "สวัสดีครับท่านผู้อ่านทุกท่านวันนี้อากาศดีมากเลยนะครับ"  # 5 marks, 30+ consonants
_FAM = "0123456789ab"


def _rt(text, family=_FAM, genre="memo") -> Template:
    return Template(family=family, genre=genre, negative=False, text=text)


def _realism(templates, dev=()):
    return validate_realism(list(templates), dev_templates=list(dev))


def _kinds(errors):
    return {e.split(":")[0] for e in errors}


def test_realism_marks_stripped():
    stripped = "สวสดครบทานผอานทกทานวนนอากาศดมากเลยนะครบ" * 2  # marks removed, >= 40 consonants
    assert "marks-stripped" not in _kinds(_realism([_rt(_THAI * 3 + " {{phone}}")]))
    assert "marks-stripped" in _kinds(_realism([_rt(stripped + " {{phone}}")]))


def test_realism_fields_glued():
    spaced = "เบอร์ {{phone}} อีเมล {{email}} ชื่อ {{name}} ครับ"
    glued = "เบอร์{{phone}}อีเมล{{email}}ชื่อ{{name}}ครับ"
    titled = "ติดต่อ นายสมชาย {{phone}}, ตอบ {{email}} นาย{{name}}"
    assert "fields-glued" not in _kinds(_realism([_rt(spaced)]))
    assert "fields-glued" in _kinds(_realism([_rt(glued)]))
    assert "fields-glued" not in _kinds(_realism([_rt("นาย{{name}}นาย{{name}}นาย{{name}} ")]))
    assert "fields-glued" not in _kinds(_realism([_rt(titled)]))


def test_realism_near_duplicate_against_test_and_dev():
    base = "รายงานผลการตรวจสอบประจำเดือนของหน่วยงานโดยละเอียด {{phone}}"
    other = _rt(base.replace("เดือน", "ปี"), family="ba9876543210")
    far = _rt("ข้อความที่แตกต่างกันโดยสิ้นเชิงไม่เกี่ยวข้องกันเลย {{phone}}", family="ba9876543210")
    assert "near-duplicate-family" in _kinds(_realism([_rt(base), other]))
    assert "near-duplicate-family" in _kinds(_realism([_rt(base)], dev=[other]))
    assert "near-duplicate-family" not in _kinds(_realism([_rt(base), far]))


def _family_set(genres, lines, long_count):
    out = []
    for i in range(20):
        body = "\n".join(f"{_THAI} {i} {k}" for k in range(lines[i]))
        if i < long_count:
            body += _THAI * 20
        out.append(_rt(body + " {{phone}}", family=f"{i:012x}", genre=genres[i]))
    return out


_DIST = {"genre-over-15pct", "too-few-short-families", "too-few-long-families"}


def test_realism_distribution():
    even = [f"g{i % 10}" for i in range(20)]
    lines = [1] * 4 + [5] * 16
    assert not _kinds(_realism(_family_set(even, lines, 2))) & _DIST
    skewed = ["g0"] * 4 + [f"g{i}" for i in range(1, 17)]
    assert "genre-over-15pct" in _kinds(_realism(_family_set(skewed, lines, 2)))
    assert "too-few-short-families" in _kinds(_realism(_family_set(even, [5] * 20, 2)))
    assert "too-few-long-families" in _kinds(_realism(_family_set(even, lines, 0)))


def test_realism_opaque_ids_and_genre():
    assert not _kinds(_realism([_rt("{{phone}} x")])) & {
        "family-id-not-opaque",
        "genre-reveals-negative",
    }
    assert "family-id-not-opaque" in _kinds(_realism([_rt("{{phone}} x", family="t-p-001")]))
    assert "genre-reveals-negative" in _kinds(_realism([_rt("{{phone}} x", genre="neg-memo")]))


def test_realism_errors_carry_no_template_text():
    errors = _realism([_rt("เบอร์{{phone}}อีเมล{{email}}ชื่อ{{name}}ครับ")])
    assert errors and all("เบอร์" not in e for e in errors)

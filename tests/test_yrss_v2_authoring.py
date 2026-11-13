"""Plan, brief and assembly for the YRSS v2 test templates. Synthetic text only."""

from __future__ import annotations

import json
import re
from collections import Counter

from benchmark.yrss_v2 import authoring, corpus
from benchmark.yrss_v2.types import DECOY_KINDS, LABELED_KINDS


def test_plan_is_seeded_and_has_the_registered_shape():
    slots = authoring.plan()
    assert slots == authoring.plan()
    assert len(slots) == 200 and len({s.slot for s in slots}) == 200
    for author in authoring.AUTHORS:
        mine = [s for s in slots if s.author == author]
        assert len(mine) == 100
        assert sum(s.negative for s in mine) == 20
        lengths = Counter(s.length for s in mine)
        assert lengths["short"] == 15 and lengths["long"] == 10
    assert max(Counter(s.genre for s in slots).values()) / len(slots) <= corpus.MAX_GENRE_SHARE


def test_plan_reaches_the_type_target_from_required_placeholders_alone():
    slots = authoring.plan()
    for s in slots:
        pool = DECOY_KINDS if s.negative else LABELED_KINDS
        assert set(s.must_use) <= set(pool) and len(set(s.must_use)) == len(s.must_use)
    families = Counter(k for s in slots if not s.negative for k in s.must_use)
    assert set(families) == set(authoring.TYPE_PLACEHOLDER.values())
    # Four variants per family, so required uses alone give each type its 150.
    assert min(families.values()) * corpus.VARIANTS["test"] >= corpus.TARGET_TYPE_COUNT


def test_brief_lists_every_slot_and_carries_no_dev_template():
    slots = authoring.batch_slots("deepseek", 3)
    text = authoring.brief(slots, authoring.GUIDE.read_text("utf-8"))
    assert all(s.slot in text for s in slots)
    assert "GUIDE START" in text and "{{licence}}" in text
    for dev in corpus.load_templates("dev"):
        assert dev.text[:60] not in text


def _answer(slot: authoring.Slot, text: str | None = None, **change) -> corpus.Template:
    if text is None:
        parts = " ".join(f"ค่า {{{{{k}}}}} นะคะ" for k in slot.must_use)
        text = "ข้อความทดสอบสังเคราะห์ " + parts
        if slot.length == "long":
            text += " " + "ข้อความยาวเพิ่มเติมสำหรับทดสอบ " * 30
        if slot.length == "medium":
            text = "\n".join([text, "บรรทัดสอง", "บรรทัดสาม"])
    row = {"family": slot.slot, "genre": slot.genre, "negative": slot.negative, "text": text}
    row.update(change)
    return corpus.Template(**row)


def test_check_batch_accepts_a_complete_answer():
    slots = authoring.batch_slots("claude", 0)
    assert authoring.check_batch(slots, [_answer(s) for s in slots]) == []


def test_check_batch_names_each_fault_without_text():
    slots = authoring.batch_slots("claude", 0)
    positive = next(s for s in slots if not s.negative)
    negative = next(s for s in slots if s.negative)
    answers = {s.slot: _answer(s) for s in slots}
    answers[positive.slot] = _answer(positive, text="ไม่มีอะไรเลย {{date}}")
    answers[negative.slot] = _answer(negative, text="โทร {{phone}} {{date}}")
    missing = next(s for s in slots if s.slot not in (positive.slot, negative.slot))
    del answers[missing.slot]
    errors = authoring.check_batch(slots, list(answers.values()))
    assert f"missing:{missing.slot}" in errors
    assert f"positive-without-labeled-placeholder:{positive.slot}" in errors
    assert f"negative-has-labeled-placeholder:{negative.slot}" in errors
    assert all(re.fullmatch(r"[a-z0-9_-]+:[a-z]\d{4}", e) for e in errors), errors


def test_parse_output_keeps_only_json_lines():
    slot = authoring.batch_slots("deepseek", 0)[0]
    line = json.dumps(
        {"family": slot.slot, "genre": slot.genre, "negative": False, "text": "x"},
        ensure_ascii=False,
    )
    raw = f"> build · model\n```json\n{line}\n{{broken\n```\n"
    assert [t.family for t in authoring.parse_output(raw)] == [slot.slot]


def test_assemble_gives_opaque_unique_ids_and_keeps_every_text():
    slots = authoring.plan()[:30]
    rows = [_answer(s) for s in slots]
    out = authoring.assemble(rows)
    assert all(re.fullmatch(r"[0-9a-f]{12}", t.family) for t in out)
    assert len({t.family for t in out}) == len(out)
    assert sorted(t.text for t in out) == sorted(t.text for t in rows)
    parsed = corpus._parse(authoring.dumps(out).encode("utf-8"))
    assert [t.family for t in parsed] == [t.family for t in out]


def test_review_brief_carries_every_template_and_the_fix_only_rules():
    slots = authoring.batch_slots("claude", 1)
    rows = [_answer(s) for s in slots]
    text = authoring.review_brief(rows, authoring.GUIDE.read_text("utf-8"))
    assert "ห้ามเปลี่ยนสำนวน" in text
    families = [t.family for t in authoring.parse_output(text)]
    # The guide's own format example is a JSON line too.
    assert [f for f in families if f != "dev-p-001"] == [s.slot for s in slots]


def test_change_lines_reads_only_the_log():
    raw = '{"family": "c0000"}\nCHANGE c0003 1\nCHANGE c0007 2\nCHANGE too many words here\n'
    assert authoring.change_lines(raw) == ["c0003:1", "c0007:2"]

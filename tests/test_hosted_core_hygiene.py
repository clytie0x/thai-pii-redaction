"""Exact historical Hosted NAME guards needed by the canonical adapter."""

from __future__ import annotations

import pytest

from pii_redactor.detectors import tb_detector


@pytest.mark.parametrize("label", ["คำตอบ", "คำตอบ:", "**คำตอบ:**", "คำตอบ:**", "# คำตอบ："])
def test_fixed_answer_label_is_not_a_name(label):
    assert tb_detector._name_hygiene(label, 0, len(label)) == []


def test_answer_label_does_not_remove_a_nearby_real_full_name():
    name = "นายสมชาย ใจดี"
    text = f"**คำตอบ:**\n{name}"
    start = text.index(name)
    labels = tb_detector._finalize_tb_candidate(text, 0, start - 1, "PERSON")
    names = tb_detector._finalize_tb_candidate(text, start, len(text), "PERSON")
    assert labels == []
    assert [(item.data_type, item.span, item.original_text) for item in names] == [
        ("NAME", (start, len(text)), name)
    ]


def test_multiline_glued_role_tail_retains_exact_name_source_range():
    text = "คำชี้แจง\nผู้สมัครสังเคราะห์ สมชาย ใจดี"
    name = "สังเคราะห์ สมชาย ใจดี"
    spans = tb_detector._name_hygiene(text, 0, len(text))
    assert (text.index(name), len(text)) in spans
    assert all(text[start:end] != "ผู้สมัครสังเคราะห์ สมชาย ใจดี" for start, end in spans)


def test_separately_spaced_role_tail_keeps_the_existing_boundary():
    text = "คำชี้แจง\nผู้สมัคร สังเคราะห์ สมชาย ใจดี"
    tail_start = text.index("ผู้สมัคร")
    assert (tail_start, len(text)) in tb_detector._name_hygiene(text, 0, len(text))

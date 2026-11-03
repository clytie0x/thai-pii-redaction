"""Bounded prior-SDK detector contracts shared by all canonical callers."""

from __future__ import annotations

import pytest

from pii_redactor.detectors import aggregate, tb_detector
from pii_redactor.detectors.name_context import detect_name_context
from pii_redactor.models import Entity


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("เมือง", "LOCATION"),
        ("ถนนมิตรภาพ", "LOCATION"),
        ("บ้านตามทะเบียนบ้าน", "LOCATION"),
        ("12 ถนนตัวอย่าง", "ADDRESS"),
        ("๑๒ ถนนตัวอย่าง", "ADDRESS"),
        ("ตำบลบางพระ อำเภอศรีราชา จังหวัดชลบุรี", "ADDRESS"),
    ],
)
def test_address_label_parity_keeps_the_exact_protected_source(monkeypatch, text, expected):
    candidate = Entity("synthetic", "TB", "ADDRESS", (0, len(text)), 0.85, text)
    monkeypatch.setattr(aggregate, "detect_fp", lambda _text: [])
    monkeypatch.setattr(aggregate, "detect_tb", lambda _text, **_kwargs: [candidate])
    monkeypatch.setattr(aggregate, "scan_fn", lambda *_args: [])
    monkeypatch.setattr(aggregate, "detect_parallel_record_names", lambda *_args: [])
    result = aggregate.detect_all(text)
    assert [(item.data_type, item.span, item.original_text) for item in result] == [
        (expected, candidate.span, text)
    ]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("คนขับคนที่สาม ณัฐดนัย ภูวนาถ ใบขับขี่ 94198359", "ณัฐดนัย ภูวนาถ"),
        ("ผู้เช่าหลัก วรพล เกียรติก้องไกล ใบอนุญาตขับรถเลขที่ 96567268", "วรพล เกียรติก้องไกล"),
        ("รุจิรา แสนสุขเกษม ใบขับขี่ 52920948", "รุจิรา แสนสุขเกษม"),
        ("ปวีณ์นุช โกศลสิริ Driver's License number 66668982", "ปวีณ์นุช โกศลสิริ"),
        ("บริษัทออดิทไทย จำกัด มอบหมายให้ ปกรณ์ ตั้งสิริกุล เดินทางไปตรวจสอบสาขา", "ปกรณ์ ตั้งสิริกุล"),
    ],
)
def test_document_and_assignment_cues_preserve_name_spans(text, name):
    names = detect_name_context(text)
    assert any(
        item.original_text == name and text[item.span[0] : item.span[1]] == name for item in names
    )


@pytest.mark.parametrize(
    "text", ["มอบหมายให้ดำเนินการ แทนข้าพเจ้า ได้", "มอบหมายให้ บริษัท ตัวอย่าง จำกัด ดำเนินการแทน"]
)
def test_assignment_cue_does_not_admit_glued_prose_or_organizations(text):
    assert detect_name_context(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "เลขผู้เสียภาษี",
        "ใบสั่งงานไรเดอร์ประจำกะเช้า",
        "ทำเนียบไลน์ไอดีตัวแทนจำหน่ายแฟรนไชส์",
        "น.ส.3ก เดิม",
        "น.ส.4จ",
        "น.ส.3",
    ],
)
def test_form_labels_and_land_abbreviations_are_not_person_spans(text):
    assert tb_detector._name_hygiene(text, 0, len(text)) == []


@pytest.mark.parametrize(
    "text", ["ทิพย์มณี", "วรากร", "อริยะสกุล", "มานพ", "น.ส.สมศรี ใจดี", "น.ส. สมศรี ใจดี"]
)
def test_existing_real_name_shapes_keep_their_source_span(text):
    assert tb_detector._name_hygiene(text, 0, len(text)) == [(0, len(text))]


def test_land_abbreviation_line_does_not_discard_the_person_line():
    text = "น.ส.3ก เดิม\nเจ้าของที่ดิน สุทธิดา อินทรกำแหง"
    name = "เจ้าของที่ดิน สุทธิดา อินทรกำแหง"
    assert tb_detector._name_hygiene(text, 0, len(text)) == [(text.index(name), len(text))]

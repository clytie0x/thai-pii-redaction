"""Retain the SDK's field-label guards without adding sensitive masking."""

import pytest

from pii_redactor import leak_guard
from pii_redactor.config import CoreConfig
from pii_redactor.models import Entity

CONFIG = CoreConfig(allow_remote=False)


@pytest.mark.parametrize("label", ["เลขบัตรประชาชน", "เลขผู้เสียภาษี"])
def test_known_field_name_is_not_a_primary_or_segment_name_leak(monkeypatch, label):
    calls = []
    entity = Entity("synthetic", "TB", "NAME", (0, len(label)), 1.0, label)

    def detect(text, *, config):
        calls.append((text, config))
        return [entity]

    monkeypatch.setattr(leak_guard, "detect_tb", detect)
    monkeypatch.setattr(leak_guard, "detect_fp", lambda text: [])
    assert (
        leak_guard.scan_outbound_leaks(label, leak_guard.OutboundGuardContext(), config=CONFIG)
        == []
    )
    assert leak_guard._segment_leaks(label, config=CONFIG) == []
    assert calls == [(label, CONFIG), (label, CONFIG)]


def test_segment_guard_keeps_a_real_name_and_structured_identifier():
    names = leak_guard._segment_leaks("นายอานนท์ สุขใจ", config=CONFIG)
    assert any(entity.data_type == "NAME" for entity in names)
    structured = leak_guard._segment_leaks("เลขบัตรประชาชน 0000000000001", config=CONFIG)
    assert any(entity.data_type == "THAI_ID" for entity in structured)


def test_field_label_gate_does_not_excuse_other_entity_types(monkeypatch):
    entity = Entity("synthetic", "FP", "PHONE", (0, 3), 1.0, "เลขบัตรประชาชน")
    monkeypatch.setattr(leak_guard, "detect_tb", lambda text, *, config: [])
    monkeypatch.setattr(leak_guard, "detect_fp", lambda text: [entity])
    assert leak_guard.scan_outbound_leaks(
        "synthetic", leak_guard.OutboundGuardContext(), config=CONFIG
    ) == [entity]
    assert leak_guard._segment_leaks("synthetic", config=CONFIG) == [entity]

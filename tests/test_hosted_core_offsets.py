"""Safe offset metadata needed by the Hosted generated-PII projection."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from pii_redactor import output_validator, stateless
from pii_redactor.anonymizer.token_generator import generate_token
from pii_redactor.config import CoreConfig
from pii_redactor.models import Entity, EntityRegistry, ReverseResult
from pii_redactor.session_vault import SessionVault


def entity(span):
    return Entity("synthetic", "TB", "NAME", span, 1.0, "synthetic")


def test_leak_error_keeps_only_valid_integer_offset_metadata():
    marker = "SYNTHETIC-TEXT-MUST-NOT-BE-RETAINED"
    error = output_validator.PIILeakError(
        marker,
        count=True,
        spans=[(1, 3), (True, 5), (4, 4), (-1, 3), (2, marker), [4, 7], marker, (5, 10)],
    )
    assert error.count == 1
    assert error.spans == ((1, 3), (5, 10))
    assert error.spans_complete is False
    assert marker not in repr(error.__dict__) + repr(error.args) + str(error)


def test_validation_reports_only_untrusted_parts_of_crossing_spans(monkeypatch):
    text = "xxSYNTHETICyy"
    vault = SessionVault()
    vault.seed("SYNTHETIC-PSEUDONYM", "SYNTHETIC")
    config = CoreConfig(engine="thainer", allow_remote=False)
    seen = []

    def detect(value, *, config):
        seen.append(config)
        assert value == text
        return [entity((0, len(text)))]

    monkeypatch.setattr(output_validator, "detect_all", detect)
    monkeypatch.setattr(output_validator, "scan_obfuscated_structured_entities", lambda _text: [])
    try:
        with pytest.raises(output_validator.PIILeakError) as raised:
            output_validator.validate_output(
                ReverseResult(text, restored_ranges=((2, 11),)),
                EntityRegistry([], 0, 0),
                vault,
                config=config,
            )
        assert raised.value.count == 1
        assert raised.value.spans == ((0, 2), (11, 13))
        assert raised.value.spans_complete is True
        assert seen == [config]
    finally:
        vault.clear()


def test_same_value_outside_authoritative_restoration_is_still_untrusted(monkeypatch):
    text = "SYNTHETIC SYNTHETIC"
    vault = SessionVault()
    vault.seed("SYNTHETIC-PSEUDONYM", "SYNTHETIC")
    monkeypatch.setattr(
        output_validator, "detect_all", lambda _text, **_kwargs: [entity((0, 9)), entity((10, 19))]
    )
    monkeypatch.setattr(output_validator, "scan_obfuscated_structured_entities", lambda _text: [])
    try:
        with pytest.raises(output_validator.PIILeakError) as raised:
            output_validator.validate_output(
                ReverseResult(text, restored_ranges=((0, 9),)), EntityRegistry([], 0, 0), vault
            )
        assert raised.value.count == 1
        assert raised.value.spans == ((10, 19),)
    finally:
        vault.clear()


@pytest.mark.parametrize("ranges", [((0, 10), (10, 12)), ((0, 10), (9, 12)), ((10, 12), (0, 10))])
def test_union_of_authoritative_ranges_covers_a_detected_span(monkeypatch, ranges):
    text = "081-234-5678"
    vault = SessionVault()
    for index, (start, end) in enumerate(ranges):
        vault.seed(f"SYNTHETIC-PSEUDONYM-{index}", text[start:end])
    monkeypatch.setattr(
        output_validator, "detect_all", lambda _text, **_kwargs: [entity((0, len(text)))]
    )
    monkeypatch.setattr(output_validator, "scan_obfuscated_structured_entities", lambda _text: [])
    try:
        result = output_validator.validate_output(
            ReverseResult(text, restored_ranges=ranges), EntityRegistry([], 0, 0), vault
        )
        assert result.layer1_pii_clean
    finally:
        vault.clear()


def test_one_character_gap_in_authoritative_union_still_blocks(monkeypatch):
    text = "081-234-5678"
    ranges = ((0, 9), (10, 12))
    vault = SessionVault()
    for index, (start, end) in enumerate(ranges):
        vault.seed(f"SYNTHETIC-PSEUDONYM-{index}", text[start:end])
    monkeypatch.setattr(
        output_validator, "detect_all", lambda _text, **_kwargs: [entity((0, len(text)))]
    )
    monkeypatch.setattr(output_validator, "scan_obfuscated_structured_entities", lambda _text: [])
    try:
        with pytest.raises(output_validator.PIILeakError) as raised:
            output_validator.validate_output(
                ReverseResult(text, restored_ranges=ranges), EntityRegistry([], 0, 0), vault
            )
        assert raised.value.count == 1
        assert raised.value.spans == ((9, 10),)
    finally:
        vault.clear()


def test_stateless_offsets_are_bounded_and_retained_exception_is_scrubbed(monkeypatch):
    token = generate_token("NAME", 1, namespace="a" * 25, nonce="b" * 20)
    error = output_validator.PIILeakError(
        "SYNTHETIC-NOT-RETAINED", count=2, spans=((0, 2), (9, 999)), spans_complete=True
    )
    seen = []
    config = CoreConfig(engine="thainer", allow_remote=False)

    def reject(_result, _registry, _vault, *, config):
        seen.append(config)
        raise error

    monkeypatch.setattr(stateless, "validate_output", reject)
    output = stateless.restore_stateless(
        token, mapping={token: "SYNTHETIC"}, mode="token", config=config
    )
    assert output.generated_pii_count == 2
    assert output.generated_pii_spans == ()
    assert output.generated_pii_spans_complete is False
    assert output.restored_text == "SYNTHETIC"
    assert seen == [config]
    assert error.__dict__ == {}
    assert error.args == ()
    assert error.__traceback__ is error.__context__ is error.__cause__ is None
    assert asdict(output)["generated_pii_spans"] == ()


@pytest.mark.parametrize("invalid", [(True, 4), (-1, 4), (2, 999), ("bad", 4), ()])
def test_actual_validator_marks_partial_multi_finding_metadata_untrusted(monkeypatch, invalid):
    token = generate_token("NAME", 1, namespace="a" * 25, nonce="b" * 20)
    monkeypatch.setattr(
        stateless, "reverse_map", lambda *_args, **_kwargs: ReverseResult("SYNTHETIC")
    )
    monkeypatch.setattr(
        output_validator, "detect_all", lambda _text, **_kwargs: [entity((0, 2)), entity(invalid)]
    )
    monkeypatch.setattr(output_validator, "scan_obfuscated_structured_entities", lambda _text: [])
    output = stateless.restore_stateless(token, mapping={token: "SYNTHETIC"}, mode="token")
    assert output.generated_pii_count == 2
    assert output.generated_pii_spans_complete is False
    assert output.generated_pii_spans == ()


def test_complete_split_metadata_does_not_equal_finding_count(monkeypatch):
    token = generate_token("NAME", 1, namespace="a" * 25, nonce="b" * 20)
    error = output_validator.PIILeakError(count=1, spans=((0, 2), (5, 9)), spans_complete=True)

    def reject(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(stateless, "validate_output", reject)
    output = stateless.restore_stateless(token, mapping={token: "SYNTHETIC"}, mode="token")
    assert output.generated_pii_count == 1
    assert output.generated_pii_spans == ((0, 2), (5, 9))
    assert output.generated_pii_spans_complete is True
    assert error.__dict__ == {} and error.args == ()
    assert error.__traceback__ is error.__context__ is error.__cause__ is None


def test_cleanup_failure_does_not_retain_offsets_or_source(monkeypatch):
    token = generate_token("NAME", 1, namespace="a" * 25, nonce="b" * 20)
    error = output_validator.PIILeakError(count=1, spans=((0, 2),))

    def reject(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(stateless, "validate_output", reject)
    monkeypatch.setattr(stateless, "_clear_throwaway_vault", lambda _vault: False)
    with pytest.raises(stateless.StatelessProcessingError) as raised:
        stateless.restore_stateless(token, mapping={token: "SYNTHETIC"}, mode="token")
    assert str(raised.value) == "stateless restore failed"
    assert raised.value.__context__ is raised.value.__cause__ is None
    assert error.__dict__ == {}
    assert error.args == ()
    assert error.__traceback__ is error.__context__ is error.__cause__ is None

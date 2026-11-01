"""Freeze checks for the reproducible blind-v2 comparison set.

Failures report error kinds and counts, not document text or entity values.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from benchmark.blind_v2.corpus import (
    GENERATION_SEED,
    LOCK_PATH,
    VERSION,
    _thai_id,
    corpus_sha256,
    generate_corpus,
    iban_from_bban,
    load_lock,
    luhn_complete,
    public_lock,
    validate_corpus,
)
from benchmark.blind_v2.types import REDACTION_TYPES, SECTION26_TYPES

ROOT = Path(__file__).resolve().parents[1]


def test_generation_is_deterministic_and_valid():
    first = generate_corpus()
    second = generate_corpus()
    assert first.seed == GENERATION_SEED
    assert first.version == VERSION
    assert corpus_sha256(first) == corpus_sha256(second)
    assert validate_corpus(first) == []
    assert corpus_sha256(generate_corpus(seed=GENERATION_SEED + 1)) != corpus_sha256(first)


def test_committed_lock_matches_regeneration_and_hides_labels():
    corpus = generate_corpus()
    lock = load_lock()
    assert lock == public_lock(corpus)
    assert lock["labels_committed"] is False
    assert lock["seed"] == GENERATION_SEED
    assert lock["plaintext_sha256"] == corpus_sha256(corpus)
    assert LOCK_PATH.name == "blind-v2-repro.lock.json"

    def _walk(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from _walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from _walk(item)

    for text in _walk(lock):
        assert "@" not in text
        assert not any("\u0e00" <= char <= "\u0e7f" for char in text)


def test_every_redaction_type_and_robustness_case_is_present():
    corpus = generate_corpus()
    counts = Counter(span.entity_type for doc in corpus.documents for span in doc.spans)
    for entity_type in REDACTION_TYPES:
        assert counts[entity_type] >= 8, entity_type

    styles = {doc.style for doc in corpus.documents}
    for style in (
        "adv_grouped_space",
        "adv_every_space",
        "adv_zwsp",
        "adv_thai_digits",
        "adv_arabic_digits",
        "adv_ocr",
        "mixed_email",
        "negative",
    ):
        assert style in styles

    assert sum(doc.slice == "negative" for doc in corpus.documents) >= 12
    assert any(len(doc.text) > 500 for doc in corpus.documents if doc.style == "long_memo")
    assert any("\u200b" in doc.text for doc in corpus.documents if doc.style == "adv_zwsp")
    assert any(
        any("\u0e50" <= char <= "\u0e59" for char in doc.text)
        for doc in corpus.documents
        if doc.style == "adv_thai_digits"
    )
    assert any(
        any("\u0660" <= char <= "\u0669" for char in doc.text)
        for doc in corpus.documents
        if doc.style == "adv_arabic_digits"
    )
    assert any(
        "O" in doc.text[span.start : span.end]
        for doc in corpus.documents
        if doc.style == "adv_ocr"
        for span in doc.spans
        if span.entity_type == "THAI_ID"
    )
    assert sum(len(doc.questions) for doc in corpus.documents) >= 12


def test_section26_categories_are_warn_labels_not_redaction_spans():
    corpus = generate_corpus()
    found = Counter(category for doc in corpus.documents for category in doc.section26)
    for category in SECTION26_TYPES:
        assert found[category] >= 1, category
    redaction_types = {span.entity_type for doc in corpus.documents for span in doc.spans}
    assert redaction_types.isdisjoint(SECTION26_TYPES)


def test_detector_packages_do_not_import_the_freeze():
    for root_name in ("pii_redactor", "app"):
        for path in (ROOT / root_name).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "blind_v2" not in text, path.as_posix()
            assert "blind-v2-repro" not in text, path.as_posix()


def test_sealed_protocol_corpus_is_a_different_artifact():
    sealed = json.loads((ROOT / "benchmark" / "data" / "blind-v2.lock.json").read_text())
    repro = load_lock()
    assert sealed["version"] == "blind-v2"
    assert sealed["plaintext_sha256"] == (
        "a4503b4e3596dd56af19aef137ec25d2429ee8c09a9e4c94eb43d411ec6e56a5"
    )
    assert sealed["ciphertext_sha256"] == (
        "d6fdd3713d7d72e456f19903f11533d3728c79b382048e693d357ab79aa529fe"
    )
    assert repro["plaintext_sha256"] != sealed["plaintext_sha256"]
    assert repro["sealed_corpus_untouched"] == "benchmark/data/blind-v2.enc"


def test_checksum_helpers_match_their_public_formulas():
    assert luhn_complete("411111111111111") == "4111111111111111"
    digits = _thai_id(random.Random(0))
    body = digits[:12]
    total = sum(int(body[i]) * (13 - i) for i in range(12))
    check = str((11 - (total % 11)) % 10)
    assert len(digits) == 13 and digits.isdigit() and digits[-1] == check
    iban = iban_from_bban("DE", "100000001000000000")
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    assert int(numeric) % 97 == 1


def test_self_check_command_stays_quiet(capsys):
    from benchmark.blind_v2.__main__ import main

    assert main(["--self-check"]) == 0
    captured = capsys.readouterr()
    assert "sha256=" in captured.out
    assert "@" not in captured.out
    assert "สมชาย" not in captured.out

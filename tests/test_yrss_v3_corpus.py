"""Family splits, seeds, and determinism for the YRSS evaluation v3 generator."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.yrss_v2.types import SCHEME_TYPES
from benchmark.yrss_v3 import families
from benchmark.yrss_v3.corpus import (
    SEEDS,
    VARIANTS,
    CorpusSealError,
    build_public,
    check_public,
    disjointness_errors,
    render_split,
    template_bytes,
    validate_documents,
    validate_templates,
)
from benchmark.yrss_v3.protocol import KEY_ENV
from benchmark.yrss_v3.qi import QI_KINDS, catalog_section26

_ROOT = Path(__file__).resolve().parents[1]
_DOMAINS = {"clinical_note", "gov_form", "chat", "insurance"}


def test_seeds_and_variants_are_the_registered_maps():
    assert SEEDS == {"train": 20261117, "dev": 20261118, "test": 20261119}
    assert VARIANTS == {"train": 2, "dev": 2, "test": 2}
    assert KEY_ENV == "YRSS_V3_TEST_KEY_FILE"


def test_families_do_not_cross_splits_or_touch_v2_dev():
    assert disjointness_errors() == []
    seen: dict[str, str] = {}
    for split in families.SPLITS:
        for template in families.templates(split):
            assert template.family not in seen
            seen[template.family] = split
            assert template.family.startswith(f"v3-{split}-")
    assert set(seen) == {template.family for template in families.all_templates()}


def test_each_split_covers_the_four_domains_and_rejects_its_own_templates_as_clean():
    for split in families.SPLITS:
        rows = families.templates(split)
        assert _DOMAINS <= {template.genre for template in rows}
        assert validate_templates(rows) == []
        assert any(template.negative for template in rows)
        assert any(not template.negative for template in rows)


def test_each_split_covers_the_eleven_types_and_the_section26_catalog():
    fingerprint = b"\x11" * 32
    for split in families.SPLITS:
        kwargs = {"fingerprint": fingerprint} if split == "test" else {}
        documents = render_split(split, **kwargs)
        assert validate_documents(documents) == []
        types = {span.entity_type for doc in documents for span in doc.spans}
        assert types == set(SCHEME_TYPES)
        labels = {span.section26 for doc in documents for span in doc.qi if span.section26}
        assert labels == set(catalog_section26())
        qi_types = {span.qi_type for doc in documents for span in doc.qi}
        assert qi_types == set(QI_KINDS)


def test_public_splits_are_deterministic_and_ignore_a_key(monkeypatch):
    monkeypatch.setenv(KEY_ENV, "/tmp/yrss-v3-does-not-exist.key")
    first = build_public("dev")
    second = build_public("dev")
    assert first == second
    assert render_split("train") == render_split("train")
    variant = render_split("dev")
    other = [doc for doc in variant if doc.family == "v3-dev-01"]
    assert other[0].text != other[1].text


def test_test_render_requires_a_fingerprint_and_is_stable_for_one_key():
    fingerprint = bytes(range(32))
    with_key = render_split("test", fingerprint=fingerprint)
    assert with_key == render_split("test", fingerprint=fingerprint)
    assert with_key != render_split("test", fingerprint=b"\x02" * 32)
    try:
        render_split("test")
    except CorpusSealError as exc:
        assert str(exc) == "test-requires-key"
    else:
        raise AssertionError("test-rendered-without-key")
    try:
        render_split("dev", fingerprint=fingerprint)
    except CorpusSealError as exc:
        assert str(exc) == "key-not-used-on-this-split"
    else:
        raise AssertionError("dev-accepted-a-key")


def test_keyed_placeholder_repeats_one_value():
    named = next(doc for doc in render_split("train") if doc.family == "v3-train-03")
    surfaces = [
        named.text[span.start : span.end] for span in named.spans if span.entity_type == "NAME"
    ]
    assert surfaces[0] == surfaces[1]
    nick_doc = next(doc for doc in render_split("train") if doc.family == "v3-train-05")
    nicks = [
        nick_doc.text[span.start : span.end] for span in nick_doc.qi if span.qi_type == "nickname"
    ]
    assert nicks[0] == nicks[1]


def test_committed_train_and_dev_match_the_generator_and_hide_values():
    for split in ("train", "dev"):
        path = _ROOT / "benchmark" / "data" / "yrss-v3" / f"{split}-templates.jsonl"
        assert path.read_bytes() == template_bytes(split)
        lock = check_public(split)
        blob = (_ROOT / "benchmark" / "data" / "yrss-v3" / f"{split}.lock.json").read_text(
            encoding="utf-8"
        )
        assert "ciphertext_sha256" not in json.loads(blob)
        for doc in build_public(split):
            for span in doc.spans:
                assert doc.text[span.start : span.end] not in blob
        assert lock["seed"] == SEEDS[split]
        assert lock["families"] * lock["variants_per_family"] == lock["documents"]


def test_generator_source_does_not_name_the_v2_ciphertext_or_a_detector():
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in (_ROOT / "benchmark" / "yrss_v3").glob("*.py")
    )
    for banned in ("yrss-v2-test", "YRSS_V2_TEST_KEY_FILE", "pii_redactor.detectors", "detect_all"):
        assert banned not in text


def test_adr_records_the_seeds_the_command_and_the_operating_points():
    adr = (_ROOT / "docs" / "decisions" / "2026-11-17-yrss-eval-v3.md").read_text(encoding="utf-8")
    for seed in SEEDS.values():
        assert str(seed) in adr
    assert "YRSS_V3_TEST_KEY_FILE=/path/to/keyfile python -m benchmark.yrss_v3 seal" in adr
    for name in ("recall-first", "balanced", "precision-first"):
        assert name in adr
    assert "scored exactly once" in adr
    assert "secondary" in adr

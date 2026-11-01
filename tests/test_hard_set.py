"""Freeze checks for the harder dev and test splits."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.blind_v2.hard_set import (
    DEV_SEED,
    TEST_SEED,
    generate_hard,
    lock_path,
    public_lock,
    validate_hard,
)

ROOT = Path(__file__).resolve().parents[1]


def test_hard_splits_are_frozen_and_distinct():
    dev = generate_hard("dev")
    test = generate_hard("test")
    assert dev.seed == DEV_SEED
    assert test.seed == TEST_SEED
    assert validate_hard(dev) == []
    assert validate_hard(test) == []
    assert public_lock(dev) == json.loads(lock_path("dev").read_text(encoding="utf-8"))
    assert public_lock(test) == json.loads(lock_path("test").read_text(encoding="utf-8"))
    assert public_lock(dev)["plaintext_sha256"] != public_lock(test)["plaintext_sha256"]
    assert dev.documents[0].text != test.documents[0].text


def test_hard_locks_hide_surface_forms():
    for split in ("dev", "test"):
        text = lock_path(split).read_text(encoding="utf-8")
        assert "@" not in text
        assert not any("\u0e00" <= char <= "\u0e7f" for char in text)


def test_detector_packages_do_not_import_the_hard_test_split():
    for root_name in ("pii_redactor", "app"):
        for path in (ROOT / root_name).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "hard_set" not in source
            assert "hard-test.lock" not in source

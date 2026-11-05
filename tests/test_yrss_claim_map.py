"""The YRSS claim map must quote stored scores and keep their citation limits.

The test reads committed JSON and the lock files. It does not score a corpus
and it does not open a sealed blob.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIM = ROOT / "research" / "yrss2026" / "CLAIM-MAP.md"
METHODS = ROOT / "research" / "yrss2026" / "METHODS-RESULTS.md"
BASELINE = ROOT / "research" / "yrss2026" / "baseline.json"
HELDOUT = ROOT / "research" / "yrss2026" / "heldout-paired.json"
HARD = ROOT / "docs" / "benchmark" / "runs" / "hard-test.json"
SCORES = ROOT / "benchmark" / "data" / "blind-scores.jsonl"
BLIND_LOCK = ROOT / "benchmark" / "data" / "blind-v2.lock.json"
HOLDOUT_LOCK = ROOT / "benchmark" / "data" / "yrss-holdout-v1.lock.json"
HARD_LOCK = ROOT / "benchmark" / "data" / "hard-test.lock.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _blind_reveal() -> dict:
    found = []
    for line in SCORES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("version") == "blind-v2":
            found.append(row)
    assert len(found) == 1
    return found[0]


def _must_contain(path: Path, snippets: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    assert not missing, missing


def test_claim_map_quotes_stored_headline_floats() -> None:
    baseline = _load(BASELINE)
    heldout = _load(HELDOUT)
    hard = _load(HARD)
    reveal = _blind_reveal()
    gold = baseline["arms"]["full"]["metrics"]["overall"]
    base = heldout["baseline"]["metrics"]["overall"]
    candidate = heldout["candidate"]["metrics"]["overall"]
    micro = next(row for row in hard["systems"] if row["name"] == "aiguard")["micro"]
    blind = reveal["metrics"]["overall"]

    assert f"{gold['f2']:.3f}" == "0.947"
    assert f"{base['f2']:.3f}" == "0.834"
    assert f"{candidate['f2']:.3f}" == "0.871"
    assert f"{blind['f2']:.3f}" == "0.799"
    assert f"{micro['f1']:.3f}" == "0.971"
    assert f"{micro['f2']:.3f}" == "0.965"

    _must_contain(
        CLAIM,
        [
            str(gold["f2"]),
            str(gold["f1"]),
            str(gold["precision"]),
            str(gold["recall"]),
            str(base["f2"]),
            str(base["f1"]),
            str(candidate["f2"]),
            str(candidate["f1"]),
            str(blind["f2"]),
            str(blind["f1"]),
            str(blind["precision"]),
            str(blind["recall"]),
            str(micro["f1"]),
            str(micro["f2"]),
            str(micro["precision"]),
            str(micro["recall"]),
            baseline["manifest"]["corpus_sha256"],
            _load(BLIND_LOCK)["plaintext_sha256"],
            _load(BLIND_LOCK)["ciphertext_sha256"],
            _load(HOLDOUT_LOCK)["plaintext_sha256"],
            _load(HOLDOUT_LOCK)["ciphertext_sha256"],
            _load(HARD_LOCK)["plaintext_sha256"],
            hard["dataset"]["plaintext_sha256"],
        ],
    )


def test_claim_map_keeps_citation_limits() -> None:
    text = CLAIM.read_text(encoding="utf-8").lower()
    assert "dev only" in text or "development set" in text
    assert "true held-out" in text
    assert "not a held-out substitute" in text
    assert "may not" in text
    assert "unverified" in text or "absent" in text


def test_sealed_blind_v2_reveal_matches_its_lock() -> None:
    reveal = _blind_reveal()
    lock = _load(BLIND_LOCK)
    assert reveal["ciphertext_sha256"] == lock["ciphertext_sha256"]
    assert reveal["corpus_sha256"] == lock["plaintext_sha256"]
    assert reveal["reveal_index"] == 1
    assert reveal["over_budget"] is False
    assert lock["version"] == "blind-v2"


def test_methods_report_f1_beside_f2_and_the_limits() -> None:
    hard = _load(HARD)
    section = hard["section26"]
    assert section["micro_recall"] == 0.0
    assert section["n"] == 8
    _must_contain(
        METHODS,
        [
            "F1",
            "F2",
            "0.9469240048250904",
            "0.7991604778818212",
            "0.8335633452939553",
            "0.8707557502738226",
            "0.970873786407767",
            "0.9652509652509652",
            "d93d10b",
            "Section 26",
            "gemma",
            "not reopened",
            "fp",
            "tb",
            "address_merge",
        ],
    )

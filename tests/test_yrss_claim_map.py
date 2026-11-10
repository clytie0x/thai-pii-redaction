"""The YRSS claim map must quote stored scores and keep their citation limits.

The test reads committed JSON and the lock files. It does not score a corpus
and it does not open a sealed blob.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from benchmark.types import SHARED_ENTITY_TYPES

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
GEMMA_RUNS = ROOT / "docs" / "benchmark" / "runs"
_METRIC_KEYS = ("tp", "fp", "fn", "precision", "recall", "f1", "f2")
_METRIC_LABELS = ("tp", "fp", "fn", "P", "R", "F1", "F2")
_FREEZE_SHA = "ce0b88a3dd2281133f85ddbcdc38a5498f83865754e5bb77510bd12553ce8624"
_HARD_SHA = "90749a8891d42b924bbfbbb690f9637ab599867013f27c4a3ed459e8f3aaca11"
_HOLDOUT_TYPES = ("CREDIT_CARD", "PHONE", "STUDENT_ID")
_SEALED_COMMAND = (
    "import json, pathlib; "
    "row=json.loads(pathlib.Path('benchmark/data/blind-scores.jsonl').read_text(encoding='utf-8').splitlines()[6]); "
    "types=('THAI_ID','PHONE','EMAIL','BANK_ACCOUNT','CREDIT_CARD','PASSPORT','VEHICLE_PLATE','STUDENT_ID','DATE_OF_BIRTH','NAME','ADDRESS'); "
    "by=row['metrics']['by_type']; "
    "print('\\n'.join(t+' '+str(by[t]['tp'])+'/'+str(by[t]['n']) for t in types)); "
    "print(str(by['OUT_OF_SCHEME']['fp'])+' of '+str(row['metrics']['overall']['fp'])); "
    "print(str(row['metrics']['shared_11']['excluded_predictions'])); "
    "neg=row['metrics']['negative']; "
    "print(str(neg['clean_docs'])+'/'+str(neg['documents']))"
)
_HOLDOUT_COMMAND = (
    "import json, pathlib; "
    "d=json.loads(pathlib.Path('research/yrss2026/heldout-paired.json').read_text(encoding='utf-8')); "
    "types=('CREDIT_CARD','PHONE','STUDENT_ID'); "
    "b=d['baseline']['metrics']; "
    "c=d['candidate']['metrics']; "
    "print('\\n'.join(t+' '+str(b['by_type'][t]['tp'])+'/'+str(b['corpus']['by_type'][t])+' to '+str(c['by_type'][t]['tp'])+'/'+str(c['corpus']['by_type'][t]) for t in types)); "
    "n=b['by_slice']['negative']; "
    "m=c['by_slice']['negative']; "
    "print(str(n['clean_docs'])+'/'+str(n['documents'])+' and '+str(m['clean_docs'])+'/'+str(m['documents']))"
)


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


def _run_claim_command(code: str) -> str:
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert completed.stderr == ""
    return completed.stdout


def test_claim_map_quotes_stored_type_counts() -> None:
    """Per-type recall rows must match line 7 and the closed holdout file."""
    lines = SCORES.read_text(encoding="utf-8").splitlines()
    reveal = json.loads(lines[6])
    assert reveal == _blind_reveal()
    assert reveal["version"] == "blind-v2"
    assert reveal["reveal_index"] == 1
    by_type = reveal["metrics"]["by_type"]
    assert len(SHARED_ENTITY_TYPES) == 11
    assert "(" + ",".join(repr(name) for name in SHARED_ENTITY_TYPES) + ")" in _SEALED_COMMAND
    type_lines = []
    for entity_type in SHARED_ENTITY_TYPES:
        row = by_type[entity_type]
        assert row["tp"] + row["fn"] == row["n"]
        type_lines.append(f"{entity_type} {row['tp']}/{row['n']}")
    outside = by_type["OUT_OF_SCHEME"]["fp"]
    total_fp = reveal["metrics"]["overall"]["fp"]
    inside = sum(by_type[entity_type]["fp"] for entity_type in SHARED_ENTITY_TYPES)
    assert inside + outside == total_fp
    assert reveal["metrics"]["shared_11"]["excluded_predictions"] == outside
    negative = reveal["metrics"]["negative"]
    sealed_negative = f"{negative['clean_docs']}/{negative['documents']}"

    heldout = _load(HELDOUT)
    moves = []
    for entity_type in _HOLDOUT_TYPES:
        before = heldout["baseline"]["metrics"]
        after = heldout["candidate"]["metrics"]
        before_count = before["by_type"][entity_type]
        after_count = after["by_type"][entity_type]
        before_n = before["corpus"]["by_type"][entity_type]
        after_n = after["corpus"]["by_type"][entity_type]
        assert before_count["tp"] + before_count["fn"] == before_n
        assert after_count["tp"] + after_count["fn"] == after_n
        moves.append(
            f"{entity_type} {before_count['tp']}/{before_n} to {after_count['tp']}/{after_n}"
        )
    base_neg = heldout["baseline"]["metrics"]["by_slice"]["negative"]
    cand_neg = heldout["candidate"]["metrics"]["by_slice"]["negative"]
    assert (base_neg["clean_docs"], base_neg["documents"]) == (
        cand_neg["clean_docs"],
        cand_neg["documents"],
    )
    holdout_negative = (
        f"{base_neg['clean_docs']}/{base_neg['documents']} and "
        f"{cand_neg['clean_docs']}/{cand_neg['documents']}"
    )

    assert _run_claim_command(_SEALED_COMMAND).splitlines() == [
        *type_lines,
        f"{outside} of {total_fp}",
        str(outside),
        sealed_negative,
    ]
    assert _run_claim_command(_HOLDOUT_COMMAND).splitlines() == [*moves, holdout_negative]
    _must_contain(
        CLAIM,
        [
            *type_lines,
            f"{outside} of {total_fp}",
            f"{inside} false positives are inside the 11 types",
            sealed_negative,
            "9/52, untouched stored negative slice",
            *moves,
            "23/35 to 23/35 in both arms",
            holdout_negative,
            "benchmark/data/blind-scores.jsonl",
            "line 7",
            "splitlines()[6]",
            "metrics.by_type.OUT_OF_SCHEME.fp",
            "metrics.overall.fp",
            "metrics.shared_11.excluded_predictions",
            "metrics.negative.clean_docs",
            "metrics.negative.documents",
            "research/yrss2026/heldout-paired.json",
            "baseline.metrics.by_type.CREDIT_CARD.tp",
            "baseline.metrics.corpus.by_type.CREDIT_CARD",
            "candidate.metrics.by_type.CREDIT_CARD.tp",
            "candidate.metrics.corpus.by_type.CREDIT_CARD",
            "baseline.metrics.by_type.PHONE.tp",
            "baseline.metrics.corpus.by_type.PHONE",
            "candidate.metrics.by_type.PHONE.tp",
            "candidate.metrics.corpus.by_type.PHONE",
            "baseline.metrics.by_type.STUDENT_ID.tp",
            "baseline.metrics.corpus.by_type.STUDENT_ID",
            "candidate.metrics.by_type.STUDENT_ID.tp",
            "candidate.metrics.corpus.by_type.STUDENT_ID",
            "baseline.metrics.by_slice.negative.clean_docs",
            "baseline.metrics.by_slice.negative.documents",
            "candidate.metrics.by_slice.negative.clean_docs",
            "candidate.metrics.by_slice.negative.documents",
            "payment card",
            f'python -c "{_SEALED_COMMAND}"',
            f'python -c "{_HOLDOUT_COMMAND}"',
        ],
    )


def _metric_line(prefix: str, micro: dict) -> str:
    parts = [prefix]
    for label, key in zip(_METRIC_LABELS, _METRIC_KEYS):
        parts.append(f"{label} {micro[key]}")
    return " ".join(parts)


def _mean_row(rows: list[dict]) -> dict:
    return {key: sum(row[key] for row in rows) / len(rows) for key in _METRIC_KEYS}


def _extreme_row(rows: list[dict], choose) -> dict:
    return {key: choose(row[key] for row in rows) for key in _METRIC_KEYS}


def _range_sentence(rows: list[dict]) -> str:
    mean = _mean_row(rows)
    low = _extreme_row(rows, min)
    high = _extreme_row(rows, max)
    bits = [
        f"{label} {mean[key]} (min {low[key]}, max {high[key]})"
        for label, key in zip(_METRIC_LABELS, _METRIC_KEYS)
    ]
    return "; ".join(bits)


def _llm_micro(path: Path, seed: int, documents: int, plaintext: str) -> dict:
    report = _load(path)
    system = report["systems"][0]
    assert system["name"] == "llm"
    assert system["status"] == "ok"
    assert system["sampling_seed"] == seed
    assert system["cost_usd"] == 0.0
    assert report["dataset"]["official"] is True
    assert report["dataset"]["documents"] == documents
    assert report["dataset"]["plaintext_sha256"] == plaintext
    assert report["ablations"] == {"status": "skipped", "reason": "disabled"}
    assert report["utility"]["status"] == "skipped"
    assert report["section26"]["status"] == "skipped"
    return system["micro"]


def test_gemma_seeded_claim_quotes_the_run_files() -> None:
    freeze = [
        _llm_micro(GEMMA_RUNS / f"gemma-freeze-seed-{seed}.json", seed, 82, _FREEZE_SHA)
        for seed in range(1, 6)
    ]
    hard = [
        _llm_micro(GEMMA_RUNS / f"gemma-hard-test-seed-{seed}.json", seed, 60, _HARD_SHA)
        for seed in range(1, 6)
    ]
    freeze_summary = _load(GEMMA_RUNS / "gemma-freeze-seeds.json")
    hard_summary = _load(GEMMA_RUNS / "gemma-hard-test-seeds.json")
    assert freeze_summary["mean"] == _mean_row(freeze)
    assert freeze_summary["min"] == _extreme_row(freeze, min)
    assert freeze_summary["max"] == _extreme_row(freeze, max)
    assert hard_summary["mean"] == _mean_row(hard)
    assert hard_summary["min"] == _extreme_row(hard, min)
    assert hard_summary["max"] == _extreme_row(hard, max)
    assert [row["seed"] for row in freeze_summary["runs"]] == [1, 2, 3, 4, 5]
    for row, micro in zip(freeze_summary["runs"], freeze):
        assert (
            row["sha256"]
            == hashlib.sha256(
                (GEMMA_RUNS / f"gemma-freeze-seed-{row['seed']}.json").read_bytes()
            ).hexdigest()
        )
        for key in _METRIC_KEYS:
            assert row[key] == micro[key]

    freeze_range = "Freeze mean±range: " + _range_sentence(freeze)
    hard_range = "Hard-test mean±range: " + _range_sentence(hard)
    shared = [
        freeze_range,
        hard_range,
        "F2 0.009 is an unreproduced historical print",
        "97558784bdc9175075a72655bf360b15da17df6b3b9e5182af9f8c0c8e58ba7c",
        "0.40.14",
        "temperature 1",
        "30b97690883f81897cb7c6bac7fa6c2b85c04c57",
        "python -m benchmark.blind_v2 --split freeze --systems llm --no-ablate --no-utility --no-section26 --llm-seed 1 --json docs/benchmark/runs/gemma-freeze-seed-1.json",
        "python -m benchmark.blind_v2 --split hard-test --systems llm --no-ablate --no-utility --no-section26 --llm-seed 1 --json docs/benchmark/runs/gemma-hard-test-seed-1.json",
        "443 seconds",
    ]
    _must_contain(CLAIM, shared)
    _must_contain(METHODS, shared)
    _must_contain(
        CLAIM,
        [_metric_line(f"seed {seed}", micro) for seed, micro in enumerate(freeze, start=1)]
        + [_metric_line(f"seed {seed}", micro) for seed, micro in enumerate(hard, start=1)],
    )


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

"""Score systems on one split of the YRSS evaluation v2.

The report holds counts, scores, intervals, timings, and hashes. It never
holds document text, document ids, or entity surface strings.
Protocol: docs/decisions/2026-11-13-yrss-eval-v2.md.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
import platform
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from benchmark.blind_v2.score import percentile, prf, score_predictions

from . import stats, systems
from .corpus import (
    SEEDS,
    Corpus,
    build_corpus,
    canonical_bytes,
    load_templates,
    lock_path,
    public_lock,
    validate_corpus,
    validate_templates,
)
from .types import SCHEME_TYPES

PROTOCOL = "docs/decisions/2026-11-13-yrss-eval-v2.md"
TEST_FLAG = "--i-understand-this-spends-the-test-split"

_ROOT = Path(__file__).resolve().parents[2]
# Files whose content decides a score. Their hashes go in every run file.
_HASHED_FILES = (
    "benchmark/blind_v2/score.py",
    "benchmark/blind_v2/ablate.py",
    "benchmark/blind_v2/baselines.py",
    "benchmark/yrss_v2/stats.py",
    "benchmark/yrss_v2/systems.py",
    "benchmark/yrss_v2/harness.py",
    "benchmark/yrss_v2/corpus.py",
    "benchmark/yrss_v2/values.py",
    "benchmark/yrss_v2/llm_openai.py",
)
_PACKAGES = (
    "pythainlp",
    "python-crfsuite",
    "transformers",
    "torch",
    "presidio-analyzer",
    "spacy",
    "en-core-web-sm",
    "numpy",
)
# Loads models before the timed documents. It is synthetic and is not scored.
_WARM_UP_TEXT = "นายตัวอย่าง ระบบ โทร 02-000-0000"


class TestSplitRefused(PermissionError):
    """The test split is scored once. It needs an explicit argument."""

    __test__ = False  # not a pytest class


class CorpusLockError(RuntimeError):
    """The built corpus is invalid or does not match its lock file."""


def run(
    split: str,
    systems_to_run: Sequence[str],
    *,
    llm_options: Mapping | None = None,
    allow_test: bool = False,
) -> dict:
    """Build the split, run each named system, and return the report."""
    if split not in SEEDS:
        raise ValueError(f"unknown split {split}")
    if split == "test" and not allow_test:
        raise TestSplitRefused(f"the test split is scored once; pass allow_test=True ({TEST_FLAG})")
    names = list(systems_to_run)
    if not names:
        raise ValueError("no system selected")
    if len(set(names)) != len(names):
        raise ValueError("a system is listed twice")
    unknown = [name for name in names if name not in systems.system_names()]
    if unknown:
        raise ValueError(f"unknown system {unknown[0]}")
    options = dict(llm_options) if llm_options else None

    corpus = _locked_corpus(split)
    # Build every system before any scoring, so a missing package stops the run early.
    predictors = {name: systems.build(name, llm_options=options) for name in names}
    report = evaluate(corpus, predictors)
    if "llm" in names and options:
        report["llm"] = {
            "api_key_env": options.get("api_key_env"),
            "base_url": options.get("base_url"),
            "model": options.get("model"),
            "seed": options.get("seed"),
        }
    return report


def evaluate(corpus: Corpus, predictors: Mapping[str, Callable[[str], list]]) -> dict:
    """Score ready predictors on a built corpus. ``run`` is the guarded entry point."""
    # The NER chunk warning names a label and a length, and it floods the output.
    logging.getLogger("pii_redactor.detectors.tb_detector").setLevel(logging.ERROR)
    documents = corpus.documents
    resamples = stats.family_resamples([document.family for document in documents])

    rows: dict[str, dict] = {}
    counts: dict[str, dict[str, list]] = {}
    for name, predict in predictors.items():
        predictions, latencies = _predict_all(predict, documents)
        counts[name] = {
            view: stats.view_counts(documents, predictions, view) for view in stats.VIEWS
        }
        rows[name] = _system_row(documents, predictions, latencies, counts[name], resamples)

    return {
        "bootstrap": {
            "interval": "95% percentile",
            "resamples": len(resamples.draws),
            "seed": resamples.seed,
            "unit": "family",
        },
        "corpus": {
            "documents": len(documents),
            "entities": sum(len(document.spans) for document in documents),
            "families": len(resamples.members),
            "negative_documents": sum(1 for document in documents if not document.spans),
            # Same value as plaintext_sha256 in the split's lock file.
            "plaintext_sha256": hashlib.sha256(canonical_bytes(corpus)).hexdigest(),
            "seed": corpus.seed,
            "version": corpus.version,
        },
        "environment": environment(),
        "paired": _paired(counts, resamples),
        "protocol": PROTOCOL,
        "scheme": list(SCHEME_TYPES),
        "split": corpus.split,
        "systems": rows,
    }


def git_commit() -> str:
    """Current commit, or ``unknown`` when git cannot say."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() or "unknown"


def _git_dirty() -> bool | None:
    """True when tracked files differ from the commit. None when git cannot say."""
    try:
        done = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bool(done.stdout.strip())


def environment() -> dict:
    packages = {}
    for package in _PACKAGES:
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    hashes = {}
    for relative in _HASHED_FILES:
        path = _ROOT / relative
        if path.is_file():
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "file_sha256": hashes,
        "git_commit": git_commit(),
        "git_dirty": _git_dirty(),
        "packages": packages,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "scorer_sha256": hashes.get("benchmark/blind_v2/score.py"),
    }


def render_report(report: dict) -> str:
    """A short table for the terminal. Scores only."""
    corpus = report["corpus"]
    lines = [
        f"yrss-eval-v2 split={report['split']} documents={corpus['documents']} "
        f"families={corpus['families']} sha256={corpus['plaintext_sha256']}",
        f"{'system':<26}{'view':<12}{'P':>7}{'R':>7}{'F1':>7}{'F2':>7}  F2 95% CI",
    ]
    for name, row in report["systems"].items():
        for view, score in row["views"].items():
            low, high = score["f2_ci"]
            lines.append(
                f"{name:<26}{view:<12}{score['precision']:>7.3f}{score['recall']:>7.3f}"
                f"{score['f1']:>7.3f}{score['f2']:>7.3f}  [{low:.3f}, {high:.3f}]"
            )
        negative = row["negative"]
        lines.append(
            f"  negative clean {negative['clean_docs']}/{negative['documents']} "
            f"false_positives={negative['false_positives']} "
            f"out_of_scheme_fp={row['out_of_scheme_false_positives']} "
            f"p50={row['latency_ms']['p50']:.1f}ms p95={row['latency_ms']['p95']:.1f}ms"
        )
    paired = report["paired"]
    if paired["comparisons"]:
        lines.append(f"paired F2 difference, {paired['direction']} (Holm: all view)")
        for name, views in paired["comparisons"].items():
            for view, row in views.items():
                low, high = row["f2_ci"]
                holm = "" if row["p_holm"] is None else f" p_holm={row['p_holm']:.4f}"
                lines.append(
                    f"  {name:<26}{view:<12}{row['f2_difference']:>+7.3f} "
                    f"[{low:+.3f}, {high:+.3f}] p={row['p_value']:.4f}{holm}"
                )
    return "\n".join(lines)


def _read_lock(split: str) -> dict:
    return json.loads(lock_path(split).read_text(encoding="utf-8"))


def _locked_corpus(split: str) -> Corpus:
    """Build the split and check it against its lock. A failed check is a failed run."""
    try:
        errors = validate_templates(load_templates(split))
        corpus = build_corpus(split)
        expected = _read_lock(split)
    except FileNotFoundError as exc:
        raise CorpusLockError(f"the {split} split has no templates or no lock file") from exc
    errors += validate_corpus(corpus)
    if errors:
        raise CorpusLockError(f"the {split} split is invalid: {','.join(sorted(set(errors)))}")
    if public_lock(corpus) != expected:
        raise CorpusLockError(f"the {split} split does not match its lock file")
    return corpus


def _predict_all(predict, documents) -> tuple[list[list], list[float]]:
    predict(_WARM_UP_TEXT)
    predictions = []
    latencies = []
    for document in documents:
        started = time.perf_counter()
        found = predict(document.text)
        latencies.append(time.perf_counter() - started)
        predictions.append([(int(start), int(end), str(label)) for start, end, label in found])
    return predictions, latencies


def _score(counts, resamples) -> dict:
    scored = prf(*stats.total(counts))
    low, high = stats.f2_interval(counts, resamples)
    return {
        "tp": scored["tp"],
        "fp": scored["fp"],
        "fn": scored["fn"],
        "precision": scored["precision"],
        "recall": scored["recall"],
        "f1": scored["f1"],
        "f2": scored["f2"],
        "f2_ci": [low, high],
    }


def _system_row(documents, predictions, latencies, view_counts, resamples) -> dict:
    scored = score_predictions(documents, predictions, types=SCHEME_TYPES)
    keys = ("n", "tp", "fp", "fn", "precision", "recall", "f1", "f2")
    return {
        "by_type": {
            entity_type: {key: scored["by_type"][entity_type][key] for key in keys}
            for entity_type in SCHEME_TYPES
        },
        "latency_ms": {
            "p50": percentile(latencies, 50) * 1000,
            "p95": percentile(latencies, 95) * 1000,
        },
        "negative": {
            "documents": scored["negative"]["documents"],
            "clean_docs": scored["negative"]["clean_docs"],
            "false_positives": scored["negative"]["false_positives"],
        },
        "out_of_scheme_false_positives": scored["other_false_positives"],
        "views": {view: _score(view_counts[view], resamples) for view in stats.VIEWS},
    }


def _paired(counts: dict, resamples) -> dict:
    """AI Guard minus each other system, over the shared family resamples."""
    reference = systems.REFERENCE
    family = [name for name in systems.COMPARATORS if name in counts]
    result = {
        "comparisons": {},
        "direction": "aiguard minus system",
        "holm_alpha": 0.05,
        "holm_family": family if reference in counts else [],
        "holm_view": "all",
        "reference": reference,
    }
    if reference not in counts:
        return result
    for name in counts:
        if name == reference:
            continue
        views = {}
        for view in stats.VIEWS:
            ours, theirs = counts[reference][view], counts[name][view]
            f2_row = stats.paired_difference(ours, theirs, resamples)
            recall_row = stats.paired_difference(ours, theirs, resamples, metric=stats.recall)
            views[view] = {
                "f2_difference": f2_row["difference"],
                "f2_ci": [f2_row["ci_low"], f2_row["ci_high"]],
                "p_value": f2_row["p_value"],
                "p_holm": None,
                "recall_difference": recall_row["difference"],
                "recall_ci": [recall_row["ci_low"], recall_row["ci_high"]],
            }
        result["comparisons"][name] = views
    raw = [result["comparisons"][name]["all"]["p_value"] for name in family]
    for name, adjusted in zip(family, stats.holm(raw)):
        result["comparisons"][name]["all"]["p_holm"] = adjusted
    return result

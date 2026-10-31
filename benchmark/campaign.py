"""Offline, value-free development evidence for the YRSS accuracy campaign.

This CLI deliberately has no blind-data input. Run it in one process without
concurrent requests: component interventions temporarily replace callables.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import socket
import subprocess
import time
from collections import Counter
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from .gold import GOLD_VERSION, load_gold
from .scorer import _prepare_predictions, _prf, _score_group, score
from .types import SHARED_ENTITY_TYPE_SET

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("format_only", "raw_crf", "without_name_context", "without_fn", "full")


def _json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()


def file_digest(path: Path) -> str:
    """Canonical UTF-8 text hashing across Windows and LF checkouts."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def prediction_digest(samples, predictions) -> str:
    if len(samples) != len(predictions):
        raise ValueError("prediction count mismatch")
    rows = [
        [s.template_id, hashlib.sha256(s.text.encode()).hexdigest(), sorted(p)]
        for s, p in zip(samples, predictions)
    ]
    return hashlib.sha256(_json_bytes(rows)).hexdigest()


def error_inventory(samples, predictions) -> dict:
    """Separate exposed characters, label errors, and boundary imprecision."""
    if len(samples) != len(predictions):
        raise ValueError("prediction count mismatch")
    summary = Counter()
    gold_errors, extra_predictions = [], []
    for sample, preds in zip(samples, predictions):
        for start, end, label in preds:
            if not (
                type(start) is int and type(end) is int and 0 <= start < end <= len(sample.text)
            ):
                raise ValueError("invalid prediction span")
            if not isinstance(label, str):
                raise ValueError("invalid prediction type")
        gold_chars = {i for g in sample.spans for i in range(g.start, g.end)}
        pred_chars = {i for start, end, _ in preds for i in range(start, end)}
        summary["gold_entities"] += len(sample.spans)
        summary["uncovered_characters"] += len(gold_chars - pred_chars)
        summary["overmasked_characters"] += len(pred_chars - gold_chars)
        for g in sample.spans:
            uncovered = len(set(range(g.start, g.end)) - pred_chars)
            overlaps = [p for p in preds if p[0] < g.end and g.start < p[1]]
            exact = (g.start, g.end, g.entity_type) in preds
            if exact:
                continue
            if uncovered == g.end - g.start:
                kind = "uncovered"
                summary["uncovered_entities"] += 1
            elif uncovered:
                kind = "partial_coverage"
                summary["partially_uncovered_entities"] += 1
            elif not any(p[2] == g.entity_type for p in overlaps):
                kind = "wrong_type_fully_covered"
            else:
                kind = "boundary_fully_covered"
            summary[kind] += 1
            gold_errors.append(
                {
                    "doc_id": sample.template_id,
                    "slice": sample.slice,
                    "type": g.entity_type,
                    "span": [g.start, g.end],
                    "kind": kind,
                    "uncovered_characters": uncovered,
                    "overlapping_predictions": [list(p) for p in overlaps],
                }
            )
        for start, end, label in preds:
            outside = len(set(range(start, end)) - gold_chars)
            out_of_scheme = label not in SHARED_ENTITY_TYPE_SET
            summary["out_of_scheme_predictions"] += int(out_of_scheme)
            if outside or out_of_scheme:
                extra_predictions.append(
                    {
                        "doc_id": sample.template_id,
                        "slice": sample.slice,
                        "type": label,
                        "span": [start, end],
                        "outside_gold_characters": outside,
                        "out_of_scheme": out_of_scheme,
                    }
                )
    for key in ("uncovered_entities", "partially_uncovered_entities", "out_of_scheme_predictions"):
        summary.setdefault(key, 0)
    return {
        "summary": dict(summary),
        "gold_errors": gold_errors,
        "extra_predictions": extra_predictions,
    }


def document_counts(samples, predictions) -> list[tuple[int, int, int]]:
    """Sufficient statistics for an isolated paired evaluator; never text."""
    error_inventory(samples, predictions)
    counts = []
    for sample, rows in zip(samples, _prepare_predictions(predictions, shared_only=False)):
        _, result = _score_group([sample], [rows])
        if result["gold_entities"] == 0:
            counts.append((0, result["false_positives"], 0))
        else:
            counts.append((result["tp"], result["fp"], result["fn"]))
    return counts


def paired_f2_interval(baseline, candidate, *, iterations: int = 1000, seed: int = 0) -> dict:
    if not baseline or len(baseline) != len(candidate) or iterations < 1:
        raise ValueError("paired evaluation requires complete document pairs")
    if any(
        len(row) != 3 or any(type(v) is not int or v < 0 for v in row)
        for row in [*baseline, *candidate]
    ):
        raise ValueError("invalid document counts")

    def f2(rows):
        tp, fp, fn = (sum(row[i] for row in rows) for i in range(3))
        return _prf(tp, fp, fn)["f2"]

    rng = random.Random(seed)
    differences = []
    for _ in range(iterations):
        indices = [rng.randrange(len(baseline)) for _ in baseline]
        differences.append(f2([candidate[i] for i in indices]) - f2([baseline[i] for i in indices]))
    differences.sort()
    return {
        "delta": f2(candidate) - f2(baseline),
        "lower": differences[int(0.025 * iterations)],
        "upper": differences[max(0, int(0.975 * iterations) - 1)],
        "confidence": 0.95,
        "iterations": iterations,
        "seed": seed,
        "unit": "document",
        "method": "paired percentile bootstrap, common document indices",
    }


@contextmanager
def offline():
    def denied(*args, **kwargs):
        raise RuntimeError("network disabled for campaign measurement")

    with ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"PYTHAINLP_OFFLINE": "1"}))
        for target in ("connect", "connect_ex"):
            stack.enter_context(patch.object(socket.socket, target, denied))
        stack.enter_context(patch.object(socket, "getaddrinfo", denied))
        yield


def predict_arm(samples, arm: str):
    from pii_redactor.detectors import aggregate, name_context, tb_detector

    from . import runner

    if arm not in ARMS:
        raise ValueError("unknown campaign arm")
    diagnostics = tb_detector.NERChunkDiagnostics()
    with ExitStack() as stack:
        if arm == "without_fn":
            stack.enter_context(patch.object(aggregate, "scan_fn", lambda *a: []))
        if arm == "without_name_context":
            for module, attr in (
                (name_context, "detect_name_context"),
                (name_context, "detect_conjunction_names"),
                (aggregate, "detect_parallel_record_names"),
            ):
                stack.enter_context(patch.object(module, attr, lambda *a: []))
        if arm == "format_only":
            predictions = [
                [(e.span[0], e.span[1], e.data_type) for e in aggregate.detect_fp(s.text)]
                for s in samples
            ]
        elif arm == "raw_crf":
            saved = dict(tb_detector._ner_cache)
            try:
                ner = tb_detector._load_ner("thainer")
                predictions = []
                for sample in samples:
                    diagnostics.attempted += 1
                    tagged = ner.tag(sample.text)
                    diagnostics.succeeded += 1
                    predictions.append(
                        [
                            (start, end, tb_detector.LABEL_MAP[label])
                            for _, start, end, label in tb_detector._bio_to_spans(
                                tagged, sample.text
                            )
                            if tb_detector.LABEL_MAP.get(label) is not None
                        ]
                    )
            finally:
                tb_detector._ner_cache = saved
        else:
            predictions = runner.predict_samples(samples, "crf", diagnostics=diagnostics)
    if diagnostics.skipped:
        raise runner.BenchmarkIntegrityError(diagnostics.as_dict())
    return predictions, diagnostics.as_dict()


def manifest() -> dict:
    from pythainlp.corpus import corpus_path, get_corpus_path

    model = Path(get_corpus_path("thainer-1.4"))
    model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
    asset_root = Path(corpus_path())
    assets = {
        p.relative_to(asset_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(asset_root.rglob("*"))
        if p.is_file() and p.suffix not in (".py", ".pyc")
    }
    sources = {
        p.relative_to(ROOT).as_posix(): file_digest(p)
        for p in sorted((ROOT / "pii_redactor").rglob("*.py"))
    }
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT))
    return {
        "schema": 1,
        "git": {"head": head, "dirty": dirty},
        "source_files": sources,
        "source_sha256": hashlib.sha256(_json_bytes(sources)).hexdigest(),
        "scorer_sha256": file_digest(ROOT / "benchmark/scorer.py"),
        "evaluator_sha256": {
            p.name: file_digest(p) for p in sorted((ROOT / "benchmark").glob("*.py"))
        },
        "corpus_sha256": file_digest(ROOT / "benchmark/data/gold.jsonl"),
        "requirements_sha256": file_digest(ROOT / "requirements.lock"),
        "model_sha256": {"thainer-1.4": model_hash},
        "pythainlp_assets_sha256": assets,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": dict(
            sorted(
                (d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions()
            )
        ),
        "engine": "thainer",
        "network": "socket connects and DNS denied; automatic corpus downloads disabled",
    }


def create_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def verify_identity(reference: dict, current: dict) -> None:
    for key in (
        "model_sha256",
        "source_sha256",
        "scorer_sha256",
        "corpus_sha256",
        "requirements_sha256",
        "packages",
        "python",
        "pythainlp_assets_sha256",
        "evaluator_sha256",
    ):
        if key not in reference or key not in current or reference[key] != current[key]:
            raise ValueError(f"identity mismatch: {key}")


def capture(path: Path, *, ablations: bool = False, expected: dict | None = None) -> dict:
    create_output(path)
    with offline():
        before = manifest()
        if expected is not None:
            verify_identity(expected, before)
        samples = load_gold()
        predictions, chunks = predict_arm(samples, "full")
        repeated, _ = predict_arm(samples, "full")
        digest = prediction_digest(samples, predictions)
        if prediction_digest(samples, repeated) != digest:
            raise RuntimeError("prediction reproducibility failure")
        reports = {}
        for arm in ARMS if ablations else ("full",):
            start = time.perf_counter()
            current, diag = (predictions, chunks) if arm == "full" else predict_arm(samples, arm)
            measured = time.perf_counter() - start if arm != "full" else None
            reports[arm] = {
                "metrics": score(samples, current),
                "diagnostics": diag,
                "prediction_sha256": prediction_digest(samples, current),
                "inventory": error_inventory(samples, current),
                "one_pass_seconds_including_model_load": measured,
            }
        after = manifest()
        if before != after:
            raise RuntimeError("measurement identity changed during run")
    result = {
        "manifest": before,
        "gold_version": GOLD_VERSION,
        "repeat_prediction_match": True,
        "arms": reports,
    }
    (path / "evidence.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument(
        "--expect", type=Path, help="refuse identity drift against a previous evidence.json"
    )
    args = parser.parse_args(argv)
    expected = (
        json.loads(args.expect.read_text(encoding="utf-8"))["manifest"] if args.expect else None
    )
    result = capture(args.out, ablations=args.ablations, expected=expected)
    for arm, data in result["arms"].items():
        overall = data["metrics"]["overall"]
        print(
            f"{arm}: F2={overall['f2']:.6f}; coverage={overall['coverage_recall']:.6f}; exact={overall['exact_recall']:.6f}"
        )
    print("Prediction repeat matched; evidence contains IDs/offsets/types/counts only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Provider-free evaluation of the exact hosted Thai PII detector path.

The module imports only local detection, protection, restoration, and Section 26
rules. It installs a process-wide network tripwire before importing the core,
removes credential-like environment variables, and emits only aggregate metrics
plus case IDs, offsets, and types. Corpus text, pseudonyms, mappings, and restored
content never enter the result artifact or stdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import platform
import re
import socket
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    import resource
except ImportError:  # pragma: no cover - evaluator runs in the Linux core image
    resource = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent
SECRET_ENV_MARKERS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "API_KEY",
    "ACCESS_KEY",
    "PRIVATE_KEY",
    "CREDENTIAL",
    "COOKIE",
)
ALLOWED_ENV = {
    "HOME",
    "HOSTNAME",
    "LANG",
    "LC_ALL",
    "PATH",
    "PYTHONPATH",
    "PYTHONUTF8",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONUNBUFFERED",
    "PYTHAINLP_DATA",
    "PYTHAINLP_OFFLINE",
    "TZ",
}
NETWORK_ATTEMPTS: list[str] = []


def _sanitize_environment() -> None:
    for key in list(os.environ):
        upper = key.upper()
        if key not in ALLOWED_ENV or any(marker in upper for marker in SECRET_ENV_MARKERS):
            os.environ.pop(key, None)
    os.environ["PYTHAINLP_OFFLINE"] = "1"


def _deny_network(*_args: Any, **_kwargs: Any) -> None:
    NETWORK_ATTEMPTS.append("blocked")
    raise RuntimeError("network disabled for Thai PII evaluation")


def _install_network_tripwire() -> None:
    socket.create_connection = _deny_network  # type: ignore[assignment]
    original_socket = socket.socket

    class OfflineSocket(original_socket):
        def connect(self, *_args: Any, **_kwargs: Any) -> None:
            _deny_network()

        def connect_ex(self, *_args: Any, **_kwargs: Any) -> int:
            _deny_network()
            return 1

    socket.socket = OfflineSocket  # type: ignore[assignment,misc]


def _canonical_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _case_hash(case: dict) -> str:
    return _sha256_bytes(case["text"].encode("utf-8"))[:16]


def _round(value: float) -> float:
    return round(value, 6)


def _ratio(numerator: int, denominator: int) -> float:
    return _round(numerator / denominator) if denominator else 0.0


def _prf(tp: int, fp: int, fn: int) -> dict[str, int | float]:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _round(2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    f2 = _round(5 * precision * recall / (4 * precision + recall)) if precision + recall else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "f2": f2,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return _round(ordered[rank - 1])


def _iou(left: dict, right: dict) -> float:
    intersection = max(0, min(left["end_cp"], right["end_cp"]) - max(left["start_cp"], right["start_cp"]))
    union = max(left["end_cp"], right["end_cp"]) - min(left["start_cp"], right["start_cp"])
    return intersection / union if union else 0.0


def _exact_keys(spans: Iterable[dict]) -> set[tuple[int, int, str]]:
    return {(item["start_cp"], item["end_cp"], item["type"]) for item in spans}


def _relaxed_matches(expected: list[dict], observed: list[dict]) -> int:
    candidates: list[tuple[float, int, int]] = []
    for expected_index, gold in enumerate(expected):
        for observed_index, prediction in enumerate(observed):
            if gold["type"] != prediction["type"]:
                continue
            score = _iou(gold, prediction)
            if score >= 0.5:
                candidates.append((-score, expected_index, observed_index))
    matched_expected: set[int] = set()
    matched_observed: set[int] = set()
    for _score, expected_index, observed_index in sorted(candidates):
        if expected_index in matched_expected or observed_index in matched_observed:
            continue
        matched_expected.add(expected_index)
        matched_observed.add(observed_index)
    return len(matched_expected)


def _normalized_fragment(text: str) -> str:
    return re.sub(r"[\s\-\u200b\u200c\u200d\ufeff]", "", text).casefold()


def _diagnose(case: dict, observed: list[dict]) -> list[dict]:
    expected = case["expected_spans"]
    unmatched_expected = set(range(len(expected)))
    unmatched_observed = set(range(len(observed)))
    ledger: list[dict] = []

    for expected_index, gold in enumerate(expected):
        for observed_index, prediction in enumerate(observed):
            if (
                gold["start_cp"] == prediction["start_cp"]
                and gold["end_cp"] == prediction["end_cp"]
                and gold["type"] == prediction["type"]
            ):
                unmatched_expected.discard(expected_index)
                unmatched_observed.discard(observed_index)
                break

    def record(category: str, gold: dict | None, prediction: dict | None) -> None:
        ledger.append(
            {
                "case_id": case["case_id"],
                "case_hash": _case_hash(case),
                "category": category,
                "expected_type": gold["type"] if gold else None,
                "observed_type": prediction["type"] if prediction else None,
                "expected_span": [gold["start_cp"], gold["end_cp"]] if gold else None,
                "observed_span": [prediction["start_cp"], prediction["end_cp"]] if prediction else None,
            }
        )

    for expected_index in sorted(list(unmatched_expected)):
        gold = expected[expected_index]
        same_span = next(
            (
                observed_index
                for observed_index in sorted(unmatched_observed)
                if observed[observed_index]["start_cp"] == gold["start_cp"]
                and observed[observed_index]["end_cp"] == gold["end_cp"]
            ),
            None,
        )
        if same_span is not None:
            record("wrong_type", gold, observed[same_span])
            unmatched_expected.remove(expected_index)
            unmatched_observed.remove(same_span)
            continue
        overlapping = [
            observed_index
            for observed_index in sorted(unmatched_observed)
            if observed[observed_index]["type"] == gold["type"] and _iou(gold, observed[observed_index]) > 0
        ]
        if overlapping:
            best = max(overlapping, key=lambda index: (_iou(gold, observed[index]), -index))
            prediction = observed[best]
            if prediction["start_cp"] <= gold["start_cp"] and prediction["end_cp"] >= gold["end_cp"]:
                category = "overextended_span"
            elif gold["start_cp"] <= prediction["start_cp"] and gold["end_cp"] >= prediction["end_cp"]:
                category = "partial_span"
            else:
                category = "boundary_mismatch"
            record(category, gold, prediction)
            unmatched_expected.remove(expected_index)
            unmatched_observed.remove(best)
            continue
        normalized_gold = _normalized_fragment(case["text"][gold["start_cp"] : gold["end_cp"]])
        normalized = next(
            (
                observed_index
                for observed_index in sorted(unmatched_observed)
                if observed[observed_index]["type"] == gold["type"]
                and _normalized_fragment(
                    case["text"][observed[observed_index]["start_cp"] : observed[observed_index]["end_cp"]]
                )
                == normalized_gold
            ),
            None,
        )
        if normalized is not None:
            record("normalization_mismatch", gold, observed[normalized])
            unmatched_expected.remove(expected_index)
            unmatched_observed.remove(normalized)
            continue
        record("missed_entity", gold, None)
        unmatched_expected.remove(expected_index)

    for observed_index in sorted(unmatched_observed):
        record("false_positive", None, observed[observed_index])
    return ledger


def _detect_adapter(text: str, diagnostics: Any) -> list[dict]:
    from pii_redactor.detectors.aggregate import detect_all
    from pii_redactor.ingest.text_cleaner import clean_length_preserving

    entities = detect_all(clean_length_preserving(text), ner_diagnostics=diagnostics)
    return [
        {
            "start_cp": entity.span[0],
            "end_cp": entity.span[1],
            "type": entity.data_type,
            "redact_type": entity.redact_type,
        }
        for entity in entities
    ]


def _detect_corpus(cases: list[dict]) -> tuple[dict[str, list[dict]], dict[str, int]]:
    from pii_redactor.detectors.tb_detector import NERChunkDiagnostics

    predictions: dict[str, list[dict]] = {}
    totals = Counter()
    for case in cases:
        diagnostics = NERChunkDiagnostics()
        predictions[case["case_id"]] = _detect_adapter(case["text"], diagnostics)
        totals.update(diagnostics.as_dict())
    if totals["skipped"]:
        raise RuntimeError("NER diagnostics reported skipped chunks")
    return predictions, dict(sorted(totals.items()))


def _score_detection(cases: list[dict], predictions: dict[str, list[dict]]) -> dict:
    hard_cases = [case for case in cases if case["action"] != "ambiguous"]
    headline_expected: list[tuple[str, tuple[int, int, str]]] = []
    headline_observed: list[tuple[str, tuple[int, int, str]]] = []
    relaxed_tp = 0
    exact_by_type: dict[str, Counter] = defaultdict(Counter)
    exact_by_scenario: dict[str, Counter] = defaultdict(Counter)
    document_f1: list[float] = []
    error_ledger: list[dict] = []
    gold_chars = 0
    predicted_chars = 0
    intersection_chars = 0
    total_chars = sum(len(case["text"]) for case in hard_cases)

    for case in hard_cases:
        expected = case["expected_spans"]
        observed = predictions[case["case_id"]]
        expected_keys = _exact_keys(expected)
        observed_keys = _exact_keys(observed)
        exact = expected_keys & observed_keys
        tp = len(exact)
        fp = len(observed_keys - expected_keys)
        fn = len(expected_keys - observed_keys)
        document_f1.append(float(_prf(tp, fp, fn)["f1"]))
        relaxed_tp += _relaxed_matches(expected, observed)
        headline_expected.extend((case["case_id"], item) for item in expected_keys)
        headline_observed.extend((case["case_id"], item) for item in observed_keys)
        types = {item[2] for item in expected_keys | observed_keys}
        for data_type in types:
            expected_type = {item for item in expected_keys if item[2] == data_type}
            observed_type = {item for item in observed_keys if item[2] == data_type}
            exact_by_type[data_type].update(
                tp=len(expected_type & observed_type),
                fp=len(observed_type - expected_type),
                fn=len(expected_type - observed_type),
                support=len(expected_type),
            )
        exact_by_scenario[case["scenario"]].update(tp=tp, fp=fp, fn=fn, documents=1)
        error_ledger.extend(_diagnose(case, observed))
        gold_positions: set[int] = set()
        observed_positions: set[int] = set()
        for item in expected:
            gold_positions.update(range(item["start_cp"], item["end_cp"]))
        for item in observed:
            observed_positions.update(range(item["start_cp"], item["end_cp"]))
        gold_chars += len(gold_positions)
        predicted_chars += len(observed_positions)
        intersection_chars += len(gold_positions & observed_positions)

    expected_set = set(headline_expected)
    observed_set = set(headline_observed)
    exact_summary = _prf(
        len(expected_set & observed_set),
        len(observed_set - expected_set),
        len(expected_set - observed_set),
    )
    relaxed_summary = _prf(relaxed_tp, len(observed_set) - relaxed_tp, len(expected_set) - relaxed_tp)
    per_type = {}
    for data_type, counts in sorted(exact_by_type.items()):
        summary = _prf(counts["tp"], counts["fp"], counts["fn"])
        summary["support"] = counts["support"]
        summary["interpretation"] = "descriptive_only" if counts["support"] < 25 else "supported_stratum"
        per_type[data_type] = summary
    per_scenario = {
        scenario: {**_prf(counts["tp"], counts["fp"], counts["fn"]), "documents": counts["documents"]}
        for scenario, counts in sorted(exact_by_scenario.items())
    }
    negatives = [case for case in cases if case["action"] == "do_not_mask"]
    negative_fp_entities = sum(len(predictions[case["case_id"]]) for case in negatives)
    negative_docs_with_fp = sum(bool(predictions[case["case_id"]]) for case in negatives)
    negative_chars = sum(len(case["text"]) for case in negatives)
    ambiguous = [case for case in cases if case["action"] == "ambiguous"]
    taxonomy = Counter(item["category"] for item in error_ledger)
    return {
        "headline_population": {
            "documents": len(hard_cases),
            "positive_documents": sum(case["action"] == "mask_required" for case in hard_cases),
            "negative_documents": len(negatives),
            "expected_entities": len(expected_set),
            "predicted_entities": len(observed_set),
        },
        "exact_typed_entity": exact_summary,
        "typed_iou_gte_0_5": relaxed_summary,
        "span_metrics": {
            "exact_span_and_type_rate_over_expected": _ratio(
                int(exact_summary["tp"]), len(expected_set)
            ),
            "exact_boundary_rate_among_typed_iou_gte_0_5_matches": _ratio(
                int(exact_summary["tp"]), relaxed_tp
            ),
            "exact_matches": int(exact_summary["tp"]),
            "typed_iou_gte_0_5_matches": relaxed_tp,
            "expected_entities": len(expected_set),
        },
        "document_macro_f1": _round(statistics.fmean(document_f1)) if document_f1 else 0.0,
        "protective_character_recall": _ratio(intersection_chars, gold_chars),
        "character_precision": _ratio(intersection_chars, predicted_chars),
        "overmasked_characters_per_1000": _round(
            max(0, predicted_chars - intersection_chars) * 1000 / total_chars
        ) if total_chars else 0.0,
        "per_type": per_type,
        "per_scenario": per_scenario,
        "negative_controls": {
            "documents": len(negatives),
            "documents_with_false_positive": negative_docs_with_fp,
            "document_false_positive_rate": _ratio(negative_docs_with_fp, len(negatives)),
            "false_positive_entities": negative_fp_entities,
            "false_positive_entities_per_1000_chars": _round(
                negative_fp_entities * 1000 / negative_chars
            ) if negative_chars else 0.0,
        },
        "ambiguous": {
            "documents_excluded_from_headline": len(ambiguous),
            "documents_with_any_detection": sum(bool(predictions[case["case_id"]]) for case in ambiguous),
        },
        "error_taxonomy": dict(sorted(taxonomy.items())),
        "error_ledger": sorted(
            error_ledger,
            key=lambda item: (item["case_id"], item["category"], item["expected_span"] or [-1, -1]),
        ),
    }


def _score_section26(cases: list[dict]) -> dict:
    from pii_redactor.report import scan_section26

    tp = fp = fn = 0
    exact_documents = 0
    ledger: list[dict] = []
    per_category: dict[str, Counter] = defaultdict(Counter)
    for case in cases:
        observed = {item["category"] for item in scan_section26(case["text"])}
        expected = set(case["expected_categories"])
        if observed == expected:
            exact_documents += 1
        tp += len(observed & expected)
        fp += len(observed - expected)
        fn += len(expected - observed)
        for category in sorted(observed | expected):
            per_category[category].update(
                tp=int(category in observed and category in expected),
                fp=int(category in observed and category not in expected),
                fn=int(category in expected and category not in observed),
                support=int(category in expected),
            )
        if observed != expected:
            ledger.append(
                {
                    "case_id": case["case_id"],
                    "case_hash": _case_hash(case),
                    "missed_categories": sorted(expected - observed),
                    "unexpected_categories": sorted(observed - expected),
                }
            )
    return {
        "label": "HEURISTIC SIGNAL EVALUATION — not PDPA compliance accuracy",
        "documents": len(cases),
        "document_exact_set_accuracy": _ratio(exact_documents, len(cases)),
        "micro": _prf(tp, fp, fn),
        "per_category": {
            category: {**_prf(counts["tp"], counts["fp"], counts["fn"]), "support": counts["support"]}
            for category, counts in sorted(per_category.items())
        },
        "error_ledger": ledger,
    }


def _evaluate_protection(cases: list[dict]) -> tuple[dict, list[float], list[float]]:
    from pii_redactor.ingest.text_cleaner import clean_length_preserving
    from pii_redactor.stateless import restore_stateless, sanitize_stateless

    eligible = [case for case in cases if case["action"] == "mask_required"]
    by_mode: dict[str, dict] = {}
    sanitize_latencies: list[float] = []
    restore_latencies: list[float] = []
    for mode in ("token", "surrogate"):
        counters = Counter()
        failures: list[dict] = []
        for case in eligible:
            counters["documents_attempted"] += 1
            try:
                started = time.perf_counter_ns()
                sanitized = sanitize_stateless(
                    case["text"],
                    mode=mode,
                    salt=f"aiguard-thai-pii-eval-v1:{case['case_id']}",
                    detection_text=clean_length_preserving(case["text"]),
                )
                sanitize_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
                counters["documents_sanitized"] += 1
                recognized_absent = 0
                for entity in sanitized.entities:
                    source_fragment = case["text"][entity["start"] : entity["end"]]
                    recognized_absent += int(source_fragment not in sanitized.sanitized_text)
                counters["recognized_entities"] += len(sanitized.entities)
                counters["recognized_entities_removed"] += recognized_absent
                expected_absent = 0
                for expected in case["expected_spans"]:
                    source_fragment = case["text"][expected["start_cp"] : expected["end_cp"]]
                    expected_absent += int(source_fragment not in sanitized.sanitized_text)
                counters["expected_entities"] += len(case["expected_spans"])
                counters["expected_entities_removed"] += expected_absent
                mapping = sanitized.mapping
                started = time.perf_counter_ns()
                restored = restore_stateless(sanitized.sanitized_text, mapping=mapping, mode=mode)
                restore_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
                counters["exact_restorations"] += int(restored.restored_text == case["text"])
                counters["zero_leftover_restorations"] += int(not restored.leftover_pseudonyms)
                counters["restoration_warnings"] += len(restored.warnings)
                counters["outbound_policy_pass"] += 1
                mapping = None
                sanitized = None
                restored = None
            except Exception as error:
                safe_leak_types = [
                    item
                    for item in getattr(error, "leak_types", [])
                    if isinstance(item, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", item)
                ]
                safe_policy_categories = [
                    item
                    for item in getattr(error, "policy_categories", [])
                    if isinstance(item, str) and re.fullmatch(r"[a-z][a-z0-9_]*", item)
                ]
                counters["fail_closed_documents"] += 1
                failures.append(
                    {
                        "case_id": case["case_id"],
                        "case_hash": _case_hash(case),
                        "failure_class": type(error).__name__,
                        "leak_types": sorted(set(safe_leak_types)),
                        "policy_categories": sorted(set(safe_policy_categories)),
                        "unsafe_text_returned": False,
                    }
                )
                error = None
        by_mode[mode] = {
            "documents_attempted": counters["documents_attempted"],
            "documents_sanitized": counters["documents_sanitized"],
            "sanitization_success_rate": _ratio(counters["documents_sanitized"], len(eligible)),
            "fail_closed_documents": counters["fail_closed_documents"],
            "fail_closed_rate": _ratio(counters["fail_closed_documents"], len(eligible)),
            "safe_disposition_rate": _ratio(
                counters["documents_sanitized"] + counters["fail_closed_documents"], len(eligible)
            ),
            "recognized_entities": counters["recognized_entities"],
            "recognized_raw_value_removal_rate": _ratio(
                counters["recognized_entities_removed"], counters["recognized_entities"]
            ),
            "expected_entities": counters["expected_entities"],
            "expected_raw_value_removal_rate": _ratio(
                counters["expected_entities_removed"], counters["expected_entities"]
            ),
            "exact_restoration_rate": _ratio(counters["exact_restorations"], counters["documents_sanitized"]),
            "zero_leftover_rate": _ratio(
                counters["zero_leftover_restorations"], counters["documents_sanitized"]
            ),
            "restoration_warning_count": counters["restoration_warnings"],
            "outbound_policy_pass_rate": _ratio(counters["outbound_policy_pass"], len(eligible)),
            "failures": failures,
        }
    return {
        "provider_calls": 0,
        "reidentification_pair_material_exported": False,
        "modes": by_mode,
    }, sanitize_latencies, restore_latencies


def _canonical_prediction_hash(predictions: dict[str, list[dict]]) -> str:
    canonical = [
        [case_id, item["start_cp"], item["end_cp"], item["type"], item["redact_type"]]
        for case_id in sorted(predictions)
        for item in predictions[case_id]
    ]
    return _sha256_bytes(_canonical_bytes(canonical))


def _measure_performance(
    cases: list[dict],
    repeats: int,
    first_detection_ms: float,
    sanitize_latencies: list[float],
    restore_latencies: list[float],
) -> dict:
    detect_latencies: list[float] = []
    pass_totals: list[float] = []
    varied = list(cases)
    for pass_index in range(repeats):
        ordered = varied[pass_index:] + varied[:pass_index]
        pass_started = time.perf_counter_ns()
        for case in ordered:
            started = time.perf_counter_ns()
            _detect_adapter(case["text"], None)
            detect_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        pass_totals.append((time.perf_counter_ns() - pass_started) / 1_000_000)
    mixed = next(case for case in cases if case["base_id"] == "mixed_hr")
    mixed_latencies = []
    for _ in range(max(5, repeats)):
        started = time.perf_counter_ns()
        _detect_adapter(mixed["text"], None)
        mixed_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
    total_chars = sum(len(case["text"]) for case in cases) * repeats
    total_seconds = sum(pass_totals) / 1000
    return {
        "scope": "local detector/protection only; excludes Tokenmind and is not a hosted SLA",
        "warm_passes": repeats,
        "samples": len(detect_latencies),
        "first_detection_ms_after_import": _round(first_detection_ms),
        "detect_ms": {
            "median": _round(statistics.median(detect_latencies)),
            "p95": _percentile(detect_latencies, 0.95),
            "max": _round(max(detect_latencies)),
        },
        "mixed_document_detect_ms": {
            "samples": len(mixed_latencies),
            "median": _round(statistics.median(mixed_latencies)),
            "p95": _percentile(mixed_latencies, 0.95),
        },
        "corpus_pass_ms": {
            "median": _round(statistics.median(pass_totals)),
            "p95": _percentile(pass_totals, 0.95),
        },
        "throughput_documents_per_second": _round(len(cases) * repeats / total_seconds) if total_seconds else 0.0,
        "throughput_characters_per_second": _round(total_chars / total_seconds) if total_seconds else 0.0,
        "sanitize_ms": {
            "samples": len(sanitize_latencies),
            "median": _round(statistics.median(sanitize_latencies)),
            "p95": _percentile(sanitize_latencies, 0.95),
        },
        "restore_ms": {
            "samples": len(restore_latencies),
            "median": _round(statistics.median(restore_latencies)),
            "p95": _percentile(restore_latencies, 0.95),
        },
        "peak_rss_kib": (
            int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) if resource is not None else None
        ),
    }


def _asset_tree_hash(path: str | None) -> str | None:
    if not path:
        return None
    root = Path(path)
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    for candidate in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(candidate.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def evaluate(repository_sha: str, runtime_image: str, runtime_revision: str, performance_repeats: int) -> dict:
    _sanitize_environment()
    _install_network_tripwire()
    logging.disable(logging.WARNING)
    corpus_path = ROOT / "corpus.v1.json"
    section26_path = ROOT / "section26.v1.json"
    manifest_path = ROOT / "manifest.v1.json"
    capabilities_path = ROOT / "capabilities.json"
    corpus = _load_json(corpus_path)
    section26 = _load_json(section26_path)
    manifest = _load_json(manifest_path)
    capabilities = _load_json(capabilities_path)
    cases = corpus["cases"]

    first_started = time.perf_counter_ns()
    first_predictions, first_diagnostics = _detect_corpus(cases[:1])
    first_detection_ms = (time.perf_counter_ns() - first_started) / 1_000_000
    predictions, diagnostics = _detect_corpus(cases)
    hashes = [_canonical_prediction_hash(predictions)]
    for _ in range(2):
        repeated, repeat_diagnostics = _detect_corpus(cases)
        diagnostics = dict(Counter(diagnostics) + Counter(repeat_diagnostics))
        hashes.append(_canonical_prediction_hash(repeated))
    for diagnostic_name in ("attempted", "succeeded", "skipped"):
        diagnostics.setdefault(diagnostic_name, 0)
    if len(set(hashes)) != 1:
        raise RuntimeError("detector predictions were not deterministic across three runs")

    detection = _score_detection(cases, predictions)
    section26_result = _score_section26(section26["cases"])
    protection, sanitize_latencies, restore_latencies = _evaluate_protection(cases)
    performance = _measure_performance(
        cases,
        performance_repeats,
        first_detection_ms,
        sanitize_latencies,
        restore_latencies,
    )
    if NETWORK_ATTEMPTS:
        raise RuntimeError("network tripwire recorded an attempt")

    prediction_inventory = {
        case_id: [
            {
                "start_cp": item["start_cp"],
                "end_cp": item["end_cp"],
                "type": item["type"],
                "redact_type": item["redact_type"],
            }
            for item in items
        ]
        for case_id, items in sorted(predictions.items())
    }
    return {
        "schema_version": 1,
        "evaluation_id": "aiguard-thai-pii-adversarial-baseline-v1",
        "claim_scope": "deterministic synthetic/adversarial evaluation; not a population-representative benchmark",
        "repository_sha": repository_sha,
        "production_baseline_sha": capabilities["production_baseline_sha"],
        "vendored_upstream_sha": _load_json(ROOT.parent.parent / "sync" / "PORT_MANIFEST.json")["commit"],
        "runtime": {
            "image": runtime_image,
            "image_revision": runtime_revision,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "ner_engine": "pythainlp-thainer-offline",
            "ner_asset_tree_sha256": _asset_tree_hash(os.environ.get("PYTHAINLP_DATA")),
            "network_attempts": len(NETWORK_ATTEMPTS),
            "provider_calls": 0,
            "credentials_required": False,
        },
        "corpus": {
            "id": corpus["corpus_id"],
            "sha256": _sha256_bytes(corpus_path.read_bytes()),
            "manifest_sha256": _sha256_bytes(manifest_path.read_bytes()),
            "cases": len(cases),
            "base_templates": manifest["base_template_count"],
            "positive_cases": sum(case["action"] == "mask_required" for case in cases),
            "negative_cases": sum(case["action"] == "do_not_mask" for case in cases),
            "ambiguous_cases": sum(case["action"] == "ambiguous" for case in cases),
            "expected_entities": sum(len(case["expected_spans"]) for case in cases if case["action"] != "ambiguous"),
            "entity_types": capabilities["entity_types"],
            "offset_unit": corpus["offset_unit"],
            "synthetic_declaration": corpus["synthetic_declaration"],
        },
        "determinism": {
            "passes": 3,
            "canonical_prediction_sha256": hashes[0],
            "all_passes_identical": True,
            "ner_diagnostics": diagnostics,
        },
        "detection": detection,
        "section26": section26_result,
        "protection": protection,
        "performance": performance,
        "prediction_inventory": prediction_inventory,
        "artifact_privacy": {
            "contains_corpus_text": False,
            "contains_reidentification_pairs": False,
            "contains_generated_replacements": False,
            "contains_provider_body": False,
            "contains_credentials": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--runtime-image", required=True)
    parser.add_argument("--runtime-revision", required=True)
    parser.add_argument("--performance-repeats", type=int, default=3, choices=range(3, 11))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        repository_sha=args.repository_sha,
        runtime_image=args.runtime_image,
        runtime_revision=args.runtime_revision,
        performance_repeats=args.performance_repeats,
    )
    args.output.write_bytes(_canonical_bytes(result))
    print(
        "evaluation complete: "
        f"cases={result['corpus']['cases']} "
        f"exact_f1={result['detection']['exact_typed_entity']['f1']:.6f} "
        f"provider_calls={result['runtime']['provider_calls']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

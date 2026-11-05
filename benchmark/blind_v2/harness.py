"""One-command comparison of AI Guard and the baselines.

The report stores scores, timings, and skip reasons. It does not store
document text, entity values, prompts, or model replies.
"""

from __future__ import annotations

import logging
import time
import tracemalloc

from .ablate import LAYERS, AIGuard, predict_ablated
from .baselines import PresidioBaseline, PyThaiNLPNER, RegexBaseline, WangchanBERTaNER
from .corpus import corpus_sha256
from .llm import LLMRedactor, LLMUnavailable, complete, probe_llm
from .score import name_miss_census, percentile, score_predictions
from .types import REDACTION_TYPES, SECTION26_TYPES
from .utility import score_utility

_SYSTEMS = {
    "aiguard": AIGuard,
    "regex": RegexBaseline,
    "presidio": PresidioBaseline,
    "pythainlp-ner": PyThaiNLPNER,
    "wangchanberta-ner": WangchanBERTaNER,
    "llm": LLMRedactor,
}


def default_system_names() -> tuple[str, ...]:
    return tuple(_SYSTEMS)


def build_systems(names: list[str], *, llm_seed: int | None = None):
    unknown = [name for name in names if name not in _SYSTEMS]
    if unknown:
        raise ValueError("unknown system")
    systems = []
    for name in names:
        if name == "llm":
            systems.append(LLMRedactor(seed=llm_seed))
        else:
            systems.append(_SYSTEMS[name]())
    return systems


def run_benchmark(
    corpus,
    *,
    systems=None,
    ablate: bool = True,
    utility: bool = True,
    section26: bool = True,
    limit: int = 0,
) -> dict:
    documents = corpus.documents if not limit else corpus.documents[:limit]
    # The NER chunk warning names a label and a length, and it floods the table.
    logging.getLogger("pii_redactor.detectors.tb_detector").setLevel(logging.ERROR)
    selected = systems if systems is not None else build_systems(list(default_system_names()))
    system_rows = []
    predictions = {}
    for system in selected:
        row, predicted = _evaluate(system, documents)
        system_rows.append(row)
        if predicted is not None:
            predictions[system.name] = predicted

    identity = _dataset_identity(corpus)
    report = {
        "ablations": _ablations(documents)
        if ablate
        else {"status": "skipped", "reason": "disabled"},
        "dataset": {
            "documents": len(documents),
            "limited": bool(limit),
            "official": not limit,
            **identity,
        },
        "section26": _section26(documents) if section26 else {"status": "skipped"},
        "systems": system_rows,
        "utility": _utility(documents, predictions)
        if utility
        else {"status": "skipped", "reason": "disabled"},
    }
    return report


def render_report(report: dict) -> str:
    dataset = report["dataset"]
    lines = [
        f"dataset={dataset['version']} seed={dataset['seed']} "
        f"documents={dataset['documents']} sha256={dataset['plaintext_sha256']} "
        f"official={str(dataset['official']).lower()}",
        f"{'system':<18}{'status':<10}{'P':>8}{'R':>8}{'F1':>8}{'F2':>8}"
        f"{'macroF1':>9}{'macroF2':>9}"
        f"{'p50ms':>8}{'p95ms':>8}{'p50KiB':>9}{'p95KiB':>9}{'cost':>8}",
    ]
    for system in report["systems"]:
        lines.append(_system_line(system))
        if system["status"] != "ok":
            lines.append(f"  reason: {system['reason']}")
    lines.append("per-entity")
    header = f"{'system':<18}{'type':<16}{'n':>5}{'P':>8}{'R':>8}{'F1':>8}{'F2':>8}"
    lines.append(header)
    for system in report["systems"]:
        if system["status"] != "ok":
            continue
        for entity_type in REDACTION_TYPES:
            row = system["by_type"][entity_type]
            if row["n"] == 0:
                lines.append(
                    f"{system['name']:<18}{entity_type:<16}{row['n']:>5}"
                    "     n/a     n/a     n/a     n/a"
                )
                continue
            lines.append(
                f"{system['name']:<18}{entity_type:<16}{row['n']:>5}"
                f"{row['precision']:>8.3f}{row['recall']:>8.3f}"
                f"{row['f1']:>8.3f}{row['f2']:>8.3f}"
            )
        negative = system["negative"]
        lines.append(
            f"  negative clean {negative['clean_docs']}/{negative['documents']} "
            f"false_positives={negative['false_positives']} "
            f"other_fp={system['other_false_positives']}"
        )
        misses = system.get("name_misses")
        if misses:
            lines.append(
                "  name_fn "
                f"cued={misses['false_negatives_with_prefix_cue']} "
                f"uncued={misses['false_negatives_without_prefix_cue']}"
            )
    ablation = report["ablations"]
    lines.append("ablations (delta = layer-removed minus full; negative means the layer helped)")
    if ablation.get("status") != "ok":
        lines.append(f"  {ablation.get('status', 'skipped')}: {ablation.get('reason', '')}")
    else:
        lines.append(f"  full micro F2={ablation['full_micro_f2']:.3f}")
        for row in ablation["layers"]:
            lines.append(
                f"  without {row['disabled']:<16} F2={row['micro_f2']:.3f} "
                f"delta_f2={row['delta_micro_f2']:+.3f} "
                f"delta_recall={row['delta_micro_recall']:+.3f}"
            )
            deltas = row.get("delta_by_type_recall")
            if not deltas:
                continue
            moved = any(abs(value) > 1e-12 for value in deltas.values())
            if row["disabled"] not in {"fp", "tb"} and not moved:
                continue
            lines.append(f"  per-type recall delta without {row['disabled']}")
            for entity_type in REDACTION_TYPES:
                lines.append(f"    {entity_type:<16} {deltas[entity_type]:+.3f}")
    section = report["section26"]
    lines.append("section26 warn-path (AI Guard keyword scan, not a redaction score)")
    if section.get("status") == "skipped":
        lines.append("  skipped")
    else:
        recall = section.get("micro_recall")
        recall_text = "n/a" if recall is None else f"{recall:.3f}"
        lines.append(f"  micro_recall={recall_text} n={section['n']}")
        for category in SECTION26_TYPES:
            row = section["by_category"][category]
            recall = "n/a" if row["recall"] is None else f"{row['recall']:.3f}"
            lines.append(f"  {category:<20} n={row['n']:<3} recall={recall}")
    utility = report["utility"]
    lines.append("utility (answer contained in the reply; safe = non-PII question)")
    if utility.get("status") != "ok":
        lines.append(f"  {utility.get('status', 'skipped')}: {utility.get('reason', '')}")
    else:
        for name, row in utility["systems"].items():
            lines.append(
                f"  {name:<18} safe raw={_fmt(row['safe_raw_accuracy'])} "
                f"redacted={_fmt(row['safe_redacted_accuracy'])} "
                f"pii raw={_fmt(row['pii_raw_accuracy'])} "
                f"redacted={_fmt(row['pii_redacted_accuracy'])} "
                f"n_safe={row['safe_n']} n_pii={row['pii_n']}"
            )
    return "\n".join(lines)


def _evaluate(system, documents):
    reason = system.prepare()
    if reason:
        return _skipped(system, reason), None
    predictions = []
    latencies: list[float] = []
    peaks: list[float] = []
    tracing = tracemalloc.is_tracing()
    if not tracing:
        tracemalloc.start()
    try:
        try:
            # Load models before the timed documents. The string is not scored.
            system.predict("นายตัวอย่าง ระบบ โทร 02-000-0000")
        except Exception:
            pass
        for document in documents:
            tracemalloc.reset_peak()
            started = time.perf_counter()
            try:
                predicted = [
                    (int(start), int(end), str(entity_type))
                    for start, end, entity_type in system.predict(document.text)
                ]
            except Exception as exc:
                return _failed(system, type(exc).__name__), None
            latencies.append(time.perf_counter() - started)
            peaks.append(float(tracemalloc.get_traced_memory()[1]))
            predictions.append(predicted)
    finally:
        if not tracing:
            tracemalloc.stop()
    scored = score_predictions(documents, predictions)
    row = {
        "by_type": scored["by_type"],
        "cost_usd": system.cost_usd,
        "latency_ms": {
            "p50": _ms(percentile(latencies, 50)),
            "p95": _ms(percentile(latencies, 95)),
        },
        "macro": scored["macro"],
        "micro": scored["micro"],
        "name": system.name,
        "name_misses": name_miss_census(documents, predictions),
        "negative": scored["negative"],
        "other_false_positives": scored["other_false_positives"],
        "peak_memory_bytes": {
            "p50": percentile(peaks, 50),
            "p95": percentile(peaks, 95),
        },
        "reason": "",
        "status": "ok",
    }
    sampling_seed = getattr(system, "sampling_seed", None)
    if sampling_seed is not None:
        row["sampling_seed"] = sampling_seed
    return row, predictions


def layer_delta(full_score: dict, scored: dict, disabled: str) -> dict:
    """Score with one layer removed, minus the full score. No document text."""
    return {
        "by_type": scored["by_type"],
        "delta_by_type_recall": {
            entity_type: scored["by_type"][entity_type]["recall"]
            - full_score["by_type"][entity_type]["recall"]
            for entity_type in scored["by_type"]
        },
        "delta_micro_f1": scored["micro"]["f1"] - full_score["micro"]["f1"],
        "delta_micro_f2": scored["micro"]["f2"] - full_score["micro"]["f2"],
        "delta_micro_recall": scored["micro"]["recall"] - full_score["micro"]["recall"],
        "disabled": disabled,
        "macro": scored["macro"],
        "micro": scored["micro"],
        "micro_f2": scored["micro"]["f2"],
        "micro_recall": scored["micro"]["recall"],
    }


def _ablations(documents) -> dict:
    try:
        import pythainlp  # noqa: F401
    except ImportError:
        return {"status": "skipped", "reason": "pythainlp is not installed"}
    try:
        full = [predict_ablated(document.text, None) for document in documents]
        full_score = score_predictions(documents, full)
        layers = []
        for layer in LAYERS:
            predicted = [predict_ablated(document.text, layer) for document in documents]
            scored = score_predictions(documents, predicted)
            layers.append(layer_delta(full_score, scored, layer))
    except Exception as exc:
        return {"status": "error", "reason": type(exc).__name__}
    return {
        "full_by_type": full_score["by_type"],
        "full_macro": full_score["macro"],
        "full_micro": full_score["micro"],
        "full_micro_f2": full_score["micro"]["f2"],
        "layers": layers,
        "status": "ok",
    }


def _section26(documents) -> dict:
    from pii_redactor.report import scan_section26

    totals = {category: {"flagged": 0, "n": 0} for category in SECTION26_TYPES}
    for document in documents:
        found = {hit["category"] for hit in scan_section26(document.text)}
        for category in document.section26:
            totals[category]["n"] += 1
            totals[category]["flagged"] += int(category in found)
    by_category = {}
    total_n = 0
    total_flagged = 0
    for category in SECTION26_TYPES:
        row = totals[category]
        total_n += row["n"]
        total_flagged += row["flagged"]
        by_category[category] = {
            **row,
            "recall": (row["flagged"] / row["n"]) if row["n"] else None,
        }
    return {
        "by_category": by_category,
        "micro_recall": (total_flagged / total_n) if total_n else None,
        "n": total_n,
        "status": "ok",
    }


def _dataset_identity(corpus) -> dict:
    """Hash the corpus with the lock that owns it. Hard splits have no version."""
    if hasattr(corpus, "version"):
        return {
            "plaintext_sha256": corpus_sha256(corpus),
            "seed": corpus.seed,
            "version": corpus.version,
        }
    from .hard_set import public_lock as hard_public_lock

    lock = hard_public_lock(corpus)
    return {
        "plaintext_sha256": lock["plaintext_sha256"],
        "seed": corpus.seed,
        "version": lock["version"],
    }


def _utility(documents, predictions: dict) -> dict:
    if not documents or not hasattr(documents[0], "questions"):
        return {"status": "skipped", "reason": "the split has no questions", "systems": {}}
    if not predictions:
        return {"status": "skipped", "reason": "no system produced predictions"}
    probe = probe_llm()
    if not probe.available:
        return {"status": "skipped", "reason": probe.reason, "systems": {}}

    def complete_fn(prompt: str) -> str:
        return complete(prompt, probe)

    try:
        return score_utility(documents, predictions, complete_fn)
    except LLMUnavailable as exc:
        return {"status": "skipped", "reason": exc.reason, "systems": {}}


def _skipped(system, reason: str) -> dict:
    return {
        "by_type": None,
        "cost_usd": None,
        "latency_ms": None,
        "macro": None,
        "micro": None,
        "name": system.name,
        "negative": None,
        "other_false_positives": None,
        "peak_memory_bytes": None,
        "reason": reason,
        "status": "skipped",
    }


def _failed(system, reason: str) -> dict:
    row = _skipped(system, reason)
    row["status"] = "error"
    return row


def _ms(seconds: float | None) -> float | None:
    if seconds is None:
        return None
    return seconds * 1000


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _system_line(system: dict) -> str:
    if system["status"] != "ok":
        return (
            f"{system['name']:<18}{system['status']:<10}"
            f"{'':>8}{'':>8}{'':>8}{'':>8}{'':>9}{'':>9}"
            f"{'':>8}{'':>8}{'':>9}{'':>9}{'n/a':>8}"
        )
    micro = system["micro"]
    cost = system["cost_usd"]
    cost_text = "n/a" if cost is None else f"{cost:.2f}"
    return (
        f"{system['name']:<18}{system['status']:<10}"
        f"{micro['precision']:>8.3f}{micro['recall']:>8.3f}"
        f"{micro['f1']:>8.3f}{micro['f2']:>8.3f}"
        f"{system['macro']['f1']:>9.3f}{system['macro']['f2']:>9.3f}"
        f"{system['latency_ms']['p50']:>8.1f}{system['latency_ms']['p95']:>8.1f}"
        f"{system['peak_memory_bytes']['p50'] / 1024:>9.1f}"
        f"{system['peak_memory_bytes']['p95'] / 1024:>9.1f}"
        f"{cost_text:>8}"
    )

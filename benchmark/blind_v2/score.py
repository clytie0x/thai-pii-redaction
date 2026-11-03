"""Entity scores for the blind-v2 comparison.

Matching is type-aware overlap, one gold span to one prediction, the same rule
as ``benchmark/scorer.py``. Macro averages the predeclared redaction types.
Predictions outside that scheme count as false positives in the micro score
and are not given their own macro row.
"""

from __future__ import annotations

import math

from .types import REDACTION_TYPE_SET, REDACTION_TYPES

# Titles and label cues. Longest first so นางสาว wins over นาง. A cue counts
# only when it sits in the short window before a gold NAME and is not glued
# to another letter (that rejects นาย inside นายก).
_NAME_CUE_WINDOW = 16
_NAME_PREFIX_CUES = (
    "ผู้เสียหาย",
    "ข้าพเจ้า",
    "เด็กหญิง",
    "เด็กชาย",
    "นางสาว",
    "น.ส.",
    "ด.ช.",
    "ด.ญ.",
    "ชื่อ",
    "นาง",
    "นาย",
)


def prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    f2 = (5 * precision * recall / (4 * precision + recall)) if (4 * precision + recall) else 0.0
    return {
        "f1": f1,
        "fn": fn,
        "f2": f2,
        "fp": fp,
        "precision": precision,
        "recall": recall,
        "tp": tp,
    }


def _letter(char: str) -> bool:
    return ("\u0e00" <= char <= "\u0e7f") or char.isalpha()


def prefix_name_cue(text: str, start: int) -> bool:
    """True when a cue token ends in the window immediately before ``start``."""
    window = text[max(0, start - _NAME_CUE_WINDOW) : start]
    for cue in _NAME_PREFIX_CUES:
        index = window.rfind(cue)
        if index < 0:
            continue
        if index > 0 and _letter(window[index - 1]):
            continue
        after = index + len(cue)
        if after < len(window) and _letter(window[after]):
            continue
        return True
    return False


def name_miss_census(documents, predictions) -> dict:
    """Count NAME misses with and without a prefix cue. Counts only, no text."""
    if len(documents) != len(predictions):
        raise ValueError("documents and predictions must have the same length")
    cued = 0
    uncued = 0
    gold_n = 0
    for document, predicted in zip(documents, predictions):
        golds = [(span.start, span.end) for span in document.spans if span.entity_type == "NAME"]
        choices = [(start, end) for start, end, entity_type in predicted if entity_type == "NAME"]
        used: set[int] = set()
        for start, end in golds:
            gold_n += 1
            hit = None
            for index, candidate in enumerate(choices):
                if index in used:
                    continue
                if _overlap((start, end), candidate):
                    hit = index
                    break
            if hit is not None:
                used.add(hit)
                continue
            if prefix_name_cue(document.text, start):
                cued += 1
            else:
                uncued += 1
    return {
        "false_negatives_with_prefix_cue": cued,
        "false_negatives_without_prefix_cue": uncued,
        "gold": gold_n,
    }


def percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile. ``pct`` is in ``[0, 100]``."""
    if not values:
        return None
    if not 0 <= pct <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered)) - 1
    rank = min(max(rank, 0), len(ordered) - 1)
    return ordered[rank]


def dedupe_predictions(
    spans: list[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    """Keep a non-overlapping set, preferring the earlier then longer span."""
    ordered = sorted(spans, key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
    kept: list[tuple[int, int, str]] = []
    cursor = 0
    for start, end, entity_type in ordered:
        if end <= start or start < cursor:
            continue
        kept.append((start, end, entity_type))
        cursor = end
    return kept


def _overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return min(left[1], right[1]) - max(left[0], right[0]) > 0


def score_predictions(documents, predictions) -> dict:
    if len(documents) != len(predictions):
        raise ValueError("documents and predictions must have the same length")

    counts = {entity_type: {"tp": 0, "fp": 0, "fn": 0, "n": 0} for entity_type in REDACTION_TYPES}
    other_fp = 0
    for document, predicted in zip(documents, predictions):
        gold_by_type: dict[str, list[tuple[int, int]]] = {
            entity_type: [] for entity_type in REDACTION_TYPES
        }
        for span in document.spans:
            if span.entity_type in counts:
                counts[span.entity_type]["n"] += 1
                gold_by_type[span.entity_type].append((span.start, span.end))
        predicted_by_type: dict[str, list[tuple[int, int]]] = {
            entity_type: [] for entity_type in REDACTION_TYPES
        }
        for start, end, entity_type in predicted:
            if entity_type in REDACTION_TYPE_SET:
                predicted_by_type[entity_type].append((start, end))
            else:
                other_fp += 1
        for entity_type in REDACTION_TYPES:
            golds = gold_by_type[entity_type]
            choices = predicted_by_type[entity_type]
            used: set[int] = set()
            for gold in golds:
                hit = None
                for index, candidate in enumerate(choices):
                    if index in used:
                        continue
                    if _overlap(gold, candidate):
                        hit = index
                        break
                if hit is None:
                    counts[entity_type]["fn"] += 1
                else:
                    used.add(hit)
                    counts[entity_type]["tp"] += 1
            counts[entity_type]["fp"] += len(choices) - len(used)

    by_type = {}
    for entity_type in REDACTION_TYPES:
        row = counts[entity_type]
        by_type[entity_type] = {"n": row["n"], **prf(row["tp"], row["fp"], row["fn"])}

    micro = prf(
        sum(row["tp"] for row in counts.values()),
        sum(row["fp"] for row in counts.values()) + other_fp,
        sum(row["fn"] for row in counts.values()),
    )
    scored_types = [
        by_type[entity_type] for entity_type in REDACTION_TYPES if by_type[entity_type]["n"]
    ]
    if scored_types:
        macro = {
            "f1": sum(row["f1"] for row in scored_types) / len(scored_types),
            "f2": sum(row["f2"] for row in scored_types) / len(scored_types),
            "precision": sum(row["precision"] for row in scored_types) / len(scored_types),
            "recall": sum(row["recall"] for row in scored_types) / len(scored_types),
            "types": len(scored_types),
        }
    else:
        macro = {"f1": 0.0, "f2": 0.0, "precision": 0.0, "recall": 0.0, "types": 0}

    negative_indexes = [index for index, document in enumerate(documents) if not document.spans]
    negative_fp = sum(len(predictions[index]) for index in negative_indexes)
    negative_clean = sum(1 for index in negative_indexes if not predictions[index])
    negative_docs = len(negative_indexes)
    return {
        "by_type": by_type,
        "macro": macro,
        "micro": micro,
        "negative": {
            "clean_docs": negative_clean,
            "clean_doc_rate": (negative_clean / negative_docs) if negative_docs else 1.0,
            "documents": negative_docs,
            "false_positives": negative_fp,
        },
        "other_false_positives": other_fp,
    }

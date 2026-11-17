"""Scoring definitions registered for YRSS evaluation v3.

Per-type precision, recall, and F2 use the v2 matcher unchanged. Over-redaction
is the share of characters outside gold entity spans that a prediction covers.
Latency is not computed here; the pre-registration leaves the number unmeasured.
"""

from __future__ import annotations

from collections.abc import Sequence

from benchmark.blind_v2.score import score_predictions
from benchmark.yrss_v2.types import SCHEME_TYPES


def per_type_scores(documents, predictions) -> dict:
    """Entity-level P/R/F2 on the eleven-type scheme. Predictions are ``(start, end, type)``."""
    scored = score_predictions(documents, predictions, types=SCHEME_TYPES)
    rows = {}
    for entity_type in SCHEME_TYPES:
        row = scored["by_type"][entity_type]
        rows[entity_type] = {
            "f2": row["f2"],
            "n": row["n"],
            "precision": row["precision"],
            "recall": row["recall"],
        }
    return {"by_type": rows, "micro": scored["micro"]}


def over_redaction_rate(
    text: str,
    gold: Sequence[tuple[int, int]],
    predicted: Sequence[tuple[int, int]],
) -> float:
    """Characters outside gold entity spans that a prediction still covers, over those outside.

    Zero when the gold spans cover the whole text, because there is no outside
    character to over-redact. Spans are Unicode code points, half-open.
    """
    length = len(text)
    gold_flags = bytearray(length)
    pred_flags = bytearray(length)
    _paint(gold_flags, gold, length)
    _paint(pred_flags, predicted, length)
    outside = 0
    hit = 0
    for gold_bit, pred_bit in zip(gold_flags, pred_flags):
        if gold_bit:
            continue
        outside += 1
        if pred_bit:
            hit += 1
    return hit / outside if outside else 0.0


def _paint(flags: bytearray, spans: Sequence[tuple[int, int]], length: int) -> None:
    for start, end in spans:
        if not 0 <= start <= end <= length:
            raise ValueError("span-out-of-range")
        flags[start:end] = b"\x01" * (end - start)

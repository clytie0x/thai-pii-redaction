"""Counts, cluster bootstrap, paired differences, and Holm for the YRSS evaluation v2.

Pure functions. Nothing here loads a detector or reads a corpus file.
Protocol: docs/decisions/2026-11-13-yrss-eval-v2.md.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from benchmark.blind_v2.score import score_predictions

from .types import CONTEXTUAL_TYPES, SCHEME_TYPES, STRUCTURED_TYPES

VIEWS = ("all", "structured", "contextual")
N_RESAMPLES = 1000
SEED = 0

Counts = tuple[int, int, int]
Prediction = tuple[int, int, str]
Metric = Callable[[int, int, int], float]

_VIEW_TYPES = {
    "all": SCHEME_TYPES,
    "structured": STRUCTURED_TYPES,
    "contextual": CONTEXTUAL_TYPES,
}


def view_types(view: str) -> tuple[str, ...]:
    if view not in _VIEW_TYPES:
        raise ValueError(f"unknown view {view}")
    return _VIEW_TYPES[view]


def f2(tp: int, fp: int, fn: int) -> float:
    """F2 = 5PR / (4P + R), written with counts. 0 when the denominator is 0."""
    denominator = 5 * tp + 4 * fn + fp
    return 5 * tp / denominator if denominator else 0.0


def recall(tp: int, fp: int, fn: int) -> float:
    return tp / (tp + fn) if (tp + fn) else 0.0


def document_counts(
    documents: Sequence,
    predictions: Sequence[Sequence[Prediction]],
    types: Sequence[str],
    *,
    out_of_scope_is_fp: bool,
) -> list[Counts]:
    """Per-document ``(tp, fp, fn)`` with the matching rule of ``score_predictions``.

    Gold spans outside ``types`` are never scored. A prediction outside
    ``types`` is a false positive when ``out_of_scope_is_fp`` is true, and is
    dropped before scoring when it is false.
    """
    if len(documents) != len(predictions):
        raise ValueError("documents and predictions must have the same length")
    scheme = tuple(types)
    scheme_set = frozenset(scheme)
    rows: list[Counts] = []
    for document, predicted in zip(documents, predictions):
        kept = [item for item in predicted if out_of_scope_is_fp or item[2] in scheme_set]
        micro = score_predictions([document], [kept], types=scheme)["micro"]
        rows.append((micro["tp"], micro["fp"], micro["fn"]))
    return rows


def view_counts(
    documents: Sequence, predictions: Sequence[Sequence[Prediction]], view: str
) -> list[Counts]:
    """Per-document counts for one view.

    ``all``: the eleven scheme types. A prediction of any other type is a false
    positive (the unrestricted view of the protocol).

    ``structured`` and ``contextual``: gold and predictions are both cut down to
    that group. A prediction of a type outside the group is ignored here, not
    counted as a false positive. So a NER-only system is not charged in the
    contextual view for labels such as LOCATION, and a system is not charged in
    the structured view for a NAME. Those predictions still cost precision in
    the ``all`` view.
    """
    return document_counts(
        documents, predictions, view_types(view), out_of_scope_is_fp=(view == "all")
    )


def total(counts: Sequence[Counts]) -> Counts:
    return (
        sum(row[0] for row in counts),
        sum(row[1] for row in counts),
        sum(row[2] for row in counts),
    )


@dataclass(frozen=True)
class Resamples:
    """One shared set of family draws. Reuse it so paired differences line up."""

    members: tuple[tuple[int, ...], ...]  # document indexes of each family
    draws: tuple[tuple[int, ...], ...]  # family indexes of each resample
    seed: int

    @property
    def documents(self) -> int:
        return sum(len(group) for group in self.members)


def family_resamples(
    families: Sequence[str], *, n_resamples: int = N_RESAMPLES, seed: int = SEED
) -> Resamples:
    """Draw whole families with replacement. ``families`` has one entry per document.

    Documents from one template share wording, so they are not independent.
    Each resample draws as many families as the corpus has.
    """
    grouped: dict[str, list[int]] = {}
    for index, family in enumerate(families):
        grouped.setdefault(family, []).append(index)
    members = tuple(tuple(indexes) for indexes in grouped.values())
    rng = random.Random(seed)
    size = len(members)
    draws = tuple(tuple(rng.randrange(size) for _ in range(size)) for _ in range(n_resamples))
    return Resamples(members, draws, seed)


def _family_sums(counts: Sequence[Counts], resamples: Resamples) -> list[Counts]:
    if len(counts) != resamples.documents:
        raise ValueError("counts and resamples must cover the same documents")
    return [total([counts[index] for index in group]) for group in resamples.members]


def bootstrap_metric(
    counts: Sequence[Counts], resamples: Resamples, metric: Metric = f2
) -> list[float]:
    """The micro metric of each resample, from summed per-document counts."""
    sums = _family_sums(counts, resamples)
    return [metric(*total([sums[family] for family in draw])) for draw in resamples.draws]


def percentile(values: Sequence[float], pct: float) -> float:
    """Percentile with linear interpolation between the two nearest ranks."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def interval(values: Sequence[float]) -> tuple[float, float]:
    """95% percentile interval."""
    return percentile(values, 2.5), percentile(values, 97.5)


def f2_interval(counts: Sequence[Counts], resamples: Resamples) -> tuple[float, float]:
    return interval(bootstrap_metric(counts, resamples))


def paired_difference(
    counts_a: Sequence[Counts],
    counts_b: Sequence[Counts],
    resamples: Resamples,
    *,
    metric: Metric = f2,
) -> dict:
    """Metric of A minus metric of B, over the same family resamples.

    The p-value is two-sided: twice the smaller share of resampled differences
    on one side of zero (zero counts on both sides), capped at 1 and floored at
    ``1 / (n_resamples + 1)`` because a finite bootstrap cannot show less.
    """
    point = metric(*total(counts_a)) - metric(*total(counts_b))
    left = bootstrap_metric(counts_a, resamples, metric)
    right = bootstrap_metric(counts_b, resamples, metric)
    differences = [a - b for a, b in zip(left, right)]
    n = len(differences)
    at_or_below = sum(1 for value in differences if value <= 0) / n
    at_or_above = sum(1 for value in differences if value >= 0) / n
    p_value = max(min(1.0, 2 * min(at_or_below, at_or_above)), 1 / (n + 1))
    low, high = interval(differences)
    return {"difference": point, "ci_low": low, "ci_high": high, "p_value": p_value}


def holm(p_values: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values, in input order."""
    order = sorted(range(len(p_values)), key=lambda index: p_values[index])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted

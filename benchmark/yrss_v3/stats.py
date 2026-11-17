"""Paired tests for YRSS evaluation v3, on the v2 resampling rules.

The bootstrap, its seed, and Holm are the functions in
``benchmark/yrss_v2/stats.py``. Approximate randomization is a paired
sign-flip of the same family aggregates, reported beside the bootstrap and
corrected with the same Holm procedure.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from benchmark.yrss_v2.stats import (
    N_RESAMPLES,
    SEED,
    Counts,
    f2,
    holm,
    paired_difference,
)

__all__ = [
    "N_PERMUTATIONS",
    "N_RESAMPLES",
    "SEED",
    "f2",
    "holm",
    "paired_difference",
    "sign_flip_difference",
]

# Same budget and seed as the v2 bootstrap, so the two tests are comparable.
N_PERMUTATIONS = N_RESAMPLES


def _sum(rows: Sequence[Counts]) -> Counts:
    return (
        sum(row[0] for row in rows),
        sum(row[1] for row in rows),
        sum(row[2] for row in rows),
    )


def sign_flip_difference(
    left: Sequence[Counts],
    right: Sequence[Counts],
    *,
    n_permutations: int = N_PERMUTATIONS,
    seed: int = SEED,
    metric=f2,
) -> dict:
    """Two-sided paired sign-flip. One row is one family, not one document.

    Under the null, either system may own a family's counts. The p-value is
    the share of permutations whose absolute difference is at least the
    observed one, floored at ``1 / (n + 1)`` the way the v2 bootstrap is,
    because a finite draw cannot show a smaller probability.
    """
    if len(left) != len(right):
        raise ValueError("family-counts-differ")
    if n_permutations < 1:
        raise ValueError("no-permutations")
    point = metric(*_sum(left)) - metric(*_sum(right))
    rng = random.Random(seed)
    extreme = 0
    for _ in range(n_permutations):
        flipped_left = []
        flipped_right = []
        for a, b in zip(left, right):
            if rng.randrange(2):
                flipped_left.append(b)
                flipped_right.append(a)
            else:
                flipped_left.append(a)
                flipped_right.append(b)
        diff = metric(*_sum(flipped_left)) - metric(*_sum(flipped_right))
        if abs(diff) + 1e-12 >= abs(point):
            extreme += 1
    p_value = min(1.0, max(extreme / n_permutations, 1 / (n_permutations + 1)))
    return {
        "difference": point,
        "n_permutations": n_permutations,
        "p_value": p_value,
        "seed": seed,
    }

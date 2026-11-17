"""Registered names for the YRSS evaluation v3. No thresholds live here.

Numeric operating-point cutoffs, the population size, and the fine-tune
hyperparameters are not known yet. They stay out of this module until an
addendum freezes them, before any test scoring.
"""

from __future__ import annotations

VERSION = "yrss-eval-v3"
PROTOCOL = "docs/decisions/2026-11-17-yrss-eval-v3.md"
KEY_ENV = "YRSS_V3_TEST_KEY_FILE"
BLIND_VERSION = "yrss-v3-test"
# k=5 is the owner's registered uniqueness threshold (2026-11-17).
K_ANONYMITY = 5
OPERATING_POINTS = ("recall-first", "balanced", "precision-first")
# One scoring run of test-v3. The v2 test split is not scored again.
TEST_SCORES_ALLOWED = 1
# Shortest fixed-text copy that the contamination check treats as a family leak.
MIN_COPY_CHARS = 40

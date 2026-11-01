"""Reproducible blind-v2 comparison corpus.

This package generates a synthetic Thai PII set from a fixed seed and checks
it against a committed hash. Rendered documents are not committed. Detector
code under ``pii_redactor/`` and ``app/`` must not import this package.

The sealed protocol blobs ``benchmark/data/blind-v1.enc`` and
``benchmark/data/blind-v2.enc`` are a different artifact. Do not decrypt them
here, and do not tune detectors against this set. Tuning stays on the gold set.
"""

from .corpus import (
    GENERATION_SEED,
    VERSION,
    generate_corpus,
    load_lock,
    public_lock,
)

__all__ = [
    "GENERATION_SEED",
    "VERSION",
    "generate_corpus",
    "load_lock",
    "public_lock",
]

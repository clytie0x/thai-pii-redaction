"""One source for the product/detector version every PDPA artifact records.

receipt.py, breach.py and dsar.py used to carry identical private copies that
read a repo-root VERSION file — which an installed wheel does not have, so a
pip user's receipts said "unknown". The shared helper asks distribution
metadata, the same answer `amphrang.__version__` gives."""

from __future__ import annotations

import amphrang
from amphrang.engine import breach, dsar, environment, receipt


def test_product_version_matches_facade_version():
    assert environment.product_version() == amphrang.__version__
    assert environment.product_version() not in ("", "unknown")


def test_detector_version_names_pythainlp():
    assert environment.detector_version().startswith("pythainlp ")


def test_environment_has_the_three_recorded_fields():
    env = environment.environment()
    assert set(env) == {"product_version", "ner_engine", "detector_version"}
    assert env["product_version"] == amphrang.__version__


def test_artifact_modules_share_the_helper():
    assert receipt._environment is environment.environment
    assert breach._environment is environment.environment
    assert dsar._environment is environment.environment

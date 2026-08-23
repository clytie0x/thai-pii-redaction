"""The environment block every PDPA artifact records: product build, NER engine, detector release.

Single implementation reading distribution metadata, which is right in both an editable
checkout and a wheel (a repo-root VERSION file is absent from wheels).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from amprang.engine.detectors.tb_detector import _resolve_engine_name


def product_version() -> str:
    """Installed amprang version, or ``"unknown"``; never a hardcoded literal."""
    try:
        return version("amprang")
    except PackageNotFoundError:
        return "unknown"


def detector_version() -> str:
    """The PyThaiNLP release that produced the result; the ``>=`` floor lets two machines with
    the same product_version run different CRF models, which this field makes visible.
    """
    try:
        return f"pythainlp {version('pythainlp')}"
    except PackageNotFoundError:
        return "unknown"


def environment() -> dict:
    return {
        "product_version": product_version(),
        "ner_engine": _resolve_engine_name(),
        "detector_version": detector_version(),
    }

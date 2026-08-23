"""The environment block every PDPA artifact (receipt, breach assessment, DSAR
locate) records: which product build, which NER engine, which detector
release produced the result.

One implementation on purpose. The artifact modules used to carry identical
private copies that read a repo-root ``VERSION`` file; an installed wheel has
no such file, so a pip user's receipts reported ``"unknown"``. Distribution
metadata is the answer that is right in both a source checkout (editable
install) and a wheel, and it is what ``amprang.__version__`` already reports.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from amprang.engine.detectors.tb_detector import _resolve_engine_name


def product_version() -> str:
    """The installed amprang version, or ``"unknown"`` outside any install.

    Never a hardcoded literal: a receipt that guesses its own version is worse
    than one that admits it does not know.
    """
    try:
        return version("amprang")
    except PackageNotFoundError:
        return "unknown"


def detector_version() -> str:
    """The PyThaiNLP release that produced the detection result.

    ``requirements.txt`` carries a loose ``>=`` floor, so two machines with the
    same ``product_version`` can run different CRF models. Without this field
    a genuine model difference surfaces as a ``result_mismatch`` with an empty
    list of differences.
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

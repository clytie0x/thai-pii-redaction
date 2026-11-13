"""Systems scored in the YRSS evaluation v2.

``build(name)`` returns ``predict(text) -> [(start, end, type)]``. Optional
packages are imported only when their system is selected. A selected system
that cannot run raises ``SystemUnavailable``; nothing falls back to another
engine.
"""

from __future__ import annotations

import importlib.util
import re
from collections.abc import Callable

from benchmark.blind_v2.score import dedupe_predictions

Prediction = tuple[int, int, str]
Predictor = Callable[[str], list[Prediction]]

REFERENCE = "aiguard"
# The five comparisons of question Q2, in protocol order.
COMPARATORS = ("regex", "crf-ner", "wangchanberta-ner", "presidio", "llm")
# Report name -> layer name in benchmark/blind_v2/ablate.py.
ABLATIONS = {
    "aiguard-no-fp": "fp",
    "aiguard-no-tb": "tb",
    "aiguard-no-address_merge": "address_merge",
}

# Same shape as the product rule: 8 digits soon after a licence cue.
# No digit and no line break may sit between the cue and the number.
_LICENCE_RE = re.compile(
    r"(?:ใบขับขี่|ใบอนุญาตขับขี่|ใบอนุญาตขับรถ"
    r"|driving\s+licen[cs]e|driver(?:['’]?s)?\s+licen[cs]e)"
    r"[^\d\n]{0,24}?(\d{8})(?!\d)",
    re.IGNORECASE,
)


class SystemUnavailable(RuntimeError):
    """A selected system cannot run. The message names what is missing."""


def _importable(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _require(system: str, *packages: tuple[str, str]) -> None:
    """Each item is ``(import name, name to install)``."""
    missing = [install for module, install in packages if not _importable(module)]
    if missing:
        raise SystemUnavailable(f"{system} needs {', '.join(missing)}, which is not installed")


def _deduped(predict: Callable[[str], list]) -> Predictor:
    def run(text: str) -> list[Prediction]:
        found = [(int(start), int(end), str(label)) for start, end, label in predict(text)]
        return dedupe_predictions(found)

    # Keep a remote predictor's counters reachable through the wrapper.
    if isinstance(getattr(predict, "stats", None), dict):
        run.stats = predict.stats
    return run


def licence_spans(text: str) -> list[Prediction]:
    return [(m.start(1), m.end(1), "DRIVER_LICENSE") for m in _LICENCE_RE.finditer(text)]


def _aiguard(layer: str | None) -> Predictor:
    _require("aiguard", ("pythainlp", "pythainlp"))
    from benchmark.blind_v2.ablate import predict_ablated

    return _deduped(lambda text: predict_ablated(text, layer))


def _regex() -> Predictor:
    from benchmark.blind_v2.baselines import regex_predict

    return _deduped(lambda text: regex_predict(text) + licence_spans(text))


def _prepared(baseline) -> Predictor:
    """Load an older baseline now, so a load failure is an error and not a skip."""
    reason = baseline.prepare()
    if reason:
        raise SystemUnavailable(reason)
    return _deduped(baseline.predict)


def _crf_ner() -> Predictor:
    _require("crf-ner", ("pythainlp", "pythainlp"), ("pycrfsuite", "python-crfsuite"))
    from benchmark.blind_v2.baselines import PyThaiNLPNER

    return _prepared(PyThaiNLPNER())


def _wangchanberta_ner() -> Predictor:
    _require(
        "wangchanberta-ner",
        ("pythainlp", "pythainlp"),
        ("transformers", "transformers"),
        ("torch", "torch"),
    )
    from benchmark.blind_v2.baselines import WangchanBERTaNER

    return _prepared(WangchanBERTaNER())


def _presidio() -> Predictor:
    _require("presidio", ("presidio_analyzer", "presidio-analyzer"), ("spacy", "spacy"))
    from benchmark.blind_v2.baselines import PresidioBaseline

    return _prepared(PresidioBaseline())


def _llm(llm_options: dict | None) -> Predictor:
    options = dict(llm_options or {})
    if not options.get("base_url") or not options.get("model"):
        raise ValueError("the llm system needs base_url and model")
    if options.get("seed") is None:
        raise ValueError("the llm system needs a seed")
    # Another module owns the client. Import it only when the llm is selected.
    from benchmark.yrss_v2.llm_openai import make_predictor

    extra = {"timeout": float(options["timeout"])} if options.get("timeout") else {}
    return _deduped(
        make_predictor(
            base_url=str(options["base_url"]),
            model=str(options["model"]),
            api_key_env=options.get("api_key_env"),
            seed=int(options["seed"]),
            **extra,
        )
    )


_FACTORIES: dict[str, Callable[[dict | None], Predictor]] = {
    REFERENCE: lambda options: _aiguard(None),
    "regex": lambda options: _regex(),
    "crf-ner": lambda options: _crf_ner(),
    "wangchanberta-ner": lambda options: _wangchanberta_ner(),
    "presidio": lambda options: _presidio(),
    "llm": _llm,
    **{name: (lambda options, layer=layer: _aiguard(layer)) for name, layer in ABLATIONS.items()},
}


def system_names() -> tuple[str, ...]:
    return tuple(_FACTORIES)


def build(name: str, *, llm_options: dict | None = None) -> Predictor:
    """Return the predictor for ``name``. Its output is already deduplicated."""
    if name not in _FACTORIES:
        raise ValueError(f"unknown system {name}")
    return _FACTORIES[name](llm_options)

"""Run AI Guard's detector with one assembly layer removed.

The full path (``disabled is None``) calls the same functions as
``detect_all`` in the same order. A unit test locks that equality. This
module does not change detection rules. Source recovery and label normalization
remain enabled in every assembly-layer variant.
"""

from __future__ import annotations

LAYERS = (
    "fp",
    "tb",
    "fn",
    "record_names",
    "address_merge",
    "facility_filter",
    "student_relabel",
)


def predict_ablated(text: str, disabled: str | None = None) -> list[tuple[int, int, str]]:
    if disabled is not None and disabled not in LAYERS:
        raise ValueError(f"unknown layer {disabled}")
    from pii_redactor.detectors.aggregate import (
        _drop_unanchored_facility_spans,
        _extend_address_chains,
        _prefer_record_names,
        _relabel_numberless_addresses,
        _relabel_student_ids,
        dedupe_spans,
        merge_address_spans,
    )
    from pii_redactor.detectors.fn_scanner import scan_fn
    from pii_redactor.detectors.fp_detector import detect_fp
    from pii_redactor.detectors.name_context import detect_parallel_record_names
    from pii_redactor.detectors.scan_views import original_guard_entities
    from pii_redactor.detectors.structured_views import admit_recovery, recover_structured
    from pii_redactor.detectors.tb_detector import detect_tb

    off = disabled
    fp = [] if off == "fp" else detect_fp(text)
    tb = [] if off == "tb" else detect_tb(text)
    fn = [] if off == "fn" else scan_fn(text, fp + tb)
    record_names = [] if off == "record_names" else detect_parallel_record_names(text, fp + tb + fn)
    deduped = dedupe_spans([*fp, *tb, *fn, *record_names])
    preferred = deduped if off == "record_names" else _prefer_record_names(deduped, record_names)
    if off == "address_merge":
        kept = preferred
    else:
        kept = merge_address_spans(text, preferred)
        kept = _extend_address_chains(text, kept, tb)
    kept = _relabel_numberless_addresses(kept)
    if off != "facility_filter":
        kept = _drop_unanchored_facility_spans(text, kept)
    if off != "student_relabel":
        kept = _relabel_student_ids(tb, kept)
    recovered = recover_structured(text)
    kept = admit_recovery(
        kept,
        recovered,
        required=original_guard_entities(text) if recovered else (),
    )
    return [(entity.span[0], entity.span[1], entity.data_type) for entity in kept]


class AIGuard:
    name = "aiguard"
    cost_usd = 0.0

    def prepare(self) -> str | None:
        try:
            import pythainlp  # noqa: F401
        except ImportError:
            return "pythainlp is not installed; AI Guard was not run"
        return None

    def predict(self, text: str) -> list[tuple[int, int, str]]:
        return predict_ablated(text, None)

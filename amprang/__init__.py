"""Amprang — Thai PII detection, anonymization, and redaction.

The public, semver-stable surface of the ``amprang`` package is exactly what
this module exports:

    detect(text)                     -> list[Entity]
    anonymize(text, mode=...)        -> AnonymizeResult   (.text, .mapping)
    restore(text, mapping)           -> RestoreResult     (.text)
    analyze(text)                    -> dict              (PDPA risk analysis)
    redact_pdf(input, output)        -> RedactionResult
    Session(...)                     — multi-turn anonymize/restore with an
                                       in-memory vault (mapping never leaves
                                       this process)

plus the ``Entity`` dataclass and the result dataclasses above. Everything
under ``amprang.engine.*`` is the internal engine and carries no stability
contract between releases.

Privacy note: ``anonymize`` hands the pseudonym→original mapping back to the
caller. Once it crosses this boundary, keeping it out of logs, disks, and
telemetry is the caller's responsibility. Prefer ``Session`` when the mapping
can stay inside your process for the conversation's lifetime.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from dataclasses import replace as _dc_replace
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from pathlib import Path

from amprang.engine.detectors.aggregate import detect_all as _detect_all
from amprang.engine.ingest.text_cleaner import clean as _clean
from amprang.engine.ingest.text_cleaner import clean_length_preserving as _clean_lp
from amprang.engine.models import Entity, EntityRegistry
from amprang.engine.report import analyze_text as _analyze_text
from amprang.engine.session_service import OutboundLeakError as _OutboundLeakError
from amprang.engine.session_service import SessionExpiredError, _identity_finalize
from amprang.engine.session_service import SessionService as _SessionService
from amprang.engine.stateless import (
    StatelessLeakError,
)
from amprang.engine.stateless import (
    restore_stateless as _restore_stateless,
)
from amprang.engine.stateless import (
    sanitize_stateless as _sanitize_stateless,
)

try:
    __version__ = _dist_version("amprang")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0.dev0"

__all__ = [
    "AnonymizeResult",
    "Entity",
    "LeakBlockedError",
    "RedactionResult",
    "RestoreResult",
    "Session",
    "SessionExpiredError",
    "analyze",
    "anonymize",
    "detect",
    "redact_pdf",
    "restore",
]

# Re-exported so callers can catch the fail-closed outbound block without
# importing internals. The engine raises it when a masked result would still
# carry structured, text-based, or digit-run residual PII.
LeakBlockedError = StatelessLeakError


def detect(text: str) -> list[Entity]:
    """Detect Thai PII in ``text`` and return deduplicated entities.

    Detection runs on a length-preserving normalization (Thai digits to
    Arabic only), so every ``Entity.span`` indexes directly into the caller's
    ``text`` and ``Entity.original_text`` is the exact slice of it.
    """
    entities = _detect_all(_clean_lp(text))
    return [
        _dc_replace(entity, original_text=text[entity.span[0] : entity.span[1]])
        for entity in entities
    ]


@dataclass
class AnonymizeResult:
    """A masked text plus the mapping needed to restore it."""

    text: str
    mapping: dict[str, str]
    entities: list[dict]
    entity_type_counts: dict[str, int]
    warnings: list[str] = field(default_factory=list)


def anonymize(
    text: str,
    *,
    mode: str = "token",
    salt: str | None = None,
    prior_mapping: dict[str, str] | None = None,
) -> AnonymizeResult:
    """Replace detected PII with tokens (``mode="token"``) or realistic
    surrogates (``mode="surrogate"``).

    Fails closed: if the masked result would still contain residual PII the
    call raises ``LeakBlockedError`` instead of returning a partial mask.
    Passing the same ``salt`` makes surrogate output reproducible; passing a
    previous call's ``mapping`` as ``prior_mapping`` keeps token continuity
    across calls.
    """
    # detection_text mirrors detect(): without the length-preserving Thai-digit
    # normalization a Thai-numeral phone number is never detected — and never
    # masked (the engine only applies it when the caller passes it in).
    result = _sanitize_stateless(
        text,
        mode=mode,
        salt=salt or secrets.token_hex(16),
        prior_mapping=prior_mapping,
        detection_text=_clean_lp(text),
    )
    return AnonymizeResult(
        text=result.sanitized_text,
        mapping=dict(result.mapping),
        entities=list(result.entities),
        entity_type_counts=dict(result.entity_type_counts),
        warnings=list(result.warnings),
    )


@dataclass
class RestoreResult:
    """A restored text plus counters describing how complete the restore was.

    ``generated_pii_count`` > 0 means the AI's reply contained values that look
    like real PII but were never in the mapping — review before publishing.
    ``foreign_replacement_count`` counts product-shaped tokens from some other
    session; they are left untouched.
    """

    text: str
    replaced_count: int
    leftover_pseudonyms: list[str]
    warnings: list[str] = field(default_factory=list)
    generated_pii_count: int = 0
    foreign_replacement_count: int = 0


def _restore_warnings(warnings: list[str], generated: int, foreign: int) -> list[str]:
    merged = list(warnings)
    if generated and "ai_generated_pii" not in merged:
        merged.append("ai_generated_pii")
    if foreign and "foreign_replacement" not in merged:
        merged.append("foreign_replacement")
    return merged


def restore(
    text: str,
    mapping: dict[str, str],
    *,
    mode: str | None = None,
) -> RestoreResult:
    """Restore originals into ``text`` using a mapping from ``anonymize``."""
    result = _restore_stateless(text, mapping=mapping, mode=mode)
    return RestoreResult(
        text=result.restored_text,
        replaced_count=result.replaced_count,
        leftover_pseudonyms=list(result.leftover_pseudonyms),
        warnings=_restore_warnings(
            result.warnings,
            result.generated_pii_count,
            result.foreign_replacement_count,
        ),
        generated_pii_count=result.generated_pii_count,
        foreign_replacement_count=result.foreign_replacement_count,
    )


def analyze(text: str) -> dict:
    """PDPA-oriented risk analysis: entity counts, Section 26 signals, and a
    re-identification risk score. The result contains no raw PII values."""
    # Full clean first — the analyzer is documented for cleaned text, and the
    # result carries no spans, so offset-shifting normalization is safe here.
    return _analyze_text(_clean(text).text)


@dataclass
class RedactionResult:
    """Outcome of a PDF redaction."""

    output_path: Path
    entity_count: int
    entity_type_counts: dict[str, int]
    human_review: bool
    warnings: list[str] = field(default_factory=list)


def redact_pdf(input_path: str | Path, output_path: str | Path) -> RedactionResult:
    """Permanently black out detected PII in a PDF and flatten the result.

    Word boxes are selected only by authoritative source-interval
    intersection; if the text-to-box mapping is missing or unsafe the call
    fails before writing output rather than guessing. Scanned/hybrid pages
    need the ``amprang[ocr]`` extra.
    """
    from amprang.engine.ingest.file_detector import detect_source_type
    from amprang.engine.ingest.text_extractor import extract
    from amprang.engine.redactor import redact_pdf as _redact

    in_path = Path(input_path)
    out_path = Path(output_path)
    source_type = detect_source_type(in_path)
    raw_text, word_bboxes, meta = extract(in_path, source_type)
    entities = _detect_all(_clean_lp(raw_text))
    fp_count = sum(entity.redact_type == "FP" for entity in entities)
    registry = EntityRegistry(
        entities=entities,
        fp_count=fp_count,
        tb_count=len(entities) - fp_count,
    )
    _redact(str(in_path), registry, word_bboxes, str(out_path))
    counts: dict[str, int] = {}
    for entity in entities:
        counts[entity.data_type] = counts.get(entity.data_type, 0) + 1
    return RedactionResult(
        output_path=out_path,
        entity_count=len(entities),
        entity_type_counts=counts,
        human_review=bool(meta.get("human_review")),
        warnings=list(meta.get("warnings", [])),
    )


class Session:
    """Multi-turn anonymize/restore with an in-memory vault.

    Unlike ``anonymize``/``restore``, the pseudonym→original mapping never
    leaves this object: the same entity keeps the same pseudonym across
    turns, and ``restore`` works without the caller ever holding the mapping.
    The vault lives only in process memory and is dropped by ``close`` (also
    called by ``with`` exit). ``ttl_s`` is enforced on access: a session idle
    longer than that raises ``SessionExpiredError`` on the next call — there
    is no background sweeper, so call ``close`` to drop the mapping promptly.

    A blocked mask raises ``LeakBlockedError``, same as ``anonymize``.
    """

    def __init__(self, *, mode: str = "token", ttl_s: int = 1800):
        self._service = _SessionService(cap=1, ttl_s=ttl_s)
        self._mode = mode
        self._session_id: str | None = None

    def anonymize(self, text: str) -> AnonymizeResult:
        try:
            outcome = self._service.sanitize_transaction(
                text,
                mode=self._mode,
                session_id=self._session_id,
                detection_text=_clean_lp(text),
                finalize=_identity_finalize,
            )
        except _OutboundLeakError as error:
            raise LeakBlockedError(
                list(error.leak_types),
                policy_categories=list(error.policy_categories),
            ) from None
        self._session_id = outcome.session_id
        return AnonymizeResult(
            text=outcome.sanitized_text,
            mapping={},  # deliberately withheld: the vault owns it
            entities=list(outcome.entities),
            entity_type_counts=dict(outcome.entity_type_counts),
            warnings=list(outcome.warnings),
        )

    def restore(self, text: str) -> RestoreResult:
        if self._session_id is None:
            raise ValueError("nothing anonymized in this session yet")
        outcome = self._service.restore(self._session_id, text)
        return RestoreResult(
            text=outcome.restored_text,
            replaced_count=outcome.replaced_count,
            leftover_pseudonyms=list(outcome.leftover_tokens),
            warnings=_restore_warnings(
                outcome.warnings,
                outcome.generated_pii_count,
                outcome.foreign_replacement_count,
            ),
            generated_pii_count=outcome.generated_pii_count,
            foreign_replacement_count=outcome.foreign_replacement_count,
        )

    def close(self) -> None:
        if self._session_id is not None:
            self._service.drop(self._session_id)
            self._session_id = None
        self._service.close()

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

"""Amphrang — Thai PII detection and anonymization.

The public, semver-stable surface of the ``amphrang`` package is exactly what
this module exports:

    detect(text)                     -> list[Entity]
    detect_batch(texts)              -> list[list[Entity]]
    anonymize(text, mode=...)        -> AnonymizeResult   (.text, .mapping)
    anonymize_batch(texts, mode=...) -> list[AnonymizeResult]
    restore(text, mapping)           -> RestoreResult     (.text)
    analyze(text)                    -> dict              (PDPA risk analysis)
    Session(...)                     — multi-turn anonymize/restore with an
                                       in-memory vault (mapping never leaves
                                       this process)

plus the ``Entity`` dataclass and the result dataclasses above. Everything
under ``amphrang.engine.*`` is internal and carries no stability contract.

Privacy note: ``anonymize`` hands the pseudonym→original mapping to the caller,
who then owns keeping it out of logs, disks, and telemetry. Prefer ``Session``
when the mapping can stay inside your process.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from dataclasses import replace as _dc_replace
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

from pii_redactor.config import CoreConfig
from pii_redactor.detectors.aggregate import detect_all as _detect_all
from pii_redactor.detectors.ner_failure import NERFailureError, ner_failure_metadata
from pii_redactor.ingest.text_cleaner import clean as _clean
from pii_redactor.ingest.text_cleaner import clean_length_preserving as _clean_lp
from pii_redactor.models import Entity
from pii_redactor.report import analyze_text as _analyze_text
from pii_redactor.report import project_analysis as _project_analysis
from pii_redactor.safe_errors import discard_exception_graph, minimize_failure_frames
from pii_redactor.session_service import OutboundLeakError as _OutboundLeakError
from pii_redactor.session_service import SessionExpiredError, _identity_finalize
from pii_redactor.session_service import SessionService as _SessionService
from pii_redactor.stateless import (
    StatelessLeakError,
)
from pii_redactor.stateless import (
    restore_stateless as _restore_stateless,
)
from pii_redactor.stateless import (
    sanitize_stateless as _sanitize_stateless,
)

from amphrang._core_config import sdk_core_config

try:
    __version__ = _dist_version("amphrang")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0.dev0"

__all__ = [
    "AnonymizeResult",
    "Entity",
    "LeakBlockedError",
    "RestoreResult",
    "Session",
    "SessionExpiredError",
    "analyze",
    "anonymize",
    "anonymize_batch",
    "detect",
    "detect_batch",
    "restore",
]

# Re-exported so callers can catch the fail-closed outbound block without importing internals.
LeakBlockedError = StatelessLeakError


def _require_local_config(config: CoreConfig) -> None:
    if not isinstance(config, CoreConfig):
        raise TypeError("SDK config must be a CoreConfig")
    if config.allow_remote:
        raise ValueError("SDK remote engines are disabled")


@minimize_failure_frames
def detect(text: str) -> list[Entity]:
    """Detect Thai PII in ``text`` and return deduplicated entities.

    Detection runs on a length-preserving normalization (Thai digits to
    Arabic only), so every ``Entity.span`` indexes directly into the caller's
    ``text`` and ``Entity.original_text`` is the exact slice of it.
    """
    return _detect_with_config(text, config=sdk_core_config())


@minimize_failure_frames
def _detect_with_config(text: str, *, config: CoreConfig) -> list[Entity]:
    _require_local_config(config)
    entities = _detect_all(_clean_lp(text), config=config)
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


@minimize_failure_frames
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
    return _anonymize_with_config(
        text, mode=mode, salt=salt, prior_mapping=prior_mapping, config=sdk_core_config()
    )


@minimize_failure_frames
def _anonymize_with_config(
    text: str,
    *,
    mode: str = "token",
    salt: str | None = None,
    prior_mapping: dict[str, str] | None = None,
    config: CoreConfig,
) -> AnonymizeResult:
    # Keep caller spans while recognizing Thai numerals.
    _require_local_config(config)
    result = _sanitize_stateless(
        text,
        mode=mode,
        salt=salt or secrets.token_hex(16),
        prior_mapping=prior_mapping,
        detection_text=_clean_lp(text),
        config=config,
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


@minimize_failure_frames
def restore(
    text: str,
    mapping: dict[str, str],
    *,
    mode: str | None = None,
) -> RestoreResult:
    """Restore originals into ``text`` using a mapping from ``anonymize``."""
    return _restore_with_config(text, mapping, mode=mode, config=sdk_core_config())


@minimize_failure_frames
def _restore_with_config(
    text: str,
    mapping: dict[str, str],
    *,
    mode: str | None = None,
    config: CoreConfig,
) -> RestoreResult:
    _require_local_config(config)
    result = _restore_stateless(text, mapping=mapping, mode=mode, config=config)
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


_LEAK_SENTINEL = "__amphrang_leak_blocked__"
_NER_SENTINEL = "__amphrang_ner_failed__"


@minimize_failure_frames
def _detect_one(job: tuple[str, CoreConfig]):
    text, config = job
    try:
        return _detect_with_config(text, config=config)
    except NERFailureError as error:
        failure = (_NER_SENTINEL, *ner_failure_metadata(error))
        discard_exception_graph(error)
        return failure


@minimize_failure_frames
def _anonymize_one(job: tuple[str, str, str | None, CoreConfig]):
    """One anonymize for the batch paths. A leak block comes back as a plain
    tuple, not the exception: exceptions with keyword-only constructors do
    not survive the process-pool pickle round trip."""
    text, mode, salt, config = job
    try:
        return _anonymize_with_config(text, mode=mode, salt=salt, config=config)
    except LeakBlockedError as error:
        failure = (_LEAK_SENTINEL, list(error.leak_types), list(error.policy_categories))
        discard_exception_graph(error)
        return failure
    except NERFailureError as error:
        failure = (_NER_SENTINEL, *ner_failure_metadata(error))
        discard_exception_graph(error)
        return failure


@minimize_failure_frames
def _run_in_pool(fn, jobs: list, workers: int) -> list:
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
        return list(pool.map(fn, jobs))


@minimize_failure_frames
def detect_batch(texts: list[str], *, workers: int = 1) -> list[list[Entity]]:
    """``detect`` over many texts, one entity list per input, in order.

    ``workers > 1`` runs across a process pool; every worker pays the NER
    model load once, so it only pays off for large batches. Results are
    identical to calling ``detect`` in a loop.
    """
    config = sdk_core_config()
    jobs = [(text, config) for text in texts]
    if workers > 1 and len(jobs) > 1:
        outcomes = _run_in_pool(_detect_one, jobs, workers)
    else:
        outcomes = [_detect_one(job) for job in jobs]
    for outcome in outcomes:
        _raise_ner_failure(outcome)
    return outcomes


def _raise_ner_failure(outcome) -> None:
    if isinstance(outcome, tuple) and outcome and outcome[0] == _NER_SENTINEL:
        raise NERFailureError(outcome[1], category=outcome[2], count=outcome[3])


@minimize_failure_frames
def anonymize_batch(
    texts: list[str],
    *,
    mode: str = "token",
    salt: str | None = None,
    workers: int = 1,
) -> list[AnonymizeResult]:
    """``anonymize`` over many texts, one ``AnonymizeResult`` per input.

    Items are independent: with ``salt=None`` each gets its own random salt
    (same as calling ``anonymize`` in a loop); passing a ``salt`` makes the
    whole batch reproducible. Fails closed as a unit — the first item whose
    mask would still leak raises ``LeakBlockedError`` with the offending
    position in ``batch_index``, and no partial batch is returned.
    ``workers`` behaves as in ``detect_batch``.
    """
    config = sdk_core_config()
    jobs = [(text, mode, salt, config) for text in texts]
    if workers > 1 and len(jobs) > 1:
        outcomes = _run_in_pool(_anonymize_one, jobs, workers)
    else:
        outcomes = [_anonymize_one(job) for job in jobs]

    results: list[AnonymizeResult] = []
    for index, outcome in enumerate(outcomes):
        _raise_ner_failure(outcome)
        if isinstance(outcome, tuple) and outcome and outcome[0] == _LEAK_SENTINEL:
            error = LeakBlockedError(outcome[1], policy_categories=outcome[2])
            error.batch_index = index
            raise error
        results.append(outcome)
    return results


@minimize_failure_frames
def analyze(text: str) -> dict:
    """PDPA-oriented risk analysis: entity counts, Section 26 signals, and a
    re-identification risk score. The result contains no raw PII values."""
    return _analyze_with_config(text, config=sdk_core_config())


@minimize_failure_frames
def _analyze_with_config(text: str, *, config: CoreConfig) -> dict:
    _require_local_config(config)
    return _project_analysis(_analyze_text(_clean(text).text, config=config))


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
        self._service = _SessionService(cap=1, ttl_s=ttl_s, config=sdk_core_config())
        self._mode = mode
        self._session_id: str | None = None

    @minimize_failure_frames
    def anonymize(self, text: str) -> AnonymizeResult:
        failure = None
        try:
            outcome = self._service.sanitize_transaction(
                text,
                mode=self._mode,
                session_id=self._session_id,
                detection_text=_clean_lp(text),
                finalize=_identity_finalize,
            )
        except _OutboundLeakError as error:
            failure = (list(error.leak_types), list(error.policy_categories))
            discard_exception_graph(error)
        if failure is not None:
            raise LeakBlockedError(failure[0], policy_categories=failure[1])
        self._session_id = outcome.session_id
        return AnonymizeResult(
            text=outcome.sanitized_text,
            mapping={},  # deliberately withheld: the vault owns it
            entities=list(outcome.entities),
            entity_type_counts=dict(outcome.entity_type_counts),
            warnings=list(outcome.warnings),
        )

    @minimize_failure_frames
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

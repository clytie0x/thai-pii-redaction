"""Outbound PII leak scan shared by the CLI pre-send guard and the web path.

A "leak" is a detector hit in already-pseudonymized text that pseudonym
occurrences cannot account for. Fuzzy NER spans around embedded pseudonyms
are excused via position-based overlap + per-segment remainder scans + a
cue-preserving name_context re-check (see PR #33/#34 history).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from pii_redactor.detectors import scan_views as _shared_views
from pii_redactor.detectors.fp_detector import detect_fp
from pii_redactor.detectors.name_context import detect_name_context
from pii_redactor.detectors.tb_detector import detect_tb
from pii_redactor.models import Entity
from pii_redactor.native_broker_context import native_broker_detector_phase
from pii_redactor.pdpa_categories import canonical_section26


class _GuardContext(Protocol):
    """Minimum trusted state needed by the outbound policy."""

    def trusted_pseudonyms(self) -> set[str]: ...


@dataclass(frozen=True, slots=True)
class OutboundGuardContext:
    """Original-free, repr-hidden context for rechecking a masked result."""

    _trusted: frozenset[str] = field(default_factory=frozenset, repr=False)

    def trusted_pseudonyms(self) -> set[str]:
        return set(self._trusted)


SAFE_OUTBOUND_LEAK_TYPES = frozenset(
    {
        "ADDRESS",
        "ANONYMIZE_FAILED",
        "BANK_ACCOUNT",
        "CREDIT_CARD",
        "CRIMINAL_RECORD",
        "DATE",
        "DATE_OF_BIRTH",
        "DISABILITY",
        "EMAIL",
        "HEALTH",
        "IBAN",
        "ID_NUMBER",
        "LABOR_UNION",
        "LOCATION",
        "MEDICAL_ID",
        "MISSING_REPLACEMENT_RECORD",
        "NAME",
        "ORGANIZATION",
        "ORPHAN_DIGITS",
        "PASSPORT",
        "PHONE",
        "POLITICAL_OPINION",
        "POSTAL_CODE",
        "RACE_ETHNICITY",
        "RELIGION",
        "SEXUAL_BEHAVIOR",
        "STUDENT_ID",
        "SURNAME",
        "THAI_ID",
        "UNCLASSIFIED_RESIDUAL",
        "VEHICLE_PLATE",
    }
)
_POLICY_CATEGORIES = frozenset(
    {"structured", "text", "detector_independent", "replacement_integrity"}
)


def normalize_outbound_leak_types(labels: object) -> list[str]:
    """Deduplicate fixed type labels without retaining injected values."""
    if not isinstance(labels, (list, tuple, set, frozenset)):
        return ["UNCLASSIFIED_RESIDUAL"]
    safe: set[str] = set()
    invalid = False
    for label in labels:
        if not isinstance(label, str):
            invalid = True
            continue
        canonical = canonical_section26(label)
        if canonical is not None:
            safe.add(canonical)
        elif label in SAFE_OUTBOUND_LEAK_TYPES:
            safe.add(label)
        else:
            invalid = True
    if invalid or not safe:
        safe.add("UNCLASSIFIED_RESIDUAL")
    return sorted(safe)


def _safe_policy_categories(categories: set[str] | list[str] | tuple[str, ...]) -> list[str]:
    return sorted(
        {
            category
            for category in categories
            if isinstance(category, str) and category in _POLICY_CATEGORIES
        }
    )


class OutboundPolicyError(Exception):
    """Value-free residual classification raised before outbound use."""

    def __init__(
        self,
        leak_types: list[str] | set[str] | tuple[str, ...],
        *,
        policy_categories: set[str] | list[str] | tuple[str, ...],
    ):
        self.leak_types = normalize_outbound_leak_types(leak_types)
        self.policy_categories = _safe_policy_categories(policy_categories)
        self.category_count = len(self.policy_categories)
        self.policy_category_count = self.category_count
        super().__init__(f"outbound residual detected: {self.leak_types}")


def pseudonym_ranges(text: str, pseudonyms: list[str]) -> list[tuple[int, int]]:
    """
    Character ranges of every known-pseudonym occurrence in text.

    Longest pseudonym first so a shorter pseudonym cannot claim a slice of a
    longer one (same ordering rule as reverse_mapper); ranges never overlap.
    """
    claimed: list[tuple[int, int]] = []

    def _taken(start: int, end: int) -> bool:
        return any(start < ce and end > cs for cs, ce in claimed)

    for p in sorted(pseudonyms, key=len, reverse=True):
        pos = 0
        while (i := text.find(p, pos)) >= 0:
            if not _taken(i, i + len(p)):
                claimed.append((i, i + len(p)))
            pos = i + 1
    return claimed


def _cue_leak_in_window(
    text: str,
    start: int,
    end: int,
    ranges: list[tuple[int, int]],
) -> bool:
    """Find cue-linked text outside trusted pseudonym occurrences."""
    ctx_start = max(0, start - 16)
    window = text[ctx_start:end]
    for candidate in detect_name_context(window):
        candidate_start = ctx_start + candidate.span[0]
        candidate_end = ctx_start + candidate.span[1]
        for index in range(max(candidate_start, start), min(candidate_end, end)):
            if text[index].strip() and not any(
                claimed_start <= index < claimed_end for claimed_start, claimed_end in ranges
            ):
                return True
    return False


# A digit run this long is an identifier, not a quantity, in the documents this
# system handles. Six is deliberately below the numeric detectors' eight-digit
# floor: that floor is precisely the gap a hospital number or a short reference
# number falls through.
_ORPHAN_DIGITS_RE = re.compile(r"(?<!\d)(\d{6,})(?!\d)")
_REPEATED_WHITESPACE_RE = re.compile(r"\s{2,}")
_SPACED_IBAN_START_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2}\d{2})(?= )")
_SPACED_IBAN_GROUP_RE = re.compile(r"([A-Z0-9]{1,4})(?![A-Z0-9])")
_MAX_IBAN_LENGTH = 34
_MAX_IBAN_GROUPS = 9
_OBFUSCATED_STRUCTURED_TYPES = _shared_views.OBFUSCATED_STRUCTURED_TYPES
_OBFUSCATED_SIGNAL_PREFIX = "obfuscated_structured:"


def _has_security_view_trigger(text: str) -> bool:
    return _REPEATED_WHITESPACE_RE.search(text) is not None or any(
        unicodedata.category(character) == "Cf" or 0xFF01 <= ord(character) <= 0xFF5E
        for character in text
    )


def _security_scan_view(text: str) -> tuple[str, list[int]]:
    return _shared_views._security_scan_view(text)


def _map_security_view_entities(text, security_view, source_offsets, *, allowed_types):
    return _shared_views._map_security_view_entities(
        text, security_view, source_offsets, allowed_types=allowed_types
    )


def _single_spaced_iban_views(text: str) -> list[tuple[str, list[int]]]:
    return _shared_views._single_spaced_iban_views(text, group_pattern=_SPACED_IBAN_GROUP_RE)


def scan_obfuscated_structured_entities(text: str) -> list[Entity]:
    """Detect structured PII in bounded scan views and map hits to source spans."""
    mapped: list[Entity] = []
    if _has_security_view_trigger(text):
        security_view, source_offsets = _security_scan_view(text)
        mapped.extend(
            _map_security_view_entities(
                text,
                security_view,
                source_offsets,
                allowed_types=_OBFUSCATED_STRUCTURED_TYPES,
            )
        )
        for compact, offsets in _single_spaced_iban_views(security_view):
            mapped.extend(
                _map_security_view_entities(
                    text,
                    compact,
                    [source_offsets[i] for i in offsets],
                    allowed_types=frozenset({"IBAN"}),
                )
            )
    for security_view, source_offsets in _single_spaced_iban_views(text):
        mapped.extend(
            _map_security_view_entities(
                text,
                security_view,
                source_offsets,
                allowed_types=frozenset({"IBAN"}),
            )
        )

    deduplicated: list[Entity] = []
    seen: set[tuple[tuple[int, int], str]] = set()
    for entity in mapped:
        key = (entity.span, entity.data_type)
        if key not in seen:
            deduplicated.append(entity)
            seen.add(key)
    return deduplicated


def _obfuscated_structured_signals(
    text: str,
    trusted_ranges: list[tuple[int, int]],
) -> list[str]:
    found: set[str] = set()
    for entity in scan_obfuscated_structured_entities(text):
        source_start, source_end = entity.span
        if any(cs <= source_start and source_end <= ce for cs, ce in trusted_ranges):
            continue
        found.add(entity.data_type)
    return [f"{_OBFUSCATED_SIGNAL_PREFIX}{data_type}" for data_type in sorted(found)]


def scan_residual_signals(text: str, guard_context: _GuardContext) -> list[str]:
    """A second opinion over structural and obfuscated residuals.

    `scan_outbound_leaks` runs the same `detect_fp`/`detect_tb` that produced
    this text, so whatever detection missed on the way in is missed again on
    the way out: three layers on the architecture diagram, one layer in
    practice (correlated failure). The bare-number check depends on neither
    detector. A second, scan-only view removes embedded format controls and
    repeated whitespace, then applies structured validation without changing
    caller text or source spans.

    The strings are structural findings, not caller-facing warnings. The
    shared outbound policy turns any finding into a fail-closed decision.
    """
    trusted = guard_context.trusted_pseudonyms()
    ranges = pseudonym_ranges(text, sorted(trusted, key=len, reverse=True))
    signals: list[str] = []
    for m in _ORPHAN_DIGITS_RE.finditer(text):
        start, end = m.start(1), m.end(1)
        if any(cs <= start and end <= ce for cs, ce in ranges):
            continue  # part of a pseudonym we wrote
        signals.append(f"orphan_digits:{end - start}")
    signals.extend(_obfuscated_structured_signals(text, ranges))
    return signals


@native_broker_detector_phase
def scan_outbound_leaks(text: str, guard_context: _GuardContext) -> list[Entity]:
    """Return real leaks in pseudonymized text (empty list = safe to send)."""
    # Caller-seeded mappings are declarations, not proof. Only replacements
    # minted or actually reused by this processing turn may excuse any FP or TB
    # hit. A fuzzy TB span can cross a trusted replacement, so re-scan only its
    # uncovered segments and preserve cue-linked checks around the full span.
    trusted = guard_context.trusted_pseudonyms()
    trusted_ranges = pseudonym_ranges(text, sorted(trusted, key=len, reverse=True))
    real_leaks = []
    for entity in detect_fp(text) + detect_tb(text):
        if entity.original_text in trusted:
            continue
        start, end = entity.span
        overlapping = [
            (claimed_start, claimed_end)
            for claimed_start, claimed_end in trusted_ranges
            if claimed_start < end and claimed_end > start
        ]
        if overlapping:
            if any(
                claimed_start <= start and end <= claimed_end
                for claimed_start, claimed_end in overlapping
            ):
                continue
            if entity.redact_type == "TB":
                segments = []
                position = start
                for claimed_start, claimed_end in sorted(overlapping):
                    if claimed_start > position:
                        segments.append(text[position : min(claimed_start, end)])
                    position = max(position, claimed_end)
                if position < end:
                    segments.append(text[position:end])
                segments_clean = all(
                    not segment.strip() or (not detect_fp(segment) and not detect_tb(segment))
                    for segment in segments
                )
                if segments_clean and not _cue_leak_in_window(
                    text,
                    start,
                    end,
                    trusted_ranges,
                ):
                    continue
        real_leaks.append(entity)
    return real_leaks


def enforce_outbound_policy(
    text: str,
    *,
    guard_context: _GuardContext,
    scan_leaks: Callable[[str, _GuardContext], list[Entity]] = scan_outbound_leaks,
    scan_residual: Callable[[str, _GuardContext], list[str]] = scan_residual_signals,
) -> None:
    """Fail closed on structured, text, or detector-independent residuals.

    The exception retains only bounded type labels and fixed policy categories.
    It never retains Entity objects, scanner signals, or source text.
    """
    leak_types: set[str] = set()
    categories: set[str] = set()
    leaks = list(scan_leaks(text, guard_context))
    for leak in leaks:
        data_type = getattr(leak, "data_type", None)
        if isinstance(data_type, str):
            leak_types.add(data_type)
        categories.add("structured" if getattr(leak, "redact_type", None) == "FP" else "text")

    residual_signals = list(scan_residual(text, guard_context))
    if residual_signals:
        structured_types: set[str] = set()
        has_other_signal = False
        for signal in residual_signals:
            if not isinstance(signal, str) or not signal.startswith(_OBFUSCATED_SIGNAL_PREFIX):
                has_other_signal = True
                continue
            data_type = signal.removeprefix(_OBFUSCATED_SIGNAL_PREFIX)
            if data_type in _OBFUSCATED_STRUCTURED_TYPES:
                structured_types.add(data_type)
            else:
                has_other_signal = True
        leak_types.update(structured_types)
        if structured_types:
            categories.add("structured")
        if has_other_signal:
            leak_types.add("ORPHAN_DIGITS")
            categories.add("detector_independent")

    if leak_types or categories:
        safe_leak_types = normalize_outbound_leak_types(leak_types)
        safe_categories = _safe_policy_categories(categories)
        text = ""
        guard_context = None
        scan_leaks = None
        scan_residual = None
        leaks.clear()
        leaks = []
        leak = None
        data_type = None
        raise OutboundPolicyError(
            safe_leak_types,
            policy_categories=safe_categories,
        )

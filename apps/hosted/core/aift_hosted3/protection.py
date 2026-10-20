"""Deterministic Hosted 3.0 protection over the manifest-pinned sanitizer."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

TOKEN_NAMESPACE_ALPHABET = "abcdef"
TOKEN_NONCE_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
TOKEN_NAMESPACE_LENGTH = 25
TOKEN_NONCE_LENGTH = 20
PROTECTION_GENERATION_REVISION = "pg-v1"


@dataclass(slots=True)
class ProtectionResult:
    protected_text: str = field(repr=False)
    mapping: dict[str, str] = field(repr=False)
    entity_type_counts: dict[str, int]
    section26_categories: list[str]
    guard_findings: list[dict[str, str]]
    highlights: tuple[Any, ...]

    @property
    def detected_entity_count(self) -> int:
        return sum(self.entity_type_counts.values())


def _expand_alphabet(
    seed: bytes,
    *,
    domain: bytes,
    alphabet: str,
    length: int,
) -> str:
    """Domain-separated deterministic rejection sampling without modulo bias."""

    if not isinstance(seed, bytes) or len(seed) != 32:
        raise ValueError("pg-v1 seed must contain 32 bytes")
    if not isinstance(domain, bytes) or not domain:
        raise ValueError("pg-v1 domain is invalid")
    limit = 256 - (256 % len(alphabet))
    output: list[str] = []
    counter = 0
    while len(output) < length:
        block = hmac.new(
            seed,
            b"aiguard-pg-v1\0" + domain + counter.to_bytes(4, "big"),
            hashlib.sha256,
        ).digest()
        counter += 1
        for value in block:
            if value < limit:
                output.append(alphabet[value % len(alphabet)])
                if len(output) == length:
                    break
    return "".join(output)


def _token_seed_mapping(
    text: str,
    generation_seed: bytes,
    *,
    detect: Callable[[str], list[Any]],
    cleaner: Callable[[str], str],
    token_factory: Callable[..., str],
) -> dict[str, str]:
    """Build caller-held seeds matching the sanitizer's tail-first ordinals."""

    namespace = _expand_alphabet(
        generation_seed,
        domain=b"namespace",
        alphabet=TOKEN_NAMESPACE_ALPHABET,
        length=TOKEN_NAMESPACE_LENGTH,
    )
    detected = detect(cleaner(text))
    next_ordinal: dict[str, int] = {}
    by_identity: dict[tuple[str, str], str] = {}
    used: set[str] = set()
    for entity in sorted(detected, key=lambda item: item.span[0], reverse=True):
        identity = (entity.data_type, entity.original_text)
        if identity in by_identity:
            continue
        ordinal = next_ordinal.get(entity.data_type, 0) + 1
        next_ordinal[entity.data_type] = ordinal
        original_bytes = entity.original_text.encode("utf-8")
        for attempt in range(32):
            domain = b"\0".join(
                (
                    b"nonce",
                    entity.data_type.encode("ascii"),
                    ordinal.to_bytes(4, "big"),
                    attempt.to_bytes(2, "big"),
                    original_bytes,
                )
            )
            nonce = _expand_alphabet(
                generation_seed,
                domain=domain,
                alphabet=TOKEN_NONCE_ALPHABET,
                length=TOKEN_NONCE_LENGTH,
            )
            candidate = token_factory(
                entity.data_type,
                ordinal,
                namespace=namespace,
                nonce=nonce,
            )
            if candidate not in text and candidate not in used:
                by_identity[identity] = candidate
                used.add(candidate)
                break
        else:  # pragma: no cover - cryptographically implausible, fail closed
            raise ValueError("pg-v1 could not derive a unique token")
        original_bytes = b""
    return {token: original for (_data_type, original), token in by_identity.items()}


def _section26_categories(findings: object) -> list[str]:
    if not isinstance(findings, list):
        return []
    order = (
        "RACE_ETHNICITY",
        "POLITICAL_OPINION",
        "RELIGION",
        "HEALTH",
        "SEXUAL_BEHAVIOR",
        "CRIMINAL_RECORD",
        "DISABILITY",
        "LABOR_UNION",
    )
    observed = {
        finding.get("category")
        for finding in findings
        if isinstance(finding, dict)
    }
    return [category for category in order if category in observed]


def _guard_findings(
    text: str,
    *,
    scanner: Callable[[str], list[Any]],
) -> list[dict[str, str]]:
    allowed_categories = {
        "instruction_override",
        "role_hijack",
        "exfiltration",
        "hidden_chars",
        "suspicious_payload",
    }
    allowed_severities = {"low", "medium", "high"}
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for finding in scanner(text):
        pair = (getattr(finding, "category", None), getattr(finding, "severity", None))
        if pair[0] in allowed_categories and pair[1] in allowed_severities and pair not in seen:
            output.append({"category": str(pair[0]), "severity": str(pair[1])})
            seen.add(pair)
    return output


class ProtectionService:
    """Recreate exact protected bytes without retaining source or mappings."""

    def __init__(
        self,
        *,
        detect: Callable[[str], list[Any]] | None = None,
        cleaner: Callable[[str], str] | None = None,
        token_factory: Callable[..., str] | None = None,
        sanitizer: Callable[..., Any] | None = None,
        injection_scanner: Callable[[str], list[Any]] | None = None,
    ):
        if any(
            value is None
            for value in (detect, cleaner, token_factory, sanitizer, injection_scanner)
        ):
            from pii_redactor.anonymizer.token_generator import generate_token
            from pii_redactor.detectors.aggregate import detect_all
            from pii_redactor.guard.injection import scan_injection
            from pii_redactor.ingest.text_cleaner import clean_length_preserving
            from pii_redactor.stateless import sanitize_stateless

            detect = detect_all if detect is None else detect
            cleaner = clean_length_preserving if cleaner is None else cleaner
            token_factory = generate_token if token_factory is None else token_factory
            sanitizer = sanitize_stateless if sanitizer is None else sanitizer
            injection_scanner = scan_injection if injection_scanner is None else injection_scanner
        self._detect = detect
        self._cleaner = cleaner
        self._token_factory = token_factory
        self._sanitizer = sanitizer
        self._injection_scanner = injection_scanner

    def protect(
        self,
        text: str,
        *,
        mode: str,
        salt: str,
        generation_seed: bytes | None,
    ) -> ProtectionResult:
        if mode not in {"token", "surrogate"}:
            raise ValueError("protection mode is invalid")
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("protection text is invalid") from None
        seeded = None
        if mode == "token":
            if not isinstance(generation_seed, bytes) or len(generation_seed) != 32:
                raise ValueError("pg-v1 seed is invalid")
            seeded = _token_seed_mapping(
                text,
                generation_seed,
                detect=self._detect,
                cleaner=self._cleaner,
                token_factory=self._token_factory,
            )
        elif generation_seed is not None:
            raise ValueError("surrogate mode does not accept a pg-v1 seed")
        result = None
        try:
            result = self._sanitizer(
                text,
                mode=mode,
                salt=salt,
                prior_mapping=seeded,
                detection_text=self._cleaner(text),
            )
            return ProtectionResult(
                protected_text=result.sanitized_text,
                mapping=result.mapping,
                entity_type_counts=dict(result.entity_type_counts),
                section26_categories=_section26_categories(result.section26),
                guard_findings=_guard_findings(text, scanner=self._injection_scanner),
                highlights=tuple(result.replacement_highlights),
            )
        finally:
            if seeded is not None:
                seeded.clear()

    def protect_document(
        self,
        segments: tuple[str, ...],
        *,
        salt: str,
        generation_seed: bytes,
    ) -> ProtectionResult:
        """Protect immutable segments without allowing replacement across a boundary."""

        if (
            not isinstance(segments, tuple)
            or not 1 <= len(segments) <= 80
            or any(not isinstance(value, str) or not value for value in segments)
            or not isinstance(generation_seed, bytes)
            or len(generation_seed) != 32
        ):
            raise ValueError("document protection input is invalid")
        protected_parts: list[str] = []
        mapping: dict[str, str] = {}
        counts: dict[str, int] = {}
        section26: list[str] = []
        guard_findings: list[dict[str, str]] = []
        try:
            for index, segment in enumerate(segments, start=1):
                segment_seed = hmac.new(
                    generation_seed,
                    b"aiguard-pg-v1-document-segment\0" + index.to_bytes(2, "big"),
                    hashlib.sha256,
                ).digest()
                result = self.protect(
                    segment,
                    mode="token",
                    salt=salt,
                    generation_seed=segment_seed,
                )
                try:
                    for pseudonym, original in result.mapping.items():
                        if pseudonym in mapping:
                            raise ValueError("document token collision")
                        mapping[pseudonym] = original
                    protected_parts.append(result.protected_text)
                    for label, count in result.entity_type_counts.items():
                        counts[label] = counts.get(label, 0) + count
                    for label in result.section26_categories:
                        if label not in section26:
                            section26.append(label)
                    for finding in result.guard_findings:
                        if finding not in guard_findings:
                            guard_findings.append(finding)
                finally:
                    result.mapping.clear()
            protected_text = "\n\n".join(protected_parts)
            from pii_redactor.leak_guard import (
                OutboundGuardContext,
                OutboundPolicyError,
                enforce_outbound_policy,
            )
            from pii_redactor.stateless import StatelessLeakError

            try:
                enforce_outbound_policy(
                    protected_text,
                    guard_context=OutboundGuardContext(frozenset(mapping)),
                )
            except OutboundPolicyError as error:
                raise StatelessLeakError(
                    error.leak_types,
                    policy_categories=error.policy_categories,
                ) from None
            return ProtectionResult(
                protected_text=protected_text,
                mapping=mapping,
                entity_type_counts=counts,
                section26_categories=section26,
                guard_findings=guard_findings,
                highlights=(),
            )
        except Exception:
            mapping.clear()
            protected_parts.clear()
            counts.clear()
            section26.clear()
            guard_findings.clear()
            raise

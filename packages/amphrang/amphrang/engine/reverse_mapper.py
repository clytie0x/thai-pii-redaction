"""Reverse mapping for de-anonymization.

Restores original PII from pseudonymized AI response using the vault's reverse index.
"""

import re
from collections.abc import Iterable

from amphrang.engine.anonymizer.token_generator import token_namespace_from_candidate
from amphrang.engine.detectors.fp_detector import detect_fp
from amphrang.engine.models import AIResponse, EntityRegistry, ReverseResult
from amphrang.engine.session_vault import SessionVault


def _char_class(c: str) -> str | None:
    """Classify a char for the boundary guard: surrogate pseudonyms are bare values, so a raw
    substring match must not be glued to a same-class char. Bracket tokens (class None) are
    never boundary-rejected."""
    if c.isdigit():  # covers Thai (๐-๙) and ASCII digits
        return "digit"
    if "ก" <= c <= "๎":  # Thai letters / vowels / tone marks (digits handled above)
        return "thai"
    if c.isascii() and c.isalpha():
        return "latin"
    return None


def _boundary_ok(text: str, start: int, end: int, pseudonym: str) -> bool:
    """Reject a match embedded in a longer token. Digits/Latin reject glue on EITHER side;
    Thai has no word spaces ("ผมชื่อ<name>" is legitimate), so it rejects only when glued on
    BOTH sides."""
    lc = _char_class(pseudonym[0])
    rc = _char_class(pseudonym[-1])
    left_glue = start > 0 and lc is not None and _char_class(text[start - 1]) == lc
    right_glue = end < len(text) and rc is not None and _char_class(text[end]) == rc
    if (left_glue and lc in ("digit", "latin")) or (right_glue and rc in ("digit", "latin")):
        return False
    if left_glue and right_glue:
        return False
    return True


# Foreign-token detector: bracket-shaped tokens in the raw reply that we never sent.
# Alert-only: guessing their meaning could restore the wrong person.
_BRACKET_CANDIDATE = re.compile(r"\[([^\[\]\r\n]{1,128})\]")
# ASCII-only ordinal: str.isdigit() accepts Thai digits the generator never emits.
_TOKEN_ORDINAL = re.compile(r"[1-9][0-9]*")


def _is_token_shaped(inner: str) -> bool:
    label, sep, ordinal = inner.rpartition("_")
    if not sep or not label:
        return False
    return _TOKEN_ORDINAL.fullmatch(ordinal) is not None


def count_foreign_tokens(
    raw_text: str,
    sent_pseudonyms: Iterable[str],
    *,
    mode: str | None = None,
) -> int:
    """Count bracket tokens in `raw_text` that are not in the sent set.

    Namespaced tokens count in every mode (stale tokens must not fail open in a surrogate
    session); other token shapes only in token mode to avoid surrogate false positives.
    Returns a count, never the candidates: model output must not reach audit logs.
    """
    sent = {p for p in sent_pseudonyms if p}

    def _is_token(p: str) -> bool:
        m = _BRACKET_CANDIDATE.fullmatch(p)
        return bool(m) and _is_token_shaped(m.group(1))

    token_mode = mode == "token" or (mode is None and any(_is_token(p) for p in sent))
    count = 0
    for match in _BRACKET_CANDIDATE.finditer(raw_text):
        candidate = match.group(0)
        if candidate in sent:
            continue
        if token_namespace_from_candidate(candidate) is not None or (
            token_mode and _is_token_shaped(match.group(1))
        ):
            count += 1
    return count


def _pre_reverse_validate(ai_response: AIResponse, vault: SessionVault) -> None:
    """Raise VaultTimeoutError if vault is idle, ValueError if response is empty."""
    vault.check_idle()
    if not ai_response.text or not ai_response.text.strip():
        raise ValueError("Empty or blank AI response — cannot reverse map")


def _do_reverse(
    text: str,
    vault: SessionVault,
) -> tuple[str, list[str], tuple[tuple[int, int], ...]]:
    """Replace pseudonyms with originals. Returns (restored text, replaced pseudonyms, ranges).

    Claims occurrences on the UNTOUCHED text, longest pseudonym first, non-overlapping (same
    rule as leak_guard.pseudonym_ranges), then rebuilds positionally. A progressive
    str.replace would rewrite a pseudonym-looking substring inside an already-restored value.
    """
    pseudo_to_original: dict[str, str] = {}
    for pseudonym, entity_id in vault._reverse.items():
        record = vault.get_by_entity_id(entity_id)
        if record is not None:
            pseudo_to_original[pseudonym] = record.original

    claimed: list[tuple[int, int, str]] = []

    def _taken(start: int, end: int) -> bool:
        return any(start < ce and end > cs for cs, ce, _ in claimed)

    replaced: list[str] = []
    for pseudonym in sorted(pseudo_to_original, key=len, reverse=True):
        if not pseudonym:
            continue
        found = False
        pos = 0
        while (i := text.find(pseudonym, pos)) >= 0:
            j = i + len(pseudonym)
            if not _taken(i, j) and _boundary_ok(text, i, j, pseudonym):
                claimed.append((i, j, pseudonym))
                found = True
            pos = i + 1
        if found:
            replaced.append(pseudonym)

    parts: list[str] = []
    restored_ranges: list[tuple[int, int]] = []
    source_cursor = 0
    restored_cursor = 0
    for cs, ce, pseudonym in sorted(claimed, key=lambda item: item[0]):
        prefix = text[source_cursor:cs]
        parts.append(prefix)
        restored_cursor += len(prefix)
        original = pseudo_to_original[pseudonym]
        start = restored_cursor
        parts.append(original)
        restored_cursor += len(original)
        restored_ranges.append((start, restored_cursor))
        source_cursor = ce
    parts.append(text[source_cursor:])
    restored = "".join(parts)

    return restored, replaced, tuple(restored_ranges)


def _post_reverse_validate(
    restored_text: str,
    replaced: list[str],
    entity_registry: EntityRegistry,
    vault: SessionVault,
) -> tuple[list[str], dict]:
    """Residue, completeness and informational PII checks. Returns (flags, audit_summary)."""
    flags = []

    residue_count = sum(1 for pseudonym in vault._reverse if pseudonym in restored_text)
    if residue_count:
        flags.append(f"pseudonym_residue:{residue_count}")

    # Count DISTINCT pseudonyms, not entities: N mentions of one person share one pseudonym,
    # so counting entities false-flags every repeated value on a perfect restore.
    expected_pseudonyms: set[str] = set()
    for e in entity_registry.entities:
        rec = vault.get_by_entity_id(e.entity_id)
        if rec is not None:
            expected_pseudonyms.add(rec.pseudonym)
    total_entities = len(expected_pseudonyms)
    replaced_count = len(replaced)
    if replaced_count < total_entities:
        flags.append(f"incomplete_reverse:{replaced_count}/{total_entities}")

    # Informational only: PII is EXPECTED here since we just restored it.
    restored_pii = detect_fp(restored_text)

    audit_summary = {
        "total_entities": total_entities,
        "replaced_count": replaced_count,
        "residue_count": residue_count,
        "restored_pii_types": list({e.data_type for e in restored_pii}),
        "request_id": "unknown",
    }

    return flags, audit_summary


def reverse_map(
    ai_response: AIResponse,
    entity_registry: EntityRegistry,
    vault: SessionVault,
    *,
    mode: str | None = None,
) -> ReverseResult:
    """Restore original PII in the AI response. Returns ReverseResult (text, flags, audit).

    Raises ValueError on empty response, VaultTimeoutError if the vault is idle.
    """
    _pre_reverse_validate(ai_response, vault)

    # Scan the RAW reply: after restoration the sent tokens are gone and a restored original
    # may itself contain bracket-looking text.
    foreign_count = count_foreign_tokens(
        ai_response.text,
        vault._reverse.keys(),
        mode=mode,
    )

    restored_text, replaced, restored_ranges = _do_reverse(ai_response.text, vault)

    flags, audit_summary = _post_reverse_validate(restored_text, replaced, entity_registry, vault)
    audit_summary["request_id"] = ai_response.request_id
    if foreign_count:
        flags.append(f"foreign_tokens:{foreign_count}")
    audit_summary["foreign_token_count"] = foreign_count

    return ReverseResult(
        text=restored_text,
        restored_ranges=restored_ranges,
        flags=flags,
        audit_summary=audit_summary,
    )

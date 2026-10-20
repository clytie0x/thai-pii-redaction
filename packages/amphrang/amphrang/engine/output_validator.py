"""3-layer output validation to detect PII leaks and data integrity issues.

Security design:
- Layer 1: Detect unexpected PII (not in vault) → halt
- Layer 2: Check pseudonym residue and entity completeness → flag only
- Layer 3: Verify UTF-8 encoding and no abrupt truncation → halt
"""

from dataclasses import dataclass

from amphrang.engine.detectors.aggregate import detect_all
from amphrang.engine.leak_guard import scan_obfuscated_structured_entities
from amphrang.engine.models import EntityRegistry, ReverseResult
from amphrang.engine.session_vault import SessionVault


@dataclass
class ValidationResult:
    """Result of 3-layer output validation."""

    passed: bool  # True if all layers pass
    layer1_pii_clean: bool  # Layer 1: no unexpected PII found
    layer2_completeness_ok: bool  # Layer 2: pseudonym residue and entity counts ok
    layer3_integrity_ok: bool  # Layer 3: UTF-8 encodable, no abrupt truncation
    flags: list[str]  # All flags from all layers
    halt: bool  # True if Layer 3 failed (Layer 1 raises PIILeakError instead)


class PIILeakError(Exception):
    """Layer 1: Unexpected PII found in final output. Pipeline must halt immediately."""

    def __init__(self, *_discarded: object, count: int = 1):
        self.count = count if type(count) is int and count > 0 else 1
        super().__init__("Unexpected PII detected in output")


def _layer1_pii_scan(
    reverse_result: ReverseResult,
    vault: SessionVault,
) -> tuple[bool, list[str]]:
    """Return (pii_clean, flags). Detected PII is EXPECTED only when EVERY character of its span
    lies inside some range the reverse mapper restored; a matching vault value elsewhere does not
    count."""
    flags = []
    text = reverse_result.text

    vault.check_idle()

    known_originals: set[str] = set()
    for record in vault._table.values():
        known_originals.add(record.original)

    # Char coverage, not single-range containment. The ม.26 merge splits one CRF span into an
    # entity plus a sensitive span, so the restored text re-detects the original wide span
    # straddling TWO adjacent restored ranges. Each range is still validated individually
    # against known_originals and a span containing an unrestored character is still
    # rejected; the old single-range rule is the special case of one range.
    expected: set[int] = set()
    for item in reverse_result.restored_ranges:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and type(item[0]) is int
            and type(item[1]) is int
            and 0 <= item[0] < item[1] <= len(text)
            and text[item[0] : item[1]] in known_originals
        ):
            expected.update(range(item[0], item[1]))

    detected = detect_all(text)
    for candidate in scan_obfuscated_structured_entities(text):
        if any(
            existing.data_type == candidate.data_type
            and existing.span[0] <= candidate.span[0]
            and candidate.span[1] <= existing.span[1]
            for existing in detected
        ):
            continue
        detected.append(candidate)
    unexpected = [
        entity for entity in detected if not all(index in expected for index in range(*entity.span))
    ]

    if unexpected:
        flags.append(f"unexpected_pii_count:{len(unexpected)}")
        return False, flags

    return True, flags


def _layer2_completeness(
    reverse_result: ReverseResult,
    entity_registry: EntityRegistry,
    vault: SessionVault,
) -> tuple[bool, list[str]]:
    """Check pseudonym residue and entity completeness. Returns (ok, flags); never halts."""
    flags = []

    residue_flags = [f for f in reverse_result.flags if "pseudonym_residue" in f]
    if residue_flags:
        flags.extend(residue_flags)

    summary = reverse_result.audit_summary
    total = summary.get("total_entities", 0)
    replaced = summary.get("replaced_count", 0)
    if total > 0 and replaced < total:
        flags.append(f"incomplete_reverse:{replaced}/{total}")

    ok = len(flags) == 0
    return ok, flags


def _layer3_integrity(text: str) -> tuple[bool, list[str]]:
    """Check UTF-8 encodability and abrupt truncation. Returns (ok, flags)."""
    flags = []

    try:
        text.encode("utf-8")
    except UnicodeEncodeError as e:
        flags.append(f"encoding_error:{e}")
        return False, flags

    # Truncation heuristic is a blocklist of mid-cut endings (comma, hyphen, open bracket...).
    # Any letter/digit is a valid ending: Thai has no sentence-final punctuation and a trailing
    # phone number or proper noun is normal, so requiring punctuation halted real exports.
    if text and len(text) > 20:
        last = text[-1]
        is_valid_ending = (
            last.isalnum() or last.isspace() or last in ".!?ฯๆ…%" or last in ")]}»\"'”’"
        )
        if not is_valid_ending:
            flags.append("possible_truncation:no_terminal_punctuation")

    ok = len(flags) == 0
    return ok, flags


def validate_output(
    reverse_result: ReverseResult,
    entity_registry: EntityRegistry,
    vault: SessionVault,
) -> ValidationResult:
    """Run 3-layer validation. Layer 1 failure raises PIILeakError; Layer 2 flags only;
    Layer 3 sets halt=True without raising."""
    text = reverse_result.text
    all_flags = []

    l1_ok, l1_flags = _layer1_pii_scan(reverse_result, vault)
    all_flags.extend(l1_flags)

    if not l1_ok:
        unexpected_count = 0
        for flag in l1_flags:
            prefix = "unexpected_pii_count:"
            if flag.startswith(prefix):
                try:
                    unexpected_count += int(flag[len(prefix) :])
                except ValueError:
                    unexpected_count += 1
        raise PIILeakError(count=unexpected_count)

    l2_ok, l2_flags = _layer2_completeness(reverse_result, entity_registry, vault)
    all_flags.extend(l2_flags)

    l3_ok, l3_flags = _layer3_integrity(text)
    all_flags.extend(l3_flags)

    halt = not l3_ok
    passed = l1_ok and l2_ok and l3_ok

    return ValidationResult(
        passed=passed,
        layer1_pii_clean=l1_ok,
        layer2_completeness_ok=l2_ok,
        layer3_integrity_ok=l3_ok,
        flags=all_flags,
        halt=halt,
    )

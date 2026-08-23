"""Locate which files mention a data subject -- for a PDPA มาตรา 30 access request.

Locates only, never reproduces content. No subject identifier VALUE (nor a hash of one, which is
brute-forceable for a 13-digit id) reaches `to_json_dict()`, an exception message, or a dataclass
repr: every dataclass holds only type counts, basenames, grades, and flags, so nothing is there
to leak. Not a legal conclusion; unmatched files are counted but never listed.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from amphrang.engine.detectors.aggregate import detect_all
from amphrang.engine.environment import environment as _environment
from amphrang.engine.ingest.file_detector import detect_source_type
from amphrang.engine.ingest.text_cleaner import clean
from amphrang.engine.ingest.text_extractor import extract
from amphrang.engine.reid_risk import assess_reid_risk
from amphrang.engine.scan_common import canonical_value, discover_files, short_reason

DSAR_SCHEMA = "amphrang.dsar-locate/1"

# Subject-file line classification, in priority order: 13 digits -> THAI_ID, [A-Z]{2}\d{7} ->
# PASSPORT, contains "@" -> EMAIL, domestic/+66 phone shape -> PHONE, anything else -> NAME.
_PASSPORT_LINE_RE = re.compile(r"^[A-Z]{2}\d{7}$")
_PHONE_DOMESTIC_RE = re.compile(r"^0\d{8,9}$")
_PHONE_INTL_RE = re.compile(r"^\+66\d{8,9}$")

# Explicit "+66" marker (the plus sign, not bare "66") -- see the PHONE guard below.
_PLUS_66_MARKER_RE = re.compile(r"\+\s*66")

_METHOD_STATEMENT = (
    "A file matches the subject only on exact canonical equality between a detected "
    "entity's value and one of the identifiers supplied in the subject file -- same "
    "normalization breach.py uses (spaced/hyphenated Thai id forms, mixed-case "
    "emails, +66/domestic phone forms, and a name with its title stripped all "
    "collapse to one canonical value). Matching is value-based only: the detector's "
    "own type label for that entity is never consulted, only the canonical value of "
    "what it detected against the subject identifier's own canonical form -- a phone "
    "number the detector happens to label BANK_ACCOUNT in one document, or a name it "
    "labels ORGANIZATION in another, still matches, because the label is the "
    "detector's contextual guess, not a property of the value. One deliberate "
    "exception guards against a false match: a phone number's international-to-"
    "domestic fold (+66 -> 0) only applies when the detected text still carries "
    "an explicit +66 marker, so an unrelated bare digit run that merely starts "
    "with 66 (e.g. a bank account) is never folded into a false phone match. No "
    "fuzzy or partial matching is attempted."
)

_OCR_LIMITATION_NOTE = (
    "Exact-match-only means an OCR misread of a scanned page's identifier will not "
    "match the subject file even when a human reader would recognize it as the same "
    "value -- this is a known Track A limitation, not a claim that a document does "
    "not concern the subject."
)

_THIRD_PARTY_NOTE = (
    "third_party_possible is set on a matched file whose overall PII inventory "
    "contains a type or a count beyond what matched the subject's own identifiers -- "
    "that extra personal data may belong to someone else. It is a warning to review "
    "and redact before serving a copy, not a conclusion that a third party is present. "
    "This flag is heuristic: it also fires on the subject's own data under a type they "
    "did not list in the subject file, and on the detector's own false positives (e.g. "
    'a stray NAME hit on a label like "national id number"), so a true value here is '
    "not proof of a third party either -- review the file's own PII inventory before "
    "acting on it."
)

_NAME_WEAK_MATCH_NOTE = (
    "weak_only is set on a matched file whose ONLY matched identifier type is NAME. "
    "NAME is a weak identifier -- the same rule breach.py already applies when bounding "
    "its subjects_min/max estimate -- because spelling and OCR variants of a name "
    "inflate it and a common Thai name can belong to someone other than the requester. "
    "A weak_only match is evidence that a person with this name appears in the file, "
    "not proof that the requester does; it needs human confirmation before the file is "
    "treated as concerning the subject."
)

_SCOPE_NOTE = (
    "This tool locates matching files; it does not reproduce, copy, or excerpt their "
    "content, and it does not by itself constitute a completed response to the "
    "access request. Unmatched files are counted but never listed, and are out of "
    "scope for this request."
)


class NoSubjectIdentifiersError(ValueError):
    """The subject file was empty, or every line was blank."""


class NoFilesAssessedError(RuntimeError):
    """Nothing could be assessed -- no files found, or every one failed."""


@dataclass
class FailedFile:
    """One file that could not be processed. Never carries file content."""

    basename: str
    reason: str  # "<ExceptionClassName> <short message>"


@dataclass
class MatchedFile:
    """One file where the subject was found. Type names, counts, a grade, and flags only."""

    basename: str
    source_type: str  # "text" | "pdf_text" | "pdf_hybrid"
    matched_identifier_counts: dict[
        str, int
    ]  # identifier type -> occurrences that matched the subject
    type_counts: dict[str, int]  # this file's full PII inventory: data_type -> occurrences
    risk_grade: str
    human_review: bool
    third_party_possible: bool
    weak_only: bool  # True iff the ONLY matched identifier type is NAME (see _NAME_WEAK_MATCH_NOTE)


@dataclass
class DsarResult:
    """Corpus-level result of `locate_subject`. Both the CLI JSON and the PDF renderer build from
    `to_json_dict()`, so the two cannot drift. `subject_counts` holds identifier types, never
    values."""

    subject_counts: dict[str, int]  # identifier type -> count supplied
    files_total: int
    files_assessed: int
    files_failed: list[FailedFile]
    files_skipped: list[str]  # basenames dropped by the *.txt/*.pdf directory filter
    matched_files: list[MatchedFile]
    environment: dict[str, str]
    assessed_at: str

    def to_json_dict(self) -> dict:
        """JSON-serializable shape; no identifier value, document excerpt, or hash appears here."""
        return {
            "schema": DSAR_SCHEMA,
            "assessed_at": self.assessed_at,
            "subject": {"types": self.subject_counts},
            "files": {
                "total": self.files_total,
                "assessed": self.files_assessed,
                "matched": len(self.matched_files),
                "failed": [{"basename": f.basename, "reason": f.reason} for f in self.files_failed],
                "skipped": {
                    "count": len(self.files_skipped),
                    "basenames": list(self.files_skipped),
                },
            },
            "matched_files": [
                {
                    "basename": row.basename,
                    "source_type": row.source_type,
                    "matched_identifier_counts": row.matched_identifier_counts,
                    "type_counts": row.type_counts,
                    "risk_grade": row.risk_grade,
                    "human_review": row.human_review,
                    "third_party_possible": row.third_party_possible,
                    "weak_only": row.weak_only,
                }
                for row in self.matched_files
            ],
            "method": {
                "match": _METHOD_STATEMENT,
                "ocr_limitation": _OCR_LIMITATION_NOTE,
                "third_party": _THIRD_PARTY_NOTE,
                "name_weak_match": _NAME_WEAK_MATCH_NOTE,
                "scope": _SCOPE_NOTE,
            },
            "environment": self.environment,
        }


def _classify_subject_line(line: str) -> str | None:
    """Classify one subject-file line by shape; `None` only for a blank line (NAME is the
    catch-all)."""
    stripped = line.strip()
    if not stripped:
        return None

    compact = re.sub(r"[\s-]", "", stripped)
    if compact.isdigit() and len(compact) == 13:
        return "THAI_ID"
    if _PASSPORT_LINE_RE.fullmatch(stripped):
        return "PASSPORT"
    if "@" in stripped:
        return "EMAIL"
    if _PHONE_DOMESTIC_RE.fullmatch(compact) or _PHONE_INTL_RE.fullmatch(compact):
        return "PHONE"
    return "NAME"


def _read_subject_identifiers(subject_file: str | Path) -> list[tuple[str, str]]:
    """Read and classify every non-blank line of `subject_file` into (data_type, canonical_value)
    pairs; nothing read is logged or persisted.

    Raises NoSubjectIdentifiersError (message names the path, never a line) if no line classifies.
    """
    path = Path(subject_file)
    raw_lines = path.read_text(encoding="utf-8").splitlines()

    identifiers: list[tuple[str, str]] = []
    for line in raw_lines:
        data_type = _classify_subject_line(line)
        if data_type is None:
            continue
        identifiers.append((data_type, canonical_value(data_type, line.strip())))

    if not identifiers:
        raise NoSubjectIdentifiersError(
            f"Subject file has no identifiable line (expected one Thai national id, "
            f"passport, phone, email, or name per line): {path}"
        )
    return identifiers


def _entity_matches_any_subject_value(
    subject_type: str, subject_values: set[str], entity_text: str
) -> bool:
    """Whether `entity_text` (any detector label) is a spelling of one of the subject's
    `subject_type` identifiers, via `canonical_value`'s own normalization.

    PHONE guard: `canonical_value("PHONE", ...)` folds a bare "66..." digit run to domestic form,
    so an unrelated 10/11-digit bank account starting with 66 would false-match. The fold is
    therefore applied only when the raw text carries an explicit "+66" marker.
    """
    if subject_type == "PHONE":
        digits = re.sub(r"\D", "", entity_text)
        if digits in subject_values:
            return True
        if _PLUS_66_MARKER_RE.search(entity_text):
            return canonical_value("PHONE", entity_text) in subject_values
        return False
    return canonical_value(subject_type, entity_text) in subject_values


def locate_subject(
    paths: Sequence[str | Path],
    subject_file: str | Path,
    *,
    recursive: bool = False,
) -> DsarResult:
    """Locate which of `paths` mention the subject named in `subject_file` (one identifier per
    line, classified by shape). Matching is exact canonical-value equality, label-independent
    (see `_METHOD_STATEMENT`); a failed file is recorded by basename and the run continues.

    Raises NoSubjectIdentifiersError (no classifiable line) or NoFilesAssessedError (nothing
    could be assessed).
    """
    subject_identifiers = _read_subject_identifiers(subject_file)

    subject_counts: dict[str, int] = {}
    subject_lookup: dict[str, set[str]] = {}
    for data_type, value in subject_identifiers:
        subject_counts[data_type] = subject_counts.get(data_type, 0) + 1
        subject_lookup.setdefault(data_type, set()).add(value)

    files, skipped_names = discover_files(paths, recursive=recursive)
    files_total = len(files) + len(skipped_names)

    matched_files: list[MatchedFile] = []
    failed: list[FailedFile] = []

    for path in files:
        try:
            source_type = detect_source_type(path)
            raw_text, _bboxes, meta = extract(path, source_type)
            text = clean(raw_text).text
            entities = detect_all(text)
        except Exception as exc:
            failed.append(FailedFile(basename=path.name, reason=short_reason(exc, path)))
            continue

        type_counts: dict[str, int] = {}
        matched_identifier_counts: dict[str, int] = {}
        for entity in entities:
            type_counts[entity.data_type] = type_counts.get(entity.data_type, 0) + 1
            # Value-based, not label-based: the detector's data_type is a contextual guess, so
            # every subject type gets a turn at this entity's raw text (see _METHOD_STATEMENT).
            for subject_type, subject_values in subject_lookup.items():
                if _entity_matches_any_subject_value(
                    subject_type, subject_values, entity.original_text
                ):
                    matched_identifier_counts[subject_type] = (
                        matched_identifier_counts.get(subject_type, 0) + 1
                    )

        if not matched_identifier_counts:
            continue

        third_party_possible = sum(type_counts.values()) > sum(matched_identifier_counts.values())
        # True only when NAME is the ONLY matched type; any strong match on the file makes it False.
        weak_only = set(matched_identifier_counts) == {"NAME"}
        reid = assess_reid_risk(text)

        matched_files.append(
            MatchedFile(
                basename=path.name,
                source_type=source_type,
                matched_identifier_counts=dict(sorted(matched_identifier_counts.items())),
                type_counts=dict(sorted(type_counts.items())),
                risk_grade=reid.grade,
                human_review=bool(meta.get("human_review", False)),
                third_party_possible=third_party_possible,
                weak_only=weak_only,
            )
        )

    # files_assessed counts every file the pipeline ran on, matched or not (same as breach.py).
    files_assessed = files_total - len(skipped_names) - len(failed)
    if files_assessed == 0:
        raise NoFilesAssessedError(
            f"No files could be assessed: {files_total} discovered, "
            f"{len(skipped_names)} skipped, {len(failed)} failed"
        )

    return DsarResult(
        subject_counts=dict(sorted(subject_counts.items())),
        files_total=files_total,
        files_assessed=files_assessed,
        files_failed=failed,
        files_skipped=skipped_names,
        matched_files=matched_files,
        environment=_environment(),
        assessed_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )

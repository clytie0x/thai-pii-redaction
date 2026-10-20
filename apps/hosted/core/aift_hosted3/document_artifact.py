"""Strict source-anchored Protected Markdown validation and rendering."""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from .pdf_client import (
    EXTRACTION_REVISION,
    PARSER_REVISION,
    DocumentSegment,
)


MAX_PROVIDER_RESPONSE_BYTES = 32 * 1024
MAX_PROTECTED_CHARACTERS = 16_000
MAX_PROTECTED_UTF8_BYTES = 48 * 1024
MAX_SEGMENTS = 80
PROMPT_REVISION = "structure-protected-document-classifications-v1"

ROLE_HEADINGS_TH = {
    "identity": "ข้อมูลผู้สมัคร",
    "contact": "ข้อมูลติดต่อ",
    "profile": "ข้อมูลโดยสรุป",
    "experience": "ประสบการณ์ทำงาน",
    "education": "การศึกษา",
    "skills": "ทักษะ",
    "achievements": "ผลงาน",
    "other": "ข้อมูลเพิ่มเติม",
}
_SEGMENT_ID = re.compile(r"^seg_[0-9]{3}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_RECEIPT_ID = re.compile(r"^[A-Za-z0-9_-]{22}$")
_SCENARIO_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_TOKEN_CANDIDATE = re.compile(r"\[[^\[\]\r\n]{1,128}\]")
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#+\-.!|])")


class DocumentArtifactError(ValueError):
    """Fixed value-free failure for provider structure or output integrity."""

    def __init__(self, code: str = "document_structure_invalid"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ArtifactProvenance:
    hosted_version: str
    source_kind: str
    source_receipt_id: str = field(repr=False)
    parser_revision: str
    extraction_revision: str
    page_count: int
    omitted_visual_page_numbers: tuple[int, ...]
    scenario_id: str | None = None
    scenario_registry_revision: str | None = None


@dataclass(slots=True)
class ProtectedArtifact:
    protected_document_ast: dict[str, object]
    protected_markdown: str = field(repr=False)
    protected_plain_text: str = field(repr=False)
    semantic_html: str = field(repr=False)
    exact_segment_coverage: bool
    expected_token_integrity: bool
    structured_output_validated: bool

    def clear(self) -> None:
        self.protected_document_ast.clear()
        self.protected_markdown = ""
        self.protected_plain_text = ""
        self.semantic_html = ""


def render_protected_artifact(
    provider_body: bytes,
    *,
    segments: tuple[DocumentSegment, ...],
    provenance: ArtifactProvenance,
    outbound_guard: Callable[[str, set[str]], None] | None = None,
) -> ProtectedArtifact:
    """Validate a content-free provider AST and render only source segments."""

    source = _validated_segments(segments)
    metadata = _validated_provenance(provenance)
    value = _strict_provider_ast(provider_body, expected_ids=tuple(source))
    assigned = tuple(
        (row["segment_id"], row["role"]) for row in value["classifications"]
    )
    ordered = [
        (role, [segment_id for segment_id, assigned_role in assigned if assigned_role == role])
        for role in ROLE_HEADINGS_TH
        if any(assigned_role == role for _segment_id, assigned_role in assigned)
    ]

    reordered = [source[segment_id] for _role, ids in ordered for segment_id in ids]
    reconstructed = "\n\n".join(reordered)
    source_text = "\n\n".join(source.values())
    expected_tokens = _tokens(source_text)
    if Counter(_tokens(reconstructed)) != Counter(expected_tokens):
        raise DocumentArtifactError("document_integrity_failed")
    try:
        if outbound_guard is None:
            from pii_redactor.leak_guard import (
                OutboundGuardContext,
                OutboundPolicyError,
                enforce_outbound_policy,
            )

            try:
                enforce_outbound_policy(
                    reconstructed,
                    guard_context=OutboundGuardContext(frozenset(expected_tokens)),
                )
            except OutboundPolicyError:
                raise DocumentArtifactError("document_integrity_failed") from None
        else:
            outbound_guard(reconstructed, set(expected_tokens))
    except DocumentArtifactError:
        raise
    except Exception:
        raise DocumentArtifactError("document_integrity_failed") from None

    header = _provenance_lines(metadata)
    markdown_lines = [f"> {_escape_markdown(line)}" for line in header]
    markdown_lines.extend(("", "# เอกสารข้อความที่ป้องกันแล้ว"))
    plain_lines = list(header)
    plain_lines.extend(("", "เอกสารข้อความที่ป้องกันแล้ว"))
    html_sections: list[str] = []
    for role, ids in ordered:
        heading = ROLE_HEADINGS_TH[role]
        markdown_lines.extend(("", f"## {heading}"))
        plain_lines.extend(("", heading))
        paragraphs: list[str] = []
        for segment_id in ids:
            text = source[segment_id]
            markdown_lines.extend(("", _escape_markdown(text)))
            plain_lines.append(text)
            paragraphs.append(f"<p>{html.escape(text, quote=True)}</p>")
        html_sections.append(
            f'<section data-role="{role}"><h2>{html.escape(heading)}</h2>'
            + "".join(paragraphs)
            + "</section>"
        )
    semantic_html = (
        '<article lang="th" data-aiguard-artifact="protected-document">'
        '<aside aria-label="ที่มาและข้อจำกัด"><ul>'
        + "".join(f"<li>{html.escape(line, quote=True)}</li>" for line in header)
        + "</ul></aside><h1>เอกสารข้อความที่ป้องกันแล้ว</h1>"
        + "".join(html_sections)
        + "</article>"
    )
    canonical_ast = {
        "ordered_sections": [
            {"role": role, "segment_ids": list(ids)} for role, ids in ordered
        ]
    }
    return ProtectedArtifact(
        protected_document_ast=canonical_ast,
        protected_markdown="\n".join(markdown_lines) + "\n",
        protected_plain_text="\n".join(plain_lines) + "\n",
        semantic_html=semantic_html,
        exact_segment_coverage=True,
        expected_token_integrity=True,
        structured_output_validated=True,
    )


def _validated_segments(
    segments: tuple[DocumentSegment, ...],
) -> dict[str, str]:
    if not isinstance(segments, tuple) or not 1 <= len(segments) <= MAX_SEGMENTS:
        raise DocumentArtifactError("document_integrity_failed")
    output: dict[str, str] = {}
    for index, row in enumerate(segments, start=1):
        if (
            not isinstance(row, DocumentSegment)
            or row.segment_id != f"seg_{index:03d}"
            or _SEGMENT_ID.fullmatch(row.segment_id) is None
            or not isinstance(row.text, str)
            or not row.text
            or "\x00" in row.text
            or "\r" in row.text
            or "\n" in row.text
        ):
            raise DocumentArtifactError("document_integrity_failed")
        try:
            row.text.encode("utf-8")
        except UnicodeEncodeError:
            raise DocumentArtifactError("document_integrity_failed") from None
        output[row.segment_id] = row.text
    protected = "\n\n".join(output.values())
    if (
        len(protected) > MAX_PROTECTED_CHARACTERS
        or len(protected.encode("utf-8")) > MAX_PROTECTED_UTF8_BYTES
    ):
        raise DocumentArtifactError("document_integrity_failed")
    return output


def _validated_provenance(value: ArtifactProvenance) -> ArtifactProvenance:
    if (
        not isinstance(value, ArtifactProvenance)
        or _VERSION.fullmatch(value.hosted_version) is None
        or value.source_kind
        not in {"synthetic_document", "document_standard", "document_invite"}
        or _RECEIPT_ID.fullmatch(value.source_receipt_id) is None
        or value.parser_revision != PARSER_REVISION
        or value.extraction_revision != EXTRACTION_REVISION
        or type(value.page_count) is not int
        or not 1 <= value.page_count <= 10
        or value.omitted_visual_page_numbers
        != tuple(sorted(set(value.omitted_visual_page_numbers)))
        or any(
            type(page) is not int or not 1 <= page <= value.page_count
            for page in value.omitted_visual_page_numbers
        )
    ):
        raise DocumentArtifactError("document_integrity_failed")
    if value.source_kind == "synthetic_document":
        if (
            not isinstance(value.scenario_id, str)
            or _SCENARIO_ID.fullmatch(value.scenario_id) is None
            or not isinstance(value.scenario_registry_revision, str)
            or not value.scenario_registry_revision
            or not value.scenario_registry_revision.isascii()
        ):
            raise DocumentArtifactError("document_integrity_failed")
    elif value.scenario_id is not None or value.scenario_registry_revision is not None:
        raise DocumentArtifactError("document_integrity_failed")
    return value


def _strict_provider_ast(
    body: bytes,
    *,
    expected_ids: tuple[str, ...],
) -> dict[str, list[dict[str, str]]]:
    if (
        not isinstance(body, bytes)
        or not 1 <= len(body) <= MAX_PROVIDER_RESPONSE_BYTES
    ):
        raise DocumentArtifactError()
    duplicate = False

    def pairs(rows):
        nonlocal duplicate
        output = {}
        for key, value in rows:
            if key in output:
                duplicate = True
            output[key] = value
        return output

    try:
        value = json.loads(body, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DocumentArtifactError() from None
    if duplicate or not isinstance(value, dict) or set(value) != {"classifications"}:
        raise DocumentArtifactError()
    rows = value.get("classifications")
    if (
        not isinstance(rows, list)
        or len(rows) != len(expected_ids)
    ):
        raise DocumentArtifactError()
    for index, row in enumerate(rows):
        if (
            not isinstance(row, dict)
            or set(row) != {"segment_id", "role"}
            or row.get("segment_id") != expected_ids[index]
            or row.get("role") not in ROLE_HEADINGS_TH
        ):
            raise DocumentArtifactError()
    return value


def _tokens(value: str) -> list[str]:
    from pii_redactor.anonymizer.token_generator import token_data_type_from_candidate

    return [
        candidate
        for candidate in _TOKEN_CANDIDATE.findall(value)
        if token_data_type_from_candidate(candidate) is not None
    ]


def _provenance_lines(value: ArtifactProvenance) -> list[str]:
    lines = [
        f"AI Guard Hosted {value.hosted_version}",
        "Protected/pseudonymized, not anonymous.",
        "The source PDF is unchanged and not sanitized.",
        "PII was not restored.",
        "Selectable text layer only; OCR, images, diagrams, and visual layout were not read.",
        "Human review is required; undetected PII may remain.",
    ]
    pages = (
        ", ".join(str(page) for page in value.omitted_visual_page_numbers)
        if value.omitted_visual_page_numbers
        else "none"
    )
    lines.append(f"Pages with omitted visual content: {pages}.")
    if value.source_kind == "synthetic_document":
        lines.append(
            f"Synthetic scenario: {value.scenario_id} · registry: "
            f"{value.scenario_registry_revision}."
        )
    else:
        lines.append(
            f"Request-scoped source receipt: {value.source_receipt_id} · parser: "
            f"{value.parser_revision} · extraction: {value.extraction_revision}."
        )
    return lines


def _escape_markdown(value: str) -> str:
    return _MARKDOWN_SPECIAL.sub(r"\\\1", value)

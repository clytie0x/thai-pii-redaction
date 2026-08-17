"""Provider-free Hosted 3.0 PDF preview over the secretless parser."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from collections.abc import Awaitable, Callable

from .approval import ApprovalEngine, DocumentFacts
from .authority import AuthorityContext
from .document_artifact import MAX_PROTECTED_CHARACTERS, MAX_PROTECTED_UTF8_BYTES
from .document_provider import (
    MAX_PROVIDER_PROTECTED_CHARACTERS,
    MAX_PROVIDER_SEGMENTS,
    DocumentProviderRequestError,
    encode_document_provider_request,
)
from .pdf_client import DocumentSegment, PDFParserClient, PDFParserError, ParsedDocument
from .preview import PreviewError
from .protection import ProtectionResult, ProtectionService


DOCUMENT_INITIAL_REMAINING_SECONDS = 1_230
DOCUMENT_PREMINT_REMAINING_SECONDS = 1_200
QUEUE_ADMISSION_SECONDS = 900
DOCUMENT_MINIMUM_REVIEW_SECONDS = 300
MODE = "token"

SCENARIOS = {
    "hr-resume-pdf-structured-v1": {
        "title": "เรซูเม่ภาษาไทยสมมติ",
        "registry_revision": "synthetic-document-registry-v1",
        "source_pdf_sha256": "57ffcd9cddfe5abbe3b5b276ad93d22a549d386f01967344315a97cbafc51e6c",
    }
}
SCENARIO_REGISTRY_SHA256 = hashlib.sha256(
    json.dumps(
        SCENARIOS,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
).hexdigest()


class DocumentPreviewService:
    """Parse and protect documents without contacting the AI provider."""

    def __init__(
        self,
        approval: ApprovalEngine,
        *,
        parser: PDFParserClient | None = None,
        protector: ProtectionService | None = None,
        hosted_version: str,
        now: Callable[[], float] | None = None,
        random_bytes: Callable[[int], bytes] | None = None,
        blocked_exceptions: tuple[type[BaseException], ...] | None = None,
        uncertain_exceptions: tuple[type[BaseException], ...] | None = None,
    ):
        self._approval = approval
        self._parser = PDFParserClient() if parser is None else parser
        if protector is None:
            from pii_redactor.detectors.ner_failure import NERFailureError
            from pii_redactor.stateless import StatelessLeakError, StatelessProcessingError

            protector = ProtectionService()
            blocked_exceptions = (StatelessLeakError,)
            uncertain_exceptions = (NERFailureError, StatelessProcessingError)
        self._protector = protector
        self._blocked_exceptions = blocked_exceptions or ()
        self._uncertain_exceptions = uncertain_exceptions or ()
        self._hosted_version = hosted_version
        self._now = time.time if now is None else now
        self._random_bytes = secrets.token_bytes if random_bytes is None else random_bytes

    async def preview_scenario(
        self,
        request: object,
        *,
        authority: AuthorityContext,
    ) -> dict[str, object]:
        if type(request) is not dict or set(request) != {"scenario_id"}:
            raise PreviewError("request_schema_invalid", status=422)
        scenario_id = request.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id not in SCENARIOS:
            raise PreviewError("request_schema_invalid", status=422)
        self._require_initial_window(authority)
        try:
            parsed = await self._parser.parse_scenario(scenario_id)
        except PDFParserError as error:
            raise _translated_parser_error(error) from None
        expected = SCENARIOS[scenario_id]
        if (
            parsed.source_pdf_sha256 != expected["source_pdf_sha256"]
            or parsed.scenario
            != {
                "scenario_id": scenario_id,
                "title": expected["title"],
                "registry_revision": expected["registry_revision"],
            }
        ):
            parsed.clear()
            raise PreviewError("document_parser_unavailable", status=503)
        return self._preview_parsed(
            parsed,
            authority=authority,
            ticket_kind="synthetic_document_v1",
            source_kind="synthetic_document",
            scenario_id=scenario_id,
        )

    async def preview_upload(
        self,
        receive: Callable[[], Awaitable[dict]],
        *,
        body_bytes: int,
        authority: AuthorityContext,
    ) -> dict[str, object]:
        self._require_initial_window(authority)
        parser_source = "standard" if authority.scope == "public_guest" else "priority"
        try:
            parsed = await self._parser.parse_document(
                receive,
                body_bytes=body_bytes,
                source_kind=parser_source,
            )
        except PDFParserError as error:
            raise _translated_parser_error(error) from None
        ticket_kind = (
            "standard_document_v1"
            if authority.scope == "public_guest"
            else "invite_document_v1"
        )
        source_kind = (
            "document_standard"
            if authority.scope == "public_guest"
            else "document_invite"
        )
        return self._preview_parsed(
            parsed,
            authority=authority,
            ticket_kind=ticket_kind,
            source_kind=source_kind,
            scenario_id=None,
        )

    def _preview_parsed(
        self,
        parsed: ParsedDocument,
        *,
        authority: AuthorityContext,
        ticket_kind: str,
        source_kind: str,
        scenario_id: str | None,
    ) -> dict[str, object]:
        salt = self._fresh_bytes(16).hex()
        generation_seed = self._fresh_bytes(32)
        source_receipt_id = _b64url(self._fresh_bytes(16))
        protected: ProtectionResult | None = None
        try:
            if parsed.segment_count > MAX_PROVIDER_SEGMENTS:
                raise PreviewError("document_too_complex", status=422)
            try:
                protected = self._protector.protect_document(
                    tuple(row.text for row in parsed.segments),
                    salt=salt,
                    generation_seed=generation_seed,
                )
            except Exception as error:
                if isinstance(error, self._uncertain_exceptions):
                    return self._response(
                        parsed,
                        source_kind=source_kind,
                        scenario_id=scenario_id,
                        source_receipt_id=source_receipt_id,
                        status="uncertain",
                        residual_count=0,
                        protected=None,
                    )
                if not isinstance(error, self._blocked_exceptions):
                    raise
                residual_count = getattr(error, "policy_category_count", 0)
                if type(residual_count) is not int or residual_count < 1:
                    residual_count = 1
                return self._response(
                    parsed,
                    source_kind=source_kind,
                    scenario_id=scenario_id,
                    source_receipt_id=source_receipt_id,
                    status="blocked",
                    residual_count=residual_count,
                    protected=None,
                )

            if (
                len(protected.protected_text) > MAX_PROTECTED_CHARACTERS
                or len(protected.protected_text.encode("utf-8"))
                > MAX_PROTECTED_UTF8_BYTES
            ):
                raise PreviewError("document_too_complex", status=422)
            protected_parts = _protected_segments(parsed, protected.protected_text)
            if len(protected.protected_text) > MAX_PROVIDER_PROTECTED_CHARACTERS:
                raise PreviewError("document_too_complex", status=422)
            try:
                encode_document_provider_request(
                    tuple(
                        DocumentSegment(
                            page=source.page,
                            segment_id=source.segment_id,
                            text=value,
                        )
                        for source, value in zip(
                            parsed.segments,
                            protected_parts,
                            strict=True,
                        )
                    )
                )
            except DocumentProviderRequestError:
                raise PreviewError("document_too_complex", status=422) from None
            minted_at = int(self._now())
            if authority.expires_at_unix - minted_at < DOCUMENT_PREMINT_REMAINING_SECONDS:
                raise PreviewError("session_review_window", status=409)
            protected_sha256 = _sha256_text(protected.protected_text)
            scenario = SCENARIOS.get(scenario_id) if scenario_id is not None else None
            facts = DocumentFacts(
                source_pdf_sha256=parsed.source_pdf_sha256,
                parser_revision=parsed.parser_revision,
                extraction_revision=parsed.extraction_revision,
                segmentation_revision=parsed.segmentation_revision,
                page_count=parsed.page_count,
                character_count=parsed.character_count,
                segment_count=parsed.segment_count,
                omitted_visual_page_numbers=parsed.omitted_visual_page_numbers,
                source_receipt_id=source_receipt_id,
                segment_manifest_sha256=parsed.segment_manifest_sha256,
                scenario_id=scenario_id,
                scenario_registry_sha256=(
                    SCENARIO_REGISTRY_SHA256 if scenario is not None else None
                ),
            )
            ticket, ticket_expires = self._approval.mint_document(
                kind=ticket_kind,
                authority=authority,
                protected_sha256=protected_sha256,
                salt=salt,
                generation_seed=generation_seed,
                facts=facts,
            )
            queue_join_before = min(
                ticket_expires,
                authority.expires_at_unix - QUEUE_ADMISSION_SECONDS,
            )
            if queue_join_before - minted_at < DOCUMENT_MINIMUM_REVIEW_SECONDS:
                raise PreviewError("session_review_window", status=409)
            return self._response(
                parsed,
                source_kind=source_kind,
                scenario_id=scenario_id,
                source_receipt_id=source_receipt_id,
                status="no_residual_signal_detected",
                residual_count=0,
                protected=protected,
                protected_sha256=protected_sha256,
                ticket=ticket,
                ticket_expires=ticket_expires,
                queue_join_before=queue_join_before,
            )
        finally:
            salt = ""
            generation_seed = b""
            source_receipt_id = ""
            if protected is not None:
                protected.mapping.clear()
            parsed.clear()

    def _response(
        self,
        parsed: ParsedDocument,
        *,
        source_kind: str,
        scenario_id: str | None,
        source_receipt_id: str,
        status: str,
        residual_count: int,
        protected: ProtectionResult | None,
        protected_sha256: str | None = None,
        ticket: str | None = None,
        ticket_expires: int | None = None,
        queue_join_before: int | None = None,
    ) -> dict[str, object]:
        scenario = SCENARIOS.get(scenario_id) if scenario_id is not None else None
        can_execute = status == "no_residual_signal_detected"
        warnings = _warnings(status, parsed.omitted_visual_page_numbers)
        return {
            "source_kind": source_kind,
            "scenario": (
                {
                    "scenario_id": scenario_id,
                    "title": scenario["title"],
                    "registry_revision": scenario["registry_revision"],
                }
                if scenario is not None
                else None
            ),
            "hosted_version": self._hosted_version,
            "mode": MODE,
            "parser_revision": parsed.parser_revision,
            "extraction_revision": parsed.extraction_revision,
            "page_count": parsed.page_count,
            "character_count": parsed.character_count,
            "segment_count": parsed.segment_count,
            "omitted_visual_page_numbers": list(parsed.omitted_visual_page_numbers),
            "protected_text": protected.protected_text if protected is not None else "",
            "detected_entity_count": (
                protected.detected_entity_count if protected is not None else 0
            ),
            "entity_type_counts": (
                protected.entity_type_counts if protected is not None else {}
            ),
            "outbound_gate": {
                "status": status,
                "residual_count": residual_count,
                "human_review_required": True,
            },
            "warnings": warnings,
            "source_receipt_id": source_receipt_id,
            "protected_sha256": (
                protected_sha256
                if protected_sha256 is not None
                else hashlib.sha256(b"").hexdigest()
            ),
            "can_execute": can_execute,
            "ticket": ticket if can_execute else None,
            "ticket_expires_at_unix": ticket_expires if can_execute else None,
            "queue_join_before_unix": queue_join_before if can_execute else None,
        }

    def _require_initial_window(self, authority: AuthorityContext) -> None:
        if not isinstance(authority, AuthorityContext):
            raise PreviewError("authentication_required", status=401)
        if authority.expires_at_unix - int(self._now()) < DOCUMENT_INITIAL_REMAINING_SECONDS:
            raise PreviewError("session_review_window", status=409)

    def _fresh_bytes(self, size: int) -> bytes:
        value = self._random_bytes(size)
        if not isinstance(value, bytes) or len(value) != size:
            raise RuntimeError("document preview random source returned invalid bytes")
        return value


def _translated_parser_error(error: PDFParserError) -> PreviewError:
    status = 429 if error.code == "document_busy" else 503
    if error.code in {
        "document_unsupported",
        "pdf_text_layer_required",
        "pdf_visual_content_unsupported",
        "document_too_complex",
    }:
        status = 422
    return PreviewError(error.code, status=status)


def _protected_segments(parsed: ParsedDocument, protected_text: str) -> list[str]:
    parts = protected_text.split("\n\n")
    if (
        len(parts) != parsed.segment_count
        or any(not value or "\x00" in value for value in parts)
    ):
        raise PreviewError("internal_error", status=500)
    return parts


def _warnings(status: str, omitted_pages: tuple[int, ...]) -> list[str]:
    if status == "no_residual_signal_detected":
        outcome_warning = (
            "AI Guard replaced only detected PII; undetected PII may remain. "
            "Human review is required."
        )
    elif status == "blocked":
        outcome_warning = (
            "AI Guard blocked this preview and returned no usable protected result. "
            "Nothing was sent to Pathumma. Review the source and try again."
        )
    elif status == "uncertain":
        outcome_warning = (
            "AI Guard could not complete a reliable protected preview and returned "
            "no usable protected result. Nothing was sent to Pathumma. Retry or "
            "review the source."
        )
    else:
        raise ValueError("unsupported document preview status")
    warnings = [
        outcome_warning,
        "The source PDF is unchanged and is not a sanitized document.",
        "AI Guard used only selectable text; OCR and visual layout were not interpreted. Compare the result with the source PDF.",
    ]
    if omitted_pages:
        pages = ", ".join(str(value) for value in omitted_pages)
        warnings.append(
            "Images, diagrams, icons, or drawing elements were detected on page(s) "
            f"{pages} and were omitted from the text result."
        )
    return warnings


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

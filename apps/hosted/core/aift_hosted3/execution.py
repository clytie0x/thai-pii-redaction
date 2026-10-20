"""Queue-bound Hosted 3.0 provider execution services.

The browser-held queue capability is the continuation boundary.  This module
never accepts an approval ticket directly and never contacts a provider until
``ProviderQueue.begin_execute`` has atomically consumed the matching claim.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from .approval import ApprovalError, decode_generation_seed
from .authority import AuthorityContext
from .custom_provider import (
    MAX_CUSTOM_PROVIDER_OUTPUT_CODEPOINTS,
    MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES,
    CustomProviderCallError,
    complete_custom_provider,
)
from .document_artifact import (
    PROMPT_REVISION as DOCUMENT_PROMPT_REVISION,
    ArtifactProvenance,
    DocumentArtifactError,
    ProtectedArtifact,
    render_protected_artifact,
)
from .document_preview import SCENARIOS, SCENARIO_REGISTRY_SHA256
from .document_provider import (
    DOCUMENT_SYSTEM_PROMPT,
    MAX_PROVIDER_PROTECTED_CHARACTERS,
    MAX_PROVIDER_SEGMENTS,
    DocumentProviderCallError,
    DocumentProviderRequestError,
    complete_document_provider,
    encode_document_provider_request,
)
from .pdf_client import DocumentSegment, PDFParserClient, PDFParserError, ParsedDocument
from .preview import (
    DEFAULT_SYSTEM_PROMPT,
    MAX_CUSTOM_TEXT_CODEPOINTS,
    PROMPT_REVISION,
    default_bindings,
    document_bindings,
)
from .protection import PROTECTION_GENERATION_REVISION, ProtectionResult, ProtectionService
from .provider_queue import ProviderQueue, ProviderQueueError, QueueExecution


RECEIPT_VERSION = 1


class ExecuteError(RuntimeError):
    """A fixed value-free execute failure safe for HTTP translation."""

    def __init__(
        self,
        code: str = "internal_error",
        *,
        attempt_count: int = 0,
        queue_reason: str | None = None,
    ):
        self.code = code
        self.attempt_count = attempt_count if type(attempt_count) is int else 0
        self.queue_reason = queue_reason or _queue_reason(code)
        super().__init__(code)


@dataclass(slots=True, repr=False)
class _PreparedCustom:
    protected: ProtectionResult
    approval: dict[str, object] = field(repr=False)

    def clear(self) -> None:
        self.protected.mapping.clear()
        self.approval.clear()


@dataclass(slots=True, repr=False)
class _PreparedDocument:
    protected_text: str = field(repr=False)
    segments: tuple[DocumentSegment, ...] = field(repr=False)
    approval: dict[str, object] = field(repr=False)
    provenance: ArtifactProvenance
    scenario: dict[str, str] | None
    warnings: list[str]

    def clear(self) -> None:
        self.protected_text = ""
        self.segments = ()
        self.approval.clear()
        self.warnings.clear()


class ExecuteService:
    """Own the claim-to-provider-to-result lifecycle for Hosted 3.0."""

    def __init__(
        self,
        queue: ProviderQueue,
        *,
        hosted_version: str,
        parser: PDFParserClient | None = None,
        protector: ProtectionService | None = None,
        custom_provider_call: Callable[[str, str, Callable[[int], None]], tuple[str, float, int]]
        | None = None,
        document_provider_call: Callable[[str, str], str] | None = None,
        restore: Callable[..., object] | None = None,
        outbound_guard: Callable[[str, set[str]], None] | None = None,
        monotonic: Callable[[], float] | None = None,
        request_id: Callable[[], str] | None = None,
    ):
        if not isinstance(queue, ProviderQueue):
            raise ValueError("execute queue is invalid")
        if not isinstance(hosted_version, str) or not hosted_version:
            raise ValueError("hosted version is invalid")
        self._queue = queue
        self._hosted_version = hosted_version
        self._parser = PDFParserClient() if parser is None else parser
        self._protector = ProtectionService() if protector is None else protector
        self._custom_provider_call = (
            _default_custom_provider_call if custom_provider_call is None else custom_provider_call
        )
        self._document_provider_call = (
            _default_document_provider_call
            if document_provider_call is None
            else document_provider_call
        )
        self._restore = _default_restore if restore is None else restore
        self._outbound_guard = _default_outbound_guard if outbound_guard is None else outbound_guard
        self._monotonic = time.monotonic if monotonic is None else monotonic
        self._request_id = (lambda: str(uuid.uuid4())) if request_id is None else request_id

    def execute_custom(
        self,
        request: object,
        *,
        authority: AuthorityContext,
    ) -> dict[str, object]:
        text, queue_capability, claim_token = _custom_request(request)
        execution = self._queue.begin_execute(
            queue_capability,
            claim_token,
            authority=authority,
        )
        prepared: _PreparedCustom | None = None
        succeeded = False
        attempt_count = 0
        failure_reason = "internal_error"
        started = self._monotonic()
        try:
            prepared = self._prepare_custom(
                execution.approval,
                text,
                authority=authority,
            )

            def before_attempt(_attempt: int) -> None:
                try:
                    self._outbound_guard(
                        prepared.protected.protected_text,
                        set(prepared.protected.mapping),
                    )
                except Exception:
                    raise ExecuteError(
                        "residual_pii",
                        attempt_count=_attempt,
                    ) from None

            try:
                ai_text, _provider_latency, attempt_count = self._custom_provider_call(
                    DEFAULT_SYSTEM_PROMPT,
                    prepared.protected.protected_text,
                    before_attempt,
                )
            except ExecuteError:
                raise
            except Exception as error:
                raise _translated_custom_provider_error(error) from None
            if type(attempt_count) is not int or not 1 <= attempt_count <= 3:
                raise ExecuteError("provider_response_invalid")
            _validate_custom_provider_text(ai_text, attempt_count=attempt_count)
            try:
                restored = self._restore(
                    ai_text,
                    mapping=prepared.protected.mapping,
                    mode=str(prepared.approval["mode"]),
                )
            except Exception:
                raise ExecuteError("restore_failed", attempt_count=attempt_count) from None
            response = self._custom_response(
                prepared,
                ai_text=ai_text,
                restored=restored,
                attempt_count=attempt_count,
                duration_ms=_duration_ms(started, self._monotonic()),
            )
            succeeded = True
            return response
        except ExecuteError as error:
            attempt_count = max(attempt_count, error.attempt_count)
            failure_reason = error.queue_reason
            raise
        except ApprovalError:
            failure_reason = "approval_invalid"
            raise ExecuteError("approval_invalid", queue_reason=failure_reason) from None
        except Exception:
            failure_reason = "internal_error"
            raise ExecuteError() from None
        finally:
            text = ""
            try:
                self._queue.finish(
                    execution,
                    succeeded=succeeded,
                    attempt_count=attempt_count,
                    failure_reason=None if succeeded else failure_reason,
                )
            finally:
                if prepared is not None:
                    prepared.clear()
                execution.clear()

    async def execute_synthetic_document(
        self,
        request: object,
        *,
        authority: AuthorityContext,
    ) -> dict[str, object]:
        queue_capability, claim_token = _synthetic_request(request)
        execution = self._queue.begin_execute(
            queue_capability,
            claim_token,
            authority=authority,
        )
        parsed: ParsedDocument | None = None
        prepared: _PreparedDocument | None = None
        succeeded = False
        attempt_count = 0
        failure_reason = "internal_error"
        started = self._monotonic()
        try:
            approval = execution.approval
            scenario_id = approval.get("scenario_id")
            if not isinstance(scenario_id, str) or scenario_id not in SCENARIOS:
                raise ExecuteError("approval_invalid", queue_reason="approval_invalid")
            try:
                parsed = await self._parser.parse_scenario(scenario_id)
            except PDFParserError:
                raise ExecuteError(
                    "document_parser_unavailable",
                    queue_reason="document_parser_unavailable",
                ) from None
            prepared = self._prepare_synthetic(
                approval,
                parsed,
                authority=authority,
            )
            parsed = None
            response, attempt_count = self._complete_document(
                prepared,
                started=started,
            )
            succeeded = True
            return response
        except ExecuteError as error:
            attempt_count = max(attempt_count, error.attempt_count)
            failure_reason = error.queue_reason
            raise
        except ApprovalError:
            failure_reason = "approval_invalid"
            raise ExecuteError("approval_invalid", queue_reason=failure_reason) from None
        except Exception:
            failure_reason = "internal_error"
            raise ExecuteError() from None
        finally:
            if parsed is not None:
                parsed.clear()
            try:
                self._queue.finish(
                    execution,
                    succeeded=succeeded,
                    attempt_count=attempt_count,
                    failure_reason=None if succeeded else failure_reason,
                )
            finally:
                if prepared is not None:
                    prepared.clear()
                execution.clear()

    def execute_uploaded_document(
        self,
        request: object,
        *,
        authority: AuthorityContext,
    ) -> dict[str, object]:
        protected_text, queue_capability, claim_token = _document_request(request)
        execution = self._queue.begin_execute(
            queue_capability,
            claim_token,
            authority=authority,
        )
        prepared: _PreparedDocument | None = None
        succeeded = False
        attempt_count = 0
        failure_reason = "internal_error"
        started = self._monotonic()
        try:
            prepared = self._prepare_uploaded(
                execution.approval,
                protected_text,
                authority=authority,
            )
            response, attempt_count = self._complete_document(
                prepared,
                started=started,
            )
            succeeded = True
            return response
        except ExecuteError as error:
            attempt_count = max(attempt_count, error.attempt_count)
            failure_reason = error.queue_reason
            raise
        except ApprovalError:
            failure_reason = "approval_invalid"
            raise ExecuteError("approval_invalid", queue_reason=failure_reason) from None
        except Exception:
            failure_reason = "internal_error"
            raise ExecuteError() from None
        finally:
            protected_text = ""
            try:
                self._queue.finish(
                    execution,
                    succeeded=succeeded,
                    attempt_count=attempt_count,
                    failure_reason=None if succeeded else failure_reason,
                )
            finally:
                if prepared is not None:
                    prepared.clear()
                execution.clear()

    def _prepare_custom(
        self,
        approval: Mapping[str, object],
        text: str,
        *,
        authority: AuthorityContext,
    ) -> _PreparedCustom:
        expected = default_bindings()
        source_kind = "custom_standard" if authority.scope == "public_guest" else "custom_invite"
        checks = (
            approval.get("kind") == "custom_text_v1",
            approval.get("scope") == authority.scope,
            approval.get("session_nonce") == authority.session_nonce,
            approval.get("source_kind") == source_kind,
            approval.get("provider_id") == expected.provider_id,
            approval.get("provider_model") == expected.provider_model,
            approval.get("prompt_revision") == expected.prompt_revision,
            approval.get("detector_code_sha256") == expected.detector_code_sha256,
            approval.get("detector_model_sha256") == expected.detector_model_sha256,
            hmac.compare_digest(str(approval.get("source_sha256", "")), _sha256(text)),
        )
        if not all(checks):
            raise ApprovalError()
        mode = approval.get("mode")
        if mode not in {"token", "surrogate"}:
            raise ApprovalError()
        seed = (
            decode_generation_seed(approval.get("protection_generation_seed"))
            if mode == "token"
            else None
        )
        protected: ProtectionResult | None = None
        try:
            protected = self._protector.protect(
                text,
                mode=str(mode),
                salt=str(approval.get("salt", "")),
                generation_seed=seed,
            )
            if not hmac.compare_digest(
                str(approval.get("protected_sha256", "")),
                _sha256(protected.protected_text),
            ):
                raise ApprovalError()
            return _PreparedCustom(protected=protected, approval=dict(approval))
        except Exception as error:
            if protected is not None:
                protected.mapping.clear()
            from pii_redactor.leak_guard import OutboundPolicyError
            from pii_redactor.stateless import StatelessLeakError

            if isinstance(error, (OutboundPolicyError, StatelessLeakError)):
                raise ExecuteError("residual_pii") from None
            raise
        finally:
            seed = None

    def _prepare_synthetic(
        self,
        approval: Mapping[str, object],
        parsed: ParsedDocument,
        *,
        authority: AuthorityContext,
    ) -> _PreparedDocument:
        scenario_id = str(approval.get("scenario_id", ""))
        scenario = SCENARIOS.get(scenario_id)
        if scenario is None:
            raise ApprovalError()
        _validate_document_approval(
            approval,
            authority=authority,
            expected_kind="synthetic_document_v1",
            expected_source_kind="synthetic_document",
        )
        expected_scenario = {
            "scenario_id": scenario_id,
            "title": scenario["title"],
            "registry_revision": scenario["registry_revision"],
        }
        if (
            approval.get("scenario_registry_sha256") != SCENARIO_REGISTRY_SHA256
            or parsed.scenario != expected_scenario
            or parsed.source_pdf_sha256 != scenario["source_pdf_sha256"]
            or not _document_facts_match(approval, parsed)
        ):
            raise ApprovalError()
        seed = decode_generation_seed(approval.get("protection_generation_seed"))
        protected: ProtectionResult | None = None
        try:
            protected = self._protector.protect_document(
                tuple(row.text for row in parsed.segments),
                salt=str(approval.get("salt", "")),
                generation_seed=seed,
            )
            if not hmac.compare_digest(
                str(approval.get("protected_sha256", "")),
                _sha256(protected.protected_text),
            ):
                raise ApprovalError()
            parts = _split_protected_text(
                protected.protected_text,
                expected_count=parsed.segment_count,
            )
            segments = tuple(
                DocumentSegment(row.page, row.segment_id, value)
                for row, value in zip(parsed.segments, parts, strict=True)
            )
            return _PreparedDocument(
                protected_text=protected.protected_text,
                segments=segments,
                approval=dict(approval),
                provenance=_artifact_provenance(approval, self._hosted_version),
                scenario=expected_scenario,
                warnings=_document_warnings(parsed.omitted_visual_page_numbers),
            )
        except Exception as error:
            from pii_redactor.leak_guard import OutboundPolicyError
            from pii_redactor.stateless import StatelessLeakError

            if isinstance(error, (OutboundPolicyError, StatelessLeakError)):
                raise ExecuteError("residual_pii") from None
            raise
        finally:
            seed = b""
            if protected is not None:
                protected.mapping.clear()
            parsed.clear()

    def _prepare_uploaded(
        self,
        approval: Mapping[str, object],
        protected_text: str,
        *,
        authority: AuthorityContext,
    ) -> _PreparedDocument:
        expected_kind = (
            "standard_document_v1" if authority.scope == "public_guest" else "invite_document_v1"
        )
        expected_source_kind = (
            "document_standard" if authority.scope == "public_guest" else "document_invite"
        )
        _validate_document_approval(
            approval,
            authority=authority,
            expected_kind=expected_kind,
            expected_source_kind=expected_source_kind,
        )
        if not hmac.compare_digest(
            str(approval.get("protected_sha256", "")),
            _sha256(protected_text),
        ):
            raise ApprovalError()
        count = approval.get("segment_count")
        if type(count) is not int:
            raise ApprovalError()
        parts = _split_protected_text(protected_text, expected_count=count)
        segments = tuple(
            DocumentSegment(1, f"seg_{index:03d}", value)
            for index, value in enumerate(parts, start=1)
        )
        return _PreparedDocument(
            protected_text=protected_text,
            segments=segments,
            approval=dict(approval),
            provenance=_artifact_provenance(approval, self._hosted_version),
            scenario=None,
            warnings=_document_warnings(
                tuple(int(value) for value in approval["omitted_visual_page_numbers"])
            ),
        )

    def _complete_document(
        self,
        prepared: _PreparedDocument,
        *,
        started: float,
    ) -> tuple[dict[str, object], int]:
        attempt_count = 0
        provider_body = ""
        artifact: ProtectedArtifact | None = None
        try:
            try:
                self._outbound_guard(
                    prepared.protected_text,
                    _document_tokens(prepared.protected_text),
                )
            except Exception:
                raise ExecuteError(
                    "residual_pii",
                    attempt_count=attempt_count,
                ) from None
            user = encode_document_provider_request(prepared.segments)
            attempt_count = 1
            try:
                provider_body = self._document_provider_call(
                    DOCUMENT_SYSTEM_PROMPT,
                    user,
                )
            except DocumentProviderCallError as error:
                raise ExecuteError(
                    error.code,
                    attempt_count=(0 if error.code == "provider_configuration" else 1),
                ) from None
            except Exception:
                raise ExecuteError("provider_unavailable", attempt_count=1) from None
            try:
                provider_bytes = provider_body.encode("utf-8")
            except (AttributeError, UnicodeEncodeError):
                raise ExecuteError("provider_response_invalid", attempt_count=1) from None
            try:
                artifact = render_protected_artifact(
                    provider_bytes,
                    segments=prepared.segments,
                    provenance=prepared.provenance,
                    outbound_guard=self._outbound_guard,
                )
            except DocumentArtifactError as error:
                raise ExecuteError(error.code, attempt_count=1) from None
            response = self._document_response(
                prepared,
                artifact=artifact,
                attempt_count=1,
                duration_ms=_duration_ms(started, self._monotonic()),
            )
            return response, 1
        except DocumentProviderRequestError:
            raise ExecuteError("document_integrity_failed", attempt_count=attempt_count) from None
        except ExecuteError:
            raise
        except Exception:
            raise ExecuteError("internal_error", attempt_count=attempt_count) from None
        finally:
            provider_body = ""
            if artifact is not None:
                artifact.clear()

    def _custom_response(
        self,
        prepared: _PreparedCustom,
        *,
        ai_text: str,
        restored: object,
        attempt_count: int,
        duration_ms: int,
    ) -> dict[str, object]:
        request_id = self._request_id()
        warnings = _restore_warnings(restored)
        leftovers = getattr(restored, "leftover_pseudonyms", [])
        leftover_count = len(leftovers) if isinstance(leftovers, list) else 0
        full_text = str(getattr(restored, "restored_text", ""))

        # A detected span in provider prose is a precision question about that
        # one span. Every other warning says the mapping itself did not land,
        # and no part of such a reply is trustworthy enough to show.
        blocking = [w for w in warnings if w.get("code") != "generated_pii"]
        generated = [w for w in warnings if w.get("code") == "generated_pii"]
        masked_spans: tuple[tuple[int, int], ...] = ()
        if generated and not blocking and not leftover_count:
            masked_spans = _generated_pii_spans(restored, len(full_text))

        if blocking:
            restoration_status = "unsafe"
        elif leftover_count:
            restoration_status = "incomplete"
        elif generated:
            # Without usable offsets the distrusted text cannot be located, so
            # withholding the whole reply stays the only safe answer.
            restoration_status = "sanitized" if masked_spans else "unsafe"
        else:
            restoration_status = "complete"

        restoration = {
            "status": restoration_status,
            "replaced_count": int(getattr(restored, "replaced_count", 0)),
            "leftover_count": leftover_count,
            "masked_count": len(masked_spans),
        }
        if restoration_status == "complete":
            restored_text = full_text
        elif restoration_status == "sanitized":
            restored_text = _mask_spans(full_text, masked_spans)
        else:
            restored_text = ""
        approval = prepared.approval
        receipt = {
            "receipt_version": RECEIPT_VERSION,
            "request_id": request_id,
            "hosted_version": self._hosted_version,
            "source_kind": approval["source_kind"],
            "scenario_id": None,
            "scenario_registry_revision": None,
            "mode": approval["mode"],
            "provider_id": approval["provider_id"],
            "provider_model": approval["provider_model"],
            "prompt_revision": approval["prompt_revision"],
            "detector_code_sha256": approval["detector_code_sha256"],
            "detector_model_sha256": approval["detector_model_sha256"],
            "protected_sha256": approval["protected_sha256"],
            "digest_match": True,
            "outbound_gate_status": "no_residual_signal_detected",
            "provider_attempt_count": attempt_count,
            "duration_ms": duration_ms,
            "restoration_status": restoration_status,
            "synthetic_provenance": None,
        }
        return {
            "request_id": request_id,
            "hosted_version": self._hosted_version,
            "source_kind": approval["source_kind"],
            "scenario": None,
            "synthetic_provenance": None,
            "protected_text": prepared.protected.protected_text,
            "ai_response_masked": ai_text,
            "restored_text": restored_text,
            "mode": approval["mode"],
            "detected_entity_count": prepared.protected.detected_entity_count,
            "entity_type_counts": prepared.protected.entity_type_counts,
            "section26_categories": prepared.protected.section26_categories,
            "guard_findings": prepared.protected.guard_findings,
            "warnings": warnings,
            "safety": {"status": "pass", "residual_count": 0},
            "restoration": restoration,
            "provider": {
                "id": approval["provider_id"],
                "model": approval["provider_model"],
                "attempt_count": attempt_count,
            },
            "receipt": receipt,
        }

    def _document_response(
        self,
        prepared: _PreparedDocument,
        *,
        artifact: ProtectedArtifact,
        attempt_count: int,
        duration_ms: int,
    ) -> dict[str, object]:
        request_id = self._request_id()
        approval = prepared.approval
        provenance = _provenance_payload(prepared.provenance)
        receipt = {
            "receipt_version": RECEIPT_VERSION,
            "request_id": request_id,
            "hosted_version": self._hosted_version,
            "source_kind": approval["source_kind"],
            "scenario_id": prepared.provenance.scenario_id,
            "scenario_registry_revision": prepared.provenance.scenario_registry_revision,
            "source_receipt_id": approval["source_receipt_id"],
            "parser_revision": approval["parser_revision"],
            "extraction_revision": approval["extraction_revision"],
            "segmentation_revision": approval["segmentation_revision"],
            "protection_generation_revision": approval["protection_generation_revision"],
            "provider_id": approval["provider_id"],
            "provider_model": approval["provider_model"],
            "prompt_revision": approval["prompt_revision"],
            "protected_sha256": approval["protected_sha256"],
            "digest_match": True,
            "outbound_gate_status": "no_residual_signal_detected",
            "exact_segment_coverage": artifact.exact_segment_coverage,
            "expected_token_integrity": artifact.expected_token_integrity,
            "structured_output_validated": artifact.structured_output_validated,
            "provider_attempt_count": attempt_count,
            "duration_ms": duration_ms,
            "omitted_visual_page_numbers": list(prepared.provenance.omitted_visual_page_numbers),
            "warnings": list(prepared.warnings),
            "artifact_provenance": provenance,
        }
        return {
            "request_id": request_id,
            "hosted_version": self._hosted_version,
            "source_kind": approval["source_kind"],
            "scenario": prepared.scenario,
            "artifact_provenance": provenance,
            "protected_text": prepared.protected_text,
            "source_receipt_id": approval["source_receipt_id"],
            "protected_document_ast": {
                "ordered_sections": [
                    {
                        "role": row["role"],
                        "segment_ids": list(row["segment_ids"]),
                    }
                    for row in artifact.protected_document_ast["ordered_sections"]
                ]
            },
            "protected_markdown": artifact.protected_markdown,
            "protected_plain_text": artifact.protected_plain_text,
            "omitted_visual_page_numbers": list(prepared.provenance.omitted_visual_page_numbers),
            "warnings": list(prepared.warnings),
            "provider": {
                "id": approval["provider_id"],
                "model": approval["provider_model"],
                "attempt_count": attempt_count,
            },
            "receipt": receipt,
        }


def _custom_request(request: object) -> tuple[str, str, str]:
    if type(request) is not dict or set(request) != {
        "text",
        "queue_capability",
        "claim_token",
    }:
        raise ExecuteError("request_schema_invalid")
    text = request.get("text")
    capability = request.get("queue_capability")
    claim = request.get("claim_token")
    if (
        not isinstance(text, str)
        or not 1 <= len(text) <= MAX_CUSTOM_TEXT_CODEPOINTS
        or not isinstance(capability, str)
        or not capability
        or not isinstance(claim, str)
        or not claim
    ):
        raise ExecuteError("request_schema_invalid")
    return text, capability, claim


def _synthetic_request(request: object) -> tuple[str, str]:
    if type(request) is not dict or set(request) != {
        "queue_capability",
        "claim_token",
    }:
        raise ExecuteError("request_schema_invalid")
    capability = request.get("queue_capability")
    claim = request.get("claim_token")
    if not isinstance(capability, str) or not capability or not isinstance(claim, str) or not claim:
        raise ExecuteError("request_schema_invalid")
    return capability, claim


def _document_request(request: object) -> tuple[str, str, str]:
    if type(request) is not dict or set(request) != {
        "protected_text",
        "queue_capability",
        "claim_token",
    }:
        raise ExecuteError("request_schema_invalid")
    text = request.get("protected_text")
    capability = request.get("queue_capability")
    claim = request.get("claim_token")
    if (
        not isinstance(text, str)
        or not text
        or not isinstance(capability, str)
        or not capability
        or not isinstance(claim, str)
        or not claim
    ):
        raise ExecuteError("request_schema_invalid")
    return text, capability, claim


def _validate_document_approval(
    approval: Mapping[str, object],
    *,
    authority: AuthorityContext,
    expected_kind: str,
    expected_source_kind: str,
) -> None:
    bindings = document_bindings()
    checks = (
        approval.get("kind") == expected_kind,
        approval.get("scope") == authority.scope,
        approval.get("session_nonce") == authority.session_nonce,
        approval.get("source_kind") == expected_source_kind,
        approval.get("mode") == "token",
        approval.get("provider_id") == bindings.provider_id,
        approval.get("provider_model") == bindings.provider_model,
        approval.get("prompt_revision") == DOCUMENT_PROMPT_REVISION,
        approval.get("prompt_revision") == bindings.prompt_revision,
        approval.get("detector_code_sha256") == bindings.detector_code_sha256,
        approval.get("detector_model_sha256") == bindings.detector_model_sha256,
        approval.get("protection_generation_revision") == PROTECTION_GENERATION_REVISION,
    )
    if not all(checks):
        raise ApprovalError()


def _document_facts_match(
    approval: Mapping[str, object],
    parsed: ParsedDocument,
) -> bool:
    return all(
        (
            approval.get("source_pdf_sha256") == parsed.source_pdf_sha256,
            approval.get("parser_revision") == parsed.parser_revision,
            approval.get("extraction_revision") == parsed.extraction_revision,
            approval.get("segmentation_revision") == parsed.segmentation_revision,
            approval.get("page_count") == parsed.page_count,
            approval.get("character_count") == parsed.character_count,
            approval.get("segment_count") == parsed.segment_count,
            approval.get("omitted_visual_page_numbers") == list(parsed.omitted_visual_page_numbers),
            approval.get("segment_manifest_sha256") == parsed.segment_manifest_sha256,
        )
    )


def _artifact_provenance(
    approval: Mapping[str, object],
    hosted_version: str,
) -> ArtifactProvenance:
    source_kind = str(approval["source_kind"])
    scenario_id = approval.get("scenario_id")
    scenario = SCENARIOS.get(str(scenario_id)) if scenario_id is not None else None
    return ArtifactProvenance(
        hosted_version=hosted_version,
        source_kind=source_kind,
        source_receipt_id=str(approval["source_receipt_id"]),
        parser_revision=str(approval["parser_revision"]),
        extraction_revision=str(approval["extraction_revision"]),
        page_count=int(approval["page_count"]),
        omitted_visual_page_numbers=tuple(
            int(value) for value in approval["omitted_visual_page_numbers"]
        ),
        scenario_id=str(scenario_id) if scenario_id is not None else None,
        scenario_registry_revision=(
            str(scenario["registry_revision"]) if scenario is not None else None
        ),
    )


def _provenance_payload(value: ArtifactProvenance) -> dict[str, object]:
    return {
        "hosted_version": value.hosted_version,
        "source_kind": value.source_kind,
        "source_receipt_id": value.source_receipt_id,
        "parser_revision": value.parser_revision,
        "extraction_revision": value.extraction_revision,
        "page_count": value.page_count,
        "omitted_visual_page_numbers": list(value.omitted_visual_page_numbers),
        "scenario_id": value.scenario_id,
        "scenario_registry_revision": value.scenario_registry_revision,
    }


def _split_protected_text(value: str, *, expected_count: int) -> tuple[str, ...]:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= MAX_PROVIDER_PROTECTED_CHARACTERS
        or len(value.encode("utf-8")) > 48 * 1024
        or type(expected_count) is not int
        or not 1 <= expected_count <= MAX_PROVIDER_SEGMENTS
    ):
        raise ApprovalError()
    parts = tuple(value.split("\n\n"))
    if len(parts) != expected_count or any(
        not part or "\x00" in part or "\r" in part or "\n" in part for part in parts
    ):
        raise ApprovalError()
    return parts


def _document_warnings(omitted_pages: tuple[int, ...]) -> list[str]:
    warnings = [
        "AI Guard replaced only detected PII; undetected PII may remain. Human review is required.",
        "The source PDF is unchanged and is not a sanitized document.",
        "AI Guard used only selectable text; OCR and visual layout were not interpreted. Compare the result with the source PDF.",
        "PII was not restored in this protected document artifact.",
    ]
    if omitted_pages:
        pages = ", ".join(str(value) for value in omitted_pages)
        warnings.append(
            "Images, diagrams, icons, or drawing elements were detected on page(s) "
            f"{pages} and were omitted from the text result."
        )
    return warnings


def _document_tokens(value: str) -> set[str]:
    from pii_redactor.anonymizer.token_generator import token_data_type_from_candidate
    import re

    candidates = re.findall(r"\[[^\[\]\r\n]{1,128}\]", value)
    return {
        candidate
        for candidate in candidates
        if token_data_type_from_candidate(candidate) is not None
    }


def _default_outbound_guard(text: str, trusted_tokens: set[str]) -> None:
    from pii_redactor.leak_guard import OutboundGuardContext, enforce_outbound_policy

    enforce_outbound_policy(
        text,
        guard_context=OutboundGuardContext(frozenset(trusted_tokens)),
    )


def _default_custom_provider_call(
    system: str,
    user: str,
    before_attempt: Callable[[int], None],
) -> tuple[str, float, int]:
    try:
        return complete_custom_provider(
            system,
            user,
            before_attempt,
        )
    except CustomProviderCallError as error:
        raise ExecuteError(error.code, attempt_count=error.attempts) from None


def _default_document_provider_call(system: str, user: str) -> str:
    return complete_document_provider(system, user)


def _default_restore(text: str, *, mapping: dict[str, str], mode: str):
    from pii_redactor.stateless import restore_stateless

    return restore_stateless(text, mapping=mapping, mode=mode)


def _translated_custom_provider_error(error: Exception) -> ExecuteError:
    if isinstance(error, ExecuteError):
        return error
    category = getattr(error, "category", "failed")
    status = getattr(error, "status_code", None)
    attempts = getattr(error, "attempts", 0)
    return ExecuteError(
        _provider_code(
            category if isinstance(category, str) else "failed",
            status if type(status) is int else None,
        ),
        attempt_count=attempts if type(attempts) is int else 0,
    )


def _provider_code(category: str, status_code: int | None) -> str:
    if category in {"malformed", "non_text"}:
        return "provider_response_invalid"
    if category == "http_status" and status_code is not None:
        if status_code == 429 or status_code >= 500:
            return "provider_unavailable"
        return "provider_rejected"
    return "provider_unavailable"


def _validate_custom_provider_text(value: object, *, attempt_count: int) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_CUSTOM_PROVIDER_OUTPUT_CODEPOINTS
    ):
        raise ExecuteError(
            "provider_response_invalid",
            attempt_count=attempt_count,
        )
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise ExecuteError(
            "provider_response_invalid",
            attempt_count=attempt_count,
        ) from None
    if len(encoded) > MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES:
        raise ExecuteError(
            "provider_response_invalid",
            attempt_count=attempt_count,
        )


def _restore_warnings(value: object) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    generated = getattr(value, "generated_pii_count", 0)
    foreign = getattr(value, "foreign_replacement_count", 0)
    if type(generated) is int and generated > 0:
        output.append({"code": "generated_pii", "count": generated})
    if type(foreign) is int and foreign > 0:
        output.append({"code": "foreign_replacement", "count": foreign})
    return output


# Value-free and type-free. The detector's type guess on text the model wrote is
# frequently wrong, so naming a type here would assert something the pipeline
# does not actually know.
GENERATED_PII_MARKER = "[ปกปิดโดยระบบ]"


def _generated_pii_spans(value: object, text_length: int) -> tuple[tuple[int, int], ...]:
    """Normalize reported offsets into sorted, merged, in-bounds ranges."""
    raw = getattr(value, "generated_pii_spans", ())
    if not isinstance(raw, (tuple, list)):
        return ()
    clean: list[tuple[int, int]] = []
    for item in raw:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and type(item[0]) is int
            and type(item[1]) is int
            and 0 <= item[0] < item[1] <= text_length
        ):
            clean.append((item[0], item[1]))
    if not clean:
        return ()
    clean.sort()
    merged: list[tuple[int, int]] = [clean[0]]
    for start, end in clean[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return tuple(merged)


def _mask_spans(text: str, spans: tuple[tuple[int, int], ...]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(text[cursor:start])
        parts.append(GENERATED_PII_MARKER)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


# Value-free and type-free. The detector's type guess on text the model wrote is
# frequently wrong, so naming a type here would assert something the pipeline
# does not know.
GENERATED_PII_MARKER = "[ปกปิดโดยระบบ]"


def _generated_pii_spans(value: object, text_length: int) -> tuple[tuple[int, int], ...]:
    """Normalize reported offsets into sorted, merged, in-bounds ranges."""
    raw = getattr(value, "generated_pii_spans", ())
    if not isinstance(raw, (tuple, list)):
        return ()
    clean: list[tuple[int, int]] = []
    for item in raw:
        if (
            isinstance(item, tuple)
            and len(item) == 2
            and type(item[0]) is int
            and type(item[1]) is int
            and 0 <= item[0] < item[1] <= text_length
        ):
            clean.append((item[0], item[1]))
    if not clean:
        return ()
    clean.sort()
    merged: list[tuple[int, int]] = [clean[0]]
    for start, end in clean[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return tuple(merged)


def _mask_spans(text: str, spans: tuple[tuple[int, int], ...]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(text[cursor:start])
        parts.append(GENERATED_PII_MARKER)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _duration_ms(started: float, finished: float) -> int:
    return max(0, int(round((finished - started) * 1000)))


def _sha256(value: str) -> str:
    try:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    except (AttributeError, UnicodeEncodeError):
        raise ApprovalError() from None


def _queue_reason(code: str) -> str:
    if code in {
        "approval_invalid",
        "document_integrity_failed",
        "document_parser_unavailable",
        "residual_pii",
        "restore_failed",
        "internal_error",
    }:
        return code
    return "provider_failed"

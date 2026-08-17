"""Provider-free Hosted 3.0 previews and pre-provider validation seams."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .approval import (
    ApprovalBindings,
    ApprovalEngine,
    ApprovalError,
    DocumentFacts,
    decode_generation_seed,
)
from .authority import AuthorityContext
from .document_artifact import PROMPT_REVISION as DOCUMENT_PROMPT_REVISION
from .protection import ProtectionResult, ProtectionService

MAX_CUSTOM_TEXT_CODEPOINTS = 20_000
MAX_CUSTOM_PROTECTED_UTF8_BYTES = 96 * 1024
CUSTOM_INITIAL_REMAINING_SECONDS = 1_030
CUSTOM_PREMINT_REMAINING_SECONDS = 1_020
QUEUE_ADMISSION_SECONDS = 900
CUSTOM_MINIMUM_REVIEW_SECONDS = 120
PROVIDER_ID = "tokenmind"
PROVIDER_MODEL = "thaillm-8b"
DETECTOR_CODE_SHA256 = "01bb7d890aa79cbc4f03a8c8da09c134e7e5074cfca3ef64960bf401c7391c64"
DETECTOR_MODEL_SHA256 = "bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315"
DEFAULT_SYSTEM_PROMPT = (
    "คุณเป็น AI assistant ที่มีประสิทธิภาพ "
    "ข้อความที่ได้รับอาจมี token เช่น 1909802000000 หรือ นายสมชาย รักชาติ "
    "ให้เก็บ token เหล่านั้นไว้ในคำตอบโดยไม่แก้ไขหรือแปล"
)
PROMPT_REVISION = "default-v1-" + hashlib.sha256(DEFAULT_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]


class PreviewError(ValueError):
    """A value-free provider-free preview failure."""

    def __init__(self, code: str, *, status: int):
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(slots=True)
class ValidatedCustomExecution:
    protected: ProtectionResult
    approval: dict[str, object] = field(repr=False)

    def clear(self) -> None:
        self.protected.mapping.clear()
        self.approval.clear()


def default_bindings() -> ApprovalBindings:
    return ApprovalBindings(
        provider_id=PROVIDER_ID,
        provider_model=PROVIDER_MODEL,
        prompt_revision=PROMPT_REVISION,
        detector_code_sha256=DETECTOR_CODE_SHA256,
        detector_model_sha256=DETECTOR_MODEL_SHA256,
    )


def document_bindings() -> ApprovalBindings:
    """Bind document approvals to the source-anchored structure prompt."""

    return ApprovalBindings(
        provider_id=PROVIDER_ID,
        provider_model=PROVIDER_MODEL,
        prompt_revision=DOCUMENT_PROMPT_REVISION,
        detector_code_sha256=DETECTOR_CODE_SHA256,
        detector_model_sha256=DETECTOR_MODEL_SHA256,
    )


class PreviewService:
    """Own provider-free preview and deterministic execute validation."""

    def __init__(
        self,
        approval: ApprovalEngine,
        *,
        protector: ProtectionService | None = None,
        hosted_version: str,
        now: Callable[[], float] | None = None,
        random_bytes: Callable[[int], bytes] | None = None,
        blocked_exceptions: tuple[type[BaseException], ...] | None = None,
        uncertain_exceptions: tuple[type[BaseException], ...] | None = None,
    ):
        self._approval = approval
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

    def preview_custom(
        self,
        request: object,
        *,
        authority: AuthorityContext,
    ) -> dict[str, object]:
        text, mode = _validate_custom_request(request)
        initial_now = int(self._now())
        if authority.expires_at_unix - initial_now < CUSTOM_INITIAL_REMAINING_SECONDS:
            raise PreviewError("session_review_window", status=409)
        salt = self._fresh_bytes(16).hex()
        generation_seed = self._fresh_bytes(32) if mode == "token" else None
        protected: ProtectionResult | None = None
        try:
            try:
                protected = self._protector.protect(
                    text,
                    mode=mode,
                    salt=salt,
                    generation_seed=generation_seed,
                )
            except Exception as error:
                if isinstance(error, self._uncertain_exceptions):
                    return self._blocked_response(
                        mode=mode,
                        authority=authority,
                        status="uncertain",
                        residual_count=0,
                    )
                if not isinstance(error, self._blocked_exceptions):
                    raise
                residual_count = getattr(error, "policy_category_count", 0)
                if type(residual_count) is not int or residual_count < 1:
                    residual_count = 1
                return self._blocked_response(
                    mode=mode,
                    authority=authority,
                    status="blocked",
                    residual_count=residual_count,
                )
            minted_at = int(self._now())
            if authority.expires_at_unix - minted_at < CUSTOM_PREMINT_REMAINING_SECONDS:
                raise PreviewError("session_review_window", status=409)
            try:
                protected_bytes = protected.protected_text.encode("utf-8")
            except UnicodeEncodeError:
                raise PreviewError("provider_payload_too_large", status=422) from None
            if len(protected_bytes) > MAX_CUSTOM_PROTECTED_UTF8_BYTES:
                protected_bytes = b""
                raise PreviewError("provider_payload_too_large", status=422)
            protected_bytes = b""
            source_sha256 = _text_sha256(text)
            protected_sha256 = _text_sha256(protected.protected_text)
            ticket, ticket_expires = self._approval.mint_custom(
                authority=authority,
                mode=mode,
                source_sha256=source_sha256,
                protected_sha256=protected_sha256,
                salt=salt,
                generation_seed=generation_seed,
            )
            queue_join_before = min(
                ticket_expires,
                authority.expires_at_unix - QUEUE_ADMISSION_SECONDS,
            )
            if queue_join_before - minted_at < CUSTOM_MINIMUM_REVIEW_SECONDS:
                raise PreviewError("session_review_window", status=409)
            return self._success_response(
                protected,
                mode=mode,
                authority=authority,
                protected_sha256=protected_sha256,
                ticket=ticket,
                ticket_expires=ticket_expires,
                queue_join_before=queue_join_before,
            )
        finally:
            text = ""
            salt = ""
            generation_seed = None
            if protected is not None:
                protected.mapping.clear()

    def validate_and_consume_custom(
        self,
        ticket: str,
        text: str,
        *,
        authority: AuthorityContext,
    ) -> ValidatedCustomExecution:
        if not isinstance(text, str) or not 1 <= len(text) <= MAX_CUSTOM_TEXT_CODEPOINTS:
            raise ApprovalError()
        payload = self._approval.inspect(
            ticket,
            authority=authority,
            expected_kind="custom_text_v1",
        )
        if not hmac.compare_digest(str(payload["source_sha256"]), _text_sha256(text)):
            raise ApprovalError()
        mode = str(payload["mode"])
        generation_seed = (
            decode_generation_seed(payload["protection_generation_seed"])
            if mode == "token"
            else None
        )
        protected: ProtectionResult | None = None
        try:
            protected = self._protector.protect(
                text,
                mode=mode,
                salt=str(payload["salt"]),
                generation_seed=generation_seed,
            )
            digest = _text_sha256(protected.protected_text)
            if not hmac.compare_digest(str(payload["protected_sha256"]), digest):
                raise ApprovalError()
            consumed = self._approval.consume(
                ticket,
                authority=authority,
                expected_kind="custom_text_v1",
            )
            return ValidatedCustomExecution(protected=protected, approval=consumed)
        except Exception:
            if protected is not None:
                protected.mapping.clear()
            raise
        finally:
            text = ""
            generation_seed = None

    def validate_document_facts(
        self,
        ticket: str,
        *,
        authority: AuthorityContext,
        expected_kind: str,
        facts: DocumentFacts,
    ) -> dict[str, object]:
        payload = self._approval.inspect(
            ticket,
            authority=authority,
            expected_kind=expected_kind,
        )
        expected = {
            "source_pdf_sha256": facts.source_pdf_sha256,
            "parser_revision": facts.parser_revision,
            "extraction_revision": facts.extraction_revision,
            "segmentation_revision": facts.segmentation_revision,
            "page_count": facts.page_count,
            "character_count": facts.character_count,
            "segment_count": facts.segment_count,
            "omitted_visual_page_numbers": list(facts.omitted_visual_page_numbers),
            "source_receipt_id": facts.source_receipt_id,
            "segment_manifest_sha256": facts.segment_manifest_sha256,
        }
        if expected_kind == "synthetic_document_v1":
            expected.update(
                {
                    "scenario_id": facts.scenario_id,
                    "scenario_registry_sha256": facts.scenario_registry_sha256,
                }
            )
        if any(payload.get(key) != value for key, value in expected.items()):
            raise ApprovalError()
        return payload

    def _success_response(
        self,
        protected: ProtectionResult,
        *,
        mode: str,
        authority: AuthorityContext,
        protected_sha256: str,
        ticket: str,
        ticket_expires: int,
        queue_join_before: int,
    ) -> dict[str, object]:
        return {
            "source_kind": (
                "custom_standard"
                if authority.scope == "public_guest"
                else "custom_invite"
            ),
            "scenario": None,
            "source_text": None,
            "protected_text": protected.protected_text,
            "mode": mode,
            "hosted_version": self._hosted_version,
            "provider": {
                "id": PROVIDER_ID,
                "model": PROVIDER_MODEL,
                "prompt_revision": PROMPT_REVISION,
            },
            "detected_entity_count": protected.detected_entity_count,
            "entity_type_counts": protected.entity_type_counts,
            "highlights": [
                {
                    "start": item.start,
                    "end": item.end,
                    "data_type": item.data_type,
                    "redact_type": item.redact_type,
                }
                for item in protected.highlights
            ],
            "section26_categories": protected.section26_categories,
            "guard_findings": protected.guard_findings,
            "outbound_gate": {
                "status": "no_residual_signal_detected",
                "residual_count": 0,
                "human_review_required": True,
            },
            "can_execute": True,
            "protected_sha256": protected_sha256,
            "ticket": ticket,
            "ticket_expires_at_unix": ticket_expires,
            "queue_join_before_unix": queue_join_before,
        }

    def _blocked_response(
        self,
        *,
        mode: str,
        authority: AuthorityContext,
        status: str,
        residual_count: int,
    ) -> dict[str, object]:
        return {
            "source_kind": (
                "custom_standard"
                if authority.scope == "public_guest"
                else "custom_invite"
            ),
            "scenario": None,
            "source_text": None,
            "protected_text": "",
            "mode": mode,
            "hosted_version": self._hosted_version,
            "provider": {
                "id": PROVIDER_ID,
                "model": PROVIDER_MODEL,
                "prompt_revision": PROMPT_REVISION,
            },
            "detected_entity_count": 0,
            "entity_type_counts": {},
            "highlights": [],
            "section26_categories": [],
            "guard_findings": [],
            "outbound_gate": {
                "status": status,
                "residual_count": residual_count,
                "human_review_required": True,
            },
            "can_execute": False,
            "protected_sha256": hashlib.sha256(b"").hexdigest(),
            "ticket": None,
            "ticket_expires_at_unix": None,
            "queue_join_before_unix": None,
        }

    def _fresh_bytes(self, size: int) -> bytes:
        value = self._random_bytes(size)
        if not isinstance(value, bytes) or len(value) != size:
            raise RuntimeError("preview random source returned an invalid value")
        return value


def _validate_custom_request(request: object) -> tuple[str, str]:
    if type(request) is not dict or set(request) != {"text", "mode"}:
        raise PreviewError("request_schema_invalid", status=422)
    text = request.get("text")
    mode = request.get("mode")
    if (
        not isinstance(text, str)
        or not 1 <= len(text) <= MAX_CUSTOM_TEXT_CODEPOINTS
        or not text.strip()
        or mode not in {"token", "surrogate"}
    ):
        code = (
            "payload_too_large"
            if isinstance(text, str) and len(text) > MAX_CUSTOM_TEXT_CODEPOINTS
            else "request_schema_invalid"
        )
        raise PreviewError(code, status=413 if code == "payload_too_large" else 422)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise PreviewError("request_schema_invalid", status=422) from None
    return text, str(mode)


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

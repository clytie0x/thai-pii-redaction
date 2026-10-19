#!/usr/bin/env python3
"""Stage 3B Core parser-client and provider-free document preview contracts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
sys.path.insert(0, str(CORE))

from aift_hosted3.approval import ApprovalEngine  # noqa: E402
from aift_hosted3.authority import AuthorityContext  # noqa: E402
from aift_hosted3.document_preview import (  # noqa: E402
    DOCUMENT_INITIAL_REMAINING_SECONDS,
    DOCUMENT_PREMINT_REMAINING_SECONDS,
    SCENARIO_REGISTRY_SHA256,
    SCENARIOS,
    DocumentPreviewService,
    _warnings,
)
from aift_hosted3.document_provider import (  # noqa: E402
    MAX_PROVIDER_PROTECTED_CHARACTERS,
    MAX_PROVIDER_REQUEST_BYTES,
    MAX_PROVIDER_SEGMENTS,
)
from aift_hosted3.overlay import Hosted3Overlay  # noqa: E402
from aift_hosted3.pdf_client import (  # noqa: E402
    DocumentSegment,
    PDFParserError,
    ParsedDocument,
    _parsed_response,
)
from aift_hosted3.preview import (  # noqa: E402
    PreviewError,
    default_bindings,
    document_bindings,
)
from aift_hosted3.protection import ProtectionResult  # noqa: E402


SOURCE_SHA = SCENARIOS["hr-resume-pdf-structured-v1"]["source_pdf_sha256"]


@dataclass
class Clock:
    value: int = 1_000

    def __call__(self):
        return self.value


class Bytes:
    def __init__(self):
        self.value = 0

    def __call__(self, size):
        self.value += 1
        return bytes([self.value % 251]) * size


class Blocked(Exception):
    policy_category_count = 2


class Uncertain(Exception):
    pass


class FakeProtector:
    def __init__(self, *, failure=None, clock=None, advance=0):
        self.failure = failure
        self.clock = clock
        self.advance = advance
        self.calls = 0

    def protect(self, text, *, mode, salt, generation_seed):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        protected = text.replace("กานต์ธิดา", "[NAME_1]").replace(
            "kanthida.s@example.com", "[EMAIL_1]"
        )
        if self.clock is not None:
            self.clock.value += self.advance
        return ProtectionResult(
            protected_text=protected,
            mapping={"[NAME_1]": "กานต์ธิดา", "[EMAIL_1]": "kanthida.s@example.com"},
            entity_type_counts={"NAME": 1, "EMAIL": 1},
            section26_categories=[],
            guard_findings=[],
            highlights=(),
        )

    def protect_document(self, segments, *, salt, generation_seed):
        return self.protect(
            "\n\n".join(segments),
            mode="token",
            salt=salt,
            generation_seed=generation_seed,
        )


class FixedTextProtector(FakeProtector):
    def __init__(self, protected_text):
        super().__init__()
        self.protected_text = protected_text

    def protect(self, text, *, mode, salt, generation_seed):
        result = super().protect(text, mode=mode, salt=salt, generation_seed=generation_seed)
        result.protected_text = self.protected_text
        return result


def parsed_document(*, scenario: bool, segment_count: int = 2) -> ParsedDocument:
    if segment_count == 2:
        segments = [
            DocumentSegment(page=1, segment_id="seg_001", text="กานต์ธิดา ศรีสุข"),
            DocumentSegment(
                page=1,
                segment_id="seg_002",
                text="kanthida.s@example.com",
            ),
        ]
    else:
        segments = [
            DocumentSegment(
                page=1,
                segment_id=f"seg_{index:03d}",
                text=f"synthetic segment {index}",
            )
            for index in range(1, segment_count + 1)
        ]
    manifest = hashlib.sha256(
        json.dumps(
            [
                {"page": row.page, "segment_id": row.segment_id, "text": row.text}
                for row in segments
            ],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return ParsedDocument(
        source_pdf_sha256=SOURCE_SHA if scenario else "a" * 64,
        parser_revision="aiguard-pdf-parser-v1",
        extraction_revision="pdfplumber-lines-v1",
        segmentation_revision="immutable-lines-v1",
        page_count=1,
        character_count=len("\n\n".join(row.text for row in segments)),
        segment_count=len(segments),
        omitted_visual_page_numbers=(1,),
        segments=segments,
        segment_manifest_sha256=manifest,
        extracted_text="\n\n".join(row.text for row in segments),
        scenario=(
            {
                "scenario_id": "hr-resume-pdf-structured-v1",
                "title": "เรซูเม่ภาษาไทยสมมติ",
                "registry_revision": "synthetic-document-registry-v1",
            }
            if scenario
            else None
        ),
    )


class FakeParser:
    def __init__(self, *, segment_count=2):
        self.calls = []
        self.last: ParsedDocument | None = None
        self.segment_count = segment_count

    async def parse_scenario(self, scenario_id):
        self.calls.append(("scenario", scenario_id))
        self.last = parsed_document(scenario=True, segment_count=self.segment_count)
        return self.last

    async def parse_document(self, receive, *, body_bytes, source_kind):
        self.calls.append(("document", body_bytes, source_kind))
        message = await receive()
        if message != {"type": "http.request", "body": b"pdf", "more_body": False}:
            raise AssertionError("unexpected fake upload body")
        self.last = parsed_document(scenario=False, segment_count=self.segment_count)
        return self.last


def approval(clock, random_bytes):
    return ApprovalEngine(
        b"K" * 32,
        default_bindings(),
        document_bindings=document_bindings(),
        now=clock,
        random_bytes=random_bytes,
        boot_nonce=b"B" * 16,
    )


class DocumentPreviewTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.random = Bytes()
        self.engine = approval(self.clock, self.random)
        self.standard = AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce="standard-session",
            subject_id=None,
            expires_at_unix=self.clock.value + 2_000,
        )
        self.priority = AuthorityContext(
            scope="priority_invite",
            service_class="priority",
            session_nonce="priority-session",
            subject_id="sub_AAAAAAAAAAAAAAAAAAAAAA",
            expires_at_unix=self.clock.value + 2_000,
        )

    def service(self, *, parser=None, protector=None):
        return DocumentPreviewService(
            self.engine,
            parser=parser or FakeParser(),
            protector=protector or FakeProtector(),
            hosted_version="3.0.2",
            now=self.clock,
            random_bytes=self.random,
            blocked_exceptions=(Blocked,),
            uncertain_exceptions=(Uncertain,),
        )

    def test_visual_and_ocr_warning_is_unconditional_and_pages_are_specific(self):
        without_omissions = _warnings("no_residual_signal_detected", ())
        self.assertEqual(len(without_omissions), 3)
        self.assertIn("replaced only detected PII", without_omissions[0])
        self.assertIn("selectable text", without_omissions[2])
        self.assertIn("visual layout", without_omissions[2])
        self.assertIn("OCR", without_omissions[2])
        with_omissions = _warnings("no_residual_signal_detected", (1, 3))
        self.assertEqual(with_omissions[:3], without_omissions)
        self.assertEqual(len(with_omissions), 4)
        self.assertIn("page(s) 1, 3", with_omissions[3])
        self.assertIn("omitted", with_omissions[3])

    def test_failure_warnings_are_status_aware_and_retain_source_limits(self):
        blocked = _warnings("blocked", ())
        uncertain = _warnings("uncertain", (2,))
        for warnings in (blocked, uncertain):
            self.assertIn("no usable protected result", warnings[0])
            self.assertIn("Nothing was sent to Pathumma", warnings[0])
            self.assertNotIn("replaced only detected PII", warnings[0])
            self.assertIn("source PDF is unchanged", warnings[1])
            self.assertIn("OCR and visual layout were not interpreted", warnings[2])
        self.assertIn("blocked this preview", blocked[0])
        self.assertIn("could not complete a reliable protected preview", uncertain[0])
        self.assertIn("page(s) 2", uncertain[3])

    def test_provider_segment_cap_fails_before_protection_and_clears_source(self):
        parser = FakeParser(segment_count=MAX_PROVIDER_SEGMENTS + 1)
        protector = FakeProtector()
        with self.assertRaisesRegex(PreviewError, "document_too_complex"):
            asyncio.run(
                self.service(parser=parser, protector=protector).preview_scenario(
                    {"scenario_id": "hr-resume-pdf-structured-v1"},
                    authority=self.standard,
                )
            )
        self.assertEqual(protector.calls, 0)
        self.assertEqual(parser.last.extracted_text, "")
        self.assertEqual(parser.last.segments, [])

    def test_scenario_and_uploaded_success_dtos_are_exact_and_source_free(self):
        parser = FakeParser()
        service = self.service(parser=parser)
        scenario = asyncio.run(
            service.preview_scenario(
                {"scenario_id": "hr-resume-pdf-structured-v1"},
                authority=self.standard,
            )
        )
        expected_keys = {
            "source_kind",
            "scenario",
            "hosted_version",
            "mode",
            "parser_revision",
            "extraction_revision",
            "page_count",
            "character_count",
            "segment_count",
            "omitted_visual_page_numbers",
            "protected_text",
            "detected_entity_count",
            "entity_type_counts",
            "outbound_gate",
            "warnings",
            "source_receipt_id",
            "protected_sha256",
            "can_execute",
            "ticket",
            "ticket_expires_at_unix",
            "queue_join_before_unix",
        }
        self.assertEqual(set(scenario), expected_keys)
        self.assertEqual(scenario["source_kind"], "synthetic_document")
        self.assertEqual(scenario["mode"], "token")
        self.assertTrue(scenario["can_execute"])
        self.assertEqual(scenario["queue_join_before_unix"] - self.clock.value, 600)
        payload = self.engine.inspect(
            scenario["ticket"],
            authority=self.standard,
            expected_kind="synthetic_document_v1",
        )
        self.assertEqual(
            payload["prompt_revision"],
            "structure-protected-document-classifications-v1",
        )
        self.assertEqual(payload["scenario_registry_sha256"], SCENARIO_REGISTRY_SHA256)
        self.assertEqual(payload["source_pdf_sha256"], SOURCE_SHA)
        self.assertEqual(payload["protected_sha256"], scenario["protected_sha256"])
        for forbidden in (
            "source_pdf_sha256",
            "source_sha256",
            "extracted_text",
            "segments",
            "mapping",
            "authority",
        ):
            self.assertNotIn(forbidden, scenario)
        self.assertEqual(parser.last.extracted_text, "")
        self.assertEqual(parser.last.segments, [])

        async def receive():
            return {"type": "http.request", "body": b"pdf", "more_body": False}

        uploaded = asyncio.run(
            service.preview_upload(
                receive,
                body_bytes=3,
                authority=self.priority,
            )
        )
        self.assertEqual(set(uploaded), expected_keys)
        self.assertEqual(uploaded["source_kind"], "document_invite")
        self.assertIsNone(uploaded["scenario"])
        self.engine.inspect(
            uploaded["ticket"],
            authority=self.priority,
            expected_kind="invite_document_v1",
        )
        self.assertNotIn("kanthida.s@example.com", repr(uploaded))

    def test_blocked_uncertain_and_timing_fail_closed(self):
        for failure, status in ((Blocked(), "blocked"), (Uncertain(), "uncertain")):
            response = asyncio.run(
                self.service(protector=FakeProtector(failure=failure)).preview_scenario(
                    {"scenario_id": "hr-resume-pdf-structured-v1"},
                    authority=self.standard,
                )
            )
            self.assertEqual(response["outbound_gate"]["status"], status)
            self.assertFalse(response["can_execute"])
            self.assertIsNone(response["ticket"])
            self.assertIsNone(response["ticket_expires_at_unix"])
            self.assertIsNone(response["queue_join_before_unix"])
            self.assertIn("no usable protected result", response["warnings"][0])
            self.assertIn("Nothing was sent to Pathumma", response["warnings"][0])
            self.assertNotIn("replaced only detected PII", response["warnings"][0])

        exact_parts = ["x"] * 2
        exact_parts[0] = "x" * (MAX_PROVIDER_PROTECTED_CHARACTERS - 3)
        exact = asyncio.run(
            self.service(
                protector=FixedTextProtector("\n\n".join(exact_parts))
            ).preview_scenario(
                {"scenario_id": "hr-resume-pdf-structured-v1"},
                authority=self.standard,
            )
        )
        self.assertTrue(exact["can_execute"])
        self.assertEqual(len(exact["protected_text"]), MAX_PROVIDER_PROTECTED_CHARACTERS)
        oversized_encoded_request = ("ก" * 3_100) + "\n\nx"
        self.assertLess(len(oversized_encoded_request), MAX_PROVIDER_PROTECTED_CHARACTERS)
        self.assertGreater(
            len(oversized_encoded_request.encode("utf-8")),
            MAX_PROVIDER_REQUEST_BYTES,
        )
        for protected_text in (
            ("x" * (MAX_PROVIDER_PROTECTED_CHARACTERS - 2)) + "\n\nx",
            oversized_encoded_request,
        ):
            with self.assertRaisesRegex(PreviewError, "document_too_complex"):
                asyncio.run(
                    self.service(
                        protector=FixedTextProtector(protected_text)
                    ).preview_scenario(
                        {"scenario_id": "hr-resume-pdf-structured-v1"},
                        authority=self.standard,
                    )
                )

        expiring = AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce="expiring",
            subject_id=None,
            expires_at_unix=self.clock.value + DOCUMENT_INITIAL_REMAINING_SECONDS - 1,
        )
        parser = FakeParser()
        with self.assertRaisesRegex(PreviewError, "session_review_window"):
            asyncio.run(
                self.service(parser=parser).preview_scenario(
                    {"scenario_id": "hr-resume-pdf-structured-v1"},
                    authority=expiring,
                )
            )
        self.assertEqual(parser.calls, [])

        delayed = self.service(
            protector=FakeProtector(
                clock=self.clock,
                advance=(2_000 - DOCUMENT_PREMINT_REMAINING_SECONDS + 1),
            )
        )
        with self.assertRaisesRegex(PreviewError, "session_review_window"):
            asyncio.run(
                delayed.preview_scenario(
                    {"scenario_id": "hr-resume-pdf-structured-v1"},
                    authority=self.standard,
                )
            )

    def test_parser_response_reconstruction_rejects_unknown_or_changed_facts(self):
        parsed = parsed_document(scenario=False)
        value = {
            "parser_revision": parsed.parser_revision,
            "extraction_revision": parsed.extraction_revision,
            "segmentation_revision": parsed.segmentation_revision,
            "source_sha256": parsed.source_pdf_sha256,
            "page_count": parsed.page_count,
            "character_count": parsed.character_count,
            "segment_count": parsed.segment_count,
            "omitted_visual_page_numbers": list(parsed.omitted_visual_page_numbers),
            "segments": [
                {"page": row.page, "segment_id": row.segment_id, "text": row.text}
                for row in parsed.segments
            ],
            "segment_manifest_sha256": parsed.segment_manifest_sha256,
            "extracted_text": parsed.extracted_text,
        }
        result = _parsed_response(
            {"ok": True, "result": value},
            expected_source_sha256="a" * 64,
        )
        self.assertNotIn("กานต์ธิดา", repr(result))
        result.clear()
        for corrupt in (
            value | {"raw_pdf": "forbidden"},
            value | {"source_sha256": "b" * 64},
            value | {"character_count": value["character_count"] - 1},
            value | {"segment_manifest_sha256": "0" * 64},
        ):
            with self.assertRaises(PDFParserError):
                _parsed_response(
                    {"ok": True, "result": corrupt},
                    expected_source_sha256="a" * 64,
                )


class DummyASGI:
    async def __call__(self, _scope, _receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b""})


class FakeTextService:
    def preview_custom(self, request, *, authority):
        return {"text": request, "scope": authority.scope}


class FakeDocumentService:
    def __init__(self):
        self.calls = []

    async def preview_scenario(self, request, *, authority):
        self.calls.append(("scenario", request, authority.scope))
        return {"document": "scenario"}

    async def preview_upload(self, receive, *, body_bytes, authority):
        self.calls.append(("upload", body_bytes, authority.scope))
        message = await receive()
        self.calls.append(("body", message["body"]))
        return {"document": "upload"}


async def overlay_request(app, path, authority, *, headers, body=b"", forbid_body=False):
    messages = []
    delivered = False

    async def receive():
        nonlocal delivered
        if forbid_body:
            raise AssertionError("body was consumed before request rejection")
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "query_string": b"",
        "headers": headers,
        "state": {"aiguard_authority": authority},
    }
    await app(scope, receive, send)
    start = next(value for value in messages if value["type"] == "http.response.start")
    response = b"".join(
        value.get("body", b"")
        for value in messages
        if value["type"] == "http.response.body"
    )
    return start["status"], json.loads(response)


class OverlayDocumentTests(unittest.TestCase):
    def test_exact_internal_document_and_scenario_routes_preserve_before_body_gates(self):
        authority = AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce="overlay",
            subject_id=None,
            expires_at_unix=5_000,
        )
        documents = FakeDocumentService()
        app = Hosted3Overlay(
            DummyASGI(),
            environ={"AIGUARD_API_KEY": "key"},
            service=FakeTextService(),
            document_service=documents,
            now=lambda: 1_000,
        )
        common = [(b"x-aiguard-contract-version", b"2"), (b"x-aiguard-key", b"key")]
        status, body = asyncio.run(
            overlay_request(
                app,
                "/api/document-preview",
                authority,
                headers=common + [(b"content-type", b"text/plain"), (b"content-length", b"3")],
                forbid_body=True,
            )
        )
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "request_schema_invalid")
        self.assertEqual(documents.calls, [])

        status, body = asyncio.run(
            overlay_request(
                app,
                "/api/document-preview",
                authority,
                headers=common
                + [
                    (b"content-type", b"application/pdf"),
                    (b"content-length", str(5 * 1024 * 1024 + 1).encode()),
                ],
                forbid_body=True,
            )
        )
        self.assertEqual(status, 413)
        self.assertEqual(body["error"]["code"], "payload_too_large")

        status, body = asyncio.run(
            overlay_request(
                app,
                "/api/document-preview",
                authority,
                headers=common
                + [(b"content-type", b"application/pdf"), (b"content-length", b"3")],
                body=b"pdf",
            )
        )
        self.assertEqual((status, body), (200, {"document": "upload"}))
        self.assertEqual(documents.calls[-2:], [("upload", 3, "public_guest"), ("body", b"pdf")])

        status, body = asyncio.run(
            overlay_request(
                app,
                "/api/guest/preview",
                authority,
                headers=common
                + [(b"content-type", b"application/json"), (b"content-length", b"58")],
                body=b'{"scenario_id":"hr-resume-pdf-structured-v1"}',
            )
        )
        self.assertEqual((status, body), (200, {"document": "scenario"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)

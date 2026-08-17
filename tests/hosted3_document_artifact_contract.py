#!/usr/bin/env python3
"""Stage 3 source-anchored Protected Markdown contract."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from aift_hosted3.document_artifact import (  # noqa: E402
    MAX_PROVIDER_RESPONSE_BYTES,
    ArtifactProvenance,
    DocumentArtifactError,
    render_protected_artifact,
)
from aift_hosted3.document_provider import (  # noqa: E402
    DOCUMENT_PROVIDER_MAX_TOKENS,
    DOCUMENT_SYSTEM_PROMPT,
    MAX_PROVIDER_REQUEST_BYTES,
    MAX_PROVIDER_SEGMENTS,
    DocumentProviderCallError,
    DocumentProviderRequestError,
    _run_document_provider_worker,
    document_provider_payload,
    encode_document_provider_request,
)
from aift_hosted3.document_provider_worker import (  # noqa: E402
    MAX_PROVIDER_WIRE_RESPONSE_BYTES,
    ProviderWireError,
    _complete_with_provider,
    _read_bounded_wire_response,
)
from aift_hosted3.pdf_client import DocumentSegment  # noqa: E402
from aift_hosted3.protection import ProtectionResult, ProtectionService  # noqa: E402
from pii_redactor.anonymizer.token_generator import generate_token  # noqa: E402


TOKEN = generate_token(
    "NAME",
    1,
    namespace="a" * 25,
    nonce="b" * 20,
)


def segments():
    return (
        DocumentSegment(1, "seg_001", f"ชื่อ: {TOKEN}"),
        DocumentSegment(1, "seg_002", "ประสบการณ์ <script>alert(1)</script>"),
        DocumentSegment(1, "seg_003", "Python * SQL [unsafe](https://example.test)"),
    )


def provenance(*, synthetic=False):
    return ArtifactProvenance(
        hosted_version="3.0.2",
        source_kind="synthetic_document" if synthetic else "document_standard",
        source_receipt_id="A" * 22,
        parser_revision="aiguard-pdf-parser-v1",
        extraction_revision="pdfplumber-lines-v1",
        page_count=1,
        omitted_visual_page_numbers=(1,),
        scenario_id="hr-resume-pdf-structured-v1" if synthetic else None,
        scenario_registry_revision="synthetic-document-registry-v1" if synthetic else None,
    )


def provider_value():
    return {
        "classifications": [
            {"segment_id": "seg_001", "role": "identity"},
            {"segment_id": "seg_002", "role": "experience"},
            {"segment_id": "seg_003", "role": "skills"},
        ]
    }


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


class DocumentArtifactTests(unittest.TestCase):
    def test_provider_request_is_exact_bounded_and_carries_only_protected_segments(self):
        lengths = [248] * 31 + [220]
        boundary_segments = tuple(
            DocumentSegment(
                1,
                f"seg_{index:03d}",
                (f"Protected segment {index:03d} " + "X" * 400)[:length],
            )
            for index, length in enumerate(lengths, start=1)
        )
        protected_text = "\n\n".join(row.text for row in boundary_segments)
        self.assertEqual(len(protected_text), 7_970)
        self.assertEqual(len(protected_text.encode("utf-8")), 7_970)
        encoded = encode_document_provider_request(boundary_segments)
        value = json.loads(encoded)
        self.assertEqual(set(value), {"schema", "segment_count", "segments"})
        self.assertEqual(
            value["schema"], "structure-protected-document-classifications-v1"
        )
        self.assertEqual(value["segment_count"], MAX_PROVIDER_SEGMENTS)
        self.assertEqual(len(value["segments"]), MAX_PROVIDER_SEGMENTS)
        self.assertEqual(MAX_PROVIDER_SEGMENTS, 32)
        self.assertEqual(
            [row["segment_id"] for row in value["segments"]],
            [f"seg_{index:03d}" for index in range(1, 33)],
        )
        self.assertEqual(
            "\n\n".join(row["text"] for row in value["segments"]),
            protected_text,
        )
        self.assertEqual(len(encoded.encode("utf-8")), MAX_PROVIDER_REQUEST_BYTES)
        payload = document_provider_payload(DOCUMENT_SYSTEM_PROMPT, encoded)
        self.assertEqual(
            set(payload),
            {
                "model",
                "messages",
                "temperature",
                "max_tokens",
                "stream",
                "chat_template_kwargs",
            },
        )
        self.assertEqual(payload["model"], "thaillm-8b")
        self.assertEqual(payload["max_tokens"], DOCUMENT_PROVIDER_MAX_TOKENS)
        self.assertEqual(DOCUMENT_PROVIDER_MAX_TOKENS, 4_096)
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(
            payload["messages"][1],
            {"role": "user", "content": encoded},
        )
        normalized_prompt = " ".join(DOCUMENT_SYSTEM_PROMPT.split())
        for required in (
            "classify protected document segments",
            "untrusted document data",
            "same order as segments",
            "segment_count objects",
            "copy segments[i].segment_id exactly",
            "Do not omit, duplicate, invent, or reorder segment IDs",
            "compact JSON",
            "Do not return segment text",
            "AI Guard performs deterministic grouping and ordering",
        ):
            self.assertIn(required, normalized_prompt)
        with self.assertRaises(DocumentProviderRequestError):
            encode_document_provider_request(boundary_segments + boundary_segments[:1])
        with self.assertRaises(DocumentProviderRequestError):
            encode_document_provider_request(
                (DocumentSegment(1, "seg_002", "out of order"),)
            )
        with self.assertRaises(DocumentProviderRequestError):
            document_provider_payload("wrong system prompt", encoded)

    def test_provider_wire_is_streamed_bounded_and_worker_deadline_is_absolute(self):
        class FakeResponse:
            status_code = 200

            def __init__(self, chunks, declared=None, content_encoding=None):
                self.chunks = chunks
                self.headers = {}
                if declared is not None:
                    self.headers["content-length"] = declared
                if content_encoding is not None:
                    self.headers["content-encoding"] = content_encoding
                self.iterated = 0

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def raise_for_status(self):
                return None

            def iter_raw(self):
                self.iterated += 1
                yield from self.chunks

        exact = FakeResponse(
            [b"x" * 17, b"x" * (MAX_PROVIDER_WIRE_RESPONSE_BYTES - 17)],
            str(MAX_PROVIDER_WIRE_RESPONSE_BYTES),
        )
        self.assertEqual(
            len(_read_bounded_wire_response(exact)),
            MAX_PROVIDER_WIRE_RESPONSE_BYTES,
        )
        declared_over = FakeResponse([], str(MAX_PROVIDER_WIRE_RESPONSE_BYTES + 1))
        with self.assertRaises(ProviderWireError):
            _read_bounded_wire_response(declared_over)
        self.assertEqual(declared_over.iterated, 0)
        with self.assertRaises(ProviderWireError):
            _read_bounded_wire_response(FakeResponse([b"x"], "invalid"))
        compressed = FakeResponse(
            [b"compressed bytes that must never be decoded"],
            "43",
            "gzip",
        )
        with self.assertRaises(ProviderWireError):
            _read_bounded_wire_response(compressed)
        self.assertEqual(compressed.iterated, 0)
        identity = FakeResponse([b"{}"], "2", "identity")
        self.assertEqual(_read_bounded_wire_response(identity), b"{}")
        with self.assertRaises(ProviderWireError):
            _read_bounded_wire_response(
                FakeResponse(
                    [b"x" * MAX_PROVIDER_WIRE_RESPONSE_BYTES, b"y"],
                    "1",
                )
            )

        outer = b'{"bounded":true}'
        streamed = FakeResponse([outer[:3], outer[3:]], str(len(outer)))

        class FakeClient:
            def __init__(self):
                self.calls = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def stream(self, *args, **kwargs):
                captured = dict(kwargs)
                captured["headers"] = dict(kwargs.get("headers", {}))
                self.calls.append((args, captured))
                return streamed

        class FakeProvider:
            _api_key = "provider-test-key"
            _url = "https://provider.invalid/v1/chat/completions"

            def __init__(self):
                self.client = FakeClient()

            def _client(self):
                return self.client

            def _validated_content(self, response):
                self.assertion = response.content == outer
                return '{"classifications":[{"segment_id":"seg_001","role":"other"}]}'

        provider = FakeProvider()
        result = _complete_with_provider(
            provider,
            DOCUMENT_SYSTEM_PROMPT,
            encode_document_provider_request((DocumentSegment(1, "seg_001", "x"),)),
        )
        self.assertTrue(provider.assertion)
        self.assertEqual(len(provider.client.calls), 1)
        self.assertEqual(provider.client.calls[0][0][0], "POST")
        self.assertEqual(
            provider.client.calls[0][1]["headers"]["Accept-Encoding"],
            "identity",
        )
        self.assertEqual(provider._api_key, "")
        self.assertIn("classifications", result)

        with tempfile.TemporaryDirectory() as directory:
            worker = Path(directory) / "slow_worker.py"
            worker.write_text(
                "import sys,time\n"
                "for _ in range(300):\n"
                " sys.stdout.write('x')\n"
                " sys.stdout.flush()\n"
                " time.sleep(.1)\n",
                encoding="utf-8",
            )
            started = time.monotonic()
            with self.assertRaises(DocumentProviderCallError) as caught:
                _run_document_provider_worker(
                    b"{}",
                    timeout_seconds=0.2,
                    worker_path=worker,
                    environment=os.environ.copy(),
                )
            self.assertEqual(caught.exception.code, "provider_timeout")
            self.assertLess(time.monotonic() - started, 10.0)

    def test_document_protection_rejects_any_cross_segment_token_collision(self):
        class CollidingProtector(ProtectionService):
            def __init__(self):
                pass

            def protect(self, text, *, mode, salt, generation_seed):
                return ProtectionResult(
                    protected_text=TOKEN,
                    mapping={TOKEN: text},
                    entity_type_counts={"NAME": 1},
                    section26_categories=[],
                    guard_findings=[],
                    highlights=(),
                )

        with self.assertRaisesRegex(ValueError, "document token collision"):
            CollidingProtector().protect_document(
                ("first", "second"),
                salt="53" * 16,
                generation_seed=b"G" * 32,
            )

    def test_exact_ast_renders_only_fixed_headings_and_escaped_source(self):
        calls = []
        artifact = render_protected_artifact(
            encoded(provider_value()),
            segments=segments(),
            provenance=provenance(),
            outbound_guard=lambda text, tokens: calls.append((text, tokens)),
        )
        self.assertEqual(
            set(artifact.protected_document_ast), {"ordered_sections"}
        )
        self.assertTrue(artifact.exact_segment_coverage)
        self.assertTrue(artifact.expected_token_integrity)
        self.assertTrue(artifact.structured_output_validated)
        self.assertEqual(calls[0][1], {TOKEN})
        self.assertTrue(artifact.protected_markdown.startswith("> AI Guard Hosted 3\\.0\\.2"))
        self.assertTrue(artifact.protected_plain_text.startswith("AI Guard Hosted 3.0.2"))
        self.assertIn("## ข้อมูลผู้สมัคร", artifact.protected_markdown)
        self.assertNotIn("<script>", artifact.semantic_html)
        self.assertIn("&lt;script&gt;", artifact.semantic_html)
        self.assertNotIn("<a ", artifact.semantic_html)
        self.assertNotIn("[unsafe](https://example.test)", artifact.protected_markdown)
        self.assertIn("\\[unsafe\\]\\(https://example\\.test\\)", artifact.protected_markdown)
        self.assertNotIn("source_sha256", repr(artifact))
        artifact.clear()
        self.assertEqual(artifact.protected_document_ast, {})
        self.assertEqual(artifact.protected_markdown, "")

    def test_provider_cannot_author_content_or_break_exact_coverage(self):
        invalid = (
            provider_value() | {"title": "provider heading"},
            {"classifications": [
                {"segment_id": "seg_001", "role": "unknown"},
                {"segment_id": "seg_002", "role": "experience"},
                {"segment_id": "seg_003", "role": "skills"},
            ]},
            {"classifications": provider_value()["classifications"][:2]},
            {"classifications": provider_value()["classifications"] + [
                {"segment_id": "seg_004", "role": "other"}
            ]},
            {"classifications": [
                {"segment_id": "seg_002", "role": "identity"},
                {"segment_id": "seg_001", "role": "experience"},
                {"segment_id": "seg_003", "role": "skills"},
            ]},
            {"classifications": [
                {"segment_id": "seg_001", "role": "identity", "text": "forbidden"},
                {"segment_id": "seg_002", "role": "experience"},
                {"segment_id": "seg_003", "role": "skills"},
            ]},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(DocumentArtifactError):
                render_protected_artifact(
                    encoded(value),
                    segments=segments(),
                    provenance=provenance(),
                    outbound_guard=lambda _text, _tokens: None,
                )

    def test_json_size_duplicate_keys_unicode_and_provenance_fail_closed(self):
        bodies = (
            b"",
            b"x" * (MAX_PROVIDER_RESPONSE_BYTES + 1),
            b'{"classifications":[],"classifications":[]}',
            b'{"classifications":[{"segment_id":"\\ud800","role":"identity"}]}',
            b'{"classifications":[],"free_text":"hello"}',
        )
        for body in bodies:
            with self.subTest(body=body[:30]), self.assertRaises(DocumentArtifactError):
                render_protected_artifact(
                    body,
                    segments=segments(),
                    provenance=provenance(),
                    outbound_guard=lambda _text, _tokens: None,
                )
        with self.assertRaises(DocumentArtifactError):
            render_protected_artifact(
                encoded(provider_value()),
                segments=segments(),
                provenance=ArtifactProvenance(
                    **{
                        name: getattr(provenance(), name)
                        for name in ArtifactProvenance.__dataclass_fields__
                        if name != "source_receipt_id"
                    },
                    source_receipt_id="raw-source-sha-not-allowed",
                ),
                outbound_guard=lambda _text, _tokens: None,
            )

    def test_residual_or_guard_failure_is_value_free_integrity_error(self):
        for guard in (
            lambda _text, _tokens: (_ for _ in ()).throw(RuntimeError("raw value")),
            lambda _text, _tokens: (_ for _ in ()).throw(
                DocumentArtifactError("document_integrity_failed")
            ),
        ):
            with self.assertRaises(DocumentArtifactError) as caught:
                render_protected_artifact(
                    encoded(provider_value()),
                    segments=segments(),
                    provenance=provenance(synthetic=True),
                    outbound_guard=guard,
                )
            self.assertEqual(caught.exception.code, "document_integrity_failed")
            self.assertNotIn("raw value", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Stage 4B2 queue-bound custom and document execute contract."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(os.environ.get("AIGUARD_HOSTED3_RUNTIME_ROOT", ROOT / "core"))
sys.path.insert(0, str(RUNTIME_ROOT))

from aift_hosted3.approval import ApprovalEngine, DocumentFacts  # noqa: E402
from aift_hosted3.authority import AuthorityContext  # noqa: E402
import aift_hosted3.custom_provider as custom_provider_module  # noqa: E402
from aift_hosted3.custom_provider import (  # noqa: E402
    MAX_CUSTOM_PROVIDER_OUTPUT_CODEPOINTS,
    MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES,
    CustomProviderCallError,
    complete_custom_provider,
    _validate_request as validate_custom_provider_request,
    _run_worker as run_custom_provider_worker,
    _worker_response as custom_provider_worker_response,
)
from aift_hosted3.custom_provider_worker import (  # noqa: E402
    MAX_CUSTOM_PROVIDER_WIRE_RESPONSE_BYTES,
    CustomProviderConfigurationError,
    CustomProviderWireError,
    _build_provider as build_custom_provider,
    _read_bounded_wire_response,
    _strict_request_frame as strict_custom_provider_request_frame,
)
from aift_hosted3.document_preview import (  # noqa: E402
    SCENARIOS,
    SCENARIO_REGISTRY_SHA256,
)
from aift_hosted3.execution import (  # noqa: E402
    GENERATED_PII_MARKER,
    ExecuteError,
    ExecuteService,
    _generated_pii_spans,
    _mask_spans,
)
from aift_hosted3.document_provider import DocumentProviderCallError  # noqa: E402
from aift_hosted3.overlay import (  # noqa: E402
    DOCUMENT_EXECUTE_PATH,
    GUEST_EXECUTE_PATH,
    PROTECTION_EXECUTE_PATH,
    Hosted3Overlay,
)
from aift_hosted3.pdf_client import (  # noqa: E402
    EXTRACTION_REVISION,
    PARSER_REVISION,
    SEGMENTATION_REVISION,
    DocumentSegment,
    ParsedDocument,
)
from aift_hosted3.preview import default_bindings, document_bindings  # noqa: E402
from aift_hosted3.protection import ProtectionResult  # noqa: E402
from aift_hosted3.provider_queue import ProviderQueue, ProviderQueueError  # noqa: E402
from pii_redactor.anonymizer.token_generator import generate_token  # noqa: E402


NOW = 2_100_000_000
TOKEN = generate_token(
    "NAME",
    1,
    namespace="a" * 25,
    nonce="b" * 20,
)
CUSTOM_SOURCE = "สรุปประวัติของ สมชาย ใจดี"
CUSTOM_PROTECTED = f"สรุปประวัติของ {TOKEN}"
DOCUMENT_SOURCE_PARTS = ("ชื่อ สมชาย ใจดี", "ทักษะ Python และ SQL")
DOCUMENT_PROTECTED_PARTS = (f"ชื่อ {TOKEN}", "ทักษะ Python และ SQL")
DOCUMENT_PROTECTED = "\n\n".join(DOCUMENT_PROTECTED_PARTS)
SCENARIO_ID = "hr-resume-pdf-structured-v1"


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Clock:
    def __init__(self, value: int = NOW):
        self.value = value

    def __call__(self):
        return float(self.value)


class Entropy:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def __call__(self, size: int) -> bytes:
        with self.lock:
            self.value += 1
            value = self.value
        output = b""
        while len(output) < size:
            output += hashlib.sha256(f"execute:{value}:{len(output)}".encode()).digest()
        return output[:size]


class FakeProtector:
    def __init__(self):
        self.results = []

    def protect(self, text, *, mode, salt, generation_seed):
        if text != CUSTOM_SOURCE or mode != "token":
            raise AssertionError("unexpected custom reconstruction")
        result = ProtectionResult(
            protected_text=CUSTOM_PROTECTED,
            mapping={TOKEN: "สมชาย ใจดี"},
            entity_type_counts={"NAME": 1},
            section26_categories=[],
            guard_findings=[],
            highlights=(),
        )
        self.results.append(result)
        return result

    def protect_document(self, segments, *, salt, generation_seed):
        if segments != DOCUMENT_SOURCE_PARTS:
            raise AssertionError("unexpected document reconstruction")
        result = ProtectionResult(
            protected_text=DOCUMENT_PROTECTED,
            mapping={TOKEN: "สมชาย ใจดี"},
            entity_type_counts={"NAME": 1},
            section26_categories=[],
            guard_findings=[],
            highlights=(),
        )
        self.results.append(result)
        return result


class FakeParser:
    def __init__(self, *, wrong_source=False):
        self.calls = 0
        self.wrong_source = wrong_source

    async def parse_scenario(self, scenario_id):
        self.calls += 1
        if scenario_id != SCENARIO_ID:
            raise AssertionError("wrong scenario")
        source = SCENARIOS[SCENARIO_ID]
        rows = [
            DocumentSegment(1, "seg_001", DOCUMENT_SOURCE_PARTS[0]),
            DocumentSegment(1, "seg_002", DOCUMENT_SOURCE_PARTS[1]),
        ]
        extracted = "\n\n".join(row.text for row in rows)
        return ParsedDocument(
            source_pdf_sha256=("0" * 64 if self.wrong_source else source["source_pdf_sha256"]),
            parser_revision=PARSER_REVISION,
            extraction_revision=EXTRACTION_REVISION,
            segmentation_revision=SEGMENTATION_REVISION,
            page_count=1,
            character_count=len(extracted),
            segment_count=2,
            omitted_visual_page_numbers=(1,),
            segments=rows,
            segment_manifest_sha256="a" * 64,
            extracted_text=extracted,
            scenario={
                "scenario_id": SCENARIO_ID,
                "title": source["title"],
                "registry_revision": source["registry_revision"],
            },
        )


class Harness:
    def __init__(self):
        self.clock = Clock()
        self.entropy = Entropy()
        self.approval = ApprovalEngine(
            b"A" * 32,
            default_bindings(),
            document_bindings=document_bindings(),
            now=self.clock,
            random_bytes=self.entropy,
            boot_nonce=b"B" * 16,
        )
        self.queue = ProviderQueue(
            b"Q" * 32,
            self.approval,
            now=self.clock,
            random_bytes=self.entropy,
            boot_nonce=b"C" * 16,
        )
        self.authority = AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce=b64(b"S" * 16),
            subject_id=None,
            expires_at_unix=NOW + 1_800,
        )

    def claim(self, ticket):
        joined = self.queue.join(ticket, authority=self.authority)
        claimed = self.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=self.authority,
            wait_seconds=0,
        )
        self.assert_claim(claimed)
        return joined["queue_capability"], claimed["claim_token"]

    @staticmethod
    def assert_claim(value):
        if value.get("state") != "claim_ready":
            raise AssertionError(f"expected claim_ready, received {value!r}")

    def custom_ticket(self):
        return self.approval.mint_custom(
            authority=self.authority,
            mode="token",
            source_sha256=sha(CUSTOM_SOURCE),
            protected_sha256=sha(CUSTOM_PROTECTED),
            salt="5" * 32,
            generation_seed=b"G" * 32,
        )[0]

    def document_facts(self, *, synthetic=False):
        source = SCENARIOS[SCENARIO_ID]
        return DocumentFacts(
            source_pdf_sha256=(source["source_pdf_sha256"] if synthetic else "d" * 64),
            parser_revision=PARSER_REVISION,
            extraction_revision=EXTRACTION_REVISION,
            segmentation_revision=SEGMENTATION_REVISION,
            page_count=1,
            character_count=len("\n\n".join(DOCUMENT_SOURCE_PARTS)),
            segment_count=2,
            omitted_visual_page_numbers=(1,),
            source_receipt_id=b64(b"R" * 16),
            segment_manifest_sha256="a" * 64,
            scenario_id=SCENARIO_ID if synthetic else None,
            scenario_registry_sha256=(SCENARIO_REGISTRY_SHA256 if synthetic else None),
        )

    def document_ticket(self, *, synthetic=False):
        return self.approval.mint_document(
            kind=("synthetic_document_v1" if synthetic else "standard_document_v1"),
            authority=self.authority,
            protected_sha256=sha(DOCUMENT_PROTECTED),
            salt="6" * 32,
            generation_seed=b"H" * 32,
            facts=self.document_facts(synthetic=synthetic),
        )[0]


class DummyASGI:
    async def __call__(self, _scope, _receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b""})


class FakeHttpExecute:
    def __init__(self):
        self.calls = []

    async def execute_synthetic_document(self, request, *, authority):
        self.calls.append(("synthetic", dict(request), authority.service_class))
        return {"result": "synthetic"}

    def execute_custom(self, request, *, authority):
        self.calls.append(("custom", dict(request), authority.service_class))
        return {"result": "custom"}

    def execute_uploaded_document(self, request, *, authority):
        self.calls.append(("document", dict(request), authority.service_class))
        return {"result": "document"}


class SlowSyntheticHttpExecute(FakeHttpExecute):
    async def execute_synthetic_document(self, request, *, authority):
        self.calls.append(("synthetic", dict(request), authority.service_class))
        time.sleep(0.25)
        return {"result": "synthetic"}


class FakeWireResponse:
    def __init__(self, chunks, *, headers=None):
        self._chunks = list(chunks)
        self.headers = {} if headers is None else dict(headers)
        self.iterated = False

    def iter_raw(self):
        self.iterated = True
        yield from self._chunks


async def http_request(app, path, authority, *, payload=None, raw=None, method="POST"):
    body = (
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
        if raw is None
        else raw
    )
    delivered = False
    sent = []

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await app(
        {
            "type": "http",
            "method": method,
            "path": path,
            "query_string": b"",
            "headers": [
                (b"x-aiguard-key", b"core-key"),
                (b"x-aiguard-contract-version", b"2"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
            "state": {"aiguard_authority": authority},
        },
        receive,
        send,
    )
    if not sent:
        return None, {}, None
    start = sent[0]
    headers = {key.decode(): value.decode() for key, value in start["headers"]}
    raw_body = b"".join(
        row.get("body", b"") for row in sent if row["type"] == "http.response.body"
    )
    return start["status"], headers, json.loads(raw_body) if raw_body else None

def provider_ast():
    return json.dumps(
        {
            "classifications": [
                {"segment_id": "seg_001", "role": "identity"},
                {"segment_id": "seg_002", "role": "skills"},
            ]
        },
        separators=(",", ":"),
    )


class ExecuteContractTests(unittest.TestCase):
    def custom_service(self, h, *, custom_call=None, outbound=None, restore_call=None):
        protector = FakeProtector()
        calls = []
        guards = []

        def provider(system, user, before_attempt):
            calls.append((system, user))
            before_attempt(0)
            return f"ผลสรุปสำหรับ {TOKEN}", 0.1, 1

        def guard(text, trusted):
            guards.append((text, set(trusted)))

        def restore(text, *, mapping, mode):
            self.assertEqual(mapping, {TOKEN: "สมชาย ใจดี"})
            return SimpleNamespace(
                restored_text=text.replace(TOKEN, "สมชาย ใจดี"),
                replaced_count=1,
                leftover_pseudonyms=[],
                generated_pii_count=0,
                foreign_replacement_count=0,
            )

        service = ExecuteService(
            h.queue,
            hosted_version="3.0.1",
            protector=protector,
            custom_provider_call=custom_call or provider,
            document_provider_call=lambda _system, _user: provider_ast(),
            restore=restore_call or restore,
            outbound_guard=outbound or guard,
            monotonic=lambda: 10.0,
            request_id=lambda: "00000000-0000-4000-8000-000000000001",
        )
        return service, protector, calls, guards

    def document_service(
        self,
        h,
        *,
        parser=None,
        document_call=None,
        outbound=None,
        request_id=None,
    ):
        calls = []
        guards = []

        def provider(system, user):
            calls.append((system, user))
            return provider_ast()

        def guard(text, trusted):
            guards.append((text, set(trusted)))

        return (
            ExecuteService(
                h.queue,
                hosted_version="3.0.1",
                parser=parser or FakeParser(),
                protector=FakeProtector(),
                custom_provider_call=lambda *_args: (_ for _ in ()).throw(
                    AssertionError("custom provider must not run")
                ),
                document_provider_call=document_call or provider,
                outbound_guard=outbound or guard,
                monotonic=lambda: 20.0,
                request_id=(
                    request_id
                    or (lambda: "00000000-0000-4000-8000-000000000002")
                ),
            ),
            calls,
            guards,
        )

    def test_custom_execute_is_claim_bound_rechecks_outbound_and_restores(self):
        h = Harness()
        capability, claim = h.claim(h.custom_ticket())
        service, protector, calls, guards = self.custom_service(h)
        response = service.execute_custom(
            {
                "text": CUSTOM_SOURCE,
                "queue_capability": capability,
                "claim_token": claim,
            },
            authority=h.authority,
        )
        self.assertEqual(
            set(response),
            {
                "request_id",
                "hosted_version",
                "source_kind",
                "scenario",
                "synthetic_provenance",
                "protected_text",
                "ai_response_masked",
                "restored_text",
                "mode",
                "detected_entity_count",
                "entity_type_counts",
                "section26_categories",
                "guard_findings",
                "warnings",
                "safety",
                "restoration",
                "provider",
                "receipt",
            },
        )
        self.assertEqual(response["protected_text"], CUSTOM_PROTECTED)
        self.assertEqual(response["restored_text"], "ผลสรุปสำหรับ สมชาย ใจดี")
        self.assertEqual(calls[0][1], CUSTOM_PROTECTED)
        self.assertNotIn("สมชาย ใจดี", calls[0][1])
        self.assertEqual(guards, [(CUSTOM_PROTECTED, {TOKEN})])
        self.assertEqual(protector.results[0].mapping, {})
        receipt = response["receipt"]
        self.assertTrue(receipt["digest_match"])
        self.assertNotIn("source_sha256", receipt)
        self.assertNotIn("queue_capability", json.dumps(response, ensure_ascii=False))
        self.assertEqual(h.queue.status(authority=h.authority)["state"], "complete")
        with self.assertRaises(ProviderQueueError):
            service.execute_custom(
                {
                    "text": CUSTOM_SOURCE,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )

    def test_custom_generated_pii_is_masked_rather_than_discarding_the_answer(self):
        """A detector hit on provider prose must cost that span, not the reply.

        The detector runs outside its calibrated domain on text the model wrote,
        so ordinary template wording produces false spans. Dropping the whole
        answer turns each such miss into total unavailability, while masking the
        span removes exactly the distrusted text and keeps the rest usable.
        """
        answer = "ทักษะที่ควรใส่ ได้แก่ การสื่อสาร และ นายสมหญิง ทดสอบดี ปิดท้าย"
        start = answer.index("นายสมหญิง ทดสอบดี")
        end = start + len("นายสมหญิง ทดสอบดี")
        restored = SimpleNamespace(
            restored_text=answer,
            replaced_count=1,
            leftover_pseudonyms=[],
            generated_pii_count=1,
            foreign_replacement_count=0,
            generated_pii_spans=((start, end),),
        )

        h = Harness()
        capability, claim = h.claim(h.custom_ticket())
        service, _protector, _calls, _guards = self.custom_service(
            h,
            restore_call=lambda *_args, **_kwargs: restored,
        )

        response = service.execute_custom(
            {
                "text": CUSTOM_SOURCE,
                "queue_capability": capability,
                "claim_token": claim,
            },
            authority=h.authority,
        )

        self.assertEqual(response["restoration"]["status"], "sanitized")
        self.assertEqual(response["restoration"]["masked_count"], 1)
        self.assertEqual(response["warnings"], [{"code": "generated_pii", "count": 1}])
        self.assertNotIn("นายสมหญิง", response["restored_text"])
        self.assertNotIn("ทดสอบดี", response["restored_text"])
        self.assertIn("ทักษะที่ควรใส่ ได้แก่ การสื่อสาร", response["restored_text"])
        self.assertIn("ปิดท้าย", response["restored_text"])
        self.assertEqual(response["receipt"]["restoration_status"], "sanitized")

    def test_custom_generated_pii_without_usable_spans_still_discards_the_answer(self):
        """Masking is only safe when the offsets say what to mask.

        A count with no offsets means the distrusted text cannot be located, so
        the old all-or-nothing block stays the correct answer.
        """
        restored = SimpleNamespace(
            restored_text="UNSAFE RESTORED",
            replaced_count=1,
            leftover_pseudonyms=[],
            generated_pii_count=1,
            foreign_replacement_count=0,
            generated_pii_spans=(),
        )

        h = Harness()
        capability, claim = h.claim(h.custom_ticket())
        service, _protector, _calls, _guards = self.custom_service(
            h,
            restore_call=lambda *_args, **_kwargs: restored,
        )

        response = service.execute_custom(
            {
                "text": CUSTOM_SOURCE,
                "queue_capability": capability,
                "claim_token": claim,
            },
            authority=h.authority,
        )

        self.assertEqual(response["restoration"]["status"], "unsafe")
        self.assertEqual(response["restored_text"], "")

    def test_custom_nonusable_restoration_never_returns_restored_text(self):
        cases = (
            (
                "unsafe",
                SimpleNamespace(
                    restored_text="UNSAFE RESTORED",
                    replaced_count=1,
                    leftover_pseudonyms=[],
                    generated_pii_count=0,
                    foreign_replacement_count=1,
                    generated_pii_spans=(),
                ),
                [{"code": "foreign_replacement", "count": 1}],
            ),
            (
                "unsafe",
                SimpleNamespace(
                    restored_text="UNSAFE RESTORED",
                    replaced_count=1,
                    leftover_pseudonyms=[],
                    generated_pii_count=1,
                    foreign_replacement_count=1,
                    generated_pii_spans=((0, 6),),
                ),
                [
                    {"code": "generated_pii", "count": 1},
                    {"code": "foreign_replacement", "count": 1},
                ],
            ),
            (
                "incomplete",
                SimpleNamespace(
                    restored_text=f"ผลสรุปสำหรับ {TOKEN}",
                    replaced_count=0,
                    leftover_pseudonyms=[TOKEN],
                    generated_pii_count=0,
                    foreign_replacement_count=0,
                ),
                [],
            ),
            (
                # An unresolved token means the mapping itself did not land, so
                # no part of this reply is trustworthy enough to sanitize and
                # show -- masking must not rescue it.
                "incomplete",
                SimpleNamespace(
                    restored_text=f"ผลสรุปสำหรับ {TOKEN} และ นายสมหญิง ทดสอบดี",
                    replaced_count=0,
                    leftover_pseudonyms=[TOKEN],
                    generated_pii_count=1,
                    foreign_replacement_count=0,
                    generated_pii_spans=((0, 6),),
                ),
                [{"code": "generated_pii", "count": 1}],
            ),
        )
        for expected_status, restored, expected_warnings in cases:
            with self.subTest(expected_status):
                h = Harness()
                capability, claim = h.claim(h.custom_ticket())
                service, _protector, _calls, _guards = self.custom_service(
                    h,
                    restore_call=lambda *_args, **_kwargs: restored,
                )

                response = service.execute_custom(
                    {
                        "text": CUSTOM_SOURCE,
                        "queue_capability": capability,
                        "claim_token": claim,
                    },
                    authority=h.authority,
                )

                self.assertEqual(response["restoration"]["status"], expected_status)
                self.assertEqual(response["warnings"], expected_warnings)
                self.assertEqual(response["restored_text"], "")

    @unittest.skipUnless(
        importlib.util.find_spec("pythainlp") is not None,
        "real detector dependencies are verified in the Core image",
    )
    def test_real_port_restoration_accepts_exact_tokens_and_rejects_generated_name(self):
        from pii_redactor.stateless import restore_stateless, sanitize_stateless

        source = "ผู้สมัครสังเคราะห์ สมชาย ใจดี ติดต่อ test@example.invalid"
        protected = sanitize_stateless(source, mode="token", salt="hosted-3.0.1")
        exact = restore_stateless(
            f"**คำตอบ:**\n\n{protected.sanitized_text}",
            mapping=protected.mapping,
            mode="token",
        )
        generated = restore_stateless(
            f"ผู้ติดต่อใหม่ นายสมหญิง ทดสอบดี\n{protected.sanitized_text}",
            mapping=protected.mapping,
            mode="token",
        )

        self.assertEqual(exact.restored_text, f"**คำตอบ:**\n\n{source}")
        self.assertEqual(exact.replaced_count, len(protected.mapping))
        self.assertEqual(exact.leftover_pseudonyms, [])
        self.assertEqual(exact.generated_pii_count, 0)
        self.assertGreaterEqual(generated.generated_pii_count, 1)
        self.assertEqual(len(generated.generated_pii_spans), generated.generated_pii_count)
        covered = "".join(
            generated.restored_text[start:end] for start, end in generated.generated_pii_spans
        )
        self.assertIn("สมหญิง", covered)

    @unittest.skipUnless(
        importlib.util.find_spec("pythainlp") is not None,
        "real detector dependencies are verified in the Core image",
    )
    def test_real_port_keeps_a_pii_free_template_answer_the_detector_misreads(self):
        """The exact public incident: résumé template prose blocked a whole reply.

        The provider wrote a placeholder and ordinary Thai template wording that
        contains no personal data at all. The detector still claims spans there,
        because provider prose is outside the domain it was measured on. The
        reply must survive with those spans masked.
        """
        from pii_redactor.stateless import restore_stateless, sanitize_stateless

        source = "ผู้สมัครสังเคราะห์ สมชาย ใจดี ติดต่อ test@example.invalid"
        protected = sanitize_stateless(source, mode="token", salt="hosted-3.0.1")
        answer = (
            "เรียน ฝ่ายทรัพยากรบุคคล [บริษัท/องค์กร]\n"
            f"{protected.sanitized_text}\n"
            "จึงเรียนมาเพื่อโปรดพิจารณา"
        )
        restored = restore_stateless(answer, mapping=protected.mapping, mode="token")

        self.assertEqual(restored.leftover_pseudonyms, [])
        self.assertGreaterEqual(restored.generated_pii_count, 1)

        spans = _generated_pii_spans(restored, len(restored.restored_text))
        self.assertTrue(spans)
        masked = _mask_spans(restored.restored_text, spans)

        # The mapping's own values stay restored; only the misread template
        # wording is closed, and the surrounding answer survives.
        self.assertIn("สมชาย ใจดี", masked)
        self.assertIn("เรียน ฝ่ายทรัพยากรบุคคล", masked)
        self.assertIn("จึงเรียนมาเพื่อโปรดพิจารณา", masked)
        self.assertIn(GENERATED_PII_MARKER, masked)

    def test_custom_mismatch_and_outbound_failure_contact_no_unapproved_provider(self):
        h = Harness()
        capability, claim = h.claim(h.custom_ticket())
        service, _protector, calls, _guards = self.custom_service(h)
        with self.assertRaisesRegex(ExecuteError, "approval_invalid"):
            service.execute_custom(
                {
                    "text": CUSTOM_SOURCE + "!",
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(calls, [])
        status = h.queue.status(authority=h.authority)
        self.assertEqual((status["state"], status["reason"]), ("failed", "approval_invalid"))

        h = Harness()
        capability, claim = h.claim(h.custom_ticket())
        contacts = []

        def retrying(_system, _user, before):
            before(0)
            contacts.append("attempt-1")
            before(1)
            contacts.append("attempt-2")
            return "never", 0.0, 2

        guard_calls = []

        def fail_second(_text, _trusted):
            guard_calls.append(1)
            if len(guard_calls) == 2:
                raise RuntimeError("sensitive detail must not escape")

        service, _protector, _calls, _guards = self.custom_service(
            h,
            custom_call=retrying,
            outbound=fail_second,
        )
        with self.assertRaisesRegex(ExecuteError, "residual_pii"):
            service.execute_custom(
                {
                    "text": CUSTOM_SOURCE,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(contacts, ["attempt-1"])
        self.assertEqual(h.queue.snapshot()[0]["provider_attempt_count"], 1)

    def test_uploaded_document_requires_exact_protected_bytes_and_returns_only_artifact(self):
        h = Harness()
        capability, claim = h.claim(h.document_ticket())
        service, calls, guards = self.document_service(h)
        response = service.execute_uploaded_document(
            {
                "protected_text": DOCUMENT_PROTECTED,
                "queue_capability": capability,
                "claim_token": claim,
            },
            authority=h.authority,
        )
        self.assertEqual(
            set(response),
            {
                "request_id",
                "hosted_version",
                "source_kind",
                "scenario",
                "artifact_provenance",
                "protected_text",
                "source_receipt_id",
                "protected_document_ast",
                "protected_markdown",
                "protected_plain_text",
                "omitted_visual_page_numbers",
                "warnings",
                "provider",
                "receipt",
            },
        )
        self.assertEqual(response["source_kind"], "document_standard")
        self.assertIsNone(response["scenario"])
        self.assertIn("# เอกสารข้อความที่ป้องกันแล้ว", response["protected_markdown"])
        self.assertIn("PII was not restored", response["protected_markdown"])
        self.assertNotIn("สมชาย ใจดี", json.dumps(response, ensure_ascii=False))
        self.assertEqual(len(calls), 1)
        self.assertIn(TOKEN, calls[0][1])
        self.assertEqual(guards[0], (DOCUMENT_PROTECTED, {TOKEN}))
        self.assertTrue(response["receipt"]["exact_segment_coverage"])
        self.assertEqual(
            response["protected_document_ast"],
            {
                "ordered_sections": [
                    {"role": "identity", "segment_ids": ["seg_001"]},
                    {"role": "skills", "segment_ids": ["seg_002"]},
                ]
            },
        )
        self.assertNotIn("source_pdf_sha256", response["receipt"])
        self.assertEqual(h.queue.status(authority=h.authority)["state"], "complete")

        h = Harness()
        capability, claim = h.claim(h.document_ticket())
        service, calls, _guards = self.document_service(h)
        with self.assertRaisesRegex(ExecuteError, "approval_invalid"):
            service.execute_uploaded_document(
                {
                    "protected_text": DOCUMENT_PROTECTED + "!",
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(calls, [])

    def test_synthetic_reparses_pinned_source_and_never_restores_pii(self):
        h = Harness()
        capability, claim = h.claim(h.document_ticket(synthetic=True))
        parser = FakeParser()
        service, calls, _guards = self.document_service(h, parser=parser)
        response = asyncio.run(
            service.execute_synthetic_document(
                {
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        )
        self.assertEqual(parser.calls, 1)
        self.assertEqual(response["source_kind"], "synthetic_document")
        self.assertEqual(response["scenario"]["scenario_id"], SCENARIO_ID)
        self.assertIn("PII was not restored", response["protected_plain_text"])
        self.assertNotIn("restored_text", response)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("สมชาย ใจดี", calls[0][1])

        h = Harness()
        capability, claim = h.claim(h.document_ticket(synthetic=True))
        service, calls, _guards = self.document_service(
            h,
            parser=FakeParser(wrong_source=True),
        )
        with self.assertRaisesRegex(ExecuteError, "approval_invalid"):
            asyncio.run(
                service.execute_synthetic_document(
                    {
                        "queue_capability": capability,
                        "claim_token": claim,
                    },
                    authority=h.authority,
                )
            )
        self.assertEqual(calls, [])

    def test_schema_and_stale_claim_fail_before_provider_contact(self):
        h = Harness()
        service, _protector, calls, _guards = self.custom_service(h)
        with self.assertRaisesRegex(ExecuteError, "request_schema_invalid"):
            service.execute_custom(
                {
                    "text": CUSTOM_SOURCE,
                    "queue_capability": "x",
                    "claim_token": "y",
                    "extra": True,
                },
                authority=h.authority,
            )
        self.assertEqual(calls, [])

    def test_fixed_provider_restore_structure_and_parser_failures_are_value_free(self):
        h = Harness()
        capability, claim = h.claim(h.custom_ticket())

        def empty_provider(_system, _user, before):
            before(0)
            return "", 0.0, 1

        service, _protector, _calls, _guards = self.custom_service(
            h,
            custom_call=empty_provider,
        )
        with self.assertRaisesRegex(ExecuteError, "provider_response_invalid"):
            service.execute_custom(
                {
                    "text": CUSTOM_SOURCE,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(h.queue.snapshot()[0]["provider_attempt_count"], 1)
        self.assertEqual(h.queue.status(authority=h.authority)["reason"], "provider_failed")

        h = Harness()
        capability, claim = h.claim(h.custom_ticket())
        service, _protector, _calls, _guards = self.custom_service(
            h,
            restore_call=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("raw provider response must not escape")
            ),
        )
        with self.assertRaisesRegex(ExecuteError, "restore_failed"):
            service.execute_custom(
                {
                    "text": CUSTOM_SOURCE,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(h.queue.status(authority=h.authority)["reason"], "restore_failed")

        h = Harness()
        capability, claim = h.claim(h.document_ticket())
        service, calls, _guards = self.document_service(
            h,
            document_call=lambda _system, user: (
                calls.append(user) or '{"classifications":[]}'
            ),
        )
        with self.assertRaisesRegex(ExecuteError, "document_structure_invalid"):
            service.execute_uploaded_document(
                {
                    "protected_text": DOCUMENT_PROTECTED,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(h.queue.snapshot()[0]["provider_attempt_count"], 1)
        self.assertEqual(h.queue.status(authority=h.authority)["reason"], "provider_failed")

        h = Harness()
        capability, claim = h.claim(h.document_ticket())
        service, calls, _guards = self.document_service(
            h,
            document_call=lambda _system, _user: (_ for _ in ()).throw(
                DocumentProviderCallError("provider_configuration")
            ),
        )
        with self.assertRaisesRegex(ExecuteError, "provider_configuration"):
            service.execute_uploaded_document(
                {
                    "protected_text": DOCUMENT_PROTECTED,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(h.queue.snapshot()[0]["provider_attempt_count"], 0)

        h = Harness()
        capability, claim = h.claim(h.document_ticket())
        provider_contacts = []
        service, _calls, _guards = self.document_service(
            h,
            document_call=lambda _system, _user: provider_contacts.append(1),
            outbound=lambda _text, _trusted: (_ for _ in ()).throw(
                RuntimeError("residual detail")
            ),
        )
        with self.assertRaisesRegex(ExecuteError, "residual_pii"):
            service.execute_uploaded_document(
                {
                    "protected_text": DOCUMENT_PROTECTED,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(provider_contacts, [])
        self.assertEqual(h.queue.status(authority=h.authority)["reason"], "residual_pii")

        h = Harness()
        capability, claim = h.claim(h.document_ticket())
        service, _calls, _guards = self.document_service(
            h,
            request_id=lambda: (_ for _ in ()).throw(RuntimeError("internal detail")),
        )
        with self.assertRaisesRegex(ExecuteError, "internal_error"):
            service.execute_uploaded_document(
                {
                    "protected_text": DOCUMENT_PROTECTED,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(h.queue.status(authority=h.authority)["reason"], "internal_error")

        capability, claim = h.claim(h.custom_ticket())
        h.clock.value += 16
        h.queue.tick()
        with self.assertRaises(ProviderQueueError):
            service.execute_custom(
                {
                    "text": CUSTOM_SOURCE,
                    "queue_capability": capability,
                    "claim_token": claim,
                },
                authority=h.authority,
            )
        self.assertEqual(calls, [])

    def test_internal_execute_routes_are_exact_no_store_and_schema_strict(self):
        h = Harness()
        fake = FakeHttpExecute()
        app = Hosted3Overlay(
            DummyASGI(),
            environ={"AIGUARD_API_KEY": "core-key"},
            service=SimpleNamespace(),
            queue=h.queue,
            execute_service=fake,
            now=h.clock,
        )
        rows = (
            (
                GUEST_EXECUTE_PATH,
                {"queue_capability": "cap", "claim_token": "claim"},
                "synthetic",
            ),
            (
                PROTECTION_EXECUTE_PATH,
                {
                    "text": "protected",
                    "queue_capability": "cap",
                    "claim_token": "claim",
                },
                "custom",
            ),
            (
                DOCUMENT_EXECUTE_PATH,
                {
                    "protected_text": "protected",
                    "queue_capability": "cap",
                    "claim_token": "claim",
                },
                "document",
            ),
        )
        for path, payload, expected in rows:
            status, headers, body = asyncio.run(
                http_request(app, path, h.authority, payload=payload)
            )
            self.assertEqual(status, 200)
            self.assertEqual(headers["cache-control"], "no-store")
            self.assertEqual(headers["x-aiguard-contract-version"], "2")
            self.assertEqual(headers["x-aiguard-service-class"], "standard")
            self.assertEqual(body, {"result": expected})
        self.assertEqual([row[0] for row in fake.calls], ["synthetic", "custom", "document"])

        before = len(fake.calls)
        status, _headers, body = asyncio.run(
            http_request(
                app,
                PROTECTION_EXECUTE_PATH,
                h.authority,
                raw=b'{"text":"x","text":"y"}',
            )
        )
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "request_schema_invalid")
        self.assertEqual(len(fake.calls), before)

        status, _headers, body = asyncio.run(
            http_request(
                app,
                PROTECTION_EXECUTE_PATH,
                h.authority,
                payload={"text": "x"},
                method="GET",
            )
        )
        self.assertEqual(status, 405)
        self.assertEqual(body["error"]["code"], "method_not_allowed")
        self.assertEqual(len(fake.calls), before)

    def test_synthetic_execute_keeps_the_asgi_event_loop_responsive(self):
        h = Harness()
        fake = SlowSyntheticHttpExecute()
        app = Hosted3Overlay(
            DummyASGI(),
            environ={"AIGUARD_API_KEY": "core-key"},
            service=SimpleNamespace(),
            queue=h.queue,
            execute_service=fake,
            now=h.clock,
        )

        async def exercise():
            started = time.monotonic()
            heartbeat = asyncio.create_task(asyncio.sleep(0.025))
            request = asyncio.create_task(
                http_request(
                    app,
                    GUEST_EXECUTE_PATH,
                    h.authority,
                    payload={"queue_capability": "cap", "claim_token": "claim"},
                )
            )
            await heartbeat
            heartbeat_elapsed = time.monotonic() - started
            response = await request
            return heartbeat_elapsed, response

        heartbeat_elapsed, (status, _headers, body) = asyncio.run(exercise())
        self.assertLess(heartbeat_elapsed, 0.12)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"result": "synthetic"})

    def test_custom_transport_caps_raw_wire_before_parse_and_has_absolute_timeout(self):
        exact_input = "😀" * (MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES // 4)
        validate_custom_provider_request(
            custom_provider_module.DEFAULT_SYSTEM_PROMPT,
            exact_input,
        )
        request_frame = json.dumps(
            {
                "system_b64": base64.urlsafe_b64encode(
                    custom_provider_module.DEFAULT_SYSTEM_PROMPT.encode("utf-8")
                ).decode("ascii"),
                "user_b64": base64.urlsafe_b64encode(
                    exact_input.encode("utf-8")
                ).decode("ascii"),
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        self.assertEqual(
            strict_custom_provider_request_frame(request_frame),
            (custom_provider_module.DEFAULT_SYSTEM_PROMPT, exact_input),
        )

        response = FakeWireResponse([b'{"ok":', b'true}'])
        self.assertEqual(_read_bounded_wire_response(response), b'{"ok":true}')
        self.assertTrue(response.iterated)

        encoded = FakeWireResponse(
            [b"compressed"],
            headers={"content-encoding": "gzip"},
        )
        with self.assertRaises(CustomProviderWireError):
            _read_bounded_wire_response(encoded)
        self.assertFalse(encoded.iterated)

        declared = FakeWireResponse(
            [b"x"],
            headers={"content-length": str(MAX_CUSTOM_PROVIDER_WIRE_RESPONSE_BYTES + 1)},
        )
        with self.assertRaises(CustomProviderWireError):
            _read_bounded_wire_response(declared)
        self.assertFalse(declared.iterated)

        chunked = FakeWireResponse(
            [b"x" * MAX_CUSTOM_PROVIDER_WIRE_RESPONSE_BYTES, b"x"]
        )
        with self.assertRaises(CustomProviderWireError):
            _read_bounded_wire_response(chunked)

        oversized = "😀" * (MAX_CUSTOM_PROVIDER_OUTPUT_CODEPOINTS + 1)
        frame = json.dumps(
            {
                "ok": True,
                "content_b64": base64.urlsafe_b64encode(
                    oversized.encode("utf-8")
                ).decode("ascii").rstrip("="),
            },
            separators=(",", ":"),
        ).encode("ascii")
        self.assertGreater(len(oversized.encode("utf-8")), MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES)
        with self.assertRaisesRegex(CustomProviderCallError, "provider_response_invalid"):
            custom_provider_worker_response(frame)

        with tempfile.TemporaryDirectory() as directory:
            worker = Path(directory) / "slow_worker.py"
            worker.write_text(
                "import time\ntime.sleep(1.0)\nprint('{}')\n",
                encoding="utf-8",
            )
            started = time.monotonic()
            with self.assertRaisesRegex(CustomProviderCallError, "provider_timeout"):
                run_custom_provider_worker(
                    b"{}",
                    worker_path=worker,
                    environment={},
                    timeout_seconds=0.05,
                )
            self.assertLess(time.monotonic() - started, 0.5)

            real_popen = custom_provider_module.subprocess.Popen

            def delayed_popen(*args, **kwargs):
                time.sleep(0.08)
                return real_popen(*args, **kwargs)

            started = time.monotonic()
            with mock.patch.object(
                custom_provider_module.subprocess,
                "Popen",
                side_effect=delayed_popen,
            ):
                with self.assertRaisesRegex(
                    CustomProviderCallError,
                    "provider_timeout",
                ):
                    run_custom_provider_worker(
                        b"{}",
                        worker_path=worker,
                        environment={},
                        timeout_seconds=0.05,
                    )
            self.assertLess(time.monotonic() - started, 0.5)

        attempts = []
        with (
            mock.patch.object(
                custom_provider_module,
                "_complete_once",
                side_effect=[
                    CustomProviderCallError("provider_timeout"),
                    CustomProviderCallError("provider_unavailable"),
                    "bounded result",
                ],
            ),
            mock.patch.object(custom_provider_module.time, "sleep"),
        ):
            value, _latency, count = complete_custom_provider(
                custom_provider_module.DEFAULT_SYSTEM_PROMPT,
                "protected",
                attempts.append,
            )
        self.assertEqual((value, count, attempts), ("bounded result", 3, [0, 1, 2]))

        attempts = []
        with mock.patch.object(
            custom_provider_module,
            "_complete_once",
            side_effect=CustomProviderCallError("provider_response_invalid"),
        ):
            with self.assertRaisesRegex(
                CustomProviderCallError,
                "provider_response_invalid",
            ):
                complete_custom_provider(
                    custom_provider_module.DEFAULT_SYSTEM_PROMPT,
                    "protected",
                    attempts.append,
                )
        self.assertEqual(attempts, [0])

        with self.assertRaises(CustomProviderConfigurationError):
            build_custom_provider(
                lambda: (_ for _ in ()).throw(ValueError("operator detail"))
            )

        attempts = []
        with mock.patch.object(
            custom_provider_module,
            "_complete_once",
            side_effect=CustomProviderCallError("provider_configuration"),
        ):
            with self.assertRaises(CustomProviderCallError) as caught:
                complete_custom_provider(
                    custom_provider_module.DEFAULT_SYSTEM_PROMPT,
                    "protected",
                    attempts.append,
                )
        self.assertEqual(caught.exception.code, "provider_configuration")
        self.assertEqual(caught.exception.attempts, 0)
        self.assertEqual(attempts, [0])

if __name__ == "__main__":
    unittest.main(verbosity=2)

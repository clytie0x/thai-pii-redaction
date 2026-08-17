#!/usr/bin/env python3
"""Stage-2 contracts for approval tickets and provider-free text preview."""

from __future__ import annotations

import base64
import asyncio
import ast
import concurrent.futures
import hashlib
import json
import sys
import threading
import unittest
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
sys.path.insert(0, str(CORE))

from aift_hosted3.approval import (  # noqa: E402
    APPROVAL_CONTEXT,
    ApprovalBindings,
    ApprovalEngine,
    ApprovalError,
    ConsumedJTIRegistry,
    DocumentFacts,
    derive_approval_key,
)
from aift_hosted3.authority import AuthorityContext  # noqa: E402
from aift_hosted3.preview import (  # noqa: E402
    DEFAULT_SYSTEM_PROMPT,
    DETECTOR_CODE_SHA256,
    DETECTOR_MODEL_SHA256,
    PROMPT_REVISION,
    PreviewError,
    PreviewService,
    document_bindings,
)
from aift_hosted3.overlay import Hosted3Overlay  # noqa: E402
from aift_hosted3.protection import (  # noqa: E402
    ProtectionResult,
    _token_seed_mapping,
)
from aift_hosted3.runtime import require_single_worker  # noqa: E402


HASH_A = "a" * 64
HASH_B = "b" * 64
PROTECTION_REVISION_FILES = (
    "pii_redactor/detectors/aggregate.py",
    "pii_redactor/detectors/fn_scanner.py",
    "pii_redactor/detectors/fp_detector.py",
    "pii_redactor/detectors/name_context.py",
    "pii_redactor/detectors/ner_failure.py",
    "pii_redactor/detectors/tb_detector.py",
    "pii_redactor/detectors/thai_id.py",
    "pii_redactor/detectors/tner_client.py",
    "pii_redactor/anonymizer/anonymizer.py",
    "pii_redactor/anonymizer/fp_generator.py",
    "pii_redactor/anonymizer/tb_generator.py",
    "pii_redactor/anonymizer/token_generator.py",
    "pii_redactor/guard/injection.py",
    "pii_redactor/ingest/text_cleaner.py",
    "pii_redactor/leak_guard.py",
    "pii_redactor/models.py",
    "pii_redactor/report.py",
    "pii_redactor/scan_common.py",
    "pii_redactor/session_vault.py",
    "pii_redactor/stateless.py",
)


@dataclass
class Entity:
    span: tuple[int, int]
    data_type: str
    original_text: str


@dataclass
class Highlight:
    start: int
    end: int
    data_type: str
    redact_type: str


class Blocked(Exception):
    policy_category_count = 2


class Uncertain(Exception):
    pass


class FakeProtector:
    def __init__(self, failure: BaseException | None = None):
        self.failure = failure
        self.calls = 0

    def protect(self, text, *, mode, salt, generation_seed):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        suffix = hashlib.sha256(
            salt.encode() + (generation_seed or b"") + mode.encode()
        ).hexdigest()[:10]
        protected = f"protected:{suffix}"
        return ProtectionResult(
            protected_text=protected,
            mapping={f"[{suffix}]": text},
            entity_type_counts={"EMAIL": 1},
            section26_categories=[],
            guard_findings=[],
            highlights=(Highlight(0, len(protected), "EMAIL", "FP"),),
        )


class AdvancingProtector(FakeProtector):
    def __init__(self, advance):
        super().__init__()
        self._advance = advance

    def protect(self, text, *, mode, salt, generation_seed):
        result = super().protect(
            text,
            mode=mode,
            salt=salt,
            generation_seed=generation_seed,
        )
        self._advance()
        return result


class OversizedProtectedProtector(FakeProtector):
    def __init__(self, protected_text):
        super().__init__()
        self.protected_text = protected_text
        self.result = None

    def protect(self, text, *, mode, salt, generation_seed):
        self.calls += 1
        self.result = ProtectionResult(
            protected_text=self.protected_text,
            mapping={"[protected]": text},
            entity_type_counts={"NAME": 1},
            section26_categories=[],
            guard_findings=[],
            highlights=(),
        )
        return self.result


class FakePreviewService:
    def __init__(self):
        self.calls = []

    def preview_custom(self, request, *, authority):
        self.calls.append((request, authority))
        return {"preview": "provider-free"}


class DummyASGI:
    async def __call__(self, _scope, _receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b""})


async def overlay_request(
    app,
    *,
    authority,
    body=b'{"text":"x","mode":"token"}',
    headers=None,
    method="POST",
    query=b"",
    forbid_body=False,
):
    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if forbid_body:
            raise AssertionError("preview body read before admission")
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": method,
        "path": "/api/protection-preview",
        "query_string": query,
        "headers": headers
        or [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"x-aiguard-key", b"core-key"),
            (b"x-aiguard-contract-version", b"2"),
        ],
        "state": {"aiguard_authority": authority} if authority is not None else {},
    }
    await app(scope, receive, send)
    start = next(item for item in sent if item["type"] == "http.response.start")
    response_headers = {
        key.decode().lower(): value.decode()
        for key, value in start.get("headers", [])
    }
    response_body = b"".join(
        item.get("body", b"") for item in sent if item["type"] == "http.response.body"
    )
    return start["status"], response_headers, response_body


class DeterministicBytes:
    def __init__(self):
        self.counter = 0

    def __call__(self, size: int) -> bytes:
        self.counter += 1
        return bytes([self.counter]) * size


class Hosted3ApprovalContractTests(unittest.TestCase):
    def setUp(self):
        self.now_value = 1_900_000_000
        self.standard = AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce="standard-session-nonce",
            subject_id=None,
            expires_at_unix=self.now_value + 1800,
        )
        self.priority = AuthorityContext(
            scope="priority_invite",
            service_class="priority",
            session_nonce="priority-session-nonce",
            subject_id="sub_AAAAAAAAAAAAAAAAAAAAAA",
            expires_at_unix=self.now_value + 1800,
        )
        self.bindings = ApprovalBindings(
            provider_id="tokenmind",
            provider_model="thaillm-8b",
            prompt_revision=PROMPT_REVISION,
            detector_code_sha256=DETECTOR_CODE_SHA256,
            detector_model_sha256=DETECTOR_MODEL_SHA256,
        )
        self.key = derive_approval_key(b"K" * 32)

    def engine(self, *, random_bytes=None, boot=b"B" * 16, capacity=8, key=None, bindings=None):
        return ApprovalEngine(
            self.key if key is None else key,
            self.bindings if bindings is None else bindings,
            document_bindings=document_bindings(),
            now=lambda: self.now_value,
            random_bytes=random_bytes or DeterministicBytes(),
            boot_nonce=boot,
            replay_capacity=capacity,
        )

    def mint_custom(self, engine, *, authority=None, mode="token"):
        return engine.mint_custom(
            authority=authority or self.standard,
            mode=mode,
            source_sha256=HASH_A,
            protected_sha256=HASH_B,
            salt="11" * 16,
            generation_seed=b"G" * 32 if mode == "token" else None,
        )[0]

    def test_key_derivation_and_deterministic_vector(self):
        self.assertEqual(len(self.key), 32)
        self.assertNotEqual(self.key, b"K" * 32)
        engine = self.engine(random_bytes=lambda size: bytes([size]) * size)
        ticket = self.mint_custom(engine)
        self.assertEqual(len(ticket), 1279)
        self.assertEqual(
            hashlib.sha256(ticket.encode()).hexdigest(),
            "30e1767c6dfa0128d57e4de88fbf11b9fcace9e97614836e29a9191eca09229f",
        )
        decoded = base64.urlsafe_b64decode(ticket + "=" * (-len(ticket) % 4))
        self.assertNotIn(b"source", decoded)
        self.assertNotIn(b"mapping", decoded)
        self.assertTrue(APPROVAL_CONTEXT)

    def test_nonce_uniqueness_tamper_wrong_key_and_wrong_boot_fail(self):
        random_source = DeterministicBytes()
        engine = self.engine(random_bytes=random_source)
        one = self.mint_custom(engine)
        two = self.mint_custom(engine)
        self.assertNotEqual(one, two)
        tampered = one[:-1] + ("A" if one[-1] != "A" else "B")
        with self.assertRaisesRegex(ApprovalError, "approval_invalid"):
            engine.inspect(tampered, authority=self.standard, expected_kind="custom_text_v1")
        with self.assertRaises(ApprovalError):
            self.engine(key=b"W" * 32).inspect(
                one, authority=self.standard, expected_kind="custom_text_v1"
            )
        with self.assertRaises(ApprovalError):
            self.engine(boot=b"R" * 16).inspect(
                one, authority=self.standard, expected_kind="custom_text_v1"
            )

    def test_session_class_kind_revision_and_expiry_fail_closed(self):
        engine = self.engine()
        ticket = self.mint_custom(engine)
        for authority in (
            self.priority,
            AuthorityContext(
                scope="public_guest",
                service_class="standard",
                session_nonce="different-session",
                subject_id=None,
                expires_at_unix=self.standard.expires_at_unix,
            ),
        ):
            with self.assertRaises(ApprovalError):
                engine.inspect(ticket, authority=authority, expected_kind="custom_text_v1")
        with self.assertRaises(ApprovalError):
            engine.inspect(ticket, authority=self.standard, expected_kind="invite_document_v1")
        changed = ApprovalBindings(
            provider_id=self.bindings.provider_id,
            provider_model=self.bindings.provider_model,
            prompt_revision="changed-v2",
            detector_code_sha256=self.bindings.detector_code_sha256,
            detector_model_sha256=self.bindings.detector_model_sha256,
        )
        with self.assertRaises(ApprovalError):
            self.engine(bindings=changed).inspect(
                ticket, authority=self.standard, expected_kind="custom_text_v1"
            )
        self.now_value += 301
        with self.assertRaisesRegex(ApprovalError, "approval_expired"):
            engine.inspect(ticket, authority=self.standard, expected_kind="custom_text_v1")

    def test_replay_registry_is_atomic_bounded_pruned_and_value_free(self):
        registry = ConsumedJTIRegistry(capacity=2, now=lambda: self.now_value)
        registry.consume("first", self.now_value + 10)
        with self.assertRaisesRegex(ApprovalError, "approval_consumed"):
            registry.consume("first", self.now_value + 10)
        registry.consume("second", self.now_value + 20)
        with self.assertRaisesRegex(ApprovalError, "approval_registry_full"):
            registry.consume("third", self.now_value + 30)
        rows = registry.snapshot()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(len(key) == 32 and type(expiry) is int for key, expiry in rows))
        self.assertNotIn(b"first", repr(rows).encode())
        self.now_value += 11
        registry.consume("third", self.now_value + 30)

    def test_concurrent_execute_has_one_winner_and_fixed_consumed_losers(self):
        raw = "somchai@example.com"
        service = self.service()
        preview = service.preview_custom(
            {"text": raw, "mode": "token"}, authority=self.standard
        )
        worker_count = 32
        barrier = threading.Barrier(worker_count)

        def attempt(_index):
            barrier.wait()
            try:
                validated = service.validate_and_consume_custom(
                    preview["ticket"], raw, authority=self.standard
                )
                validated.clear()
                return "winner"
            except ApprovalError as error:
                return error.code

        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
            outcomes = list(pool.map(attempt, range(worker_count)))
        self.assertEqual(outcomes.count("winner"), 1)
        self.assertEqual(outcomes.count("approval_consumed"), worker_count - 1)

    def test_document_codecs_bind_injected_facts_without_content(self):
        facts = DocumentFacts(
            source_pdf_sha256=HASH_A,
            parser_revision="parser-v1",
            extraction_revision="extract-v1",
            segmentation_revision="segments-v1",
            page_count=2,
            character_count=8000,
            segment_count=80,
            omitted_visual_page_numbers=(2,),
            source_receipt_id=base64.urlsafe_b64encode(b"R" * 16).decode().rstrip("="),
            segment_manifest_sha256=HASH_B,
        )
        engine = self.engine()
        ticket, expiry = engine.mint_document(
            kind="standard_document_v1",
            authority=self.standard,
            protected_sha256=HASH_B,
            salt="22" * 16,
            generation_seed=b"D" * 32,
            facts=facts,
        )
        self.assertEqual(expiry, self.now_value + 900)
        payload = engine.inspect(
            ticket, authority=self.standard, expected_kind="standard_document_v1"
        )
        self.assertEqual(payload["page_count"], 2)
        self.assertEqual(
            payload["prompt_revision"],
            "structure-protected-document-classifications-v1",
        )
        self.assertNotIn("source_text", payload)
        self.assertNotIn("mapping", payload)
        with self.assertRaises(ApprovalError):
            engine.inspect(ticket, authority=self.priority, expected_kind="standard_document_v1")
        custom_prompt_engine = ApprovalEngine(
            self.key,
            self.bindings,
            document_bindings=self.bindings,
            now=lambda: self.now_value,
            random_bytes=DeterministicBytes(),
            boot_nonce=b"B" * 16,
        )
        with self.assertRaises(ApprovalError):
            custom_prompt_engine.inspect(
                ticket,
                authority=self.standard,
                expected_kind="standard_document_v1",
            )
        for invalid in (
            replace(facts, page_count=11),
            replace(facts, character_count=8001),
            replace(facts, segment_count=81),
            replace(facts, omitted_visual_page_numbers=(3,)),
        ):
            with self.assertRaises(ApprovalError):
                engine.mint_document(
                    kind="standard_document_v1",
                    authority=self.standard,
                    protected_sha256=HASH_B,
                    salt="22" * 16,
                    generation_seed=b"D" * 32,
                    facts=invalid,
                )

    def test_every_document_ticket_branch_rejects_surrogate_smuggling(self):
        base_facts = DocumentFacts(
            source_pdf_sha256=HASH_A,
            parser_revision="parser-v1",
            extraction_revision="extract-v1",
            segmentation_revision="segments-v1",
            page_count=1,
            character_count=100,
            segment_count=2,
            omitted_visual_page_numbers=(),
            source_receipt_id=base64.urlsafe_b64encode(b"R" * 16).decode().rstrip("="),
            segment_manifest_sha256=HASH_B,
        )
        engine = self.engine()
        for kind, authority, facts in (
            ("standard_document_v1", self.standard, base_facts),
            ("invite_document_v1", self.priority, base_facts),
            (
                "synthetic_document_v1",
                self.standard,
                replace(
                    base_facts,
                    scenario_id="thai-resume-v1",
                    scenario_registry_sha256=HASH_A,
                ),
            ),
        ):
            ticket, _ = engine.mint_document(
                kind=kind,
                authority=authority,
                protected_sha256=HASH_B,
                salt="22" * 16,
                generation_seed=b"D" * 32,
                facts=facts,
            )
            payload = engine.inspect(
                ticket,
                authority=authority,
                expected_kind=kind,
            )
            payload["mode"] = "surrogate"
            payload.pop("protection_generation_seed")
            payload.pop("protection_generation_revision")
            forged = engine._encrypt(payload)
            with self.assertRaisesRegex(ApprovalError, "approval_invalid"):
                engine.inspect(
                    forged,
                    authority=authority,
                    expected_kind=kind,
                )

    def test_pg_v1_mapping_is_deterministic_and_uuid_independent(self):
        text = "A@example.com / A@example.com / 0812345678"

        def detect(_text):
            return [
                Entity((0, 13), "EMAIL", "A@example.com"),
                Entity((16, 29), "EMAIL", "A@example.com"),
                Entity((32, 42), "PHONE", "0812345678"),
            ]

        def token_factory(data_type, ordinal, *, namespace, nonce):
            return f"[{data_type}_{namespace}_{nonce}_{ordinal}]"

        first = _token_seed_mapping(
            text,
            b"G" * 32,
            detect=detect,
            cleaner=lambda value: value,
            token_factory=token_factory,
        )
        second = _token_seed_mapping(
            text,
            b"G" * 32,
            detect=detect,
            cleaner=lambda value: value,
            token_factory=token_factory,
        )
        self.assertEqual(first, second)
        self.assertEqual(list(first.values()).count("A@example.com"), 1)
        self.assertEqual(len(first), 2)
        self.assertNotEqual(
            first,
            _token_seed_mapping(
                text,
                b"H" * 32,
                detect=detect,
                cleaner=lambda value: value,
                token_factory=token_factory,
            ),
        )

    def service(self, protector=None, *, random_bytes=None):
        engine = self.engine(random_bytes=DeterministicBytes())
        return PreviewService(
            engine,
            protector=protector or FakeProtector(),
            hosted_version="3.0.1",
            now=lambda: self.now_value,
            random_bytes=random_bytes or DeterministicBytes(),
            blocked_exceptions=(Blocked,),
            uncertain_exceptions=(Uncertain,),
        )

    def test_preview_exact_dto_timing_no_raw_echo_and_no_provider(self):
        raw = "somchai@example.com"
        protector = FakeProtector()
        service = self.service(protector)
        response = service.preview_custom(
            {"text": raw, "mode": "token"}, authority=self.standard
        )
        self.assertEqual(
            set(response),
            {
                "source_kind", "scenario", "source_text", "protected_text", "mode",
                "hosted_version", "provider", "detected_entity_count",
                "entity_type_counts", "highlights", "section26_categories",
                "guard_findings", "outbound_gate", "can_execute", "protected_sha256",
                "ticket", "ticket_expires_at_unix", "queue_join_before_unix",
            },
        )
        self.assertEqual(response["source_kind"], "custom_standard")
        self.assertIsNone(response["source_text"])
        self.assertNotIn(raw, repr(response))
        self.assertEqual(response["ticket_expires_at_unix"], self.now_value + 300)
        self.assertEqual(response["queue_join_before_unix"], self.now_value + 300)
        self.assertEqual(response["outbound_gate"]["status"], "no_residual_signal_detected")
        self.assertEqual(protector.calls, 1)
        self.assertFalse(hasattr(service, "provider"))

    def test_preview_modes_limits_blocked_uncertain_and_time_floor(self):
        for mode in ("token", "surrogate"):
            response = self.service().preview_custom(
                {"text": "x", "mode": mode}, authority=self.priority
            )
            self.assertEqual(response["mode"], mode)
            self.assertEqual(response["source_kind"], "custom_invite")
        for protector, state in (
            (FakeProtector(Blocked()), "blocked"),
            (FakeProtector(Uncertain()), "uncertain"),
        ):
            response = self.service(protector).preview_custom(
                {"text": "x", "mode": "token"}, authority=self.standard
            )
            self.assertEqual(response["outbound_gate"]["status"], state)
            self.assertFalse(response["can_execute"])
            self.assertIsNone(response["ticket"])
            self.assertIsNone(response["ticket_expires_at_unix"])
            self.assertIsNone(response["queue_join_before_unix"])
        with self.assertRaisesRegex(PreviewError, "payload_too_large"):
            self.service().preview_custom(
                {"text": "x" * 20_001, "mode": "token"}, authority=self.standard
            )
        four_byte_source = "😀" * 20_000
        self.assertTrue(
            self.service().preview_custom(
                {"text": four_byte_source, "mode": "token"},
                authority=self.standard,
            )["can_execute"]
        )
        exact_provider_payload = "x" * (96 * 1024)
        self.assertTrue(
            self.service(OversizedProtectedProtector(exact_provider_payload))
            .preview_custom(
                {"text": "x", "mode": "token"},
                authority=self.standard,
            )["can_execute"]
        )
        oversized_protector = OversizedProtectedProtector(
            exact_provider_payload + "x"
        )
        with self.assertRaisesRegex(PreviewError, "provider_payload_too_large"):
            self.service(oversized_protector).preview_custom(
                {"text": "x", "mode": "token"}, authority=self.standard
            )
        self.assertEqual(oversized_protector.result.mapping, {})
        for invalid in (
            {"text": "", "mode": "token"},
            {"text": "x", "mode": "bad"},
            {"text": "x", "mode": "token", "extra": 1},
        ):
            with self.assertRaises(PreviewError):
                self.service().preview_custom(invalid, authority=self.standard)
        self.now_value = self.standard.expires_at_unix - 1029
        with self.assertRaisesRegex(PreviewError, "session_review_window"):
            self.service().preview_custom(
                {"text": "x", "mode": "token"}, authority=self.standard
            )

    def test_preview_exact_initial_premint_and_deadline_boundaries(self):
        initial_now = self.now_value
        exact_initial = replace(
            self.standard,
            expires_at_unix=initial_now + 1_030,
        )
        accepted = self.service().preview_custom(
            {"text": "x", "mode": "token"}, authority=exact_initial
        )
        self.assertEqual(accepted["queue_join_before_unix"], initial_now + 130)

        self.now_value = initial_now
        exact_premint = self.service(
            AdvancingProtector(lambda: setattr(self, "now_value", initial_now + 10))
        ).preview_custom(
            {"text": "x", "mode": "token"}, authority=exact_initial
        )
        self.assertEqual(exact_premint["queue_join_before_unix"], initial_now + 130)
        self.assertEqual(
            exact_premint["queue_join_before_unix"] - self.now_value,
            120,
        )

        self.now_value = initial_now
        with self.assertRaisesRegex(PreviewError, "session_review_window"):
            self.service(
                AdvancingProtector(
                    lambda: setattr(self, "now_value", initial_now + 11)
                )
            ).preview_custom(
                {"text": "x", "mode": "token"}, authority=exact_initial
            )

        self.now_value = initial_now
        for remaining, expected_join_before in (
            (1_301, initial_now + 300),  # ticket expiry strictly earlier
            (1_200, initial_now + 300),  # exact equality
            (1_199, initial_now + 299),  # session deadline strictly earlier
        ):
            authority = replace(
                self.standard,
                expires_at_unix=initial_now + remaining,
            )
            response = self.service().preview_custom(
                {"text": "x", "mode": "token"}, authority=authority
            )
            self.assertEqual(
                response["queue_join_before_unix"],
                expected_join_before,
            )

    def test_execute_seam_reconstructs_then_consumes_without_provider(self):
        raw = "somchai@example.com"
        service = self.service()
        preview = service.preview_custom(
            {"text": raw, "mode": "token"}, authority=self.standard
        )
        with self.assertRaises(ApprovalError):
            service.validate_and_consume_custom(
                preview["ticket"], raw + " changed", authority=self.standard
            )
        with self.assertRaises(ApprovalError):
            service.validate_and_consume_custom(
                preview["ticket"], raw, authority=self.priority
            )
        validated = service.validate_and_consume_custom(
            preview["ticket"], raw, authority=self.standard
        )
        self.assertEqual(
            hashlib.sha256(validated.protected.protected_text.encode()).hexdigest(),
            preview["protected_sha256"],
        )
        validated.clear()
        self.assertEqual(validated.protected.mapping, {})
        self.assertEqual(validated.approval, {})
        self.assertNotIn("source_sha256", repr(validated))
        with self.assertRaisesRegex(ApprovalError, "approval_consumed"):
            service.validate_and_consume_custom(
                preview["ticket"], raw, authority=self.standard
            )

    def test_single_worker_runtime_invariant_fails_closed(self):
        require_single_worker({})
        require_single_worker({"UVICORN_WORKERS": "1"})
        for value in ("2", "01", " 1", "", "invalid"):
            with self.assertRaisesRegex(RuntimeError, "UVICORN_WORKERS=1"):
                require_single_worker({"UVICORN_WORKERS": value})
        gateway = (CORE / "aift_gateway.py").read_text(encoding="utf-8")
        self.assertLess(
            gateway.index("require_single_worker()"),
            gateway.index("from app"),
        )

    def test_detector_and_model_hashes_are_bound_to_current_sources(self):
        digest = hashlib.sha256()
        for relative in PROTECTION_REVISION_FILES:
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update((CORE / relative).read_bytes())
        self.assertEqual(digest.hexdigest(), DETECTOR_CODE_SHA256)
        verifier = (ROOT / "core" / "verify_thainer_assets.py").read_text(encoding="utf-8")
        self.assertIn(DETECTOR_MODEL_SHA256, verifier)
        ai_client_path = CORE / "pii_redactor" / "ai_client.py"
        ai_client_text = ai_client_path.read_text(encoding="utf-8")
        tree = ast.parse(ai_client_text)
        prompt = None
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "DEFAULT_SYSTEM_PROMPT" for target in node.targets)
            ):
                prompt = ast.literal_eval(node.value)
                break
        self.assertEqual(prompt, DEFAULT_SYSTEM_PROMPT)
        self.assertEqual(
            PROMPT_REVISION,
            "default-v1-" + hashlib.sha256(DEFAULT_SYSTEM_PROMPT.encode()).hexdigest()[:16],
        )
        self.assertIn('MODEL = "thaillm-8b"', ai_client_text)
        self.assertIn('"tokenmind": TokenmindProvider', ai_client_text)

    def test_internal_overlay_is_strict_timed_and_provider_free(self):
        fake = FakePreviewService()
        overlay = Hosted3Overlay(
            DummyASGI(),
            environ={"AIGUARD_API_KEY": "core-key"},
            service=fake,
            now=lambda: self.now_value,
        )
        status, headers, body = asyncio.run(
            overlay_request(overlay, authority=self.standard)
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"preview": "provider-free"})
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertEqual(headers["x-aiguard-server-time-ms"], str(self.now_value * 1000))
        self.assertEqual(headers["x-aiguard-service-class"], "standard")
        self.assertEqual(len(fake.calls), 1)

        expiring = AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce="expiring-session",
            subject_id=None,
            expires_at_unix=self.now_value + 1029,
        )
        status, _headers, body = asyncio.run(
            overlay_request(
                overlay,
                authority=expiring,
                forbid_body=True,
            )
        )
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(body)["error"]["code"], "session_review_window")

    def test_internal_overlay_rejects_contract_key_schema_and_duplicate_json(self):
        overlay = Hosted3Overlay(
            DummyASGI(),
            environ={"AIGUARD_API_KEY": "core-key"},
            service=FakePreviewService(),
            now=lambda: self.now_value,
        )
        cases = (
            (
                [(b"content-type", b"application/json"), (b"x-aiguard-key", b"core-key")],
                b'{}',
                426,
                "contract_version_required",
            ),
            (
                [
                    (b"content-type", b"application/json"),
                    (b"x-aiguard-key", b"wrong"),
                    (b"x-aiguard-contract-version", b"2"),
                ],
                b'{}',
                401,
                "authentication_required",
            ),
            (
                [
                    (b"content-type", b"application/json"),
                    (b"x-aiguard-key", b"core-key"),
                    (b"x-aiguard-contract-version", b"2"),
                ],
                b'{"text":"x","text":"y","mode":"token"}',
                422,
                "request_schema_invalid",
            ),
        )
        for headers, body, expected_status, code in cases:
            with self.subTest(code=code):
                status, _response_headers, response = asyncio.run(
                    overlay_request(
                        overlay,
                        authority=self.standard,
                        body=body,
                        headers=headers,
                    )
                )
                self.assertEqual(status, expected_status)
                self.assertEqual(json.loads(response)["error"]["code"], code)


if __name__ == "__main__":
    unittest.main()

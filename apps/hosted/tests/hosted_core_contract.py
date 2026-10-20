"""Provider and internal-PDF regressions for the bounded hosted core slice.

This uses the synchronized production modules directly. Heavy detector/OCR
imports are replaced with narrow test doubles so the GitLab check job can run
the security contracts without downloading models or calling a provider.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import httpx

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
MASKED_TEXT = "synthetic immutable masked text"
SYSTEM_PROMPT = "synthetic system prompt"


def _purge_core_modules() -> None:
    for name in list(sys.modules):
        if name == "pii_redactor" or name.startswith("pii_redactor."):
            del sys.modules[name]


def _load_ai_client():
    _purge_core_modules()
    package = types.ModuleType("pii_redactor")
    package.__path__ = [str(CORE / "pii_redactor")]
    sys.modules["pii_redactor"] = package

    leak_guard = types.ModuleType("pii_redactor.leak_guard")

    class OutboundPolicyError(RuntimeError):
        pass

    leak_guard.OutboundPolicyError = OutboundPolicyError
    leak_guard.enforce_outbound_policy = lambda *_args, **_kwargs: None
    leak_guard.scan_outbound_leaks = lambda *_args, **_kwargs: []
    leak_guard.scan_residual_signals = lambda *_args, **_kwargs: []
    sys.modules[leak_guard.__name__] = leak_guard

    models = types.ModuleType("pii_redactor.models")

    class AIResponse:
        def __init__(self, **values):
            self.__dict__.update(values)

    models.AIResponse = AIResponse
    models.EntityRegistry = object
    sys.modules[models.__name__] = models

    compat = types.ModuleType("pii_redactor.openai_compat")
    compat.chat_completions_url = lambda base: base.rstrip("/") + "/chat/completions"
    compat.is_sse_response = lambda content_type: "text/event-stream" in (content_type or "")

    def extract_chat_content(payload):
        choice = payload["choices"][0]
        return choice["message"]["content"], choice["finish_reason"]

    def validate_header_value(value, *, env_name):
        if not value or not value.isascii() or value.strip() != value or "\n" in value or "\r" in value:
            raise ValueError(f"{env_name} is invalid")
        return value

    compat.extract_chat_content = extract_chat_content
    compat.validate_header_value = validate_header_value
    sys.modules[compat.__name__] = compat

    safe_errors = types.ModuleType("pii_redactor.safe_errors")
    safe_errors.discard_exception_graph = lambda _error: None
    sys.modules[safe_errors.__name__] = safe_errors

    vault = types.ModuleType("pii_redactor.session_vault")

    class SessionVault:
        pass

    class VaultTimeoutError(RuntimeError):
        pass

    vault.SessionVault = SessionVault
    vault.VaultTimeoutError = VaultTimeoutError
    sys.modules[vault.__name__] = vault

    path = CORE / "pii_redactor" / "ai_client.py"
    spec = importlib.util.spec_from_file_location("pii_redactor.ai_client", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load synchronized ai_client")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, OutboundPolicyError


def _status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://provider.invalid/v1/complete")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("synthetic status", request=request, response=response)


class HostedProviderContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ai, cls.OutboundPolicyError = _load_ai_client()

    def setUp(self):
        self.original_sleep = self.ai._sleep
        self.delays = []
        self.ai._sleep = self.delays.append

    def tearDown(self):
        self.ai._sleep = self.original_sleep

    def _provider(self, outcomes):
        ai = self.ai

        class SequenceProvider(ai.AIProvider):
            def __init__(self):
                self.calls = []

            def complete(self, system, user, *, timeout=30.0):
                self.calls.append((system, user, timeout))
                outcome = outcomes[len(self.calls) - 1]
                if isinstance(outcome, BaseException):
                    raise outcome
                return outcome

        return SequenceProvider()

    def test_tokenmind_complete_is_exactly_one_network_request(self):
        for failure in (
            httpx.Response(429),
            httpx.Response(503),
            httpx.ReadTimeout("synthetic timeout"),
        ):
            with self.subTest(failure=type(failure).__name__):
                calls = []

                def handler(request):
                    calls.append(request)
                    if isinstance(failure, BaseException):
                        raise failure
                    return failure

                with mock.patch.dict(
                    os.environ,
                    {
                        "TOKENMIND_BASE_URL": "https://tokenmind.invalid/v1",
                        "TOKENMIND_API_KEY": "synthetic-key",
                    },
                    clear=False,
                ):
                    provider = self.ai.TokenmindProvider()
                provider._client = lambda: httpx.Client(transport=httpx.MockTransport(handler))
                with self.assertRaises(httpx.HTTPError):
                    provider.complete("system", MASKED_TEXT)
                self.assertEqual(len(calls), 1)

    def test_successful_first_attempt_roundtrip_path_calls_provider_once(self):
        provider = self._provider([MASKED_TEXT])
        checks = []

        response, _latency, attempts = self.ai.complete_provider_with_retry_policy(
            provider,
            SYSTEM_PROMPT,
            MASKED_TEXT,
            before_attempt=checks.append,
        )

        self.assertEqual((response, attempts), (MASKED_TEXT, 1))
        self.assertEqual(checks, [0])
        self.assertEqual(provider.calls, [(SYSTEM_PROMPT, MASKED_TEXT, 60.0)])
        self.assertEqual(self.delays, [])

        server = (CORE / "app" / "server.py").read_text(encoding="utf-8")
        roundtrip_path = server[server.index("def roundtrip(") : server.index("def guard(")]
        self.assertEqual(roundtrip_path.count("complete_provider_with_retry_policy("), 1)
        self.assertIn("before_attempt=validate_provider_attempt", roundtrip_path)
        self.assertNotIn("provider.complete(", roundtrip_path)

    def test_initial_outbound_validation_rejection_calls_provider_zero_times(self):
        provider = self._provider([MASKED_TEXT])
        checks = []

        def reject_before_provider(attempt):
            checks.append(attempt)
            raise self.OutboundPolicyError("fixed pre-provider policy rejection")

        with self.assertRaises(self.OutboundPolicyError):
            self.ai.complete_provider_with_retry_policy(
                provider,
                SYSTEM_PROMPT,
                MASKED_TEXT,
                before_attempt=reject_before_provider,
            )

        self.assertEqual(checks, [0])
        self.assertEqual(provider.calls, [])
        self.assertEqual(self.delays, [])

    def test_shared_orchestration_owns_three_attempts_and_fresh_scans(self):
        transient = (
            httpx.ReadTimeout("synthetic timeout"),
            httpx.ConnectError("synthetic network"),
            _status_error(429),
            _status_error(500),
        )
        for failure in transient:
            with self.subTest(failure=type(failure).__name__):
                provider = self._provider([failure, failure, MASKED_TEXT])
                checks = []
                response, _latency, attempts = self.ai.complete_provider_with_retry_policy(
                    provider,
                    SYSTEM_PROMPT,
                    MASKED_TEXT,
                    before_attempt=checks.append,
                    max_attempts=99,
                )
                self.assertEqual((response, attempts), (MASKED_TEXT, 3))
                self.assertEqual(checks, [0, 1, 2])
                self.assertEqual(self.delays[-2:], [1, 2])
                self.assertEqual(len(provider.calls), 3)
                self.assertTrue(all(call == (SYSTEM_PROMPT, MASKED_TEXT, 60.0) for call in provider.calls))

    def test_nontransient_failures_are_single_attempt_and_value_free(self):
        marker = "SYNTHETIC-PROVIDER-BODY-MUST-NOT-ESCAPE"
        failures = (
            _status_error(400),
            self.ai.ProviderProtocolError(marker),
            RuntimeError(marker),
            b"not text",
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                provider = self._provider([failure])
                with self.assertRaises(self.ai.ProviderCallError) as raised:
                    self.ai.complete_provider_with_retry_policy(
                        provider,
                        SYSTEM_PROMPT,
                        MASKED_TEXT,
                        before_attempt=lambda _attempt: None,
                    )
                self.assertEqual(len(provider.calls), 1)
                self.assertNotIn(marker, str(raised.exception))

    def test_retry_is_blocked_by_fresh_outbound_policy(self):
        provider = self._provider([_status_error(503), MASKED_TEXT])
        checks = []

        def before_attempt(attempt):
            checks.append(attempt)
            if attempt == 1:
                raise self.OutboundPolicyError("fixed policy failure")

        with self.assertRaises(self.OutboundPolicyError):
            self.ai.complete_provider_with_retry_policy(
                provider, SYSTEM_PROMPT, MASKED_TEXT, before_attempt=before_attempt
            )
        self.assertEqual(checks, [0, 1])
        self.assertEqual(len(provider.calls), 1)

    def test_hosted_allowlist_is_tokenmind_only_without_fallback(self):
        factories = self.ai.get_provider_factories(allowed=["tokenmind"])
        self.assertEqual(set(factories), {"tokenmind"})
        with self.assertRaises(ValueError):
            self.ai.get_provider_factories(allowed=["missing-provider"])
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn('AIGUARD_PROVIDERS: "tokenmind"', compose)
        self.assertNotIn('AIGUARD_PROVIDERS: "tokenmind,', compose)
        server = (CORE / "app" / "server.py").read_text(encoding="utf-8")
        self.assertIn("get_provider_factories(\n    allowed=", server)
        self.assertNotIn("provider_fallback", server)


def _load_pdf_modules():
    _purge_core_modules()
    if str(CORE) not in sys.path:
        sys.path.insert(0, str(CORE))

    pdfium = types.ModuleType("pypdfium2")

    class FakeDocument:
        def __init__(self, _path):
            self.closed = False

        def __len__(self):
            return 1

        def close(self):
            self.closed = True

    pdfium.PdfDocument = FakeDocument
    sys.modules["pypdfium2"] = pdfium

    pil = types.ModuleType("PIL")
    pil_image = types.ModuleType("PIL.Image")
    pil_image.ADAPTIVE = 0
    pil_image.new = lambda *_args, **_kwargs: None
    pil_draw = types.ModuleType("PIL.ImageDraw")
    pil_draw.Draw = lambda _image: None
    pil.Image = pil_image
    pil.ImageDraw = pil_draw
    sys.modules["PIL"] = pil
    sys.modules["PIL.Image"] = pil_image
    sys.modules["PIL.ImageDraw"] = pil_draw
    models = importlib.import_module("pii_redactor.models")
    redactor = importlib.import_module("pii_redactor.redactor")
    return models, redactor


class InternalPdfProvenanceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models, cls.redactor = _load_pdf_modules()

    def entity(self, start, text="synthetic-marker", entity_id="synthetic"):
        return self.models.Entity(
            entity_id=entity_id,
            redact_type="TB",
            data_type="NAME",
            span=(start, start + len(text)),
            score=1.0,
            original_text=text,
        )

    def registry(self, *entities):
        return self.models.EntityRegistry(list(entities), 0, len(entities))

    def box(self, text, page, x, span):
        return self.models.WordBbox(text, page, x, 72.0, max(12.0, len(text) * 6.0), 12.0, span)

    def mapped_x(self, registry, boxes):
        return [[box.x for box in row] for row in self.redactor._map_entities_to_boxes(registry, boxes)]

    def test_repeated_values_and_pages_use_authoritative_intervals(self):
        text = "synthetic-marker"
        gap = len(text) + 2
        boxes = [
            self.box(text, 1, 10, (0, len(text))),
            self.box(text, 2, 210, (gap, gap + len(text))),
        ]
        self.assertEqual(self.mapped_x(self.registry(self.entity(0)), boxes), [[10]])
        self.assertEqual(self.mapped_x(self.registry(self.entity(gap)), boxes), [[210]])

    def test_multifragment_and_thai_unicode_intervals_map_exactly(self):
        fragments = [
            self.box("alpha", 1, 10, (0, 5)),
            self.box("beta", 1, 60, (6, 10)),
        ]
        self.assertEqual(
            self.mapped_x(self.registry(self.entity(0, "alpha\nbeta")), fragments),
            [[10, 60]],
        )
        thai = "ก\u0e49า"
        self.assertEqual(
            self.mapped_x(
                self.registry(self.entity(0, thai)),
                [self.box(thai, 1, 10, (0, len(thai)))],
            ),
            [[10]],
        )

    def test_missing_or_conflicting_provenance_fails_closed_before_output(self):
        text = "synthetic-marker"
        with self.assertRaises(self.redactor.PdfSourceMappingError):
            self.mapped_x(
                self.registry(self.entity(0)),
                [self.box(text, 1, 10, None)],
            )
        with self.assertRaises(self.redactor.PdfSourceMappingError):
            self.mapped_x(
                self.registry(self.entity(0)),
                [
                    self.box(text, 1, 10, (0, len(text))),
                    self.box(text, 2, 20, (0, len(text))),
                ],
            )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "must-not-exist.pdf"
            with self.assertRaises(self.redactor.PdfSourceMappingError) as raised:
                self.redactor.redact_pdf(
                    "synthetic-input.pdf",
                    self.registry(self.entity(0)),
                    [self.box(text, 1, 10, None)],
                    str(output),
                )
            self.assertFalse(output.exists())
            self.assertNotIn(text, str(raised.exception))

    def test_extractors_record_intervals_and_flattening_is_unchanged(self):
        extractor = (CORE / "pii_redactor" / "ingest" / "text_extractor.py").read_text(
            encoding="utf-8"
        )
        redactor = (CORE / "pii_redactor" / "redactor.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(extractor.count("source_span="), 4)
        self.assertIn('_PDF_PAGE_SEPARATOR = "\\n\\n"', extractor)
        self.assertIn('.convert("P", palette=Image.ADAPTIVE)', redactor)
        self.assertIn('"PDF",\n        save_all=True,', redactor)


if __name__ == "__main__":
    unittest.main(verbosity=2)

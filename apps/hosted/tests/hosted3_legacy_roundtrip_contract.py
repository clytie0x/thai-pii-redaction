#!/usr/bin/env python3
"""Stage 4B3 legacy `/roundtrip` shared-scheduler contract."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(os.environ.get("AIGUARD_HOSTED3_RUNTIME_ROOT", ROOT / "core"))
sys.path.insert(0, str(RUNTIME_ROOT))

from aift_hosted3.approval import ApprovalBindings, ApprovalEngine  # noqa: E402
from aift_hosted3.authority import AuthorityContext  # noqa: E402
from aift_hosted3.legacy_roundtrip import (  # noqa: E402
    LEGACY_ROUNDTRIP_PATH,
    install_legacy_roundtrip_admission,
    legacy_roundtrip_authority,
)
from aift_hosted3.provider_queue import (  # noqa: E402
    LEGACY_ROUNDTRIP_WAIT_SECONDS,
    LegacyQueueExecution,
    ProviderQueue,
)


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


class Entropy:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def __call__(self, size: int) -> bytes:
        with self.lock:
            self.value += 1
            seed = self.value
        output = b""
        while len(output) < size:
            output += hashlib.sha256(
                f"legacy:{seed}:{len(output)}".encode("ascii")
            ).digest()
        return output[:size]


class LegacyHarness:
    def __init__(self):
        self.now = int(time.time())
        self.entropy = Entropy()
        bindings = ApprovalBindings(
            provider_id="tokenmind",
            provider_model="thaillm-8b",
            prompt_revision="pg-v1",
            detector_code_sha256="1" * 64,
            detector_model_sha256="2" * 64,
        )
        self.approval = ApprovalEngine(
            b"A" * 32,
            bindings,
            document_bindings=bindings,
            now=lambda: float(self.now),
            random_bytes=self.entropy,
            boot_nonce=b"B" * 16,
        )
        self.queue = ProviderQueue(
            b"Q" * 32,
            self.approval,
            now=lambda: float(self.now),
            random_bytes=self.entropy,
            boot_nonce=b"C" * 16,
        )

    def priority(self, index: int, *, remaining: int = 1_800) -> AuthorityContext:
        return AuthorityContext(
            scope="priority_invite",
            service_class="priority",
            session_nonce=b64((100 + index).to_bytes(16, "big")),
            subject_id="sub_" + b64((200 + index).to_bytes(16, "big")),
            expires_at_unix=self.now + remaining,
        )

    def standard(self, index: int) -> AuthorityContext:
        return AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce=b64(index.to_bytes(16, "big")),
            subject_id=None,
            expires_at_unix=self.now + 1_800,
        )

    def ticket(self, authority: AuthorityContext) -> str:
        return self.approval.mint_custom(
            authority=authority,
            mode="token",
            source_sha256="3" * 64,
            protected_sha256="4" * 64,
            salt="5" * 32,
            generation_seed=b"G" * 32,
        )[0]


class LegacySchedulerTests(unittest.TestCase):
    def setUp(self):
        self.h = LegacyHarness()

    def test_free_slot_admits_priority_and_finish_releases_content_free_record(self):
        authority = self.h.priority(1)
        execution = self.h.queue.admit_legacy_roundtrip(
            authority=authority,
            wait_seconds=0,
        )
        self.assertIsInstance(execution, LegacyQueueExecution)
        self.assertEqual(self.h.queue.status(authority=authority)["state"], "running")
        self.h.queue.finish_legacy_roundtrip(execution, succeeded=True)
        status = self.h.queue.status(authority=authority)
        self.assertEqual(status["state"], "complete")
        snapshot = self.h.queue.snapshot()
        self.assertEqual(snapshot[0]["service_class"], "priority")
        self.assertEqual(snapshot[0]["provider_attempt_count"], 0)
        serialized = repr(snapshot)
        self.assertNotIn("queue_capability", serialized)
        self.assertNotIn("approval", serialized)

    def test_two_busy_slots_make_legacy_timeout_without_provider_admission(self):
        first = self.h.queue.admit_legacy_roundtrip(
            authority=self.h.priority(1), wait_seconds=0
        )
        second = self.h.queue.admit_legacy_roundtrip(
            authority=self.h.priority(2), wait_seconds=0
        )
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        started = time.monotonic()
        denied = self.h.queue.admit_legacy_roundtrip(
            authority=self.h.priority(3), wait_seconds=0.05
        )
        self.assertIsNone(denied)
        self.assertGreaterEqual(time.monotonic() - started, 0.045)
        states = [row["state"] for row in self.h.queue.snapshot()]
        self.assertEqual(states.count("running"), 2)
        self.assertEqual(states.count("expired"), 1)
        self.h.queue.finish_legacy_roundtrip(first, succeeded=True)
        self.h.queue.finish_legacy_roundtrip(second, succeeded=True)

    def test_owner_and_expiry_rejections_do_not_preempt_active_work(self):
        authority = self.h.priority(1)
        execution = self.h.queue.admit_legacy_roundtrip(
            authority=authority, wait_seconds=0
        )
        self.assertIsNotNone(execution)
        self.assertIsNone(
            self.h.queue.admit_legacy_roundtrip(
                authority=authority,
                wait_seconds=0,
            )
        )
        self.assertIsNone(
            self.h.queue.admit_legacy_roundtrip(
                authority=self.h.priority(2, remaining=209),
                wait_seconds=0,
            )
        )
        self.h.queue.finish_legacy_roundtrip(execution, succeeded=False)

    def test_same_priority_subject_cannot_open_a_second_legacy_lease(self):
        first_authority = self.h.priority(1)
        second_authority = AuthorityContext(
            scope="priority_invite",
            service_class="priority",
            session_nonce=b64((999).to_bytes(16, "big")),
            subject_id=first_authority.subject_id,
            expires_at_unix=first_authority.expires_at_unix,
        )
        execution = self.h.queue.admit_legacy_roundtrip(
            authority=first_authority,
            wait_seconds=0,
        )
        self.assertIsNotNone(execution)
        self.assertIsNone(
            self.h.queue.admit_legacy_roundtrip(
                authority=second_authority,
                wait_seconds=0,
            )
        )
        self.h.queue.finish_legacy_roundtrip(execution, succeeded=True)

    def test_cancelled_waiter_leaves_no_eligible_record_or_slot(self):
        first = self.h.queue.admit_legacy_roundtrip(
            authority=self.h.priority(1), wait_seconds=0
        )
        second = self.h.queue.admit_legacy_roundtrip(
            authority=self.h.priority(2), wait_seconds=0
        )
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertIsNone(
            self.h.queue.admit_legacy_roundtrip(
                authority=self.h.priority(3),
                wait_seconds=1,
                cancelled=lambda: True,
            )
        )
        states = [row["state"] for row in self.h.queue.snapshot()]
        self.assertEqual(states.count("running"), 2)
        self.assertEqual(states.count("cancelled"), 1)
        self.assertFalse(self.h.queue._eligible)
        self.h.queue.finish_legacy_roundtrip(first, succeeded=True)
        self.h.queue.finish_legacy_roundtrip(second, succeeded=True)

    def test_running_legacy_provider_work_outlives_its_admission_deadline(self):
        authority = self.h.priority(1)
        execution = self.h.queue.admit_legacy_roundtrip(
            authority=authority,
            wait_seconds=0,
        )
        self.assertIsNotNone(execution)
        self.h.now += 10
        self.assertEqual(self.h.queue.status(authority=authority)["state"], "running")
        self.assertIsNone(
            self.h.queue.admit_legacy_roundtrip(
                authority=authority,
                wait_seconds=0,
            )
        )
        self.h.queue.finish_legacy_roundtrip(execution, succeeded=True)

    def test_legacy_priority_participates_in_shared_weighted_grants(self):
        occupied = [
            self.h.queue.admit_legacy_roundtrip(
                authority=self.h.priority(index), wait_seconds=0
            )
            for index in (1, 2)
        ]
        standard = self.h.standard(1)
        joined = self.h.queue.join(self.h.ticket(standard), authority=standard)
        standard_result = []
        priority_result = []

        def wait_standard():
            standard_result.append(
                self.h.queue.claim(
                    joined["queue_capability"],
                    last_revision=0,
                    authority=standard,
                    wait_seconds=1,
                )
            )

        def wait_priority():
            priority_result.append(
                self.h.queue.admit_legacy_roundtrip(
                    authority=self.h.priority(3),
                    wait_seconds=1,
                )
            )

        standard_thread = threading.Thread(target=wait_standard)
        priority_thread = threading.Thread(target=wait_priority)
        standard_thread.start()
        priority_thread.start()
        deadline = time.monotonic() + 1
        while len(self.h.queue._eligible) < 2:  # exact white-box scheduler seam
            if time.monotonic() >= deadline:
                self.fail("both shared-scheduler contenders did not become eligible")
            time.sleep(0.005)
        self.h.queue.finish_legacy_roundtrip(occupied[0], succeeded=True)
        priority_thread.join(1)
        self.assertFalse(priority_thread.is_alive())
        self.assertIsInstance(priority_result[0], LegacyQueueExecution)
        self.assertEqual(standard_result, [])
        self.h.queue.finish_legacy_roundtrip(occupied[1], succeeded=True)
        standard_thread.join(1)
        self.assertFalse(standard_thread.is_alive())
        self.assertEqual(standard_result[0]["state"], "claim_ready")
        self.h.queue.finish_legacy_roundtrip(priority_result[0], succeeded=True)


class FakeContractError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class FakeQueue:
    def __init__(self):
        self.admitted = LegacyQueueExecution("queue", 0, 2)
        self.authorities = []
        self.finishes = []

    def admit_legacy_roundtrip(self, *, authority):
        self.authorities.append(authority)
        return self.admitted

    def finish_legacy_roundtrip(self, execution, *, succeeded):
        self.finishes.append((execution, succeeded))


class FakeProviderQueue(FakeQueue, ProviderQueue):
    """Satisfy the installer type fence without constructing queue internals."""


class LegacyRouteInstallerTests(unittest.TestCase):
    def setUp(self):
        self.original_http_v2 = sys.modules.get("app.http_v2")
        self.original_server = sys.modules.get("app.server")
        app_package = sys.modules.setdefault("app", types.ModuleType("app"))
        http_v2 = types.ModuleType("app.http_v2")
        http_v2.ContractError = FakeContractError
        sys.modules["app.http_v2"] = http_v2
        app_package.http_v2 = http_v2
        server = types.ModuleType("app.server")
        server._PROVIDER_FACTORIES = {"tokenmind": object()}

        def validate_text(text):
            if not text or not text.strip():
                raise FakeContractError("invalid_request")
            if len(text) > 8:
                raise FakeContractError("payload_too_large")

        server._validate_text_input = validate_text
        sys.modules["app.server"] = server
        app_package.server = server

    def tearDown(self):
        if self.original_http_v2 is None:
            sys.modules.pop("app.http_v2", None)
        else:
            sys.modules["app.http_v2"] = self.original_http_v2
        if self.original_server is None:
            sys.modules.pop("app.server", None)
        else:
            sys.modules["app.server"] = self.original_server

    def test_wrapper_preserves_result_and_releases_on_success_or_failure(self):
        def endpoint(request):
            if request.text == "explode":
                raise RuntimeError("provider failed")
            return {"exact": request.text}

        route = SimpleNamespace(
            path=LEGACY_ROUNDTRIP_PATH,
            methods={"POST"},
            dependant=SimpleNamespace(call=endpoint),
        )
        app = SimpleNamespace(routes=[route], state=SimpleNamespace())
        queue = object.__new__(FakeProviderQueue)
        FakeQueue.__init__(queue)
        install_legacy_roundtrip_admission(app, queue)
        authority = LegacyHarness().priority(9)
        with legacy_roundtrip_authority(authority):
            self.assertEqual(
                route.dependant.call(
                    SimpleNamespace(text="bytes", mode="token", provider="tokenmind")
                ),
                {"exact": "bytes"},
            )
            with self.assertRaisesRegex(RuntimeError, "provider failed"):
                route.dependant.call(
                    SimpleNamespace(text="explode", mode="token", provider="tokenmind")
                )
        self.assertEqual(queue.authorities, [authority, authority])
        self.assertEqual(queue.finishes[0], (queue.admitted, True))
        self.assertEqual(queue.finishes[1], (queue.admitted, False))
        with self.assertRaisesRegex(RuntimeError, "installed twice"):
            install_legacy_roundtrip_admission(app, queue)

    def test_wrapper_releases_once_when_the_endpoint_is_cancelled(self):
        def endpoint(_request):
            raise asyncio.CancelledError()

        route = SimpleNamespace(
            path=LEGACY_ROUNDTRIP_PATH,
            methods={"POST"},
            dependant=SimpleNamespace(call=endpoint),
        )
        app = SimpleNamespace(routes=[route], state=SimpleNamespace())
        queue = object.__new__(FakeProviderQueue)
        FakeQueue.__init__(queue)
        install_legacy_roundtrip_admission(app, queue)
        with legacy_roundtrip_authority(LegacyHarness().priority(1)):
            with self.assertRaises(asyncio.CancelledError):
                route.dependant.call(
                    SimpleNamespace(text="valid", mode="token", provider="tokenmind")
                )
        self.assertEqual(queue.finishes, [(queue.admitted, False)])

    def test_semantic_validation_precedes_admission_and_keeps_exact_error_codes(self):
        route = SimpleNamespace(
            path=LEGACY_ROUNDTRIP_PATH,
            methods={"POST"},
            dependant=SimpleNamespace(call=lambda request: request),
        )
        app = SimpleNamespace(routes=[route], state=SimpleNamespace())
        queue = object.__new__(FakeProviderQueue)
        FakeQueue.__init__(queue)
        install_legacy_roundtrip_admission(app, queue)
        cases = (
            (SimpleNamespace(text="", mode="token", provider="tokenmind"), "invalid_request"),
            (SimpleNamespace(text="  ", mode="token", provider="tokenmind"), "invalid_request"),
            (SimpleNamespace(text="overflow!", mode="token", provider="tokenmind"), "payload_too_large"),
            (SimpleNamespace(text="valid", mode="invalid", provider="tokenmind"), "invalid_request"),
            (SimpleNamespace(text="valid", mode="token", provider="unknown"), "invalid_request"),
        )
        with legacy_roundtrip_authority(LegacyHarness().priority(1)):
            for request, code in cases:
                with self.assertRaises(FakeContractError) as failure:
                    route.dependant.call(request)
                self.assertEqual(failure.exception.code, code)
        self.assertEqual(queue.authorities, [])
        self.assertEqual(queue.finishes, [])

    def test_wrapper_uses_exact_vendored_auth_and_rate_error_codes(self):
        route = SimpleNamespace(
            path=LEGACY_ROUNDTRIP_PATH,
            methods={"POST"},
            dependant=SimpleNamespace(call=lambda request: request),
        )
        app = SimpleNamespace(routes=[route], state=SimpleNamespace())
        queue = object.__new__(FakeProviderQueue)
        FakeQueue.__init__(queue)
        install_legacy_roundtrip_admission(app, queue)
        request = SimpleNamespace(text="valid", mode="token", provider="tokenmind")
        with self.assertRaises(FakeContractError) as missing:
            route.dependant.call(request)
        self.assertEqual(missing.exception.code, "authentication_required")
        with legacy_roundtrip_authority(LegacyHarness().standard(1)):
            with self.assertRaises(FakeContractError) as standard:
                route.dependant.call(request)
        self.assertEqual(standard.exception.code, "control_forbidden")
        queue.admitted = None
        with legacy_roundtrip_authority(LegacyHarness().priority(1)):
            with self.assertRaises(FakeContractError) as full:
                route.dependant.call(request)
        self.assertEqual(full.exception.code, "rate_limited")


class SourceWiringTests(unittest.TestCase):
    def test_gateway_installs_one_shared_queue_without_vendored_edits(self):
        gateway = (RUNTIME_ROOT / "aift_gateway.py").read_text(encoding="utf-8")
        overlay = (RUNTIME_ROOT / "aift_hosted3" / "overlay.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("install_legacy_roundtrip_admission", gateway)
        self.assertIn("hosted3_overlay.provider_queue", gateway)
        self.assertIn("LEGACY_ROUNDTRIP_PATH", overlay)
        self.assertEqual(LEGACY_ROUNDTRIP_WAIT_SECONDS, 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

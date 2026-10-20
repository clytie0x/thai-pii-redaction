#!/usr/bin/env python3
"""Stage 4B1 internal queue HTTP and disconnect contract."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(os.environ.get("AIGUARD_HOSTED3_RUNTIME_ROOT", ROOT / "core"))
sys.path.insert(0, str(RUNTIME_ROOT))

from aift_hosted3.approval import ApprovalBindings, ApprovalEngine  # noqa: E402
from aift_hosted3.authority import AuthorityContext  # noqa: E402
import aift_hosted3.overlay as overlay_module  # noqa: E402
from aift_hosted3.overlay import (  # noqa: E402
    MAX_QUEUE_BODY_BYTES,
    QUEUE_CANCEL_PATH,
    QUEUE_CLAIM_PATH,
    QUEUE_JOIN_PATH,
    QUEUE_STATUS_PATH,
    Hosted3Overlay,
)
from aift_hosted3.provider_queue import (  # noqa: E402
    CLAIM_HTTP_ACK_TTL_SECONDS,
    ProviderQueue,
    ProviderQueueError,
)


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


class Clock:
    def __init__(self, value: int = 2_100_000_000):
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
            output += hashlib.sha256(f"queue-http:{value}:{len(output)}".encode()).digest()
        return output[:size]


class DummyPreview:
    def preview_custom(self, _request, *, authority):
        raise AssertionError(f"preview service must not run for {authority.service_class}")


class DummyASGI:
    async def __call__(self, _scope, _receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b""})


class DeadlineRaceQueue:
    """Force disconnect cleanup to race with a terminal scheduler error."""

    def __init__(self):
        self.wakes = 0

    def claim(self, _capability, *, cancelled, **_kwargs):
        deadline = time.monotonic() + 2
        while not cancelled():
            if time.monotonic() >= deadline:
                raise AssertionError("disconnect signal did not reach claim worker")
            time.sleep(0.001)
        raise ProviderQueueError("queue_expired")

    def wake_claims(self):
        self.wakes += 1


class QueueHttpHarness:
    def __init__(self):
        self.clock = Clock()
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
        self.app = Hosted3Overlay(
            DummyASGI(),
            environ={"AIGUARD_API_KEY": "core-key"},
            service=DummyPreview(),
            queue=self.queue,
            now=self.clock,
        )

    def authority(self, index: int, *, remaining: int = 1_800):
        return AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce=b64(index.to_bytes(16, "big")),
            subject_id=None,
            expires_at_unix=self.clock.value + remaining,
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


async def request(
    app,
    path,
    authority,
    *,
    method=None,
    payload=None,
    body=None,
    headers=None,
    query=b"",
    forbid_body=False,
    disconnect_when=None,
):
    if body is None:
        body = (
            json.dumps(payload, separators=(",", ":")).encode()
            if payload is not None
            else b""
        )
    if method is None:
        method = "GET" if path == QUEUE_STATUS_PATH else "POST"
    if headers is None:
        headers = [
            (b"x-aiguard-key", b"core-key"),
            (b"x-aiguard-contract-version", b"2"),
            (b"content-length", str(len(body)).encode()),
        ]
        if method != "GET":
            headers.append((b"content-type", b"application/json"))
    sent = []
    delivered = False
    wait_forever = asyncio.Event()

    async def receive():
        nonlocal delivered
        if forbid_body:
            raise AssertionError("request body was read before the fixed admission gate")
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        if disconnect_when is not None:
            deadline = time.monotonic() + 2
            while not disconnect_when():
                if time.monotonic() >= deadline:
                    raise AssertionError("claim never became eligible before disconnect")
                await asyncio.sleep(0.005)
            return {"type": "http.disconnect"}
        await wait_forever.wait()
        raise AssertionError("unreachable")

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query,
        "headers": headers,
        "state": {"aiguard_authority": authority} if authority is not None else {},
    }
    await app(scope, receive, send)
    if not sent:
        return None, {}, None, sent
    start = next(row for row in sent if row["type"] == "http.response.start")
    response_headers = {
        key.decode().lower(): value.decode() for key, value in start["headers"]
    }
    raw = b"".join(
        row.get("body", b"") for row in sent if row["type"] == "http.response.body"
    )
    parsed = json.loads(raw) if raw else None
    return start["status"], response_headers, parsed, sent


class QueueHttpTests(unittest.TestCase):
    def setUp(self):
        self.h = QueueHttpHarness()

    def test_join_status_claim_cancel_are_exact_no_store_and_not_preview_gated(self):
        authority = self.h.authority(1, remaining=1_000)
        ticket = self.h.ticket(authority)
        status, headers, joined, _ = asyncio.run(
            request(
                self.h.app,
                QUEUE_JOIN_PATH,
                authority,
                payload={"ticket": ticket},
            )
        )
        self.assertEqual(status, 201)
        self.assertEqual(
            set(joined),
            {
                "state",
                "position",
                "queue_expires_at_unix",
                "poll_after_ms",
                "queue_capability",
            },
        )
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertEqual(headers["x-aiguard-service-class"], "standard")
        self.assertEqual(
            headers["x-aiguard-session-expires-at-ms"],
            str(authority.expires_at_unix * 1000),
        )

        before = self.h.queue.snapshot()
        status, _headers, current, _ = asyncio.run(
            request(self.h.app, QUEUE_STATUS_PATH, authority)
        )
        self.assertEqual(status, 200)
        self.assertEqual(current["state"], "queued")
        self.assertNotIn("queue_capability", current)
        self.assertEqual(self.h.queue.snapshot(), before)

        status, _headers, claimed, _ = asyncio.run(
            request(
                self.h.app,
                QUEUE_CLAIM_PATH,
                authority,
                payload={
                    "queue_capability": joined["queue_capability"],
                    "last_revision": 0,
                },
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            set(claimed),
            {
                "state",
                "revision",
                "claim_token",
                "claim_expires_at_unix",
                "claim_window_seconds",
                "queue_expires_at_unix",
            },
        )
        self.assertEqual(claimed["state"], "claim_ready")
        self.assertEqual(
            claimed["claim_expires_at_unix"],
            self.h.clock.value + CLAIM_HTTP_ACK_TTL_SECONDS,
        )
        self.assertEqual(
            claimed["claim_window_seconds"], CLAIM_HTTP_ACK_TTL_SECONDS
        )
        claimed_record = next(iter(self.h.queue._records.values()))
        self.assertTrue(claimed_record.claim_acknowledgement_pending)
        self.assertEqual(
            claimed_record.claim_expires_at_unix,
            claimed["claim_expires_at_unix"],
        )

        status, headers, body, _ = asyncio.run(
            request(self.h.app, QUEUE_CANCEL_PATH, authority, payload={})
        )
        self.assertEqual((status, body), (204, None))
        self.assertEqual(headers["content-length"], "0")
        self.assertNotIn("content-type", headers)
        status, _headers, current, _ = asyncio.run(
            request(self.h.app, QUEUE_STATUS_PATH, authority)
        )
        self.assertEqual((status, current["state"], current["reason"]), (200, "cancelled", "cancelled"))

    def test_fractional_grant_and_full_send_budget_retain_fifteen_seconds(self):
        authority = self.h.authority(1)
        joined = self.h.queue.join(self.h.ticket(authority), authority=authority)
        self.h.clock.value += 0.999
        original_json = self.h.app._json

        async def delayed_complete_json(send, status, payload, *, authority):
            await original_json(send, status, payload, authority=authority)
            self.h.clock.value += 5
            self.h.queue.tick()

        self.h.app._json = delayed_complete_json
        status, _headers, claimed, sent = asyncio.run(
            request(
                self.h.app,
                QUEUE_CLAIM_PATH,
                authority,
                payload={
                    "queue_capability": joined["queue_capability"],
                    "last_revision": 0,
                },
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual([message["type"] for message in sent], [
            "http.response.start",
            "http.response.body",
        ])
        self.assertEqual(claimed["state"], "claim_ready")
        self.assertEqual(claimed["claim_window_seconds"], CLAIM_HTTP_ACK_TTL_SECONDS)
        record = next(iter(self.h.queue._records.values()))
        self.assertTrue(record.claim_acknowledgement_pending)
        self.assertEqual(record.claim_expires_at_unix, claimed["claim_expires_at_unix"])
        self.assertAlmostEqual(
            claimed["claim_expires_at_unix"] - self.h.clock.value,
            15.001,
            places=6,
        )
        self.assertGreaterEqual(
            claimed["claim_expires_at_unix"] - self.h.clock.value,
            15,
        )
        self.h.clock.value = claimed["claim_expires_at_unix"] - 0.001
        execution = self.h.queue.begin_execute(
            joined["queue_capability"],
            claimed["claim_token"],
            authority=authority,
        )
        self.h.queue.finish(execution, succeeded=True, attempt_count=1)
        execution.clear()

    def test_connected_no_slot_timeout_returns_queued_without_claim_ack(self):
        blockers = []
        for index in (1, 2):
            authority = self.h.authority(index)
            joined = self.h.queue.join(self.h.ticket(authority), authority=authority)
            claim = self.h.queue.claim(
                joined["queue_capability"],
                last_revision=0,
                authority=authority,
                wait_seconds=0,
            )
            blockers.append(
                self.h.queue.begin_execute(
                    joined["queue_capability"], claim["claim_token"], authority=authority
                )
            )

        waiting = self.h.authority(3)
        joined = self.h.queue.join(self.h.ticket(waiting), authority=waiting)
        original_claim = self.h.queue.claim

        def immediate_claim(capability, **kwargs):
            kwargs["wait_seconds"] = 0
            return original_claim(capability, **kwargs)

        self.h.queue.claim = immediate_claim

        status, _headers, body, sent = asyncio.run(
            request(
                self.h.app,
                QUEUE_CLAIM_PATH,
                waiting,
                payload={
                    "queue_capability": joined["queue_capability"],
                    "last_revision": 0,
                },
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "queued")
        self.assertIsNone(body["claim_token"])
        self.assertEqual([message["type"] for message in sent], [
            "http.response.start",
            "http.response.body",
        ])
        waiting_record = next(
            row for row in self.h.queue._records.values()
            if row.state == "queued"
        )
        self.assertFalse(waiting_record.claim_acknowledgement_pending)
        self.assertEqual(waiting_record.claim_miss_count, 0)
        self.assertIsNone(waiting_record.slot)

        for execution in blockers:
            self.h.queue.finish(execution, succeeded=True, attempt_count=1)
            execution.clear()

    def test_claim_response_send_timeout_abandons_without_a_second_response(self):
        authority = self.h.authority(1)
        joined = self.h.queue.join(self.h.ticket(authority), authority=authority)
        raw = json.dumps(
            {
                "queue_capability": joined["queue_capability"],
                "last_revision": 0,
            },
            separators=(",", ":"),
        ).encode()
        delivered = False
        receive_block = asyncio.Event()
        send_block = asyncio.Event()
        sent = []

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            await receive_block.wait()
            raise AssertionError("unreachable")

        async def blocked_body_send(message):
            sent.append(message)
            if message["type"] == "http.response.body":
                await send_block.wait()

        scope = {
            "type": "http",
            "method": "POST",
            "path": QUEUE_CLAIM_PATH,
            "query_string": b"",
            "headers": [
                (b"x-aiguard-key", b"core-key"),
                (b"x-aiguard-contract-version", b"2"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
            ],
            "state": {"aiguard_authority": authority},
        }
        original_timeout = overlay_module.CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS
        overlay_module.CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS = 0.01
        try:
            with self.assertRaisesRegex(Exception, "claim response"):
                asyncio.run(self.h.app(scope, receive, blocked_body_send))
        finally:
            overlay_module.CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS = original_timeout

        self.assertEqual(
            [message["type"] for message in sent],
            ["http.response.start", "http.response.body"],
        )
        record = next(iter(self.h.queue._records.values()))
        self.assertEqual(record.state, "queued")
        self.assertIsNone(record.slot)
        self.assertEqual(record.claim_miss_count, 0)
        self.assertFalse(record.poll_active)

    def test_methods_queries_contract_key_and_no_body_status_fail_before_processing(self):
        authority = self.h.authority(1)
        cases = (
            {"path": QUEUE_JOIN_PATH, "method": "GET", "expected": (405, "method_not_allowed")},
            {"path": QUEUE_STATUS_PATH, "method": "POST", "expected": (405, "method_not_allowed")},
            {"path": QUEUE_STATUS_PATH, "query": b"x=1", "expected": (422, "request_schema_invalid")},
            {
                "path": QUEUE_STATUS_PATH,
                "headers": [(b"x-aiguard-key", b"core-key"), (b"content-length", b"0")],
                "expected": (426, "contract_version_required"),
            },
            {
                "path": QUEUE_STATUS_PATH,
                "headers": [
                    (b"x-aiguard-key", b"wrong"),
                    (b"x-aiguard-contract-version", b"2"),
                    (b"content-length", b"0"),
                ],
                "expected": (401, "authentication_required"),
            },
        )
        for case in cases:
            with self.subTest(case=case):
                status, _headers, body, _ = asyncio.run(
                    request(
                        self.h.app,
                        case["path"],
                        authority,
                        method=case.get("method"),
                        headers=case.get("headers"),
                        query=case.get("query", b""),
                        forbid_body=True,
                    )
                )
                self.assertEqual((status, body["error"]["code"]), case["expected"])
        status, _headers, body, _ = asyncio.run(
            request(self.h.app, QUEUE_STATUS_PATH, None)
        )
        self.assertEqual((status, body["error"]["code"]), (401, "authentication_required"))

    def test_strict_json_content_length_and_exact_fields_reject_ambiguity(self):
        authority = self.h.authority(1)
        common = [
            (b"x-aiguard-key", b"core-key"),
            (b"x-aiguard-contract-version", b"2"),
            (b"content-type", b"application/json"),
        ]
        cases = (
            (QUEUE_JOIN_PATH, b'{"ticket":"a","ticket":"b"}', None, 422),
            (QUEUE_JOIN_PATH, b'{"ticket":"a","extra":1}', None, 422),
            (QUEUE_CLAIM_PATH, b'{"queue_capability":"a","last_revision":true}', None, 422),
            (QUEUE_CANCEL_PATH, b'{"extra":1}', None, 422),
            (QUEUE_JOIN_PATH, b'{}', common + [(b"content-length", b"3")], 422),
            (QUEUE_JOIN_PATH, b'[]', None, 422),
        )
        for path, raw, headers, expected in cases:
            with self.subTest(path=path, raw=raw):
                status, _headers, body, _ = asyncio.run(
                    request(
                        self.h.app,
                        path,
                        authority,
                        body=raw,
                        headers=headers,
                    )
                )
                self.assertEqual((status, body["error"]["code"]), (expected, "request_schema_invalid"))

        oversized_headers = common + [
            (b"content-length", str(MAX_QUEUE_BODY_BYTES + 1).encode())
        ]
        status, _headers, body, _ = asyncio.run(
            request(
                self.h.app,
                QUEUE_JOIN_PATH,
                authority,
                headers=oversized_headers,
                forbid_body=True,
            )
        )
        self.assertEqual((status, body["error"]["code"]), (413, "payload_too_large"))

        status, _headers, body, _ = asyncio.run(
            request(
                self.h.app,
                QUEUE_STATUS_PATH,
                authority,
                body=b"x",
                headers=[
                    (b"x-aiguard-key", b"core-key"),
                    (b"x-aiguard-contract-version", b"2"),
                    (b"content-type", b"text/plain"),
                    (b"content-length", b"1"),
                ],
            )
        )
        self.assertEqual((status, body["error"]["code"]), (422, "request_schema_invalid"))

    def test_approval_and_queue_errors_are_fixed_value_free_envelopes(self):
        authority = self.h.authority(1)
        status, _headers, body, _ = asyncio.run(
            request(
                self.h.app,
                QUEUE_JOIN_PATH,
                authority,
                payload={"ticket": "tampered"},
            )
        )
        self.assertEqual((status, body["error"]["code"]), (403, "approval_invalid"))
        self.assertEqual(body["error"]["count"], 0)
        self.assertNotIn("tampered", json.dumps(body))

        first = self.h.ticket(authority)
        asyncio.run(
            request(self.h.app, QUEUE_JOIN_PATH, authority, payload={"ticket": first})
        )
        second = self.h.ticket(authority)
        status, _headers, body, _ = asyncio.run(
            request(self.h.app, QUEUE_JOIN_PATH, authority, payload={"ticket": second})
        )
        self.assertEqual((status, body["error"]["code"]), (409, "queue_already_active"))
        self.assertEqual(set(body["error"]), {"code", "category", "count", "retryable", "status"})

    def test_disconnect_stops_long_poll_removes_eligibility_and_sends_nothing(self):
        executions = []
        for index in (1, 2):
            authority = self.h.authority(index)
            joined = self.h.queue.join(self.h.ticket(authority), authority=authority)
            claim = self.h.queue.claim(
                joined["queue_capability"],
                last_revision=0,
                authority=authority,
                wait_seconds=0,
            )
            executions.append(
                self.h.queue.begin_execute(
                    joined["queue_capability"],
                    claim["claim_token"],
                    authority=authority,
                )
            )

        waiting = self.h.authority(3)
        status, _headers, joined, _ = asyncio.run(
            request(
                self.h.app,
                QUEUE_JOIN_PATH,
                waiting,
                payload={"ticket": self.h.ticket(waiting)},
            )
        )
        self.assertEqual(status, 201)
        status, headers, body, sent = asyncio.run(
            request(
                self.h.app,
                QUEUE_CLAIM_PATH,
                waiting,
                payload={
                    "queue_capability": joined["queue_capability"],
                    "last_revision": 0,
                },
                disconnect_when=lambda: bool(self.h.queue._eligible),
            )
        )
        self.assertEqual((status, headers, body, sent), (None, {}, None, []))
        self.assertEqual(self.h.queue._eligible, set())
        self.assertEqual(self.h.queue._active_polls, set())
        self.assertEqual(self.h.queue._poll_capabilities, {})
        paused = self.h.queue.status(authority=waiting)
        self.assertEqual((paused["state"], paused["reason"]), ("paused", None))

        for execution in executions:
            self.h.queue.finish(execution, succeeded=True, attempt_count=1)
            execution.clear()

    def test_immediate_disconnect_with_a_free_slot_abandons_undelivered_claim(self):
        for index in range(1, 21):
            harness = QueueHttpHarness()
            authority = harness.authority(index)
            joined = harness.queue.join(harness.ticket(authority), authority=authority)
            status, headers, body, sent = asyncio.run(
                request(
                    harness.app,
                    QUEUE_CLAIM_PATH,
                    authority,
                    payload={
                        "queue_capability": joined["queue_capability"],
                        "last_revision": 0,
                    },
                    disconnect_when=lambda: True,
                )
            )
            self.assertEqual((status, headers, body, sent), (None, {}, None, []))
            snapshot = harness.queue.snapshot()[0]
            self.assertEqual(snapshot["state"], "queued")
            self.assertIsNone(snapshot["slot"])
            self.assertEqual(snapshot["claim_miss_count"], 0)

    def test_silent_disconnect_during_send_becomes_a_bounded_missed_claim(self):
        authority = self.h.authority(1)
        joined = self.h.queue.join(self.h.ticket(authority), authority=authority)
        raw = json.dumps(
            {
                "queue_capability": joined["queue_capability"],
                "last_revision": 0,
            },
            separators=(",", ":"),
        ).encode()
        request_sent = False
        disconnect_ready = asyncio.Event()
        attempted = []

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": raw, "more_body": False}
            await disconnect_ready.wait()
            return {"type": "http.disconnect"}

        async def uvicorn_style_silent_send(message):
            attempted.append(message["type"])
            if message["type"] == "http.response.start":
                disconnect_ready.set()
                await asyncio.sleep(0)
            # Uvicorn h11 returns silently once its transport is disconnected.

        scope = {
            "type": "http",
            "method": "POST",
            "path": QUEUE_CLAIM_PATH,
            "query_string": b"",
            "headers": [
                (b"x-aiguard-key", b"core-key"),
                (b"x-aiguard-contract-version", b"2"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
            ],
            "state": {"aiguard_authority": authority},
        }
        asyncio.run(self.h.app(scope, receive, uvicorn_style_silent_send))
        self.assertIn("http.response.start", attempted)
        record = next(iter(self.h.queue._records.values()))
        self.assertEqual(record.state, "claim_ready")
        self.assertTrue(record.claim_acknowledgement_pending)
        self.assertIsNotNone(record.slot)
        self.h.clock.value += CLAIM_HTTP_ACK_TTL_SECONDS + 1
        self.h.queue.tick()
        self.assertEqual(record.state, "queued")
        self.assertFalse(record.claim_acknowledgement_pending)
        self.assertIsNone(record.slot)
        self.assertEqual(record.claim_miss_count, 1)
        self.assertFalse(record.poll_active)

    def test_uvicorn_post_response_disconnect_does_not_revoke_a_valid_claim(self):
        authority = self.h.authority(1)
        joined = self.h.queue.join(self.h.ticket(authority), authority=authority)
        raw = json.dumps(
            {
                "queue_capability": joined["queue_capability"],
                "last_revision": 0,
            },
            separators=(",", ":"),
        ).encode()
        request_sent = False
        response_complete = asyncio.Event()
        sent = []

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": raw, "more_body": False}
            await response_complete.wait()
            # Pinned Uvicorn h11 emits this after an ordinary complete response.
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                response_complete.set()

        scope = {
            "type": "http",
            "method": "POST",
            "path": QUEUE_CLAIM_PATH,
            "query_string": b"",
            "headers": [
                (b"x-aiguard-key", b"core-key"),
                (b"x-aiguard-contract-version", b"2"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
            ],
            "state": {"aiguard_authority": authority},
        }
        asyncio.run(self.h.app(scope, receive, send))
        payload = json.loads(
            b"".join(
                message.get("body", b"")
                for message in sent
                if message["type"] == "http.response.body"
            )
        )
        record = next(iter(self.h.queue._records.values()))
        self.assertEqual(record.state, "claim_ready")
        self.assertTrue(record.claim_acknowledgement_pending)
        execution = self.h.queue.begin_execute(
            joined["queue_capability"],
            payload["claim_token"],
            authority=authority,
        )
        self.assertFalse(record.claim_acknowledgement_pending)
        self.assertEqual(record.state, "running")
        self.h.queue.finish(execution, succeeded=True, attempt_count=1)
        execution.clear()

    def test_disconnect_wins_over_concurrent_expiry_or_invalid_capability(self):
        authority = self.h.authority(1)
        race = DeadlineRaceQueue()
        race_app = Hosted3Overlay(
            DummyASGI(),
            environ={"AIGUARD_API_KEY": "core-key"},
            service=DummyPreview(),
            queue=race,
            now=self.h.clock,
        )
        status, headers, body, sent = asyncio.run(
            request(
                race_app,
                QUEUE_CLAIM_PATH,
                authority,
                payload={"queue_capability": "opaque", "last_revision": 0},
                disconnect_when=lambda: True,
            )
        )
        self.assertEqual((status, headers, body, sent), (None, {}, None, []))
        self.assertGreaterEqual(race.wakes, 1)

        for _ in range(20):
            status, headers, body, sent = asyncio.run(
                request(
                    self.h.app,
                    QUEUE_CLAIM_PATH,
                    authority,
                    payload={"queue_capability": "invalid", "last_revision": 0},
                    disconnect_when=lambda: True,
                )
            )
            self.assertEqual((status, headers, body, sent), (None, {}, None, []))

    def test_partial_body_disconnect_sends_no_schema_error(self):
        authority = self.h.authority(1)
        sent = []
        messages = iter(
            (
                {"type": "http.request", "body": b'{"ticket":', "more_body": True},
                {"type": "http.disconnect"},
            )
        )

        async def receive():
            return next(messages)

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": QUEUE_JOIN_PATH,
            "query_string": b"",
            "headers": [
                (b"x-aiguard-key", b"core-key"),
                (b"x-aiguard-contract-version", b"2"),
                (b"content-type", b"application/json"),
                (b"content-length", b"100"),
            ],
            "state": {"aiguard_authority": authority},
        }
        asyncio.run(self.h.app(scope, receive, send))
        self.assertEqual(sent, [])

    def test_send_failure_and_outer_cancellation_release_claim_or_eligibility(self):
        authority = self.h.authority(1)
        joined = self.h.queue.join(self.h.ticket(authority), authority=authority)
        raw = json.dumps(
            {
                "queue_capability": joined["queue_capability"],
                "last_revision": 0,
            },
            separators=(",", ":"),
        ).encode()
        delivered = False
        blocked = asyncio.Event()

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            await blocked.wait()
            raise AssertionError("unreachable")

        async def broken_send(_message):
            self.h.clock.value += 16
            self.h.queue.tick()
            raise OSError("synthetic closed transport")

        scope = {
            "type": "http",
            "method": "POST",
            "path": QUEUE_CLAIM_PATH,
            "query_string": b"",
            "headers": [
                (b"x-aiguard-key", b"core-key"),
                (b"x-aiguard-contract-version", b"2"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
            ],
            "state": {"aiguard_authority": authority},
        }
        with self.assertRaisesRegex(Exception, "synthetic closed transport"):
            asyncio.run(self.h.app(scope, receive, broken_send))
        snapshot = self.h.queue.snapshot()[0]
        self.assertEqual(snapshot["state"], "queued")
        self.assertIsNone(snapshot["slot"])

        blockers = []
        for index in (2, 3):
            other = self.h.authority(index)
            row = self.h.queue.join(self.h.ticket(other), authority=other)
            claim = self.h.queue.claim(
                row["queue_capability"],
                last_revision=0,
                authority=other,
                wait_seconds=0,
            )
            blockers.append(
                self.h.queue.begin_execute(
                    row["queue_capability"], claim["claim_token"], authority=other
                )
            )

        async def cancelled_poll():
            task = asyncio.create_task(
                request(
                    self.h.app,
                    QUEUE_CLAIM_PATH,
                    authority,
                    payload={
                        "queue_capability": joined["queue_capability"],
                        "last_revision": 0,
                    },
                )
            )
            deadline = time.monotonic() + 2
            while not self.h.queue._eligible:
                if time.monotonic() >= deadline:
                    raise AssertionError("poll never became eligible")
                await asyncio.sleep(0.005)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        asyncio.run(cancelled_poll())
        self.assertEqual(self.h.queue._eligible, set())
        self.assertEqual(self.h.queue._poll_capabilities, {})
        for execution in blockers:
            self.h.queue.finish(execution, succeeded=True, attempt_count=1)
            execution.clear()

    def test_delayed_cancelled_send_releases_an_expired_undelivered_claim(self):
        harness = QueueHttpHarness()
        authority = harness.authority(1)
        joined = harness.queue.join(harness.ticket(authority), authority=authority)
        raw = json.dumps(
            {
                "queue_capability": joined["queue_capability"],
                "last_revision": 0,
            },
            separators=(",", ":"),
        ).encode()
        delivered = False
        blocked = asyncio.Event()

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            await blocked.wait()
            raise AssertionError("unreachable")

        async def cancelled_send(_message):
            harness.clock.value += 16
            harness.queue.tick()
            raise asyncio.CancelledError()

        scope = {
            "type": "http",
            "method": "POST",
            "path": QUEUE_CLAIM_PATH,
            "query_string": b"",
            "headers": [
                (b"x-aiguard-key", b"core-key"),
                (b"x-aiguard-contract-version", b"2"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
            ],
            "state": {"aiguard_authority": authority},
        }
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(harness.app(scope, receive, cancelled_send))
        snapshot = harness.queue.snapshot()[0]
        self.assertEqual(snapshot["state"], "queued")
        self.assertIsNone(snapshot["slot"])
        self.assertEqual(snapshot["claim_miss_count"], 0)

    def test_nonclaim_transport_failure_never_attempts_a_second_response(self):
        for path, payload in (
            (QUEUE_JOIN_PATH, "join"),
            (QUEUE_STATUS_PATH, None),
            (QUEUE_CANCEL_PATH, {}),
        ):
            for fail_at in (1, 2):
                with self.subTest(path=path, fail_at=fail_at):
                    harness = QueueHttpHarness()
                    authority = harness.authority(1)
                    request_payload = (
                        {"ticket": harness.ticket(authority)}
                        if payload == "join"
                        else payload
                    )
                    body = (
                        json.dumps(request_payload, separators=(",", ":")).encode()
                        if request_payload is not None
                        else b""
                    )
                    method = "GET" if path == QUEUE_STATUS_PATH else "POST"
                    delivered = False
                    calls = []

                    async def receive():
                        nonlocal delivered
                        if not delivered:
                            delivered = True
                            return {
                                "type": "http.request",
                                "body": body,
                                "more_body": False,
                            }
                        await asyncio.Event().wait()
                        raise AssertionError("unreachable")

                    async def failing_send(message):
                        calls.append(message["type"])
                        if len(calls) == fail_at:
                            raise OSError("synthetic nonclaim transport failure")

                    headers = [
                        (b"x-aiguard-key", b"core-key"),
                        (b"x-aiguard-contract-version", b"2"),
                        (b"content-length", str(len(body)).encode()),
                    ]
                    if method == "POST":
                        headers.append((b"content-type", b"application/json"))
                    scope = {
                        "type": "http",
                        "method": method,
                        "path": path,
                        "query_string": b"",
                        "headers": headers,
                        "state": {"aiguard_authority": authority},
                    }
                    with self.assertRaisesRegex(
                        Exception,
                        "synthetic nonclaim transport failure",
                    ):
                        asyncio.run(harness.app(scope, receive, failing_send))
                    self.assertEqual(
                        calls,
                        ["http.response.start"]
                        if fail_at == 1
                        else ["http.response.start", "http.response.body"],
                    )

    def test_absent_cancel_is_idempotent_and_has_no_response_body(self):
        authority = self.h.authority(1)
        for _ in range(2):
            status, headers, body, _ = asyncio.run(
                request(self.h.app, QUEUE_CANCEL_PATH, authority, payload={})
            )
            self.assertEqual((status, body), (204, None))
            self.assertEqual(headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main(verbosity=2)

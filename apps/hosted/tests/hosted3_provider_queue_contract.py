#!/usr/bin/env python3
"""Stage 4A content-free provider queue and claim contract."""

from __future__ import annotations

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

from aift_hosted3.approval import (  # noqa: E402
    ApprovalBindings,
    ApprovalEngine,
    ApprovalError,
    DocumentFacts,
)
from aift_hosted3.authority import AuthorityContext  # noqa: E402
from aift_hosted3.provider_queue import (  # noqa: E402
    CLAIM_GRANT_SEQUENCE,
    CLAIM_HTTP_ACK_TTL_SECONDS,
    CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS,
    CLAIM_TTL_SECONDS,
    MAX_RECORDS,
    PRIORITY_ACTIVE_CAPACITY,
    PROVIDER_SLOTS,
    QUEUE_CAPABILITY_TTL_SECONDS,
    QUEUE_WAIT_CAP_SECONDS,
    STANDARD_ACTIVE_CAPACITY,
    STANDARD_IDLE_BORROW_SECONDS,
    STANDARD_QUEUE_JOIN_BURST,
    STANDARD_QUEUE_JOIN_PER_MINUTE,
    PRIORITY_QUEUE_JOIN_BURST,
    PRIORITY_QUEUE_JOIN_PER_MINUTE,
    STATUS_POLL_AFTER_MS,
    TOTAL_ACTIVE_CAPACITY,
    ProviderQueue,
    ProviderQueueError,
    QueueExecution,
    derive_provider_queue_key,
)


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


class Clock:
    def __init__(self, value: int = 2_000_000_000):
        self.value = value

    def __call__(self):
        return float(self.value)

    def advance(self, seconds: int):
        self.value += seconds


class Entropy:
    def __init__(self):
        self.counter = 0
        self.lock = threading.Lock()

    def __call__(self, size: int) -> bytes:
        with self.lock:
            self.counter += 1
            seed = self.counter
        output = b""
        block = 0
        while len(output) < size:
            output += hashlib.sha256(f"{seed}:{block}".encode("ascii")).digest()
            block += 1
        return output[:size]


def bindings(prompt="pg-v1"):
    return ApprovalBindings(
        provider_id="tokenmind",
        provider_model="thaillm-8b",
        prompt_revision=prompt,
        detector_code_sha256="1" * 64,
        detector_model_sha256="2" * 64,
    )


class QueueHarness:
    def __init__(self):
        self.clock = Clock()
        self.entropy = Entropy()
        self.approval = ApprovalEngine(
            b"A" * 32,
            bindings(),
            document_bindings=bindings("structure-protected-document-classifications-v1"),
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

    def standard(self, index: int, *, remaining=1800):
        return AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce=b64(index.to_bytes(16, "big")),
            subject_id=None,
            expires_at_unix=self.clock.value + remaining,
        )

    def priority(self, index: int, *, remaining=1800):
        return AuthorityContext(
            scope="priority_invite",
            service_class="priority",
            session_nonce=b64((100 + index).to_bytes(16, "big")),
            subject_id="sub_" + b64((200 + index).to_bytes(16, "big")),
            expires_at_unix=self.clock.value + remaining,
        )

    def custom_ticket(self, authority: AuthorityContext):
        return self.approval.mint_custom(
            authority=authority,
            mode="token",
            source_sha256="3" * 64,
            protected_sha256="4" * 64,
            salt="5" * 32,
            generation_seed=b"G" * 32,
        )[0]

    def document_ticket(self, authority: AuthorityContext, kind: str):
        return self.approval.mint_document(
            kind=kind,
            authority=authority,
            protected_sha256="6" * 64,
            salt="7" * 32,
            generation_seed=b"H" * 32,
            facts=DocumentFacts(
                source_pdf_sha256="8" * 64,
                parser_revision="aiguard-pdf-parser-v1",
                extraction_revision="pdfplumber-lines-v1",
                segmentation_revision="immutable-lines-v1",
                page_count=1,
                character_count=100,
                segment_count=3,
                omitted_visual_page_numbers=(1,),
                source_receipt_id=b64(b"R" * 16),
                segment_manifest_sha256="9" * 64,
                scenario_id=(
                    "hr-resume-pdf-structured-v1"
                    if kind == "synthetic_document_v1"
                    else None
                ),
                scenario_registry_sha256=(
                    "a" * 64 if kind == "synthetic_document_v1" else None
                ),
            ),
        )[0]


class ProviderQueueTests(unittest.TestCase):
    def setUp(self):
        self.h = QueueHarness()

    def join_custom(self, authority):
        return self.h.queue.join(
            self.h.custom_ticket(authority),
            authority=authority,
        )

    def test_key_join_status_and_snapshot_are_strict_and_content_free(self):
        self.assertEqual(len(derive_provider_queue_key(b"K" * 32)), 32)
        with self.assertRaises(ValueError):
            derive_provider_queue_key(b"short")
        authority = self.h.standard(1)
        joined = self.join_custom(authority)
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
        self.assertEqual(joined["state"], "queued")
        self.assertEqual(joined["position"], 1)
        self.assertEqual(joined["poll_after_ms"], STATUS_POLL_AFTER_MS)
        self.assertEqual(
            joined["queue_expires_at_unix"],
            self.h.clock.value + QUEUE_WAIT_CAP_SECONDS,
        )
        status = self.h.queue.status(authority=authority)
        self.assertEqual(
            set(status),
            {
                "state",
                "position",
                "reason",
                "enqueued_at_unix",
                "queue_expires_at_unix",
                "poll_after_ms",
                "automatic_execute_possible",
            },
        )
        self.assertEqual(status["state"], "queued")
        self.assertTrue(status["automatic_execute_possible"])
        snapshot = self.h.queue.snapshot()
        self.assertEqual(len(snapshot), 1)
        serialized = json.dumps(snapshot, sort_keys=True)
        for forbidden in (
            "3333333333333333",
            "4444444444444444",
            "5555555555555555",
            "source_sha256",
            "protected_sha256",
            "generation_seed",
            "queue_capability",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn(joined["queue_capability"], repr(self.h.queue))
        tampered = joined["queue_capability"][:-1] + (
            "A" if joined["queue_capability"][-1] != "A" else "B"
        )
        with self.assertRaises(ProviderQueueError):
            self.h.queue.claim(
                tampered,
                last_revision=0,
                authority=authority,
                wait_seconds=0,
            )

    def test_active_claim_poll_retains_only_minimal_opaque_binding(self):
        blockers = []
        for index in (1, 2):
            authority = self.h.standard(index)
            joined = self.join_custom(authority)
            ready = self.h.queue.claim(
                joined["queue_capability"],
                last_revision=0,
                authority=authority,
                wait_seconds=0,
            )
            blockers.append(
                (
                    authority,
                    self.h.queue.begin_execute(
                        joined["queue_capability"],
                        ready["claim_token"],
                        authority=authority,
                    ),
                )
            )

        waiting = self.h.standard(3)
        joined = self.join_custom(waiting)
        outcome = []

        def poll():
            outcome.append(
                self.h.queue.claim(
                    joined["queue_capability"],
                    last_revision=0,
                    authority=waiting,
                    wait_seconds=2,
                )
            )

        thread = threading.Thread(target=poll)
        thread.start()
        deadline = time.monotonic() + 1
        while not self.h.queue._poll_capabilities and time.monotonic() < deadline:
            time.sleep(0.01)
        retained = json.dumps(self.h.queue._poll_capabilities, sort_keys=True)
        self.assertEqual(
            set(next(iter(self.h.queue._poll_capabilities.values()))),
            {"jti", "scope", "session_nonce", "subject_id"},
        )
        for forbidden in (
            "approval",
            "source_sha256",
            "protected_sha256",
            "protection_generation_seed",
            "salt",
        ):
            self.assertNotIn(forbidden, retained)
        self.h.queue.finish(blockers[0][1], succeeded=True, attempt_count=1)
        thread.join(timeout=3)
        self.assertTrue(outcome)
        if outcome[0]["state"] == "claim_ready":
            execution = self.h.queue.begin_execute(
                joined["queue_capability"],
                outcome[0]["claim_token"],
                authority=waiting,
            )
            self.h.queue.finish(execution, succeeded=True, attempt_count=1)
            execution.clear()
        self.h.queue.finish(blockers[1][1], succeeded=True, attempt_count=1)
        for _, execution in blockers:
            execution.clear()

    def test_all_ticket_branches_cross_authority_and_boot_nonce_fail_closed(self):
        cases = (
            (self.h.standard(1), "custom_text_v1"),
            (self.h.standard(2), "standard_document_v1"),
            (self.h.priority(1), "invite_document_v1"),
            (self.h.priority(2), "synthetic_document_v1"),
        )
        for authority, kind in cases:
            with self.subTest(kind=kind):
                harness = QueueHarness()
                authority = (
                    harness.standard(1)
                    if authority.service_class == "standard"
                    else harness.priority(1)
                )
                ticket = (
                    harness.custom_ticket(authority)
                    if kind == "custom_text_v1"
                    else harness.document_ticket(authority, kind)
                )
                joined = harness.queue.join(ticket, authority=authority)
                claim = harness.queue.claim(
                    joined["queue_capability"],
                    last_revision=0,
                    authority=authority,
                    wait_seconds=0,
                )
                other = (
                    harness.standard(9)
                    if authority.service_class == "standard"
                    else harness.priority(9)
                )
                with self.assertRaises(ProviderQueueError):
                    harness.queue.begin_execute(
                        joined["queue_capability"],
                        claim["claim_token"],
                        authority=other,
                    )
                tampered_claim = claim["claim_token"][:-1] + (
                    "A" if claim["claim_token"][-1] != "A" else "B"
                )
                with self.assertRaises(ProviderQueueError):
                    harness.queue.begin_execute(
                        joined["queue_capability"],
                        tampered_claim,
                        authority=authority,
                    )
                other_queue = ProviderQueue(
                    b"Q" * 32,
                    harness.approval,
                    now=harness.clock,
                    random_bytes=harness.entropy,
                    boot_nonce=b"D" * 16,
                )
                with self.assertRaises(ProviderQueueError):
                    other_queue.claim(
                        joined["queue_capability"],
                        last_revision=0,
                        authority=authority,
                        wait_seconds=0,
                    )
                execution = harness.queue.begin_execute(
                    joined["queue_capability"],
                    claim["claim_token"],
                    authority=authority,
                )
                self.assertEqual(execution.approval["kind"], kind)
                harness.queue.finish(execution, succeeded=True, attempt_count=1)
                execution.clear()

    def test_capacity_one_active_owner_and_concurrent_duplicate_join(self):
        standard = [self.h.standard(index) for index in range(1, 10)]
        priority = [self.h.priority(index) for index in range(1, 6)]
        for authority in standard[:STANDARD_ACTIVE_CAPACITY]:
            self.join_custom(authority)
        with self.assertRaisesRegex(ProviderQueueError, "queue_full"):
            self.join_custom(standard[STANDARD_ACTIVE_CAPACITY])

        other = QueueHarness()
        standard = [other.standard(index) for index in range(1, 9)]
        priority = [other.priority(index) for index in range(1, 6)]
        for authority in standard:
            other.queue.join(other.custom_ticket(authority), authority=authority)
        for authority in priority[:PRIORITY_ACTIVE_CAPACITY]:
            other.queue.join(other.custom_ticket(authority), authority=authority)
        self.assertEqual(len(other.queue.snapshot()), TOTAL_ACTIVE_CAPACITY)
        with self.assertRaisesRegex(ProviderQueueError, "queue_full"):
            other.queue.join(other.custom_ticket(priority[-1]), authority=priority[-1])

        concurrent = QueueHarness()
        authority = concurrent.standard(1)
        ticket = concurrent.custom_ticket(authority)
        barrier = threading.Barrier(17)
        outcomes = []
        lock = threading.Lock()

        def join_once():
            barrier.wait()
            try:
                concurrent.queue.join(ticket, authority=authority)
                value = "winner"
            except (ProviderQueueError, ApprovalError) as error:
                value = error.code
            with lock:
                outcomes.append(value)

        threads = [threading.Thread(target=join_once) for _ in range(16)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(outcomes.count("winner"), 1)
        self.assertEqual(len(outcomes), 16)
        self.assertEqual(outcomes.count("queue_already_active"), 15)

        per_credential = QueueHarness()
        first = per_credential.priority(1)
        copied = AuthorityContext(
            scope="priority_invite",
            service_class="priority",
            session_nonce=b64(b"copied-session-1"),
            subject_id=first.subject_id,
            expires_at_unix=first.expires_at_unix,
        )
        per_credential.queue.join(
            per_credential.custom_ticket(first),
            authority=first,
        )
        with self.assertRaisesRegex(ProviderQueueError, "queue_already_active"):
            per_credential.queue.join(
                per_credential.custom_ticket(copied),
                authority=copied,
            )
        self.assertEqual(
            per_credential.queue.status(authority=copied)["state"],
            "absent",
        )

    def test_claim_is_one_use_cancel_running_is_truthful_and_finish_releases(self):
        authority = self.h.standard(1)
        joined = self.join_custom(authority)
        claim = self.h.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=authority,
            wait_seconds=0,
        )
        self.assertEqual(claim["state"], "claim_ready")
        self.assertEqual(
            claim["claim_expires_at_unix"], self.h.clock.value + CLAIM_TTL_SECONDS
        )
        execution = self.h.queue.begin_execute(
            joined["queue_capability"],
            claim["claim_token"],
            authority=authority,
        )
        self.assertEqual(execution.slot, 0)
        with self.assertRaisesRegex(ProviderQueueError, "queue_not_ready"):
            self.h.queue.begin_execute(
                joined["queue_capability"],
                claim["claim_token"],
                authority=authority,
            )
        with self.assertRaisesRegex(ProviderQueueError, "provider_already_running"):
            self.h.queue.cancel(authority=authority)
        self.h.queue.finish(execution, succeeded=True, attempt_count=1)
        self.assertEqual(self.h.queue.status(authority=authority)["state"], "complete")
        self.assertTrue(execution.approval)
        execution.clear()
        self.assertEqual(execution.approval, {})
        replacement = self.join_custom(authority)
        self.assertEqual(replacement["state"], "queued")

    def test_undelivered_claim_abandonment_releases_slot_without_counting_a_miss(self):
        authority = self.h.standard(1)
        joined = self.join_custom(authority)
        claim = self.h.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=authority,
            wait_seconds=0,
            execute_ack_pending=True,
        )
        self.assertEqual(claim["state"], "claim_ready")
        self.h.clock.advance(CLAIM_TTL_SECONDS + 1)
        self.assertTrue(
            self.h.queue.abandon_undelivered_claim(
                joined["queue_capability"],
                claim["claim_token"],
                authority=authority,
            )
        )
        snapshot = self.h.queue.snapshot()[0]
        self.assertEqual(snapshot["state"], "queued")
        self.assertIsNone(snapshot["slot"])
        self.assertEqual(snapshot["claim_miss_count"], 0)
        self.assertEqual(self.h.queue.status(authority=authority)["state"], "paused")
        with self.assertRaisesRegex(ProviderQueueError, "queue_not_ready"):
            self.h.queue.begin_execute(
                joined["queue_capability"],
                claim["claim_token"],
                authority=authority,
            )
        replacement = self.h.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=authority,
            wait_seconds=0,
        )
        execution = self.h.queue.begin_execute(
            joined["queue_capability"],
            replacement["claim_token"],
            authority=authority,
        )
        self.h.queue.finish(execution, succeeded=True, attempt_count=1)
        execution.clear()

    def test_http_claim_without_execute_ack_counts_one_bounded_miss(self):
        first_authority = self.h.standard(1)
        first_joined = self.join_custom(first_authority)
        first_claim = self.h.queue.claim(
            first_joined["queue_capability"],
            last_revision=0,
            authority=first_authority,
            wait_seconds=0,
            execute_ack_pending=True,
        )
        self.assertEqual(first_claim["state"], "claim_ready")
        first_record = next(iter(self.h.queue._records.values()))
        second_authority = self.h.standard(2)
        self.join_custom(second_authority)

        self.h.clock.advance(CLAIM_HTTP_ACK_TTL_SECONDS + 1)
        self.h.queue.tick()

        self.assertEqual(first_record.state, "queued")
        self.assertIsNone(first_record.slot)
        self.assertEqual(first_record.claim_miss_count, 1)
        self.assertFalse(first_record.claim_acknowledgement_pending)
        self.assertEqual(
            self.h.queue.status(authority=first_authority)["reason"],
            "claim_missed_requeued",
        )
        self.assertEqual(self.h.queue.status(authority=second_authority)["position"], 1)
        self.assertEqual(self.h.queue.status(authority=first_authority)["position"], 2)
        with self.assertRaisesRegex(ProviderQueueError, "queue_not_ready"):
            self.h.queue.begin_execute(
                first_joined["queue_capability"],
                first_claim["claim_token"],
                authority=first_authority,
            )

    def test_first_claim_miss_demotes_and_second_expires_without_provider_contact(self):
        authority = self.h.standard(1)
        joined = self.join_custom(authority)
        second_authority = self.h.standard(2)
        self.join_custom(second_authority)
        first = self.h.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=authority,
            wait_seconds=0,
        )
        self.assertEqual(first["state"], "claim_ready")
        self.h.clock.advance(CLAIM_TTL_SECONDS + 1)
        self.h.queue.tick()
        status = self.h.queue.status(authority=authority)
        self.assertEqual(status["state"], "paused")
        self.assertEqual(status["reason"], "claim_missed_requeued")
        self.assertEqual(
            self.h.queue.status(authority=second_authority)["position"], 1
        )
        self.assertEqual(self.h.queue.status(authority=authority)["position"], 2)
        second = self.h.queue.claim(
            joined["queue_capability"],
            last_revision=first["revision"],
            authority=authority,
            wait_seconds=0,
        )
        self.assertEqual(second["state"], "claim_ready")
        self.h.clock.advance(CLAIM_TTL_SECONDS + 1)
        self.h.queue.tick()
        status = self.h.queue.status(authority=authority)
        self.assertEqual(status["state"], "expired")
        self.assertEqual(status["reason"], "claim_missed_expired")
        with self.assertRaises(ProviderQueueError):
            self.h.queue.begin_execute(
                joined["queue_capability"],
                second["claim_token"],
                authority=authority,
            )

    def test_status_is_read_only_deadline_is_derived_then_tick_prunes(self):
        authority = self.h.standard(1)
        joined = self.join_custom(authority)
        before = self.h.queue.snapshot()
        self.h.clock.value = int(joined["queue_expires_at_unix"])
        first = self.h.queue.status(authority=authority)
        second = self.h.queue.status(authority=authority)
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "expired")
        self.assertEqual(first["reason"], "deadline_expired")
        self.assertEqual(self.h.queue.snapshot(), before)
        self.h.queue.tick()
        self.assertEqual(
            self.h.queue.status(authority=authority)["reason"],
            "deadline_expired",
        )
        self.h.clock.advance(301)
        self.h.queue.tick()
        self.assertEqual(self.h.queue.status(authority=authority)["state"], "absent")

    def test_claim_requires_the_full_fifteen_second_handoff_window(self):
        exact = QueueHarness()
        exact_authority = exact.standard(1)
        exact_joined = exact.queue.join(
            exact.custom_ticket(exact_authority), authority=exact_authority
        )
        exact.clock.value = int(exact_joined["queue_expires_at_unix"]) - CLAIM_TTL_SECONDS
        exact_claim = exact.queue.claim(
            exact_joined["queue_capability"],
            last_revision=0,
            authority=exact_authority,
            wait_seconds=0,
        )
        self.assertEqual(exact_claim["state"], "claim_ready")
        self.assertEqual(
            exact_claim["claim_expires_at_unix"],
            exact_joined["queue_expires_at_unix"],
        )
        exact.clock.advance(CLAIM_TTL_SECONDS - 1)
        execution = exact.queue.begin_execute(
            exact_joined["queue_capability"],
            exact_claim["claim_token"],
            authority=exact_authority,
        )
        exact.queue.finish(execution, succeeded=True, attempt_count=1)
        execution.clear()

        short = QueueHarness()
        short_authority = short.standard(1)
        short_joined = short.queue.join(
            short.custom_ticket(short_authority), authority=short_authority
        )
        short.clock.value = (
            int(short_joined["queue_expires_at_unix"]) - CLAIM_TTL_SECONDS + 1
        )
        short_claim = short.queue.claim(
            short_joined["queue_capability"],
            last_revision=0,
            authority=short_authority,
            wait_seconds=0,
        )
        self.assertEqual(short_claim["state"], "queued")
        self.assertIsNone(short_claim["claim_token"])
        short.clock.advance(CLAIM_TTL_SECONDS - 1)
        short.queue.tick()
        self.assertEqual(
            short.queue.status(authority=short_authority)["reason"],
            "deadline_expired",
        )

    def test_http_claim_requires_the_full_response_and_execute_ack_window(self):
        required = CLAIM_HTTP_ACK_TTL_SECONDS
        exact = QueueHarness()
        authority = exact.standard(1)
        joined = exact.queue.join(exact.custom_ticket(authority), authority=authority)
        exact.clock.value = int(joined["queue_expires_at_unix"]) - required
        claim = exact.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=authority,
            wait_seconds=0,
            execute_ack_pending=True,
        )
        self.assertEqual(claim["state"], "claim_ready")
        self.assertEqual(
            claim["claim_expires_at_unix"],
            joined["queue_expires_at_unix"],
        )
        self.assertEqual(claim["claim_window_seconds"], CLAIM_HTTP_ACK_TTL_SECONDS)
        execution = exact.queue.begin_execute(
            joined["queue_capability"], claim["claim_token"], authority=authority
        )
        exact.queue.finish(execution, succeeded=True, attempt_count=1)
        execution.clear()

        short = QueueHarness()
        short_authority = short.standard(1)
        short_joined = short.queue.join(
            short.custom_ticket(short_authority), authority=short_authority
        )
        short.clock.value = int(short_joined["queue_expires_at_unix"]) - required + 1
        short_claim = short.queue.claim(
            short_joined["queue_capability"],
            last_revision=0,
            authority=short_authority,
            wait_seconds=0,
            execute_ack_pending=True,
        )
        self.assertEqual(short_claim["state"], "queued")
        self.assertIsNone(short_claim["claim_token"])

    def test_fractional_http_grant_never_shortens_server_side_ack_validity(self):
        harness = QueueHarness()
        authority = harness.standard(1)
        joined = harness.queue.join(
            harness.custom_ticket(authority), authority=authority
        )
        harness.clock.value += 0.999
        claim = harness.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=authority,
            wait_seconds=0,
            execute_ack_pending=True,
        )
        self.assertEqual(claim["state"], "claim_ready")
        self.assertGreaterEqual(
            claim["claim_expires_at_unix"] - harness.clock.value,
            CLAIM_HTTP_ACK_TTL_SECONDS,
        )
        self.assertLess(
            claim["claim_expires_at_unix"] - harness.clock.value,
            CLAIM_HTTP_ACK_TTL_SECONDS + 1,
        )
        harness.clock.value += CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS
        self.assertGreaterEqual(
            claim["claim_expires_at_unix"] - harness.clock.value,
            CLAIM_TTL_SECONDS,
        )
        execution = harness.queue.begin_execute(
            joined["queue_capability"],
            claim["claim_token"],
            authority=authority,
        )
        harness.queue.finish(execution, succeeded=True, attempt_count=1)
        execution.clear()

    def test_foreground_long_poll_crossing_deadline_returns_queue_expired(self):
        blockers = []
        for index in (1, 2):
            authority = self.h.standard(index)
            joined = self.join_custom(authority)
            ready = self.h.queue.claim(
                joined["queue_capability"],
                last_revision=0,
                authority=authority,
                wait_seconds=0,
            )
            blockers.append(
                self.h.queue.begin_execute(
                    joined["queue_capability"],
                    ready["claim_token"],
                    authority=authority,
                )
            )

        waiting = self.h.standard(3)
        joined = self.join_custom(waiting)
        outcomes = []

        def poll():
            try:
                self.h.queue.claim(
                    joined["queue_capability"],
                    last_revision=0,
                    authority=waiting,
                    wait_seconds=2,
                )
                outcomes.append("unexpected_success")
            except ProviderQueueError as error:
                outcomes.append(error.code)

        thread = threading.Thread(target=poll)
        thread.start()
        deadline = time.monotonic() + 1
        while not self.h.queue._poll_capabilities and time.monotonic() < deadline:
            time.sleep(0.01)
        self.h.clock.value = int(joined["queue_expires_at_unix"])
        self.h.queue.tick()
        thread.join(timeout=3)
        self.assertEqual(outcomes, ["queue_expired"])
        status = self.h.queue.status(authority=waiting)
        self.assertEqual(status["state"], "expired")
        self.assertEqual(status["reason"], "deadline_expired")
        for execution in blockers:
            self.h.queue.finish(execution, succeeded=True, attempt_count=1)
            execution.clear()

    def test_disconnect_signal_removes_claim_eligibility_without_state_mutation(self):
        blockers = []
        for index in (1, 2):
            authority = self.h.standard(index)
            joined = self.join_custom(authority)
            ready = self.h.queue.claim(
                joined["queue_capability"],
                last_revision=0,
                authority=authority,
                wait_seconds=0,
            )
            blockers.append(
                self.h.queue.begin_execute(
                    joined["queue_capability"],
                    ready["claim_token"],
                    authority=authority,
                )
            )
        waiting = self.h.standard(3)
        joined = self.join_custom(waiting)
        disconnected = threading.Event()
        outcomes = []

        def poll():
            try:
                self.h.queue.claim(
                    joined["queue_capability"],
                    last_revision=0,
                    authority=waiting,
                    wait_seconds=5,
                    cancelled=disconnected.is_set,
                )
                outcomes.append("unexpected_success")
            except ProviderQueueError as error:
                outcomes.append(error.code)

        thread = threading.Thread(target=poll)
        thread.start()
        deadline = time.monotonic() + 1
        while not self.h.queue._poll_capabilities and time.monotonic() < deadline:
            time.sleep(0.01)
        disconnected.set()
        self.h.queue.wake_claims()
        thread.join(timeout=2)
        self.assertEqual(outcomes, ["queue_poll_cancelled"])
        self.assertFalse(self.h.queue._poll_capabilities)
        self.assertFalse(self.h.queue._eligible)
        status = self.h.queue.status(authority=waiting)
        self.assertEqual(status["state"], "paused")
        self.assertIsNone(status["reason"])
        for execution in blockers:
            self.h.queue.finish(execution, succeeded=True, attempt_count=1)
            execution.clear()

    def test_two_slots_borrow_and_global_grants_follow_priority_priority_priority_standard(self):
        p1, p2, p3 = (self.h.priority(index) for index in range(1, 4))
        standard = self.h.standard(1)
        joined = {
            "p1": self.join_custom(p1),
            "p2": self.join_custom(p2),
            "p3": self.join_custom(p3),
            "s": self.join_custom(standard),
        }
        first = self.h.queue.claim(
            joined["p1"]["queue_capability"],
            last_revision=0,
            authority=p1,
            wait_seconds=0,
        )
        second = self.h.queue.claim(
            joined["p2"]["queue_capability"],
            last_revision=0,
            authority=p2,
            wait_seconds=0,
        )
        e1 = self.h.queue.begin_execute(
            joined["p1"]["queue_capability"], first["claim_token"], authority=p1
        )
        e2 = self.h.queue.begin_execute(
            joined["p2"]["queue_capability"], second["claim_token"], authority=p2
        )
        self.assertEqual({e1.slot, e2.slot}, set(range(PROVIDER_SLOTS)))

        results = {}
        errors = []
        result_lock = threading.Lock()

        def wait_for_claim(name, authority):
            try:
                value = self.h.queue.claim(
                    joined[name]["queue_capability"],
                    last_revision=0,
                    authority=authority,
                    wait_seconds=5,
                )
                with result_lock:
                    results[name] = value
            except Exception as error:  # pragma: no cover - diagnostic capture
                with result_lock:
                    errors.append(error)

        tp = threading.Thread(target=wait_for_claim, args=("p3", p3))
        ts = threading.Thread(target=wait_for_claim, args=("s", standard))
        tp.start()
        ts.start()
        deadline = time.monotonic() + 1
        while len(self.h.queue._poll_capabilities) < 2:
            if time.monotonic() >= deadline:
                self.fail("both Priority and Standard claim contenders did not become eligible")
            time.sleep(0.005)
        self.h.queue.finish(e1, succeeded=True, attempt_count=1)

        deadline = time.monotonic() + 3
        while "p3" not in results and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIn("p3", results)
        self.assertNotIn("s", results)
        e3 = self.h.queue.begin_execute(
            joined["p3"]["queue_capability"],
            results["p3"]["claim_token"],
            authority=p3,
        )
        self.h.queue.finish(e3, succeeded=True, attempt_count=1)

        deadline = time.monotonic() + 3
        while "s" not in results and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIn("s", results)
        e4 = self.h.queue.begin_execute(
            joined["s"]["queue_capability"],
            results["s"]["claim_token"],
            authority=standard,
        )
        grants = [
            e1.service_class,
            e2.service_class,
            e3.service_class,
            e4.service_class,
        ]
        self.assertEqual(tuple(grants), CLAIM_GRANT_SEQUENCE)
        self.h.queue.finish(e2, succeeded=True, attempt_count=1)
        self.h.queue.finish(e4, succeeded=True, attempt_count=1)
        tp.join(timeout=2)
        ts.join(timeout=2)
        self.assertFalse(errors)

    def test_one_claim_has_one_concurrent_executor_and_sensitive_facts_clear(self):
        authority = self.h.standard(1)
        joined = self.join_custom(authority)
        claim = self.h.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=authority,
            wait_seconds=0,
        )
        barrier = threading.Barrier(17)
        outcomes = []
        executions = []
        lock = threading.Lock()

        def execute_once():
            barrier.wait()
            try:
                execution = self.h.queue.begin_execute(
                    joined["queue_capability"],
                    claim["claim_token"],
                    authority=authority,
                )
                outcome = "winner"
            except ProviderQueueError as error:
                execution = None
                outcome = error.code
            with lock:
                outcomes.append(outcome)
                if execution is not None:
                    executions.append(execution)

        threads = [threading.Thread(target=execute_once) for _ in range(16)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(outcomes.count("winner"), 1)
        self.assertEqual(outcomes.count("queue_not_ready"), 15)
        self.assertEqual(len(executions), 1)
        execution = executions[0]
        self.assertNotIn("source_sha256", repr(execution))
        self.h.queue.finish(execution, succeeded=True, attempt_count=2)
        execution.clear()
        self.assertEqual(execution.approval, {})
        row = self.h.queue.snapshot()[0]
        self.assertEqual(row["provider_attempt_count"], 2)

    def test_simultaneous_cancel_and_execute_have_one_atomic_transition(self):
        """A barrier race can only cancel, or begin exactly one running execution."""

        for attempt in range(16):
            with self.subTest(attempt=attempt):
                harness = QueueHarness()
                authority = harness.standard(1)
                joined = harness.queue.join(
                    harness.custom_ticket(authority), authority=authority
                )
                claim = harness.queue.claim(
                    joined["queue_capability"],
                    last_revision=0,
                    authority=authority,
                    wait_seconds=0,
                )
                barrier = threading.Barrier(3)
                outcomes = {}
                result_lock = threading.Lock()

                def begin_execute():
                    barrier.wait()
                    try:
                        result = harness.queue.begin_execute(
                            joined["queue_capability"],
                            claim["claim_token"],
                            authority=authority,
                        )
                    except ProviderQueueError as error:
                        result = error.code
                    with result_lock:
                        outcomes["execute"] = result

                def cancel():
                    barrier.wait()
                    try:
                        harness.queue.cancel(authority=authority)
                        result = "cancelled"
                    except ProviderQueueError as error:
                        result = error.code
                    with result_lock:
                        outcomes["cancel"] = result

                execute_thread = threading.Thread(target=begin_execute)
                cancel_thread = threading.Thread(target=cancel)
                execute_thread.start()
                cancel_thread.start()
                barrier.wait()
                execute_thread.join(timeout=5)
                cancel_thread.join(timeout=5)
                self.assertFalse(execute_thread.is_alive())
                self.assertFalse(cancel_thread.is_alive())
                self.assertEqual(set(outcomes), {"execute", "cancel"})

                row = harness.queue.snapshot()[0]
                if outcomes == {
                    "execute": "queue_not_ready",
                    "cancel": "cancelled",
                }:
                    self.assertEqual(row["state"], "cancelled")
                    self.assertIsNone(row["slot"])
                    self.assertEqual(row["provider_attempt_count"], 0)
                    self.assertEqual(
                        harness.queue.status(authority=authority)["state"], "cancelled"
                    )
                    continue

                self.assertEqual(outcomes["cancel"], "provider_already_running")
                execution = outcomes["execute"]
                self.assertIsInstance(execution, QueueExecution)
                self.assertEqual(row["state"], "running")
                self.assertEqual(row["slot"], execution.slot)
                self.assertEqual(row["provider_attempt_count"], 0)
                harness.queue.finish(execution, succeeded=True, attempt_count=1)
                execution.clear()
                self.assertEqual(harness.queue.status(authority=authority)["state"], "complete")

    def test_claim_ready_cancel_releases_slot_and_failure_is_value_free(self):
        first = self.h.standard(1)
        joined = self.join_custom(first)
        claim = self.h.queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=first,
            wait_seconds=0,
        )
        self.assertEqual(claim["state"], "claim_ready")
        self.h.queue.cancel(authority=first)
        self.assertEqual(self.h.queue.status(authority=first)["state"], "cancelled")
        self.assertIsNone(self.h.queue.snapshot()[0]["slot"])

        authorities = (self.h.standard(2), self.h.standard(3))
        executions = []
        for authority in authorities:
            queued = self.join_custom(authority)
            ready = self.h.queue.claim(
                queued["queue_capability"],
                last_revision=0,
                authority=authority,
                wait_seconds=0,
            )
            executions.append(
                self.h.queue.begin_execute(
                    queued["queue_capability"],
                    ready["claim_token"],
                    authority=authority,
                )
            )
        self.assertEqual({item.slot for item in executions}, set(range(PROVIDER_SLOTS)))
        self.h.queue.finish(executions[0], succeeded=False, attempt_count=3)
        failed = self.h.queue.status(authority=authorities[0])
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(failed["reason"], "provider_failed")
        failed_row = next(
            row for row in self.h.queue.snapshot() if row["state"] == "failed"
        )
        self.assertEqual(failed_row["provider_attempt_count"], 3)
        self.h.queue.finish(executions[1], succeeded=True, attempt_count=1)
        for execution in executions:
            execution.clear()

    def test_cancel_is_idempotent_and_short_session_never_consumes_approval(self):
        short = self.h.standard(1, remaining=899)
        ticket = self.h.custom_ticket(short)
        with self.assertRaisesRegex(ProviderQueueError, "queue_expired"):
            self.h.queue.join(ticket, authority=short)
        inspected = self.h.approval.inspect(
            ticket,
            authority=short,
            expected_kind="custom_text_v1",
        )
        self.assertTrue(inspected)

        authority = self.h.standard(2)
        joined = self.join_custom(authority)
        self.h.queue.cancel(authority=authority)
        self.h.queue.cancel(authority=authority)
        status = self.h.queue.status(authority=authority)
        self.assertEqual(status["state"], "cancelled")
        self.assertEqual(status["reason"], "cancelled")
        with self.assertRaisesRegex(ProviderQueueError, "queue_invalid"):
            self.h.queue.claim(
                joined["queue_capability"],
                last_revision=0,
                authority=authority,
                wait_seconds=0,
            )

    def test_bounded_terminal_history_never_causes_false_active_queue_full(self):
        for _ in range(MAX_RECORDS + 2):
            authority = self.h.standard(1)
            joined = self.join_custom(authority)
            self.assertEqual(joined["state"], "queued")
            self.h.queue.cancel(authority=authority)
            # This stress test isolates terminal-record pruning from the exact
            # Standard queue-admission bucket; each new preview is deliberately
            # separated by a complete published refill interval.
            self.h.clock.advance(60)
        authority = self.h.standard(1)
        self.assertLessEqual(len(self.h.queue.snapshot()), MAX_RECORDS)
        replacement = self.join_custom(authority)
        self.assertEqual(replacement["state"], "queued")

    def test_verified_queue_join_rates_and_standard_idle_borrow_are_exact(self):
        self.assertEqual((STANDARD_QUEUE_JOIN_PER_MINUTE, STANDARD_QUEUE_JOIN_BURST), (1, 1))
        self.assertEqual((PRIORITY_QUEUE_JOIN_PER_MINUTE, PRIORITY_QUEUE_JOIN_BURST), (6, 2))
        standard = self.h.standard(1)
        for _ in range(2):
            self.h.queue.cancel(authority=standard)
            self.join_custom(standard)
        self.h.queue.cancel(authority=standard)
        with self.assertRaisesRegex(ProviderQueueError, "queue_rate_limited"):
            self.join_custom(standard)
        owner = hashlib.sha256(
            f"standard\x1f{standard.session_nonce}".encode("ascii")
        ).digest()
        self.h.queue._standard_last_provider_admission[owner] = (
            self.h.clock.value - STANDARD_IDLE_BORROW_SECONDS
        )
        borrowed = self.join_custom(standard)
        self.assertEqual(borrowed["state"], "queued")
        self.h.queue.cancel(authority=standard)

        priority = self.h.priority(2)
        for _ in range(1 + PRIORITY_QUEUE_JOIN_BURST):
            self.join_custom(priority)
            self.h.queue.cancel(authority=priority)
        with self.assertRaisesRegex(ProviderQueueError, "queue_rate_limited"):
            self.join_custom(priority)

    def test_constants_match_approved_contract(self):
        self.assertEqual(PROVIDER_SLOTS, 2)
        self.assertEqual(TOTAL_ACTIVE_CAPACITY, 12)
        self.assertEqual(STANDARD_ACTIVE_CAPACITY, 8)
        self.assertEqual(PRIORITY_ACTIVE_CAPACITY, 4)
        self.assertEqual(CLAIM_GRANT_SEQUENCE, ("priority", "priority", "priority", "standard"))
        self.assertEqual(CLAIM_TTL_SECONDS, 15)
        self.assertEqual(CLAIM_RESPONSE_SEND_TIMEOUT_SECONDS, 5)
        self.assertEqual(CLAIM_HTTP_ACK_TTL_SECONDS, 20)
        self.assertEqual(QUEUE_WAIT_CAP_SECONDS, 600)
        self.assertEqual(QUEUE_CAPABILITY_TTL_SECONDS, 900)


if __name__ == "__main__":
    unittest.main(verbosity=2)

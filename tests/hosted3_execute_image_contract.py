#!/usr/bin/env python3
"""Opt-in real-detector Stage 4B2 execution probe for the exact Core image."""

from __future__ import annotations

import base64
import hashlib
import os
import sys
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from aift_hosted3.approval import ApprovalEngine  # noqa: E402
from aift_hosted3.authority import AuthorityContext  # noqa: E402
from aift_hosted3.execution import ExecuteService  # noqa: E402
from aift_hosted3.preview import (  # noqa: E402
    PreviewService,
    default_bindings,
    document_bindings,
)
from aift_hosted3.provider_queue import ProviderQueue  # noqa: E402


RUN_REAL = os.environ.get("AIGUARD_HOSTED3_REAL_EXECUTE") == "1"
SOURCE = (
    "ชื่อผู้สมัคร สมชาย ใจดี อีเมล somchai@example.com "
    "โทรศัพท์ 081-234-5678 ต้องการสรุปประวัติย่อ"
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
            value = self.value
        output = b""
        while len(output) < size:
            output += hashlib.sha256(f"real-execute:{value}:{len(output)}".encode()).digest()
        return output[:size]


@unittest.skipUnless(RUN_REAL, "exact Core image real-detector probe only")
class RealExecuteImageTests(unittest.TestCase):
    def test_real_preview_queue_execute_restores_without_sending_original_pii(self):
        now = 2_100_000_000
        entropy = Entropy()
        authority = AuthorityContext(
            scope="public_guest",
            service_class="standard",
            session_nonce=b64(b"S" * 16),
            subject_id=None,
            expires_at_unix=now + 1_800,
        )
        approval = ApprovalEngine(
            b"A" * 32,
            default_bindings(),
            document_bindings=document_bindings(),
            now=lambda: float(now),
            random_bytes=entropy,
            boot_nonce=b"B" * 16,
        )
        preview = PreviewService(
            approval,
            hosted_version="3.0.0",
            now=lambda: float(now),
            random_bytes=entropy,
        ).preview_custom(
            {"text": SOURCE, "mode": "token"},
            authority=authority,
        )
        self.assertTrue(preview["can_execute"])
        self.assertNotEqual(preview["protected_text"], SOURCE)
        self.assertNotIn("สมชาย ใจดี", preview["protected_text"])
        self.assertNotIn("somchai@example.com", preview["protected_text"])
        self.assertNotIn("081-234-5678", preview["protected_text"])

        queue = ProviderQueue(
            b"Q" * 32,
            approval,
            now=lambda: float(now),
            random_bytes=entropy,
            boot_nonce=b"C" * 16,
        )
        joined = queue.join(preview["ticket"], authority=authority)
        claimed = queue.claim(
            joined["queue_capability"],
            last_revision=0,
            authority=authority,
            wait_seconds=0,
        )
        provider_inputs = []
        guard_calls = []

        def provider(_system, user, before_attempt):
            before_attempt(0)
            guard_calls.append(1)
            provider_inputs.append(user)
            return user, 0.0, 1

        result = ExecuteService(
            queue,
            hosted_version="3.0.0",
            custom_provider_call=provider,
            request_id=lambda: "00000000-0000-4000-8000-000000000003",
        ).execute_custom(
            {
                "text": SOURCE,
                "queue_capability": joined["queue_capability"],
                "claim_token": claimed["claim_token"],
            },
            authority=authority,
        )
        self.assertEqual(guard_calls, [1])
        self.assertEqual(provider_inputs, [preview["protected_text"]])
        self.assertNotIn("สมชาย ใจดี", provider_inputs[0])
        self.assertEqual(result["restored_text"], SOURCE)
        self.assertEqual(result["provider"]["attempt_count"], 1)
        self.assertTrue(result["receipt"]["digest_match"])
        self.assertEqual(queue.status(authority=authority)["state"], "complete")


if __name__ == "__main__":
    unittest.main(verbosity=2)

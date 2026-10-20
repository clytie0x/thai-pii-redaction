#!/usr/bin/env python3
"""Stage 4C deterministic closeout for the complete internal state machine.

This is intentionally a behavioural aggregate, not a source-text audit.  The
four component contracts run in isolated Python processes so their barriers,
fake clocks, ASGI transports, and fake providers exercise the actual bounded
overlay without sharing mutable scheduler state.  Keeping the closeout here
prevents a second, subtly divergent copy of the Stage 4 state machine tests.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class Stage4CCloseoutContract(unittest.TestCase):
    """Run every deterministic Stage 4 behaviour family once as one closeout."""

    def _run(self, filename: str) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests" / filename)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=90,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"{filename} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            ),
        )

    def test_scheduler_authority_replay_deadline_and_cleanup_behaviour(self):
        """Threads/barriers cover 3:1 grants, slots, misses, replay and cleanup."""

        self._run("hosted3_provider_queue_contract.py")

    def test_http_claim_ack_disconnect_and_partial_send_behaviour(self):
        """ASGI fakes cover the HTTP acknowledgement lifecycle and loss bounds."""

        self._run("hosted3_queue_http_contract.py")

    def test_custom_and_document_provider_execution_behaviour(self):
        """Fake providers cover retry/timeout/integrity and restoration boundaries."""

        self._run("hosted3_execute_contract.py")

    def test_legacy_priority_shared_slot_and_validation_behaviour(self):
        """The byte-compatible legacy adapter remains inside the global scheduler."""

        self._run("hosted3_legacy_roundtrip_contract.py")


if __name__ == "__main__":
    unittest.main(verbosity=2)

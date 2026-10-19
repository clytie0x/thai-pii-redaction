#!/usr/bin/env python3
"""Opt-in exact-image FastAPI checks for Stage 4B3 legacy admission."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_IMAGE = os.environ.get("AIGUARD_CORE_IMAGE", "aiguard-stage4b3-core:local")
RUN_IMAGE = os.environ.get("AIGUARD_HOSTED3_LEGACY_IMAGE") == "1"


def _run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=True, capture_output=True, text=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _image_hashes(image: str, roots: list[str]) -> dict[str, str]:
    script = """
import hashlib,json
from pathlib import Path
roots=%s
files=[]
for raw in roots:
    path=Path('/app')/raw
    if path.is_file():
        files.append(path)
    elif path.is_dir():
        files.extend(item for item in path.rglob('*') if item.is_file() and '__pycache__' not in item.parts)
print(json.dumps({str(path.relative_to('/app')).replace('\\\\','/'):
 hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)},separators=(',',':'),sort_keys=True))
""" % repr(roots)
    output = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            image,
            "python",
            "-c",
            script,
        ]
    )
    return json.loads(output.stdout)


def _probe(image: str) -> dict[str, object]:
    """Run the copied FastAPI app with only an in-process synthetic provider."""

    script = textwrap.dedent(
        r'''
        import asyncio
        import base64
        import json
        import threading
        import time

        import httpx

        import aift_gateway
        from aift_hosted3.authority import AuthorityContext
        from aift_auth import COOKIE_NAME
        from app import server

        class ProbeProvider:
            calls = 0
            fail = False
            block = False
            started = threading.Event()
            release = threading.Event()
            completed = threading.Event()
            lock = threading.Lock()

            def complete(self, _system, user, *, timeout=30.0):
                with self.lock:
                    type(self).calls += 1
                type(self).started.set()
                try:
                    if type(self).block and not type(self).release.wait(timeout):
                        raise RuntimeError("synthetic provider wait expired")
                    if type(self).fail:
                        raise RuntimeError("synthetic provider failure")
                    return user
                finally:
                    type(self).completed.set()

        server._PROVIDER_FACTORIES["tokenmind"] = ProbeProvider
        origin = "https://team08.aiforthai.in.th"
        common = {
            "origin": origin,
            "x-aiguard-contract-version": "2",
            "x-aiguard-key": "synthetic-core-key-0001",
        }
        payload = {"text": "Synthetic legacy compatibility text.", "mode": "token", "provider": "tokenmind"}

        def b64(value):
            return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

        async def login(client):
            response = await client.post(
                "/aift/auth/login",
                json={"access_code": "synthetic-priority-code-0001"},
                headers={"origin": origin},
            )
            assert response.status_code == 204, response.text

        async def request(client, body=payload):
            return await client.post("/api/roundtrip", json=body, headers=common)

        async def main():
            transport = httpx.ASGITransport(app=aift_gateway.app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url=origin) as client:
                await login(client)
                success = await request(client)
                assert success.status_code == 200, success.text
                success_body = success.json()
                assert set(success_body) == {
                    "sanitized_text", "ai_response_masked", "restored_text",
                    "detected_entity_count", "entity_type_counts", "provider_used",
                    "section26_categories", "guard_findings", "warnings", "safety",
                    "restoration",
                }
                assert success.headers.get("x-aiguard-contract-version") == "2"
                assert success.headers.get("access-control-allow-origin") is None
                assert ProbeProvider.calls == 1

                malformed = await request(client, {"text": "malformed"})
                assert malformed.status_code == 422, malformed.text
                assert malformed.json()["error"]["code"] == "request_schema_invalid"
                assert malformed.headers.get("x-aiguard-contract-version") == "2"
                assert ProbeProvider.calls == 1

                ProbeProvider.fail = True
                provider_error = await request(client)
                assert provider_error.status_code == 502, provider_error.text
                assert provider_error.json()["error"]["code"] == "provider_unavailable"
                assert provider_error.headers.get("x-aiguard-contract-version") == "2"
                assert not [row for row in aift_gateway.hosted3_overlay.provider_queue.snapshot() if row["state"] == "running"]
                ProbeProvider.fail = False

                queue = aift_gateway.hosted3_overlay.provider_queue
                authority = next(iter(aift_gateway.app._active_sessions.values())).context
                other = AuthorityContext(
                    scope="priority_invite", service_class="priority",
                    session_nonce=b64(b"second-session01"),
                    subject_id="sub_" + b64(b"second-subject01"),
                    expires_at_unix=authority.expires_at_unix,
                )
                third = AuthorityContext(
                    scope="priority_invite", service_class="priority",
                    session_nonce=b64(b"third-session-01"),
                    subject_id="sub_" + b64(b"third-subject-01"),
                    expires_at_unix=authority.expires_at_unix,
                )
                held = [
                    queue.admit_legacy_roundtrip(authority=other, wait_seconds=0),
                    queue.admit_legacy_roundtrip(authority=third, wait_seconds=0),
                ]
                assert all(held)
                baseline = queue.snapshot()
                before_semantic_rejections = ProbeProvider.calls
                semantic_cases = (
                    ({"text": "", "mode": "token", "provider": "tokenmind"}, 400, "invalid_request"),
                    ({"text": "  ", "mode": "token", "provider": "tokenmind"}, 400, "invalid_request"),
                    ({"text": "x" * 20_001, "mode": "token", "provider": "tokenmind"}, 413, "payload_too_large"),
                    ({"text": "valid", "mode": "unsupported", "provider": "tokenmind"}, 400, "invalid_request"),
                    ({"text": "valid", "mode": "token", "provider": "unknown"}, 400, "invalid_request"),
                )
                for invalid_payload, status, code in semantic_cases:
                    started = time.monotonic()
                    rejected = await request(client, invalid_payload)
                    assert time.monotonic() - started < 0.5
                    assert rejected.status_code == status, rejected.text
                    assert rejected.json()["error"]["code"] == code
                    assert rejected.headers.get("x-aiguard-contract-version") == "2"
                    assert queue.snapshot() == baseline
                    assert ProbeProvider.calls == before_semantic_rejections
                before_denial = ProbeProvider.calls
                started = time.monotonic()
                denied = await request(client)
                elapsed = time.monotonic() - started
                assert denied.status_code == 429, denied.text
                assert denied.json()["error"]["code"] == "rate_limited"
                assert denied.headers.get("x-aiguard-contract-version") == "2"
                assert elapsed >= 4.8, elapsed
                assert ProbeProvider.calls == before_denial
                for item in held:
                    queue.finish_legacy_roundtrip(item, succeeded=True)

                ProbeProvider.block = True
                ProbeProvider.started.clear()
                ProbeProvider.release.clear()
                running = asyncio.create_task(request(client))
                assert await asyncio.to_thread(ProbeProvider.started.wait, 2.0)
                running_rows = [row for row in queue.snapshot() if row["state"] == "running"]
                assert len(running_rows) == 1, running_rows
                direct_one = queue.admit_legacy_roundtrip(authority=other, wait_seconds=0)
                direct_two = queue.admit_legacy_roundtrip(authority=third, wait_seconds=0)
                assert direct_one is not None and direct_two is None
                ProbeProvider.release.set()
                finished = await running
                assert finished.status_code == 200, finished.text
                queue.finish_legacy_roundtrip(direct_one, succeeded=True)
                assert not [row for row in queue.snapshot() if row["state"] == "running"]

                cookie = client.cookies.get(COOKIE_NAME)
                assert cookie
                raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

                def raw_scope():
                    return {
                        "type": "http", "asgi": {"version": "3.0"},
                        "http_version": "1.1", "method": "POST", "scheme": "https",
                        "path": "/api/roundtrip", "raw_path": b"/api/roundtrip",
                        "query_string": b"", "server": ("team08.aiforthai.in.th", 443),
                        "client": ("127.0.0.1", 1), "root_path": "", "state": {},
                        "headers": [
                            (b"host", b"team08.aiforthai.in.th"),
                            (b"origin", origin.encode("ascii")),
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(raw_body)).encode("ascii")),
                            (b"x-aiguard-contract-version", b"2"),
                            (b"x-aiguard-key", b"synthetic-core-key-0001"),
                            (b"cookie", (COOKIE_NAME + "=" + cookie).encode("ascii")),
                        ],
                    }

                async def one_request_then_disconnect():
                    sent_request = False
                    async def receive():
                        nonlocal sent_request
                        if not sent_request:
                            sent_request = True
                            return {"type": "http.request", "body": raw_body, "more_body": False}
                        return {"type": "http.disconnect"}
                    return receive

                ProbeProvider.block = True
                ProbeProvider.started.clear()
                ProbeProvider.completed.clear()
                ProbeProvider.release.clear()
                receive = await one_request_then_disconnect()
                disconnect_task = asyncio.create_task(aift_gateway.app(raw_scope(), receive, lambda _message: asyncio.sleep(0)))
                assert await asyncio.to_thread(ProbeProvider.started.wait, 2.0)
                assert len([row for row in queue.snapshot() if row["state"] == "running"]) == 1
                ProbeProvider.release.set()
                await disconnect_task
                assert await asyncio.to_thread(ProbeProvider.completed.wait, 2.0)
                assert not [row for row in queue.snapshot() if row["state"] == "running"]

                ProbeProvider.started.clear()
                ProbeProvider.completed.clear()
                ProbeProvider.release.clear()
                cancelled = asyncio.create_task(request(client))
                assert await asyncio.to_thread(ProbeProvider.started.wait, 2.0)
                cancelled.cancel()
                await asyncio.sleep(0.05)
                assert not cancelled.done()
                assert len([row for row in queue.snapshot() if row["state"] == "running"]) == 1
                ProbeProvider.release.set()
                try:
                    await cancelled
                except asyncio.CancelledError:
                    pass
                assert await asyncio.to_thread(ProbeProvider.completed.wait, 2.0)
                for _ in range(20):
                    if not [row for row in queue.snapshot() if row["state"] == "running"]:
                        break
                    await asyncio.sleep(0.05)
                assert not [row for row in queue.snapshot() if row["state"] == "running"]
                ProbeProvider.block = False

                sent = []
                sent_request = False
                async def receive_once():
                    nonlocal sent_request
                    if not sent_request:
                        sent_request = True
                        return {"type": "http.request", "body": raw_body, "more_body": False}
                    return {"type": "http.disconnect"}
                async def send_failure(message):
                    sent.append(message["type"])
                    raise OSError("synthetic response transport failure")
                try:
                    await aift_gateway.app(raw_scope(), receive_once, send_failure)
                except OSError:
                    pass
                assert sent == ["http.response.start"], sent
                assert not [row for row in queue.snapshot() if row["state"] == "running"]

        asyncio.run(main())
        print(json.dumps({"fastapi_legacy_probe": "passed"}, separators=(",", ":")))
        '''
    )
    output = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "-e",
            "AIGUARD_API_KEY=synthetic-core-key-0001",
            "-e",
            "AIFT_ACCESS_CODE=synthetic-priority-code-0001",
            "-e",
            "AIFT_COOKIE_SIGNING_KEY=synthetic-cookie-signing-key-0000000001",
            "-e",
            "AIFT_ALLOWED_ORIGINS=https://team08.aiforthai.in.th",
            "-e",
            "AIGUARD_ALLOWED_HOSTS=team08.aiforthai.in.th",
            "-e",
            "AIGUARD_PROVIDERS=tokenmind",
            "-e",
            "AIGUARD_AUDIT_STDOUT=1",
            "-e",
            "AIGUARD_MAX_TEXT_CHARS=20000",
            "-e",
            "UVICORN_WORKERS=1",
            image,
            "python",
            "-c",
            script,
        ]
    )
    if "Synthetic legacy compatibility text." in output.stdout:
        raise AssertionError("legacy request text reached the Core stdout audit log")
    return json.loads(output.stdout.splitlines()[-1])


@unittest.skipUnless(RUN_IMAGE, "Stage 4B3 exact-image FastAPI checks only")
class LegacyRoundtripImageTests(unittest.TestCase):
    def test_exact_core_source_bytes_and_revision_label(self):
        expected = {
            "aift_auth.py": _sha256(ROOT / "core" / "aift_auth.py"),
            "aift_gateway.py": _sha256(ROOT / "core" / "aift_gateway.py"),
        }
        expected.update(
            {
                str(path.relative_to(ROOT / "core")).replace("\\", "/"): _sha256(path)
                for path in sorted((ROOT / "core" / "aift_hosted3").glob("*.py"))
            }
        )
        self.assertEqual(
            _image_hashes(CORE_IMAGE, ["aift_auth.py", "aift_gateway.py", "aift_hosted3"]),
            expected,
        )
        inspected = json.loads(_run(["docker", "image", "inspect", CORE_IMAGE]).stdout)[0]
        revision = (inspected.get("Config", {}).get("Labels") or {}).get(
            "org.opencontainers.image.revision"
        )
        self.assertIsInstance(revision, str)
        self.assertNotIn(revision, {"", "local-working-tree"})

    def test_real_built_fastapi_roundtrip_contract_and_slot_lifecycle(self):
        self.assertEqual(_probe(CORE_IMAGE), {"fastapi_legacy_probe": "passed"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Standard-library contract tests for the port-owned AIFT auth gateway."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO / "core" / "aift_auth.py"


def load_module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"missing auth gateway: {MODULE_PATH.relative_to(REPO)}")
    core = str(MODULE_PATH.parent)
    sys.path.insert(0, core)
    try:
        spec = importlib.util.spec_from_file_location("aift_auth_under_test", MODULE_PATH)
        if spec is None or spec.loader is None:
            raise AssertionError("could not load auth gateway module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(core)


class DummyApp:
    def __init__(self):
        self.scopes: list[dict] = []

    async def __call__(self, scope, _receive, send):
        self.scopes.append(scope)
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"downstream":true}'})


async def request(
    app,
    path: str,
    *,
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
    body: bytes = b"",
) -> tuple[int, dict[str, list[str]], bytes]:
    sent: list[dict] = []
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
        "server": ("team08.aiforthai.in.th", 443),
    }
    await app(scope, receive, send)
    start = next(item for item in sent if item["type"] == "http.response.start")
    response_headers: dict[str, list[str]] = {}
    for key, value in start.get("headers", []):
        response_headers.setdefault(key.decode("latin-1").lower(), []).append(
            value.decode("latin-1")
        )
    response_body = b"".join(
        item.get("body", b"") for item in sent if item["type"] == "http.response.body"
    )
    return start["status"], response_headers, response_body


def header(name: str, value: str) -> tuple[bytes, bytes]:
    return name.lower().encode("ascii"), value.encode("latin-1")


class AuthContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.auth = load_module()

    def setUp(self):
        self.now_value = 1_800_000_000
        self.environment = {
            "AIFT_ACCESS_CODE": "entry-code-for-contract-tests",
            "AIFT_COOKIE_SIGNING_KEY": "signing-key-for-contract-tests-32-bytes-minimum",
            "AIGUARD_API_KEY": "core-service-key-for-contract-tests",
            "TOKENMIND_API_KEY": "provider-key-for-contract-tests",
            "AIFT_ALLOWED_ORIGINS": "https://team08.aiforthai.in.th",
            "AIFT_SESSION_TTL_SECONDS": "1800",
        }
        self.downstream = DummyApp()
        self.gateway = self.auth.AuthGateway(
            self.downstream,
            environ=self.environment,
            now=lambda: self.now_value,
            nonce_bytes=lambda size: b"N" * size,
        )

    def call(self, *args, **kwargs):
        return asyncio.run(request(self.gateway, *args, **kwargs))

    def login(self) -> str:
        body = json.dumps({"access_code": self.environment["AIFT_ACCESS_CODE"]}).encode(
            "utf-8"
        )
        status, headers, response_body = self.call(
            "/aift/auth/login",
            method="POST",
            headers=[
                header("content-type", "application/json"),
                header("origin", "https://team08.aiforthai.in.th"),
                header("sec-fetch-site", "same-origin"),
            ],
            body=body,
        )
        self.assertEqual(status, 204)
        self.assertEqual(response_body, b"")
        cookie_row = headers["set-cookie"][0]
        return cookie_row.split(";", 1)[0]

    def test_configuration_fails_loud(self):
        for missing in (
            "AIFT_ACCESS_CODE",
            "AIFT_COOKIE_SIGNING_KEY",
            "AIGUARD_API_KEY",
        ):
            env = dict(self.environment)
            del env[missing]
            with self.subTest(missing=missing):
                with self.assertRaises(self.auth.AuthConfigurationError):
                    self.auth.AuthGateway(DummyApp(), environ=env)

        weak = dict(self.environment)
        weak["AIFT_COOKIE_SIGNING_KEY"] = "too-short"
        with self.assertRaises(self.auth.AuthConfigurationError):
            self.auth.AuthGateway(DummyApp(), environ=weak)

        weak = dict(self.environment)
        weak["AIGUARD_API_KEY"] = "too-short"
        with self.assertRaises(self.auth.AuthConfigurationError):
            self.auth.AuthGateway(DummyApp(), environ=weak)

        secret_names = (
            "AIFT_ACCESS_CODE",
            "AIFT_COOKIE_SIGNING_KEY",
            "AIGUARD_API_KEY",
            "TOKENMIND_API_KEY",
        )
        shared = "shared-contract-secret-with-at-least-32-bytes"
        for index, first in enumerate(secret_names):
            for second in secret_names[index + 1 :]:
                reused = dict(self.environment)
                reused[first] = shared
                reused[second] = shared
                with self.subTest(reused=(first, second)):
                    with self.assertRaises(self.auth.AuthConfigurationError):
                        self.auth.AuthGateway(DummyApp(), environ=reused)

    def test_health_is_public_and_auth_route_is_not_forwarded(self):
        status, _headers, body = self.call("/api/health")
        self.assertEqual((status, body), (200, b'{"downstream":true}'))
        self.assertEqual(len(self.downstream.scopes), 1)

        status, _headers, _body = self.call("/aift/auth/session")
        self.assertEqual(status, 401)
        self.assertEqual(len(self.downstream.scopes), 1)

    def test_login_uses_fixed_failure_and_never_echoes_access_code(self):
        body = b'{"access_code":"wrong-contract-test-code"}'
        status, headers, response_body = self.call(
            "/aift/auth/login",
            method="POST",
            headers=[header("content-type", "application/json")],
            body=body,
        )
        self.assertEqual(status, 401)
        self.assertEqual(headers["cache-control"], ["no-store"])
        self.assertNotIn(b"wrong-contract-test-code", response_body)
        self.assertNotIn(b"entry-code", response_body)
        self.assertEqual(
            json.loads(response_body), {"error": {"code": "authentication_required"}}
        )
        self.assertEqual(self.downstream.scopes, [])

    def test_login_mints_short_lived_secure_cookie(self):
        cookie = self.login()
        value = cookie.split("=", 1)[1]
        self.assertNotIn(self.environment["AIFT_ACCESS_CODE"], value)

        body = json.dumps({"access_code": self.environment["AIFT_ACCESS_CODE"]}).encode(
            "utf-8"
        )
        status, headers, _response_body = self.call(
            "/aift/auth/login",
            method="POST",
            headers=[header("content-type", "application/json")],
            body=body,
        )
        self.assertEqual(status, 204)
        row = headers["set-cookie"][0]
        for required in (
            "__Host-aift_session=",
            "Max-Age=1800",
            "Path=/",
            "Secure",
            "HttpOnly",
            "SameSite=Strict",
        ):
            self.assertIn(required, row)
        self.assertNotIn("Domain=", row)

    def test_all_business_routes_require_a_valid_cookie(self):
        protected = (
            "/api/detect",
            "/api/guard",
            "/api/roundtrip",
            "/api/redact-pdf",
            "/api/analyze-report",
        )
        for path in protected:
            with self.subTest(path=path):
                status, _headers, _body = self.call(path, method="POST")
                self.assertEqual(status, 401)
        self.assertEqual(self.downstream.scopes, [])

        cookie = self.login()
        for path in protected:
            with self.subTest(path=path):
                status, _headers, body = self.call(
                    path,
                    method="POST",
                    headers=[header("cookie", cookie)],
                )
                self.assertEqual((status, body), (200, b'{"downstream":true}'))
        self.assertEqual(
            [scope["path"] for scope in self.downstream.scopes],
            list(protected),
        )

    def test_tamper_expiry_and_secret_rotation_invalidate_cookie(self):
        cookie = self.login()
        name, value = cookie.split("=", 1)
        tampered = f"{name}={value[:-1]}{'A' if value[-1] != 'A' else 'B'}"
        status, headers, _body = self.call(
            "/api/detect",
            method="POST",
            headers=[header("cookie", tampered)],
        )
        self.assertEqual(status, 401)
        self.assertIn("Max-Age=0", headers["set-cookie"][0])

        self.now_value += 1800
        status, _headers, _body = self.call(
            "/api/detect",
            method="POST",
            headers=[header("cookie", cookie)],
        )
        self.assertEqual(status, 401)

        self.now_value -= 1800
        rotated = dict(self.environment)
        rotated["AIFT_ACCESS_CODE"] = "rotated-entry-code-for-contract-tests"
        rotated_gateway = self.auth.AuthGateway(
            DummyApp(),
            environ=rotated,
            now=lambda: self.now_value,
            nonce_bytes=lambda size: b"N" * size,
        )
        status, _headers, _body = asyncio.run(
            request(
                rotated_gateway,
                "/api/detect",
                method="POST",
                headers=[header("cookie", cookie)],
            )
        )
        self.assertEqual(status, 401)

        rotated = dict(self.environment)
        rotated["AIFT_COOKIE_SIGNING_KEY"] = (
            "rotated-signing-key-for-contract-tests-32-bytes"
        )
        rotated_gateway = self.auth.AuthGateway(
            DummyApp(),
            environ=rotated,
            now=lambda: self.now_value,
            nonce_bytes=lambda size: b"N" * size,
        )
        status, _headers, _body = asyncio.run(
            request(
                rotated_gateway,
                "/api/detect",
                method="POST",
                headers=[header("cookie", cookie)],
            )
        )
        self.assertEqual(status, 401)

    def test_noncanonical_cookie_encoding_is_rejected(self):
        cookie = self.login()
        name, token = cookie.split("=", 1)
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        signature = token.rsplit(".", 1)[1]
        decoded = self.auth._b64url_decode(signature)
        alternatives = [
            char
            for char in alphabet
            if char != signature[-1]
            and self.auth._b64url_decode(signature[:-1] + char) == decoded
        ]
        self.assertTrue(alternatives)
        mutated = f"{name}={token[:-1]}{alternatives[0]}"
        status, _headers, _body = self.call(
            "/api/detect",
            method="POST",
            headers=[header("cookie", mutated)],
        )
        self.assertEqual(status, 401)

    def test_cross_site_and_unapproved_origin_are_rejected(self):
        cookie = self.login()
        for headers in (
            [
                header("cookie", cookie),
                header("sec-fetch-site", "cross-site"),
            ],
            [
                header("cookie", cookie),
                header("origin", "https://example.invalid"),
            ],
        ):
            status, _response_headers, body = self.call(
                "/api/roundtrip",
                method="POST",
                headers=headers,
            )
            self.assertEqual(status, 403)
            self.assertEqual(
                json.loads(body), {"error": {"code": "cross_site_forbidden"}}
            )
        self.assertEqual(self.downstream.scopes, [])

    def test_session_logout_revokes_replay_and_restart_fails_closed(self):
        cookie = self.login()
        status, _headers, body = self.call(
            "/aift/auth/session",
            headers=[header("cookie", cookie)],
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(body),
            {"authenticated": True, "expires_in": 1800},
        )

        status, headers, body = self.call(
            "/aift/auth/logout",
            method="POST",
            headers=[header("cookie", cookie)],
        )
        self.assertEqual(status, 204)
        self.assertEqual(body, b"")
        self.assertIn("Max-Age=0", headers["set-cookie"][0])

        status, headers, body = self.call(
            "/api/detect",
            method="POST",
            headers=[header("cookie", cookie)],
        )
        self.assertEqual(status, 401)
        self.assertIn("Max-Age=0", headers["set-cookie"][0])
        self.assertEqual(json.loads(body), {"error": {"code": "authentication_required"}})

        status, _headers, body = self.call(
            "/aift/auth/logout",
            method="POST",
            headers=[header("cookie", "__Host-aift_session=\xff")],
        )
        self.assertEqual((status, body), (204, b""))

        fresh_cookie = self.login()
        restarted_gateway = self.auth.AuthGateway(
            DummyApp(),
            environ=self.environment,
            now=lambda: self.now_value,
            nonce_bytes=lambda size: b"R" * size,
        )
        status, _headers, _body = asyncio.run(
            request(
                restarted_gateway,
                "/api/detect",
                method="POST",
                headers=[header("cookie", fresh_cookie)],
            )
        )
        self.assertEqual(status, 401)

    def test_active_session_capacity_fails_closed_without_echo(self):
        self.gateway._active_sessions = {
            index.to_bytes(32, "big"): self.now_value + 1800
            for index in range(self.auth._MAX_ACTIVE_SESSIONS)
        }
        status, headers, body = self.call(
            "/aift/auth/login",
            method="POST",
            headers=[header("content-type", "application/json")],
            body=b'{"access_code":"entry-code-for-contract-tests"}',
        )
        self.assertEqual(status, 429)
        self.assertEqual(headers["cache-control"], ["no-store"])
        self.assertEqual(json.loads(body), {"error": {"code": "rate_limited"}})
        self.assertNotIn(b"entry-code", body)

    def test_login_schema_and_body_size_fail_without_echo(self):
        cases = (
            (b"not-json", 400),
            (b'{"access_code":"entry-code-for-contract-tests","extra":1}', 400),
            (b'{"access_code":"\\ud800"}', 400),
            (b"x" * 4097, 413),
        )
        for body, expected in cases:
            with self.subTest(expected=expected):
                status, headers, response_body = self.call(
                    "/aift/auth/login",
                    method="POST",
                    headers=[header("content-type", "application/json")],
                    body=body,
                )
                self.assertEqual(status, expected)
                self.assertEqual(headers["cache-control"], ["no-store"])
                self.assertNotIn(body[:32], response_body)

    def test_gateway_installs_access_filter_before_core_import(self):
        source = (REPO / "core" / "aift_gateway.py").read_text(encoding="utf-8")
        install = source.find("install_uvicorn_access_log_filter()")
        report_policy = source.find("install_hosted_report_policy()")
        core_import = source.find("from app import server as _server")
        self.assertGreaterEqual(install, 0)
        self.assertGreater(report_policy, install)
        self.assertGreater(core_import, install)
        self.assertGreater(core_import, report_policy)
        self.assertIn('os.environ.get("AIGUARD_AUDIT_STDOUT") == "1"', source)
        self.assertIn('_server._get_audit_log_dir = lambda: "/tmp"', source)

    def test_hosted_report_policy_projects_section26_as_heuristic(self):
        policy_path = REPO / "core" / "aift_report_policy.py"
        fake_report = types.ModuleType("pii_redactor.report")
        calls: list[str] = []

        def analyze_text(text: str) -> dict:
            calls.append(text)
            return {
                "recommendations": [
                    {
                        "level": "high",
                        "title": "Section 26 sensitive data found (HEALTH)",
                        "desc": "unsafe legal overclaim",
                    },
                    {"level": "info", "title": "Other", "desc": "unchanged"},
                ]
            }

        fake_report.analyze_text = analyze_text
        fake_package = types.ModuleType("pii_redactor")
        fake_package.report = fake_report
        previous_package = sys.modules.get("pii_redactor")
        previous_report = sys.modules.get("pii_redactor.report")
        try:
            sys.modules["pii_redactor"] = fake_package
            sys.modules["pii_redactor.report"] = fake_report
            spec = importlib.util.spec_from_file_location(
                "aift_report_policy_under_test", policy_path
            )
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.install_hosted_report_policy()
            result = fake_report.analyze_text("synthetic")
        finally:
            if previous_package is None:
                sys.modules.pop("pii_redactor", None)
            else:
                sys.modules["pii_redactor"] = previous_package
            if previous_report is None:
                sys.modules.pop("pii_redactor.report", None)
            else:
                sys.modules["pii_redactor.report"] = previous_report

        self.assertEqual(calls, ["synthetic"])
        self.assertIn("heuristic", result["recommendations"][0]["desc"])
        self.assertNotIn("ต้องได้รับความยินยอม", result["recommendations"][0]["desc"])
        self.assertEqual(result["recommendations"][1]["desc"], "unchanged")


if __name__ == "__main__":
    unittest.main(verbosity=2)

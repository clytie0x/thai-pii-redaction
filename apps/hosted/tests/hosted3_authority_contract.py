#!/usr/bin/env python3
"""Stage-1 contract tests for Hosted 3.0 authority and timing metadata."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CORE = REPO / "core"
MODULE_PATH = CORE / "aift_auth.py"
ORIGIN = "https://team08.aiforthai.in.th"


def load_module():
    sys.path.insert(0, str(CORE))
    try:
        spec = importlib.util.spec_from_file_location(
            "aift_auth_hosted3_under_test", MODULE_PATH
        )
        if spec is None or spec.loader is None:
            raise AssertionError("could not load auth gateway module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(CORE))


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
    query_string: bytes = b"",
    forbid_body_read: bool = False,
) -> tuple[int, dict[str, list[str]], bytes]:
    sent: list[dict] = []
    delivered = False

    async def receive():
        nonlocal delivered
        if forbid_body_read:
            raise AssertionError("request body was read before authority rejection")
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
        "query_string": query_string,
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
        item.get("body", b"")
        for item in sent
        if item["type"] == "http.response.body"
    )
    return start["status"], response_headers, response_body


def header(name: str, value: str) -> tuple[bytes, bytes]:
    return name.lower().encode("ascii"), value.encode("latin-1")


def cookie_from(headers: dict[str, list[str]], name: str) -> str:
    prefix = f"{name}="
    row = next(value for value in headers["set-cookie"] if value.startswith(prefix))
    return row.split(";", 1)[0]


class Hosted3AuthorityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.auth = load_module()

    def setUp(self):
        self.now_value = 1_800_000_000.125
        self.priority_a = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        self.priority_b = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        self.registry = [
            {
                "subject_id": "sub_AAAAAAAAAAAAAAAAAAAAAA",
                "role": "priority_invite",
                "enabled": True,
                "code_sha256": hashlib.sha256(self.priority_a.encode()).hexdigest(),
            },
            {
                "subject_id": "sub_BBBBBBBBBBBBBBBBBBBBBB",
                "role": "priority_invite",
                "enabled": True,
                "code_sha256": hashlib.sha256(self.priority_b.encode()).hexdigest(),
            },
        ]
        self.environment = {
            "AIFT_ACCESS_CODE": "legacy-entry-code-for-contract-tests",
            "AIFT_PRIORITY_INVITES_JSON": json.dumps(self.registry),
            "AIFT_COOKIE_SIGNING_KEY": "signing-key-for-contract-tests-32-bytes-minimum",
            "AIGUARD_API_KEY": "core-service-key-for-contract-tests",
            "TOKENMIND_API_KEY": "provider-key-for-contract-tests",
            "AIFT_ALLOWED_ORIGINS": ORIGIN,
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

    def browser_headers(self, *extra: tuple[bytes, bytes]):
        return [
            header("origin", ORIGIN),
            header("sec-fetch-site", "same-origin"),
            *extra,
        ]

    def start_standard(self) -> tuple[str, dict]:
        status, headers, body = self.call(
            "/aift/auth/guest",
            method="POST",
            headers=self.browser_headers(header("content-type", "application/json")),
            body=b"{}",
        )
        self.assertEqual(status, 201)
        return cookie_from(headers, "__Host-aift_guest"), json.loads(body)

    def login_priority(
        self,
        code: str,
        *,
        cookie: str | None = None,
    ) -> tuple[str, dict[str, list[str]]]:
        payload = json.dumps({"access_code": code}).encode()
        headers = self.browser_headers(header("content-type", "application/json"))
        if cookie is not None:
            headers.append(header("cookie", cookie))
        status, headers, body = self.call(
            "/aift/auth/login",
            method="POST",
            headers=headers,
            body=payload,
        )
        self.assertEqual((status, body), (204, b""))
        return cookie_from(headers, "__Host-aift_session"), headers

    def test_standard_start_is_exact_timed_and_idempotent(self):
        cookie, payload = self.start_standard()
        self.assertEqual(
            payload,
            {
                "scope": "public_guest",
                "expires_at_unix": 1_800_001_800,
                "service_class": "standard",
                "capabilities": [
                    "analyze_report",
                    "detect",
                    "document_execute",
                    "document_preview",
                    "guard",
                    "protection_execute",
                    "protection_preview",
                    "synthetic_scenarios",
                ],
            },
        )
        status, headers, body = self.call(
            "/aift/auth/guest",
            method="POST",
            headers=self.browser_headers(
                header("content-type", "application/json"), header("cookie", cookie)
            ),
            body=b"{}",
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), payload)
        self.assertNotIn("set-cookie", headers)
        self.assertEqual(headers["x-aiguard-server-time-ms"], ["1800000000125"])
        self.assertEqual(
            headers["x-aiguard-session-expires-at-ms"], ["1800001800000"]
        )
        self.assertEqual(headers["x-aiguard-service-class"], ["standard"])

    def test_standard_start_schema_origin_query_and_capacity_fail_closed(self):
        cases = (
            ("GET", b"{}", b"", [], 405, "method_not_allowed"),
            ("POST", b"", b"", [], 400, "request_schema_invalid"),
            ("POST", b'{"extra":1}', b"", [], 400, "request_schema_invalid"),
            ("POST", b"{}", b"x=1", [], 400, "request_schema_invalid"),
            (
                "POST",
                b"{}",
                b"",
                [header("origin", "https://example.invalid")],
                403,
                "cross_site_forbidden",
            ),
        )
        for method, body, query, extra, expected, code in cases:
            with self.subTest(code=code, method=method):
                status, _headers, response = self.call(
                    "/aift/auth/guest",
                    method=method,
                    headers=[header("content-type", "application/json"), *extra],
                    body=body,
                    query_string=query,
                )
                self.assertEqual(status, expected)
                self.assertEqual(json.loads(response), {"error": {"code": code}})

        self.gateway._standard_sessions = {
            index.to_bytes(32, "big"): 1_800_001_800
            for index in range(self.auth._MAX_STANDARD_SESSIONS)
        }
        status, _headers, response = self.call(
            "/aift/auth/guest",
            method="POST",
            headers=self.browser_headers(header("content-type", "application/json")),
            body=b"{}",
        )
        self.assertEqual(status, 429)
        self.assertEqual(json.loads(response), {"error": {"code": "standard_capacity"}})

    def test_standard_end_is_exact_idempotent_and_revokes(self):
        cookie, _payload = self.start_standard()
        for supplied in (cookie, ""):
            headers = self.browser_headers(header("content-type", "application/json"))
            if supplied:
                headers.append(header("cookie", supplied))
            status, response_headers, body = self.call(
                "/aift/auth/guest/end",
                method="POST",
                headers=headers,
                body=b"{}",
            )
            self.assertEqual((status, body), (204, b""))
            self.assertIn("Max-Age=0", response_headers["set-cookie"][0])

        status, _headers, _body = self.call(
            "/api/detect",
            method="POST",
            headers=[header("cookie", cookie)],
            forbid_body_read=True,
        )
        self.assertEqual(status, 401)

    def test_standard_tamper_expiry_restart_and_key_rotation_fail_closed(self):
        cookie, _payload = self.start_standard()
        name, value = cookie.split("=", 1)
        tampered = f"{name}={value[:-1]}{'A' if value[-1] != 'A' else 'B'}"
        status, headers, _body = self.call(
            "/api/detect",
            method="POST",
            headers=[header("cookie", tampered)],
            forbid_body_read=True,
        )
        self.assertEqual(status, 401)
        self.assertIn("Max-Age=0", headers["set-cookie"][0])

        restarted = self.auth.AuthGateway(
            DummyApp(),
            environ=self.environment,
            now=lambda: self.now_value,
            nonce_bytes=lambda size: b"R" * size,
        )
        status, _headers, _body = asyncio.run(
            request(
                restarted,
                "/api/detect",
                method="POST",
                headers=[header("cookie", cookie)],
                forbid_body_read=True,
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
            nonce_bytes=lambda size: b"K" * size,
        )
        status, _headers, _body = asyncio.run(
            request(
                rotated_gateway,
                "/api/detect",
                method="POST",
                headers=[header("cookie", cookie)],
                forbid_body_read=True,
            )
        )
        self.assertEqual(status, 401)

        self.now_value += 1800
        status, _headers, _body = self.call(
            "/api/detect",
            method="POST",
            headers=[header("cookie", cookie)],
            forbid_body_read=True,
        )
        self.assertEqual(status, 401)

    def test_priority_registry_is_per_credential_and_raw_codes_are_not_retained(self):
        cookie_a, _headers = self.login_priority(self.priority_a)
        cookie_b, _headers = self.login_priority(self.priority_b)
        for cookie, subject in (
            (cookie_a, "sub_AAAAAAAAAAAAAAAAAAAAAA"),
            (cookie_b, "sub_BBBBBBBBBBBBBBBBBBBBBB"),
        ):
            status, _headers, body = self.call(
                "/api/detect",
                method="POST",
                headers=[header("cookie", cookie)],
            )
            self.assertEqual((status, body), (200, b'{"downstream":true}'))
            authority = self.downstream.scopes[-1]["state"]["aiguard_authority"]
            self.assertEqual(authority.scope, "priority_invite")
            self.assertEqual(authority.service_class, "priority")
            self.assertEqual(authority.subject_id, subject)
            self.assertEqual(authority.expires_at_unix, 1_800_001_800)

        retained = repr(vars(self.gateway))
        for secret in (
            self.priority_a,
            self.priority_b,
            self.environment["AIFT_ACCESS_CODE"],
        ):
            self.assertNotIn(secret, retained)

    def test_disabled_registry_entry_and_restart_revocation_fail_closed(self):
        cookie, _headers = self.login_priority(self.priority_a)
        disabled = [dict(item) for item in self.registry]
        disabled[0]["enabled"] = False
        environment = dict(self.environment)
        environment["AIFT_PRIORITY_INVITES_JSON"] = json.dumps(disabled)
        restarted = self.auth.AuthGateway(
            DummyApp(),
            environ=environment,
            now=lambda: self.now_value,
            nonce_bytes=lambda size: b"R" * size,
        )
        status, _headers, _body = asyncio.run(
            request(
                restarted,
                "/api/detect",
                method="POST",
                headers=[header("cookie", cookie)],
                forbid_body_read=True,
            )
        )
        self.assertEqual(status, 401)

        weak = [dict(self.registry[0])]
        weak[0]["code_sha256"] = hashlib.sha256(b"short").hexdigest()
        weak_environment = dict(self.environment)
        weak_environment["AIFT_PRIORITY_INVITES_JSON"] = json.dumps(weak)
        weak_gateway = self.auth.AuthGateway(
            DummyApp(),
            environ=weak_environment,
            now=lambda: self.now_value,
        )
        status, _headers, _body = asyncio.run(
            request(
                weak_gateway,
                "/aift/auth/login",
                method="POST",
                headers=[header("content-type", "application/json")],
                body=b'{"access_code":"short"}',
            )
        )
        self.assertEqual(status, 401)
        payload = json.dumps({"access_code": self.priority_a}).encode()
        status, _headers, _body = asyncio.run(
            request(
                restarted,
                "/aift/auth/login",
                method="POST",
                headers=[header("content-type", "application/json")],
                body=payload,
            )
        )
        self.assertEqual(status, 401)

    def test_registry_configuration_is_strict_and_bounded(self):
        bad_registries = (
            {},
            [{**self.registry[0], "name": "human"}],
            [{**self.registry[0], "subject_id": "judge-name"}],
            [{**self.registry[0], "role": "admin"}],
            [{**self.registry[0], "code_sha256": "A" * 64}],
            [self.registry[0], dict(self.registry[0])],
            [self.registry[0], {**self.registry[1], "code_sha256": self.registry[0]["code_sha256"]}],
            [
                {
                    **self.registry[0],
                    "subject_id": f"sub_{index:022d}",
                    "code_sha256": f"{index:064x}",
                }
                for index in range(33)
            ],
        )
        for registry in bad_registries:
            with self.subTest(kind=type(registry).__name__, size=len(registry)):
                environment = dict(self.environment)
                environment["AIFT_PRIORITY_INVITES_JSON"] = json.dumps(registry)
                with self.assertRaises(self.auth.AuthConfigurationError):
                    self.auth.AuthGateway(DummyApp(), environ=environment)

    def test_additive_timing_error_rows_are_exact_and_value_free(self):
        from aift_hosted3 import http_v2

        self.assertEqual(
            http_v2.error_payload("session_review_window"),
            {
                "error": {
                    "code": "session_review_window",
                    "category": "session",
                    "count": 0,
                    "retryable": False,
                    "status": 409,
                }
            },
        )
        self.assertEqual(
            http_v2.error_payload("approval_expired"),
            {
                "error": {
                    "code": "approval_expired",
                    "category": "session",
                    "count": 0,
                    "retryable": False,
                    "status": 410,
                }
            },
        )
        with self.assertRaises(KeyError):
            http_v2.error_payload("request-derived-value")

    def test_authority_routes_and_mutual_exclusion_fail_before_body(self):
        standard_cookie, _payload = self.start_standard()
        for path in ("/api/detect", "/api/guard", "/api/analyze-report"):
            status, _headers, _body = self.call(
                path,
                method="POST",
                headers=[header("cookie", standard_cookie)],
            )
            self.assertEqual(status, 200)
            authority = self.downstream.scopes[-1]["state"]["aiguard_authority"]
            self.assertEqual((authority.scope, authority.service_class), ("public_guest", "standard"))

        for path in ("/api/roundtrip", "/api/redact-pdf"):
            status, _headers, body = self.call(
                path,
                method="POST",
                headers=[header("cookie", standard_cookie)],
                forbid_body_read=True,
            )
            self.assertEqual(status, 403)
            self.assertEqual(json.loads(body), {"error": {"code": "control_forbidden"}})

        priority_cookie, login_headers = self.login_priority(
            self.priority_a,
            cookie=standard_cookie,
        )
        self.assertTrue(
            any(
                row.startswith("__Host-aift_guest=") and "Max-Age=0" in row
                for row in login_headers["set-cookie"]
            )
        )
        status, _headers, _body = self.call(
            "/api/roundtrip",
            method="POST",
            headers=[header("cookie", priority_cookie)],
        )
        self.assertEqual(status, 200)

        # A valid Priority authority cannot be silently replaced by Standard.
        status, _headers, body = self.call(
            "/aift/auth/guest",
            method="POST",
            headers=self.browser_headers(
                header("content-type", "application/json"),
                header("cookie", priority_cookie),
            ),
            body=b"{}",
            forbid_body_read=True,
        )
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(body), {"error": {"code": "authority_conflict"}})

    def test_two_valid_cookies_clear_both_and_auth_session_keeps_body_compatible(self):
        standard_cookie, _payload = self.start_standard()
        priority_cookie, _headers = self.login_priority(self.priority_a)

        for cookie, service_class in (
            (standard_cookie, "standard"),
            (priority_cookie, "priority"),
        ):
            status, headers, body = self.call(
                "/aift/auth/session",
                headers=[header("cookie", cookie)],
            )
            self.assertEqual(status, 200)
            self.assertEqual(body, b'{"authenticated":true,"expires_in":1800}')
            self.assertEqual(headers["x-aiguard-server-time-ms"], ["1800000000125"])
            self.assertEqual(
                headers["x-aiguard-session-expires-at-ms"], ["1800001800000"]
            )
            self.assertEqual(headers["x-aiguard-service-class"], [service_class])

        # The alternate client omitted the Standard cookie during Priority
        # login; presenting both valid process-local cookies must fail closed.
        both = f"{priority_cookie}; {standard_cookie}"
        status, headers, body = self.call(
            "/aift/auth/session",
            headers=[header("cookie", both)],
            forbid_body_read=True,
        )
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(body), {"error": {"code": "authority_conflict"}})
        self.assertEqual(len(headers["set-cookie"]), 2)
        self.assertTrue(all("Max-Age=0" in row for row in headers["set-cookie"]))

    def test_duplicate_authority_cookie_fails_closed_before_simplecookie_selection(self):
        standard_cookie, _payload = self.start_standard()
        authority, headers, conflict = self.gateway._request_authority(
            {
                "headers": [
                    header(
                        "cookie",
                        "__Host-aift_guest=attacker-controlled; " + standard_cookie,
                    )
                ]
            }
        )
        self.assertIsNone(authority)
        self.assertTrue(conflict)
        self.assertEqual(len(headers), 2)


if __name__ == "__main__":
    unittest.main()

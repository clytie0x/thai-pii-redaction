"""Source-only regressions for the real-image Nginx contract harness."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def load_contract():
    path = Path(__file__).with_name("nginx_contract.py")
    spec = importlib.util.spec_from_file_location("nginx_harness_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NginxHarnessTests(unittest.TestCase):
    def test_rate_reset_is_owned_and_startup_readiness_is_bounded(self):
        contract = load_contract()
        with (
            mock.patch.object(contract, "run") as restart,
            mock.patch.object(
                contract.subprocess,
                "run",
                side_effect=[SimpleNamespace(returncode=1), SimpleNamespace(returncode=0)],
            ) as probe,
            mock.patch.object(contract.time, "sleep"),
        ):
            contract.reset_proxy_rate_state()
        restart.assert_called_once_with("docker", "restart", contract.PROXY)
        self.assertEqual(probe.call_count, 2)
        for call in probe.call_args_list:
            self.assertEqual(call.args[0][-1], "http://127.0.0.1:8001/internal-health")
        with (
            mock.patch.object(contract, "run"),
            mock.patch.object(
                contract.subprocess, "run", return_value=SimpleNamespace(returncode=1)
            ) as failed_probe,
            mock.patch.object(contract.time, "sleep"),
        ):
            with self.assertRaises(contract.ContractFailure):
                contract.reset_proxy_rate_state()
        self.assertEqual(failed_probe.call_count, 20)

    def test_static_product_checks_use_the_current_source_version(self):
        contract = load_contract()
        pages = {
            "/": "index.html",
            "/app": "app.html",
            "/privacy": "privacy.html",
            "/terms": "terms.html",
            "/help": "help.html",
            "/downloads": "downloads.html",
            "/developers": "developers.html",
            "/robots.txt": "robots.txt",
            "/sitemap.xml": "sitemap.xml",
        }

        def web_get(path):
            if path in pages:
                return 200, (contract.REPO / "web" / pages[path]).read_text(encoding="utf-8")
            if path == "/not-a-product-page":
                return 404, (contract.REPO / "web/404.html").read_text(encoding="utf-8")
            return 404, "fixed denial"

        def asset(path):
            file = contract.REPO / "web" / path.lstrip("/")
            if not file.is_file():
                return 404, {}, b"fixed denial"
            content_type = {
                ".svg": "image/svg+xml",
                ".woff2": "font/woff2",
                ".txt": "text/plain",
                ".css": "text/css",
                ".js": "application/javascript",
            }[file.suffix]
            return 200, {"Content-Type": content_type}, file.read_bytes()

        def redirect(_base, path, _headers):
            target = "/api/health" if path.startswith("/health") else "/private"
            return 308, {"Location": "https://team08.aiforthai.in.th" + target}

        failures = []
        with (
            mock.patch.object(contract, "web_get", web_get),
            mock.patch.object(contract, "web_binary_response", asset),
            mock.patch.object(contract, "no_redirect_response", redirect),
        ):
            contract.check_product_pages_and_https_enforcement(failures)
        self.assertEqual(failures, [])

    def test_functional_document_aliases_each_have_fresh_rate_state(self):
        contract = load_contract()
        state = {"document_calls": 0, "resets": 0, "upstream": 0}
        document_paths = []

        def reset():
            state["document_calls"] = 0
            state["resets"] += 1

        def call(path, *, method, data, headers=None):
            canonical = path.removeprefix("/v1")
            if canonical == "/provider-queue/status" and data:
                return 413, {}, "fixed denial"
            if canonical in contract.HOSTED3_AUTH:
                state["upstream"] += 1
                return 200, {}, json.dumps({"path": "/aift" + canonical, "key": "", "contract": ""})
            if canonical == "/document-preview":
                document_paths.append(path)
                state["document_calls"] += 1
                # Reproduce the observed CI bucket exhaustion, without Docker.
                if state["document_calls"] > 1:
                    return 429, {}, "fixed rate limit"
            state["upstream"] += 1
            upstream = contract.HOSTED3_PROTECTED[canonical][2]
            return (
                200,
                {},
                json.dumps({"path": upstream, "key": contract.TEST_KEY, "contract": "2"}),
            )

        failures = []
        with (
            mock.patch.object(contract, "call", call),
            mock.patch.object(contract, "stub_log_lines", lambda: state["upstream"]),
            mock.patch.object(contract, "reset_proxy_rate_state", reset, create=True),
        ):
            contract.check_hosted3_exact_routes_reach_only_approved_core_paths(failures)
        self.assertEqual(failures, [])
        self.assertEqual(document_paths, ["/document-preview", "/v1/document-preview"])
        self.assertEqual(state["resets"], 2)

    def test_shared_document_rate_probe_requires_a_real_refusal(self):
        contract = load_contract()
        for statuses, should_fail in (
            ((200, 200, 429), False),
            ((200, 429, 429), False),
            ((200, 200, 200), True),
            ((429, 429, 429), True),
        ):
            with self.subTest(statuses=statuses):
                paths = []
                cookies = []

                def call(
                    path,
                    *,
                    method,
                    data,
                    headers,
                    _paths=paths,
                    _cookies=cookies,
                    _statuses=statuses,
                ):
                    _paths.append(path)
                    _cookies.append(headers["Cookie"])
                    return _statuses[len(_paths) - 1], {}, "synthetic response"

                failures = []
                with (
                    mock.patch.object(contract, "call", call),
                    mock.patch.object(contract, "reset_proxy_rate_state", create=True) as reset,
                ):
                    contract.check_document_aliases_share_rate_limit(failures)
                self.assertEqual(bool(failures), should_fail)
                self.assertEqual(
                    paths, ["/document-preview", "/v1/document-preview", "/document-preview"]
                )
                self.assertEqual(len(set(cookies)), 1)
                reset.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

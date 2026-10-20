"""An internal restore defect must not surface as a raw 500 / generic job_failed.

The provider try/except in both surfaces covers provider.complete only;
restore_stateless on the next line was bare (spec: explicit scope, both paths).
"""

import pytest


class TestServerRestoreBoundary:
    @pytest.fixture()
    def client(self):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from amphrang.server.server import app

        return TestClient(
            app,
            base_url="http://localhost",
            headers={"X-Amphrang-Contract-Version": "2"},
        )

    def test_restore_defect_is_clean_500(self, client, monkeypatch):
        from amphrang.server import server

        def boom(text, *, mapping):
            raise RuntimeError("internal defect detail")

        monkeypatch.setattr(server, "restore_stateless", boom)
        resp = client.post(
            "/api/roundtrip",
            json={"text": "สวัสดีครับผมชื่อสมชาย", "mode": "token", "provider": "fake"},
        )
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "restore_failed"
        assert "internal defect detail" not in resp.text

    def test_non_string_provider_return_is_502(self, client, monkeypatch):
        from amphrang.engine.ai_client import AIProvider
        from amphrang.server import server

        class Broken(AIProvider):
            def complete(self, system, user, *, timeout=30.0):
                return None  # type: ignore[return-value]

        monkeypatch.setitem(server._PROVIDER_FACTORIES, "fake", Broken)
        resp = client.post(
            "/api/roundtrip",
            json={"text": "สวัสดีครับ", "mode": "token", "provider": "fake"},
        )
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "provider_response_invalid"

    def test_provider_protocol_error_is_502_not_500(self, client, monkeypatch):
        # spec testing item 4: empty/protocol-violating content must surface as
        # 502 on the HTTP path (the first spec draft had this inverted)
        from amphrang.engine.ai_client import AIProvider, ProviderProtocolError
        from amphrang.server import server

        class Protocol(AIProvider):
            def complete(self, system, user, *, timeout=30.0):
                raise ProviderProtocolError("provider returned empty content")

        monkeypatch.setitem(server._PROVIDER_FACTORIES, "fake", Protocol)
        resp = client.post(
            "/api/roundtrip",
            json={"text": "สวัสดีครับ", "mode": "token", "provider": "fake"},
        )
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "provider_response_invalid"

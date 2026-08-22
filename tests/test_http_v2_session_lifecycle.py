"""Pins the strict HTTP v2 session lifecycle: keyed sanitize/reidentify/
delete-session against a fresh SessionService, and that fully stateless
routes never create a session."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

import thaiguard.server.server as server
from thaiguard.engine.session_service import SessionService

_NOW = 1_800_000_000.0
_V2_DATA_HEADERS = {
    "X-AIGuard-Contract-Version": "2",
    "X-AIGuard-Key": "synthetic-data-authority",
}


@pytest.fixture
def keyed_client(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "_API_KEY", "synthetic-data-authority")
    monkeypatch.setattr(server, "_BOOT_TOKEN", "synthetic-control-authority")
    monkeypatch.setattr(server, "_authorization_now", lambda: _NOW)
    monkeypatch.setattr(server, "_get_audit_log_dir", lambda: str(tmp_path))
    monkeypatch.setattr(server, "SERVICE", SessionService())
    return TestClient(server.app, base_url="http://localhost")


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_nested_keys(child) for child in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_nested_keys(child) for child in value), set())
    return set()


def test_private_http_v2_session_lifecycle_is_authoritative_and_mapping_minimized(
    keyed_client,
):
    sanitized = keyed_client.post(
        "/api/sanitize",
        headers=_V2_DATA_HEADERS,
        json={"text": "synthetic plain input", "mode": "token"},
    )
    assert sanitized.status_code == 200
    body = sanitized.json()
    backend_session_id = body["session_id"]
    assert server.SERVICE.session_count == 1
    assert not {
        "mapping",
        "mappings",
        "vault",
        "original_text",
        "credentials",
    }.intersection(_nested_keys(body))

    continued = keyed_client.post(
        "/api/reidentify",
        headers=_V2_DATA_HEADERS,
        json={"session_id": backend_session_id, "text": body["sanitized_text"]},
    )
    assert continued.status_code == 200
    assert server.SERVICE.session_count == 1

    unauthorized = keyed_client.delete(
        f"/api/session/{backend_session_id}",
        headers={"X-AIGuard-Contract-Version": "2"},
    )
    assert unauthorized.status_code == 403
    assert unauthorized.json()["error"]["code"] == "control_forbidden"
    assert server.SERVICE.session_count == 1

    authorization = server._make_session_disposal_authorization(
        "synthetic-control-authority",
        backend_session_id,
        now=_NOW,
        nonce=b"synthetic-nonce!",
    )
    disposed = keyed_client.delete(
        f"/api/session/{backend_session_id}",
        headers={
            "X-AIGuard-Contract-Version": "2",
            "X-AIGuard-Token": authorization,
        },
    )
    assert disposed.status_code == 200
    assert disposed.json() == {"deleted": True}
    assert server.SERVICE.session_count == 0

    stale = keyed_client.post(
        "/api/reidentify",
        headers=_V2_DATA_HEADERS,
        json={"session_id": backend_session_id, "text": "synthetic"},
    )
    assert stale.status_code == 404
    assert stale.json()["error"]["code"] == "session_unavailable"


def test_stateless_private_routes_do_not_invent_session_state(keyed_client):
    assert server.SERVICE.session_count == 0
    detected = keyed_client.post(
        "/api/detect",
        headers=_V2_DATA_HEADERS,
        json={"text": "synthetic plain input"},
    )
    guarded = keyed_client.post(
        "/api/guard",
        headers=_V2_DATA_HEADERS,
        json={"text": "synthetic plain input"},
    )
    roundtrip = keyed_client.post(
        "/api/roundtrip",
        headers=_V2_DATA_HEADERS,
        json={
            "text": "synthetic plain input",
            "mode": "token",
            "provider": "fake",
        },
    )
    assert [detected.status_code, guarded.status_code, roundtrip.status_code] == [200, 200, 200]
    assert server.SERVICE.session_count == 0

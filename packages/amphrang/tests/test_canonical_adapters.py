"""Bound SDK adapters use canonical modules and retain their wire boundaries."""

import asyncio
import json

import httpx
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from pii_redactor import ai_client, audit, session_service
from pii_redactor.config import AuditConfig, CoreConfig
from pydantic import ValidationError

import amphrang
from amphrang.proxy import core as proxy_core
from amphrang.proxy import server as proxy_server
from amphrang.server import server as http_server
from amphrang.server.http_v2 import SanitizeResponse, SanitizeWarning


def test_http_adapter_uses_canonical_service_provider_and_audit():
    assert http_server.SessionService is session_service.SessionService
    assert http_server.SERVICE._config is http_server._CORE_CONFIG
    assert http_server._CORE_CONFIG.allow_remote is False
    assert http_server.write_process_log is audit.write_process_log
    assert http_server.get_provider_factories is ai_client.get_provider_factories
    assert (
        http_server.complete_provider_with_retry_policy
        is ai_client.complete_provider_with_retry_policy
    )


def test_http_detection_keeps_snapshot_after_environment_changes(monkeypatch):
    captured = []
    snapshot = CoreConfig(allow_remote=False)
    monkeypatch.setattr(http_server, "_CORE_CONFIG", snapshot)
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "unsupported-after-boot")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setattr(
        http_server,
        "detect_all",
        lambda text, *, config: captured.append(config) or [],
    )
    result = http_server.detect(http_server.DetectRequest(text="synthetic text"))
    assert result["detected_entity_count"] == 0
    assert captured == [snapshot]


def test_http_audit_startup_and_emission_share_snapshot(monkeypatch, tmp_path):
    snapshot = AuditConfig(stdout=True)
    monkeypatch.setattr(http_server, "_AUDIT_CONFIG", snapshot)
    monkeypatch.setenv("AMPHRANG_AUDIT_STDOUT", "0")
    monkeypatch.setattr(
        http_server,
        "_get_audit_log_dir",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected disk access")),
    )
    http_server._check_audit_dir_writable()
    seen = []
    monkeypatch.setattr(http_server, "_get_audit_log_dir", lambda: str(tmp_path))
    monkeypatch.setattr(http_server, "write_process_log", lambda **kwargs: seen.append(kwargs))
    response = http_server.sanitize(http_server.SanitizeRequest(text="โทร 081-234-5678"))
    assert seen and seen[0]["audit_config"] is snapshot
    payload = json.loads(response.body)
    assert "mapping" not in payload
    http_server.SERVICE.drop(payload["session_id"])


def test_http_sensitive_warning_uses_existing_field_and_contract_header(monkeypatch):
    monkeypatch.setattr(http_server, "_AUDIT_CONFIG", AuditConfig(stdout=True))
    with TestClient(http_server.app, base_url="http://localhost") as client:
        response = client.post(
            "/api/sanitize",
            json={"text": "ข้อมูลพันธุกรรม"},
            headers={"X-Amphrang-Contract-Version": "2"},
        )
    assert response.status_code == 200
    assert response.headers["X-Amphrang-Contract-Version"] == "2"
    payload = response.json()
    assert payload["sanitized_text"] == "ข้อมูลพันธุกรรม"
    assert payload["warnings"] == [{"code": "section26:GENETIC", "count": 1}]
    assert payload["section26_categories"] == ["GENETIC"]
    assert "mapping" not in payload
    http_server.SERVICE.drop(payload["session_id"])


def test_section26_warning_dtos_keep_closed_codes_counts_and_order():
    for payload in (
        {"code": "section26:SYNTHETIC_UNKNOWN", "count": 1},
        {"code": "section26:HEALTH", "count": 0},
        {"code": "section26:HEALTH", "count": True},
        {"code": "section26:HEALTH", "count": 1, "text": "synthetic"},
    ):
        with pytest.raises(ValidationError):
            SanitizeWarning.model_validate(payload)

    base = {
        "session_id": "synthetic-session",
        "sanitized_text": "synthetic",
        "detected_entity_count": 0,
        "replacement_count": 0,
        "entity_type_counts": {},
        "highlights": [],
        "section26_categories": ["HEALTH"],
        "guard_findings": [],
        "safety": {"status": "pass", "residual_count": 0},
    }
    for codes in (
        ["section26:HEALTH", "section26:HEALTH"],
        ["section26:GENETIC", "section26:HEALTH"],
    ):
        with pytest.raises(ValidationError):
            SanitizeResponse.model_validate(
                {**base, "warnings": [{"code": code, "count": 1} for code in codes]}
            )


def test_http_roundtrip_captures_config_across_retries_and_reports_warning(monkeypatch):
    monkeypatch.setattr(http_server, "_AUDIT_CONFIG", AuditConfig(stdout=True))
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    config = http_server._CORE_CONFIG
    captures = {"mask": [], "guard": [], "restore": []}
    operations = {
        "mask": ("sanitize_stateless", http_server.sanitize_stateless),
        "guard": ("enforce_outbound_policy", http_server.enforce_outbound_policy),
        "restore": ("restore_stateless", http_server.restore_stateless),
    }
    for name, (attribute, original) in operations.items():

        def capture(*args, config, name=name, original=original, **kwargs):
            captures[name].append(config)
            return original(*args, config=config, **kwargs)

        monkeypatch.setattr(http_server, attribute, capture)

    attempts = []

    class Provider:
        def complete(self, system, user, *, timeout=30.0):
            attempts.append(user)
            monkeypatch.setenv("AMPHRANG_NER_ENGINE", "unsupported-between-retries")
            if len(attempts) == 1:
                raise httpx.ReadTimeout("synthetic timeout")
            return user

    monkeypatch.setitem(http_server._PROVIDER_FACTORIES, "synthetic-retry", Provider)
    monkeypatch.setattr(ai_client, "_sleep", lambda _: None)
    response = http_server.roundtrip(
        http_server.RoundtripRequest(
            text="โรค โทร 081-234-5678", mode="token", provider="synthetic-retry"
        )
    )
    payload = json.loads(response.body)
    assert len(attempts) == 2
    assert len(captures["mask"]) == 1 and len(captures["restore"]) == 1
    assert len(captures["guard"]) == 2
    assert all(value is config for values in captures.values() for value in values)
    assert payload["restored_text"] == "โรค โทร 081-234-5678"
    assert payload["warnings"] == [{"code": "section26:HEALTH", "count": 1}]
    assert payload["restoration"]["status"] == "complete"
    assert "mapping" not in payload


def test_proxy_captures_snapshot_and_warns_without_changing_openai_schema(monkeypatch):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    seen = []
    original_mask = amphrang._anonymize_with_config
    original_restore = amphrang._restore_with_config

    def mask(*args, config, **kwargs):
        seen.append(config)
        return original_mask(*args, config=config, **kwargs)

    def restore(*args, config, **kwargs):
        seen.append(config)
        return original_restore(*args, config=config, **kwargs)

    monkeypatch.setattr(amphrang, "_anonymize_with_config", mask)
    monkeypatch.setattr(amphrang, "_restore_with_config", restore)

    def upstream(request):
        masked = json.loads(request.content)["messages"][0]["content"]
        assert "081-234-5678" not in masked
        assert "โรค" in masked
        return httpx.Response(200, json={"choices": [{"message": {"content": masked}}]})

    app = proxy_server.create_app(
        "https://synthetic.example",
        frozenset({"test-model"}),
        transport=httpx.MockTransport(upstream),
    )
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "unsupported-after-boot")
    with pytest.warns(UserWarning) as warnings:
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "โรค โทร 081-234-5678"}],
                },
            )
    assert response.status_code == 200
    assert response.json() == {"choices": [{"message": {"content": "โรค โทร 081-234-5678"}}]}
    assert seen and all(config is seen[0] for config in seen)
    assert seen[0] == CoreConfig(allow_remote=False)
    assert [str(item.message) for item in warnings] == ["section26:HEALTH"]


def test_proxy_guard_uses_same_snapshot(monkeypatch):
    snapshot = CoreConfig(allow_remote=False)
    captured = []
    real_enforce = proxy_core.enforce_outbound_policy

    def enforce(*args, config, **kwargs):
        captured.append(config)
        return real_enforce(*args, config=config, **kwargs)

    monkeypatch.setattr(proxy_core, "enforce_outbound_policy", enforce)
    proxy_core._sanitize_chat_request_with_config(
        {"messages": [{"role": "user", "content": "hello"}] * 2, "temperature": 0.5},
        salt="synthetic-salt",
        config=snapshot,
    )
    assert captured and all(config is snapshot for config in captured)


def test_mcp_captures_snapshot_and_preserves_plaintext_success(monkeypatch):
    pytest.importorskip("mcp")
    from amphrang import mcp

    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    assert mcp.SessionService is session_service.SessionService
    server = mcp.build_server()
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "unsupported-after-boot")

    async def invoke():
        masked = (
            await server.call_tool("sanitize", {"text": "โรค โทร 081-234-5678"})
        ).structured_content
        assert "mapping" not in masked
        assert "081-234-5678" not in masked["sanitized_text"]
        assert masked["warnings"] == ["section26:HEALTH"]
        restored = (
            await server.call_tool(
                "reidentify",
                {"session_handle": masked["session_handle"], "text": masked["sanitized_text"]},
            )
        ).structured_content
        assert restored["restored_text"] == "โรค โทร 081-234-5678"
        report = (await server.call_tool("pdpa_analyze", {"text": "โรค"})).structured_content
        assert report["section26"] and all("text" not in hit for hit in report["section26"])
        await server.call_tool("close_session", {"session_handle": masked["session_handle"]})

    asyncio.run(invoke())


def test_mcp_malformed_key_errors_do_not_echo_credentials():
    pytest.importorskip("mcp")
    from amphrang import mcp

    with pytest.raises(ValueError) as caught:
        mcp.parse_caller_keys("SYNTHETIC_PRIVATE_BAD_KEY")
    assert "SYNTHETIC_PRIVATE_BAD_KEY" not in str(caught.value)

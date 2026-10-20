"""Proxy CLI configuration is fail-closed before the server starts."""

import pytest

from amphrang.proxy.__main__ import main


@pytest.mark.parametrize("raw", [None, "", " ,  , "])
def test_cli_refuses_missing_or_empty_model_allowlist(monkeypatch, capsys, raw):
    monkeypatch.setenv("AMPHRANG_PROXY_UPSTREAM", "https://upstream.example")
    if raw is None:
        monkeypatch.delenv("AMPHRANG_PROXY_MODELS", raising=False)
    else:
        monkeypatch.setenv("AMPHRANG_PROXY_MODELS", raw)

    assert main([]) == 1
    assert "AMPHRANG_PROXY_MODELS is not set or empty" in capsys.readouterr().err


def test_cli_passes_trimmed_deduplicated_immutable_allowlist(monkeypatch):
    import uvicorn

    import amphrang.proxy.server as proxy_server

    captured = {}
    app = object()

    def fake_create_app(**kwargs):
        captured["create"] = kwargs
        return app

    def fake_run(received_app, **kwargs):
        captured["run"] = (received_app, kwargs)

    monkeypatch.setenv("AMPHRANG_PROXY_UPSTREAM", "https://upstream.example")
    monkeypatch.setenv(
        "AMPHRANG_PROXY_MODELS",
        " gpt-test, gpt-4.1-2025-04-14,gpt-test ",
    )
    monkeypatch.setattr(proxy_server, "create_app", fake_create_app)
    monkeypatch.setattr(uvicorn, "run", fake_run)

    assert main(["--port", "8450"]) == 0
    assert captured["create"]["allowed_models"] == frozenset({"gpt-test", "gpt-4.1-2025-04-14"})
    assert captured["run"] == (
        app,
        {"host": "127.0.0.1", "port": 8450, "log_level": "warning"},
    )


def test_cli_refuses_invalid_configured_model(monkeypatch, capsys):
    monkeypatch.setenv("AMPHRANG_PROXY_UPSTREAM", "https://upstream.example")
    monkeypatch.setenv("AMPHRANG_PROXY_MODELS", "gpt-test,081-234-5678")

    assert main([]) == 1
    assert "contains an invalid model identifier" in capsys.readouterr().err

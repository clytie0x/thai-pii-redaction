"""Proxy CLI configuration is fail-closed before the server starts."""

import builtins

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
    uvicorn = pytest.importorskip("uvicorn", reason="optional proxy extra")
    pytest.importorskip("fastapi", reason="optional proxy extra")

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
    pytest.importorskip("uvicorn", reason="optional proxy extra")
    pytest.importorskip("fastapi", reason="optional proxy extra")
    monkeypatch.setenv("AMPHRANG_PROXY_UPSTREAM", "https://upstream.example")
    monkeypatch.setenv("AMPHRANG_PROXY_MODELS", "gpt-test,081-234-5678")

    assert main([]) == 1
    assert "contains an invalid model identifier" in capsys.readouterr().err


def test_cli_reports_missing_proxy_extra_without_starting(monkeypatch, capsys):
    original_import = builtins.__import__

    def without_uvicorn(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("synthetic missing optional package")
        return original_import(name, *args, **kwargs)

    monkeypatch.setenv("AMPHRANG_PROXY_UPSTREAM", "https://upstream.example")
    monkeypatch.setenv("AMPHRANG_PROXY_MODELS", "gpt-test")
    monkeypatch.setattr(builtins, "__import__", without_uvicorn)

    assert main([]) == 1
    assert 'pip install "amphrang[proxy]"' in capsys.readouterr().err

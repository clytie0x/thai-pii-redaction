"""The pip-installed server profile keeps broker-era code inert.

`app.server` still carries the private-backend bootstrap and control-auth
paths from the native-broker product. In this package they must stay dormant:
no broker injects credentials here, so booting without that environment must
yield a plain localhost server with `private_backend` off. This pins the
inert default until the broker residue is removed outright (planned 0.2.x).
"""

import importlib
import sys

import pytest


def test_private_backend_bootstrap_is_inert_without_env(monkeypatch):
    for name in (
        "AIGUARD_PRIVATE_BACKEND_FD",
        "AIGUARD_PRIVATE_BACKEND_KEY_FILE",
        "AIGUARD_PRIVATE_BACKEND_CONTROL_FILE",
    ):
        monkeypatch.delenv(name, raising=False)
    from app import private_backend_bootstrap

    importlib.reload(private_backend_bootstrap)
    assert private_backend_bootstrap.consume_private_backend_credentials() is None


def test_server_boots_with_private_backend_disabled():
    pytest.importorskip("fastapi")
    server = sys.modules.get("app.server")
    if server is None:
        import app.server as server
    assert server.app.state.private_backend is False


def test_server_version_is_not_a_stale_release_literal():
    """An installed wheel has no VERSION file; the fallback chain must end at
    distribution metadata or an honest 0.0.0 — never a bygone release number."""
    pytest.importorskip("fastapi")
    server = sys.modules.get("app.server")
    if server is None:
        import app.server as server
    assert server.__version__ != "3.0.0"

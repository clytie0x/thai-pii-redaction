"""The pip-installed server profile carries no native-broker residue.

`app.server` used to carry dormant private-backend bootstrap, control-auth,
and detector-budget hooks left over from the native-broker product it was
extracted from. Those modules and their call sites are removed outright
(0.2.x item); this pins that they stay gone rather than creeping back in.
"""

import sys

import pytest


def test_private_backend_bootstrap_module_is_gone():
    with pytest.raises(ModuleNotFoundError):
        import amphrang.server.private_backend_bootstrap


def test_native_broker_context_module_is_gone():
    with pytest.raises(ModuleNotFoundError):
        import amphrang.engine.native_broker_context


def test_server_has_no_private_backend_state():
    pytest.importorskip("fastapi")
    server = sys.modules.get("amphrang.server.server")
    if server is None:
        import amphrang.server.server as server
    assert not hasattr(server.app.state, "private_backend")


def test_server_version_is_not_a_stale_release_literal():
    """An installed wheel has no VERSION file; the fallback chain must end at
    distribution metadata or an honest 0.0.0 — never a bygone release number."""
    pytest.importorskip("fastapi")
    server = sys.modules.get("amphrang.server.server")
    if server is None:
        import amphrang.server.server as server
    assert server.__version__ != "3.0.0"

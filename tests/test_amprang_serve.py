"""`amphrang serve` — Tier-0 local UI entry point.

The binding guard is the security-relevant part: the local API's data-plane
key is optional, so a non-loopback bind must be an explicit, keyed choice.
"""

import pytest

from amphrang.serve import check_binding

pytest.importorskip("fastapi")


def test_loopback_binding_is_allowed_without_flags():
    check_binding("127.0.0.1", allow_remote=False, api_key_set=False)
    check_binding("localhost", allow_remote=False, api_key_set=False)


def test_non_loopback_binding_refused_without_allow_remote():
    with pytest.raises(SystemExit, match="refusing to bind"):
        check_binding("0.0.0.0", allow_remote=False, api_key_set=True)


def test_non_loopback_binding_refused_without_api_key():
    with pytest.raises(SystemExit, match="AMPHRANG_API_KEY"):
        check_binding("0.0.0.0", allow_remote=True, api_key_set=False)


def test_non_loopback_binding_allowed_when_explicit_and_keyed():
    check_binding("0.0.0.0", allow_remote=True, api_key_set=True)


def test_demo_page_ships_inside_the_server_package():
    from amphrang.server.server import _demo_page_path

    page = _demo_page_path()
    assert page.is_file()
    assert page.parent.name == "demo"
    assert page.parent.parent.name == "server"


def test_cli_exposes_serve_subcommand():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "amphrang.cli", "serve", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--no-browser" in result.stdout

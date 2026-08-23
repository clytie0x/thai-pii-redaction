"""`amprang serve` — the zero-build local UI.

Starts the local FastAPI backend with the demo playground enabled and opens
the browser at it, so trying amprang on your own machine is one command::

    pip install "amprang[server]"
    amprang serve

Everything runs in this one process; nothing leaves the machine. The server
binds loopback only unless `--allow-remote` is passed explicitly — the local
API's data-plane authentication is optional (`AMPRANG_API_KEY`), so exposing
it beyond the machine without a key would hand sanitize/reidentify to the
whole network.
"""

from __future__ import annotations

import argparse
import os
import threading
import webbrowser

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def add_serve_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open the playground in a browser",
    )
    parser.add_argument(
        "--no-demo",
        action="store_true",
        help="serve the API only, without the /demo playground page",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help=(
            "permit a non-loopback --host; requires AMPRANG_API_KEY to be set "
            "so the data plane is not open to the network"
        ),
    )


def check_binding(host: str, *, allow_remote: bool, api_key_set: bool) -> None:
    """Refuse a non-loopback bind unless explicitly allowed AND keyed."""
    if host in _LOOPBACK_HOSTS:
        return
    if not allow_remote:
        raise SystemExit(
            f"refusing to bind {host}: this server is local-first. "
            "Pass --allow-remote (and set AMPRANG_API_KEY) if you really "
            "mean to expose it."
        )
    if not api_key_set:
        raise SystemExit(
            f"refusing to bind {host} without AMPRANG_API_KEY: the data "
            "plane would be open to everyone who can reach the port."
        )


def run_serve(args: argparse.Namespace) -> None:
    check_binding(
        args.host,
        allow_remote=args.allow_remote,
        api_key_set=bool(os.environ.get("AMPRANG_API_KEY")),
    )
    if not args.no_demo:
        os.environ["AMPRANG_DEMO"] = "1"

    try:
        import uvicorn

        from amprang.server.server import app
    except ImportError:
        raise SystemExit(
            "amprang serve needs the server extra: pip install 'amprang[server]'"
        ) from None

    url = f"http://{args.host}:{args.port}" + ("" if args.no_demo else "/demo")
    print(f"amprang serving on {url} (Ctrl+C to stop)")
    if not args.no_browser:
        # Fire after uvicorn has had a moment to bind; a missed open is only
        # a convenience loss, never an error.
        opener = threading.Timer(1.0, webbrowser.open, [url])
        opener.daemon = True
        opener.start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="amprang-serve",
        description="Run the local amprang backend with the demo playground",
    )
    add_serve_arguments(parser)
    run_serve(parser.parse_args())


if __name__ == "__main__":
    main()

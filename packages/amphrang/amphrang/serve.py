"""`amphrang serve` — run the local FastAPI backend and open a browser to its API docs.

Binds loopback only unless `--allow-remote` is passed: data-plane auth (`AMPHRANG_API_KEY`) is
optional, so an unkeyed non-loopback bind would expose sanitize/reidentify to the network.
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
        help="do not open the API docs in a browser",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help=(
            "permit a non-loopback --host; requires AMPHRANG_API_KEY to be set "
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
            "Pass --allow-remote (and set AMPHRANG_API_KEY) if you really "
            "mean to expose it."
        )
    if not api_key_set:
        raise SystemExit(
            f"refusing to bind {host} without AMPHRANG_API_KEY: the data "
            "plane would be open to everyone who can reach the port."
        )


def run_serve(args: argparse.Namespace) -> None:
    check_binding(
        args.host,
        allow_remote=args.allow_remote,
        api_key_set=bool(os.environ.get("AMPHRANG_API_KEY")),
    )
    try:
        import uvicorn

        from amphrang.server.server import app
    except ImportError:
        raise SystemExit(
            "amphrang serve needs the server extra: pip install 'amphrang[server]'"
        ) from None

    url = f"http://{args.host}:{args.port}"
    print(f"amphrang serving on {url} (Ctrl+C to stop)")
    if not args.no_browser:
        # Fire after uvicorn has had a moment to bind; a missed open is not an error.
        opener = threading.Timer(1.0, webbrowser.open, [url])
        opener.daemon = True
        opener.start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="amphrang-serve",
        description="Run the local amphrang backend",
    )
    add_serve_arguments(parser)
    run_serve(parser.parse_args())


if __name__ == "__main__":
    main()

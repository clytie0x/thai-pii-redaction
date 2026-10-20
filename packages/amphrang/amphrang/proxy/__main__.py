"""Run the sanitizing proxy: ``python -m amphrang.proxy`` or ``amphrang-proxy``.

Loopback only in v1 — the proxy carries a plaintext↔masked boundary, so
exposing it beyond the machine is a Phase 3 (auth) concern. The upstream is
configured by environment, never by the request:

    AMPHRANG_PROXY_UPSTREAM       e.g. https://api.openai.com (required)
    AMPHRANG_PROXY_UPSTREAM_KEY   bearer key for the upstream (optional)
    AMPHRANG_PROXY_MODELS         comma-separated exact model allowlist (required)
"""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="amphrang-proxy", description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=8400)
    args = parser.parse_args(argv)

    upstream = os.environ.get("AMPHRANG_PROXY_UPSTREAM", "").strip()
    if not upstream:
        print(
            "amphrang-proxy: AMPHRANG_PROXY_UPSTREAM is not set "
            "(e.g. https://api.openai.com); refusing to start",
            file=sys.stderr,
        )
        return 1

    allowed_models = frozenset(
        model.strip()
        for model in os.environ.get("AMPHRANG_PROXY_MODELS", "").split(",")
        if model.strip()
    )
    if not allowed_models:
        print(
            "amphrang-proxy: AMPHRANG_PROXY_MODELS is not set or empty; refusing to start",
            file=sys.stderr,
        )
        return 1

    try:
        import uvicorn

        from amphrang.proxy.server import create_app
    except ImportError:
        print(
            'amphrang-proxy needs the proxy extra: pip install "amphrang[proxy]"',
            file=sys.stderr,
        )
        return 1

    try:
        app = create_app(
            upstream_base_url=upstream,
            allowed_models=allowed_models,
            upstream_api_key=os.environ.get("AMPHRANG_PROXY_UPSTREAM_KEY") or None,
        )
    except ValueError:
        print(
            "amphrang-proxy: AMPHRANG_PROXY_MODELS contains an invalid model identifier; "
            "refusing to start",
            file=sys.stderr,
        )
        return 1
    print(f"amphrang-proxy: 127.0.0.1:{args.port} -> {upstream} (loopback only)")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

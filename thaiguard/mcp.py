"""MCP adapter — the thaiguard toolset for AI agents.

Run locally over stdio (full local privacy — text never leaves the machine,
and stdio is only reachable by the parent process, so no auth is needed)::

    thaiguard-mcp

or as a shared HTTP endpoint (hosted convenience tier — callers' text reaches
this server; state is one in-memory vault with a TTL, nothing on disk). HTTP
is reachable by anything that can open the port, so every caller must
present a per-caller key — there is no unauthenticated fallback::

    AIGUARD_MCP_KEYS="agent-a:key-a,agent-b:key-b" \\
        thaiguard-mcp --transport http --host 127.0.0.1 --port 8300

Design rule (see docs/decisions/0003-mcp-no-plaintext-mapping.md): a tool
result always enters the calling model's context, so no tool here ever
returns the pseudonym→original mapping. ``sanitize`` returns an opaque
``session_handle`` to a server-side in-memory vault; ``reidentify`` accepts
that handle. The plaintext-mapping form exists only in the in-process Python
facade, where the caller is code rather than a model context.
"""

from __future__ import annotations

import hmac
import os
from typing import Any

try:
    from mcp.server import MCPServer
except ImportError as _error:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "the MCP adapter needs the 'mcp' package: pip install 'thaiguard[mcp]'"
    ) from _error

import thaiguard
from thaiguard.engine.guard.injection import scan_injection
from thaiguard.engine.ingest.text_cleaner import clean_length_preserving
from thaiguard.engine.session_service import (
    OutboundLeakError,
    SessionExpiredError,
    SessionService,
    _identity_finalize,
)

_SESSION_CAP = 64
_SESSION_TTL_S = 1800


def _safe_leak_error(error: OutboundLeakError) -> ValueError:
    # Value-free by construction: leak_types are fixed category labels.
    return ValueError(f"sanitize blocked: residual risk {sorted(error.leak_types)}")


def parse_caller_keys(raw: str) -> dict[str, str]:
    """Parse ``AIGUARD_MCP_KEYS`` ("caller_id:key,caller_id2:key2") into {key: caller_id}."""
    keys: dict[str, str] = {}
    for entry in filter(None, (item.strip() for item in raw.split(","))):
        caller_id, sep, secret = entry.partition(":")
        if not sep or not caller_id or not secret:
            raise ValueError(f"malformed AIGUARD_MCP_KEYS entry {entry!r}: expected caller_id:key")
        keys[secret] = caller_id
    return keys


class _CallerKeyMiddleware:
    """Fail-closed per-caller bearer-key gate for the shared HTTP transport.

    Every request must carry ``Authorization: Bearer <key>`` matching one of
    the configured per-caller keys — there is no unauthenticated path, unlike
    the local FastAPI server's optional ``AIGUARD_API_KEY``. An MCP HTTP
    endpoint hands the PII guard to any caller who can reach the port, so it
    stays closed until a caller proves who it is.
    """

    def __init__(self, app: Any, keys_by_secret: dict[str, str]) -> None:
        self._app = app
        self._keys_by_secret = keys_by_secret

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        header = headers.get(b"authorization", b"").decode("latin-1")
        prefix = "bearer "
        supplied = header[len(prefix) :] if header.lower().startswith(prefix) else ""
        caller_id = next(
            (
                owner
                for secret, owner in self._keys_by_secret.items()
                if supplied and hmac.compare_digest(supplied, secret)
            ),
            None,
        )
        if caller_id is None:
            body = b'{"error":"invalid_token","error_description":"a valid Authorization: Bearer <key> is required"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (b"www-authenticate", b"Bearer"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        scope["state"] = {**scope.get("state", {}), "caller_id": caller_id}
        await self._app(scope, receive, send)


def build_server(
    *,
    session_cap: int = _SESSION_CAP,
    session_ttl_s: int = _SESSION_TTL_S,
) -> MCPServer:
    """Create the thaiguard MCP server with its own in-memory session vault."""
    service = SessionService(cap=session_cap, ttl_s=session_ttl_s)
    server = MCPServer(
        name="thaiguard",
        version=thaiguard.__version__,
        instructions=(
            "Thai PII guard. Call sanitize before sending Thai text to any "
            "external model or service, send only sanitized_text onward, and "
            "call reidentify with the session_handle to restore the reply. "
            "Reidentified output contains real personal data: show it only "
            "to the end user, never forward it to another service or tool."
        ),
    )

    @server.tool(
        description=(
            "Detect Thai PII in text. Returns each entity's type, character "
            "span, and matched text (spans index into the input)."
        )
    )
    def detect_pii(text: str) -> dict[str, Any]:
        entities = thaiguard.detect(text)
        counts: dict[str, int] = {}
        for entity in entities:
            counts[entity.data_type] = counts.get(entity.data_type, 0) + 1
        return {
            "entities": [
                {
                    "data_type": entity.data_type,
                    "start": entity.span[0],
                    "end": entity.span[1],
                    "text": entity.original_text,
                }
                for entity in entities
            ],
            "entity_type_counts": counts,
        }

    @server.tool(
        description=(
            "Mask Thai PII before text goes to an external model or service. "
            "mode 'token' emits placeholders, 'surrogate' emits realistic "
            "fake values. Returns sanitized_text plus an opaque "
            "session_handle for reidentify — the real values stay in this "
            "server's memory and are never returned. Pass a previous "
            "session_handle to keep the same entity→pseudonym assignments "
            "across turns. Fails with an error (never a partial mask) when "
            "residual PII would remain."
        )
    )
    def sanitize(
        text: str,
        mode: str = "token",
        session_handle: str | None = None,
    ) -> dict[str, Any]:
        try:
            outcome = service.sanitize_transaction(
                text,
                mode=mode,
                session_id=session_handle,
                detection_text=clean_length_preserving(text),
                finalize=_identity_finalize,
            )
        except OutboundLeakError as error:
            raise _safe_leak_error(error) from None
        except SessionExpiredError:
            raise ValueError("session_handle expired or unknown") from None
        return {
            "sanitized_text": outcome.sanitized_text,
            "session_handle": outcome.session_id,
            "entity_type_counts": dict(outcome.entity_type_counts),
            "warnings": list(outcome.warnings),
        }

    @server.tool(
        description=(
            "Restore the original values into a reply that contains "
            "pseudonyms from a previous sanitize call. The output contains "
            "real personal data: present it to the end user only — never "
            "forward it to another service, tool, or model."
        )
    )
    def reidentify(session_handle: str, text: str) -> dict[str, Any]:
        try:
            outcome = service.restore(session_handle, text)
        except SessionExpiredError:
            raise ValueError("session_handle expired or unknown") from None
        return {
            "restored_text": outcome.restored_text,
            "replaced_count": outcome.replaced_count,
            "leftover_count": len(outcome.leftover_tokens),
            "warnings": list(outcome.warnings),
        }

    @server.tool(
        description=(
            "PDPA-oriented risk analysis of Thai text: entity counts, "
            "Section 26 sensitive-category signals, and a re-identification "
            "risk score. The result carries no raw values."
        )
    )
    def pdpa_analyze(text: str) -> dict[str, Any]:
        return thaiguard.analyze(text)

    @server.tool(
        description=(
            "Scan text for prompt-injection signals (Thai and English). "
            "Warn-only: returns categories and severities, never blocks."
        )
    )
    def guard_prompt(text: str) -> dict[str, Any]:
        findings = scan_injection(text)
        return {
            "flagged": bool(findings),
            "findings": [
                {"category": finding.category, "severity": finding.severity} for finding in findings
            ],
        }

    @server.tool(
        description=(
            "Drop a sanitize session and its in-memory mapping immediately "
            "instead of waiting for the idle timeout."
        )
    )
    def close_session(session_handle: str) -> dict[str, Any]:
        return {"closed": service.drop(session_handle)}

    return server


def run_http(server: MCPServer, *, host: str, port: int, caller_keys: dict[str, str]) -> None:
    """Serve ``server`` over streamable-http behind the per-caller key gate.

    Bypasses ``MCPServer.run("streamable-http", ...)``: the SDK's own auth
    layer is OAuth-shaped (``AuthSettings`` requires an ``issuer_url`` and
    stands up authorization-server discovery routes), which is the wrong
    protocol for a static per-caller shared secret. Wrapping the Starlette
    app with a small bearer-key ASGI middleware instead keeps the surface to
    exactly one check: is this caller's key valid.
    """
    import uvicorn

    starlette_app = server.streamable_http_app(host=host)
    starlette_app.add_middleware(_CallerKeyMiddleware, keys_by_secret=caller_keys)
    uvicorn.run(starlette_app, host=host, port=port, log_level="info")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="thaiguard-mcp",
        description="thaiguard MCP server (Thai PII guard toolset for AI agents)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="stdio for a local agent (default); http for a shared endpoint",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8300)
    args = parser.parse_args()

    server = build_server()
    if args.transport == "stdio":
        server.run("stdio")
        return

    try:
        caller_keys = parse_caller_keys(os.environ.get("AIGUARD_MCP_KEYS", ""))
    except ValueError as error:
        raise SystemExit(str(error)) from None
    if not caller_keys:
        raise SystemExit(
            "refusing to start --transport http without AIGUARD_MCP_KEYS: a "
            "shared HTTP endpoint hands the PII guard to any caller who can "
            'reach the port. Set AIGUARD_MCP_KEYS="caller_id:key[,caller_id:key...]" '
            "with one key per caller."
        )
    run_http(server, host=args.host, port=args.port, caller_keys=caller_keys)


if __name__ == "__main__":
    main()

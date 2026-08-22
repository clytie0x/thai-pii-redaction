"""MCP adapter — the thaiguard toolset for AI agents.

Run locally over stdio (full local privacy — text never leaves the machine)::

    thaiguard-mcp

or as a shared HTTP endpoint (hosted convenience tier — callers' text reaches
this server; state is one in-memory vault with a TTL, nothing on disk)::

    thaiguard-mcp --transport http --host 127.0.0.1 --port 8300

Design rule (see docs/decisions/0003-mcp-no-plaintext-mapping.md): a tool
result always enters the calling model's context, so no tool here ever
returns the pseudonym→original mapping. ``sanitize`` returns an opaque
``session_handle`` to a server-side in-memory vault; ``reidentify`` accepts
that handle. The plaintext-mapping form exists only in the in-process Python
facade, where the caller is code rather than a model context.
"""

from __future__ import annotations

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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="ththaiguard-mcp",
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
    else:
        server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()

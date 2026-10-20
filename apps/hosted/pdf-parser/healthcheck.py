"""No-network health probe for the parser Unix socket."""

from __future__ import annotations

import asyncio
import os
import signal
import struct
from pathlib import Path

from protocol import MAX_RESPONSE_BYTES, PROTOCOL_VERSION, decode_json, encode_json


STATE = Path("/work/aift-health-failures")
THRESHOLD = 3


async def check() -> None:
    reader, writer = await asyncio.wait_for(
        asyncio.open_unix_connection("/run/aiguard-pdf/parser.sock"),
        timeout=1.0,
    )
    try:
        writer.write(
            encode_json(
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "operation": "health",
                    "body_bytes": 0,
                },
                maximum=4_096,
            )
        )
        await writer.drain()
        length = struct.unpack(">I", await reader.readexactly(4))[0]
        if not 1 <= length <= MAX_RESPONSE_BYTES:
            raise RuntimeError("parser health frame length is invalid")
        value = decode_json(await reader.readexactly(length), maximum=MAX_RESPONSE_BYTES)
        if value != {"ok": True, "protocol_version": 1, "status": "ready"}:
            raise RuntimeError("parser health response is invalid")
    finally:
        writer.close()
        await writer.wait_closed()


def _fail() -> int:
    try:
        failures = int(STATE.read_text(encoding="ascii")) + 1
    except (OSError, ValueError):
        failures = 1
    try:
        STATE.write_text(str(failures), encoding="ascii")
    except OSError:
        pass
    if failures >= THRESHOLD:
        os.kill(1, signal.SIGTERM)
    return 1


def main() -> int:
    try:
        asyncio.run(check())
        STATE.unlink(missing_ok=True)
        return 0
    except Exception:
        return _fail()


if __name__ == "__main__":
    raise SystemExit(main())

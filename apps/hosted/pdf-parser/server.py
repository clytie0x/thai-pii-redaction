"""Single-job secretless Unix-socket PDF parser service."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import signal
import struct
from pathlib import Path

from protocol import (
    MAX_HEADER_BYTES,
    MAX_PDF_BYTES,
    MAX_RESPONSE_BYTES,
    PROTOCOL_VERSION,
    ProtocolError,
    decode_json,
    encode_json,
    request_header,
    validated_result,
)

SOCKET_PATH = Path("/run/aiguard-pdf/parser.sock")
WORK_DIRECTORY = Path("/work")
SCENARIO_DIRECTORY = Path("/app/scenarios")
SCENARIO_REGISTRY = {
    "hr-resume-pdf-structured-v1": {
        "filename": "hr-resume-pdf-structured-v1.pdf",
        "sha256": "57ffcd9cddfe5abbe3b5b276ad93d22a549d386f01967344315a97cbafc51e6c",
        "registry_revision": "synthetic-document-registry-v1",
        "title": "เรซูเม่ภาษาไทยสมมติ",
    }
}
JOB_LOCK: asyncio.Lock | None = None
CONNECTION_SLOTS: asyncio.Semaphore | None = None
HEADER_TIMEOUT_SECONDS = 1.0
BODY_TIMEOUT_SECONDS = 10.0
PARSE_TIMEOUT_SECONDS = 10.0


class ParserUnavailable(RuntimeError):
    """The isolated child did not produce a trusted bounded result."""


async def _read_exact(reader: asyncio.StreamReader, count: int) -> bytes:
    try:
        return await reader.readexactly(count)
    except (asyncio.IncompleteReadError, ConnectionError):
        raise ProtocolError("frame ended early") from None


async def _read_json_frame(reader: asyncio.StreamReader) -> dict[str, object]:
    length = struct.unpack(">I", await _read_exact(reader, 4))[0]
    if not 1 <= length <= MAX_HEADER_BYTES:
        raise ProtocolError("header length is invalid")
    return decode_json(await _read_exact(reader, length), maximum=MAX_HEADER_BYTES)


async def _send(writer: asyncio.StreamWriter, value: dict[str, object]) -> None:
    writer.write(encode_json(value, maximum=MAX_RESPONSE_BYTES))
    await writer.drain()


async def _spool(
    reader: asyncio.StreamReader,
    *,
    declared: int,
    path: Path,
) -> str:
    digest = hashlib.sha256()
    remaining = declared
    with path.open("xb") as stream:
        while remaining:
            chunk = await _read_exact(reader, min(64 * 1024, remaining))
            stream.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


async def _run_worker(source_path: Path, output_path: Path) -> dict[str, object]:
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/env",
        "-i",
        "HOME=/work",
        "LANG=C.UTF-8",
        "PATH=/usr/local/bin:/usr/bin:/bin",
        "PYTHONUTF8=1",
        "PYTHONDONTWRITEBYTECODE=1",
        "PYTHONUNBUFFERED=1",
        "python",
        "/app/worker.py",
        str(source_path),
        str(output_path),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        returncode = await asyncio.wait_for(process.wait(), timeout=PARSE_TIMEOUT_SECONDS)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    if returncode != 0:
        raise ParserUnavailable()
    try:
        payload = output_path.read_bytes()
    except OSError:
        raise ParserUnavailable() from None
    if not payload or len(payload) > MAX_RESPONSE_BYTES:
        raise ParserUnavailable()
    try:
        value = decode_json(payload, maximum=MAX_RESPONSE_BYTES)
    except ProtocolError:
        raise ParserUnavailable() from None
    if not isinstance(value, dict):
        raise ParserUnavailable()
    return value


def _scenario_path(scenario_id: str) -> tuple[Path, dict[str, str]]:
    value = SCENARIO_REGISTRY.get(scenario_id)
    if value is None:
        raise ProtocolError("scenario identifier is unknown")
    path = SCENARIO_DIRECTORY / value["filename"]
    if not path.is_file():
        raise ParserUnavailable()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != value["sha256"]:
        raise ParserUnavailable()
    return path, value


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    spool_path: Path | None = None
    output_path: Path | None = None
    acquired = False
    connection_acquired = False
    try:
        if CONNECTION_SLOTS is None or CONNECTION_SLOTS.locked():
            await _send(writer, {"ok": False, "code": "document_busy"})
            return
        await CONNECTION_SLOTS.acquire()
        connection_acquired = True
        header = request_header(
            await asyncio.wait_for(
                _read_json_frame(reader),
                timeout=HEADER_TIMEOUT_SECONDS,
            )
        )
        operation = header["operation"]
        if operation == "health":
            await _send(
                writer,
                {"ok": True, "protocol_version": PROTOCOL_VERSION, "status": "ready"},
            )
            return
        if JOB_LOCK is None or JOB_LOCK.locked():
            await _send(writer, {"ok": False, "code": "document_busy"})
            return
        await JOB_LOCK.acquire()
        acquired = True
        scenario: dict[str, str] | None = None
        if operation == "parse_scenario":
            source_path, scenario = _scenario_path(str(header["scenario_id"]))
        else:
            # This admission frame is the Core-before-body privacy gate. Core
            # does not consume the ASGI request stream until it receives it.
            await _send(writer, {"ok": True, "status": "ready"})
            spool_path = WORK_DIRECTORY / f"job-{secrets.token_hex(16)}.pdf"
            digest = await asyncio.wait_for(
                _spool(
                    reader,
                    declared=int(header["body_bytes"]),
                    path=spool_path,
                ),
                timeout=BODY_TIMEOUT_SECONDS,
            )
            if spool_path.stat().st_size > MAX_PDF_BYTES:
                raise ProtocolError("document body length is invalid")
            source_path = spool_path
        output_path = WORK_DIRECTORY / f"result-{secrets.token_hex(16)}.json"
        worker_response = await _run_worker(source_path, output_path)
        if worker_response.get("ok") is not True:
            if set(worker_response) != {"ok", "code"}:
                raise ParserUnavailable()
            code = worker_response.get("code")
            if code not in {
                "document_unsupported",
                "pdf_text_layer_required",
                "pdf_visual_content_unsupported",
                "document_too_complex",
            }:
                raise ParserUnavailable()
            await _send(writer, {"ok": False, "code": code})
            return
        if set(worker_response) != {"ok", "result"} or not isinstance(
            worker_response.get("result"), dict
        ):
            raise ParserUnavailable()
        expected_source_sha256 = (
            digest if operation == "parse_document" else str(scenario["sha256"])
        )
        result = validated_result(
            worker_response["result"],
            expected_source_sha256=expected_source_sha256,
        )
        if scenario is not None:
            result["scenario"] = {
                "scenario_id": str(header["scenario_id"]),
                "title": scenario["title"],
                "registry_revision": scenario["registry_revision"],
            }
        await _send(writer, {"ok": True, "result": result})
    except (ParserUnavailable, asyncio.TimeoutError):
        await _send(writer, {"ok": False, "code": "document_parser_unavailable"})
    except (ProtocolError, OSError, ValueError):
        await _send(writer, {"ok": False, "code": "document_unsupported"})
    except Exception:
        await _send(writer, {"ok": False, "code": "document_parser_unavailable"})
    finally:
        cleanup_failed = False
        for path in (spool_path, output_path):
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True
        if cleanup_failed:
            # Continuing would make the privacy and one-job boundary false. Let
            # the container supervisor restart a clean private tmpfs instead.
            os._exit(70)
        if acquired and JOB_LOCK is not None:
            JOB_LOCK.release()
        if connection_acquired and CONNECTION_SLOTS is not None:
            CONNECTION_SLOTS.release()
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, BrokenPipeError):
            pass


async def main() -> None:
    global CONNECTION_SLOTS, JOB_LOCK
    if any(key for key in os.environ if key not in {"HOME", "HOSTNAME", "LANG", "PATH", "PYTHONUTF8", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE"}):
        raise RuntimeError("pdf-parser received an unapproved environment variable")
    SOCKET_PATH.parent.mkdir(mode=0o770, parents=True, exist_ok=True)
    WORK_DIRECTORY.mkdir(mode=0o700, parents=True, exist_ok=True)
    SOCKET_PATH.unlink(missing_ok=True)
    JOB_LOCK = asyncio.Lock()
    CONNECTION_SLOTS = asyncio.Semaphore(4)
    server = await asyncio.start_unix_server(_handle, path=str(SOCKET_PATH), backlog=4)
    os.chmod(SOCKET_PATH, 0o660)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stop.set)
    async with server:
        await stop.wait()
    SOCKET_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    asyncio.run(main())

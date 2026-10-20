"""Strict streaming Core client for the secretless PDF parser socket."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import struct
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path


PROTOCOL_VERSION = 1
MAX_HEADER_BYTES = 4_096
MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
MAX_BODY_MESSAGES = 1_024
DEFAULT_SOCKET_PATH = Path("/run/aiguard-pdf/parser.sock")
PARSER_REVISION = "aiguard-pdf-parser-v1"
EXTRACTION_REVISION = "pdfplumber-lines-v1"
SEGMENTATION_REVISION = "immutable-lines-v1"
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SCENARIO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_REVISION_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_PARSER_CODES = frozenset(
    {
        "document_busy",
        "document_parser_unavailable",
        "document_unsupported",
        "pdf_text_layer_required",
        "pdf_visual_content_unsupported",
        "document_too_complex",
    }
)


class PDFParserError(RuntimeError):
    """A fixed value-free parser boundary failure."""

    def __init__(self, code: str = "document_parser_unavailable"):
        self.code = code if code in _PARSER_CODES else "document_parser_unavailable"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class DocumentSegment:
    page: int
    segment_id: str
    text: str = field(repr=False)


@dataclass(slots=True)
class ParsedDocument:
    source_pdf_sha256: str = field(repr=False)
    parser_revision: str
    extraction_revision: str
    segmentation_revision: str
    page_count: int
    character_count: int
    segment_count: int
    omitted_visual_page_numbers: tuple[int, ...]
    segments: list[DocumentSegment] = field(repr=False)
    segment_manifest_sha256: str = field(repr=False)
    extracted_text: str = field(repr=False)
    scenario: dict[str, str] | None

    def clear(self) -> None:
        self.source_pdf_sha256 = ""
        self.segment_manifest_sha256 = ""
        self.extracted_text = ""
        self.segments.clear()


class PDFParserClient:
    """Acquire parser capacity before consuming any caller PDF body bytes."""

    def __init__(
        self,
        socket_path: Path = DEFAULT_SOCKET_PATH,
        *,
        connect_timeout: float = 1.0,
        body_timeout: float = 11.0,
        result_timeout: float = 11.0,
    ):
        self._socket_path = socket_path
        self._connect_timeout = connect_timeout
        self._body_timeout = body_timeout
        self._result_timeout = result_timeout

    async def parse_scenario(self, scenario_id: str) -> ParsedDocument:
        if (
            not isinstance(scenario_id, str)
            or not scenario_id.isascii()
            or not 1 <= len(scenario_id.encode("ascii")) <= 80
        ):
            raise PDFParserError("document_unsupported")
        reader, writer = await self._open()
        try:
            await self._write_header(
                writer,
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "operation": "parse_scenario",
                    "body_bytes": 0,
                    "scenario_id": scenario_id,
                },
            )
            response = await asyncio.wait_for(
                self._read_frame(reader), timeout=self._result_timeout
            )
            return _parsed_response(response, expected_source_sha256=None)
        except PDFParserError:
            raise
        except (OSError, ConnectionError, asyncio.TimeoutError):
            raise PDFParserError() from None
        finally:
            await self._close(writer)

    async def parse_document(
        self,
        receive: Callable[[], Awaitable[dict]],
        *,
        body_bytes: int,
        source_kind: str,
    ) -> ParsedDocument:
        if type(body_bytes) is not int or not 1 <= body_bytes <= MAX_PDF_BYTES:
            raise PDFParserError("document_unsupported")
        if source_kind not in {"standard", "priority"}:
            raise PDFParserError("document_unsupported")
        reader, writer = await self._open()
        digest = hashlib.sha256()
        try:
            await self._write_header(
                writer,
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "operation": "parse_document",
                    "body_bytes": body_bytes,
                    "source_kind": source_kind,
                },
            )
            admission = await asyncio.wait_for(
                self._read_frame(reader), timeout=self._connect_timeout
            )
            _require_admission(admission)

            remaining = body_bytes
            more_body = True
            signature: bytearray | None = bytearray()
            message_count = 0
            async with asyncio.timeout(self._body_timeout):
                while more_body:
                    message_count += 1
                    if message_count > MAX_BODY_MESSAGES:
                        raise PDFParserError("document_unsupported")
                    message = await receive()
                    if message.get("type") != "http.request":
                        raise PDFParserError()
                    chunk = message.get("body", b"")
                    chunk_more = message.get("more_body", False)
                    if (
                        not isinstance(chunk, bytes)
                        or len(chunk) > remaining
                        or type(chunk_more) is not bool
                    ):
                        raise PDFParserError("document_unsupported")
                    if chunk:
                        digest.update(chunk)
                        remaining -= len(chunk)
                        if signature is not None:
                            needed = 5 - len(signature)
                            signature.extend(chunk[:needed])
                            remainder = chunk[needed:]
                            if len(signature) == 5:
                                if signature != b"%PDF-":
                                    raise PDFParserError("document_unsupported")
                                writer.write(signature)
                                signature = None
                                if remainder:
                                    writer.write(remainder)
                        else:
                            writer.write(chunk)
                        await writer.drain()
                    more_body = chunk_more
            if remaining != 0 or signature is not None:
                raise PDFParserError("document_unsupported")
            response = await asyncio.wait_for(
                self._read_frame(reader), timeout=self._result_timeout
            )
            return _parsed_response(
                response,
                expected_source_sha256=digest.hexdigest(),
            )
        except PDFParserError:
            raise
        except (OSError, ConnectionError, asyncio.TimeoutError):
            raise PDFParserError() from None
        finally:
            digest = hashlib.sha256()
            await self._close(writer)

    async def _open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        try:
            return await asyncio.wait_for(
                asyncio.open_unix_connection(str(self._socket_path)),
                timeout=self._connect_timeout,
            )
        except (OSError, ConnectionError, asyncio.TimeoutError):
            raise PDFParserError() from None

    async def _write_header(
        self,
        writer: asyncio.StreamWriter,
        value: dict[str, object],
    ) -> None:
        payload = json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        if not 1 <= len(payload) <= MAX_HEADER_BYTES:
            raise PDFParserError()
        writer.write(struct.pack(">I", len(payload)) + payload)
        await writer.drain()

    async def _read_frame(self, reader: asyncio.StreamReader) -> dict[str, object]:
        try:
            length = struct.unpack(">I", await reader.readexactly(4))[0]
            if not 1 <= length <= MAX_RESPONSE_BYTES:
                raise PDFParserError()
            payload = await reader.readexactly(length)
        except (asyncio.IncompleteReadError, OSError, struct.error):
            raise PDFParserError() from None
        return _strict_json(payload)

    @staticmethod
    async def _close(writer: asyncio.StreamWriter) -> None:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, BrokenPipeError, OSError):
            pass


def _strict_json(payload: bytes) -> dict[str, object]:
    duplicate = False

    def pairs(rows):
        nonlocal duplicate
        output = {}
        for key, value in rows:
            if key in output:
                duplicate = True
            output[key] = value
        return output

    try:
        value = json.loads(payload, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PDFParserError() from None
    if duplicate or not isinstance(value, dict):
        raise PDFParserError()
    return value


def _require_admission(value: dict[str, object]) -> None:
    if value == {"ok": True, "status": "ready"}:
        return
    _raise_parser_response(value)


def _raise_parser_response(value: dict[str, object]) -> None:
    if set(value) == {"ok", "code"} and value.get("ok") is False:
        code = value.get("code")
        if isinstance(code, str) and code in _PARSER_CODES:
            raise PDFParserError(code)
    raise PDFParserError()


def _parsed_response(
    response: dict[str, object],
    *,
    expected_source_sha256: str | None,
) -> ParsedDocument:
    if response.get("ok") is not True:
        _raise_parser_response(response)
    if set(response) != {"ok", "result"} or not isinstance(response.get("result"), dict):
        raise PDFParserError()
    value = response["result"]
    base_keys = {
        "parser_revision",
        "extraction_revision",
        "segmentation_revision",
        "source_sha256",
        "page_count",
        "character_count",
        "segment_count",
        "omitted_visual_page_numbers",
        "segments",
        "segment_manifest_sha256",
        "extracted_text",
    }
    scenario = value.get("scenario")
    expected_keys = base_keys | ({"scenario"} if scenario is not None else set())
    if set(value) != expected_keys:
        raise PDFParserError()
    source_sha256 = value.get("source_sha256")
    if (
        not isinstance(source_sha256, str)
        or _HASH_PATTERN.fullmatch(source_sha256) is None
        or (
            expected_source_sha256 is not None
            and source_sha256 != expected_source_sha256
        )
        or value.get("parser_revision") != PARSER_REVISION
        or value.get("extraction_revision") != EXTRACTION_REVISION
        or value.get("segmentation_revision") != SEGMENTATION_REVISION
    ):
        raise PDFParserError()
    page_count = value.get("page_count")
    character_count = value.get("character_count")
    segment_count = value.get("segment_count")
    if (
        type(page_count) is not int
        or not 1 <= page_count <= 10
        or type(character_count) is not int
        or not 1 <= character_count <= 8_000
        or type(segment_count) is not int
        or not 1 <= segment_count <= 80
    ):
        raise PDFParserError()
    omitted = value.get("omitted_visual_page_numbers")
    if (
        not isinstance(omitted, list)
        or any(type(page) is not int or not 1 <= page <= page_count for page in omitted)
        or omitted != sorted(set(omitted))
    ):
        raise PDFParserError()
    rows = value.get("segments")
    if not isinstance(rows, list) or len(rows) != segment_count:
        raise PDFParserError()
    segments: list[DocumentSegment] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or set(row) != {"page", "segment_id", "text"}:
            raise PDFParserError()
        page = row.get("page")
        segment_id = row.get("segment_id")
        text = row.get("text")
        if (
            type(page) is not int
            or not 1 <= page <= page_count
            or segment_id != f"seg_{index:03d}"
            or not isinstance(text, str)
            or not text
            or "\x00" in text
            or text != " ".join(text.split())
            or unicodedata.normalize("NFC", text) != text
        ):
            raise PDFParserError()
        segments.append(DocumentSegment(page=page, segment_id=segment_id, text=text))
    extracted_text = "\n\n".join(row.text for row in segments)
    if value.get("extracted_text") != extracted_text or len(extracted_text) != character_count:
        raise PDFParserError()
    manifest_payload = json.dumps(
        [
            {"page": row.page, "segment_id": row.segment_id, "text": row.text}
            for row in segments
        ],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    if value.get("segment_manifest_sha256") != manifest_sha256:
        raise PDFParserError()
    scenario_value: dict[str, str] | None = None
    if scenario is not None:
        if (
            not isinstance(scenario, dict)
            or set(scenario) != {"scenario_id", "title", "registry_revision"}
            or not isinstance(scenario.get("scenario_id"), str)
            or _SCENARIO_ID_PATTERN.fullmatch(scenario["scenario_id"]) is None
            or not isinstance(scenario.get("registry_revision"), str)
            or _REVISION_PATTERN.fullmatch(scenario["registry_revision"]) is None
            or not isinstance(scenario.get("title"), str)
            or not 1 <= len(scenario["title"]) <= 120
            or "\x00" in scenario["title"]
            or unicodedata.normalize("NFC", scenario["title"]) != scenario["title"]
        ):
            raise PDFParserError()
        scenario_value = dict(scenario)
    return ParsedDocument(
        source_pdf_sha256=source_sha256,
        parser_revision=PARSER_REVISION,
        extraction_revision=EXTRACTION_REVISION,
        segmentation_revision=SEGMENTATION_REVISION,
        page_count=page_count,
        character_count=character_count,
        segment_count=segment_count,
        omitted_visual_page_numbers=tuple(omitted),
        segments=segments,
        segment_manifest_sha256=manifest_sha256,
        extracted_text=extracted_text,
        scenario=scenario_value,
    )

"""Bounded Unix-socket protocol shared by the secretless PDF parser."""

from __future__ import annotations

import json
import hashlib
import re
import struct
from collections.abc import Mapping

PROTOCOL_VERSION = 1
MAX_HEADER_BYTES = 4_096
MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
MAX_SCENARIO_ID_BYTES = 80
PARSER_REVISION = "aiguard-pdf-parser-v1"
EXTRACTION_REVISION = "pdfplumber-lines-v1"
SEGMENTATION_REVISION = "immutable-lines-v1"
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ProtocolError(ValueError):
    """A frame is not the strict bounded protocol."""


def encode_json(value: Mapping[str, object], *, maximum: int) -> bytes:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if not payload or len(payload) > maximum:
        raise ProtocolError("JSON frame length is invalid")
    return struct.pack(">I", len(payload)) + payload


def decode_json(payload: bytes, *, maximum: int) -> dict[str, object]:
    if not payload or len(payload) > maximum:
        raise ProtocolError("JSON frame length is invalid")
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
        raise ProtocolError("JSON frame is invalid") from None
    if duplicate or not isinstance(value, dict):
        raise ProtocolError("JSON frame is not a strict object")
    return value


def request_header(value: Mapping[str, object]) -> dict[str, object]:
    header = dict(value)
    if header.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("protocol version is invalid")
    operation = header.get("operation")
    if operation == "health":
        if set(header) != {"protocol_version", "operation", "body_bytes"}:
            raise ProtocolError("health header fields are invalid")
        if header.get("body_bytes") != 0:
            raise ProtocolError("health body length is invalid")
    elif operation == "parse_document":
        if set(header) != {
            "protocol_version",
            "operation",
            "body_bytes",
            "source_kind",
        }:
            raise ProtocolError("document header fields are invalid")
        if header.get("source_kind") not in {"standard", "priority"}:
            raise ProtocolError("document source kind is invalid")
        body_bytes = header.get("body_bytes")
        if type(body_bytes) is not int or not 1 <= body_bytes <= MAX_PDF_BYTES:
            raise ProtocolError("document body length is invalid")
    elif operation == "parse_scenario":
        if set(header) != {
            "protocol_version",
            "operation",
            "body_bytes",
            "scenario_id",
        }:
            raise ProtocolError("scenario header fields are invalid")
        scenario_id = header.get("scenario_id")
        if (
            not isinstance(scenario_id, str)
            or not scenario_id.isascii()
            or not 1 <= len(scenario_id.encode("ascii")) <= MAX_SCENARIO_ID_BYTES
        ):
            raise ProtocolError("scenario identifier is invalid")
        if header.get("body_bytes") != 0:
            raise ProtocolError("scenario body length is invalid")
    else:
        raise ProtocolError("operation is invalid")
    return header


def validated_result(value: object, *, expected_source_sha256: str) -> dict[str, object]:
    """Reconstruct the only parser result allowed to cross the child boundary."""

    expected_keys = {
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
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ProtocolError("parser result fields are invalid")
    if (
        value.get("parser_revision") != PARSER_REVISION
        or value.get("extraction_revision") != EXTRACTION_REVISION
        or value.get("segmentation_revision") != SEGMENTATION_REVISION
        or value.get("source_sha256") != expected_source_sha256
        or _HASH_PATTERN.fullmatch(expected_source_sha256) is None
    ):
        raise ProtocolError("parser result identity is invalid")
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
        raise ProtocolError("parser result counts are invalid")
    omitted = value.get("omitted_visual_page_numbers")
    if (
        not isinstance(omitted, list)
        or any(type(page) is not int or not 1 <= page <= page_count for page in omitted)
        or omitted != sorted(set(omitted))
    ):
        raise ProtocolError("parser result omission pages are invalid")
    raw_segments = value.get("segments")
    if not isinstance(raw_segments, list) or len(raw_segments) != segment_count:
        raise ProtocolError("parser result segments are invalid")
    segments: list[dict[str, object]] = []
    for index, row in enumerate(raw_segments, start=1):
        if not isinstance(row, dict) or set(row) != {"page", "segment_id", "text"}:
            raise ProtocolError("parser result segment fields are invalid")
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
        ):
            raise ProtocolError("parser result segment value is invalid")
        segments.append({"page": page, "segment_id": segment_id, "text": text})
    extracted_text = "\n\n".join(str(row["text"]) for row in segments)
    if value.get("extracted_text") != extracted_text or len(extracted_text) != character_count:
        raise ProtocolError("parser result extracted text is invalid")
    manifest_payload = json.dumps(
        segments,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    if value.get("segment_manifest_sha256") != manifest_sha256:
        raise ProtocolError("parser result manifest is invalid")
    return {
        "parser_revision": PARSER_REVISION,
        "extraction_revision": EXTRACTION_REVISION,
        "segmentation_revision": SEGMENTATION_REVISION,
        "source_sha256": expected_source_sha256,
        "page_count": page_count,
        "character_count": character_count,
        "segment_count": segment_count,
        "omitted_visual_page_numbers": list(omitted),
        "segments": segments,
        "segment_manifest_sha256": manifest_sha256,
        "extracted_text": extracted_text,
    }

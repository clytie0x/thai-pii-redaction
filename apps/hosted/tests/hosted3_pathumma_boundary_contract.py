#!/usr/bin/env python3
"""Protected, opt-in Pathumma boundary measurement for Stage 3D."""

from __future__ import annotations

import json
import os
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"
sys.path.insert(0, str(CORE))

from aift_hosted3.document_artifact import (  # noqa: E402
    ArtifactProvenance,
    DocumentArtifactError,
    ROLE_HEADINGS_TH,
    render_protected_artifact,
)
from aift_hosted3.document_provider import (  # noqa: E402
    DOCUMENT_SYSTEM_PROMPT,
    MAX_PROVIDER_REQUEST_BYTES,
    MAX_PROVIDER_SEGMENTS,
    complete_document_provider,
    encode_document_provider_request,
)
from aift_hosted3.pdf_client import (  # noqa: E402
    EXTRACTION_REVISION,
    PARSER_REVISION,
    DocumentSegment,
)
RUN_LIVE = os.environ.get("AIGUARD_PATHUMMA_BOUNDARY") == "1"


def safe_response_diagnostics(response: str, expected_count: int) -> dict[str, object]:
    """Describe a rejected provider body without printing provider-authored text."""

    duplicate = False

    def pairs(rows):
        nonlocal duplicate
        output = {}
        for key, value in rows:
            if key in output:
                duplicate = True
            output[key] = value
        return output

    stripped = response.strip()
    diagnostics: dict[str, object] = {
        "response_bytes": len(response.encode("utf-8")),
        "starts_json_object": stripped.startswith("{"),
        "ends_json_object": stripped.endswith("}"),
        "starts_markdown_fence": stripped.startswith("```"),
        "json_valid": False,
        "duplicate_json_key": False,
    }
    try:
        value = json.loads(response, object_pairs_hook=pairs)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return diagnostics
    diagnostics["json_valid"] = True
    diagnostics["duplicate_json_key"] = duplicate
    diagnostics["top_level_is_object"] = isinstance(value, dict)
    diagnostics["exact_top_level_shape"] = (
        isinstance(value, dict) and set(value) == {"classifications"}
    )
    rows = value.get("classifications") if isinstance(value, dict) else None
    diagnostics["classifications_is_array"] = isinstance(rows, list)
    if not isinstance(rows, list):
        return diagnostics
    exact_rows = [
        row
        for row in rows
        if isinstance(row, dict) and set(row) == {"segment_id", "role"}
    ]
    ids = [row["segment_id"] for row in exact_rows if isinstance(row["segment_id"], str)]
    roles = [row["role"] for row in exact_rows if isinstance(row["role"], str)]
    diagnostics.update(
        {
            "classification_count": len(rows),
            "exact_row_shape_count": len(exact_rows),
            "expected_classification_count": expected_count,
            "unique_segment_id_count": len(set(ids)),
            "valid_role_count": sum(role in ROLE_HEADINGS_TH for role in roles),
        }
    )
    return diagnostics


def boundary_segments() -> tuple[DocumentSegment, ...]:
    values = (DocumentSegment(page=1, segment_id="seg_001", text="X" * 8_000),)
    protected = "\n\n".join(row.text for row in values)
    if len(protected) != 8_000 or len(protected.encode("utf-8")) != 8_000:
        raise AssertionError("boundary fixture does not reach the provider cap")
    return values


def thai_token_byte_boundary_segments() -> tuple[DocumentSegment, ...]:
    """Build a Thai/token fixture that reaches the exact encoded byte cap."""

    phrase = (
        "ประสบการณ์ [NAME_1] ทำงานกับ [ORGANIZATION_1] "
        "ติดต่อ [EMAIL_1] โทร [PHONE_1] "
    )
    values = [
        DocumentSegment(
            page=1,
            segment_id=f"seg_{index:03d}",
            text=f"{phrase}ลำดับ {index}",
        )
        for index in range(1, MAX_PROVIDER_SEGMENTS + 1)
    ]
    base_bytes = len(encode_document_provider_request(tuple(values)).encode("utf-8"))
    padding = MAX_PROVIDER_REQUEST_BYTES - base_bytes
    if padding <= 0:
        raise AssertionError("Thai/token boundary fixture has no padding budget")
    values[-1] = DocumentSegment(
        page=values[-1].page,
        segment_id=values[-1].segment_id,
        text=values[-1].text + ("X" * padding),
    )
    encoded = encode_document_provider_request(tuple(values))
    protected = "\n\n".join(row.text for row in values)
    if len(encoded.encode("utf-8")) != MAX_PROVIDER_REQUEST_BYTES:
        raise AssertionError("Thai/token fixture does not reach the request-byte cap")
    if len(protected) > 8_000:
        raise AssertionError("Thai/token fixture exceeds the protected-text cap")
    return tuple(values)


@unittest.skipUnless(RUN_LIVE, "protected Pathumma boundary measurement only")
class PathummaBoundaryTests(unittest.TestCase):
    def _assert_live_boundary(self, segments, *, fixture: str):
        self.assertTrue(os.environ.get("TOKENMIND_API_KEY"), "provider key is absent")
        self.assertTrue(os.environ.get("TOKENMIND_BASE_URL"), "provider base URL is absent")
        request = encode_document_provider_request(segments)
        response = ""
        artifact = None
        try:
            started = time.monotonic()
            response = complete_document_provider(
                DOCUMENT_SYSTEM_PROMPT,
                request,
                timeout=200.0,
            )
            elapsed_ms = round((time.monotonic() - started) * 1_000)
            try:
                artifact = render_protected_artifact(
                    response.encode("utf-8"),
                    segments=segments,
                    provenance=ArtifactProvenance(
                        hosted_version="3.0.2",
                        source_kind="document_standard",
                        source_receipt_id="AAAAAAAAAAAAAAAAAAAAAA",
                        parser_revision=PARSER_REVISION,
                        extraction_revision=EXTRACTION_REVISION,
                        page_count=1,
                        omitted_visual_page_numbers=(),
                    ),
                    outbound_guard=lambda _text, _tokens: None,
                )
            except DocumentArtifactError:
                print(
                    json.dumps(
                        safe_response_diagnostics(
                            response,
                            len(segments),
                        ),
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )
                raise
            self.assertTrue(artifact.exact_segment_coverage)
            self.assertTrue(artifact.structured_output_validated)
            self.assertEqual(
                sum(
                    len(row["segment_ids"])
                    for row in artifact.protected_document_ast["ordered_sections"]
                ),
                len(segments),
            )
            print(
                json.dumps(
                    {
                        "boundary_codepoints": len(
                            "\n\n".join(row.text for row in segments)
                        ),
                        "boundary_segments": len(segments),
                        "elapsed_ms": elapsed_ms,
                        "fixture": fixture,
                        "request_bytes": len(request.encode("utf-8")),
                        "response_bytes": len(response.encode("utf-8")),
                        "validated": True,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )
        finally:
            if artifact is not None:
                artifact.clear()
            response = ""
            request = ""

    def test_exact_protected_8000_codepoint_envelope(self):
        self._assert_live_boundary(boundary_segments(), fixture="ascii_codepoint_cap")

    def test_exact_9120b_thai_token_32_segment_envelope(self):
        self._assert_live_boundary(
            thai_token_byte_boundary_segments(),
            fixture="thai_token_byte_cap",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

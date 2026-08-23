"""True PDF redaction via flatten-to-image.

Renders each page to a raster, paints opaque black rectangles over the word bboxes matched to
entity spans, then rebuilds the PDF from the images. The output has no text layer, so redacted
text is unrecoverable (and the rest is no longer selectable). pypdfium2 + Pillow only
(permissive licenses; no PyMuPDF/AGPL).
"""

from math import isfinite
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

from amprang.engine.ingest.text_cleaner import clean_length_preserving
from amprang.engine.models import EntityRegistry, WordBbox
from amprang.engine.safe_errors import discard_exception_graph

# Render scale (points -> pixels). Higher = crisper output but larger files.
RENDER_SCALE = 2.0

# Padding (PDF points) around each redaction rectangle. Thai vowel/tone marks render ~3pt above
# the nominal bbox top, so the top pad is larger; over-coverage is the intended bias.
REDACT_PAD_PT = 2.0
REDACT_PAD_TOP_PT = 5.0

# Same-line rectangles within this gap merge into one, closing exposed gaps between words.
REDACT_MERGE_GAP_PT = 6.0

_PDF_SOURCE_MAPPING_ERROR = "PDF source mapping could not be established safely"


class PdfSourceMappingError(RuntimeError):
    """Raised when an entity interval has no safe visual mapping."""


def _mapping_error() -> PdfSourceMappingError:
    return PdfSourceMappingError(_PDF_SOURCE_MAPPING_ERROR)


def _map_entities_to_boxes(
    entity_registry: EntityRegistry,
    word_bboxes: list[WordBbox],
    *,
    page_count: int | None = None,
) -> list[list[WordBbox]]:
    """Map each entity interval to only the PDF boxes that produced it."""
    if not entity_registry.entities:
        return []

    validated_boxes: list[tuple[WordBbox, int, int]] = []
    for box in word_bboxes:
        span = box.source_span
        if (
            not isinstance(box.text, str)
            or not box.text
            or not isinstance(span, tuple)
            or len(span) != 2
        ):
            raise _mapping_error()
        start, end = span
        coordinates = (box.x, box.y, box.width, box.height)
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
            or end - start != len(box.text)
            or type(box.page) is not int
            or box.page < 1
            or (page_count is not None and box.page > page_count)
            or any(type(value) not in (int, float) or not isfinite(value) for value in coordinates)
            or box.width <= 0
            or box.height <= 0
        ):
            raise _mapping_error()
        validated_boxes.append((box, start, end))

    mapped_entities: list[list[WordBbox]] = []
    for entity in entity_registry.entities:
        span = entity.span
        if (
            not isinstance(span, tuple)
            or len(span) != 2
            or not isinstance(entity.original_text, str)
        ):
            raise _mapping_error()
        entity_start, entity_end = span
        if (
            type(entity_start) is not int
            or type(entity_end) is not int
            or entity_start < 0
            or entity_end <= entity_start
            or entity_end - entity_start != len(entity.original_text)
        ):
            raise _mapping_error()

        selected: list[tuple[WordBbox, int, int]] = []
        covered = [False] * len(entity.original_text)
        pages_by_character: dict[int, int] = {}
        for box, box_start, box_end in validated_boxes:
            overlap_start = max(entity_start, box_start)
            overlap_end = min(entity_end, box_end)
            if overlap_start >= overlap_end:
                continue

            entity_slice = entity.original_text[
                overlap_start - entity_start : overlap_end - entity_start
            ]
            box_slice = box.text[overlap_start - box_start : overlap_end - box_start]
            if clean_length_preserving(entity_slice) != clean_length_preserving(box_slice):
                raise _mapping_error()

            selected.append((box, box_start, box_end))
            for source_index in range(overlap_start, overlap_end):
                relative_index = source_index - entity_start
                covered[relative_index] = True
                existing_page = pages_by_character.setdefault(source_index, box.page)
                if existing_page != box.page:
                    raise _mapping_error()

        if any(
            not char.isspace() and not covered[index]
            for index, char in enumerate(entity.original_text)
        ):
            raise _mapping_error()

        selected.sort(
            key=lambda item: (
                item[0].page,
                item[1],
                item[2],
                item[0].y,
                item[0].x,
                item[0].width,
                item[0].height,
            )
        )
        mapped_entities.append([box for box, _start, _end in selected])

    return mapped_entities


def _merge_boxes(
    boxes: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    """Merge same-line (x0, y0, x1, y1) rectangles within REDACT_MERGE_GAP_PT into covering
    rectangles. Runs to a fixed point so chained merges collapse regardless of input order.
    """
    remaining = list(boxes)
    merged: list[tuple[float, float, float, float]] = []
    while remaining:
        x0, y0, x1, y1 = remaining.pop()
        changed = True
        while changed:
            changed = False
            still_separate = []
            for ox0, oy0, ox1, oy1 in remaining:
                vertical_overlap = y0 < oy1 and oy0 < y1
                horizontal_gap = max(x0, ox0) - min(x1, ox1)
                if vertical_overlap and horizontal_gap <= REDACT_MERGE_GAP_PT:
                    x0, y0, x1, y1 = min(x0, ox0), min(y0, oy0), max(x1, ox1), max(y1, oy1)
                    changed = True
                else:
                    still_separate.append((ox0, oy0, ox1, oy1))
            remaining = still_separate
        merged.append((x0, y0, x1, y1))
    return merged


def redact_pdf(
    input_pdf_path: str,
    entity_registry: EntityRegistry,
    word_bboxes: list[WordBbox],
    output_path: str,
) -> Path:
    """Paint black rectangles over the boxes selected by entity spans, flatten to images, and
    return the output Path. Boxes are top-origin PDF points.

    Every box must carry an exact source interval; missing or inconsistent provenance fails
    before output. Never falls back to value or substring matching.
    """
    out_path = Path(output_path)

    doc = pdfium.PdfDocument(input_pdf_path)
    mapping_failed = False
    mapped_entities: list[list[WordBbox]] = []
    try:
        mapped_entities = _map_entities_to_boxes(
            entity_registry,
            word_bboxes,
            page_count=len(doc),
        )
    except Exception as error:
        discard_exception_graph(error)
        mapping_failed = True

    if mapping_failed:
        doc.close()
        del entity_registry, word_bboxes
        mapped_entities = []
        raise _mapping_error() from None

    by_page: dict[int, list[list[WordBbox]]] = {}
    for entity_boxes in mapped_entities:
        entity_pages: dict[int, list[WordBbox]] = {}
        for box in entity_boxes:
            entity_pages.setdefault(box.page, []).append(box)
        for page, page_boxes in entity_pages.items():
            by_page.setdefault(page, []).append(page_boxes)

    try:
        page_images: list[Image.Image] = []
        for idx in range(len(doc)):
            page_num = idx + 1  # match the 1-based bboxes
            pil = doc[idx].render(scale=RENDER_SCALE).to_pil().convert("RGB")
            draw = ImageDraw.Draw(pil)

            # Pad in PDF points, merge same-line rectangles, then draw solid coverage.
            for entity_boxes in by_page.get(page_num, []):
                pt_boxes: list[tuple[float, float, float, float]] = []
                for wb in entity_boxes:
                    pt_boxes.append(
                        (
                            wb.x - REDACT_PAD_PT,
                            wb.y - REDACT_PAD_TOP_PT,
                            wb.x + wb.width + REDACT_PAD_PT,
                            wb.y + wb.height + REDACT_PAD_PT,
                        )
                    )

                for x0, y0, x1, y1 in _merge_boxes(pt_boxes):
                    draw.rectangle(
                        [
                            x0 * RENDER_SCALE,
                            y0 * RENDER_SCALE,
                            x1 * RENDER_SCALE,
                            y1 * RENDER_SCALE,
                        ],
                        fill=(0, 0, 0),
                    )

            page_images.append(pil)
    finally:
        doc.close()

    if not page_images:
        # No pages — write an empty 1-page white image so output is a valid PDF.
        page_images = [Image.new("RGB", (612, 792), (255, 255, 255))]

    # Pillow JPEG-compresses RGB pages (ringing fringe at box edges); "P" mode makes it write
    # lossless ASCIIHexDecode so redaction edges stay solid.
    page_images = [im.convert("P", palette=Image.ADAPTIVE) for im in page_images]

    page_images[0].save(
        str(out_path),
        "PDF",
        save_all=True,
        append_images=page_images[1:],
        resolution=72.0 * RENDER_SCALE,
    )
    return out_path

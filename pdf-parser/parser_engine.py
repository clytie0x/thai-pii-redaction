"""Deterministic, fail-closed text-layer PDF inspection and extraction."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
import pikepdf
import pypdfium2 as pdfium

from protocol import EXTRACTION_REVISION, PARSER_REVISION, SEGMENTATION_REVISION

MAX_PAGES = 10
MAX_PAGE_POINTS = 2_000.0
MAX_CODEPOINTS = 8_000
MAX_SEGMENTS = 80
MIN_NONSPACE_CHARS_PER_PAGE = 80
MIN_TEXT_LINES_PER_PAGE = 5
MIN_GLYPH_HEIGHT = 6.0
MAX_GLYPH_HEIGHT = 36.0
MIN_LINE_UNION_RATIO = 0.03
MIN_LINE_HULL_RATIO = 0.20
MAX_SINGLE_RASTER_RATIO = 0.10
MAX_COMBINED_RASTER_RATIO = 0.15
MAX_PDF_OBJECTS = 20_000
MAX_OBJECT_DEPTH = 40
MAX_CONTAINER_MEMBERS = 20_000
MAX_PAGE_OBJECTS = 10_000

_DISALLOWED_KEYS = {
    "/AA",
    "/AcroForm",
    "/AF",
    "/Collection",
    "/EmbeddedFiles",
    "/Encrypt",
    "/F",
    "/FS",
    "/GoToE",
    "/GoToR",
    "/ImportData",
    "/JavaScript",
    "/JS",
    "/Launch",
    "/Movie",
    "/Names",
    "/OCProperties",
    "/OpenAction",
    "/Rendition",
    "/RichMedia",
    "/Sound",
    "/SubmitForm",
    "/URI",
    "/XFA",
    "/3D",
}

_CATALOG_KEYS = {
    "/Lang",
    "/MarkInfo",
    "/Metadata",
    "/OutputIntents",
    "/PageLabels",
    "/PageLayout",
    "/PageMode",
    "/Pages",
    "/StructTreeRoot",
    "/Type",
    "/Version",
    "/ViewerPreferences",
}
_PAGE_KEYS = {
    "/ArtBox",
    "/BleedBox",
    "/Contents",
    "/CropBox",
    "/Group",
    "/LastModified",
    "/MediaBox",
    "/Metadata",
    "/Parent",
    "/PieceInfo",
    "/Resources",
    "/Rotate",
    "/StructParents",
    "/Tabs",
    "/Trans",
    "/TrimBox",
    "/Type",
    "/UserUnit",
}
_RESOURCE_KEYS = {
    "/ColorSpace",
    "/ExtGState",
    "/Font",
    "/Pattern",
    "/ProcSet",
    "/Properties",
    "/Shading",
    "/XObject",
}
_CONTENT_STREAM_KEYS = {"/DecodeParms", "/Filter", "/Length"}
_FORM_STREAM_KEYS = _CONTENT_STREAM_KEYS | {
    "/BBox",
    "/FormType",
    "/Group",
    "/Matrix",
    "/Metadata",
    "/Name",
    "/Resources",
    "/StructParent",
    "/Subtype",
    "/Type",
}
_IMAGE_STREAM_KEYS = _CONTENT_STREAM_KEYS | {
    "/Alternates",
    "/BitsPerComponent",
    "/ColorSpace",
    "/Decode",
    "/Height",
    "/ImageMask",
    "/Intent",
    "/Interpolate",
    "/Mask",
    "/Metadata",
    "/Name",
    "/OC",
    "/OPI",
    "/SMask",
    "/SMaskInData",
    "/StructParent",
    "/Subtype",
    "/Type",
    "/Width",
}


class DocumentError(ValueError):
    """A fixed public document failure without parser-derived detail."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)


@dataclass(frozen=True, slots=True)
class PageProbe:
    raster_rectangles: tuple[Rect, ...]
    has_vectors: bool


def _clip_rect(raw: dict[str, Any], width: float, height: float) -> Rect | None:
    try:
        x0 = max(0.0, min(width, float(raw["x0"])))
        x1 = max(0.0, min(width, float(raw["x1"])))
        top = max(0.0, min(height, float(raw["top"])))
        bottom = max(0.0, min(height, float(raw["bottom"])))
    except (KeyError, TypeError, ValueError, OverflowError):
        raise DocumentError("document_unsupported") from None
    rect = Rect(min(x0, x1), min(top, bottom), max(x0, x1), max(top, bottom))
    return rect if rect.area > 0 else None


def _union_area(rectangles: list[Rect]) -> float:
    xs = sorted({value for rect in rectangles for value in (rect.x0, rect.x1)})
    total = 0.0
    for left, right in zip(xs, xs[1:]):
        if right <= left:
            continue
        spans = sorted(
            (rect.y0, rect.y1)
            for rect in rectangles
            if rect.x0 < right and rect.x1 > left
        )
        covered = 0.0
        if spans:
            start, end = spans[0]
            for y0, y1 in spans[1:]:
                if y0 <= end:
                    end = max(end, y1)
                else:
                    covered += end - start
                    start, end = y0, y1
            covered += end - start
        total += (right - left) * covered
    return total


def _convex_hull_area(rectangles: list[Rect]) -> float:
    points = sorted(
        {
            point
            for rect in rectangles
            for point in (
                (rect.x0, rect.y0),
                (rect.x0, rect.y1),
                (rect.x1, rect.y0),
                (rect.x1, rect.y1),
            )
        }
    )
    if len(points) < 3:
        return 0.0

    def cross(origin, a, b):
        return (a[0] - origin[0]) * (b[1] - origin[1]) - (
            a[1] - origin[1]
        ) * (b[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    return abs(
        sum(
            hull[index][0] * hull[(index + 1) % len(hull)][1]
            - hull[(index + 1) % len(hull)][0] * hull[index][1]
            for index in range(len(hull))
        )
    ) / 2.0


def _strict_pikepdf_walk(pdf: pikepdf.Pdf) -> None:
    if pdf.is_encrypted:
        raise DocumentError("document_unsupported")
    root = pdf.Root
    for key in ("/OpenAction", "/AA", "/Names", "/AcroForm", "/OCProperties", "/Collection", "/AF"):
        if key in root:
            raise DocumentError("document_unsupported")
    if {str(key) for key in root.keys()} - _CATALOG_KEYS:
        raise DocumentError("document_unsupported")

    def require_keys(value: Any, allowed: set[str] | frozenset[str]) -> None:
        if not isinstance(value, (pikepdf.Dictionary, pikepdf.Stream)):
            raise DocumentError("document_unsupported")
        if {str(key) for key in value.keys()} - allowed:
            raise DocumentError("document_unsupported")

    def reject_clipping(value: Any) -> None:
        """Reject clip-path state that the text API cannot visibility-resolve."""

        try:
            instructions = pikepdf.parse_content_stream(value)
            if any(str(instruction.operator) in {"W", "W*"} for instruction in instructions):
                raise DocumentError("document_unsupported")
        except DocumentError:
            raise
        except (pikepdf.PdfError, TypeError, ValueError):
            raise DocumentError("document_unsupported") from None

    validated_forms: set[tuple[int, int] | int] = set()
    active_forms: set[tuple[int, int] | int] = set()
    # pikepdf may create short-lived Python wrappers for direct objects. Keeping
    # them alive prevents CPython from reusing an id during this traversal and
    # making an unrelated direct dictionary look as though it was already seen.
    direct_objects: dict[int, Any] = {}

    def object_identity(value: Any) -> tuple[int, int] | int:
        try:
            objgen = tuple(value.objgen)
        except (AttributeError, TypeError):
            objgen = None
        if objgen and objgen != (0, 0):
            return objgen
        identity = id(value)
        direct_objects[identity] = value
        return identity

    def validate_resources(resources: Any, depth: int) -> None:
        if depth > MAX_OBJECT_DEPTH:
            raise DocumentError("document_unsupported")
        require_keys(resources, _RESOURCE_KEYS)
        if "/XObject" not in resources:
            return
        xobjects = resources["/XObject"]
        if not isinstance(xobjects, pikepdf.Dictionary):
            raise DocumentError("document_unsupported")
        for name in xobjects.keys():
            value = xobjects[name]
            subtype = str(value.get("/Subtype", ""))
            if subtype == "/Image":
                require_keys(value, _IMAGE_STREAM_KEYS)
                continue
            if subtype != "/Form":
                raise DocumentError("document_unsupported")
            require_keys(value, _FORM_STREAM_KEYS)
            identity = object_identity(value)
            if identity in active_forms:
                raise DocumentError("document_unsupported")
            if identity in validated_forms:
                continue
            active_forms.add(identity)
            try:
                reject_clipping(value)
                if "/Resources" in value:
                    validate_resources(value["/Resources"], depth + 1)
            finally:
                active_forms.remove(identity)
            validated_forms.add(identity)

    for page in pdf.pages:
        require_keys(page.obj, _PAGE_KEYS)
        reject_clipping(page)
        if "/Resources" in page.obj:
            validate_resources(page.obj["/Resources"], 0)
        if "/Contents" in page.obj:
            contents = page.obj["/Contents"]
            values = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
            for value in values:
                require_keys(value, _CONTENT_STREAM_KEYS)
    seen: set[tuple[int, int] | int] = set()
    member_count = 0

    def visit(value: Any, depth: int) -> None:
        nonlocal member_count
        if depth > MAX_OBJECT_DEPTH:
            raise DocumentError("document_unsupported")
        identity = object_identity(value)
        if identity in seen:
            return
        seen.add(identity)
        if len(seen) > MAX_PDF_OBJECTS:
            raise DocumentError("document_unsupported")
        if isinstance(value, pikepdf.Dictionary):
            keys = {str(key) for key in value.keys()}
            if keys & _DISALLOWED_KEYS:
                raise DocumentError("document_unsupported")
            if "/Annots" in keys:
                try:
                    if len(value["/Annots"]):
                        raise DocumentError("document_unsupported")
                except (TypeError, ValueError):
                    raise DocumentError("document_unsupported") from None
            member_count += len(keys)
            if member_count > MAX_CONTAINER_MEMBERS:
                raise DocumentError("document_unsupported")
            for key in value.keys():
                visit(value[key], depth + 1)
        elif isinstance(value, pikepdf.Array):
            member_count += len(value)
            if member_count > MAX_CONTAINER_MEMBERS:
                raise DocumentError("document_unsupported")
            for child in value:
                visit(child, depth + 1)

    visit(root, 0)
    for page in pdf.pages:
        visit(page.obj, 0)
    for value in pdf.objects:
        visit(value, 0)


def _pdfium_page_probe(path: Path, expected_pages: int) -> list[PageProbe]:
    probes: list[PageProbe] = []
    try:
        document = pdfium.PdfDocument(str(path), autoclose=True)
        if len(document) != expected_pages:
            raise DocumentError("document_unsupported")
        for page_index in range(len(document)):
            page = document[page_index]
            width, height = page.get_size()
            if not all(math.isfinite(v) and 0 < v <= MAX_PAGE_POINTS for v in (width, height)):
                raise DocumentError("document_unsupported")
            # Force PDFium to traverse page objects and decoded text. Any failure
            # is treated as structural uncertainty rather than parser detail.
            objects = list(page.get_objects(max_depth=20))
            if len(objects) > MAX_PAGE_OBJECTS:
                raise DocumentError("document_unsupported")
            rasters: list[Rect] = []
            has_vectors = False
            for value in objects:
                if value.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                    left, bottom, right, top = value.get_bounds()
                    rect = Rect(
                        max(0.0, min(width, left)),
                        max(0.0, min(height, height - top)),
                        max(0.0, min(width, right)),
                        max(0.0, min(height, height - bottom)),
                    )
                    if rect.area > 0:
                        rasters.append(rect)
                elif value.type in {
                    pdfium.raw.FPDF_PAGEOBJ_PATH,
                    pdfium.raw.FPDF_PAGEOBJ_SHADING,
                    pdfium.raw.FPDF_PAGEOBJ_FORM,
                }:
                    has_vectors = True
                elif value.type == pdfium.raw.FPDF_PAGEOBJ_TEXT:
                    render_mode = pdfium.raw.FPDFTextObj_GetTextRenderMode(value.raw)
                    # Modes 3 and 7 do not paint. Modes 4, 5, and 6 paint but
                    # also add glyphs to the clipping path, whose effective
                    # visibility cannot be proved from the text object alone.
                    if render_mode not in {0, 1, 2}:
                        raise DocumentError("pdf_text_layer_required")
                    alphas: list[int] = []
                    if render_mode in {0, 2, 4, 6}:
                        red = ctypes.c_uint()
                        green = ctypes.c_uint()
                        blue = ctypes.c_uint()
                        alpha = ctypes.c_uint()
                        if not pdfium.raw.FPDFPageObj_GetFillColor(
                            value.raw,
                            ctypes.byref(red),
                            ctypes.byref(green),
                            ctypes.byref(blue),
                            ctypes.byref(alpha),
                        ):
                            raise DocumentError("document_unsupported")
                        alphas.append(alpha.value)
                    if render_mode in {1, 2, 5, 6}:
                        red = ctypes.c_uint()
                        green = ctypes.c_uint()
                        blue = ctypes.c_uint()
                        alpha = ctypes.c_uint()
                        if not pdfium.raw.FPDFPageObj_GetStrokeColor(
                            value.raw,
                            ctypes.byref(red),
                            ctypes.byref(green),
                            ctypes.byref(blue),
                            ctypes.byref(alpha),
                        ):
                            raise DocumentError("document_unsupported")
                        alphas.append(alpha.value)
                    if not alphas or max(alphas) < 128:
                        raise DocumentError("pdf_text_layer_required")
                else:
                    raise DocumentError("document_unsupported")
            text_page = page.get_textpage()
            text_page.get_text_range()
            text_page.close()
            page.close()
            probes.append(PageProbe(tuple(rasters), has_vectors))
        document.close()
    except DocumentError:
        raise
    except Exception:
        raise DocumentError("document_unsupported") from None
    return probes


def _extract_lines(page) -> tuple[list[dict[str, object]], list[dict[str, Any]]]:
    try:
        word_values = page.extract_words(
            x_tolerance=3,
            y_tolerance=3,
            keep_blank_chars=False,
            use_text_flow=False,
        )
    except Exception:
        raise DocumentError("document_unsupported") from None
    if not isinstance(word_values, list):
        raise DocumentError("document_unsupported")
    words: list[dict[str, object]] = []
    for value in word_values:
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            raise DocumentError("document_unsupported")
        text = " ".join(str(value["text"]).split())
        rect = _clip_rect(value, float(page.width), float(page.height))
        if text and rect is not None:
            words.append({"text": text, "rect": rect})

    # Build rows geometrically, then split a row at a materially large horizontal
    # gap. This prevents a two-column résumé from fusing unrelated left/right
    # fields while preserving ordinary intra-line word spacing.
    rows: list[list[dict[str, object]]] = []
    for word in sorted(words, key=lambda item: (item["rect"].y0, item["rect"].x0)):
        rect = word["rect"]
        destination = None
        for row in reversed(rows[-4:]):
            row_top = statistics.median(item["rect"].y0 for item in row)
            row_height = statistics.median(
                item["rect"].y1 - item["rect"].y0 for item in row
            )
            if abs(rect.y0 - row_top) <= max(3.0, row_height * 0.35):
                destination = row
                break
        if destination is None:
            destination = []
            rows.append(destination)
        destination.append(word)

    lines: list[dict[str, object]] = []
    for row in rows:
        ordered = sorted(row, key=lambda item: item["rect"].x0)
        groups: list[list[dict[str, object]]] = []
        for word in ordered:
            if not groups:
                groups.append([word])
                continue
            previous = groups[-1][-1]["rect"]
            current = word["rect"]
            median_height = statistics.median(
                item["rect"].y1 - item["rect"].y0 for item in groups[-1]
            )
            if current.x0 - previous.x1 > max(24.0, median_height * 2.0):
                groups.append([word])
            else:
                groups[-1].append(word)
        for group in groups:
            lines.append(
                {
                    "text": " ".join(str(item["text"]) for item in group),
                    "rect": Rect(
                        min(item["rect"].x0 for item in group),
                        min(item["rect"].y0 for item in group),
                        max(item["rect"].x1 for item in group),
                        max(item["rect"].y1 for item in group),
                    ),
                }
            )
    return lines, list(page.chars)


def _page_payload(
    page,
    page_number: int,
    probe: PageProbe,
) -> tuple[list[dict[str, object]], bool]:
    width = float(page.width)
    height = float(page.height)
    if not all(math.isfinite(v) and 0 < v <= MAX_PAGE_POINTS for v in (width, height)):
        raise DocumentError("document_unsupported")
    page_area = width * height
    lines, chars = _extract_lines(page)
    nonspace = [char for char in chars if str(char.get("text", "")).strip()]
    if len(nonspace) < MIN_NONSPACE_CHARS_PER_PAGE or len(lines) < MIN_TEXT_LINES_PER_PAGE:
        raise DocumentError("pdf_text_layer_required")
    heights: list[float] = []
    for char in nonspace:
        try:
            height_value = abs(float(char["bottom"]) - float(char["top"]))
        except (KeyError, TypeError, ValueError, OverflowError):
            raise DocumentError("document_unsupported") from None
        if not math.isfinite(height_value) or height_value <= 0:
            raise DocumentError("document_unsupported")
        heights.append(height_value)
    median_height = statistics.median(heights)
    line_rectangles = [value["rect"] for value in lines]
    if (
        not MIN_GLYPH_HEIGHT <= median_height <= MAX_GLYPH_HEIGHT
        or _union_area(line_rectangles) / page_area < MIN_LINE_UNION_RATIO
        or _convex_hull_area(line_rectangles) / page_area < MIN_LINE_HULL_RATIO
    ):
        raise DocumentError("pdf_text_layer_required")
    raster_rectangles = list(probe.raster_rectangles) + [
        rect
        for raw in page.images
        if (rect := _clip_rect(raw, width, height)) is not None
    ]
    if any(rect.area / page_area > MAX_SINGLE_RASTER_RATIO for rect in raster_rectangles):
        raise DocumentError("pdf_visual_content_unsupported")
    if _union_area(raster_rectangles) / page_area > MAX_COMBINED_RASTER_RATIO:
        raise DocumentError("pdf_visual_content_unsupported")
    has_vectors = bool(page.lines or page.rects or page.curves or probe.has_vectors)
    segments = [
        {"page": page_number, "text": str(value["text"])}
        for value in lines
    ]
    return segments, bool(raster_rectangles or has_vectors)


def parse_pdf(path: Path) -> dict[str, object]:
    try:
        source_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        raise DocumentError("document_unsupported") from None
    try:
        with pikepdf.Pdf.open(
            path,
            password="",
            attempt_recovery=False,
            suppress_warnings=True,
        ) as pdf:
            page_count = len(pdf.pages)
            if not 1 <= page_count <= MAX_PAGES:
                raise DocumentError("document_unsupported")
            _strict_pikepdf_walk(pdf)
    except DocumentError:
        raise
    except (pikepdf.PasswordError, pikepdf.PdfError, ValueError, OSError):
        raise DocumentError("document_unsupported") from None
    page_probes = _pdfium_page_probe(path, page_count)
    segments: list[dict[str, object]] = []
    omitted_visual_pages: list[int] = []
    try:
        with pdfplumber.open(path, unicode_norm=None, strict_metadata=True) as document:
            if len(document.pages) != page_count:
                raise DocumentError("document_unsupported")
            for page_number, page in enumerate(document.pages, start=1):
                page_segments, omitted = _page_payload(
                    page,
                    page_number,
                    page_probes[page_number - 1],
                )
                segments.extend(page_segments)
                if omitted:
                    omitted_visual_pages.append(page_number)
    except DocumentError:
        raise
    except Exception:
        raise DocumentError("document_unsupported") from None
    if not segments or len(segments) > MAX_SEGMENTS:
        raise DocumentError("document_too_complex")
    for index, segment in enumerate(segments, start=1):
        segment["segment_id"] = f"seg_{index:03d}"
    extracted_text = "\n\n".join(str(segment["text"]) for segment in segments)
    if len(extracted_text) > MAX_CODEPOINTS:
        raise DocumentError("document_too_complex")
    manifest_payload = json.dumps(
        segments,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return {
        "parser_revision": PARSER_REVISION,
        "extraction_revision": EXTRACTION_REVISION,
        "segmentation_revision": SEGMENTATION_REVISION,
        "source_sha256": source_sha256,
        "page_count": page_count,
        "character_count": len(extracted_text),
        "segment_count": len(segments),
        "omitted_visual_page_numbers": omitted_visual_pages,
        "segments": segments,
        "segment_manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "extracted_text": extracted_text,
    }

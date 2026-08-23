"""File type detection."""

from __future__ import annotations

from pathlib import Path

from amprang.engine.safe_errors import discard_exception_graph

PAGE_TEXT_LAYER_MIN_CHARS = 20


def page_needs_ocr(page) -> bool:
    """Return true when a raster page needs OCR."""
    from pypdfium2 import raw as pdfium_raw

    try:
        return any(obj.type == pdfium_raw.FPDF_PAGEOBJ_IMAGE for obj in page.get_objects())
    except Exception as exc:
        discard_exception_graph(exc)
        return True


def detect_source_type(path: str | Path) -> str:
    """Return "text" | "pdf_text" | "pdf_hybrid"; any raster page (even beside a text layer)
    makes the PDF hybrid. Raises ValueError if the PDF cannot be opened.
    """
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return "text"

    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(path))
        has_ocr_page = False
        try:
            for page in doc:
                if page_needs_ocr(page):
                    has_ocr_page = True
                    break
        finally:
            doc.close()
    except Exception as exc:
        raise ValueError(f"Cannot open PDF: {path}") from exc

    return "pdf_hybrid" if has_ocr_page else "pdf_text"


def validate_encoding(content: bytes) -> str:
    """Decode as UTF-8, then tis-620, then cp874; raise ValueError if none works."""
    for encoding in ("utf-8", "tis-620", "cp874"):
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            discard_exception_graph(exc)
            continue
    raise ValueError("Content could not be decoded as UTF-8, tis-620, or cp874")

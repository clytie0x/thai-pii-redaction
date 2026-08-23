"""Export final de-anonymized output to file (txt, pdf_text) after pre-export checks."""

from dataclasses import dataclass
from pathlib import Path

from amphrang.engine.models import ReverseResult
from amphrang.engine.output_validator import ValidationResult
from amphrang.engine.thai_pdf_text import draw_text, register_thai_font


@dataclass
class ExportResult:
    """Result of successful export."""

    output_path: Path
    format: str  # "txt" | "pdf_text"
    byte_size: int
    warnings: list[str]


class ExportError(Exception):
    """Raised when export cannot proceed (critical flag, unwritable path, unsupported format)."""

    pass


def _check_pre_export(
    validation_result: ValidationResult,
    output_path: Path,
    fmt: str,
    overwrite: bool,
) -> None:
    """Raise ExportError on halt flag, unsupported fmt, existing file without overwrite, or an
    unwritable output directory.
    """
    if validation_result.halt:
        raise ExportError("Export blocked: validation_result.halt=True (layer3 integrity failure)")

    if fmt not in {"txt", "pdf_text"}:
        raise ExportError(f"Unsupported format: {fmt!r}. Supported: txt, pdf_text")

    if output_path.exists() and not overwrite:
        raise ExportError(
            f"Output file already exists: {output_path}. Use overwrite=True to replace."
        )

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        probe = output_path.parent / ".write_probe"
        probe.touch()
        probe.unlink()
    except (PermissionError, OSError) as e:
        raise ExportError(f"Output directory not writable: {e}")


def _export_txt(text: str, output_path: Path) -> int:
    """Write text to .txt file. Returns byte size."""
    encoded = text.encode("utf-8")
    output_path.write_bytes(encoded)
    return len(encoded)


def _export_pdf_text(text: str, output_path: Path) -> int:
    """Create a simple text-based PDF using reportlab. Returns byte size."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    font_name = register_thai_font()

    c = canvas.Canvas(str(output_path), pagesize=letter)
    page_width, page_height = letter
    c.setFont(font_name, 11)

    # Simple top-down layout; reportlab uses a bottom-left origin, hence the page_height flip.
    x = 50
    y = page_height - 72
    line_height = 14

    lines = text.split("\n")
    for line in lines:
        if y < 50:
            c.showPage()
            c.setFont(font_name, 11)
            y = page_height - 72
        draw_text(c, x, y, line, font_name, 11)
        y -= line_height

    c.save()
    return output_path.stat().st_size


def export(
    reverse_result: ReverseResult,
    validation_result: ValidationResult,
    output_path: str,
    *,
    fmt: str = "txt",
    overwrite: bool = False,
) -> ExportResult:
    """Export final de-anonymized output; returns ExportResult. Raises ExportError when a
    pre-export check fails (see _check_pre_export).
    """
    path = Path(output_path)
    warnings = []

    _check_pre_export(validation_result, path, fmt, overwrite)

    # Layer 2 warnings are non-halting flags
    if not validation_result.layer2_completeness_ok:
        warnings.extend([f for f in validation_result.flags if "incomplete" in f or "residue" in f])

    text = reverse_result.text

    if fmt == "txt":
        byte_size = _export_txt(text, path)
    elif fmt == "pdf_text":
        byte_size = _export_pdf_text(text, path)

    return ExportResult(
        output_path=path,
        format=fmt,
        byte_size=byte_size,
        warnings=warnings,
    )

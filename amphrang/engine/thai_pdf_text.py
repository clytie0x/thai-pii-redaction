"""Thai text for reportlab-authored PDFs.

reportlab shapes Thai only when `uharfbuzz` imports (else `TTFont.shapable` is silently False)
AND drawString is handed a `ShapedStr`; without both, stacked tone marks (ที่, ผู้) drop or
misplace. Shaped strings alone poison the text layer (HarfBuzz re-glyphs to Private-Use
codepoints), so `draw_text()` draws real text invisibly plus shaped glyphs visibly; copying
such a line yields it twice. Every product module that draws Thai routes through here.
Requires reportlab >= 4.4.0: `shapeStr` does not exist before that (the import breaks first).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import ShapedStr, TTFont, shapeStr
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


def _bundled_font() -> str:
    """Path to the bundled Thai font; returned whether or not it exists (candidates fall through)."""
    return str(Path(__file__).resolve().parent / "fonts" / _BUNDLED_FONT_FILE)


_BUNDLED_FONT_FILE = "IBMPlexSansThaiLooped-Regular.ttf"

# Thai-capable TrueType candidates, in preference order; Helvetica fallback renders no Thai.
# The bundled font is first on purpose: a filed report must not depend on the machine's fonts,
# and it is the only entry guaranteed to exist. The rest are a net for a checkout missing it.
FONT_CANDIDATES = [
    _bundled_font(),
    r"C:\Windows\Fonts\sarabun-v17-latin_latin-ext_thai_vietnamese-regular.ttf",
    # Leelawadee UI ships with every Windows edition (the Sarabun path is hand-installed), so a
    # stock machine is not left with Helvetica. Kept AFTER Sarabun: it positions marks with
    # y-offsets and hits reportlab's setRise defect (see _install_rise_fix); Sarabun never does.
    r"C:\Windows\Fonts\leelawui.ttf",
    "/usr/share/fonts/truetype/thai/Sarabun-Regular.ttf",
    # fonts-thai-tlwg (Debian/Ubuntu, CI + Docker) ships Laksaman, a TH Sarabun New derivative.
    "/usr/share/fonts/truetype/tlwg/Laksaman.ttf",
]

# Filenames Windows itself supplies. Tahoma / leelawad.ttf deliberately absent: same rise leak,
# no extra coverage.
WINDOWS_STOCK_FONT_FILES = frozenset({"leelawui.ttf", "leelauib.ttf", "leeluisl.ttf"})
# The reportlab registration key, not a font name: whichever candidate wins is registered here.
THAI_FONT_NAME = "AmphrangThai"

# Whether a cluster needs re-glyphing depends on the FONT's glyph inventory, not adjacent
# codepoints; predicting it by regex measured wrong both ways (see shaped()). Only ask "any Thai?".
_THAI_BLOCK = re.compile("[\u0e00-\u0e7f]")

_warned = False


def _rise_state_is_lost() -> bool:
    """True when reportlab's `setRise` forgets the rise it just emitted.

    Its "optimize out r0 Ts r1 Ts" branch rewrites the operator but never stores the new rise.
    Probed by behaviour, not source, so it survives upstream refactors.
    """
    from io import BytesIO

    text = canvas.Canvas(BytesIO()).beginText(0, 0)
    text.setRise(1)  # else-branch: appends "1 Ts"
    text.setRise(2)  # optimize branch: rewrites it
    return text._rise != 2


def _install_rise_fix() -> bool:
    """Repair `setRise` in place; returns whether anything needed repairing.

    Fonts that position tone marks with y-offsets (Leelawadee UI, the only Thai face stock
    Windows ships) make `_rise` drift from the content stream and strand following characters
    at the wrong baseline. Applied conditionally so an upstream fix is not patched twice.
    """
    if not _rise_state_is_lost():
        return False

    from reportlab.pdfgen.textobject import PDFTextObject, fp_str

    # Name matches reportlab's own method, which is what it replaces.
    def setRise(self, rise):
        v = f"{fp_str(rise)} Ts"
        if self._code[-1].endswith(" Ts"):
            self._y += self._rise
            self._code[-1] = v
            self._rise = rise
            self._y -= rise
        else:
            self._rise = rise
            self._y -= rise
            self._code.append(v)

    PDFTextObject.setRise = setRise
    return True


RISE_FIX_APPLIED = _install_rise_fix()


def register_thai_font() -> str:
    """Register a Thai-capable TTF with reportlab; fall back to Helvetica."""
    font_path = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
    if font_path is None:
        return "Helvetica"
    if THAI_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(THAI_FONT_NAME, font_path))
    return THAI_FONT_NAME


def contains_thai(text: str) -> bool:
    """True when `text` has any Thai character (the Thai Unicode block)."""
    return bool(_THAI_BLOCK.search(text))


def shaping_available(font_name: str) -> bool:
    """True when `font_name` is registered and shapable (`shapable` folds in the uharfbuzz check)."""
    try:
        font = pdfmetrics.getFont(font_name)
    except Exception:
        return False
    return bool(getattr(font, "shapable", False))


def _warn_once() -> None:
    global _warned
    if _warned:
        return
    _warned = True
    # Deliberately says nothing about the text being drawn -- it is user content.
    logger.warning(
        "Thai text shaping is unavailable; some stacked tone marks may render "
        "incorrectly. Install uharfbuzz and a Thai TrueType font."
    )


def shaped(text: str, font_name: str, font_size: float) -> str:
    """Return `text` ready for `canvas.drawString`: a `ShapedStr` when HarfBuzz moved something,
    the original otherwise. Never raises.

    When shaping is unavailable the warning fires on ANY Thai text: a regex predicting
    "dangerous" clusters measured wrong both ways (false positive "ผู้", false negative "ป่วย"
    driven by the consonant's ascender), and a false negative here is a silent bad render.
    """
    if not text:
        return text
    if not shaping_available(font_name):
        if contains_thai(text):
            _warn_once()
        return text
    try:
        return shapeStr(text, font_name, font_size)
    except Exception:  # pragma: no cover - defensive; shapeStr is total in practice
        _warn_once()
        return text


def draw_text(
    c: canvas.Canvas, x: float, y: float, text: str, font_name: str, font_size: float
) -> None:
    """Draw text with Thai mark shaping: invisible real text (search/copy) plus visible shaped
    glyphs. The hidden layer sits in a saved graphics state so it cannot hide later text.
    """
    out = shaped(text, font_name, font_size)
    if not isinstance(out, ShapedStr):
        visible = c.beginText(x, y)
        visible.setFont(font_name, font_size)
        visible.textOut(out)
        c.drawText(visible)
        return
    c.saveState()
    try:
        invisible = c.beginText(x, y)
        invisible.setFont(font_name, font_size)
        invisible.setTextRenderMode(3)  # Keep real text for search and copy.
        invisible.textOut(text)
        c.drawText(invisible)
    finally:
        # Stop the hidden text mode from reaching later text.
        c.restoreState()
    visible = c.beginText(x, y)
    visible.setFont(font_name, font_size)
    visible.textOut(out)  # Draw the shaped glyphs.
    c.drawText(visible)

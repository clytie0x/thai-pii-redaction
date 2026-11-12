"""Optional OpenThai2.0-OCR-Text engine for scanned pages.

The weights and the upstream runtime stay outside this repository. The user
downloads them with scripts/download_openthai_ocr.py and points
AIGUARD_OCR_OPENTHAI_DIR at that directory. This module never fetches them.

LineOCR deskews a page that leans more than 2.5 degrees and returns each
line box in the caller's image coordinates (model card, Apache-2.0). Callers
scale those pixels into top-origin 72-pt PDF space. This module does not
deskew or rotate the image again.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
from pathlib import Path
from types import ModuleType

from pii_redactor.ingest.ocr_processor import ExplicitOCRUnavailableError
from pii_redactor.models import WordBbox
from pii_redactor.safe_errors import discard_exception_graph

REQUIRED_FILES = (
    "config.json",
    "det.onnx",
    "det.yml",
    "rec.onnx",
    "rec_dict.txt",
    "runtime/__init__.py",
    "runtime/line_engine.py",
    "runtime/thai_norm.py",
)
_BOX_ERROR = "OpenThai OCR returned a line box that cannot be mapped onto the page."
_IMAGE_ERROR = "OpenThai OCR could not read the rendered page image."
_RUNTIME_PACKAGE = "_aiguard_openthai_runtime"
_engine = None
_engine_dir: Path | None = None


class OCRBoxError(RuntimeError):
    """A line box or page image cannot be placed. Not a bare RuntimeError."""

    def __init__(self, message: str = _BOX_ERROR):
        super().__init__(message)


def model_dir() -> Path:
    """Return the local model directory, or raise if the selection cannot run."""
    raw = os.environ.get("AIGUARD_OCR_OPENTHAI_DIR", "").strip()
    path = Path(raw) if raw else None
    if path is None or any(not (path / name).is_file() for name in REQUIRED_FILES):
        raise ExplicitOCRUnavailableError("openthai")
    return path


def packages_ready() -> bool:
    """Whether the OpenThai extra imports. Does not import Paddle."""
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import pyclipper  # noqa: F401
    except Exception as exc:
        discard_exception_graph(exc)
        return False
    return True


def is_ready() -> bool:
    if not packages_ready():
        return False
    try:
        model_dir()
    except ExplicitOCRUnavailableError:
        return False
    return True


def _aabb(box) -> tuple[float, float, float, float]:
    if not isinstance(box, (list, tuple)) or len(box) < 4:
        raise OCRBoxError
    xs: list[float] = []
    ys: list[float] = []
    for point in box:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise OCRBoxError
        try:
            x, y = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            raise OCRBoxError from None
        if not math.isfinite(x) or not math.isfinite(y):
            raise OCRBoxError
        xs.append(x)
        ys.append(y)
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 <= x0 or y1 <= y0:
        raise OCRBoxError
    return x0, y0, x1, y1


def _confidence(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise OCRBoxError from None
    if not math.isfinite(number):
        raise OCRBoxError
    return number


def words_from_lines(lines, page_num: int, dpi: int) -> tuple[list[WordBbox], float]:
    """Scale caller-image quads into top-origin 72-pt boxes. No second deskew."""
    if not isinstance(lines, list):
        raise OCRBoxError
    scale = 72.0 / dpi
    words: list[WordBbox] = []
    confidences: list[float] = []
    for line in lines:
        if not isinstance(line, dict):
            raise OCRBoxError
        text = line.get("text")
        if text == "":
            continue
        if not isinstance(text, str):
            raise OCRBoxError
        x0, y0, x1, y1 = _aabb(line.get("box"))
        words.append(
            WordBbox(
                text=text,
                page=page_num,
                x=x0 * scale,
                y=y0 * scale,
                width=(x1 - x0) * scale,
                height=(y1 - y0) * scale,
            )
        )
        confidences.append(_confidence(line.get("confidence")))
    mean = sum(confidences) / len(confidences) if confidences else 0.0
    return words, mean


def _as_bgr(image):
    """LineOCR treats an ndarray as BGR. The PDF render is RGB."""
    import cv2
    import numpy as np

    array = np.asarray(image)
    if array.ndim == 2:
        return cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
    if array.ndim == 3 and array.shape[2] == 3:
        return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    raise OCRBoxError(_IMAGE_ERROR)


def _load_runtime(runtime_dir: Path, name: str):
    full = f"{_RUNTIME_PACKAGE}.{name}"
    spec = importlib.util.spec_from_file_location(full, runtime_dir / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ExplicitOCRUnavailableError("openthai")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = _RUNTIME_PACKAGE
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


def _import_line_ocr(directory: Path):
    runtime_dir = directory / "runtime"
    for name in (
        _RUNTIME_PACKAGE,
        f"{_RUNTIME_PACKAGE}.thai_norm",
        f"{_RUNTIME_PACKAGE}.line_engine",
    ):
        sys.modules.pop(name, None)
    package = ModuleType(_RUNTIME_PACKAGE)
    package.__path__ = [str(runtime_dir)]
    package.__package__ = _RUNTIME_PACKAGE
    sys.modules[_RUNTIME_PACKAGE] = package
    _load_runtime(runtime_dir, "thai_norm")
    return _load_runtime(runtime_dir, "line_engine")


def _engine_for(directory: Path):
    global _engine, _engine_dir
    if _engine is not None and _engine_dir == directory:
        return _engine
    module = _import_line_ocr(directory)
    _engine = module.LineOCR(directory, threads=1)
    _engine_dir = directory
    return _engine


def read_words(image, page_num: int, dpi: int) -> tuple[list[WordBbox], float]:
    """Read one rendered RGB page. Raises if this engine cannot run."""
    if not packages_ready():
        raise ExplicitOCRUnavailableError("openthai")
    directory = model_dir()
    result = _engine_for(directory).read(_as_bgr(image))
    if not isinstance(result, dict):
        raise OCRBoxError
    return words_from_lines(result.get("lines") or [], page_num, dpi)

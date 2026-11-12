"""OpenThai2.0-OCR-Text engine selection, coordinates, and failure behavior.

Default CI never downloads or loads the real model. The real-model test
skips unless AIGUARD_OCR_OPENTHAI_DIR already points at a local snapshot.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path

import pytest

from pii_redactor.ingest import ocr_openthai, ocr_processor
from pii_redactor.ingest.ocr_openthai import OCRBoxError
from pii_redactor.ingest.ocr_processor import ExplicitOCRUnavailableError
from pii_redactor.ingest.text_extractor import extract

ROOT = Path(__file__).resolve().parents[1]


def _load_download_script():
    path = ROOT / "scripts" / "download_openthai_ocr.py"
    spec = importlib.util.spec_from_file_location("download_openthai_ocr", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _quad() -> list[list[float]]:
    # Caller-image pixels of a line tilted more than 2.5 degrees.
    # The model card says the runtime maps this back before returning it.
    return [[200.0, 400.0], [600.0, 430.0], [590.0, 490.0], [190.0, 460.0]]


def _hybrid_pdf(tmp_path: Path) -> Path:
    from PIL import Image
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    image = Image.new("RGB", (80, 80), "white")
    path = tmp_path / "scan.pdf"
    drawing = canvas.Canvas(str(path), pagesize=letter)
    drawing.drawImage(ImageReader(image), 0, 0, width=letter[0], height=letter[1])
    drawing.save()
    return path


def _mixed_pdf(tmp_path: Path) -> Path:
    from PIL import Image
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    image = Image.new("RGB", (80, 80), "white")
    path = tmp_path / "mixed.pdf"
    drawing = canvas.Canvas(str(path), pagesize=letter)
    drawing.drawImage(ImageReader(image), 0, 0, width=letter[0], height=letter[1])
    drawing.drawString(72, 72, "Selectable footer")
    drawing.save()
    return path


def _text_pdf(tmp_path: Path) -> Path:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path = tmp_path / "text.pdf"
    drawing = canvas.Canvas(str(path), pagesize=letter)
    drawing.drawString(72, 720, "Text layer only")
    drawing.save()
    return path


def test_default_engine_stays_paddle(monkeypatch):
    monkeypatch.delenv("AIGUARD_OCR_ENGINE", raising=False)
    assert ocr_processor.engine_name() == "paddle"
    assert ocr_processor.selection_is_explicit() is False


def test_unknown_engine_is_rejected_without_echoing_the_value(monkeypatch):
    monkeypatch.setenv("AIGUARD_OCR_ENGINE", "not-an-engine")
    with pytest.raises(ExplicitOCRUnavailableError) as excinfo:
        ocr_processor.engine_name()
    assert excinfo.value.code == "rejected"
    assert "not-an-engine" not in str(excinfo.value)


def test_skewed_caller_quad_lands_in_top_origin_points():
    """144 DPI is 2 pixels per point. The box is the quad's own AABB."""
    lines = [{"text": "synthetic-line", "confidence": 0.94, "box": _quad()}]
    words, confidence = ocr_openthai.words_from_lines(lines, page_num=1, dpi=144)
    word = words[0]
    assert word.text == "synthetic-line"
    assert word.x == pytest.approx(190 / 2)
    assert word.y == pytest.approx(400 / 2)
    assert word.width == pytest.approx((600 - 190) / 2)
    assert word.height == pytest.approx((490 - 400) / 2)
    assert 0 <= word.y < 792
    assert word.y + word.height < 792
    center_y = word.y + word.height / 2
    assert center_y == pytest.approx(((400 + 490) / 2) / 2)
    assert confidence == pytest.approx(0.94)


def test_non_finite_box_is_rejected():
    lines = [
        {
            "text": "synthetic-line",
            "confidence": 0.9,
            "box": [[0, 0], [math.nan, 1], [2, 2], [0, 2]],
        }
    ]
    with pytest.raises(OCRBoxError):
        ocr_openthai.words_from_lines(lines, page_num=1, dpi=144)


def test_missing_openthai_does_not_call_paddle(tmp_path, monkeypatch):
    monkeypatch.setenv("AIGUARD_OCR_ENGINE", "openthai")
    monkeypatch.delenv("AIGUARD_OCR_OPENTHAI_DIR", raising=False)

    def boom():
        raise AssertionError("paddle was called")

    monkeypatch.setattr(ocr_processor, "_get_engine", boom)
    with pytest.raises(ExplicitOCRUnavailableError) as excinfo:
        extract(_hybrid_pdf(tmp_path), "pdf_hybrid")
    assert excinfo.value.code == "openthai"
    assert excinfo.value.__cause__ is None
    assert "PaddleOCR is not used as a fallback" in str(excinfo.value)


def test_explicit_paddle_does_not_fall_back_to_the_text_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("AIGUARD_OCR_ENGINE", "paddle")
    monkeypatch.setattr(ocr_processor, "is_available", lambda: False)
    with pytest.raises(ExplicitOCRUnavailableError) as excinfo:
        extract(_mixed_pdf(tmp_path), "pdf_hybrid")
    assert excinfo.value.code == "paddle"


def test_explicit_openthai_does_not_fall_back_to_the_text_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("AIGUARD_OCR_ENGINE", "openthai")
    monkeypatch.delenv("AIGUARD_OCR_OPENTHAI_DIR", raising=False)
    with pytest.raises(ExplicitOCRUnavailableError) as excinfo:
        extract(_mixed_pdf(tmp_path), "pdf_hybrid")
    assert excinfo.value.code == "openthai"


def test_text_layer_pdf_does_not_call_ocr(tmp_path, monkeypatch):
    monkeypatch.setenv("AIGUARD_OCR_ENGINE", "openthai")

    def boom(*_args, **_kwargs):
        raise AssertionError("ocr was called")

    monkeypatch.setattr(ocr_processor, "ocr_page", boom)
    text, _boxes, meta = extract(_text_pdf(tmp_path), "pdf_text")
    assert "Text layer only" in text
    assert meta == {}


def test_openthai_fragments_keep_source_spans(tmp_path, monkeypatch):
    monkeypatch.setenv("AIGUARD_OCR_ENGINE", "openthai")
    monkeypatch.setattr(ocr_processor, "is_available", lambda: True)
    monkeypatch.setattr(ocr_processor, "_render_page_to_array", lambda page, dpi: object())

    def fake_read(_image, page_num, dpi):
        assert dpi >= 72
        from pii_redactor.models import WordBbox

        return [
            WordBbox(text="line-one", page=page_num, x=10, y=20, width=40, height=8),
            WordBbox(text="line-two", page=page_num, x=10, y=40, width=40, height=8),
        ], 0.91

    monkeypatch.setattr(ocr_openthai, "read_words", fake_read)
    text, boxes, _meta = extract(_hybrid_pdf(tmp_path), "pdf_hybrid")
    assert [box.text for box in boxes] == ["line-one", "line-two"]
    for box in boxes:
        assert text[box.source_span[0] : box.source_span[1]] == box.text


def test_bad_box_from_the_engine_is_not_swallowed(monkeypatch):
    monkeypatch.setenv("AIGUARD_OCR_ENGINE", "openthai")
    monkeypatch.setattr(ocr_processor, "is_available", lambda: True)

    def fake_read(_image, _page_num, _dpi):
        raise OCRBoxError

    monkeypatch.setattr(ocr_openthai, "read_words", fake_read)
    monkeypatch.setattr(ocr_processor, "_render_page_to_array", lambda page, dpi: object())
    with pytest.raises(OCRBoxError):
        ocr_processor.ocr_page(object(), 1, max_retries=1)


def test_runtime_adapter_does_not_fetch():
    source = (ROOT / "pii_redactor" / "ingest" / "ocr_openthai.py").read_text(encoding="utf-8")
    for token in ("urlopen", "huggingface", "requests.", "httpx"):
        assert token not in source


def _requirement_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        names.add(stripped.split(">=")[0].split("==")[0].strip().lower())
    return names


def test_requirement_files_keep_opencv_wheels_apart():
    paddle = _requirement_names(ROOT / "requirements-ocr.txt")
    openthai = _requirement_names(ROOT / "requirements-ocr-openthai.txt")
    paddle_text = (ROOT / "requirements-ocr.txt").read_text(encoding="utf-8")
    openthai_text = (ROOT / "requirements-ocr-openthai.txt").read_text(encoding="utf-8")
    assert "opencv-python-headless" not in paddle
    assert "opencv-python-headless" in openthai
    assert "opencv-contrib-python" not in openthai
    assert "paddleocr" not in openthai
    assert "opencv-contrib-python" in paddle_text
    assert "Do not install" in openthai_text


def test_download_pins_cover_required_files_and_reject_a_bad_checksum(tmp_path):
    script = _load_download_script()
    pinned = {name for name, _digest in script.PINNED}
    assert set(ocr_openthai.REQUIRED_FILES) <= pinned
    assert script.REVISION == "39fa41bdd49f067ba41b1d9de79c06ab506d67d4"

    def fake_fetch(rel: str) -> bytes:
        return b"tampered-" + rel.encode()

    with pytest.raises(SystemExit, match="checksum mismatch"):
        script.download(tmp_path, fetch=fake_fetch)
    assert list(tmp_path.rglob("*.partial")) == []
    assert list(tmp_path.rglob("*.onnx")) == []


def test_download_stores_only_matching_bytes(tmp_path):
    script = _load_download_script()
    payloads = {name: f"body-{name}".encode() for name, _digest in script.PINNED}
    script.PINNED = tuple(
        (name, hashlib.sha256(payloads[name]).hexdigest()) for name, _digest in script.PINNED
    )
    script.download(tmp_path, fetch=lambda rel: payloads[rel])
    for name, payload in payloads.items():
        assert (tmp_path / name).read_bytes() == payload


def test_local_runtime_import_does_not_need_the_real_model(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "__init__.py").write_text("", encoding="utf-8")
    (runtime / "thai_norm.py").write_text(
        "def canonical(text):\n    return text\n", encoding="utf-8"
    )
    (runtime / "line_engine.py").write_text(
        "from .thai_norm import canonical\n"
        "class LineOCR:\n"
        "    def __init__(self, model_dir, threads=1, **overrides):\n"
        "        self.threads = threads\n"
        "        self.model_dir = str(model_dir)\n"
        "    def read(self, image):\n"
        "        return {'lines': [{'text': canonical('local'), 'confidence': 0.5,\n"
        "            'box': [[0, 0], [8, 0], [8, 4], [0, 4]]}], 'text': 'local'}\n",
        encoding="utf-8",
    )
    for name in ocr_openthai.REQUIRED_FILES:
        if name.startswith("runtime/"):
            continue
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("stub", encoding="utf-8")
    monkeypatch.setenv("AIGUARD_OCR_OPENTHAI_DIR", str(tmp_path))
    monkeypatch.setattr(ocr_openthai, "packages_ready", lambda: True)
    monkeypatch.setattr(ocr_openthai, "_as_bgr", lambda image: image)
    ocr_openthai._engine = None
    ocr_openthai._engine_dir = None
    try:
        words, confidence = ocr_openthai.read_words(object(), page_num=3, dpi=72)
    finally:
        ocr_openthai._engine = None
        ocr_openthai._engine_dir = None
    assert words[0].text == "local"
    assert words[0].page == 3
    assert words[0].width == pytest.approx(8)
    assert confidence == pytest.approx(0.5)


@pytest.mark.skipif(
    not __import__("os").environ.get("AIGUARD_OCR_OPENTHAI_DIR"),
    reason="OpenThai model directory is not configured",
)
def test_real_openthai_model_returns_caller_boxes():
    """Optional. Skips in CI. Does not download and does not assert a transcription."""
    if not ocr_openthai.packages_ready() or not ocr_openthai.is_ready():
        pytest.skip("OpenThai package or model files are absent")
    import numpy as np

    image = np.full((64, 160, 3), 255, dtype=np.uint8)
    words, confidence = ocr_openthai.read_words(image, page_num=1, dpi=72)
    assert 0.0 <= confidence <= 1.0
    for word in words:
        assert word.text
        assert math.isfinite(word.x) and math.isfinite(word.y)
        assert word.width > 0 and word.height > 0

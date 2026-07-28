"""Download the Thai OCR models into $HOME caches at build time.

Constructs the engine exactly like pii_redactor/ingest/ocr_processor.py does,
so the baked cache layout matches what the runtime lazy singleton expects
(E0 spike, 2026-07-28: /opt/ocr-home/.paddlex/official_models/...).
"""

from paddleocr import PaddleOCR

engine = PaddleOCR(lang="th", use_textline_orientation=True)
print("ocr prewarm ok:", type(engine).__name__)

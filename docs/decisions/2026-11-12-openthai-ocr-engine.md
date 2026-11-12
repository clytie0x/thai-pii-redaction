# Optional OpenThai2.0-OCR-Text engine

Date: 2026-11-12. Status: **accepted; owner selected Option A**.

## Decision

Add iApp's OpenThai2.0-OCR-Text as an optional OCR engine for scanned or
raster PDF pages (`pdf_hybrid`), beside PaddleOCR.

- PaddleOCR stays the default. Nothing selects OpenThai unless
  `AIGUARD_OCR_ENGINE=openthai`.
- The model directory is `AIGUARD_OCR_OPENTHAI_DIR`. Weights and the upstream
  runtime are not in this repository and not in the packaged exe. The only
  download is `scripts/download_openthai_ocr.py`, which the user runs.
  Runtime OCR does not contact the network.
- A missing package, a missing model, or an unknown engine name raises
  `ExplicitOCRUnavailableError`. That path does not fall back to PaddleOCR
  or to a text layer. The unset default still uses today's Paddle fallback
  when the Paddle extra is absent.
- OpenThai has its own extra, `requirements-ocr-openthai.txt`
  (`opencv-python-headless`). It must not be installed beside
  `requirements-ocr.txt` (`opencv-contrib-python`). Both wheels own `cv2`.
- The upstream runtime deskews a page tilted more than 2.5 degrees and
  returns line boxes in the caller's image coordinates. This repository
  scales those pixels into the existing top-origin 72-pt space and does not
  deskew again. Text-layer pages still use pdfplumber and pdfium.
- The pinned snapshot is Hugging Face
  `iapp/OpenThai2.0-OCR-Text` revision
  `39fa41bdd49f067ba41b1d9de79c06ab506d67d4` (Apache-2.0, v1.0.0).

OCR-Markdown, a hosted or paid iApp API, and a change of the default engine
are out of scope. Real-model acceptance is not closed by the fake-engine
tests.

## Why this is an ADR

The selection names, the no-fallback rule, and the coordinate contract are
caller-visible and expensive to reverse once a document workflow depends on
them. The owner already chose Option A on 12 Nov 2026. This record does not
ask that question again.

## Consequences

Detection is unchanged. Local AI Guard still does not send page images to an
iApp service. A core-only install behaves as before when the selector is unset.

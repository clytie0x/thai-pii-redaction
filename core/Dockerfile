# AI Guard core (FastAPI) — AIFT team08 port. Vendored slice of
# github.com/Teerapat-Vatpitak/thai-pii-redaction (commit in
# ../sync/PORT_MANIFEST.json) + the OCR layer the upstream image excludes.
# Same digest-pinned base as upstream.
FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

WORKDIR /app

ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# PyThaiNLP model home (runtime user has no home dir)
ENV PYTHAINLP_DATA=/opt/pythainlp-data
# Every ~-relative cache (PaddleX/PaddleOCR models) lands here; baked as root
# at build time, chowned to appuser below. Proven by the E0 spike 2026-07-28.
ENV HOME=/opt/ocr-home

# fonts-thai-tlwg: Thai glyphs for the PDPA report PDFs.
# libgl1/libglib2.0-0/libgomp1: PaddleX's OpenCV runtime on slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-thai-tlwg libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Dependency layers before code so rebuilds hit cache (20-min runner budget).
# The upstream graph and the AIFT OCR additions are independently exact and
# hash-locked. OCR installs with --no-deps so it cannot upgrade the core graph.
COPY requirements.lock requirements-aift.lock ./
RUN python -m pip install --no-cache-dir pip==26.1.2 \
    && python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
    && python -m pip install --no-cache-dir --no-deps --require-hashes -r requirements-aift.lock \
    && python -m pip check

# Bake the Thai NER model, then the Thai OCR models. Both BEFORE offline mode:
# these steps ARE the downloads.
RUN mkdir -p "$PYTHAINLP_DATA" \
    && python -c "from pythainlp.tag import NER; NER(engine='thainer')"
COPY prewarm_ocr.py ./
RUN mkdir -p "$HOME" && python prewarm_ocr.py

# From here the container must behave identically with or without egress.
ENV PYTHAINLP_OFFLINE=1

COPY . .

RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser /app "$PYTHAINLP_DATA" "$HOME"

# Commit identity is metadata-only and intentionally comes after every costly
# dependency/model layer so a new SHA does not invalidate the build cache.
ARG AIFT_BUILD_COMMIT=local-working-tree
LABEL org.opencontainers.image.revision="${AIFT_BUILD_COMMIT}"

USER appuser

EXPOSE 8000

# exec so SIGTERM reaches uvicorn (clean container stops); workers default 1 —
# NER/OCR models are cached per process, so extra workers multiply RAM and
# cold starts. Raise only after measuring.
CMD ["sh", "-c", "exec python -m uvicorn aift_gateway:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}"]

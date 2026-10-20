# AI Guard core (FastAPI) — AIFT team08 port. Vendored slice of
# github.com/Teerapat-Vatpitak/thai-pii-redaction (commit in
# ../sync/PORT_MANIFEST.json). Public PDF redaction/OCR is intentionally
# unsupported in this hosted deployment, so OCR-only packages are excluded.
# Same digest-pinned base as upstream.
FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

WORKDIR /app

ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# PyThaiNLP model home (runtime user has no home dir)
ENV PYTHAINLP_DATA=/opt/pythainlp-data
ENV HOME=/tmp

# fonts-thai-tlwg supplies Thai glyphs for the bounded PDPA report.
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-thai-tlwg \
    && rm -rf /var/lib/apt/lists/*

# Dependency layers before code so rebuilds hit cache (20-min runner budget).
# The upstream runtime graph is exact and hash-locked. The hosted-only overlay
# closes published runtime advisories without altering the vendored lock.
COPY requirements.lock requirements-aift-security.lock ./
RUN python -m pip install --no-cache-dir pip==26.1.2 \
    && python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
    && python -m pip install --no-cache-dir --no-deps --require-hashes -r requirements-aift-security.lock \
    && python -m pip check

# Bake the Thai NER model while egress is available, then verify the complete
# deterministic asset tree against the digest certified by Sprint 3.
COPY verify_thainer_assets.py ./
RUN mkdir -p "$PYTHAINLP_DATA" \
    && python -c "from pythainlp.tag import NER; NER(engine='thainer')" \
    && python verify_thainer_assets.py

# From here the container must behave identically with or without egress.
ENV PYTHAINLP_OFFLINE=1

# Keep runtime contents explicit. Even if a future ignore rule regresses, a
# service-local credential or test artifact cannot be copied into the image.
COPY app ./app
COPY pii_redactor ./pii_redactor
COPY demo ./demo
COPY aift_hosted3 ./aift_hosted3
COPY aift_auth.py aift_gateway.py aift_report_policy.py healthcheck.py VERSION LICENSE NOTICE ./
COPY licenses ./licenses

RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser /app "$PYTHAINLP_DATA"

# Commit identity is metadata-only and intentionally comes after every costly
# dependency/model layer so a new SHA does not invalidate the build cache.
ARG AIFT_BUILD_COMMIT=local-working-tree
LABEL org.opencontainers.image.revision="${AIFT_BUILD_COMMIT}"

USER appuser

EXPOSE 8000

# exec so SIGTERM reaches uvicorn (clean container stops); workers default 1 —
# NER/OCR models are cached per process, so extra workers multiply RAM and
# cold starts. Raise only after measuring.
CMD ["sh", "-c", "exec python -m uvicorn aift_gateway:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1} --no-access-log"]

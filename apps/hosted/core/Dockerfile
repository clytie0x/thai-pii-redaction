# Build only the context prepared by scripts/prepare_hosted_core.py.
# The shared app/pii_redactor packages come from one explicit first-party wheel.
FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

WORKDIR /app

ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# PyThaiNLP model home (runtime user has no home dir)
ENV PYTHAINLP_DATA=/opt/pythainlp-data
ENV HOME=/tmp

# The canonical wheel includes the preferred Thai font and its OFL notice.
# No OS-package or model download occurs in this artifact-only build.

# Dependency layers before code so rebuilds hit cache (20-min runner budget).
# The preserved runtime graph is exact and hash-locked. The Hosted overlay
# remains a separate, explicitly pinned security update.
COPY requirements.lock requirements-aift-security.lock core-wheel.lock CORE_BUILD_IDENTITY.json ./
COPY wheels ./wheels
COPY wheelhouse ./wheelhouse
COPY verify_core_install.py verify_core_cache.py ./
RUN python -m pip install --no-cache-dir --no-index --find-links=wheelhouse --require-hashes -r requirements.lock \
    && python -m pip install --no-cache-dir --no-index --find-links=wheelhouse --no-deps --require-hashes -r requirements-aift-security.lock \
    && python -m pip install --no-cache-dir --no-index --no-deps --require-hashes -r core-wheel.lock \
    && python -m pip check \
    && python verify_core_install.py

# Verify the complete supplied asset tree against the certified model digest.
COPY verify_thainer_assets.py ./
COPY models /opt/pythainlp-data
RUN python verify_thainer_assets.py

# From here the container must behave identically with or without egress.
ENV PYTHAINLP_OFFLINE=1

# Keep runtime contents explicit. Even if a future ignore rule regresses, a
# service-local credential or test artifact cannot be copied into the image.
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

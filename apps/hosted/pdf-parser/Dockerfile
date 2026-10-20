FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

WORKDIR /app
ENV HOME=/work \
    LANG=C.UTF-8 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock \
    && python -m pip check

COPY protocol.py parser_engine.py worker.py server.py healthcheck.py ./
COPY scenarios ./scenarios
COPY licenses ./licenses
COPY THIRD_PARTY_NOTICES.md ./

RUN useradd --uid 1000 --no-create-home --shell /bin/false appuser \
    && mkdir -p /run/aiguard-pdf /work \
    && chown -R appuser:appuser /app /run/aiguard-pdf /work \
    && chmod 0770 /run/aiguard-pdf \
    && python - <<'PY'
import pikepdf
import pdfplumber
import pypdfium2
assert pikepdf.__version__ == "10.10.0", pikepdf.__version__
assert pikepdf.__libqpdf_version__ == "12.3.2", pikepdf.__libqpdf_version__
assert pdfplumber.__version__ == "0.11.10", pdfplumber.__version__
assert pypdfium2.version.PYPDFIUM_INFO.tag == "5.12.1", pypdfium2.version.PYPDFIUM_INFO.tag
PY

ARG AIFT_BUILD_COMMIT=local-working-tree
LABEL org.opencontainers.image.revision="${AIFT_BUILD_COMMIT}" \
      org.opencontainers.image.title="AI Guard secretless PDF parser"

USER appuser
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD ["python", "/app/healthcheck.py"]
CMD ["/usr/bin/env", "-i", "HOME=/work", "LANG=C.UTF-8", "PATH=/usr/local/bin:/usr/bin:/bin", "PYTHONUTF8=1", "PYTHONDONTWRITEBYTECODE=1", "PYTHONUNBUFFERED=1", "python", "/app/server.py"]

# amphrang[server] in a container. The server is local-first by design: a
# non-loopback bind needs both --allow-remote and AMPHRANG_API_KEY, so this image
# refuses to start without the key rather than expose the data plane.
#
#   docker build -t amphrang .
#   docker run --rm -p 8000:8000 -e AMPHRANG_API_KEY=change-me amphrang
#
# Requests then carry `X-Amphrang-Key: change-me`.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 amphrang
WORKDIR /build
COPY pyproject.toml VERSION README.md LICENSE NOTICE MANIFEST.in ./
COPY amphrang ./amphrang
RUN pip install ".[server]" && rm -rf /build

# Model download as the runtime user so it lands in that user's home.
USER amphrang
WORKDIR /home/amphrang
COPY --chown=amphrang scripts/prewarm_ner.py /tmp/prewarm_ner.py
RUN python /tmp/prewarm_ner.py && rm /tmp/prewarm_ner.py

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
ENTRYPOINT ["amphrang", "serve", "--host", "0.0.0.0", "--port", "8000", "--allow-remote", "--no-browser"]

# amprang[server] in a container. The server is local-first by design: a
# non-loopback bind needs both --allow-remote and AMPRANG_API_KEY, so this image
# refuses to start without the key rather than expose the data plane.
#
#   docker build -t amprang .
#   docker run --rm -p 8000:8000 -e AMPRANG_API_KEY=change-me amprang
#
# Requests then carry `X-Amprang-Key: change-me`. The
# browser playground is off (--no-demo); drop that flag to serve /demo too.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 amprang
WORKDIR /build
COPY pyproject.toml VERSION README.md LICENSE NOTICE MANIFEST.in requirements*.txt ./
COPY amprang ./amprang
RUN pip install ".[server]" && rm -rf /build

# Model download as the runtime user so it lands in that user's home.
USER amprang
WORKDIR /home/amprang
COPY --chown=amprang scripts/prewarm_ner.py /tmp/prewarm_ner.py
RUN python /tmp/prewarm_ner.py && rm /tmp/prewarm_ner.py

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
ENTRYPOINT ["amprang", "serve", "--host", "0.0.0.0", "--port", "8000", "--allow-remote", "--no-browser", "--no-demo"]

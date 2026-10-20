FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY server.py /app/server.py
RUN useradd --no-create-home --shell /bin/false appuser && chown -R appuser /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=2s --retries=5 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=1).read()"]
CMD ["python", "/app/server.py"]

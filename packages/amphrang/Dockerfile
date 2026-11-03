# syntax=docker/dockerfile:1
# Build context contains qualified wheels/, wheelhouse/, models/ and qualification/.
# Each artifact directory has an exact SHA256SUMS inventory, supplied by the builder.
# No registry resolution or model download happens in this image build.
FROM python:3.13-slim

ARG AIGUARD_BUILD_COMMIT
LABEL org.opencontainers.image.revision=$AIGUARD_BUILD_COMMIT

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INDEX=1 \
    PYTHAINLP_DATA=/opt/pythainlp-data \
    PYTHAINLP_OFFLINE=1 \
    AMPHRANG_NER_ENGINE=thainer \
    AMPHRANG_AUDIT_STDOUT=1

RUN useradd --create-home --uid 10001 amphrang
COPY wheels /opt/wheels
COPY wheelhouse /opt/wheelhouse
COPY models /opt/pythainlp-data
COPY qualification/check_sdk_installed.py /opt/check_sdk_installed.py
RUN --network=none python -c 'import sys; from pathlib import Path; sys.path.insert(0,"/opt"); from check_sdk_installed import verify_supplied_tree; [verify_supplied_tree(Path(path)) for path in sys.argv[1:]]' /opt/wheels /opt/wheelhouse /opt/pythainlp-data \
    && set -- /opt/wheels/amphrang-*.whl && test "$#" = 1 && sdk_wheel="$1" \
    && set -- /opt/wheels/thai_pii_redaction_core-*.whl && test "$#" = 1 && core_wheel="$1" \
    && python -m pip install --no-index --find-links /opt/wheelhouse "$core_wheel" "$sdk_wheel[server]" \
    && python -m pip check \
    && target=$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])') \
    && python -I /opt/check_sdk_installed.py "$target" "$sdk_wheel" "$core_wheel"

USER amphrang
WORKDIR /home/amphrang
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
ENTRYPOINT ["amphrang", "serve", "--host", "0.0.0.0", "--port", "8000", "--allow-remote", "--no-browser"]

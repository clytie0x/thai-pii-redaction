# AI Guard AIFT — `api` proxy image. Config is baked (the platform's check
# stage rejects relative bind mounts); the official entrypoint runs envsubst
# on /etc/nginx/templates/*.template with NGINX_ENVSUBST_FILTER.
# nginx:1.29-alpine digest resolved from Docker Hub 2026-07-28 (docker image
# inspect after pull). BusyBox wget verified present in this exact image
# (used by the compose healthcheck to probe straight through to core).
FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de

RUN rm /etc/nginx/conf.d/default.conf
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY healthcheck.sh /usr/local/bin/aift-healthcheck
RUN chmod 0555 /usr/local/bin/aift-healthcheck
ARG AIFT_BUILD_COMMIT=local-working-tree
LABEL org.opencontainers.image.revision="${AIFT_BUILD_COMMIT}"
EXPOSE 8000

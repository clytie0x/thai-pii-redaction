# AI Guard AIFT — `web` static frontend. Same verified digest as api/.
FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY product.css privacy.html terms.html help.html downloads.html robots.txt sitemap.xml /usr/share/nginx/html/
COPY healthcheck.sh /usr/local/bin/aift-healthcheck
RUN chmod 0555 /usr/local/bin/aift-healthcheck
ARG AIFT_BUILD_COMMIT=local-working-tree
LABEL org.opencontainers.image.revision="${AIFT_BUILD_COMMIT}"
EXPOSE 3000

# AI Guard AIFT — `web` static frontend. Same verified digest as api/.
FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de

RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY home.css home.js app.html app.css hosted3-app.js product.css privacy.html terms.html help.html downloads.html developers.html 404.html robots.txt sitemap.xml /usr/share/nginx/html/
COPY assets/ai-guard-mark.svg assets/ai-guard-mark-one-color.svg assets/ai-guard-mark-inverse.svg assets/ai-guard-favicon.svg assets/ai-guard-favicon-inverse.svg /usr/share/nginx/html/assets/
COPY assets/fonts/anuphan-thai.woff2 assets/fonts/anuphan-latin.woff2 assets/fonts/OFL-Anuphan.txt /usr/share/nginx/html/assets/fonts/
COPY healthcheck.sh /usr/local/bin/aift-healthcheck
RUN chmod 0555 /usr/local/bin/aift-healthcheck
ARG AIFT_BUILD_COMMIT=local-working-tree
LABEL org.opencontainers.image.revision="${AIFT_BUILD_COMMIT}"
EXPOSE 3000

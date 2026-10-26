# Base images are pinned by multi-arch digest (linux/amd64 and linux/arm64 verified).
# Update digests deliberately via a reviewed PR; never use mutable tags.
FROM node:25-trixie-slim@sha256:aabbe39553d15ede8a97cc60c9e1a97034ff772afcf696ea42b94e7f5f2ec71b AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
# Exact lockfile, no install scripts (see .npmrc).
RUN npm ci
COPY . .
# Shows the development sign-in form. Release builds pass "false".
ARG VITE_DEV_LOGIN=false
ENV VITE_DEV_LOGIN=${VITE_DEV_LOGIN}
RUN npm run build && npm run check:build

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03 AS runtime
# The image ships curl and four optional nginx modules we never load. They only add image,
# font and network libraries that need patching, so they are removed.
USER 0:0
RUN apk del --no-cache curl nginx-module-geoip nginx-module-image-filter \
    nginx-module-njs nginx-module-xslt
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]

# Base images are pinned by multi-arch digest (linux/amd64 and linux/arm64 verified).
# Update digests deliberately via a reviewed PR; never use mutable tags.
FROM ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 AS uv

FROM python:3.13-slim-trixie@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim-trixie@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS runtime
# The runtime never installs packages; removing pip also drops its vendored libraries
# (urllib3, msgpack, ...) that scanners would otherwise report as part of the image.
RUN python -m pip uninstall -y pip \
    && groupadd --system --gid 10001 alvo \
    && useradd --system --uid 10001 --gid alvo --no-create-home --shell /usr/sbin/nologin alvo
WORKDIR /app
# Code and dependencies are root-owned and read-only for the runtime user.
COPY --from=builder /app/.venv /app/.venv
COPY alembic.ini ./
COPY alembic ./alembic
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]
CMD ["uvicorn", "--factory", "alvo.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]

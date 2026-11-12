FROM node:22-bookworm-slim AS webui

WORKDIR /build/webui
COPY webui/package.json webui/package-lock.json ./
RUN npm ci
COPY webui/ ./
RUN mkdir -p /build/api && npm run build


FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    DISPLAY=:99 \
    HOME=/home/collector

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        fonts-noto-cjk \
        novnc \
        openssl \
        tini \
        websockify \
        x11-utils \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY . .
COPY --from=webui /build/api/webui ./api/webui

RUN groupadd --gid 10001 collector \
    && useradd --uid 10001 --gid collector --create-home --shell /usr/sbin/nologin collector \
    && mkdir -p /app/browser_data /app/data \
    && chown -R 10001:10001 /app /home/collector \
    && chmod 0755 /app/deploy/container-entrypoint.sh

USER 10001:10001

EXPOSE 8080 6080

ENTRYPOINT ["/usr/bin/tini", "--", "/app/deploy/container-entrypoint.sh"]

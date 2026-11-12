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
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
    UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple \
    UV_HTTP_TIMEOUT=300 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    DISPLAY=:99 \
    HOME=/home/collector

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
    && python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" uv==0.9.5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project

COPY . .
COPY --from=webui /build/api/webui ./api/webui

RUN groupadd --gid 10001 collector \
    && useradd --uid 10001 --gid collector --home-dir /home/collector --no-create-home --shell /usr/sbin/nologin collector \
    && install -d -o 10001 -g 10001 /home/collector /app/browser_data /app/data \
    && chown -R 10001:10001 /app /home/collector \
    && chmod 0755 /app/deploy/container-entrypoint.sh

USER 10001:10001

EXPOSE 8080 6080

ENTRYPOINT ["/app/deploy/container-entrypoint.sh"]

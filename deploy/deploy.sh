#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

require_command docker
require_command git
load_production_environment

docker info >/dev/null 2>&1 || die "Docker 服务不可用"
release_commit="$(git -C "${PROJECT_ROOT}" rev-parse --short=12 HEAD)"
export COLLECTOR_IMAGE="collector-cloud-app:${release_commit}"

info "正在构建镜像 ${COLLECTOR_IMAGE}"
compose build app

info "正在启动 PostgreSQL"
compose up -d --no-deps postgres
wait_for_container_health postgres 60

info "正在执行数据库迁移"
compose run --rm --no-deps --entrypoint /app/.venv/bin/alembic app upgrade head

info "正在启动应用与浏览器运行时"
compose up -d --no-deps app
wait_for_app_ready 90

info "部署完成"
info "工作台：https://<Tailscale 主机名>/"
info "noVNC：https://<Tailscale 主机名>:8443/vnc.html"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

require_command docker
load_production_environment

info "Compose 服务状态"
compose ps

info "容器健康状态"
for service in postgres app; do
    container_id="$(compose ps -q "${service}")"
    if [[ -z "${container_id}" ]]; then
        printf '%s：未运行\n' "${service}"
        continue
    fi
    docker inspect --format '{{.Name}}：{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}"
done

info "Tailscale Serve 路由"
if command -v tailscale >/dev/null 2>&1 && tailscale status >/dev/null 2>&1; then
    tailscale serve status
else
    printf 'Tailscale 未连接\n'
fi

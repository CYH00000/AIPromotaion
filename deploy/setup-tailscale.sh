#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

require_command tailscale
load_production_environment

if ! tailscale status >/dev/null 2>&1; then
    die "Tailscale 未登录或未连接，请先完成 tailscale up"
fi

info "正在发布私有 HTTPS 工作台路由"
tailscale serve --bg --https=443 "http://127.0.0.1:${APP_BIND_PORT}" >/dev/null

info "正在发布私有 HTTPS noVNC 路由"
tailscale serve --bg --https=8443 "http://127.0.0.1:${NOVNC_BIND_PORT}" >/dev/null

tailscale serve status
info "公网 80/443/8080/6080 不应在云安全组中开放"
info "noVNC 地址：https://<Tailscale 主机名>:8443/vnc.html"

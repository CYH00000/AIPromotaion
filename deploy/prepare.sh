#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

require_command docker
require_command python3
require_command tailscale
require_command openssl
require_command stat
require_command find

[[ -r /etc/os-release ]] || die "无法识别操作系统"
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || die "首版生产部署仅支持 Ubuntu"
[[ "${VERSION_ID:-}" == "24.04" ]] || die "首版生产部署要求 Ubuntu 24.04"

docker info >/dev/null 2>&1 || die "Docker 服务不可用或当前用户无访问权限"
docker compose version >/dev/null 2>&1 || die "Docker Compose 插件不可用"

load_production_environment

if ! tailscale status >/dev/null 2>&1; then
    die "Tailscale 未登录或未连接，请先完成 tailscale up"
fi

available_kb="$(df -Pk "${PROJECT_ROOT}" | awk 'NR==2 {print $4}')"
if [[ -z "${available_kb}" || "${available_kb}" -lt 20971520 ]]; then
    die "项目所在磁盘至少需要 20 GB 可用空间"
fi

memory_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
if [[ -n "${memory_kb}" && "${memory_kb}" -lt 8000000 ]]; then
    printf '[部署警告] 当前内存不足 8 GB；两个浏览器并行采集可能出现资源不足。\n' >&2
fi

info "宿主机与生产配置检查通过"
info "未安装或修改任何系统软件"

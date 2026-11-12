#!/usr/bin/env bash
set -Eeuo pipefail

export DISPLAY="${DISPLAY:-:99}"
export HOME="${HOME:-/home/collector}"

readonly APP_ROOT="/app"
readonly VNC_PASSWORD_FILE="/tmp/collector-vnc.pass"
SERVICES=()


log() {
    printf '[容器入口] %s\n' "$*" >&2
}


validate_production_configuration() {
    log "正在校验生产配置"
    "${APP_ROOT}/.venv/bin/python" - <<'PY'
import os
import sys

from deploy.validate_config import validate_environment

errors = validate_environment(os.environ)
if errors:
    print("生产配置校验失败：", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(2)
print("生产配置校验通过")
PY
}


cleanup() {
    local status=$?
    trap - EXIT
    log "正在停止容器内服务"
    for pid in "${SERVICES[@]:-}"; do
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            kill -TERM "${pid}" 2>/dev/null || true
        fi
    done
    for pid in "${SERVICES[@]:-}"; do
        if [[ -n "${pid}" ]]; then
            wait "${pid}" 2>/dev/null || true
        fi
    done
    rm -f "${VNC_PASSWORD_FILE}"
    exit "${status}"
}
trap cleanup EXIT
trap 'exit 143' TERM INT


wait_for_display() {
    local attempt
    for attempt in $(seq 1 60); do
        if [[ -S /tmp/.X11-unix/X99 ]] && xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
            return 0
        fi
        if ! kill -0 "${xvfb_pid}" 2>/dev/null; then
            log "Xvfb 提前退出"
            return 1
        fi
        sleep 0.5
    done
    log "等待 Xvfb 超时"
    return 1
}


cd "${APP_ROOT}"
validate_production_configuration
mkdir -p "${APP_ROOT}/browser_data" "${APP_ROOT}/data"

log "正在启动虚拟显示器"
Xvfb :99 -screen 0 1440x900x24 -nolisten tcp -ac &
xvfb_pid=$!
SERVICES+=("${xvfb_pid}")
wait_for_display

umask 077
x11vnc -storepasswd "${NOVNC_PASSWORD}" "${VNC_PASSWORD_FILE}" >/dev/null 2>&1
log "正在启动私有 VNC 服务"
x11vnc \
    -display "${DISPLAY}" \
    -rfbport 5900 \
    -localhost \
    -forever \
    -shared \
    -rfbauth "${VNC_PASSWORD_FILE}" \
    -noxdamage \
    >/tmp/x11vnc.log 2>&1 &
x11vnc_pid=$!
SERVICES+=("${x11vnc_pid}")

log "正在启动 noVNC 网页服务"
websockify --web=/usr/share/novnc 6080 127.0.0.1:5900 &
websockify_pid=$!
SERVICES+=("${websockify_pid}")

log "正在应用数据库迁移"
.venv/bin/alembic upgrade head

log "正在启动采集工作台服务"
.venv/bin/uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips='*' &
uvicorn_pid=$!
SERVICES+=("${uvicorn_pid}")

log "服务已启动"
set +e
wait -n
exit_code=$?
set -e
log "关键子进程已退出，容器将整体停止，退出码：${exit_code}"
exit "${exit_code}"

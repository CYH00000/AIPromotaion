#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd -- "${DEPLOY_DIR}/.." && pwd -P)"
readonly DEPLOY_DIR PROJECT_ROOT
readonly COMPOSE_FILE="${DEPLOY_DIR}/compose.prod.yml"
readonly PRODUCTION_ENV_FILE="${PRODUCTION_ENV_FILE:-${DEPLOY_DIR}/.env.production}"
readonly DEFAULT_COMPOSE_PROJECT_NAME="collector-cloud"
PYTHON_BIN="${PYTHON_BIN:-python3}"


die() {
    printf '[部署失败] %s\n' "$*" >&2
    exit 1
}


info() {
    printf '[部署] %s\n' "$*"
}


require_command() {
    command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}


assert_production_file() {
    [[ -f "${PRODUCTION_ENV_FILE}" ]] || die "生产配置文件不存在：${PRODUCTION_ENV_FILE}"
    [[ -r "${PRODUCTION_ENV_FILE}" ]] || die "生产配置文件不可读"
    local owner mode
    if [[ "$(uname -s)" == "Linux" ]]; then
        owner="$(stat -c '%u' "${PRODUCTION_ENV_FILE}")"
        [[ "${owner}" == "$(id -u)" ]] || die "生产配置文件必须属于当前部署用户"
        mode="$(stat -c '%a' "${PRODUCTION_ENV_FILE}")"
        if find "${PRODUCTION_ENV_FILE}" -maxdepth 0 -perm /077 -print -quit | grep -q .; then
            die "生产配置文件权限过宽，请执行 chmod 600 <生产配置文件>（当前 ${mode}）"
        fi
    else
        info "非 Linux 开发主机：跳过 POSIX 秘密文件权限检查"
    fi
}


load_production_environment() {
    require_command "${PYTHON_BIN}"
    assert_production_file
    "${PYTHON_BIN}" "${DEPLOY_DIR}/validate_config.py" --file "${PRODUCTION_ENV_FILE}"
    set -a
    # shellcheck disable=SC1090
    source "${PRODUCTION_ENV_FILE}"
    set +a
    export PRODUCTION_ENV_FILE
    COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-${DEFAULT_COMPOSE_PROJECT_NAME}}"
    APP_BIND_PORT="${APP_BIND_PORT:-8080}"
    NOVNC_BIND_PORT="${NOVNC_BIND_PORT:-6080}"
    if [[ -z "${COLLECTOR_IMAGE:-}" ]] && command -v git >/dev/null 2>&1; then
        local release_commit
        if release_commit="$(git -C "${PROJECT_ROOT}" rev-parse --short=12 HEAD 2>/dev/null)"; then
            COLLECTOR_IMAGE="collector-cloud-app:${release_commit}"
        fi
    fi
    COLLECTOR_IMAGE="${COLLECTOR_IMAGE:-collector-cloud-app:local}"
    export COMPOSE_PROJECT_NAME APP_BIND_PORT NOVNC_BIND_PORT COLLECTOR_IMAGE
}


compose() {
    docker compose \
        --project-name "${COMPOSE_PROJECT_NAME:-${DEFAULT_COMPOSE_PROJECT_NAME}}" \
        --env-file "${PRODUCTION_ENV_FILE}" \
        -f "${COMPOSE_FILE}" \
        "$@"
}


openssl_passphrase_path() {
    local path="$1"
    if command -v cygpath >/dev/null 2>&1 && [[ "${path}" =~ ^/[a-zA-Z]/ ]]; then
        cygpath -w "${path}"
    else
        printf '%s' "${path}"
    fi
}


wait_for_container_health() {
    local service="$1" attempts="${2:-60}" container_id status
    for ((attempt = 1; attempt <= attempts; attempt++)); do
        container_id="$(compose ps -q "${service}")"
        if [[ -n "${container_id}" ]]; then
            status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")"
            if [[ "${status}" == "healthy" ]]; then
                info "${service} 健康检查通过"
                return 0
            fi
            if [[ "${status}" == "unhealthy" || "${status}" == "exited" ]]; then
                die "${service} 健康检查失败，请运行 bash deploy/logs.sh ${service}"
            fi
        fi
        sleep 2
    done
    die "等待 ${service} 健康检查超时"
}


wait_for_app_ready() {
    local attempts="${1:-60}"
    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if compose exec -T app .venv/bin/python -c \
            "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/ready', timeout=3)" \
            >/dev/null 2>&1; then
            info "应用就绪检查通过"
            return 0
        fi
        sleep 2
    done
    die "等待应用就绪超时，请运行 bash deploy/logs.sh app"
}

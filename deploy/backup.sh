#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

require_command docker
require_command openssl
require_command sha256sum
load_production_environment

passphrase_file="${BACKUP_PASSPHRASE_FILE:-}"
[[ -n "${passphrase_file}" ]] || die "未配置 BACKUP_PASSPHRASE_FILE"
[[ "${passphrase_file}" == /* ]] || die "BACKUP_PASSPHRASE_FILE 必须使用绝对路径"
openssl_passphrase_file="$(openssl_passphrase_path "${passphrase_file}")"
[[ -f "${passphrase_file}" ]] || die "备份口令文件不存在"
if [[ "$(uname -s)" == "Linux" ]]; then
    [[ "$(stat -c '%u' "${passphrase_file}")" == "$(id -u)" ]] || die "备份口令文件必须属于当前部署用户"
    if find "${passphrase_file}" -maxdepth 0 -perm /077 -print -quit | grep -q .; then
        die "备份口令文件权限必须为 600"
    fi
fi
[[ -s "${passphrase_file}" ]] || die "备份口令文件不能为空"

backup_root="${BACKUP_DIR:-${DEPLOY_DIR}/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${backup_root}/${timestamp}"

umask 077
compose up -d --no-deps postgres
wait_for_container_health postgres 60
docker image inspect "${COLLECTOR_IMAGE}" >/dev/null 2>&1 || die "生产镜像 ${COLLECTOR_IMAGE} 不存在，请先执行部署"
compose exec -T postgres pg_dump --version >/dev/null
compose exec -T app sh -c 'command -v tar >/dev/null' >/dev/null

mkdir -p "${backup_root}"
chmod 700 "${backup_root}"
mkdir "${backup_dir}"
chmod 700 "${backup_dir}"

app_was_running=0
if [[ -n "$(compose ps --status running -q app)" ]]; then
    app_was_running=1
fi

restart_app_after_backup() {
    if [[ "${app_was_running}" == "1" ]]; then
        compose start app >/dev/null 2>&1 || printf '[部署警告] 备份结束后未能自动启动应用\n' >&2
    fi
}
trap restart_app_after_backup EXIT

info "正在暂停应用以创建一致性备份"
compose stop app >/dev/null

info "正在备份 PostgreSQL"
compose exec -T postgres pg_dump \
    --format=custom \
    --no-owner \
    --no-acl \
    --username "${POSTGRES_DB_USER}" \
    --dbname "${POSTGRES_DB_NAME}" \
    | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 210000 \
        -pass "file:${openssl_passphrase_file}" \
        -out "${backup_dir}/postgres.dump.enc"

info "正在备份浏览器资料"
compose run --rm -T --no-deps --entrypoint sh app \
    -c 'tmp="$(mktemp)" && tar -C /app/browser_data -czf "$tmp" . && gzip -t "$tmp" && cat "$tmp"; status=$?; rm -f "$tmp"; exit "$status"' \
    | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 210000 \
        -pass "file:${openssl_passphrase_file}" \
        -out "${backup_dir}/browser_data.tar.gz.enc"

info "正在备份项目数据"
compose run --rm -T --no-deps --entrypoint sh app \
    -c 'tmp="$(mktemp)" && tar -C /app/data -czf "$tmp" . && gzip -t "$tmp" && cat "$tmp"; status=$?; rm -f "$tmp"; exit "$status"' \
    | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 210000 \
        -pass "file:${openssl_passphrase_file}" \
        -out "${backup_dir}/project_data.tar.gz.enc"

migration_version="$(compose exec -T postgres psql \
    --username "${POSTGRES_DB_USER}" \
    --dbname "${POSTGRES_DB_NAME}" \
    --tuples-only --no-align --command 'SELECT version_num FROM alembic_version LIMIT 1' 2>/dev/null || true)"
git_commit="$(git -C "${PROJECT_ROOT}" rev-parse HEAD 2>/dev/null || printf 'unknown')"
{
    printf 'created_at=%s\n' "${timestamp}"
    printf 'git_commit=%s\n' "${git_commit}"
    printf 'alembic_version=%s\n' "${migration_version:-unknown}"
    printf 'compose_project=%s\n' "${COMPOSE_PROJECT_NAME}"
} >"${backup_dir}/metadata.txt"

for artifact in \
    postgres.dump.enc \
    browser_data.tar.gz.enc \
    project_data.tar.gz.enc; do
    [[ -s "${backup_dir}/${artifact}" ]] || die "备份产物为空：${artifact}"
    [[ "$(head -c 8 "${backup_dir}/${artifact}")" == "Salted__" ]] || die "备份产物加密头无效：${artifact}"
done

(
    cd "${backup_dir}"
    sha256sum \
        postgres.dump.enc \
        browser_data.tar.gz.enc \
        project_data.tar.gz.enc \
        metadata.txt \
        >SHA256SUMS
)
chmod 600 "${backup_dir}"/*
info "加密备份完成：${backup_dir}"

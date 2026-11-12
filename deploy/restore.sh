#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

if [[ $# -lt 2 || "$1" != "--confirm" ]]; then
    die "恢复会覆盖数据库、浏览器资料和项目数据；请执行 bash deploy/restore.sh --confirm <备份目录>"
fi

require_command docker
require_command openssl
require_command sha256sum
require_command head
load_production_environment

passphrase_file="${BACKUP_PASSPHRASE_FILE:-}"
[[ -n "${passphrase_file}" ]] || die "未配置 BACKUP_PASSPHRASE_FILE"
[[ "${passphrase_file}" == /* ]] || die "BACKUP_PASSPHRASE_FILE 必须使用绝对路径"
openssl_passphrase_file="$(openssl_passphrase_path "${passphrase_file}")"
[[ -f "${passphrase_file}" ]] || die "备份口令文件不存在"
if [[ "$(uname -s)" == "Linux" ]]; then
    if find "${passphrase_file}" -maxdepth 0 -perm /077 -print -quit | grep -q .; then
        die "备份口令文件权限必须为 600"
    fi
fi
[[ -s "${passphrase_file}" ]] || die "备份口令文件不能为空"

backup_input="$2"
[[ -d "${backup_input}" ]] || die "备份目录不存在：${backup_input}"
backup_dir="$(cd -- "${backup_input}" && pwd -P)"

for artifact in \
    postgres.dump.enc \
    browser_data.tar.gz.enc \
    project_data.tar.gz.enc \
    metadata.txt \
    SHA256SUMS; do
    [[ -s "${backup_dir}/${artifact}" ]] || die "备份缺少文件：${artifact}"
done

info "正在校验备份完整性"
(
    cd "${backup_dir}"
    sha256sum -c SHA256SUMS >/dev/null
)
for artifact in postgres.dump.enc browser_data.tar.gz.enc project_data.tar.gz.enc; do
    [[ "$(head -c 8 "${backup_dir}/${artifact}")" == "Salted__" ]] || die "备份加密头无效：${artifact}"
done

compose up -d --no-deps postgres
wait_for_container_health postgres 60
docker image inspect "${COLLECTOR_IMAGE}" >/dev/null 2>&1 || die "生产镜像 ${COLLECTOR_IMAGE} 不存在，请先执行部署"

info "正在停止应用，恢复期间不会启动采集 Worker"
compose stop app >/dev/null 2>&1 || true

info "正在清空并恢复 PostgreSQL"
compose exec -T postgres psql \
    --username "${POSTGRES_DB_USER}" \
    --dbname "${POSTGRES_DB_NAME}" \
    --set ON_ERROR_STOP=1 \
    --command 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' >/dev/null
openssl enc -d -aes-256-cbc -pbkdf2 -iter 210000 \
    -pass "file:${openssl_passphrase_file}" \
    -in "${backup_dir}/postgres.dump.enc" \
    | compose exec -T postgres pg_restore \
        --username "${POSTGRES_DB_USER}" \
        --dbname "${POSTGRES_DB_NAME}" \
        --no-owner \
        --no-acl \
        --exit-on-error

restore_volume() {
    local archive="$1" target="$2"
    info "正在恢复 ${target}"
    compose run --rm -T --no-deps --entrypoint sh app \
        -c "find '${target}' -mindepth 1 -delete"
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 210000 \
        -pass "file:${openssl_passphrase_file}" \
        -in "${backup_dir}/${archive}" \
        | compose run --rm -T --no-deps --entrypoint sh app \
            -c "tar -xzf - -C '${target}'"
}

restore_volume browser_data.tar.gz.enc /app/browser_data
restore_volume project_data.tar.gz.enc /app/data

info "正在检查并应用数据库迁移"
compose run --rm -T --no-deps --entrypoint sh app -c 'cd /app && .venv/bin/alembic upgrade head'

info "正在重新启动应用"
compose up -d --no-deps app
wait_for_app_ready 90
info "恢复完成：${backup_dir}"

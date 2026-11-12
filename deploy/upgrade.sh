#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

require_command git
load_production_environment

target="${1:-origin/main}"
previous_commit="$(git -C "${PROJECT_ROOT}" rev-parse HEAD)"

if [[ -n "$(git -C "${PROJECT_ROOT}" status --porcelain --untracked-files=no)" ]]; then
    die "存在未提交的已跟踪文件修改，拒绝升级"
fi

info "正在获取 ${target}"
git -C "${PROJECT_ROOT}" fetch --prune origin
target_commit="$(git -C "${PROJECT_ROOT}" rev-parse --verify "${target}^{commit}")"

info "升级前正在创建加密备份"
(cd "${PROJECT_ROOT}" && bash deploy/backup.sh)

info "正在切换代码到 ${target_commit}"
git -C "${PROJECT_ROOT}" checkout --detach "${target_commit}"

if (cd "${PROJECT_ROOT}" && bash deploy/deploy.sh); then
    info "升级完成：${target_commit}"
    exit 0
fi

printf '[升级失败] 正在恢复原代码检出 %s\n' "${previous_commit}" >&2
git -C "${PROJECT_ROOT}" checkout --detach "${previous_commit}" >/dev/null 2>&1 || true
printf '如需数据库回滚，请先核对迁移兼容性，再执行：bash deploy/restore.sh --confirm <备份目录>\n' >&2
exit 1

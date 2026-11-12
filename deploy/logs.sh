#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

require_command docker

service="${1:-app}"
follow="${2:-}"
case "${service}" in
    app|postgres) ;;
    *) die "用法：bash deploy/logs.sh [app|postgres] [--follow]" ;;
esac
if [[ -n "${follow}" && "${follow}" != "--follow" ]]; then
    die "仅支持可选参数 --follow"
fi

load_production_environment
if [[ "${follow}" == "--follow" ]]; then
    compose logs --tail=200 --follow "${service}"
else
    compose logs --tail=200 "${service}"
fi

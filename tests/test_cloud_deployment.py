from pathlib import Path

import pytest
import yaml


def valid_environment() -> dict[str, str]:
    return {
        "POSTGRES_DB_NAME": "collector",
        "POSTGRES_DB_USER": "collector",
        "POSTGRES_DB_PWD": "database-password-123",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "administrator-password-123",
        "SESSION_COOKIE_SECURE": "true",
        "NOVNC_PASSWORD": "vnc-password-123",
        "ENABLE_CDP_MODE": "false",
        "AI_FILTER_API_BASE_URL": "",
        "AI_FILTER_API_KEY": "",
        "AI_FILTER_MODEL": "",
    }


def test_production_environment_accepts_complete_private_config():
    from deploy.validate_config import validate_environment

    assert validate_environment(valid_environment()) == []


def test_production_environment_rejects_insecure_cookie():
    from deploy.validate_config import validate_environment

    values = valid_environment()
    values["SESSION_COOKIE_SECURE"] = "false"
    assert validate_environment(values) == ["SESSION_COOKIE_SECURE 必须为 true"]


def test_production_environment_rejects_partial_ai_configuration():
    from deploy.validate_config import validate_environment

    values = valid_environment()
    values["AI_FILTER_API_BASE_URL"] = "https://api.example.com"
    assert validate_environment(values) == ["AI_FILTER 三项配置必须同时为空或同时填写"]


def test_production_environment_requires_https_for_ai_endpoint():
    from deploy.validate_config import validate_environment

    values = valid_environment()
    values.update(
        {
            "AI_FILTER_API_BASE_URL": "http://api.example.com",
            "AI_FILTER_API_KEY": "key",
            "AI_FILTER_MODEL": "model",
        }
    )
    assert validate_environment(values) == ["AI_FILTER_API_BASE_URL 必须使用 HTTPS"]


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("POSTGRES_DB_NAME", "", "POSTGRES_DB_NAME 不能为空"),
        ("POSTGRES_DB_USER", "", "POSTGRES_DB_USER 不能为空"),
        ("POSTGRES_DB_PWD", "replace-with-local-only-password", "POSTGRES_DB_PWD 不能使用示例占位值"),
        ("ADMIN_USERNAME", "", "ADMIN_USERNAME 不能为空"),
        ("ADMIN_PASSWORD", "short", "ADMIN_PASSWORD 至少需要 16 个字符"),
        ("ADMIN_PASSWORD", "replace-with-a-unique-password", "ADMIN_PASSWORD 不能使用示例占位值"),
        ("NOVNC_PASSWORD", "short", "NOVNC_PASSWORD 至少需要 12 个字符"),
        ("ENABLE_CDP_MODE", "true", "生产环境不得启用 ENABLE_CDP_MODE"),
    ],
)
def test_production_environment_rejects_unsafe_values(key: str, value: str, message: str):
    from deploy.validate_config import validate_environment

    values = valid_environment()
    values[key] = value
    assert message in validate_environment(values)


def load_production_compose() -> dict:
    return yaml.safe_load(Path("deploy/compose.prod.yml").read_text(encoding="utf-8"))


def test_compose_publishes_only_loopback_ports():
    compose = load_production_compose()
    services = compose["services"]
    assert services["postgres"].get("ports") is None
    assert services["app"]["ports"] == [
        "127.0.0.1:${APP_BIND_PORT:-8080}:8080",
        "127.0.0.1:${NOVNC_BIND_PORT:-6080}:6080",
    ]
    rendered = str(compose)
    assert "9222" not in rendered
    assert "0.0.0.0:8080" not in rendered


def test_compose_uses_private_persistent_storage_and_healthchecks():
    compose = load_production_compose()
    services = compose["services"]
    assert "healthcheck" in services["app"]
    assert "healthcheck" in services["postgres"]
    assert set(compose["volumes"]) == {"postgres_data", "browser_data", "project_data"}
    assert services["postgres"]["volumes"] == ["postgres_data:/var/lib/postgresql"]
    assert services["app"]["depends_on"]["postgres"]["condition"] == "service_healthy"


def test_compose_keeps_database_private_while_allowing_platform_egress():
    compose = load_production_compose()
    services = compose["services"]
    assert services["app"]["networks"] == ["collector_private", "collector_egress"]
    assert services["postgres"]["networks"] == ["collector_private"]
    assert compose["networks"]["collector_private"]["internal"] is True
    assert compose["networks"]["collector_egress"].get("internal", False) is False


def test_entrypoint_supervises_all_private_services():
    script = Path("deploy/container-entrypoint.sh").read_text(encoding="utf-8")
    for command in ("Xvfb :99", "x11vnc", "websockify", "alembic upgrade head", "uvicorn"):
        assert command in script
    assert "wait -n" in script
    assert "trap cleanup" in script
    assert "readonly SERVICES" not in script


def test_dockerfile_builds_webui_and_uses_playwright_image():
    dockerfile = Path("deploy/Dockerfile").read_text(encoding="utf-8")
    assert "FROM node:22-bookworm-slim AS webui" in dockerfile
    assert "mcr.microsoft.com/playwright/python:v1.61.0-noble" in dockerfile
    assert "npm ci" in dockerfile
    assert "uv sync --frozen --no-install-project" in dockerfile
    assert 'ENTRYPOINT ["/app/deploy/container-entrypoint.sh"]' in dockerfile


def test_dockerignore_excludes_local_data_and_secrets():
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")
    for entry in (".git", ".venv", "webui/node_modules", "browser_data", "data", "deploy/.env.production", "deploy/backups"):
        assert entry in dockerignore


def test_host_scripts_are_safe_and_relative_to_project_root():
    for name in ("prepare.sh", "deploy.sh", "status.sh", "logs.sh", "setup-tailscale.sh", "upgrade.sh"):
        text = Path("deploy", name).read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in text
        assert "deploy/.env.production" not in text


def test_tailscale_setup_uses_loopback_upstreams():
    text = Path("deploy/setup-tailscale.sh").read_text(encoding="utf-8")
    assert "http://127.0.0.1:" in text
    assert "tailscale serve" in text
    assert "0.0.0.0" not in text


def test_backup_encrypts_every_data_artifact_and_requires_passphrase():
    backup = Path("deploy/backup.sh").read_text(encoding="utf-8")
    assert "pg_dump" in backup
    assert "openssl enc -aes-256-cbc" in backup
    assert "BACKUP_PASSPHRASE_FILE" in backup
    assert "browser_data" in backup
    assert "project_data" in backup
    assert "chmod 700" in backup
    assert "compose exec -T app tar" not in backup
    assert "compose run --rm -T --no-deps --entrypoint sh app" in backup
    assert "gzip -t" in backup
    assert 'docker image inspect "${COLLECTOR_IMAGE}"' in backup


def test_restore_requires_explicit_confirmation_and_preserves_private_volumes():
    restore = Path("deploy/restore.sh").read_text(encoding="utf-8")
    assert '"$1" != "--confirm"' in restore
    assert "pg_restore" in restore
    assert "browser_data" in restore
    assert "project_data" in restore
    assert 'docker image inspect "${COLLECTOR_IMAGE}"' in restore


def test_backup_uses_openssl_compatible_passphrase_paths():
    library = Path("deploy/lib.sh").read_text(encoding="utf-8")
    backup = Path("deploy/backup.sh").read_text(encoding="utf-8")
    restore = Path("deploy/restore.sh").read_text(encoding="utf-8")
    assert "openssl_passphrase_path" in library
    assert "openssl_passphrase_file" in backup
    assert "openssl_passphrase_file" in restore


def test_lifecycle_scripts_resolve_the_deployed_commit_image():
    library = Path("deploy/lib.sh").read_text(encoding="utf-8")
    assert "COLLECTOR_IMAGE" in library
    assert "rev-parse --short=12 HEAD" in library
    assert "collector-cloud-app:${release_commit}" in library


def test_runbook_documents_private_access_and_critical_operations():
    text = Path("docs/deployment/cloud-deployment.md").read_text(encoding="utf-8")
    for phrase in ("Tailscale Serve", "noVNC", "backup.sh", "restore.sh", "upgrade.sh", "9222"):
        assert phrase in text
    assert "公网开放 8080" not in text

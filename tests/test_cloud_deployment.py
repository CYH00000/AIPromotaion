from pathlib import Path

import pytest


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

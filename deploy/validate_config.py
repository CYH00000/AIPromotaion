#!/usr/bin/env python3
"""Validate production-only environment settings without revealing their values."""

from __future__ import annotations

import argparse
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_KEYS = (
    "POSTGRES_DB_NAME",
    "POSTGRES_DB_USER",
    "POSTGRES_DB_PWD",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "NOVNC_PASSWORD",
)
AI_KEYS = (
    "AI_FILTER_API_BASE_URL",
    "AI_FILTER_API_KEY",
    "AI_FILTER_MODEL",
)
PLACEHOLDER_PREFIXES = ("replace-with", "change-me", "<", "your-")


def _text(values: Mapping[str, object], key: str) -> str:
    value = values.get(key, "")
    return str(value).strip() if value is not None else ""


def _is_placeholder(value: str) -> bool:
    normalized = value.casefold()
    return not value or normalized.startswith(PLACEHOLDER_PREFIXES)


def validate_environment(values: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_KEYS:
        if not _text(values, key):
            errors.append(f"{key} 不能为空")

    for key in ("POSTGRES_DB_PWD", "ADMIN_PASSWORD", "NOVNC_PASSWORD"):
        value = _text(values, key)
        if value and _is_placeholder(value):
            errors.append(f"{key} 不能使用示例占位值")

    admin_password = _text(values, "ADMIN_PASSWORD")
    if admin_password and not _is_placeholder(admin_password) and len(admin_password) < 16:
        errors.append("ADMIN_PASSWORD 至少需要 16 个字符")

    novnc_password = _text(values, "NOVNC_PASSWORD")
    if novnc_password and not _is_placeholder(novnc_password) and len(novnc_password) < 12:
        errors.append("NOVNC_PASSWORD 至少需要 12 个字符")

    if _text(values, "SESSION_COOKIE_SECURE").casefold() != "true":
        errors.append("SESSION_COOKIE_SECURE 必须为 true")
    if _text(values, "ENABLE_CDP_MODE").casefold() == "true":
        errors.append("生产环境不得启用 ENABLE_CDP_MODE")

    ai_values = [_text(values, key) for key in AI_KEYS]
    if any(ai_values) and not all(ai_values):
        errors.append("AI_FILTER 三项配置必须同时为空或同时填写")
    elif all(ai_values):
        endpoint = urlparse(ai_values[0])
        if endpoint.scheme.casefold() != "https" or not endpoint.netloc:
            errors.append("AI_FILTER_API_BASE_URL 必须使用 HTTPS")

    return errors


def load_environment(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"生产配置文件不存在：{path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key.replace("_", "").isalnum():
            continue
        raw_value = raw_value.strip()
        if raw_value[:1] in {"'", '"'}:
            try:
                parts = shlex.split(raw_value, comments=True, posix=True)
            except ValueError as exc:
                raise ValueError(f"生产配置文件第 {raw_line!r} 行格式无效") from exc
            value = parts[0] if parts else ""
        else:
            value = raw_value.split(" #", 1)[0].rstrip()
        values[key] = value
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验采集工作台生产配置")
    parser.add_argument("--file", required=True, type=Path, help="生产环境配置文件")
    args = parser.parse_args(argv)
    try:
        values = load_environment(args.file)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    errors = validate_environment(values)
    if errors:
        print("生产配置校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2

    print("生产配置校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

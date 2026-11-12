#!/usr/bin/env python3
"""Small API smoke test for the packaged cloud deployment."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from deploy.validate_config import load_environment


class SmokeFailure(RuntimeError):
    pass


class SmokeCookiePolicy(http.cookiejar.DefaultCookiePolicy):
    """Allow the test client to carry production Secure cookies over local HTTP."""

    def return_ok_secure(self, cookie, request) -> bool:
        return True


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.csrf_token = ""
        jar = http.cookiejar.CookieJar(policy=SmokeCookiePolicy())
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def request(
        self,
        method: str,
        path: str,
        *,
        expected: int | tuple[int, ...],
        payload: dict[str, Any] | None = None,
        csrf: bool = False,
    ) -> tuple[int, bytes]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRF-Token"] = self.csrf_token
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                status, content = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, content = exc.code, exc.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SmokeFailure(f"无法连接服务：{exc.__class__.__name__}") from exc

        expected_codes = (expected,) if isinstance(expected, int) else expected
        if status not in expected_codes:
            raise SmokeFailure(f"{method} {path} 返回 {status}，预期 {expected_codes}")
        return status, content

    def csrf(self) -> None:
        _, content = self.request("GET", "/api/auth/csrf", expected=200)
        try:
            self.csrf_token = str(json.loads(content)["csrf_token"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SmokeFailure("CSRF 响应格式无效") from exc


def administrator_credentials(env_file: Path | None) -> tuple[str, str]:
    values = load_environment(env_file) if env_file else {}
    username = os.getenv("COLLECTOR_ADMIN_USERNAME") or values.get("ADMIN_USERNAME", "")
    password = os.getenv("COLLECTOR_ADMIN_PASSWORD") or values.get("ADMIN_PASSWORD", "")
    if not username or not password:
        raise SmokeFailure("未提供管理员用户名或密码")
    return username, password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="验证云端工作台健康、登录、任务列表和登出")
    parser.add_argument("--env-file", type=Path, help="读取 ADMIN_USERNAME 和 ADMIN_PASSWORD 的环境文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = os.getenv("COLLECTOR_BASE_URL", "").strip()
    if not base_url:
        raise SmokeFailure("必须设置 COLLECTOR_BASE_URL")
    username, password = administrator_credentials(args.env_file)
    api = ApiClient(base_url)

    _, health = api.request("GET", "/health/ready", expected=200)
    if json.loads(health).get("status") != "ready":
        raise SmokeFailure("就绪探针状态不是 ready")
    print("健康检查：通过")

    api.request("GET", "/api/tasks", expected=401)
    print("未登录拦截：通过")

    api.csrf()
    api.request(
        "POST",
        "/api/auth/login",
        expected=200,
        payload={"username": username, "password": password},
        csrf=True,
    )
    _, me_content = api.request("GET", "/api/auth/me", expected=200)
    if str(json.loads(me_content).get("username", "")) != username:
        raise SmokeFailure("登录身份与管理账号不一致")
    print("CSRF 登录：通过")

    api.csrf()
    _, tasks_content = api.request("GET", "/api/tasks", expected=200)
    tasks = json.loads(tasks_content)
    if not isinstance(tasks, dict) or not isinstance(tasks.get("items"), list):
        raise SmokeFailure("任务列表响应格式无效")
    print(f"任务列表：通过（{len(tasks['items'])} 项）")

    api.request("POST", "/api/auth/logout", expected=204, csrf=True)
    api.request("GET", "/api/tasks", expected=401)
    print("退出登录：通过")
    print("云端工作台 API 冒烟测试：全部通过")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SmokeFailure, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"云端工作台 API 冒烟测试失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc

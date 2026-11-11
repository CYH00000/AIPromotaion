# -*- coding: utf-8 -*-
"""UI smoke acceptance test for the local workspace."""

import re
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


BASE = "http://127.0.0.1:8080"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def credentials() -> tuple[str, str]:
    values = {}
    for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value.strip()
    return values["ADMIN_USERNAME"], values["ADMIN_PASSWORD"]


def visible_or_none(locator) -> bool:
    try:
        return locator.count() > 0 and locator.first.is_visible()
    except Exception:
        return False


def main() -> int:
    username, password = credentials()
    browser = None
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.goto(BASE, wait_until="networkidle")

        page.locator("input[autocomplete=username]").fill(username)
        page.locator("input[autocomplete=current-password]").fill(password)
        page.get_by_role("button", name="登录").click()
        page.get_by_text("采集工作台", exact=True).wait_for(timeout=15000)
        assert page.get_by_text("Light", exact=True).count() == 0
        assert any(
            page.get_by_text(label, exact=True).count() > 0
            for label in ("浅色", "深色", "自动")
        )

        try:
            confirm = page.get_by_role("button", name="我已知晓并同意上述条款")
            confirm.wait_for(timeout=5000)
            confirm.click()
        except PlaywrightTimeoutError:
            pass
        try:
            page.get_by_role("button", name="跳过检测").wait_for(timeout=3000)
            page.get_by_role("button", name="跳过检测").click()
        except PlaywrightTimeoutError:
            pass

        assert page.get_by_role("tab", name="任务管理").is_visible()
        assert page.get_by_role("tab", name="评论结果").is_visible()
        assert page.get_by_role("tab", name="账号管理").is_visible()

        page.get_by_role("tab", name="账号管理").click()
        page.get_by_text("抖音", exact=True).first.wait_for(timeout=10000)
        page.get_by_text("小红书", exact=True).first.wait_for(timeout=10000)
        assert page.get_by_text("标准模式", exact=False).first.is_visible()

        page.get_by_role("tab", name="任务管理").click()
        task_row = page.locator("tr", has_text=re.compile(r"E2E-Search-")).first
        task_row.wait_for(timeout=10000)
        task_row.get_by_role("button", name="详情").click()
        page.get_by_text("运行详情", exact=True).wait_for(timeout=10000)
        page.get_by_text("结果摘要", exact=False).wait_for(timeout=10000)
        page.get_by_text("最近采集日志", exact=True).wait_for(timeout=10000)
        page.get_by_role("button", name="关闭").last.click()

        page.get_by_role("button", name="新建任务").click()
        page.get_by_label("内容排序").wait_for(timeout=10000)
        page.get_by_label("发布时间").wait_for(timeout=10000)
        assert page.locator('option[value="latest"]').count() > 0
        assert page.locator('option[value="7"]').count() > 0
        page.get_by_role("button", name="关闭").first.click()

        screenshot = Path.home() / "AppData" / "Local" / "Temp" / "codex-e2e-ui.png"
        page.screenshot(path=str(screenshot), full_page=True)
        print(f"UI_SCREENSHOT {screenshot}", flush=True)

        page.get_by_role("button", name="退出").click()
        page.locator("input[autocomplete=username]").wait_for(timeout=10000)
        print("ALL_UI_E2E_OK", flush=True)
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

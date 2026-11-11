# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from api.schemas.crawler import (
    CrawlerStartRequest,
    CrawlerTypeEnum,
    LoginTypeEnum,
    PlatformEnum,
    SaveDataOptionEnum,
)
from api.services.crawler_manager import crawler_manager


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BROWSER_DATA_DIR = PROJECT_ROOT / "browser_data"
PLATFORM_LABELS = {"dy": "抖音", "xhs": "小红书"}
PLATFORMS = tuple(PLATFORM_LABELS)


class AccountError(Exception):
    """Base error for account-management operations."""


class AccountBusyError(AccountError):
    """Raised when a collector or login process is already running."""


class AccountPlatformError(AccountError):
    """Raised for unsupported platforms or unsafe filesystem targets."""


_login_states: dict[str, dict[str, Any]] = {
    platform: {"state": "idle", "started_at": None, "error": None}
    for platform in PLATFORMS
}
_login_tasks: dict[str, asyncio.Task[None]] = {}


def _require_platform(platform: str) -> str:
    if platform not in PLATFORM_LABELS:
        raise AccountPlatformError(f"Unsupported platform: {platform}")
    return platform


def profile_dir(platform: str) -> Path:
    _require_platform(platform)
    suffix = config.USER_DATA_DIR % platform
    name = f"cdp_{suffix}" if config.ENABLE_CDP_MODE else suffix
    return BROWSER_DATA_DIR / name


def login_marker_path(platform: str) -> Path:
    _require_platform(platform)
    return BROWSER_DATA_DIR / ".login_state" / f"{platform}.json"


def _read_marker(platform: str) -> datetime | None:
    try:
        data = json.loads(login_marker_path(platform).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    value = data.get("logged_in_at") if isinstance(data, dict) else None
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _directory_time(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def _process_running() -> bool:
    process = crawler_manager.process
    return process is not None and process.poll() is None


def login_active() -> bool:
    return any(state["state"] == "running" for state in _login_states.values())


def account_status() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for platform, label in PLATFORM_LABELS.items():
        path = profile_dir(platform)
        configured = path.is_dir()
        last_login = _read_marker(platform)
        if last_login is None and configured:
            last_login = _directory_time(path)
        state = _login_states[platform]
        items.append(
            {
                "platform": platform,
                "label": label,
                "configured": configured,
                "profile_mode": "cdp" if config.ENABLE_CDP_MODE else "standard",
                "last_login_at": _iso(last_login),
                "login_state": state["state"],
                "login_started_at": _iso(state["started_at"]),
                "login_error": state["error"],
            }
        )
    return items


async def start_login(platform: str) -> dict[str, str]:
    _require_platform(platform)
    if login_active() or _process_running():
        raise AccountBusyError("A collector process is already running.")

    started_at = datetime.now(timezone.utc)
    state = _login_states[platform]
    state.update({"state": "running", "started_at": started_at, "error": None})

    request = CrawlerStartRequest(
        platform=PlatformEnum(platform),
        login_type=LoginTypeEnum.QRCODE,
        crawler_type=CrawlerTypeEnum.SEARCH,
        save_option=SaveDataOptionEnum.JSONL,
        headless=False,
        login_only=True,
    )
    started = await crawler_manager.start(request)
    if not started:
        state.update({"state": "failed", "error": "Could not start the login process."})
        raise AccountBusyError("A collector process is already running.")

    _login_tasks[platform] = asyncio.create_task(_watch_login(platform, started_at))
    return {"platform": platform, "status": "started"}


async def _watch_login(platform: str, started_at: datetime) -> None:
    process = crawler_manager.process
    if process is not None:
        await asyncio.to_thread(process.wait)
        if crawler_manager._read_task:
            try:
                await crawler_manager._read_task
            except Exception:
                pass

    marker = login_marker_path(platform)
    try:
        written_at = datetime.fromtimestamp(marker.stat().st_mtime, tz=timezone.utc)
        succeeded = written_at >= started_at
    except OSError:
        succeeded = False

    state = _login_states[platform]
    if succeeded:
        state.update({"state": "succeeded", "error": None})
    else:
        state.update(
            {
                "state": "failed",
                "error": "Sign-in did not complete. Check the browser window and try again.",
            }
        )


async def unbind(platform: str) -> None:
    _require_platform(platform)
    if login_active() or _process_running():
        raise AccountBusyError("A collector process is already running.")

    profile = profile_dir(platform)
    resolved = profile.resolve()
    root = BROWSER_DATA_DIR.resolve()
    if resolved.parent != root or resolved == root:
        raise AccountPlatformError("Refusing to remove an unexpected path.")
    if resolved.exists():
        if not resolved.is_dir():
            raise AccountPlatformError("Refusing to remove a non-directory target.")
        shutil.rmtree(resolved)

    try:
        login_marker_path(platform).unlink()
    except FileNotFoundError:
        pass
    _login_states[platform].update({"state": "idle", "started_at": None, "error": None})

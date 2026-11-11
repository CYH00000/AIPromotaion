# Platform Account Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local account-management view for Douyin and Xiaohongshu with QR login, login-state status, and unbind.

**Architecture:** Add a `--login_only` mode to the existing MediaCrawler CLI, expose account status/login/unbind through a FastAPI router and service, and add an account tab to the React workspace. Login state is read from `browser_data/` profiles and a login marker written after a successful login check; no new database table.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy session utilities (no new table), pytest/pytest-asyncio, React/Vite/TypeScript, existing `crawler_manager` subprocess boundary.

---

## File Structure

- `config/base_config.py` — add `LOGIN_ONLY`.
- `cmd_arg/arg.py` — add `--login_only`, apply it to config.
- `main.py` — write the login marker and exit after a login-only run.
- `media_platform/douyin/core.py` — return before crawling in login-only mode.
- `media_platform/xhs/core.py` — return before crawling in login-only mode.
- `api/schemas/crawler.py` — add `login_only` to `CrawlerStartRequest`.
- `api/services/crawler_manager.py` — pass `--login_only` to the subprocess.
- `api/services/account_service.py` — new account state/login/unbind service.
- `api/routers/accounts.py` — new REST endpoints.
- `api/routers/__init__.py`, `api/main.py` — register the router.
- `api/services/collection_worker.py` — pause claiming runs while a login is active.
- `webui/src/lib/collectorApi.ts` — account API client and types.
- `webui/src/components/collector/AccountsPanel.tsx` — new account cards.
- `webui/src/components/collector/CollectorWorkspace.tsx` — add the account tab.
- `tests/test_account_service.py` — service tests.
- `tests/test_login_only_flag.py` — CLI flag test.

## Task 1: Add the login-only CLI mode

**Files:**
- Modify: `config/base_config.py`
- Modify: `cmd_arg/arg.py`
- Modify: `main.py`
- Modify: `media_platform/douyin/core.py`
- Modify: `media_platform/xhs/core.py`
- Modify: `api/schemas/crawler.py`
- Modify: `api/services/crawler_manager.py`
- Test: `tests/test_login_only_flag.py`

- [ ] **Step 1: Write the failing flag test**

```python
import asyncio

import config
from cmd_arg import parse_cmd


def test_login_only_flag_sets_config():
    previous = config.LOGIN_ONLY
    try:
        asyncio.run(parse_cmd(["--login_only", "true"]))
        assert config.LOGIN_ONLY is True
    finally:
        config.LOGIN_ONLY = previous
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.tools\uv.exe run --env-file .env pytest tests/test_login_only_flag.py -q`

Expected: FAIL because `config.LOGIN_ONLY` and the `--login_only` option do not exist.

- [ ] **Step 3: Implement the flag**

In `config/base_config.py`, after `LOGIN_TYPE`, add:

```python
LOGIN_ONLY = False  # When true, complete login and exit without crawling.
```

In `cmd_arg/arg.py`, add a Typer option next to `headless`:

```python
login_only: Annotated[
    str,
    typer.Option(
        "--login_only",
        help="Complete login state and exit without crawling",
        rich_help_panel="Account Configuration",
        show_default=True,
    ),
] = str(config.LOGIN_ONLY),
```

Parse it and persist it with the other booleans:

```python
enable_login_only = _to_bool(login_only)
...
config.LOGIN_ONLY = enable_login_only
...
login_only=config.LOGIN_ONLY,
```

In `api/schemas/crawler.py`, add to `CrawlerStartRequest`:

```python
login_only: bool = False
```

In `api/services/crawler_manager.py`, inside `_build_command` before `return cmd`:

```python
if config.login_only:
    cmd.extend(["--login_only", "true"])
```

In both `media_platform/douyin/core.py` and `media_platform/xhs/core.py`, after the login block and before `crawler_type_var.set(...)`, add:

```python
if config.LOGIN_ONLY:
    utils.logger.info("[LoginOnly] Login state verified; skipping crawl")
    return
```

In `main.py`, add imports for `json`, `datetime`, `timezone`, and `Path`, then after `await crawler.start()`:

```python
if config.LOGIN_ONLY:
    marker_dir = PROJECT_ROOT / "browser_data" / ".login_state"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / f"{config.PLATFORM}.json"
    marker_path.write_text(
        json.dumps(
            {
                "platform": config.PLATFORM,
                "logged_in_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    print(f"[Main] Login-only mode completed for {config.PLATFORM}")
    return
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.tools\uv.exe run --env-file .env pytest tests/test_login_only_flag.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/base_config.py cmd_arg/arg.py main.py media_platform/douyin/core.py media_platform/xhs/core.py api/schemas/crawler.py api/services/crawler_manager.py tests/test_login_only_flag.py
git commit -m "feat: add login-only collector mode"
```

## Task 2: Build the account service

**Files:**
- Create: `api/services/account_service.py`
- Test: `tests/test_account_service.py`

- [ ] **Step 1: Write failing service tests**

```python
from datetime import datetime, timezone

import pytest

import api.services.account_service as account_service
import config


@pytest.fixture
def browser_root(tmp_path, monkeypatch):
    monkeypatch.setattr(account_service, "BROWSER_DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ENABLE_CDP_MODE", False)
    account_service._login_states.update(
        {platform: {"state": "idle", "started_at": None, "error": None} for platform in account_service.PLATFORMS}
    )
    return tmp_path


def test_profile_dir_uses_standard_and_cdp_names(browser_root, monkeypatch):
    assert account_service.profile_dir("dy") == browser_root / "dy_user_data_dir"
    monkeypatch.setattr(config, "ENABLE_CDP_MODE", True)
    assert account_service.profile_dir("dy") == browser_root / "cdp_dy_user_data_dir"
    with pytest.raises(account_service.AccountPlatformError):
        account_service.profile_dir("bad")


def test_status_reads_marker_and_falls_back_to_directory(browser_root):
    profile = account_service.profile_dir("xhs")
    profile.mkdir()
    marker = account_service.login_marker_path("xhs")
    marker.parent.mkdir(parents=True)
    marker.write_text('{"logged_in_at": "2026-11-11T08:00:00+00:00"}', encoding="utf-8")

    items = {item["platform"]: item for item in account_service.account_status()}

    assert items["xhs"]["configured"] is True
    assert items["xhs"]["last_login_at"].startswith("2026-11-11T08:00:00")
    assert items["dy"]["configured"] is False


@pytest.mark.asyncio
async def test_unbind_removes_profile_and_marker(browser_root):
    profile = account_service.profile_dir("dy")
    profile.mkdir()
    marker = account_service.login_marker_path("dy")
    marker.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")

    await account_service.unbind("dy")

    assert not profile.exists()
    assert not marker.exists()
    await account_service.unbind("dy")  # idempotent


@pytest.mark.asyncio
async def test_unbind_rejects_path_outside_browser_data(browser_root, monkeypatch):
    outside = browser_root.parent / "outside"
    monkeypatch.setattr(account_service, "profile_dir", lambda platform: outside)
    with pytest.raises(account_service.AccountPlatformError):
        await account_service.unbind("dy")


@pytest.mark.asyncio
async def test_login_rejects_busy_process(browser_root, monkeypatch):
    class RunningProcess:
        def poll(self):
            return None

    monkeypatch.setattr(account_service.crawler_manager, "process", RunningProcess())
    with pytest.raises(account_service.AccountBusyError):
        await account_service.start_login("dy")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.tools\uv.exe run --env-file .env pytest tests/test_account_service.py -q`

Expected: FAIL because `api.services.account_service` does not exist.

- [ ] **Step 3: Implement the service**

Create `api/services/account_service.py` with platform whitelisting, profile/marker paths, status reads, login process start, marker-based success detection, safe unbind, and a `login_active()` helper. Reuse `crawler_manager.start` with `login_only=True`, `login_type=QRCODE`, and `headless=False`. Do not return cookie values or full paths in `account_status()`.

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.tools\uv.exe run --env-file .env pytest tests/test_account_service.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/account_service.py tests/test_account_service.py
git commit -m "feat: add platform account service"
```

## Task 3: Expose account endpoints and pause the worker

**Files:**
- Create: `api/routers/accounts.py`
- Modify: `api/routers/__init__.py`
- Modify: `api/main.py`
- Modify: `api/services/collection_worker.py`
- Test: `tests/test_account_service.py` (service-level behavior)

- [ ] **Step 1: Add the router**

Create `api/routers/accounts.py` with:

- `GET /api/accounts` returning `{"items": account_status()}`;
- `POST /api/accounts/{platform}/login` returning 202 or mapping `AccountBusyError` to 409 and `AccountPlatformError` to 400;
- `DELETE /api/accounts/{platform}` returning 204, with the same error mapping.

Every route depends on `require_admin`; POST and DELETE also depend on `require_csrf`.

```python
# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from fastapi import APIRouter, Depends, HTTPException, status

from api.services.account_service import (
    AccountBusyError,
    AccountPlatformError,
    account_status,
    start_login,
    unbind,
)
from api.services.auth_service import require_admin, require_csrf


router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(_username: str = Depends(require_admin)):
    return {"items": account_status()}


@router.post("/{platform}/login", status_code=status.HTTP_202_ACCEPTED)
async def login_account(
    platform: str,
    _username: str = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
):
    try:
        return await start_login(platform)
    except AccountPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccountBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_account(
    platform: str,
    _username: str = Depends(require_admin),
    _csrf: None = Depends(require_csrf),
):
    try:
        await unbind(platform)
    except AccountPlatformError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AccountBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
```

- [ ] **Step 2: Register the router**

Export `accounts_router` from `api/routers/__init__.py` and include it in `api/main.py`:

```python
app.include_router(accounts_router, prefix="/api")
```

- [ ] **Step 3: Pause worker claiming during login**

In `api/services/collection_worker.py`, import `login_active` from `account_service` and add at the start of `_claim_next_run`:

```python
if login_active():
    return None
```

- [ ] **Step 4: Run backend tests**

Run: `.tools\uv.exe run --env-file .env pytest tests/test_account_service.py tests/test_login_only_flag.py tests/test_collection_pipeline.py tests/test_task_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/routers/accounts.py api/routers/__init__.py api/main.py api/services/collection_worker.py
git commit -m "feat: expose account management API"
```

## Task 4: Add the account-management UI

**Files:**
- Modify: `webui/src/lib/collectorApi.ts`
- Create: `webui/src/components/collector/AccountsPanel.tsx`
- Modify: `webui/src/components/collector/CollectorWorkspace.tsx`

- [ ] **Step 1: Add API types and calls**

In `collectorApi.ts`, add `AccountInfo` with `platform`, `label`, `configured`, `last_login_at`, `login_state`, `login_started_at`, and `login_error`. Add:

```ts
export const accountsApi = {
  async list() {
    const response = await api.get<{ items: AccountInfo[] }>('/accounts')
    return response.data.items
  },
  login: (platform: PlatformId) => mutate<{ platform: string; status: string }>(`/accounts/${platform}/login`),
  unbind: (platform: PlatformId) => mutate<void>(`/accounts/${platform}`, undefined, 'delete'),
}
```

- [ ] **Step 2: Build the account cards**

Create `AccountsPanel.tsx`:

- load accounts on mount;
- poll every 3 seconds while any `login_state === 'running'`;
- show platform name, `已登录过` / `未配置`, last login time;
- a `登录 / 验证登录态` button that calls `accountsApi.login` and shows a toast telling the user to scan in the opened browser;
- an `解绑` button that opens a Radix dialog and only calls `accountsApi.unbind` after confirmation;
- show a note that status is local configuration status and does not guarantee session validity;
- never render cookies or filesystem paths.

```tsx
import { useCallback, useEffect, useState } from 'react'
import { LogIn, ShieldOff } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  accountsApi,
  apiErrorMessage,
  type AccountInfo,
  type PlatformId,
} from '@/lib/collectorApi'

function formatDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function statusVariant(account: AccountInfo): 'running' | 'success' | 'idle' {
  if (account.login_state === 'running') return 'running'
  if (account.configured) return 'success'
  return 'idle'
}

function statusLabel(account: AccountInfo) {
  if (account.login_state === 'running') return '登录中'
  if (account.login_state === 'failed') return '登录失败'
  if (account.configured) return '已登录过'
  return '未配置'
}

export function AccountsPanel() {
  const [accounts, setAccounts] = useState<AccountInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [pendingPlatform, setPendingPlatform] = useState<PlatformId | null>(null)
  const [confirming, setConfirming] = useState<AccountInfo | null>(null)

  const refresh = useCallback(async () => {
    try {
      setAccounts(await accountsApi.list())
    } catch (error) {
      toast.error(apiErrorMessage(error))
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    void refresh().finally(() => setLoading(false))
  }, [refresh])

  const anyRunning = accounts.some((account) => account.login_state === 'running')
  useEffect(() => {
    if (!anyRunning) return
    const timer = window.setInterval(() => {
      void refresh()
    }, 3000)
    return () => window.clearInterval(timer)
  }, [anyRunning, refresh])

  const startLogin = async (platform: PlatformId) => {
    setPendingPlatform(platform)
    try {
      await accountsApi.login(platform)
      toast.success('已启动登录，请在弹出的浏览器中完成扫码')
      await refresh()
    } catch (error) {
      toast.error(apiErrorMessage(error))
    } finally {
      setPendingPlatform(null)
    }
  }

  const confirmUnbind = async () => {
    if (!confirming) return
    setPendingPlatform(confirming.platform)
    try {
      await accountsApi.unbind(confirming.platform)
      toast.success(`已解绑 ${confirming.label}`)
      setConfirming(null)
      await refresh()
    } catch (error) {
      toast.error(apiErrorMessage(error))
    } finally {
      setPendingPlatform(null)
    }
  }

  return (
    <section className="space-y-4">
      <Card className="p-4 text-xs leading-5 text-cyber-text-muted">
        登录态保存在本机 browser_data 配置目录。状态只表示本地配置存在，实际有效性由任务运行时的平台检查确认。
      </Card>
      <div className="grid gap-3 md:grid-cols-2">
        {accounts.map((account) => (
          <Card key={account.platform} className="flex flex-col gap-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-lg font-semibold text-cyber-text-primary">{account.label}</p>
                <p className="mt-1 text-xs text-cyber-text-muted">
                  {account.platform === 'dy' ? '抖音' : '小红书'} · 扫码登录
                </p>
              </div>
              <Badge variant={statusVariant(account)}>{statusLabel(account)}</Badge>
            </div>
            <div className="text-xs text-cyber-text-secondary">
              <p>最近登录：{formatDate(account.last_login_at)}</p>
              {account.login_error && <p className="mt-1 text-red-300">{account.login_error}</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={pendingPlatform === account.platform || account.login_state === 'running'}
                onClick={() => void startLogin(account.platform)}
              >
                <LogIn />{account.configured ? '验证登录态' : '登录'}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={!account.configured || pendingPlatform === account.platform}
                onClick={() => setConfirming(account)}
              >
                <ShieldOff />解绑
              </Button>
            </div>
          </Card>
        ))}
        {!accounts.length && (
          <p className="text-sm text-cyber-text-muted">
            {loading ? '正在读取账号状态…' : '没有可管理的平台。'}
          </p>
        )}
      </div>
      <Dialog open={confirming !== null} onOpenChange={(open) => { if (!open) setConfirming(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>解绑 {confirming?.label}</DialogTitle>
            <DialogDescription>
              这会删除本机的平台登录配置，之后需要重新扫码登录。已采集的数据不受影响。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirming(null)}>取消</Button>
            <Button
              variant="destructive"
              onClick={() => void confirmUnbind()}
              disabled={pendingPlatform !== null}
            >
              确认解绑
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}
```

- [ ] **Step 3: Add the workspace tab**

In `CollectorWorkspace.tsx`, extend `WorkspaceTab` to `'tasks' | 'comments' | 'accounts'`, add a third tab button `账号管理`, and render `<AccountsPanel />` when selected. Keep the existing task/comment panels unchanged.

- [ ] **Step 4: Build the frontend**

Run:

```powershell
Push-Location webui
npm run build
Pop-Location
```

Expected: `tsc -b` and `vite build` both succeed.

- [ ] **Step 5: Commit**

```bash
git add webui/src/lib/collectorApi.ts webui/src/components/collector/AccountsPanel.tsx webui/src/components/collector/CollectorWorkspace.tsx
git commit -m "feat: add account management tab"
```

## Task 5: Full verification

- [ ] **Step 1: Run the project test suite**

Run:

```powershell
.tools\uv.exe run --env-file .env pytest tests/test_account_service.py tests/test_login_only_flag.py tests/test_collection_limits.py tests/test_collection_pipeline.py tests/test_project_config_security.py tests/test_task_contracts.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Rebuild the frontend**

Run: `Push-Location webui; npm run build; Pop-Location`

Expected: build succeeds.

- [ ] **Step 3: Restart the local service and verify**

Restart the API, open `http://127.0.0.1:8080`, log in, and confirm the `账号管理` tab shows Douyin as configured (existing `browser_data/dy_user_data_dir`) and Xiaohongshu as unconfigured. Do not unbind a real account without explicit confirmation.

- [ ] **Step 4: Commit any verification-only adjustments**

```bash
git status --short
```

Expected: only intended files remain changed; no `.env` or `browser_data/` files are tracked.

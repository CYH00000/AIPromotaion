# 多平台按平台并行运行时 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让抖音和小红书各使用独立运行时并行采集，同时保证同平台串行、登录隔离、日志隔离和可扩展平台接入。

**Architecture:** 平台差异由不可变的 `PlatformDefinition` 描述，工厂函数创建 `PlatformRuntime`，注册表保存运行时，`CollectionWorkerSupervisor` 启动全局调度器和每平台一个 Worker。每个运行时拥有独立 `CrawlerManager`、当前运行、日志和登录状态。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、asyncio、PostgreSQL、React 18、TypeScript、Vite、pytest。

---

## 文件结构

- Create: `api/platforms/__init__.py`，导出平台定义查询接口。
- Create: `api/platforms/definitions.py`，声明 `PlatformDefinition`、抖音定义、小红书定义和注册表。
- Create: `api/services/platform_runtime.py`，定义工厂、`PlatformRuntime`、注册表和监督器。
- Modify: `api/services/crawler_manager.py`，为每个实例增加平台和当前运行标识，日志写入平台和运行 ID。
- Modify: `api/services/collection_worker.py`，将单例 Worker 泛化为 `PlatformCollectionWorker`。
- Modify: `api/services/account_service.py`，按平台查询运行时和忙状态。
- Modify: `api/schemas/crawler.py`，补充日志平台、运行 ID 和平台状态响应。
- Modify: `api/routers/crawler.py`，按平台启动、停止、状态和日志查询。
- Modify: `api/routers/collection.py`，增加平台能力与平台状态接口。
- Modify: `api/main.py`，启动和停止监督器。
- Modify: `api/services/__init__.py`，导出新运行时服务。
- Modify: `webui/src/lib/collectorApi.ts`，增加平台状态、能力和运行日志参数。
- Modify: `webui/src/components/collector/RunDetailDialog.tsx`，按平台和运行 ID 获取日志。
- Modify: `webui/src/components/collector/CollectorWorkspace.tsx`，展示平台级运行和排队状态。
- Modify: `webui/src/components/collector/TaskFormDialog.tsx`，平台选项从能力接口加载。
- Create: `tests/test_platform_runtime.py`，覆盖定义、工厂、注册表和监督器隔离。
- Modify: `tests/test_run_progress.py`、`tests/test_account_service.py`、`tests/test_account_api.py`、`tests/test_api_limits.py`，适配平台运行时。
- Modify: `README.md`、`CHANGELOG.md`、`docs/project-overview.md`、`docs/architecture/decisions.md`、`docs/architecture/backlog.md`，记录并行和扩展方式。

## Task 1: 平台定义与工厂

**Files:**
- Create: `api/platforms/__init__.py`
- Create: `api/platforms/definitions.py`
- Test: `tests/test_platform_runtime.py`

- [x] **Step 1: 写失败测试**

```python
from api.platforms import PLATFORM_DEFINITIONS, get_platform_definition


def test_platform_definitions_expose_both_supported_platforms():
    assert set(PLATFORM_DEFINITIONS) == {"dy", "xhs"}
    assert get_platform_definition("dy").label == "抖音"
    assert get_platform_definition("xhs").label == "小红书"


def test_unknown_platform_is_rejected_in_chinese():
    import pytest

    with pytest.raises(ValueError, match="不支持的平台"):
        get_platform_definition("unknown")
```

- [x] **Step 2: 验证测试失败**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py -q`

Expected: FAIL because `api.platforms` does not exist.

- [x] **Step 3: 实现平台定义**

```python
from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping


@dataclass(frozen=True)
class PlatformDefinition:
    platform_id: str
    label: str
    source_modes: frozenset[str]
    login_supported: bool
    content_filters_supported: bool
    content_id_field: str
    content_url_field: str
    source_parser: Callable[[str, str], str]


def _identity_source(mode: str, value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("来源不能为空")
    return text


PLATFORM_DEFINITIONS: Mapping[str, PlatformDefinition] = MappingProxyType({
    "dy": PlatformDefinition(
        platform_id="dy",
        label="抖音",
        source_modes=frozenset({"search", "detail"}),
        login_supported=True,
        content_filters_supported=True,
        content_id_field="aweme_id",
        content_url_field="aweme_url",
        source_parser=_identity_source,
    ),
    "xhs": PlatformDefinition(
        platform_id="xhs",
        label="小红书",
        source_modes=frozenset({"search", "detail"}),
        login_supported=True,
        content_filters_supported=True,
        content_id_field="note_id",
        content_url_field="note_url",
        source_parser=_identity_source,
    ),
})


def get_platform_definition(platform_id: str) -> PlatformDefinition:
    try:
        return PLATFORM_DEFINITIONS[platform_id]
    except KeyError as exc:
        raise ValueError(f"不支持的平台：{platform_id}") from exc
```

- [x] **Step 4: 验证测试通过**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py -q`

Expected: PASS.

## Task 2: 独立采集管理器

**Files:**
- Modify: `api/schemas/crawler.py`
- Modify: `api/services/crawler_manager.py`
- Test: `tests/test_platform_runtime.py`

- [x] **Step 1: 写失败测试**

```python
def test_crawler_managers_have_independent_process_and_log_state():
    from api.services.crawler_manager import CrawlerManager

    dy = CrawlerManager("dy")
    xhs = CrawlerManager("xhs")
    dy_log = dy._create_log_entry("抖音日志")
    xhs_log = xhs._create_log_entry("小红书日志")

    assert dy is not xhs
    assert dy.platform == "dy"
    assert xhs.platform == "xhs"
    assert dy_log.platform == "dy"
    assert xhs_log.platform == "xhs"
    assert dy.logs != xhs.logs
```

- [x] **Step 2: 验证测试失败**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py::test_crawler_managers_have_independent_process_and_log_state -q`

Expected: FAIL because the constructor does not accept a platform and logs have no platform.

- [x] **Step 3: 实现管理器标识与日志字段**

```python
class LogEntry(BaseModel):
    id: int
    timestamp: str
    level: Literal["info", "warning", "error", "success", "debug"]
    message: str
    platform: str | None = None
    run_id: str | None = None
```

```python
class CrawlerManager:
    def __init__(self, platform: str = "dy"):
        self.platform = platform
        self.current_run_id: str | None = None
        # 保留现有 lock、process、status、logs 等字段初始化

    def _create_log_entry(self, message: str, level: str = "info") -> LogEntry:
        self._log_id += 1
        entry = LogEntry(
            id=self._log_id,
            timestamp=datetime.now().strftime("%H:%M:%S"),
            level=level,
            message=message,
            platform=self.platform,
            run_id=self.current_run_id,
        )
        self._logs.append(entry)
        if len(self._logs) > 500:
            self._logs = self._logs[-500:]
        return entry
```

启动方法增加可选 `run_id`：

```python
async def start(
    self,
    config: CrawlerStartRequest,
    *,
    save_data_path: Optional[str] = None,
    extra_env: Optional[dict] = None,
    run_id: Optional[str] = None,
) -> bool:
    self.current_run_id = run_id or (extra_env or {}).get("COLLECTOR_RUN_ID")
    # 现有启动逻辑保持
```

- [x] **Step 4: 验证测试通过**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py::test_crawler_managers_have_independent_process_and_log_state -q`

Expected: PASS.

## Task 3: 平台运行时工厂与注册表

**Files:**
- Create: `api/services/platform_runtime.py`
- Test: `tests/test_platform_runtime.py`

- [x] **Step 1: 写失败测试**

```python
def test_factory_creates_isolated_runtime_for_each_platform():
    from api.platforms import get_platform_definition
    from api.services.platform_runtime import create_platform_runtime

    dy = create_platform_runtime(get_platform_definition("dy"))
    xhs = create_platform_runtime(get_platform_definition("xhs"))

    assert dy.platform == "dy"
    assert xhs.platform == "xhs"
    assert dy.worker is not xhs.worker
    assert dy.manager is not xhs.manager
    assert dy.manager.platform == "dy"
    assert xhs.manager.platform == "xhs"


def test_registry_returns_cached_runtime_and_rejects_duplicate_definition():
    from api.platforms import get_platform_definition
    from api.services.platform_runtime import PlatformRuntimeRegistry

    registry = PlatformRuntimeRegistry([get_platform_definition("dy")])
    assert registry.get("dy") is registry.get("dy")

    import pytest

    with pytest.raises(ValueError, match="重复"):
        registry.register(get_platform_definition("dy"))
```

- [x] **Step 2: 验证测试失败**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py -q -k "factory or registry"`

Expected: FAIL because `platform_runtime` does not exist.

- [x] **Step 3: 实现运行时和注册表**

```python
@dataclass
class PlatformRuntime:
    definition: PlatformDefinition
    manager: CrawlerManager
    worker: PlatformCollectionWorker

    @property
    def platform(self) -> str:
        return self.definition.platform_id


def create_platform_runtime(definition: PlatformDefinition) -> PlatformRuntime:
    manager = CrawlerManager(definition.platform_id)
    worker = PlatformCollectionWorker(definition, manager)
    return PlatformRuntime(definition=definition, manager=manager, worker=worker)


class PlatformRuntimeRegistry:
    def __init__(self, definitions=PLATFORM_DEFINITIONS.values()):
        self._runtimes: dict[str, PlatformRuntime] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: PlatformDefinition) -> PlatformRuntime:
        if definition.platform_id in self._runtimes:
            raise ValueError(f"平台运行时重复注册：{definition.platform_id}")
        runtime = create_platform_runtime(definition)
        self._runtimes[definition.platform_id] = runtime
        return runtime

    def get(self, platform_id: str) -> PlatformRuntime:
        try:
            return self._runtimes[platform_id]
        except KeyError as exc:
            raise ValueError(f"不支持的平台：{platform_id}") from exc

    def all(self) -> tuple[PlatformRuntime, ...]:
        return tuple(self._runtimes.values())
```

- [x] **Step 4: 验证测试通过**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py -q -k "factory or registry"`

Expected: PASS.

## Task 4: 平台 Worker 领取过滤与同平台串行

**Files:**
- Modify: `api/services/collection_worker.py`
- Test: `tests/test_platform_runtime.py`

- [x] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_platform_worker_claim_query_is_scoped_to_its_platform(monkeypatch):
    from api.platforms import get_platform_definition
    from api.services.collection_worker import PlatformCollectionWorker
    from api.services.crawler_manager import CrawlerManager

    worker = PlatformCollectionWorker(
        get_platform_definition("dy"), CrawlerManager("dy")
    )
    statements = []

    class FakeScalars:
        def all(self):
            return []

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeSession:
        async def execute(self, statement):
            statements.append(statement)
            return FakeResult()

    class SessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("api.services.collection_worker.collector_session", SessionContext)
    monkeypatch.setattr("api.services.collection_worker.login_active", lambda platform: False)

    assert await worker._claim_next_run() is None
    assert "collector_tasks.platform" in str(statements[0])
```

- [x] **Step 2: 验证测试失败**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py::test_platform_worker_claim_query_is_scoped_to_its_platform -q`

Expected: FAIL because `PlatformCollectionWorker` does not exist.

- [x] **Step 3: 将 Worker 参数化**

```python
class PlatformCollectionWorker:
    def __init__(self, definition: PlatformDefinition, manager: CrawlerManager):
        self.definition = definition
        self.platform = definition.platform_id
        self.manager = manager
        self.current_run_id: str | None = None
        self._runner: asyncio.Task | None = None
        self._stopping = False

    async def _claim_next_run(self):
        if login_active(self.platform):
            return None
        async with collector_session() as session:
            result = await session.execute(
                select(CollectionRun)
                .join(CollectionTask, CollectionRun.task_id == CollectionTask.id)
                .where(
                    CollectionRun.status == "queued",
                    CollectionTask.platform == self.platform,
                )
                .order_by(CollectionRun.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            run = result.scalar_one_or_none()
            # 保留现有任务停用、状态和进度初始化逻辑
            return {"run_id": run.id, "task_id": run.task_id, "config": run.config_snapshot}
```

所有对 `crawler_manager` 的调用改为 `self.manager`，所有进度日志 ID 使用 `self.manager._log_id`。

- [x] **Step 4: 验证测试通过**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py::test_platform_worker_claim_query_is_scoped_to_its_platform -q`

Expected: PASS.

## Task 5: 全局监督器

**Files:**
- Modify: `api/services/platform_runtime.py`
- Modify: `api/main.py`
- Modify: `api/services/__init__.py`
- Test: `tests/test_platform_runtime.py`

- [x] **Step 1: 写失败测试**

```python
@pytest.mark.asyncio
async def test_supervisor_starts_one_runner_per_registered_platform():
    from api.platforms import PLATFORM_DEFINITIONS
    from api.services.platform_runtime import CollectionWorkerSupervisor, PlatformRuntimeRegistry

    registry = PlatformRuntimeRegistry(PLATFORM_DEFINITIONS.values())
    supervisor = CollectionWorkerSupervisor(registry)
    started = []

    async def fake_start_worker(worker):
        started.append(worker.platform)

    for runtime in registry.all():
        runtime.worker.start = lambda runtime=runtime: fake_start_worker(runtime.worker)

    await supervisor.start()
    await supervisor.stop()
    assert sorted(started) == ["dy", "xhs"]
```

- [x] **Step 2: 验证测试失败**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py::test_supervisor_starts_one_runner_per_registered_platform -q`

Expected: FAIL because `CollectionWorkerSupervisor` does not exist.

- [x] **Step 3: 实现监督器生命周期**

```python
class CollectionWorkerSupervisor:
    def __init__(self, registry: PlatformRuntimeRegistry):
        self.registry = registry
        self._scheduler: asyncio.Task | None = None
        self._stopping = False
        self._recovery_done = False

    async def start(self):
        if not self._recovery_done:
            await self._recover_interrupted_runs()
            self._recovery_done = True
        self._stopping = False
        self._scheduler = asyncio.create_task(self._schedule_loop())
        for runtime in self.registry.all():
            await runtime.worker.start()

    async def stop(self):
        self._stopping = True
        if self._scheduler:
            self._scheduler.cancel()
        await asyncio.gather(
            *(runtime.worker.stop() for runtime in self.registry.all()),
            return_exceptions=True,
        )

    async def request_cancel(self, run_id: str):
        for runtime in self.registry.all():
            if runtime.worker.current_run_id == run_id:
                await runtime.worker.request_cancel(run_id)


platform_runtime_registry = PlatformRuntimeRegistry()
collection_worker_supervisor = CollectionWorkerSupervisor(platform_runtime_registry)
```

- [x] **Step 4: 验证测试通过**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py::test_supervisor_starts_one_runner_per_registered_platform -q`

Expected: PASS.

## Task 6: 账号登录与解绑隔离

**Files:**
- Modify: `api/services/account_service.py`
- Test: `tests/test_account_service.py`

- [x] **Step 1: 写失败测试**

```python
def test_login_busy_state_is_scoped_to_platform(monkeypatch):
    import api.services.account_service as module

    monkeypatch.setitem(
        module._login_states["dy"],
        "state",
        "running",
    )
    monkeypatch.setitem(
        module._login_states["xhs"],
        "state",
        "idle",
    )

    assert module.login_active("dy") is True
    assert module.login_active("xhs") is False
```

- [x] **Step 2: 验证测试失败**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_account_service.py::test_login_busy_state_is_scoped_to_platform -q`

Expected: FAIL because `login_active` takes no platform.

- [x] **Step 3: 使用运行时管理器**

```python
def login_active(platform: str) -> bool:
    _require_platform(platform)
    return _login_states[platform]["state"] == "running"


def _process_running(platform: str) -> bool:
    process = platform_runtime_registry.get(platform).manager.process
    return process is not None and process.poll() is None


async def start_login(platform: str) -> dict[str, str]:
    _require_platform(platform)
    if login_active(platform) or _process_running(platform):
        raise AccountBusyError(f"{PLATFORM_LABELS[platform]}已有采集或登录进程，请等待当前进程结束。")
    manager = platform_runtime_registry.get(platform).manager
    # 使用 manager.start；_watch_login 接收 platform 和 manager
```

解绑只检查 `login_active(platform) or _process_running(platform)`。

- [x] **Step 4: 验证测试通过**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_account_service.py tests\test_account_api.py -q`

Expected: PASS.

## Task 7: 平台状态与日志 API

**Files:**
- Modify: `api/schemas/crawler.py`
- Modify: `api/services/platform_runtime.py`
- Modify: `api/routers/collection.py`
- Modify: `api/routers/crawler.py`
- Test: `tests/test_platform_runtime.py`

- [x] **Step 1: 写失败测试**

```python
def test_platform_status_endpoint_requires_admin_and_returns_both_platforms(monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.services.platform_runtime import collection_worker_supervisor
    from api.services.auth_service import require_admin

    app.dependency_overrides[require_admin] = lambda: "admin"

    async def fake_statuses():
        return [
            {"platform": "dy", "label": "抖音", "queued_count": 1},
            {"platform": "xhs", "label": "小红书", "queued_count": 2},
        ]

    monkeypatch.setattr(collection_worker_supervisor, "platform_statuses", fake_statuses)
    response = TestClient(app).get("/api/platforms/status")
    assert response.status_code == 200
    assert [item["platform"] for item in response.json()["items"]] == ["dy", "xhs"]
```

- [x] **Step 2: 验证测试失败**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py::test_platform_status_endpoint_requires_admin_and_returns_both_platforms -q`

Expected: FAIL with 404.

- [x] **Step 3: 实现状态查询**

```python
async def platform_statuses(self) -> list[dict]:
    items = []
    async with collector_session() as session:
        for runtime in self.registry.all():
            queued = await session.scalar(
                select(func.count(CollectionRun.id))
                .join(CollectionTask, CollectionRun.task_id == CollectionTask.id)
                .where(
                    CollectionRun.status == "queued",
                    CollectionTask.platform == runtime.platform,
                )
            )
            manager_status = runtime.manager.get_status()
            items.append({
                "platform": runtime.platform,
                "label": runtime.definition.label,
                "source_modes": sorted(runtime.definition.source_modes),
                "login_supported": runtime.definition.login_supported,
                "content_filters_supported": runtime.definition.content_filters_supported,
                "process_status": manager_status["status"],
                "current_run_id": runtime.manager.current_run_id,
                "queued_count": int(queued or 0),
                "login_state": _login_states[runtime.platform]["state"],
                "error_message": manager_status.get("error_message"),
            })
    return items
```

增加：

```python
@router.get("/platforms")
async def list_platform_capabilities():
    return {"items": supervisor.platform_capabilities()}


@router.get("/platforms/status")
async def list_platform_statuses():
    return {"items": await supervisor.platform_statuses()}
```

日志接口按 `platform` 和 `run_id` 过滤；没有过滤参数时合并所有平台日志。

- [x] **Step 4: 验证测试通过**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py tests\test_api_limits.py -q`

Expected: PASS.

## Task 8: 前端平台状态与日志隔离

**Files:**
- Modify: `webui/src/lib/collectorApi.ts`
- Modify: `webui/src/components/collector/RunDetailDialog.tsx`
- Modify: `webui/src/components/collector/CollectorWorkspace.tsx`
- Modify: `webui/src/components/collector/TaskFormDialog.tsx`

- [x] **Step 1: 写类型和行为**

```typescript
export interface PlatformStatus {
  platform: PlatformId
  label: string
  source_modes: Array<'search' | 'detail'>
  login_supported: boolean
  content_filters_supported: boolean
  process_status: 'idle' | 'running' | 'stopping' | 'error'
  current_run_id: string | null
  queued_count: number
  login_state: 'idle' | 'running' | 'succeeded' | 'failed'
  error_message: string | null
}

export interface CollectionRun {
  // 保留现有字段
  config_snapshot: { platform: PlatformId }
}

export interface CrawlerLog {
  id: number
  timestamp: string
  level: string
  message: string
  platform: PlatformId | null
  run_id: string | null
}
```

- [x] **Step 2: 接入 API**

```typescript
async platformStatuses() {
  const response = await api.get<{ items: PlatformStatus[] }>('/platforms/status')
  return response.data.items
},
async platformCapabilities() {
  const response = await api.get<{ items: PlatformStatus[] }>('/platforms')
  return response.data.items
},
async logs(limit = 50, platform?: PlatformId, runId?: string) {
  const response = await api.get<{ logs: CrawlerLog[] }>('/crawler/logs', {
    params: { limit, platform, run_id: runId },
  })
  return response.data.logs
},
```

- [x] **Step 3: 展示平台状态**

在 `CollectorWorkspace` 增加两个平台状态卡片，显示中文平台名、`运行中/空闲/异常`、排队数和登录状态。运行详情调用 `collectorApi.logs(50, run.config_snapshot.platform, run.id)`。

任务表单使用 `platformCapabilities()` 生成平台下拉选项，不新增英文文案。

- [x] **Step 4: 构建验证**

Run: `Push-Location webui; npm run lint; npm run build; Pop-Location`

Expected: 0 errors，生产构建成功。

## Task 9: 集成回归与文档

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/project-overview.md`
- Modify: `docs/architecture/decisions.md`
- Modify: `docs/architecture/backlog.md`

- [x] **Step 1: 运行平台专项测试**

Run: `.tools\uv.exe run --env-file .env pytest tests\test_platform_runtime.py tests\test_run_progress.py tests\test_account_service.py tests\test_account_api.py tests\test_api_limits.py -q`

Expected: PASS.

- [x] **Step 2: 运行完整 Python 测试**

Run: `.tools\uv.exe run --env-file .env pytest tests -q`

Expected: 全部通过，无新增 skipped 或 failed。

- [x] **Step 3: 更新文档**

记录以下确定事实：

- 抖音和小红书各一个运行时，最多两个采集进程。
- 同一平台严格串行。
- 登录、取消、日志和账号解绑按平台隔离。
- 新增平台通过 `PlatformDefinition` 和注册表接入。
- 工厂不替代平台采集器开发。

- [x] **Step 4: 最终验证**

Run: `Push-Location webui; npm run lint; npm run build; Pop-Location`

Expected: 前端通过。

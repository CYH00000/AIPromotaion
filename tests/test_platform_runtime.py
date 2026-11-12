import asyncio
from datetime import datetime, timezone

import pytest

from api.platforms import PLATFORM_DEFINITIONS, get_platform_definition
from api.services.crawler_manager import CrawlerManager
from api.services.platform_runtime import PlatformRuntimeRegistry, create_platform_runtime


def test_platform_definitions_expose_both_supported_platforms():
    assert set(PLATFORM_DEFINITIONS) == {"dy", "xhs"}
    assert get_platform_definition("dy").label == "抖音"
    assert get_platform_definition("xhs").label == "小红书"


def test_unknown_platform_is_rejected_in_chinese():
    with pytest.raises(ValueError, match="不支持的平台"):
        get_platform_definition("unknown")


def test_platform_definitions_own_source_normalization_rules():
    assert get_platform_definition("xhs").source_parser(
        "detail",
        "https://www.xiaohongshu.com/explore/note-1?xsec_token=secret",
    ) == "https://www.xiaohongshu.com/explore/note-1"
    assert get_platform_definition("dy").source_parser(
        "detail",
        "https://www.douyin.com/video/123?modal_id=456",
    ) == "456"


def test_crawler_managers_have_independent_process_and_log_state():
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


@pytest.mark.asyncio
async def test_stopping_a_manager_clears_its_running_identity():
    class RunningProcess:
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def send_signal(self, _signal):
            self.stopped = True

    manager = CrawlerManager("dy")
    manager.process = RunningProcess()
    manager.current_run_id = "run-dy"
    manager.status = "running"

    assert await manager.stop() is True
    assert manager.get_status()["current_run_id"] is None


@pytest.mark.asyncio
async def test_starting_another_run_keeps_finished_run_logs(monkeypatch):
    import importlib
    from api.schemas.crawler import CrawlerStartRequest

    manager_module = importlib.import_module("api.services.crawler_manager")

    manager = CrawlerManager("dy")
    previous = manager._create_log_entry("上一轮运行日志")
    previous.run_id = "run-previous"

    class FinishedProcess:
        def poll(self):
            return 0

    class RunningProcess:
        def poll(self):
            return None

    async def keep_reading():
        await asyncio.Event().wait()

    monkeypatch.setattr(manager_module.subprocess, "Popen", lambda *args, **kwargs: RunningProcess())
    monkeypatch.setattr(manager, "_read_output", keep_reading)
    manager.process = FinishedProcess()

    await manager.start(CrawlerStartRequest(platform="dy"), run_id="run-current")

    assert any(log.run_id == "run-previous" for log in manager.logs)
    assert any(log.run_id == "run-current" for log in manager.logs)
    assert any(
        log.run_id == "run-current" and log.message.startswith("正在启动采集进程")
        for log in manager.logs
    )
    manager._read_task.cancel()
    await asyncio.gather(manager._read_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_start_failure_exposes_a_safe_chinese_status_message(monkeypatch):
    import importlib
    from api.schemas.crawler import CrawlerStartRequest

    manager_module = importlib.import_module("api.services.crawler_manager")
    manager = CrawlerManager("dy")

    def fail_to_start(*_args, **_kwargs):
        raise RuntimeError("sensitive local path")

    monkeypatch.setattr(manager_module.subprocess, "Popen", fail_to_start)

    assert await manager.start(CrawlerStartRequest(platform="dy")) is False
    status = manager.get_status()
    assert status["status"] == "error"
    assert status["error_message"] == "启动采集进程失败，请查看服务日志。"
    assert "sensitive local path" not in status["error_message"]


@pytest.mark.asyncio
async def test_output_read_failure_does_not_leave_the_platform_stuck_running():
    manager = CrawlerManager("dy")

    class BrokenOutput:
        def read(self):
            raise RuntimeError("output unavailable")

    class FinishedProcess:
        stdout = BrokenOutput()

        def poll(self):
            return 1

    manager.process = FinishedProcess()
    manager.status = "running"
    manager.current_run_id = "run-dy"

    await manager._read_output()

    assert manager.get_status()["status"] == "error"
    assert manager.get_status()["current_run_id"] is None
    assert manager.get_status()["error_message"] == "读取采集进程输出失败，请查看服务日志。"
    assert any(log.run_id == "run-dy" for log in manager.logs)


def test_factory_creates_isolated_runtime_for_each_platform():
    dy = create_platform_runtime(get_platform_definition("dy"))
    xhs = create_platform_runtime(get_platform_definition("xhs"))

    assert dy.platform == "dy"
    assert xhs.platform == "xhs"
    assert dy.worker is not xhs.worker
    assert dy.manager is not xhs.manager
    assert dy.manager.platform == "dy"
    assert xhs.manager.platform == "xhs"


def test_registry_returns_cached_runtime_and_rejects_duplicate_definition():
    registry = PlatformRuntimeRegistry([get_platform_definition("dy")])
    assert registry.get("dy") is registry.get("dy")

    with pytest.raises(ValueError, match="重复"):
        registry.register(get_platform_definition("dy"))


def test_aggregate_platform_status_preserves_stopping_and_error_states():
    from api.services.platform_runtime import aggregate_platform_status

    assert aggregate_platform_status([
        {"status": "idle"},
        {"status": "stopping"},
    ]) == "stopping"
    assert aggregate_platform_status([
        {"status": "error"},
        {"status": "idle"},
    ]) == "error"


@pytest.mark.asyncio
async def test_platform_worker_claim_query_is_scoped_to_its_platform(monkeypatch):
    from api.services.collection_worker import PlatformCollectionWorker
    import api.services.collection_worker as worker_module

    worker = PlatformCollectionWorker(
        get_platform_definition("dy"), CrawlerManager("dy")
    )
    statements = []

    class FakeResult:
        def scalar_one_or_none(self):
            return None

    class FakeSession:
        async def execute(self, statement):
            statements.append(statement)
            return FakeResult()

    class SessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(worker_module, "collector_session", SessionContext)
    monkeypatch.setattr(worker_module, "login_active", lambda platform: False)

    assert await worker._claim_next_run() is None
    assert "collector_tasks.platform" in str(statements[0])


@pytest.mark.asyncio
async def test_supervisor_starts_one_runner_per_registered_platform(monkeypatch):
    from api.services.platform_runtime import (
        CollectionWorkerSupervisor,
        PlatformRuntimeRegistry,
    )

    registry = PlatformRuntimeRegistry(PLATFORM_DEFINITIONS.values())
    supervisor = CollectionWorkerSupervisor(registry)
    started = []

    async def fake_start_worker(worker):
        started.append(worker.platform)

    async def fake_start_scheduler():
        return None

    monkeypatch.setattr(supervisor, "_recover_interrupted_runs", lambda: _async_none())
    monkeypatch.setattr(supervisor, "_start_scheduler", fake_start_scheduler)
    for runtime in registry.all():
        monkeypatch.setattr(
            runtime.worker,
            "start",
            lambda runtime=runtime: fake_start_worker(runtime.worker),
        )

    await supervisor.start()
    await supervisor.stop()

    assert sorted(started) == ["dy", "xhs"]


@pytest.mark.asyncio
async def test_supervisor_cancels_only_the_run_owned_by_its_platform(monkeypatch):
    from api.services.platform_runtime import (
        CollectionWorkerSupervisor,
        PlatformRuntimeRegistry,
    )

    registry = PlatformRuntimeRegistry(PLATFORM_DEFINITIONS.values())
    supervisor = CollectionWorkerSupervisor(registry)
    dy_worker = registry.get("dy").worker
    xhs_worker = registry.get("xhs").worker
    dy_worker.current_run_id = "run-dy"
    xhs_worker.current_run_id = "run-xhs"
    calls = []

    async def fake_cancel(worker, run_id):
        calls.append((worker.platform, run_id))

    for runtime in registry.all():
        monkeypatch.setattr(
            runtime.worker,
            "request_cancel",
            lambda run_id, runtime=runtime: fake_cancel(runtime.worker, run_id),
        )

    await supervisor.request_cancel("run-dy")

    assert calls == [("dy", "run-dy")]


def test_crawler_start_uses_the_requested_platform_manager(monkeypatch):
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    from api.main import app
    from api.services.auth_service import require_admin
    from api.services.platform_runtime import platform_runtime_registry

    app.dependency_overrides[require_admin] = lambda: "admin"
    dy_manager = platform_runtime_registry.get("dy").manager
    xhs_manager = platform_runtime_registry.get("xhs").manager
    try:
        monkeypatch.setattr(dy_manager, "start", AsyncMock(return_value=True))
        monkeypatch.setattr(xhs_manager, "start", AsyncMock(return_value=True))
        response = TestClient(app).post(
            "/api/crawler/start", json={"platform": "dy", "crawler_type": "search"}
        )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    dy_manager.start.assert_awaited_once()
    xhs_manager.start.assert_not_awaited()


async def _async_none():
    return None


def test_platform_status_endpoint_returns_both_platforms(monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.services.auth_service import require_admin
    from api.services.platform_runtime import collection_worker_supervisor

    app.dependency_overrides[require_admin] = lambda: "admin"

    async def fake_statuses():
        return [
            {"platform": "dy", "label": "抖音", "queued_count": 1},
            {"platform": "xhs", "label": "小红书", "queued_count": 2},
        ]

    try:
        monkeypatch.setattr(
            collection_worker_supervisor, "platform_statuses", fake_statuses
        )
        response = TestClient(app).get("/api/platforms/status")
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert [item["platform"] for item in response.json()["items"]] == ["dy", "xhs"]


def test_crawler_log_endpoint_filters_platform_and_run(monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.services.auth_service import require_admin
    from api.services.platform_runtime import platform_runtime_registry

    app.dependency_overrides[require_admin] = lambda: "admin"
    dy_manager = platform_runtime_registry.get("dy").manager
    xhs_manager = platform_runtime_registry.get("xhs").manager
    dy_manager._logs = []
    xhs_manager._logs = []
    dy_manager.current_run_id = "run-dy"
    xhs_manager.current_run_id = "run-xhs"
    dy_manager._create_log_entry("抖音运行日志")
    xhs_manager._create_log_entry("小红书运行日志")

    try:
        response = TestClient(app).get(
            "/api/crawler/logs?platform=xhs&run_id=run-xhs"
        )
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert [log["message"] for log in response.json()["logs"]] == ["小红书运行日志"]


def test_crawler_log_endpoint_merges_platform_logs_in_time_order(monkeypatch):
    from fastapi.testclient import TestClient
    from api.main import app
    from api.services.auth_service import require_admin
    from api.services.platform_runtime import platform_runtime_registry

    app.dependency_overrides[require_admin] = lambda: "admin"
    dy_manager = platform_runtime_registry.get("dy").manager
    xhs_manager = platform_runtime_registry.get("xhs").manager
    dy_manager._logs = []
    xhs_manager._logs = []
    later = dy_manager._create_log_entry("抖音较晚日志")
    earlier = xhs_manager._create_log_entry("小红书较早日志")
    later.timestamp = "12:00:02"
    earlier.timestamp = "12:00:01"

    try:
        response = TestClient(app).get("/api/crawler/logs")
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert [log["message"] for log in response.json()["logs"]] == [
        "小红书较早日志",
        "抖音较晚日志",
    ]


@pytest.mark.asyncio
async def test_platform_status_uses_the_current_run_activity(monkeypatch):
    import api.services.platform_runtime as runtime_module
    from api.services.platform_runtime import (
        CollectionWorkerSupervisor,
        PlatformRuntimeRegistry,
    )

    registry = PlatformRuntimeRegistry([get_platform_definition("dy")])
    supervisor = CollectionWorkerSupervisor(registry)
    manager = registry.get("dy").manager
    manager.current_run_id = "run-dy"
    manager.status = "running"
    manager.started_at = datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc)
    last_activity = datetime(2026, 11, 12, 8, 5, tzinfo=timezone.utc)

    class CurrentRunResult:
        def one_or_none(self):
            return type("RunRow", (), {"task_id": "task-dy", "last_activity_at": last_activity})()

    class FakeSession:
        async def scalar(self, _statement):
            return 0

        async def execute(self, _statement):
            return CurrentRunResult()

    class SessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(runtime_module, "collector_session", SessionContext)

    status = (await supervisor.platform_statuses())[0]

    assert status["current_task_id"] == "task-dy"
    assert status["last_activity_at"] == last_activity.isoformat()

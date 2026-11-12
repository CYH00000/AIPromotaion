import asyncio
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import func, select

from api.platforms import PLATFORM_DEFINITIONS, PlatformDefinition
from api.services.collection_worker import (
    PROJECT_ROOT,
    RECOVERED_RUNS_DIR,
    PlatformCollectionWorker,
)
from api.services.crawler_manager import CrawlerManager
from api.services.task_service import create_run, next_scheduled_time
from database.collector_database import collector_session
from database.collector_models import CollectionRun, CollectionTask, utc_now


def aggregate_platform_status(statuses: Iterable[dict]) -> str:
    active = {item.get("status") for item in statuses}
    for status in ("running", "stopping", "error"):
        if status in active:
            return status
    return "idle"


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
    def __init__(self, definitions: Iterable[PlatformDefinition] = PLATFORM_DEFINITIONS.values()):
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


class CollectionWorkerSupervisor:
    def __init__(self, registry: PlatformRuntimeRegistry):
        self.registry = registry
        self._scheduler: asyncio.Task | None = None
        self._stopping = False
        self._recovery_done = False

    async def start(self) -> None:
        if not self._recovery_done:
            await self._recover_interrupted_runs()
            self._cleanup_stale_staging()
            self._recovery_done = True
        self._stopping = False
        await self._start_scheduler()
        for runtime in self.registry.all():
            await runtime.worker.start()

    async def _start_scheduler(self) -> None:
        self._scheduler = asyncio.create_task(
            self._schedule_loop(), name="collector-scheduler"
        )

    async def stop(self) -> None:
        self._stopping = True
        if self._scheduler and not self._scheduler.done():
            self._scheduler.cancel()
        await asyncio.gather(
            *(runtime.worker.stop() for runtime in self.registry.all()),
            return_exceptions=True,
        )
        if self._scheduler:
            await asyncio.gather(self._scheduler, return_exceptions=True)

    async def request_cancel(self, run_id: str) -> None:
        for runtime in self.registry.all():
            if runtime.worker.current_run_id == run_id:
                await runtime.worker.request_cancel(run_id)
                return

    def platform_capabilities(self) -> list[dict]:
        return [
            {
                "platform": runtime.platform,
                "label": runtime.definition.label,
                "source_modes": sorted(runtime.definition.source_modes),
                "login_supported": runtime.definition.login_supported,
                "content_filters_supported": runtime.definition.content_filters_supported,
            }
            for runtime in self.registry.all()
        ]

    async def platform_statuses(self) -> list[dict]:
        from api.services.account_service import _login_states

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
                current_task_id = None
                last_activity_at = manager_status.get("started_at")
                current_run_id = manager_status.get("current_run_id")
                if current_run_id:
                    current_run = (
                        await session.execute(
                            select(
                                CollectionRun.task_id,
                                CollectionRun.last_activity_at,
                            ).where(CollectionRun.id == current_run_id)
                        )
                    ).one_or_none()
                    if current_run:
                        current_task_id = current_run.task_id
                        if current_run.last_activity_at:
                            last_activity_at = current_run.last_activity_at.isoformat()
                items.append(
                    {
                        "platform": runtime.platform,
                        "label": runtime.definition.label,
                        "source_modes": sorted(runtime.definition.source_modes),
                        "login_supported": runtime.definition.login_supported,
                        "content_filters_supported": runtime.definition.content_filters_supported,
                        "process_status": manager_status["status"],
                        "current_run_id": current_run_id,
                        "current_task_id": current_task_id,
                        "current_run_started_at": manager_status.get("started_at"),
                        "queued_count": int(queued or 0),
                        "login_state": _login_states[runtime.platform]["state"],
                        "last_activity_at": last_activity_at,
                        "error_message": manager_status.get("error_message"),
                    }
                )
        return items

    async def _schedule_loop(self) -> None:
        while not self._stopping:
            try:
                now = utc_now()
                async with collector_session() as session:
                    result = await session.execute(
                        select(CollectionTask)
                        .where(
                            CollectionTask.state == "enabled",
                            CollectionTask.schedule_type != "manual",
                            CollectionTask.next_run_at <= now,
                        )
                        .order_by(CollectionTask.next_run_at)
                        .limit(20)
                        .with_for_update(skip_locked=True)
                    )
                    for task in result.scalars().all():
                        session.add(create_run(task, "schedule"))
                        task.next_run_at = next_scheduled_time(
                            task.schedule_type, task.schedule_value, now
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"Collector scheduler error: {type(exc).__name__}")
            await asyncio.sleep(5)

    async def _recover_interrupted_runs(self) -> None:
        async with collector_session() as session:
            active = await session.execute(
                select(CollectionRun).where(CollectionRun.status == "running")
            )
            interrupted = list(active.scalars().all())
        for run in interrupted:
            staging = PROJECT_ROOT / "data" / "project_runs" / run.id
            PlatformCollectionWorker._recover_staging(staging, run.id)
            async with collector_session() as session:
                stored = await session.get(CollectionRun, run.id)
                if stored and stored.status == "running":
                    stored.status = "interrupted"
                    stored.phase = "failed"
                    stored.counts = {}
                    stored.progress = {**(stored.progress or {}), "stalled": False}
                    stored.finished_at = utc_now()
                    stored.safe_summary = (
                        "服务在采集期间重启；暂存数据已保留到恢复目录，可重新运行任务。"
                    )

    def _cleanup_stale_staging(self) -> None:
        root = PROJECT_ROOT / "data" / "project_runs"
        if not root.exists():
            return
        for staging in root.iterdir():
            if staging.is_dir():
                PlatformCollectionWorker._safe_remove_staging(staging)


platform_runtime_registry = PlatformRuntimeRegistry()
collection_worker_supervisor = CollectionWorkerSupervisor(platform_runtime_registry)

# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

import asyncio
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from api.schemas.crawler import CrawlerStartRequest, CrawlerTypeEnum, LoginTypeEnum, PlatformEnum, SaveDataOptionEnum
from api.services.account_service import login_active
from api.services.collection_pipeline import ingest_staging_directory
from api.services.crawler_manager import crawler_manager
from api.services.run_progress import JsonlLineCounter, is_stalled
from api.services.task_service import create_run, next_scheduled_time
from database.collector_database import collector_session
from database.collector_models import CollectionRun, CollectionTask, utc_now


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STALL_TIMEOUT_SECONDS = int(os.getenv("COLLECTOR_STALL_TIMEOUT_SECONDS", "180"))


class CollectionWorker:
    """Single-process durable queue and scheduler for project collection runs."""

    def __init__(self):
        self.current_run_id: str | None = None
        self._runner: asyncio.Task | None = None
        self._scheduler: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        async with collector_session() as session:
            active = await session.execute(select(CollectionRun).where(CollectionRun.status == "running"))
            interrupted = [
                {"id": run.id, "config": run.config_snapshot}
                for run in active.scalars().all()
            ]
        for run in interrupted:
            staging = PROJECT_ROOT / "data" / "project_runs" / run["id"]
            counts = {}
            if staging.exists():
                try:
                    counts = await ingest_staging_directory(
                        run["id"], run["config"]["platform"], run["config"], staging
                    )
                except Exception as exc:
                    print(f"Interrupted run recovery error: {type(exc).__name__}")
            async with collector_session() as session:
                stored = await session.get(CollectionRun, run["id"])
                if stored and stored.status == "running":
                    stored.status = "interrupted"
                    stored.phase = "failed"
                    stored.counts = counts
                    stored.progress = {**(stored.progress or {}), "stalled": False}
                    stored.finished_at = utc_now()
                    stored.safe_summary = "服务在采集期间重启，已保留部分结果。"
        self._cleanup_stale_staging()
        self._stopping = False
        self._runner = asyncio.create_task(self._run_loop(), name="collector-run-worker")
        self._scheduler = asyncio.create_task(self._schedule_loop(), name="collector-scheduler")

    async def stop(self) -> None:
        self._stopping = True
        if crawler_manager.process and crawler_manager.process.poll() is None:
            await crawler_manager.stop()
        for task in (self._scheduler, self._runner):
            if task and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (self._scheduler, self._runner) if task),
            return_exceptions=True,
        )

    async def request_cancel(self, run_id: str) -> None:
        if self.current_run_id == run_id:
            await crawler_manager.stop()

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

    async def _claim_next_run(self) -> dict[str, Any] | None:
        if login_active():
            return None
        async with collector_session() as session:
            result = await session.execute(
                select(CollectionRun)
                .where(CollectionRun.status == "queued")
                .order_by(CollectionRun.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            run = result.scalar_one_or_none()
            if run is None:
                return None
            task = await session.get(CollectionTask, run.task_id)
            if task is None or task.state == "disabled":
                run.status = "cancelled"
                run.finished_at = utc_now()
                run.safe_summary = "任务已不可用。"
                return None
            run.status = "running"
            run.started_at = utc_now()
            run.phase = "starting"
            run.progress = {
                "staged_contents": 0,
                "staged_comments": 0,
                "stalled": False,
                "last_log_id": 0,
            }
            run.last_activity_at = utc_now()
            return {"run_id": run.id, "task_id": task.id, "config": run.config_snapshot}

    async def _run_loop(self) -> None:
        while not self._stopping:
            run = None
            try:
                run = await self._claim_next_run()
                if run is None:
                    await asyncio.sleep(1)
                    continue
                self.current_run_id = run["run_id"]
                try:
                    await self._execute_run(run)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    print(f"Collector run error: {type(exc).__name__}")
                    await self._finish_run(
                        run["run_id"], "failed", {}, "worker_error", "The collection worker failed; see local service logs."
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"Collector worker error: {type(exc).__name__}")
                await asyncio.sleep(1)
            finally:
                self.current_run_id = None

    async def _execute_run(self, run: dict[str, Any]) -> None:
        config = run["config"]
        staging = PROJECT_ROOT / "data" / "project_runs" / run["run_id"]
        staging.mkdir(parents=True, exist_ok=True)
        progress_state = {"phase": "starting"}
        progress_task = asyncio.create_task(
            self._progress_loop(run["run_id"], staging, progress_state),
            name=f"run-progress-{run['run_id']}",
        )
        try:
            crawl_config = CrawlerStartRequest(
                platform=PlatformEnum(config["platform"]),
                login_type=LoginTypeEnum.QRCODE,
                crawler_type=CrawlerTypeEnum.SEARCH if config["source_mode"] == "search" else CrawlerTypeEnum.DETAIL,
                keywords=",".join(config["source_values"]) if config["source_mode"] == "search" else "",
                specified_ids=(
                    ",".join(config["source_values"][: config["max_contents"]])
                    if config["source_mode"] == "detail" else ""
                ),
                enable_comments=True,
                enable_sub_comments=False,
                enable_media=False,
                save_option=SaveDataOptionEnum.JSONL,
                headless=False,
                max_notes_count=config["max_contents"],
                max_comments_count=config["max_comments_per_content"],
            )

            started = await crawler_manager.start(
                crawl_config,
                save_data_path=str(staging),
                extra_env={
                    "COLLECTOR_PROJECT_MODE": "1",
                    "COLLECTOR_RUN_ID": run["run_id"],
                },
            )
            if not started or crawler_manager.process is None:
                await self._finish_run(run["run_id"], "failed", {}, "crawler_busy", "Another collector process is running.")
                return

            progress_state["phase"] = "crawling"
            process = crawler_manager.process
            exit_code = await asyncio.to_thread(process.wait)
            if crawler_manager._read_task:
                await crawler_manager._read_task
            progress_state["phase"] = "filtering"
            counts = await ingest_staging_directory(run["run_id"], config["platform"], config, staging)
            progress_state["phase"] = "finalizing"
            async with collector_session() as session:
                stored_run = await session.get(CollectionRun, run["run_id"])
                cancelled = stored_run.cancel_requested if stored_run else False
            if cancelled:
                status = "cancelled"
                error_code = None
                summary = "采集已取消，已采集的记录已保留。"
            elif exit_code == 0:
                if counts.get("semantic_failed", 0):
                    status = "partial"
                    error_code = "semantic_evaluation_failed"
                    summary = "部分评论未能完成智能语义判断，未保存。"
                else:
                    status, error_code, summary = "succeeded", None, "采集完成。"
            elif counts["matched"]:
                status, error_code, summary = "partial", f"crawler_exit_{exit_code}", "采集中断，已保存部分结果。"
            else:
                status, error_code, summary = "failed", f"crawler_exit_{exit_code}", "上游采集器异常退出。"
            progress_task.cancel()
            await asyncio.gather(progress_task, return_exceptions=True)
            await self._finish_run(run["run_id"], status, counts, error_code, summary)
        finally:
            progress_task.cancel()
            await asyncio.gather(progress_task, return_exceptions=True)
            self._safe_remove_staging(staging)

    async def _progress_loop(self, run_id: str, staging: Path, state: dict[str, str]) -> None:
        counter = JsonlLineCounter()
        last_counts = (0, 0)
        last_log_id = crawler_manager._log_id
        last_activity = utc_now()
        while True:
            await asyncio.sleep(3)
            try:
                contents, comments = counter.scan(staging)
                log_id = crawler_manager._log_id
                phase = state["phase"]
                now = utc_now()
                changed = (contents, comments) != last_counts or log_id != last_log_id
                if phase == "crawling":
                    if changed:
                        last_activity = now
                    stalled = is_stalled(last_activity, now, STALL_TIMEOUT_SECONDS)
                else:
                    last_activity = now
                    stalled = False
                async with collector_session() as session:
                    run = await session.get(CollectionRun, run_id)
                    if run is None or run.status != "running":
                        return
                    run.phase = phase
                    run.progress = {
                        "staged_contents": contents,
                        "staged_comments": comments,
                        "stalled": stalled,
                        "last_log_id": log_id,
                    }
                    run.last_activity_at = last_activity
                last_counts = (contents, comments)
                last_log_id = log_id
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"Run progress update error: {type(exc).__name__}")

    @staticmethod
    def _safe_remove_staging(staging: Path) -> None:
        root = (PROJECT_ROOT / "data" / "project_runs").resolve()
        target = staging.resolve()
        if target.parent != root or target == root:
            raise ValueError("Refusing to remove an unexpected staging path")
        if target.exists():
            shutil.rmtree(target)

    def _cleanup_stale_staging(self) -> None:
        root = PROJECT_ROOT / "data" / "project_runs"
        if not root.exists():
            return
        for staging in root.iterdir():
            if staging.is_dir():
                self._safe_remove_staging(staging)

    async def _finish_run(self, run_id: str, status: str, counts: dict, error_code: str | None, summary: str) -> None:
        async with collector_session() as session:
            run = await session.get(CollectionRun, run_id)
            if run is None:
                return
            run.status = status
            run.phase = {
                "succeeded": "completed",
                "partial": "completed",
                "cancelled": "cancelled",
                "failed": "failed",
                "interrupted": "failed",
            }.get(status, "completed")
            run.counts = counts
            run.error_code = error_code
            run.safe_summary = summary
            run.finished_at = datetime.now(timezone.utc)


collection_worker = CollectionWorker()

# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/api/routers/crawler.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio

from fastapi import APIRouter, HTTPException, Query

from ..schemas import CrawlerStartRequest, CrawlerStatusResponse
from ..services.platform_runtime import (
    aggregate_platform_status,
    platform_runtime_registry,
)

router = APIRouter(prefix="/crawler", tags=["crawler"])


def _runtime_for(platform: str):
    try:
        return platform_runtime_registry.get(platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/start")
async def start_crawler(request: CrawlerStartRequest):
    """Start crawler task"""
    runtime = _runtime_for(request.platform.value)
    success = await runtime.manager.start(request)
    if not success:
        # Handle concurrent/duplicate requests: if process is already running, return 400 instead of 500
        if runtime.manager.process and runtime.manager.process.poll() is None:
            raise HTTPException(status_code=400, detail=f"{runtime.definition.label}采集进程已在运行")
        raise HTTPException(status_code=500, detail="启动采集进程失败")

    return {"status": "ok", "message": "采集进程已启动"}


@router.post("/stop")
async def stop_crawler(platform: str | None = Query(default=None, pattern="^(dy|xhs)$")):
    """Stop crawler task"""
    runtimes = [_runtime_for(platform)] if platform else list(platform_runtime_registry.all())
    results = await asyncio.gather(
        *(runtime.manager.stop() for runtime in runtimes), return_exceptions=True
    )
    success = any(result is True for result in results)
    if not success:
        if any(isinstance(result, Exception) for result in results):
            raise HTTPException(status_code=500, detail="停止采集进程失败")
        raise HTTPException(status_code=400, detail="当前没有采集进程在运行")

    return {"status": "ok", "message": "采集进程已停止"}


@router.get("/status", response_model=CrawlerStatusResponse)
async def get_crawler_status(platform: str | None = Query(default=None, pattern="^(dy|xhs)$")):
    """Get crawler status"""
    if platform:
        return _runtime_for(platform).manager.get_status()
    statuses = [runtime.manager.get_status() for runtime in platform_runtime_registry.all()]
    return {
        "status": aggregate_platform_status(statuses),
        "platform": None,
        "current_run_id": None,
        "crawler_type": None,
        "started_at": None,
        "error_message": None,
        "platforms": statuses,
    }


@router.get("/logs")
async def get_logs(
    limit: int = Query(default=100, ge=1, le=500),
    platform: str | None = Query(default=None, pattern="^(dy|xhs)$"),
    run_id: str | None = Query(default=None, max_length=36),
):
    """Get recent logs"""
    runtimes = [_runtime_for(platform)] if platform else list(platform_runtime_registry.all())
    logs = [
        entry
        for runtime in runtimes
        for entry in runtime.manager.logs
        if run_id is None or entry.run_id == run_id
    ]
    logs.sort(key=lambda entry: entry.timestamp)
    logs = logs[-limit:]
    return {"logs": [log.model_dump() for log in logs]}

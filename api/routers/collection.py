# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.collection import TaskCreate, TaskPatch, TaskView
from api.services.auth_service import require_admin, require_csrf
from api.services.collection_worker import collection_worker
from api.services.task_service import create_run, next_scheduled_time, run_to_dict, task_to_dict
from database.collector_database import collector_session
from database.collector_models import (
    CollectionRun,
    CollectionFilterRule,
    CollectionTask,
    CollectedComment,
    CommentSnapshot,
    utc_now,
)
from api.services.collection_pipeline import spreadsheet_safe


router = APIRouter(dependencies=[Depends(require_admin)], tags=["collection"])


@router.get("/tasks")
async def list_tasks():
    async with collector_session() as session:
        result = await session.execute(select(CollectionTask).order_by(CollectionTask.updated_at.desc()))
        return {"items": [task_to_dict(task) for task in result.scalars().all()]}


async def _approved_filter_rule(session: AsyncSession, rule_id: str | None):
    if rule_id is None:
        return None
    rule = await session.get(CollectionFilterRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=422, detail="Filter rule not found.")
    if rule.status != "approved":
        raise HTTPException(status_code=422, detail="Approve the AI filter rule before using it.")
    return rule


@router.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskView)
async def create_task(payload: TaskCreate, _csrf: None = Depends(require_csrf)):
    now = utc_now()
    async with collector_session() as session:
        approved_rule = await _approved_filter_rule(session, payload.filter_rule_id)
        task = CollectionTask(
            **payload.model_dump(),
            filter_rule=approved_rule,
            state="enabled",
            next_run_at=next_scheduled_time(payload.schedule_type, payload.schedule_value, now),
        )
        session.add(task)
        await session.flush()
        return task_to_dict(task)


@router.get("/tasks/{task_id}", response_model=TaskView)
async def get_task(task_id: str):
    async with collector_session() as session:
        task = await session.get(CollectionTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task_to_dict(task)


@router.patch("/tasks/{task_id}", response_model=TaskView)
async def update_task(task_id: str, payload: TaskPatch, _csrf: None = Depends(require_csrf)):
    async with collector_session() as session:
        task = await session.get(CollectionTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        candidate = task_to_dict(task)
        candidate.update(payload.model_dump(exclude_unset=True))
        validated = TaskCreate(**{key: candidate[key] for key in TaskCreate.model_fields})
        approved_rule = await _approved_filter_rule(session, validated.filter_rule_id)
        for key, value in validated.model_dump().items():
            setattr(task, key, value)
        task.filter_rule = approved_rule
        if task.state == "enabled":
            task.next_run_at = next_scheduled_time(task.schedule_type, task.schedule_value)
        return task_to_dict(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_task(task_id: str, _csrf: None = Depends(require_csrf)):
    async with collector_session() as session:
        task = await session.get(CollectionTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        task.state = "disabled"
        task.next_run_at = None


@router.post("/tasks/{task_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_task(task_id: str, _csrf: None = Depends(require_csrf)):
    async with collector_session() as session:
        task = await session.get(CollectionTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task.state != "enabled":
            raise HTTPException(status_code=409, detail="Task is paused or disabled")
        run = create_run(task, "manual")
        session.add(run)
        await session.flush()
        return {"run_id": run.id, "status": run.status}


@router.post("/tasks/{task_id}/pause", response_model=TaskView)
async def pause_task(task_id: str, _csrf: None = Depends(require_csrf)):
    async with collector_session() as session:
        task = await session.get(CollectionTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        task.state = "paused"
        task.next_run_at = None
        return task_to_dict(task)


@router.post("/tasks/{task_id}/resume", response_model=TaskView)
async def resume_task(task_id: str, _csrf: None = Depends(require_csrf)):
    async with collector_session() as session:
        task = await session.get(CollectionTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        task.state = "enabled"
        task.next_run_at = next_scheduled_time(task.schedule_type, task.schedule_value)
        return task_to_dict(task)


@router.get("/runs")
async def list_runs(task_id: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
    query = select(CollectionRun).order_by(CollectionRun.created_at.desc()).limit(limit)
    if task_id:
        query = query.where(CollectionRun.task_id == task_id)
    async with collector_session() as session:
        result = await session.execute(query)
        return {"items": [run_to_dict(run) for run in result.scalars().all()]}


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_run(run_id: str, _csrf: None = Depends(require_csrf)):
    async with collector_session() as session:
        run = await session.get(CollectionRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run.status == "queued":
            run.status = "cancelled"
            run.finished_at = utc_now()
        elif run.status == "running":
            run.cancel_requested = True
        else:
            raise HTTPException(status_code=409, detail="Run is already finished")
        response = {"run_id": run.id, "status": run.status, "cancel_requested": run.cancel_requested}
    await collection_worker.request_cancel(run_id)
    return response


async def _query_comments(
    session: AsyncSession,
    platform: str | None,
    task_id: str | None,
    search: str | None,
    limit: int,
    offset: int,
):
    query = select(CollectedComment)
    predicates = []
    if platform:
        predicates.append(CollectedComment.platform == platform)
    if search:
        predicates.append(CollectedComment.body.ilike(f"%{search}%"))
    if task_id:
        predicates.append(
            select(CommentSnapshot.id)
            .join(CollectionRun, CommentSnapshot.run_id == CollectionRun.id)
            .where(CommentSnapshot.comment_id == CollectedComment.id, CollectionRun.task_id == task_id)
            .exists()
        )
    if predicates:
        query = query.where(*predicates)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(
        query.order_by(CollectedComment.first_seen_at.desc()).offset(offset).limit(limit)
    )
    comments = result.scalars().all()
    comment_ids = [comment.id for comment in comments]
    snapshot_query = select(CommentSnapshot).where(
        CommentSnapshot.comment_id.in_(comment_ids)
    ) if comment_ids else None
    if snapshot_query is not None and task_id:
        snapshot_query = snapshot_query.join(
            CollectionRun, CommentSnapshot.run_id == CollectionRun.id
        ).where(CollectionRun.task_id == task_id)
    snapshots_result = await session.execute(
        snapshot_query.order_by(CommentSnapshot.observed_at.desc())
    ) if snapshot_query is not None else None
    latest = {}
    if snapshots_result is not None:
        for snapshot in snapshots_result.scalars().all():
            latest.setdefault(snapshot.comment_id, snapshot)
    items = []
    for comment in comments:
        row = {column.name: getattr(comment, column.name) for column in comment.__table__.columns}
        snapshot = latest.get(comment.id)
        row["latest_like_count"] = snapshot.like_count if snapshot else 0
        row["latest_reply_count"] = snapshot.reply_count if snapshot else 0
        row["last_observed_at"] = snapshot.observed_at if snapshot else comment.first_seen_at
        row["matched_keywords"] = snapshot.matched_keywords if snapshot else comment.matched_keywords
        row["filter_rule_id"] = snapshot.filter_rule_id if snapshot else None
        row["filter_rule_version"] = snapshot.filter_rule_version if snapshot else None
        row["filter_reason"] = snapshot.filter_reason if snapshot else None
        items.append(row)
    return items, total or 0


@router.get("/comments")
async def list_comments(
    platform: str | None = Query(default=None, pattern="^(dy|xhs)$"),
    task_id: str | None = None,
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    async with collector_session() as session:
        items, total = await _query_comments(session, platform, task_id, q, limit, offset)
        return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/comments/{comment_id}/snapshots")
async def comment_snapshots(comment_id: str):
    async with collector_session() as session:
        comment = await session.get(CollectedComment, comment_id)
        if comment is None:
            raise HTTPException(status_code=404, detail="Comment not found")
        result = await session.execute(
            select(CommentSnapshot)
            .where(CommentSnapshot.comment_id == comment_id)
            .order_by(CommentSnapshot.observed_at.desc())
        )
        return {"items": [
            {column.name: getattr(snapshot, column.name) for column in snapshot.__table__.columns}
            for snapshot in result.scalars().all()
        ]}


@router.get("/exports/comments")
async def export_comments(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    platform: str | None = Query(default=None, pattern="^(dy|xhs)$"),
    task_id: str | None = None,
    q: str | None = Query(default=None, max_length=200),
):
    async with collector_session() as session:
        rows, _ = await _query_comments(session, platform, task_id, q, 10000, 0)
    columns = [
        ("platform", "平台"), ("content_title", "内容标题"), ("content_url", "内容链接"),
        ("body", "评论内容"), ("comment_time", "评论时间"),
        ("latest_like_count", "点赞数"), ("latest_reply_count", "回复数"),
        ("author_user_id", "作者用户ID"), ("author_nickname", "作者昵称"),
        ("author_profile_url", "作者主页链接"), ("matched_keywords", "命中规则"),
        ("filter_rule_version", "语义规则版本"), ("filter_reason", "筛选原因"),
        ("last_observed_at", "采集时间"),
    ]
    if format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow([title for _, title in columns])
        for row in rows:
            writer.writerow([spreadsheet_safe(_export_value(row.get(key))) for key, _ in columns])
        return Response(
            content="\ufeff" + output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="comments.csv"'},
        )

    from openpyxl import Workbook

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("评论结果")
    sheet.append([title for _, title in columns])
    for row in rows:
        sheet.append([spreadsheet_safe(_export_value(row.get(key))) for key, _ in columns])
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="comments.xlsx"'},
    )


def _export_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value

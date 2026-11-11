# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from api.schemas.collection import TaskCreate
from database.collector_models import CollectionRun, CollectionTask, utc_now


def next_scheduled_time(schedule_type: str, schedule_value: str | None, now: datetime | None = None):
    """Compute the next UTC execution time for a task schedule."""
    now = now or utc_now()
    if schedule_type == "manual":
        return None
    if schedule_type == "interval":
        return now + timedelta(minutes=int(schedule_value or "60"))
    local_now = now.astimezone(ZoneInfo("Asia/Shanghai"))
    trigger = CronTrigger.from_crontab(schedule_value or "", timezone=ZoneInfo("Asia/Shanghai"))
    next_local = trigger.get_next_fire_time(None, local_now)
    return next_local.astimezone(timezone.utc) if next_local else None


def task_to_dict(task: CollectionTask) -> dict:
    row = {column.name: getattr(task, column.name) for column in task.__table__.columns}
    rule = task.filter_rule
    row["filter_rule"] = (
        {
            "id": rule.id,
            "lineage_id": rule.lineage_id,
            "version": rule.version,
            "parent_rule_id": rule.parent_rule_id,
            "intent": rule.intent,
            "definition": rule.definition,
            "model_name": rule.model_name,
            "status": rule.status,
            "created_at": rule.created_at,
            "approved_at": rule.approved_at,
        }
        if rule else None
    )
    return row


def run_to_dict(run: CollectionRun) -> dict:
    return {column.name: getattr(run, column.name) for column in run.__table__.columns}


def create_run(task: CollectionTask, trigger_type: str) -> CollectionRun:
    """Snapshot all task inputs so future edits cannot change an existing run."""
    snapshot = TaskCreate(
        name=task.name,
        platform=task.platform,
        source_mode=task.source_mode,
        source_values=task.source_values,
        include_keywords=task.include_keywords,
        exclude_keywords=task.exclude_keywords,
        filter_rule_id=task.filter_rule_id,
        max_contents=task.max_contents,
        max_comments_per_content=task.max_comments_per_content,
        content_sort=task.content_sort,
        publish_time_days=task.publish_time_days,
        schedule_type=task.schedule_type,
        schedule_value=task.schedule_value,
    )
    config = snapshot.model_dump(mode="json")
    rule = task.filter_rule
    if rule:
        config["filter_rule"] = {
            "id": rule.id,
            "version": rule.version,
            "intent": rule.intent,
            "definition": rule.definition,
            "model_name": rule.model_name,
        }
    return CollectionRun(
        task_id=task.id,
        trigger_type=trigger_type,
        status="queued",
        config_snapshot=config,
        counts={},
    )

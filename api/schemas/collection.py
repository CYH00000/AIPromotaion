# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, model_validator

from api.platforms import get_platform_definition


Platform = Literal["dy", "xhs"]
SourceMode = Literal["search", "detail"]
ScheduleType = Literal["manual", "interval", "cron"]
ContentSort = Literal["general", "latest", "most_liked"]
PublishTimeDays = Literal[0, 1, 7, 180]


class TaskCreate(BaseModel):
    """Create a bounded collection task using the approved upstream modes."""

    name: str = Field(min_length=1, max_length=120)
    platform: Platform
    source_mode: SourceMode
    source_values: list[str] = Field(min_length=1, max_length=20)
    include_keywords: list[str] = Field(default_factory=list, max_length=50)
    exclude_keywords: list[str] = Field(default_factory=list, max_length=50)
    filter_rule_id: str | None = Field(default=None, max_length=36)
    max_contents: int = Field(default=20, ge=1, le=100)
    max_comments_per_content: int = Field(default=100, ge=1, le=1000)
    content_sort: ContentSort = "general"
    publish_time_days: PublishTimeDays = 0
    schedule_type: ScheduleType = "manual"
    schedule_value: str | None = None

    @model_validator(mode="after")
    def validate_task(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Task name cannot be blank")
        parser = get_platform_definition(self.platform).source_parser
        self.source_values = [parser(self.source_mode, item) for item in self.source_values]
        self.include_keywords = [item.strip() for item in self.include_keywords if item.strip()]
        self.exclude_keywords = [item.strip() for item in self.exclude_keywords if item.strip()]
        if self.schedule_type == "manual":
            self.schedule_value = None
        elif self.schedule_type == "interval":
            try:
                interval = int(self.schedule_value or "")
            except ValueError as exc:
                raise ValueError("Interval must be an integer number of minutes") from exc
            if not 60 <= interval <= 525600:
                raise ValueError("Interval must be between 60 and 525600 minutes")
            self.schedule_value = str(interval)
        else:
            try:
                CronTrigger.from_crontab(self.schedule_value or "", timezone=ZoneInfo("Asia/Shanghai"))
            except (ValueError, TypeError) as exc:
                raise ValueError("Cron expression must be a valid five-field expression") from exc
        return self


class TaskPatch(BaseModel):
    """Partial task update; omitted values keep their current settings."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    source_values: list[str] | None = Field(default=None, min_length=1, max_length=20)
    include_keywords: list[str] | None = Field(default=None, max_length=50)
    exclude_keywords: list[str] | None = Field(default=None, max_length=50)
    filter_rule_id: str | None = Field(default=None, max_length=36)
    max_contents: int | None = Field(default=None, ge=1, le=100)
    max_comments_per_content: int | None = Field(default=None, ge=1, le=1000)
    content_sort: ContentSort | None = None
    publish_time_days: PublishTimeDays | None = None
    schedule_type: ScheduleType | None = None
    schedule_value: str | None = None


class TaskView(BaseModel):
    id: str
    name: str
    platform: str
    source_mode: str
    source_values: list[str]
    include_keywords: list[str]
    exclude_keywords: list[str]
    filter_rule_id: str | None
    filter_rule: dict | None = None
    max_contents: int
    max_comments_per_content: int
    content_sort: str
    publish_time_days: int
    schedule_type: str
    schedule_value: str | None
    state: str
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def new_id() -> str:
    """Create a stable string UUID for project-owned records."""
    return str(uuid4())


class CollectorBase(DeclarativeBase):
    """Separate metadata for application-owned tables."""


class CollectionFilterRule(CollectorBase):
    __tablename__ = "collector_filter_rules"
    __table_args__ = (
        UniqueConstraint("lineage_id", "version", name="uq_collector_filter_rule_lineage_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lineage_id: Mapped[str] = mapped_column(String(36), nullable=False, default=new_id)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("collector_filter_rules.id", ondelete="RESTRICT")
    )
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    parent: Mapped["CollectionFilterRule | None"] = relationship(remote_side="CollectionFilterRule.id")
    tasks: Mapped[list["CollectionTask"]] = relationship(back_populates="filter_rule")


class CollectionTask(CollectorBase):
    __tablename__ = "collector_tasks"
    __table_args__ = (Index("ix_collector_tasks_due", "state", "next_run_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    platform: Mapped[str] = mapped_column(String(8), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(12), nullable=False)
    source_values: Mapped[list] = mapped_column(JSON, nullable=False)
    include_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    exclude_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    filter_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("collector_filter_rules.id", ondelete="RESTRICT")
    )
    filter_rule: Mapped[CollectionFilterRule | None] = relationship(back_populates="tasks", lazy="joined")
    max_contents: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_comments_per_content: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    schedule_type: Mapped[str] = mapped_column(String(12), nullable=False, default="manual")
    schedule_value: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(12), nullable=False, default="enabled")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class CollectionRun(CollectorBase):
    __tablename__ = "collector_runs"
    __table_args__ = (Index("ix_collector_runs_task_created", "task_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("collector_tasks.id", ondelete="RESTRICT"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    phase: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    config_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    progress: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    safe_summary: Mapped[str | None] = mapped_column(String(500))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollectedComment(CollectorBase):
    __tablename__ = "collector_comments"
    __table_args__ = (
        UniqueConstraint("platform", "external_comment_id", name="uq_collector_comment_platform_external"),
        Index("ix_collector_comments_observed", "platform", "comment_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    platform: Mapped[str] = mapped_column(String(8), nullable=False)
    external_comment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content_title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    comment_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    author_user_id: Mapped[str | None] = mapped_column(String(255))
    author_nickname: Mapped[str | None] = mapped_column(Text)
    author_profile_url: Mapped[str | None] = mapped_column(Text)
    matched_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class CommentSnapshot(CollectorBase):
    __tablename__ = "collector_comment_snapshots"
    __table_args__ = (
        UniqueConstraint("comment_id", "run_id", name="uq_collector_snapshot_comment_run"),
        Index("ix_collector_snapshots_run", "run_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    comment_id: Mapped[str] = mapped_column(ForeignKey("collector_comments.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey("collector_runs.id", ondelete="CASCADE"), nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    author_user_id: Mapped[str | None] = mapped_column(String(255))
    author_nickname: Mapped[str | None] = mapped_column(Text)
    author_profile_url: Mapped[str | None] = mapped_column(Text)
    filter_rule_id: Mapped[str | None] = mapped_column(String(36))
    filter_rule_version: Mapped[int | None] = mapped_column(Integer)
    filter_reason: Mapped[str | None] = mapped_column(String(240))
    matched_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class AdminSession(CollectorBase):
    __tablename__ = "collector_admin_sessions"

    token_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

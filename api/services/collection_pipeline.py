# -*- coding: utf-8 -*-
# Derived from MediaCrawler (https://github.com/NanmiCoder/MediaCrawler).
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1; see LICENSE.

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from api.platforms import get_platform_definition
from database.collector_database import collector_session
from database.collector_models import CollectedComment, CommentSnapshot, utc_now
from api.services.filter_model_client import FilterModelError, evaluate_comment_batch
from tools.project_author import public_author_fields


def comment_matches(body: str, include_keywords: list[str], exclude_keywords: list[str]) -> bool:
    """Apply case-insensitive substring filters; excludes always take precedence."""
    normalized = (body or "").casefold()
    if any(keyword.casefold() in normalized for keyword in exclude_keywords if keyword.strip()):
        return False
    return not include_keywords or any(
        keyword.casefold() in normalized for keyword in include_keywords if keyword.strip()
    )


def normalize_content_url(platform: str, value: str | None) -> str:
    """Keep only stable public content URL components, dropping temporary query tokens."""
    if not value:
        return ""
    try:
        allowed_hosts = get_platform_definition(platform).allowed_hosts
    except ValueError:
        return ""
    parts = urlsplit(value.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or not any(
        host == allowed or host.endswith(f".{allowed}")
        for allowed in allowed_hosts
    ):
        return ""
    return urlunsplit(("https", host, parts.path.rstrip("/"), "", ""))


def _comment_timestamp(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def normalize_comment(platform: str, raw: dict, content_index: dict) -> dict | None:
    """Map one MediaCrawler JSONL comment to the project allowlisted record shape."""
    definition = get_platform_definition(platform)
    external_id = str(raw.get("comment_id") or "").strip()
    content_id = str(raw.get(definition.content_id_field) or "").strip()
    body = str(raw.get("content") or "")
    if not external_id or not content_id or not body:
        return None

    content = content_index.get(content_id, {})
    author = raw.get("project_author") or {}
    return {
        "platform": platform,
        "external_comment_id": external_id,
        "content_id": content_id,
        "content_title": str(content.get("title") or ""),
        "content_url": normalize_content_url(platform, content.get("url")),
        "body": body,
        "comment_time": _comment_timestamp(raw.get("create_time")),
        "author_user_id": str(author.get("platform_user_id") or "") or None,
        "author_nickname": str(author.get("nickname") or "") or None,
        "author_profile_url": normalize_content_url(
            platform, author.get("profile_url")
        ),
        "like_count": _non_negative_count(raw.get("like_count")),
        "reply_count": _non_negative_count(raw.get("sub_comment_count")),
    }


def _non_negative_count(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def spreadsheet_safe(value):
    """Prefix formula-like spreadsheet values so exports open as plain text."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _read_jsonl(directory: Path, item_type: str) -> list[dict]:
    records = []
    for path in directory.rglob(f"*_{item_type}_*.jsonl"):
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    return records


async def evaluate_candidates(candidates: list[dict], filter_rule: dict | None) -> dict:
    """Evaluate semantic candidates in batches; isolate a failed batch from later batches."""
    counts = {
        "semantic_matched": 0,
        "semantic_filtered": 0,
        "semantic_failed": 0,
    }
    if not filter_rule:
        return counts

    for start in range(0, len(candidates), 20):
        batch = candidates[start:start + 20]
        model_input = [
            {"index": index, "text": item["normalized"]["body"][:2000]}
            for index, item in enumerate(batch)
        ]
        try:
            decisions = await evaluate_comment_batch(filter_rule, model_input)
        except (FilterModelError, ValueError) as exc:
            counts["semantic_failed"] += len(batch)
            if "semantic_error_code" not in counts:
                counts["semantic_error_code"] = getattr(exc, "code", "model_error")
                counts["semantic_error"] = str(exc)[:240]
            for item in batch:
                item["semantic_decision"] = None
            continue
        by_index = {decision["index"]: decision for decision in decisions}
        for index, item in enumerate(batch):
            decision = by_index[index]
            item["semantic_decision"] = decision
            if decision["matched"]:
                counts["semantic_matched"] += 1
            else:
                counts["semantic_filtered"] += 1
    return counts


async def ingest_staging_directory(run_id: str, platform: str, task: dict, directory: Path) -> dict:
    """Filter MediaCrawler JSONL output and persist only matched comments."""
    definition = get_platform_definition(platform)
    content_records = _read_jsonl(directory, "contents")
    comment_records = _read_jsonl(directory, "comments")
    content_key = definition.content_id_field
    url_key = definition.content_url_field
    content_index = {
        str(item.get(content_key)): {
            "title": item.get("title") or item.get("desc") or "",
            "url": item.get(url_key) or "",
        }
        for item in content_records
        if item.get(content_key)
    }
    counts = {
        "seen": len(comment_records),
        "matched": 0,
        "filtered": 0,
        "invalid": 0,
        "semantic_matched": 0,
        "semantic_filtered": 0,
        "semantic_failed": 0,
    }
    include = task.get("include_keywords", [])
    exclude = task.get("exclude_keywords", [])
    filter_rule = task.get("filter_rule")
    candidates = []

    for raw in comment_records:
        normalized = normalize_comment(platform, raw, content_index)
        if normalized is None:
            counts["invalid"] += 1
            continue
        if not comment_matches(normalized["body"], include, exclude):
            counts["filtered"] += 1
            continue
        matched_keywords = [
            word for word in include if word.casefold() in normalized["body"].casefold()
        ]
        candidates.append(
            {"normalized": normalized, "matched_keywords": matched_keywords}
        )

    if filter_rule:
        semantic_counts = await evaluate_candidates(candidates, filter_rule)
        counts["filtered"] += semantic_counts["semantic_filtered"]
        counts.update(semantic_counts)

    async with collector_session() as session:
        for item in candidates:
            normalized = item["normalized"]
            decision = item.get("semantic_decision")
            if filter_rule and decision is None:
                continue
            if decision is not None and not decision["matched"]:
                continue
            now = utc_now()
            comment_values = {
                **{key: value for key, value in normalized.items() if key not in {"like_count", "reply_count"}},
                "matched_keywords": item["matched_keywords"],
                "updated_at": now,
            }
            comment_insert = insert(CollectedComment).values(**comment_values)
            comment_insert = comment_insert.on_conflict_do_update(
                index_elements=[CollectedComment.platform, CollectedComment.external_comment_id],
                set_={key: getattr(comment_insert.excluded, key) for key in (
                    "content_id", "content_title", "content_url", "body", "comment_time",
                    "author_user_id", "author_nickname", "author_profile_url", "matched_keywords", "updated_at",
                )},
            )
            await session.execute(comment_insert)
            result = await session.execute(
                select(CollectedComment.id).where(
                    CollectedComment.platform == platform,
                    CollectedComment.external_comment_id == normalized["external_comment_id"],
                )
            )
            comment_id = result.scalar_one()
            snapshot_values = {
                "comment_id": comment_id,
                "run_id": run_id,
                "like_count": normalized["like_count"],
                "reply_count": normalized["reply_count"],
                "author_user_id": normalized["author_user_id"],
                "author_nickname": normalized["author_nickname"],
                "author_profile_url": normalized["author_profile_url"],
                "filter_rule_id": filter_rule["id"] if filter_rule else None,
                "filter_rule_version": filter_rule["version"] if filter_rule else None,
                "filter_reason": (
                    decision["reason"] if decision is not None else "通过关键词筛选规则"
                ),
                "matched_keywords": item["matched_keywords"],
                "observed_at": now,
            }
            snapshot_insert = insert(CommentSnapshot).values(**snapshot_values)
            snapshot_insert = snapshot_insert.on_conflict_do_update(
                index_elements=[CommentSnapshot.comment_id, CommentSnapshot.run_id],
                set_={key: getattr(snapshot_insert.excluded, key) for key in (
                    "like_count", "reply_count", "author_user_id", "author_nickname",
                    "author_profile_url", "filter_rule_id", "filter_rule_version",
                    "filter_reason", "matched_keywords", "observed_at",
                )},
            )
            await session.execute(snapshot_insert)
            counts["matched"] += 1
    return counts

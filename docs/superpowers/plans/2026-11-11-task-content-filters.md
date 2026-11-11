# Task Content Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each keyword-search task choose content sort and publish-time window.

**Architecture:** Add task-level `content_sort` and `publish_time_days`, pass them through the worker and CLI, map them to Douyin native search parameters, and apply a post-fetch publish-time filter for Xiaohongshu.

**Tech Stack:** FastAPI/Pydantic, SQLAlchemy/Alembic, MediaCrawler CLI, React/Vite/TypeScript, pytest.

---

## Task 1: Persist task filters

**Files:**
- Modify: `database/collector_models.py`
- Modify: `api/schemas/collection.py`
- Modify: `api/services/task_service.py`
- Create: `migrations/versions/2b3c4d5e6f70_task_content_filters.py`

- [ ] Add `content_sort` (default `general`) and `publish_time_days` (default `0`).
- [ ] Add Literal validation to `TaskCreate`, `TaskPatch`, `TaskView`.
- [ ] Include both fields in the run snapshot.
- [ ] Add the Alembic migration and upgrade.
- [ ] Commit `feat: add task content filters`.

## Task 2: Pass filters to the collector

**Files:**
- Modify: `config/base_config.py`
- Modify: `cmd_arg/arg.py`
- Modify: `api/schemas/crawler.py`
- Modify: `api/services/crawler_manager.py`
- Modify: `api/services/collection_worker.py`
- Test: `tests/test_content_filter_options.py`

- [ ] Add `CONTENT_SORT` config and `--content_sort` / `--publish_time_days` CLI flags.
- [ ] Add fields to `CrawlerStartRequest` and the subprocess command.
- [ ] Pass the run snapshot values from the worker.
- [ ] Test command construction and config parsing.
- [ ] Commit `feat: pass content filters to collector`.

## Task 3: Apply platform filters

**Files:**
- Modify: `media_platform/douyin/core.py`
- Modify: `media_platform/xhs/core.py`
- Modify: `tools/time_util.py`
- Test: `tests/test_content_filter_options.py`

- [ ] Douyin maps sort to `SearchSortType` and publish window to `PublishTimeType`, passing both to `search_info_by_keyword`.
- [ ] XHS maps sort to `SearchSortType`.
- [ ] Add `publish_cutoff` and `is_within_publish_window` helpers.
- [ ] XHS skips note details outside the publish window before comments.
- [ ] Test the time-window helper.
- [ ] Commit `feat: apply platform content filters`.

## Task 4: Add task form controls

**Files:**
- Modify: `webui/src/lib/collectorApi.ts`
- Create: `webui/src/lib/taskFormat.ts`
- Modify: `webui/src/components/collector/TaskFormDialog.tsx`
- Modify: `webui/src/components/collector/CollectorWorkspace.tsx`

- [ ] Add `content_sort` and `publish_time_days` to task types and payloads.
- [ ] Add selectors for search mode only; show a note for detail mode.
- [ ] Show the selected sort/window in the task table.
- [ ] Build the frontend and commit `feat: configure content filters in task form`.

## Task 5: Verify

- [ ] Run `pytest tests/test_task_contracts.py tests/test_content_filter_options.py -q`.
- [ ] Run `npm run build` in `webui`.
- [ ] Restart the API and verify a task stores `latest` / `7`.

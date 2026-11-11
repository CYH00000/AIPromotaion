# Run Runtime Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a running collection task show its phase, staged counts, last activity, logs, and a stop action.

**Architecture:** Add `phase`, `progress`, and `last_activity_at` to `collector_runs`, update them from a worker progress loop that tails JSONL staging files and crawler logs, and surface them in the existing workspace with a run detail dialog.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, pytest/pytest-asyncio, React/Vite/TypeScript, existing `crawler_manager` logs and cancel endpoint.

---

## Task 1: Add run progress fields

**Files:**
- Modify: `database/collector_models.py`
- Create: `migrations/versions/1a2b3c4d5e6f_run_progress.py`

- [ ] Add `phase`, `progress`, `last_activity_at` to `CollectionRun`.
- [ ] Create an Alembic revision with `down_revision = "c275aba14e33"` adding the columns, with a downgrade that drops them.
- [ ] Run `.tools\uv.exe run --env-file .env alembic upgrade head`.
- [ ] Commit `feat: add run progress fields`.

## Task 2: Add the JSONL counter and stall helper

**Files:**
- Create: `api/services/run_progress.py`
- Create: `tests/test_run_progress.py`

- [ ] Write failing tests for append counting, truncation reset, incomplete trailing line, and stall threshold.
- [ ] Run `pytest tests/test_run_progress.py -q` and confirm failure.
- [ ] Implement:

```python
class JsonlLineCounter:
    def __init__(self):
        self._offsets: dict[Path, int] = {}
        self._lines: dict[Path, int] = {}

    def scan(self, directory: Path) -> tuple[int, int]:
        # returns (staged_contents, staged_comments)
```

- [ ] Run the tests and commit `feat: add staging progress counter`.

## Task 3: Update run progress from the worker

**Files:**
- Modify: `api/services/collection_worker.py`
- Test: `tests/test_run_progress.py` (pure behavior)

- [ ] Set `phase="starting"` and `progress={"staged_contents": 0, "staged_comments": 0, "stalled": False}` when claiming a run.
- [ ] Start a progress task every 3 seconds while the subprocess runs; update staged counts, `last_activity_at`, and `progress` from the counter and `crawler_manager._log_id`.
- [ ] Mark `progress["stalled"] = True` after `COLLECTOR_STALL_TIMEOUT_SECONDS` (default 180) without activity.
- [ ] Stop the progress task after `process.wait()`, then set phases `filtering`, `ingesting`, `finalizing` around `ingest_staging_directory`.
- [ ] Keep `_finish_run` as the terminal writer; set `phase` to `completed` / `failed` / `cancelled`.
- [ ] Run `pytest tests/test_run_progress.py tests/test_collection_pipeline.py tests/test_task_contracts.py -q`.
- [ ] Commit `feat: update run progress while collecting`.

## Task 4: Show progress and a run detail dialog

**Files:**
- Modify: `webui/src/lib/collectorApi.ts`
- Create: `webui/src/components/collector/RunDetailDialog.tsx`
- Modify: `webui/src/components/collector/CollectorWorkspace.tsx`

- [ ] Add `phase`, `progress`, and `last_activity_at` to `CollectionRun`.
- [ ] Add `cancelRun(runId)` to `collectorApi`.
- [ ] Add a `RunDetailDialog` that shows phase, elapsed time, staged counts, final counts, last activity, recent logs (poll `/crawler/logs` every 2s while open), and a stop button.
- [ ] In the task row, show `phase` + `staged_comments/staged_contents` + relative last activity; add a `详情` button opening the dialog.
- [ ] Show a warning when `progress.stalled` is true.
- [ ] Run `npm run build` in `webui`.
- [ ] Commit `feat: add run detail and live progress`.

## Task 5: Verify end to end

- [ ] Run `.tools\uv.exe run --env-file .env pytest tests/test_run_progress.py tests/test_collection_pipeline.py tests/test_task_contracts.py tests/test_collection_limits.py -q`.
- [ ] Restart the API and confirm an existing running task shows growing staged counts and recent logs.
- [ ] Confirm the stop button cancels a running task.
- [ ] Confirm `git status --short` contains only intended changes and no `.env` or `browser_data/`.

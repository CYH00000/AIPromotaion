# Collection and Data Pipeline Implementation Plan

> Recommended execution subskill: `superpowers:executing-plans`.

**Goal:** Create and manage keyword- or URL-driven collection tasks, invoke the MediaCrawler platform collectors through an isolated Worker boundary, persist deduplicated comments, and record each run's observation snapshot.

**Architecture:** FastAPI validates task commands and writes PostgreSQL records. A single serial Worker consumes queued run records and invokes the upstream collector through a narrow adapter. An adapter normalizes upstream records before persistence. Main comments are unique by `(platform, external_comment_id)`; snapshots are unique by `(comment_id, task_run_id)`. Invalid/missing platform IDs are counted and skipped. Partial results survive failure/cancellation.

**Tech Stack:** Existing MediaCrawler Douyin/XHS collectors and SQLAlchemy conventions; FastAPI/Pydantic; PostgreSQL and Alembic; JSONL fixtures; pytest.

## Steps

### 1. Map upstream collector and storage contracts

**Paths to inspect:** `media_platform/`, `store/douyin/`, `store/xhs/`, `database/models.py`, `database/db.py`, API routers/schemas/services. Confirm exact files at the pinned SHA before edits.

- Document the upstream entry points and available fields for search and specified-content modes. Reuse these collectors; do not recreate platform clients or signature/login logic.
- Identify where anonymization occurs and confirm the license permits the minimal project-specific field handling.

### 2. Define persistence and prove idempotency

**Paths:** project models and Alembic revisions; `tests/unit/test_record_normalization.py`; `tests/integration/test_comment_repository.py`.

- Write tests first for ID normalization, URL query-token removal, missing IDs, stable uniqueness, repeated observations, field changes, and transaction behavior.
- Add project tables for accounts/tasks/runs/content/authors/comments/snapshots only where absent and consistent with the approved schema. Preserve upstream tables and migrations.
- Persist author fields through a strict allowlist: platform user ID, nickname, profile URL. Enrich only authors of comments that pass configured filtering; if missing, persist nulls without guessing.
- Keep original comment text for review/re-filtering; do not store unapproved profile attributes.

### 3. Add task and run API services

**Paths:** `api/routers/tasks.py`, `api/routers/runs.py`, `api/schemas/tasks.py`, `api/services/task_service.py`, `api/services/run_service.py` (adapt to upstream structure).

- Add request/response models matching `docs/api/openapi.yaml` and reject platform/source combinations outside the contract.
- Implement create/list/get/update/disable and manual-run/pause/resume operations. Task deletion disables future schedules and preserves task runs and collected records.
- Create a run record before queueing. Snapshot the task's effective config at run start. Enforce safe state transitions and cooperative cancel requests.

### 4. Implement the upstream adapter and ingestion pipeline

**Paths:** project service module such as `api/services/collector_adapter.py`; Worker entry point; fixtures under `tests/fixtures/collectors/`.

- Normalize both platform outputs into a project-owned record schema. Feed approved task source and conservative limits to upstream APIs.
- Apply SQL uniqueness constraints and idempotent upserts; write a snapshot per comment/run even when counts do not change.
- Keep error codes and summaries sanitized. Commit valid partial output before marking the run `partial`, `failed`, `cancelled`, or `interrupted`.

### 5. Verify and document

- Run unit and PostgreSQL integration tests with synthetic JSONL only. Confirm concurrency and transaction boundaries.
- Validate source URLs to supported platform forms and strip temporary query tokens before persistence or export.
- Update OpenAPI and the data dictionary; retain hand-triggered real-platform validation for a later user-controlled milestone.

## Completion gate

Both source modes are represented; collectors are reused through a narrow adapter; repeated comment IDs deduplicate; each run writes a snapshot; only allowed author fields persist; and all failure paths retain already committed valid data.

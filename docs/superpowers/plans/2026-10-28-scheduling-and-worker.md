# Scheduling and Worker Implementation Plan

> Recommended execution subskill: `superpowers:executing-plans`.

**Goal:** Add manual, fixed-interval and Cron scheduling with one globally serial Worker, persisted schedules, safe restart recovery, and explicit handling of platform challenges and cancellation.

**Architecture:** PostgreSQL is the durable source of task schedule and run state. A single APScheduler 3.11-series process restores enabled schedules at startup and submits due work to one serial queue. All platform work uses one account per platform and never overlaps globally. A run already executing may retain at most one pending trigger; downtime triggers coalesce to one, not a catch-up burst.

**Tech Stack:** APScheduler 3.11 series; PostgreSQL; existing upstream Worker/collector process boundary; pytest with frozen clock and isolated Postgres.

## Steps

### 1. Specify scheduler invariants with tests

**Paths:** `worker/scheduler.py`, `worker/queue.py`, `worker/run_executor.py`, `tests/unit/test_schedule_config.py`, `tests/integration/test_scheduler_recovery.py` (adjust to repository layout).

- Test manual-only, interval minimum 60 minutes, Cron validation in `Asia/Shanghai`, next-run computation across DST/timezone boundaries where applicable, restart restoration, coalescing, and single global concurrency.
- Test state transitions for queued/running/succeeded/partial/failed/cancelled/interrupted.

### 2. Persist schedules and runs transactionally

- Store schedule configuration on task rows and durable queued/running state in run rows; avoid an in-memory-only queue as the source of truth.
- Use database locking/claim semantics appropriate to a single Worker and prevent duplicate claims after a restart.
- Keep one pending run per running task; do not create repeated backlog for downtime.

### 3. Implement APScheduler adapter

- Convert interval and Cron config into APScheduler jobs only after task validation. Persist schedule definitions in PostgreSQL and reconcile them with enabled task records at startup.
- On shutdown, stop accepting new runs, request cooperative cancellation when configured, and persist final state.
- Mark stale running records `interrupted` on recovery; do not assume a run succeeded because its process exited.

### 4. Define safe error and retry policy

- Allow only bounded retry of explicitly transient network failures. Login expiry, challenge, rate limit, account restriction, or platform denial pauses that account/task and requires human review.
- Never rotate accounts/proxies or attempt anti-bot bypass. Preserve partial data and sanitized error code/summary.
- Implement cancellation as a cooperative stop signal and create a new run for manual retry.

### 5. Validate runtime behavior

- Use fake collectors and a frozen clock; verify only one run executes across platforms, duplicate due events coalesce, and restart restores active schedules without a burst.
- Update health/readiness output with safe Worker heartbeat state, OpenAPI run states, and deployment runbook. Do not expose browser debugging ports.

## Completion gate

Schedules survive restart from PostgreSQL; global serial execution is enforced; minimum interval and timezone rules are validated; overlapping/downtime events coalesce; and platform challenge/rate-limit states stop for human review.

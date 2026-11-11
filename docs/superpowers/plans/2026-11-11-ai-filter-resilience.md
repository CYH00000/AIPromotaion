# AI Filter Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent one transient model error from failing all remaining comments, and surface the failure type.

**Architecture:** Add error codes and bounded retries to the model client, isolate failures per batch in a new `evaluate_candidates` helper, and expose semantic failure counts in the run UI.

**Tech Stack:** Python 3.12, httpx, FastAPI/Pydantic, pytest/pytest-asyncio, React/Vite/TypeScript.

---

## Task 1: Add error codes and retries

**Files:**
- Modify: `api/services/filter_model_client.py`
- Test: `tests/test_ai_filter_resilience.py`

- [ ] Add `code` to `FilterModelError`.
- [ ] Split request execution into `_post_once` and retry it in `_request_json` for `timeout`, `rate_limit`, `http_5xx`, `network`; 3 attempts, 1s/2s backoff.
- [ ] Test two timeouts then success, and a config error called once.
- [ ] Commit `feat: retry transient AI filter failures`.

## Task 2: Isolate failed batches

**Files:**
- Modify: `api/services/collection_pipeline.py`
- Test: `tests/test_ai_filter_resilience.py`

- [ ] Add `evaluate_candidates(candidates, filter_rule)` that evaluates 20 at a time.
- [ ] On final batch failure, count only that batch and continue.
- [ ] Record `semantic_error_code` and `semantic_error` from the first failed batch.
- [ ] Test a failing middle batch: first and third batches still evaluated, failed count equals 20.
- [ ] Commit `fix: isolate AI filter batch failures`.

## Task 3: Show failure details

**Files:**
- Modify: `api/services/collection_worker.py`
- Modify: `webui/src/lib/runFormat.ts`
- Modify: `webui/src/components/collector/RunDetailDialog.tsx`
- Modify: `webui/src/lib/collectorApi.ts`

- [ ] Include the safe error code in the run summary.
- [ ] Show `semantic_failed` and a Chinese error label in run details.
- [ ] Build the frontend.
- [ ] Commit `feat: surface AI filter failure reason`.

## Task 4: Raise timeout and verify

**Files:**
- Modify: `.env` and `.env.example` (local secret file stays untracked)
- Modify: `docs/architecture/ai-filter-rules.md`

- [ ] Set `AI_FILTER_TIMEOUT_SECONDS=90` in `.env` and `.env.example`.
- [ ] Update the AI filter documentation.
- [ ] Run `pytest tests/test_ai_filter_resilience.py tests/test_collection_pipeline.py -q`.
- [ ] Run `npm run build` in `webui`.
- [ ] Restart the API and confirm a small semantic batch returns decisions.

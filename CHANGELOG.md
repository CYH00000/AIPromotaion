# Changelog

All notable changes to this project will be documented in this file.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html) after the first
software release.

## [Unreleased]

### Added

- PostgreSQL 18 local service, Alembic-managed project tables, admin sessions, collection tasks/runs, deduplicated comments, and run snapshots.
- Authenticated FastAPI endpoints for task management, run cancellation, comment search, history, CSV and XLSX export.
- Per-platform runtimes with persisted interval/Cron schedules that resume enabled tasks after restarts.
- Platform status and capability APIs, plus isolated per-platform logs and run cancellation.
- Local React task/result workspace and single-admin login screen, built on the existing MediaCrawler WebUI.
- Keyword include/exclude filtering, allowlisted author fields, stable URL normalization, and formula-safe exports.
- Task-level content sort (general/latest/most liked) and publish window (unlimited/day/week/six months) for keyword searches.
- Platform account management for Douyin and Xiaohongshu: QR login, local profile status, profile mode, and unbind.
- Runtime observability for collection runs: phase, staged content/comment counts, last activity, stalled warning, recent logs, and stop action.
- Chinese-only management UI and localized API error summaries.
- Production configuration validation for private Ubuntu deployment, including secret quality, Secure cookies and AI endpoint boundaries.
- Docker Compose topology with private PostgreSQL networking, separate application egress, persistent volumes and loopback-only app/noVNC ports.
- Non-root Playwright container bundling Chromium, Xvfb, x11vnc, noVNC and a supervised Uvicorn runtime.
- Tailscale Serve lifecycle scripts for private HTTPS access, plus status, bounded logs, upgrade and rollback operations.
- Encrypted PostgreSQL/browser/project backups with checksums and an explicitly confirmed restore workflow.

### Changed

- Reused the pinned MediaCrawler collectors for Douyin/Xiaohongshu; no platform client/signature/login implementation was written from scratch.
- Changed the Python preference to 3.12 while retaining the upstream `>=3.11` compatibility requirement.
- Switched dependency resolution to the standard PyPI index after the upstream mirror returned HTTP 403 during lock resolution.
- AI filtering now retries timeouts, 429, 5xx, and network failures up to three times with backoff.
- A failed semantic batch now affects only that batch; later batches continue and the failure code is shown in the run UI.
- Paused tasks can still be run manually; only disabled tasks are blocked.
- Interrupted runs preserve staging data under `data/recovered_runs/` without blocking API startup.
- Collection scheduling now runs one worker per platform: tasks on the same platform stay serial, while Douyin and Xiaohongshu can collect concurrently.
- Cloud deployment defaults to private Tailscale HTTPS and intentionally leaves the existing public domain unused until a separate public-access review.

### Fixed

- A single AI timeout no longer marks every remaining comment as failed.
- Startup no longer runs synchronous AI ingestion for interrupted runs, which previously blocked the API.
- Manual runs are no longer blocked solely because a task is paused.

### Deferred

- Real Ubuntu cloud-host acceptance, public-domain access, cloud administrator/user management, incremental ingestion during a run, run-history browsing, snapshot diff browsing, cookie-paste login, and embedded QR login remain outside this release.

# Changelog

All notable changes to this project will be documented in this file.
This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html) after the first
software release.

## [Unreleased]

### Added

- PostgreSQL 18 local service, Alembic-managed project tables, admin sessions, collection tasks/runs, deduplicated comments, and run snapshots.
- Authenticated FastAPI endpoints for task management, run cancellation, comment search, history, CSV and XLSX export.
- Serial task worker with persisted interval/Cron schedules that resumes enabled tasks after restarts.
- Local React task/result workspace and single-admin login screen, built on the existing MediaCrawler WebUI.
- Keyword include/exclude filtering, allowlisted author fields, stable URL normalization, and formula-safe exports.

### Changed

- Reused the pinned MediaCrawler collectors for Douyin/Xiaohongshu; no platform client/signature/login implementation was written from scratch.
- Changed the Python preference to 3.12 while retaining the upstream `>=3.11` compatibility requirement.
- Switched dependency resolution to the standard PyPI index after the upstream mirror returned HTTP 403 during lock resolution.

### Deferred

- AI semantic rule generation/preview/approval, platform-account management UI, and cloud HTTPS deployment hardening remain outside this local MVP.

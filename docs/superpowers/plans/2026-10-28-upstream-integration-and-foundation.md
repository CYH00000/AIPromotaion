# Upstream Integration and Foundation Implementation Plan

> Recommended execution subskill: `superpowers:executing-plans`.

**Goal:** Integrate the exact approved MediaCrawler source baseline into this documentation-first repository while preserving the approved design, then make the smallest repeatable local development foundation with PostgreSQL.

**Architecture:** The repository remains a traceable fork of NanmiCoder/MediaCrawler at `68d9ef1c1da22eab75940dfd7cec259907006538`. Current project documentation is retained by replaying its known commits on an integration branch based on that upstream revision. Upstream API, WebUI, crawler and storage boundaries remain the base; project-specific features are added incrementally. PostgreSQL 18 is the local/cloud database baseline.

**Tech Stack:** Existing upstream Python 3.11+ and `uv.lock`; existing React/Vite and `webui/package-lock.json`; FastAPI; PostgreSQL 18; Alembic for project schema evolution; Docker Compose for local Postgres.

## Preconditions and safety

- Confirm the integration branch contains the approved documentation history (`e140545`, `a094745`, `dd90ea3`) and the committed engineering-document package. If hashes differ, identify corresponding commits by message; do not reset, discard, or overwrite files.
- Fetch and inspect the approved upstream SHA and both license scopes. Do not substitute the default branch tip for the pinned revision.
- Preserve `docs/superpowers/specs/2026-10-28-douyin-xhs-comment-collector-design.md` and all engineering documents.
- Review the exact pinned tree before choosing integration paths; upstream may move files between the date this plan was written and execution.

## Steps

### 1. Integrate the source lineage

**Paths:** repository Git metadata; upstream source tree; `LICENSE`, `webui/LICENSE`, existing `docs/`.

- Verify the pinned SHA, upstream `pyproject.toml`, `uv.lock`, `webui/package.json`, `webui/package-lock.json`, headers, and all nested license notices.
- Create `codex/integrate-mediacrawler-base` from the pinned SHA and replay the documentation commits in chronological order. The pinned source already has a root `README.md` and `.github/ISSUE_TEMPLATE/bug_report.md`: preserve the entire upstream README body and its relative links, copy the project-specific overview to `docs/project-overview.md`, prepend a short project navigation/status section to root `README.md`, and name the project bug template `collector_bug_report.yml` to avoid duplicate bug forms. Resolve other path collisions additively; stop and document any conflict that cannot be resolved without changing the approved spec.
- Add/retain an `upstream` remote and record source SHA and import procedure in `LICENSES.md` and README.
- Review the resulting diff and confirm the Git parent/history points to the pinned upstream commit.

### 2. Establish repeatable local services

**Paths:** `compose.dev.yml`, `.env.example`, `.gitignore`, `README.md`, `docs/development/standards.md`.

- Add a PostgreSQL 18 development service with a persistent named volume, health check, local-only port binding, and non-default sample credentials. The example file contains placeholders only.
- Document Docker startup, shutdown, volume reset as an explicit destructive action, and local environment setup. Do not add production secrets or expose Postgres on a public interface.

### 3. Add a project schema/migration boundary

**Paths:** inspect the pinned upstream database layout first; add project-owned migration configuration under `migrations/` only if it can coexist without replacing upstream models; add a minimal migration smoke test under `tests/`.

- Decide and document whether project tables share the upstream SQLAlchemy metadata or use a clearly named project metadata/schema. Record the decision before coding the first business model.
- Add a migration that creates only a project-owned marker table, then a rollback/revision test against an isolated PostgreSQL database. Avoid changing upstream crawler tables in this foundation step.

### 4. Verify foundation before moving on

- Run the upstream Python and WebUI install/build instructions appropriate to the pinned revision.
- Start Postgres, verify readiness, apply and downgrade the marker migration, and confirm a clean second upgrade.
- Run the upstream pre-commit checks and ensure new files follow the upstream header and formatting rules.
- Record exact successful commands and any Windows-specific limitations in README; do not claim unsupported commands work.

## Completion gate

The imported source SHA and license files are verifiable; approved docs survive; PostgreSQL starts locally; a reversible project migration succeeds; and Python/WebUI dependencies remain locked to reviewed versions. No platform account login or real collection is part of this foundation step.

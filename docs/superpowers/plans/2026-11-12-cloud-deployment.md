# Cloud Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver and verify a private single-server production deployment for the collector using Docker Compose and Tailscale.

**Architecture:** One application container runs FastAPI, the collection workers, Chromium, Xvfb, x11vnc and noVNC. PostgreSQL is private to a Compose network. Only app and noVNC ports bind to host loopback; Tailscale Serve provides private HTTPS. Production configuration, encrypted backups, restore, upgrade and rollback operations are explicit scripts.

**Tech Stack:** Ubuntu 24.04, Docker Compose, PostgreSQL 18, Python 3.12, Playwright Chromium 1.61, Xvfb, x11vnc, noVNC, Tailscale Serve, Bash, pytest.

---

## File Structure

- `deploy/validate_config.py`: parse and validate the production environment without printing secret values.
- `deploy/compose.prod.yml`: private application and PostgreSQL topology.
- `deploy/Dockerfile`: repeatable Node/Python/Playwright image build.
- `deploy/container-entrypoint.sh`: start and supervise Xvfb, x11vnc, websockify and Uvicorn.
- `deploy/lib.sh`: shared path, Compose and environment helpers for host scripts.
- `deploy/prepare.sh`: validate an empty Ubuntu host before deployment.
- `deploy/deploy.sh`: build, migrate, start and verify the stack.
- `deploy/status.sh`: show health and Tailscale status without secret values.
- `deploy/logs.sh`: show bounded application or database logs.
- `deploy/setup-tailscale.sh`: configure private HTTPS routes to loopback ports.
- `deploy/backup.sh`: create encrypted database and volume archives.
- `deploy/restore.sh`: restore an explicitly confirmed encrypted backup.
- `deploy/upgrade.sh`: back up before rebuilding a requested commit.
- `deploy/.env.production.example`: production configuration template with placeholders.
- `.dockerignore`: keep secrets, local data, caches and development tools out of the image.
- `tests/test_cloud_deployment.py`: configuration, security, script and artifact contract tests.
- `docs/deployment/cloud-deployment.md`: concrete private-cloud runbook.
- `.gitignore`, `.gitattributes`: protect local production files and force Linux line endings for scripts.

### Task 1: Production configuration validator

**Files:**
- Create: `deploy/validate_config.py`
- Create: `tests/test_cloud_deployment.py`

- [ ] **Step 1: Write failing validation tests**

```python
from pathlib import Path

from deploy.validate_config import validate_environment


def valid_environment() -> dict[str, str]:
    return {
        "POSTGRES_DB_NAME": "collector",
        "POSTGRES_DB_USER": "collector",
        "POSTGRES_DB_PWD": "database-password-123",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "administrator-password-123",
        "SESSION_COOKIE_SECURE": "true",
        "NOVNC_PASSWORD": "vnc-password-123",
        "ENABLE_CDP_MODE": "false",
        "AI_FILTER_API_BASE_URL": "",
        "AI_FILTER_API_KEY": "",
        "AI_FILTER_MODEL": "",
    }


def test_production_environment_accepts_complete_private_config():
    assert validate_environment(valid_environment()) == []


def test_production_environment_rejects_insecure_cookie():
    values = valid_environment()
    values["SESSION_COOKIE_SECURE"] = "false"
    assert validate_environment(values) == ["SESSION_COOKIE_SECURE 必须为 true"]


def test_production_environment_rejects_partial_ai_configuration():
    values = valid_environment()
    values["AI_FILTER_API_BASE_URL"] = "https://api.example.com"
    assert validate_environment(values) == ["AI_FILTER 三项配置必须同时为空或同时填写"]
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q`

Expected: collection fails because `deploy.validate_config` does not exist.

- [ ] **Step 3: Implement the validator**

Create `deploy/validate_config.py` with `validate_environment(values) -> list[str]`, `load_environment(path)`, and a CLI that prints Chinese errors without values. Enforce all rules in the design, including password lengths, placeholder rejection, secure cookies, disabled CDP, and complete-or-empty AI configuration.

- [ ] **Step 4: Verify GREEN**

Run: `.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q`

Expected: all validator tests pass.

- [ ] **Step 5: Commit**

```bash
git add deploy/validate_config.py tests/test_cloud_deployment.py
git commit -m "feat(deploy): validate production configuration"
```

### Task 2: Private Compose topology and production template

**Files:**
- Create: `deploy/compose.prod.yml`
- Create: `deploy/.env.production.example`
- Modify: `tests/test_cloud_deployment.py`

- [ ] **Step 1: Add failing Compose contract tests**

```python
import yaml


def test_compose_publishes_only_loopback_ports():
    compose = yaml.safe_load(Path("deploy/compose.prod.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert services["postgres"].get("ports") is None
    assert services["app"]["ports"] == [
        "127.0.0.1:${APP_BIND_PORT:-8080}:8080",
        "127.0.0.1:${NOVNC_BIND_PORT:-6080}:6080",
    ]
    rendered = str(compose)
    assert "9222" not in rendered
    assert "0.0.0.0:8080" not in rendered


def test_compose_uses_private_persistent_storage_and_healthchecks():
    compose = yaml.safe_load(Path("deploy/compose.prod.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert "healthcheck" in services["app"]
    assert "healthcheck" in services["postgres"]
    assert set(compose["volumes"]) == {"postgres_data", "browser_data", "project_data"}
    assert services["postgres"]["volumes"] == ["postgres_data:/var/lib/postgresql"]
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q`

Expected: Compose contract tests fail because the production files do not exist.

- [ ] **Step 3: Implement `compose.prod.yml` and production environment template**

Use the exact private port bindings tested above. Define only `app` and `postgres`, one internal network, health checks, restart policies, bounded JSON logs, named volumes, `init: true`, shared memory, and `no-new-privileges`. The app uses `env_file: .env.production`; PostgreSQL variables are interpolated from the same file. Add every required placeholder to `.env.production.example`.

- [ ] **Step 4: Verify GREEN and Compose rendering**

Run:

```powershell
.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q
docker compose --env-file deploy/.env.production.example -f deploy/compose.prod.yml config --quiet
```

Expected: tests pass and Compose renders without syntax errors.

- [ ] **Step 5: Commit**

```bash
git add deploy/compose.prod.yml deploy/.env.production.example tests/test_cloud_deployment.py
git commit -m "feat(deploy): define private production topology"
```

### Task 3: Production image and supervised browser runtime

**Files:**
- Create: `deploy/Dockerfile`
- Create: `deploy/container-entrypoint.sh`
- Create: `.dockerignore`
- Modify: `tests/test_cloud_deployment.py`, `.gitattributes`

- [ ] **Step 1: Add failing image/runtime tests**

```python
def test_entrypoint_supervises_all_private_services():
    script = Path("deploy/container-entrypoint.sh").read_text(encoding="utf-8")
    for command in ("Xvfb :99", "x11vnc", "websockify", "alembic upgrade head", "uvicorn"):
        assert command in script
    assert "wait -n" in script
    assert "trap cleanup" in script


def test_dockerfile_builds_webui_and_uses_playwright_image():
    dockerfile = Path("deploy/Dockerfile").read_text(encoding="utf-8")
    assert "FROM node:22-bookworm-slim AS webui" in dockerfile
    assert "mcr.microsoft.com/playwright/python:v1.61.0-noble" in dockerfile
    assert "npm ci" in dockerfile
    assert "uv sync --frozen --no-install-project" in dockerfile
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q`

Expected: image/runtime tests fail because files are missing.

- [ ] **Step 3: Implement image and entrypoint**

The Dockerfile uses a Node 22 web build stage and the fixed Playwright Python 1.61 image. Install `xvfb`, `x11vnc`, `novnc`, `websockify` and `tini`; synchronize from `uv.lock`; build the frontend into `api/webui`; run as non-root UID 10001 with writable `/app/browser_data` and `/app/data`; set `DISPLAY=:99`.

The entrypoint validates production environment, starts Xvfb and waits for it, writes the VNC password, starts x11vnc on loopback and websockify on 6080, runs Alembic, starts one Uvicorn process, and terminates the container if any child exits.

- [ ] **Step 4: Verify syntax and image build**

Run:

```powershell
bash -n deploy/container-entrypoint.sh
.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q
docker build -f deploy/Dockerfile -t collector-cloud-app:test .
```

Expected: syntax and tests pass, and the image builds successfully.

- [ ] **Step 5: Commit**

```bash
git add deploy/Dockerfile deploy/container-entrypoint.sh .dockerignore .gitattributes tests/test_cloud_deployment.py
git commit -m "feat(deploy): package cloud browser runtime"
```

### Task 4: Deployment lifecycle and Tailscale scripts

**Files:**
- Create: `deploy/lib.sh`
- Create: `deploy/prepare.sh`
- Create: `deploy/deploy.sh`
- Create: `deploy/status.sh`
- Create: `deploy/logs.sh`
- Create: `deploy/setup-tailscale.sh`
- Create: `deploy/upgrade.sh`
- Modify: `tests/test_cloud_deployment.py`

- [ ] **Step 1: Add failing script contract tests**

```python
def test_host_scripts_are_safe_and_relative_to_project_root():
    for name in ("prepare.sh", "deploy.sh", "status.sh", "logs.sh", "setup-tailscale.sh", "upgrade.sh"):
        text = Path("deploy", name).read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash")
        assert "set -euo pipefail" in text
        assert "deploy/.env.production" not in text


def test_tailscale_setup_uses_loopback_upstreams():
    text = Path("deploy/setup-tailscale.sh").read_text(encoding="utf-8")
    assert "http://127.0.0.1:" in text
    assert "tailscale serve" in text
    assert "0.0.0.0" not in text
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q`

Expected: host script tests fail because scripts are missing.

- [ ] **Step 3: Implement lifecycle scripts**

`lib.sh` resolves project paths, selects `.env.production`, wraps Docker Compose and validates file permissions. All scripts call it. `prepare.sh` checks Ubuntu, Docker, Compose, Tailscale, configuration and disk/permissions without installing software. `deploy.sh` validates, builds a commit-tagged image, starts PostgreSQL, migrates, starts the app and waits for readiness. `status.sh`, `logs.sh`, `setup-tailscale.sh` and `upgrade.sh` implement the design operations without printing secrets.

- [ ] **Step 4: Verify GREEN and shell syntax**

Run:

```powershell
Get-ChildItem deploy\*.sh | ForEach-Object { bash -n $_.FullName }
.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q
docker compose --env-file deploy/.env.production.example -f deploy/compose.prod.yml config --quiet
```

Expected: all scripts parse, tests pass and Compose renders.

- [ ] **Step 5: Commit**

```bash
git add deploy/lib.sh deploy/prepare.sh deploy/deploy.sh deploy/status.sh deploy/logs.sh deploy/setup-tailscale.sh deploy/upgrade.sh tests/test_cloud_deployment.py
git commit -m "feat(deploy): add private cloud lifecycle scripts"
```

### Task 5: Encrypted backup and explicit restore

**Files:**
- Create: `deploy/backup.sh`
- Create: `deploy/restore.sh`
- Modify: `deploy/.env.production.example`
- Modify: `tests/test_cloud_deployment.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add failing backup contract tests**

```python
def test_backup_encrypts_every_data_artifact_and_requires_passphrase():
    backup = Path("deploy/backup.sh").read_text(encoding="utf-8")
    assert "pg_dump" in backup
    assert "openssl enc -aes-256-cbc" in backup
    assert "BACKUP_PASSPHRASE_FILE" in backup
    assert "browser_data" in backup
    assert "project_data" in backup
    assert "chmod 700" in backup


def test_restore_requires_explicit_confirmation_and_preserves_private_volumes():
    restore = Path("deploy/restore.sh").read_text(encoding="utf-8")
    assert '"$1" != "--confirm"' in restore
    assert "pg_restore" in restore
    assert "browser_data" in restore
    assert "project_data" in restore
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py -q`

Expected: backup and restore tests fail because scripts are missing.

- [ ] **Step 3: Implement encrypted backup and restore**

Backup PostgreSQL with custom-format `pg_dump`, archive browser and project volumes through the application image, encrypt every artifact with OpenSSL AES-256-CBC/PBKDF2 using `BACKUP_PASSPHRASE_FILE`, generate SHA-256 checksums and non-secret metadata, and enforce directory/file permissions. Restore validates the archive and confirmation argument, stops the app, restores database and volumes, runs migrations, starts the app and checks readiness.

- [ ] **Step 4: Verify GREEN with encrypted synthetic artifacts**

Run the contract tests, shell syntax checks, then execute `backup.sh` against the local test Compose project with a temporary passphrase file and verify each output starts with the OpenSSL salted marker and checksums validate. Use only synthetic data.

- [ ] **Step 5: Commit**

```bash
git add deploy/backup.sh deploy/restore.sh deploy/.env.production.example tests/test_cloud_deployment.py .gitignore
git commit -m "feat(deploy): add encrypted backup and restore"
```

### Task 6: Production runbook and line-ending protection

**Files:**
- Modify: `docs/deployment/cloud-deployment.md`
- Modify: `README.md`
- Modify: `.gitattributes`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add a failing documentation contract test**

```python
def test_runbook_documents_private_access_and_critical_operations():
    text = Path("docs/deployment/cloud-deployment.md").read_text(encoding="utf-8")
    for phrase in ("Tailscale Serve", "noVNC", "backup.sh", "restore.sh", "upgrade.sh", "9222"):
        assert phrase in text
    assert "公网开放 8080" not in text
```

- [ ] **Step 2: Run the test and verify RED**

Run: `.\.tools\uv.exe run --env-file .env pytest tests/test_cloud_deployment.py::test_runbook_documents_private_access_and_critical_operations -q`

Expected: the runbook lacks one or more required operations.

- [ ] **Step 3: Rewrite the cloud runbook for the implemented package**

Document first-server preparation, Tailscale setup, environment creation, deploy/status/logs, noVNC login URL, backup scheduling, restore, upgrade and rollback. Include explicit security-group settings and commands to verify public ports are closed. Mark the existing domain as intentionally unused until a later public-access decision.

- [ ] **Step 4: Verify GREEN and formatting**

Run the documentation test and `git diff --check`.

Expected: documentation contract passes with no whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add docs/deployment/cloud-deployment.md README.md .gitattributes CHANGELOG.md tests/test_cloud_deployment.py
git commit -m "docs(deploy): add private cloud operations runbook"
```

### Task 7: Full container and persistence verification

**Files:**
- Create: `scripts/cloud_smoke_test.py`
- Modify: `docs/testing/2026-11-12-full-flow-acceptance.md`

- [ ] **Step 1: Add a failing container smoke test**

Create `scripts/cloud_smoke_test.py` that accepts `COLLECTOR_BASE_URL`, performs CSRF login using environment credentials, checks `/health/ready`, `/api/auth/me`, task listing and logout, and prints only status summaries.

- [ ] **Step 2: Run it against no server and verify RED**

Run: `.\.tools\uv.exe run --env-file .env python scripts/cloud_smoke_test.py`

Expected: connection failure or missing implementation before the Compose stack is started.

- [ ] **Step 3: Start the isolated production stack and run smoke checks**

Use a temporary test environment with synthetic credentials, `SESSION_COOKIE_SECURE=false` only for the local HTTP container test, unique project name and isolated volumes. Wait for `app` and `postgres` health, run the smoke test, verify noVNC over HTTP and confirm container UID is not root.

- [ ] **Step 4: Verify persistence**

Create a synthetic task, restart `app`, verify the task remains, write a marker into browser and project volumes, restart the stack and verify both markers remain. Stop and remove only the isolated test project and its temporary secrets.

- [ ] **Step 5: Run the complete project test suite**

Run backend tests, frontend lint and frontend build. Record exact results and the container integration result in the acceptance document.

- [ ] **Step 6: Commit**

```bash
git add scripts/cloud_smoke_test.py docs/testing/2026-11-12-full-flow-acceptance.md
git commit -m "test(deploy): verify production container workflow"
```

## Execution Gate

Do not claim cloud production readiness until a real Ubuntu host has completed Tailscale HTTPS, noVNC login, public-port closure checks and a user-triggered small platform task. Local Compose verification proves packaging and persistence, not the external cloud network boundary.

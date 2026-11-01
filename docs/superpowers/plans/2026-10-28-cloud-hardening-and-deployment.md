# Cloud Hardening and Deployment Implementation Plan

> Recommended execution subskill: `superpowers:executing-plans`.

**Goal:** Prepare and validate a single-server Compose deployment with public HTTPS access to the authenticated management UI while keeping PostgreSQL, Worker internals, platform browser profiles and debugging endpoints private.

**Architecture:** A reverse proxy terminates HTTPS and forwards same-origin requests to the Web/API service. A single Worker runs privately with access to PostgreSQL and its protected persistent browser profile volume. PostgreSQL is private and persistent. Secrets are injected at deployment time; no public registration exists. The first deployment target is one Linux server, not a multi-node/high-availability design.

**Tech Stack:** Docker Compose; PostgreSQL 18; application containers based on the upstream stack; HTTPS reverse proxy and certificate management selected for the deployment environment; encrypted backups.

## Steps

### 1. Threat-model and configuration review

**Paths:** `compose.yml`, `compose.dev.yml`, `.env.example`, container build files, `docs/deployment/cloud-deployment.md`, `tests/security/`.

- Review exposed ports, container users, mounts, networks, health probes, log output and dependency supply chain.
- Add tests/checks that reject default production secrets, unsafe debug settings and public Postgres/Worker/CDP binds.
- Ensure the model endpoint requires HTTPS and blocks loopback/private/link-local/metadata targets after DNS resolution and on redirects.

### 2. Build production service topology

- Separate Web/API, Worker, PostgreSQL and reverse proxy responsibilities; only the reverse proxy publishes public ports.
- Use non-root application users, read-only filesystem where feasible, bounded resources, health checks and restart policies.
- Mount platform browser profile storage only into the Worker; mount database data only into PostgreSQL. Keep secrets out of image layers and Compose source.
- Configure secure headers, HTTPS-only cookies, same-origin API and production API docs disabled or authenticated.

### 3. Add operations and recovery procedures

- Provide documented deployment, schema migration, upgrade, rollback, backup and restore commands. Protect backups and browser profiles with encryption and restricted permissions.
- Make readiness report only dependency availability, not connection strings or secret/account values.
- Add safe metrics/logging for API status, Worker heartbeat/queue, database capacity and backup freshness. Avoid raw comments or author details in metrics/logs.
- Test restoring a database backup in an isolated environment before documenting a release as deployable.

### 4. Validate cloud boundary

- Inspect rendered Compose configuration without printing secret values; scan container/image/dependency configuration.
- Verify from an external network that only HTTPS management entry is reachable; Postgres, Worker and CDP are unreachable.
- Test login, CSRF, session expiry, account state, health probes, backup restore and application rollback on a staging server.
- Keep the first real-platform collection a user-triggered, small-scope acceptance action after deployment.

## Completion gate

The public boundary is HTTPS-only; backend services and data volumes are private; secrets are injected and never echoed; backup restoration and rollback are exercised; and the deployment runbook matches the tested Compose topology. This plan does not authorize or perform production deployment by itself.

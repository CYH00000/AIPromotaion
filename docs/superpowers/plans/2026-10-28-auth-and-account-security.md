# Authentication and Platform Account Security Implementation Plan

> Recommended execution subskill: `superpowers:executing-plans`.

**Goal:** Add a single-administrator login and safely manage one authorized Douyin account and one authorized Xiaohongshu account through MediaCrawler-supported login flows.

**Architecture:** Extend the pinned FastAPI application and its existing browser UI. Store a server-side session identifier in a Secure, HttpOnly, SameSite cookie; hash the administrator password with Argon2id; validate CSRF tokens on state-changing routes. Keep platform browser profiles/cookies private to the Worker. API responses expose only account state and safe guidance, never credential material.

**Tech Stack:** Existing FastAPI/Pydantic/SQLAlchemy and React/Vite dependencies; PostgreSQL; Argon2id password hashing library selected after checking upstream dependency compatibility; signed CSRF/session primitives from maintained dependencies.

## Steps

### 1. Specify and test the authentication boundary

**Paths:** `api/routers/auth.py`, `api/schemas/auth.py`, `api/services/auth_service.py`, `tests/api/test_auth.py` (adapt to actual pinned router/test layout).

- Add tests first for login success/failure, rate limiting, CSRF rejection, cookie flags, session revocation, protected route behavior, and the absence of registration/password-reset exposure.
- Assert every error body and log avoids passwords, cookies, keys, and platform account contents.

### 2. Implement one administrator session

- Add a one-time/controlled administrator bootstrap mechanism using an environment secret or interactive local command; do not put initial credentials in a committed seed or public endpoint.
- Persist only Argon2id password hashes and revocable server-side session records. Rotate the session at login and revoke it on logout/password rotation.
- Add `/api/auth/csrf`, `/api/auth/login`, `/api/auth/logout`, and `/api/auth/me` according to `docs/api/openapi.yaml`.
- Apply login throttling and generic authentication failure messages. Enforce same-origin deployment and CSRF checks for all unsafe HTTP methods.

### 3. Integrate platform account login state

**Paths:** `api/routers/accounts.py`, `api/schemas/accounts.py`, `api/services/account_service.py`, project configuration/secrets adapter; `tests/api/test_accounts.py`.

- Inspect the pinned MediaCrawler-supported login workflow and UI before wrapping it; keep browser/login mechanics inside upstream-supported paths.
- Enforce at most one account record per platform. Store only a secret reference and safe status; actual profile/cookie data stays in a private Worker-owned directory or secret store.
- Add start/status endpoints. Return a flow ID/status and sanitized instructions; never return cookies, tokens, local profile paths or unredacted login payloads.
- Keep account state changes auditable without storing unnecessary user data.

### 4. Update the existing WebUI login/account screens

**Paths:** `webui/src/lib/api.ts`, `webui/src/types/auth.ts`, `webui/src/pages/Login.tsx`, account settings components discovered in the pinned UI.

- Use same-origin API calls with credentials and CSRF header handling. Do not persist session credentials in localStorage/sessionStorage.
- Show only whether each platform account is ready, waiting for interactive login, or needs attention.

### 5. Validate and document

- Run targeted auth/account tests, dependency checks, upstream lint/build and pre-commit.
- Verify unauthenticated business requests fail, secrets never appear in API responses or logs, and login throttling is observable without leaking account existence.
- Update OpenAPI, README setup steps, and cloud configuration examples. Manual real-account login is a user-controlled acceptance activity, not CI.

## Completion gate

Single-admin auth and CSRF tests pass; session revocation works; each platform has at most one account; secrets remain server-side; existing upstream login is reused; and account management remains compatible with the approved two-platform boundary.

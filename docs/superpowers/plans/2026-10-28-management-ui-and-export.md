# Management UI and Export Implementation Plan

> Recommended execution subskill: `superpowers:executing-plans`.

**Goal:** Extend the existing MediaCrawler WebUI into a single-admin workspace for account state, task and run management, comment search/history, AI rule approval, and CSV/XLSX export.

**Architecture:** Continue the upstream React/Vite application and API client. Use same-origin authenticated API requests, server-side pagination, and explicit loading/empty/error states. The backend remains authoritative for filtering and export limits. The UI renders platform text as untrusted content and exposes only the approved author fields.

**Tech Stack:** Pinned upstream React/Vite/TypeScript dependencies and package lock; existing UI component conventions; FastAPI contract in `docs/api/openapi.yaml`; backend CSV/XLSX serialization.

## Steps

### 1. Audit existing UI and define routes

**Paths to inspect:** `webui/src/App.tsx`, `webui/src/lib/api.ts`, existing page/components/types/styles and `webui/package.json` at the pinned SHA.

- Reuse upstream navigation, form and table patterns where suitable. Keep project pages within current UI architecture; do not replace the WebUI wholesale.
- Define route and view states for login, overview, tasks, runs, comments, rule drafts/approval, accounts and model settings.

### 2. Implement task and run management

**Paths:** existing `webui/src` page/components/types according to audit; update API client types.

- Build task forms that enforce a single platform and either keyword or URL source, source limits, manual/interval/Cron schedule, collection caps and include/exclude terms.
- Show queue, current state, safe error summary, counts, next run, pause/resume, manual run and cooperative cancel controls.
- Confirm destructive-looking task disable behavior while explaining collected results remain available.

### 3. Implement comment search and observation history

- Add server-paginated filters for platform, task, text, author ID, matched rule and observation time.
- Show comment text, content title/link, comment time, latest likes/replies, matched rule and only platform user ID/nickname/profile link.
- Add snapshot history so count and allowed author-field changes can be compared over time.
- Treat all content as text; do not render platform-supplied HTML.

### 4. Implement rule approval and account/model settings

- Provide a draft/preview/explicit-approve workflow; distinguish draft, approved, and failed states.
- Show account login state without displaying cookies or tokens. Show model endpoint/name and key configured state without exposing the API key.
- Send writes with CSRF token and keep session material out of browser storage.

### 5. Implement exports and verify usability

- Add CSV and XLSX downloads using current filters; backend applies a 10,000-row cap and spreadsheet formula-injection protection.
- Add UI feedback for 401/session expiry, validation errors, 429, conflict, empty results and over-limit export.
- Run frontend lint/build and API/UI integration tests with synthetic fixtures. Review keyboard navigation and narrow-screen layout.

## Completion gate

The UI can manage tasks/runs, search comments and snapshots, preview/approve rules, inspect safe account/model state, and export filtered results in both formats with no credential or unapproved author fields exposed.

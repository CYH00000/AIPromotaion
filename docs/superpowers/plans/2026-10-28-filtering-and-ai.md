# Filtering and AI Rule Implementation Plan

> Recommended execution subskill: `superpowers:executing-plans`.

**Goal:** Filter comments with configurable include/exclude keywords and optional AI semantics, while requiring user preview and approval before an AI-generated rule can be used.

**Architecture:** Deterministic keyword filtering runs first. Exclude terms always reject; when include terms exist, at least one must match. If a task has an approved AI rule, a comment must also pass semantic evaluation (AND behavior). Natural-language criteria become a strictly validated, immutable, versioned JSON rule. Only comment text and the approved rule are sent to the configured model; author fields are never sent. Business storage retains only matched comments. Model errors are counted and surfaced as partial runs; failed comments are not treated as matches or persisted.

**Tech Stack:** Existing FastAPI/Pydantic/HTTPX; PostgreSQL/Alembic; configurable HTTPS OpenAI-compatible model API; Pydantic validation.

## Steps

### 1. Define the safe rule DSL and expected outcomes

**Paths:** `api/schemas/filter_rules.py`, `api/services/keyword_filter.py`, `api/services/rule_validator.py`, `tests/unit/test_keyword_filter.py`, `tests/unit/test_rule_validator.py`.

- Write tests first for include/exclude precedence, empty include list, Unicode text, invalid operators/fields/lengths, and deterministic outcomes.
- Permit only a finite allowlisted set of comment-text operators. Do not accept arbitrary Python, SQL, executable expressions, model-selected URLs, or tool calls.

### 2. Add model configuration and safe client

**Paths:** `api/services/model_client.py`, settings route/schema, secrets adapter, `tests/unit/test_model_client.py`.

- Store the API key in server-side `.env`/deployment secret configuration and expose only a configured boolean. Do not return the key on GET/PUT.
- Require HTTPS; reject non-public DNS targets and redirects. Set connection/read timeouts and response size limits.

### 3. Implement draft, preview and approval workflow

**Paths:** filter-rule model/migration, `api/routers/filter_rules.py`, `api/services/filter_rule_service.py`, `tests/api/test_filter_rules.py`.

- Create an unapproved draft from natural language and validate model output against the DSL schema.
- Preview the generated rule summary and positive/negative signals in the Add Task UI. Preview does not activate a rule.
- Approval freezes the rule version and timestamp. Approved versions cannot be edited in place; changes create a new draft/version.
- Verify the outbound model payload excludes author ID, nickname, profile URL, platform cookies and unrelated account data.

### 4. Integrate filtering into ingestion

- Run keyword filtering before optional AI. Store matched rule version and a short safe reason in the run snapshot.
- On model failure, do not persist the comment and never treat the error as a match; report the failure count in run metrics and mark the run partial.

### 5. Validate contracts and UI flow

- Update OpenAPI and project documentation for rules and task linkage; add UI states for natural-language input, generated preview, explicit approval, approved version, and provider failure.
- Keep model response handling restricted to validated JSON; no model output is executable.

## Completion gate

Keyword logic is deterministic; AI rules cannot activate before user approval; approved versions are immutable; model requests contain no author fields; failures remain visible and never silently count as matches.

# Implementation Plan: Production Hardening

## Overview

Cross-cutting engineering pass to make the multi-tenant real estate lead management SaaS production-grade. Tasks follow the 4-layer backend architecture (routers → services → repositories → models + dependencies), frontend restructure, security hardening, watcher resilience, and developer experience improvements. Each task builds incrementally on the previous ones and ends with full integration.

## Tasks

- [x] 1. Repository hygiene and .gitignore cleanup
  - Add `frontend/dist/`, `htmlcov/`, `*.db`, `*.log`, `*.sqlite`, `*.sqlite3`, `.hypothesis/`, `__pycache__/`, `.env` to `.gitignore`
  - Delete root-level test artifacts: `test_connection.py`, `test_watcher_simple.py`, `test_template_body.txt`, `test_template_body_updated.txt`, `test_template.txt`, `sample_test_email.txt`, `gmail_lead_sync.db`, `gmail_lead_sync.log`
  - Move `deployment/gmail-lead-sync.service` to `docs/deployment/systemd/` with a README explaining it is an alternative to Docker Compose
  - Consolidate duplicate root-level docs: move `API_DOCUMENTATION.md` + `API_USAGE_GUIDE.md` → `docs/API.md`; remove `BACKEND_API_REVIEW.md`, `BACKEND_COMPLETION_SUMMARY.md`, `FRONTEND_IMPLEMENTATION_PLAN.md`, `TESTING_GUIDE.md`, `TESTING_SUMMARY.md`
  - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 2. Environment variables and secrets management
  - [x] 2.1 Create root-level `.env.example` with every variable from the design's env table, inline comments, and safe placeholder values
    - Variables: `DATABASE_URL`, `ENCRYPTION_KEY`, `SECRET_KEY`, `API_HOST`, `API_PORT`, `CORS_ORIGINS`, `SESSION_TIMEOUT_HOURS`, `SYNC_INTERVAL_SECONDS`, `REGEX_TIMEOUT_MS`, `ENABLE_AUTO_RESTART`, `ENVIRONMENT`, `LOG_LEVEL`
    - _Requirements: 1.3, 4.2_

  - [x] 2.2 Add startup secret validation to `api/config.py` (or `api/core/config.py`)
    - Raise `ValueError` with descriptive message if `ENCRYPTION_KEY` or `SECRET_KEY` is absent or shorter than 32 characters
    - _Requirements: 1.4, 4.4_

  - [x] 2.3 Write property test for startup secret validation
    - **Property 1: Startup rejects short or absent secrets**
    - **Validates: Requirements 1.4, 4.4**
    - File: `tests/property/test_prop_startup_validation.py`
    - Strategy: `st.text(max_size=31)` for key values; assert `ValueError` raised

  - [x] 2.4 Write property test for .env.example coverage
    - **Property 2: .env.example covers all config variables**
    - **Validates: Requirements 1.3, 4.2**
    - File: `tests/property/test_prop_env_example_coverage.py`
    - Strategy: enumerate all variable names referenced in `load_config()`; assert each appears in `.env.example`

  - [x] 2.5 Create `scripts/generate_secrets.sh` that writes cryptographically secure `ENCRYPTION_KEY` and `SECRET_KEY` to `.env`
    - _Requirements: 4.5_

- [x] 3. Makefile and Docker Compose one-command startup
  - [x] 3.1 Create root-level `Makefile` with targets: `up`, `down`, `migrate`, `test`, `lint`, `typecheck`, `build`, `generate-secrets`
    - `up`: `docker compose up --build -d`
    - `down`: `docker compose down`
    - `migrate`: `alembic upgrade head`
    - `test`: `pytest tests/ -x`
    - `lint`: `ruff check . && cd frontend && npx eslint src/`
    - `typecheck`: `mypy api/ gmail_lead_sync/ && cd frontend && npx tsc --noEmit`
    - `build`: `cd frontend && npm run build`
    - `generate-secrets`: `scripts/generate_secrets.sh`
    - _Requirements: 1.1, 1.5, 3.1, 3.2, 3.3_

  - [x] 3.2 Create `docker-entrypoint.sh` with three-step startup sequence
    - Step 1: validate `ENCRYPTION_KEY` and `SECRET_KEY` (length ≥ 32); exit 1 with descriptive message on failure
    - Step 2: run `alembic upgrade head`; exit 1 with full stack trace on migration failure
    - Step 3: exec `uvicorn api.main:app`
    - _Requirements: 1.4, 2.2, 2.4_

  - [x] 3.3 Create or update `docker-compose.yml` with `api` and `frontend` services
    - `api` service: builds from `Dockerfile`, uses `docker-entrypoint.sh`, mounts `.env`
    - `frontend` service: builds from `frontend/Dockerfile`, serves `dist/` via nginx
    - _Requirements: 1.1, 1.2_

- [x] 4. Health endpoint
  - [x] 4.1 Create `GET /api/v1/health` route in `api/routers/public_health.py`
    - No authentication required
    - Query DB connectivity; query active watcher count and last heartbeat per agent from `WatcherRegistry`
    - Return `{"status": "healthy"|"degraded", "database": "connected"|"error", "active_watchers": int, "errors_last_24h": int, "watchers": {agent_id: {"status": str, "last_heartbeat": str|null}}}`
    - Return HTTP 200 when healthy, HTTP 503 when database unreachable
    - _Requirements: 1.6, 2.3, 2.5_

  - [x] 4.2 Write unit test for health endpoint response shape
    - Assert all required fields present; assert HTTP 200 on healthy DB; assert HTTP 503 on DB error
    - _Requirements: 2.3, 2.5_

- [x] 5. Unified error response schema
  - [x] 5.1 Verify `api/models/error_models.py` defines `ErrorResponse` with fields `error`, `message`, `code`, `details`; create or update if missing
    - _Requirements: 5.1_

  - [x] 5.2 Register exception handlers in `api/main.py` for `RequestValidationError` (422), `AuthenticationException` (401), `AuthorizationException` (403), `NotFoundException` (404), `ConflictException` (409), `TimeoutException` (408), `RateLimitExceeded` (429), and catch-all `Exception` (500)
    - All handlers return `ErrorResponse` JSON
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 5.3 Write property test for unified error schema
    - **Property 3: Unified error schema on all error responses**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
    - File: `tests/property/test_prop_error_schema.py`
    - Strategy: send random invalid requests to each endpoint category; assert response body matches `ErrorResponse` schema for all 4xx/5xx

- [x] 6. Backend 4-layer architecture — repositories layer
  - [x] 6.1 Create `api/repositories/__init__.py` and `api/repositories/lead_repository.py`
    - Implement `LeadRepository` with `get_by_id(lead_id, tenant_id)`, `list_for_tenant(tenant_id, skip, limit)`, `list_all_with_tenant(skip, limit)`, `create(data, tenant_id)`, `update(lead_id, tenant_id, data)`
    - All tenant-scoped methods MUST include `tenant_id` / `agent_id` filter in the query; never trust user-supplied IDs
    - _Requirements: 6.1, 7.1, 7.2_

  - [x] 6.2 Create `api/repositories/agent_repository.py`, `api/repositories/credential_repository.py`, `api/repositories/watcher_repository.py`, `api/repositories/lead_source_repository.py`
    - Each repository owns all SQLAlchemy queries for its domain
    - Credential repository methods always scope to owning agent
    - _Requirements: 6.4, 7.1, 7.2_

  - [x] 6.3 Write unit tests for repository tenant scoping
    - Assert `LeadRepository.get_by_id` returns `None` when `tenant_id` does not match
    - Assert `CredentialRepository` methods reject cross-tenant access
    - _Requirements: 6.1, 6.4_

- [x] 7. Backend 4-layer architecture — dependencies module
  - Create `api/dependencies/__init__.py`, `api/dependencies/auth.py`, `api/dependencies/db.py`, `api/dependencies/pagination.py`
  - `auth.py`: implement `get_current_agent`, `get_current_admin`, `require_role(role)` factory
  - `db.py`: move `get_db` session generator here
  - `pagination.py`: implement `get_pagination(skip, limit)` returning `PaginationParams`
  - Remove any duplicate `get_db` / auth dependency definitions from other modules
  - _Requirements: 7.4_

- [x] 8. Backend 4-layer architecture — router consolidation
  - [x] 8.1 Rename/consolidate `api/routes/` into `api/routers/` using the naming convention: `admin_*.py`, `agent_*.py`, `public_*.py`
    - Remove or merge `api/routes/agents.py` and any other files that overlap with `api/routers/` equivalents
    - _Requirements: 5.8, 7.1, 7.6_

  - [x] 8.2 Audit all router modules: remove direct SQLAlchemy queries from routers; replace with repository or service calls
    - Ensure no `FastAPI`-specific imports (`Request`, `Response`, `Depends`) appear in service modules
    - _Requirements: 7.2, 7.3_

  - [x] 8.3 Apply `require_role` dependency at `APIRouter` constructor level for all admin and agent routers
    - `admin_*.py` routers: `dependencies=[Depends(require_role("platform_admin"))]`
    - `agent_*.py` routers: `dependencies=[Depends(require_role("agent"))]`
    - _Requirements: 11.2, 11.3_

- [~] 9. Multi-tenant isolation enforcement
  - [x] 9.1 Audit every route that returns tenant-scoped resources; replace any user-supplied `agent_id` / `tenant_id` path/query params with the value from the authenticated session
    - _Requirements: 6.1, 6.2_

  - [~] 9.2 Add integration tests for cross-tenant access on each resource type (leads, credentials, watchers, lead sources)
    - Assert HTTP 403 returned; assert response body contains no data from the other tenant
    - _Requirements: 6.6_

  - [~] 9.3 Verify property test for tenant isolation covers new repository layer
    - **Property 4: Tenant isolation — cross-tenant access returns 403**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**
    - File: `tests/property/test_prop_tenant_isolation.py` (already exists — extend to cover repository-layer paths)

- [~] 10. Lead state machine consolidation
  - [~] 10.1 Create `api/services/lead_state_machine.py` that re-exports (or moves) the canonical `LeadStateMachine` and `LeadState` enum from `gmail_lead_sync/preapproval/state_machine.py`
    - Ensure all other modules import `LeadState` and `LeadStateMachine` from the new canonical path
    - _Requirements: 8.1, 8.2_

  - [~] 10.2 Add idempotency check to `LeadStateMachine.transition()`: before writing a `LeadStateTransition` row, check for an existing row with the same `(lead_id, from_state, to_state)` within the last 5 seconds; return existing row if found
    - _Requirements: 8.5, 8.6_

  - [~] 10.3 Create `GET /api/v1/agent/leads/{lead_id}/events` endpoint in `api/routers/agent_leads.py`
    - Returns `LeadStateTransition` rows for the lead ordered by `occurred_at` ascending
    - Scoped to authenticated agent's tenant
    - _Requirements: 8.7_

  - [~] 10.4 Verify property tests for state machine cover idempotency and event log ordering
    - **Property 5: Invalid transitions rejected** — `tests/property/test_prop_status_transitions.py` (already exists)
    - **Property 6: Valid transitions produce exactly one event row** — `tests/property/test_prop_status_transitions.py` (already exists)
    - **Property 7: State machine and watcher idempotency**
    - **Validates: Requirements 8.5, 8.6, 10.4**
    - File: `tests/property/test_prop_idempotency.py` (new)
    - **Property 8: Event log is chronologically ordered**
    - **Validates: Requirements 8.7**
    - File: `tests/property/test_prop_event_log_order.py` (new)

- [~] 11. ProcessedMessage model and watcher idempotency
  - [~] 11.1 Create `ProcessedMessage` SQLAlchemy model in `api/models/` (or `gmail_lead_sync/models.py`)
    - Fields: `id`, `agent_id`, `message_id_hash` (SHA-256 of Message-ID header), `processed_at`, `lead_id` (nullable FK)
    - Unique constraint on `(agent_id, message_id_hash)`
    - _Requirements: 10.4_

  - [~] 11.2 Generate Alembic migration for `processed_messages` table
    - _Requirements: 10.4_

  - [~] 11.3 Update `GmailWatcher.is_email_processed` to use `ProcessedMessage` table lookup by `message_id_hash` instead of `Lead.gmail_uid`
    - _Requirements: 10.4_

- [~] 12. Watcher/worker resilience
  - [~] 12.1 Replace fixed `RETRY_DELAYS` in `WatcherRegistry._run_watcher` with exponential backoff: `min(5 * 2^(attempt-1), 300)` seconds, up to 5 consecutive attempts, then transition to `FAILED`
    - _Requirements: 10.1_

  - [~] 12.2 Add `last_heartbeat` field to `WatcherInfo`; emit `DEBUG`-level heartbeat log entry every polling cycle and update `last_heartbeat` timestamp
    - _Requirements: 10.6_

  - [~] 12.3 Wrap `watcher.process_unseen_emails()` in `asyncio.wait_for(..., timeout=30)`; on `TimeoutError` log WARNING and continue to next cycle
    - _Requirements: 10.5_

  - [~] 12.4 Ensure the `except Exception` in the polling loop logs `agent_id`, `error_type`, and full stack trace (`exc_info=True`) at ERROR level and continues the loop
    - _Requirements: 10.7_

  - [~] 12.5 Implement auto-restart cooldown: when `ENABLE_AUTO_RESTART=true`, schedule watcher restart after 60-second cooldown following `FAILED` transition; log ERROR with `agent_id`, error type, message, and timestamp when marking `FAILED`
    - _Requirements: 10.2, 10.3_

  - [~] 12.6 Write property test for exponential backoff schedule
    - **Property 9: Watcher exponential backoff schedule**
    - **Validates: Requirements 10.1**
    - File: `tests/property/test_prop_watcher_backoff.py`
    - Strategy: `st.integers(min_value=1, max_value=5)` for failure count; assert delay equals `min(5 * 2^(k-1), 300)`

  - [~] 12.7 Write property test for polling loop exception survival
    - **Property 10: Watcher polling loop survives unhandled exceptions**
    - **Validates: Requirements 10.7**
    - File: `tests/property/test_prop_watcher_resilience.py`
    - Strategy: inject random exception types into the poll loop body; assert loop continues

  - [~] 12.8 Write property test for heartbeat reflected in health endpoint
    - **Property 11: Watcher heartbeat reflected in health endpoint**
    - **Validates: Requirements 10.6**
    - File: `tests/property/test_prop_watcher_heartbeat.py`
    - Strategy: mock watcher polling cycles; assert `last_heartbeat` in health response is within `SYNC_INTERVAL_SECONDS + 30` seconds

- [~] 13. Checkpoint — core backend passes tests
  - Ensure all tests pass, ask the user if questions arise.

- [~] 14. Security hardening
  - [~] 14.1 Add security headers middleware to `api/main.py`
    - Set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` on every response
    - _Requirements: 11.5_

  - [~] 14.2 Add `slowapi` rate limiting to `POST /api/v1/auth/login` and `POST /api/v1/agent/auth/login`
    - Limit: 10 requests/minute per IP; return HTTP 429 with `ErrorResponse` on excess
    - _Requirements: 11.6_

  - [~] 14.3 Create `api/utils/sanitization.py` with `sanitize_string(value: str) -> str` using `bleach.clean(value, tags=[], strip=True)`
    - Apply as Pydantic validator on `lead.name`, `lead.email`, `lead.notes` fields
    - _Requirements: 11.4_

  - [~] 14.4 Ensure `api/utils/regex_tester.py` enforces `REGEX_TIMEOUT_MS` using `signal.alarm` (Unix) or thread-based timeout; reject and return error if pattern exceeds timeout
    - _Requirements: 11.7_

  - [~] 14.5 Add auth failure logging in authentication handlers: log `WARNING` with `username_attempted` and `source_ip`; never log the attempted password
    - _Requirements: 11.8_

  - [~] 14.6 Set `secure=True`, `httponly=True`, `samesite="strict"` on all session cookies when `ENVIRONMENT=production`
    - _Requirements: 4.6_

  - [~] 14.7 Write property test for security headers
    - **Property 16: Security headers present on all responses**
    - **Validates: Requirements 11.5**
    - File: `tests/property/test_prop_security_headers.py`
    - Strategy: random endpoint paths; assert all three headers present on every response

  - [~] 14.8 Write property test for rate limiting
    - **Property 17: Rate limiting on login endpoints**
    - **Validates: Requirements 11.6**
    - File: `tests/property/test_prop_rate_limiting.py`
    - Strategy: send > 10 requests within window; assert 11th+ returns HTTP 429

  - [~] 14.9 Write property test for XSS sanitization
    - **Property 15: XSS sanitization strips HTML from string inputs**
    - **Validates: Requirements 11.4**
    - File: `tests/property/test_prop_xss_sanitization.py`
    - Strategy: random strings with HTML tags; assert stored value equals `bleach.clean(input, tags=[], strip=True)`

  - [~] 14.10 Write property test for regex timeout enforcement
    - **Property 18: Regex timeout enforcement**
    - **Validates: Requirements 11.7**
    - File: `tests/property/test_prop_regex_timeout.py`
    - Strategy: catastrophic backtracking patterns; assert validation fails within timeout

  - [~] 14.11 Write property test for RBAC
    - **Property 13: RBAC — agent sessions cannot access admin endpoints**
    - **Property 14: RBAC — admin sessions cannot act as agents**
    - **Validates: Requirements 11.2, 11.3**
    - File: `tests/property/test_prop_rbac.py`
    - Strategy: random admin/agent endpoint paths with wrong-role tokens; assert HTTP 403

  - [~] 14.12 Write property test for auth failure logging
    - **Property 19: Auth failure logs contain username and IP but not password**
    - **Validates: Requirements 11.8**
    - File: `tests/property/test_prop_auth_logging.py`
    - Strategy: random username/password pairs; assert log entry contains username + IP, does not contain password

  - [~] 14.13 Write property test for PII absent from INFO-level logs
    - **Property 20: PII absent from INFO-level logs**
    - **Validates: Requirements 4.7**
    - File: `tests/property/test_prop_pii_logging.py`
    - Strategy: random lead PII values; assert no INFO+ log entry contains those literal strings

- [~] 15. Checkpoint — security tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [~] 16. Frontend restructure
  - [~] 16.1 Create directory structure: `frontend/src/apps/agent/`, `frontend/src/apps/platform-admin/`, `frontend/src/shared/`
    - _Requirements: 9.1_

  - [~] 16.2 Move `frontend/src/agent/` → `frontend/src/apps/agent/`; update all import paths
    - _Requirements: 9.2_

  - [~] 16.3 Move platform-admin-specific files from `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/contexts/AuthContext.*` → `frontend/src/apps/platform-admin/`; update all import paths
    - _Requirements: 9.3_

  - [~] 16.4 Move shared files to `frontend/src/shared/`:
    - `src/contexts/ThemeContext.*` and `src/contexts/ToastContext.*` → `src/shared/contexts/`
    - `src/utils/api.ts` → `src/shared/api/client.ts`
    - `src/utils/theme.ts` → `src/shared/utils/theme.ts`
    - `src/utils/useT.ts` → `src/shared/hooks/useT.ts`
    - Update all import paths
    - _Requirements: 9.4_

  - [~] 16.5 Update `frontend/src/main.tsx` to mount platform-admin at `/` and agent app at `/agent/*`
    - _Requirements: 9.7_

  - [~] 16.6 Remove unused component files, hook files, and utility files identified during the restructure
    - _Requirements: 9.6, 15.6_

  - [~] 16.7 Run `make build` and fix any TypeScript/import errors until the build succeeds with zero errors
    - _Requirements: 9.5, 3.6_

- [~] 17. Lint, typecheck, and build clean pass
  - [~] 17.1 Run `make lint`; fix all `ruff` violations in Python source and all `eslint` violations in TypeScript/TSX
    - _Requirements: 3.1, 3.4_

  - [~] 17.2 Run `make typecheck`; fix all `mypy` errors in `api/` and `gmail_lead_sync/` and all `tsc --noEmit` errors in `frontend/`
    - _Requirements: 3.2, 3.5_

  - [~] 17.3 Remove all unused imports, unused variables, and unreachable code paths flagged by the linter
    - _Requirements: 15.5_

- [~] 18. Documentation
  - [~] 18.1 Create or update root-level `README.md` with: project overview, prerequisites (Python version, Node version, Docker), quick-start using `make up`, environment variable reference, CI badge, links to `docs/`
    - _Requirements: 12.1, 14.5_

  - [~] 18.2 Create `docs/ARCHITECTURE.md` describing backend layer structure, frontend app structure, database schema overview, and watcher/worker flow
    - _Requirements: 12.2_

  - [~] 18.3 Create `CONTRIBUTING.md` describing how to run tests, add a new API endpoint, add a new frontend page, and the branching/PR process
    - _Requirements: 12.3_

  - [~] 18.4 Create `SECURITY.md` describing secrets management, credential encryption, session security, and vulnerability reporting
    - _Requirements: 12.4_

  - [~] 18.5 Create `docs/TESTING_GAPS.md` listing untested modules and rationale for each gap
    - _Requirements: 12.7_

  - [~] 18.6 Create `scripts/validate_clean_clone.sh` that clones to a temp dir, copies `.env.example` → `.env` with generated secrets, runs `docker compose up -d`, polls the health endpoint until healthy or 120s timeout, and reports pass/fail
    - _Requirements: 13.1, 13.2, 13.4_

  - [~] 18.7 Create `docs/CLEAN_CLONE_VALIDATION.md` documenting the validation result, date, environment, and known issues
    - _Requirements: 13.3_

- [~] 19. CI/CD baseline
  - Create `.github/workflows/ci.yml` triggered on push and pull_request to main
  - Steps: `actions/checkout@v4`, `actions/setup-python@v5` (with pip cache keyed on `requirements-dev.txt`), `actions/setup-node@v4` (with npm cache keyed on `package-lock.json`), `pip install -r requirements-dev.txt`, `cd frontend && npm ci`, `make lint`, `make typecheck`, `make test`
  - Fail pipeline if any step exits non-zero
  - _Requirements: 14.1, 14.2, 14.3_

- [~] 20. Final checkpoint — all tests pass, build clean
  - Ensure `make lint`, `make typecheck`, `make build`, and `make test` all exit zero.
  - Ensure `make up` reaches healthy state and `GET /api/v1/health` returns HTTP 200 with `status: "healthy"`.
  - Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP pass
- Property tests reference design document property numbers for traceability
- Existing property tests (`test_prop_credential_never_plaintext.py`, `test_prop_tenant_isolation.py`, `test_prop_status_transitions.py`) are extended rather than replaced where noted
- All repository methods must include tenant scoping in the query itself — never rely solely on route-level checks
- The `ProcessedMessage` table decouples watcher idempotency from lead creation, enabling safe replay
- Frontend restructure (task 16) should be done as a single atomic commit to avoid broken intermediate import states

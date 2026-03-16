# Requirements Document

## Introduction

This document defines the requirements for a full engineering cleanup and hardening pass on the multi-tenant real estate lead management SaaS. The goal is to make the repository production-grade: clean, secure, well-documented, and runnable from a single command by any developer. The work spans backend architecture standardization, frontend restructuring, security hardening, watcher/worker resilience, developer experience improvements, and documentation completion.

The system consists of:
- A FastAPI backend (`api/`) with platform-admin routes (`api/routes/`) and agent-app routes (`api/routers/`)
- A Gmail IMAP watcher/worker module (`gmail_lead_sync/`)
- A React/TypeScript frontend (`frontend/src/`) serving both the platform-admin panel and the agent-facing app
- SQLite database managed via Alembic migrations
- Docker Compose for containerized deployment

---

## Glossary

- **System**: The complete multi-tenant real estate lead management SaaS application
- **Backend**: The FastAPI application in `api/` and the `gmail_lead_sync/` worker module
- **Frontend**: The React/TypeScript application in `frontend/src/`
- **Platform_Admin**: The internal admin panel used by platform operators (currently scattered under `frontend/src/pages/`, `frontend/src/components/`)
- **Agent_App**: The agent-facing web application (currently under `frontend/src/agent/`)
- **Watcher**: The per-agent IMAP polling process that ingests leads from Gmail
- **Watcher_Registry**: The `api/services/watcher_registry.py` module that manages Watcher lifecycle
- **Lead_State_Machine**: The single authoritative module defining lead state transitions and transition rules
- **Tenant**: An agent or company whose data must be isolated from all other tenants
- **Migration**: An Alembic database migration script in `migrations/versions/`
- **Router**: A FastAPI `APIRouter` instance defining a group of HTTP endpoints
- **Service**: A Python module in `api/services/` containing business logic
- **Repository**: A data-access layer module responsible for all database queries
- **Shared_Module**: Frontend code in `frontend/src/shared/` usable by both Agent_App and Platform_Admin
- **One_Command_Startup**: The ability to clone the repo and start all services with a single terminal command
- **Health_Endpoint**: The `GET /api/v1/health` endpoint that reports system status
- **Smoke_Test**: A minimal automated test that verifies the application starts and core paths respond correctly
- **CI_Pipeline**: An automated workflow (e.g., GitHub Actions) that runs lint, typecheck, and tests on every push
- **Dead_Code**: Source files, functions, imports, or configuration that are unreachable or unused
- **PII**: Personally Identifiable Information (lead names, email addresses, phone numbers)
- **RBAC**: Role-Based Access Control enforcing that users can only access resources permitted by their role
- **Idempotency**: The property that processing the same input multiple times produces the same result as processing it once

---

## Requirements

### Requirement 1: One-Command Startup

**User Story:** As a developer, I want to clone the repository and start all services with one command, so that I can begin development or evaluation without manual setup steps.

#### Acceptance Criteria

1. THE System SHALL provide a `docker-compose.yml` (or `Makefile` with a `make up` target) that starts the backend API, runs database migrations, and serves the frontend with a single command.
2. WHEN `docker compose up` (or `make up`) is executed on a clean clone, THE System SHALL reach a healthy state within 60 seconds with no manual intervention required.
3. THE System SHALL provide a root-level `.env.example` file containing every required and optional environment variable with descriptions and safe default values.
4. IF the `.env` file is absent at startup, THEN THE System SHALL print a clear error message listing the missing required variables and exit with a non-zero code.
5. THE System SHALL provide a `Makefile` with at minimum the targets: `up`, `down`, `migrate`, `test`, `lint`, and `build`.
6. WHEN the `make up` target completes, THE Health_Endpoint SHALL return HTTP 200 with `status: "healthy"`.

---

### Requirement 2: No Critical Runtime Errors on Startup

**User Story:** As a developer, I want the application to start cleanly without errors, so that I can trust the baseline before making changes.

#### Acceptance Criteria

1. WHEN the Backend starts with a valid `.env`, THE System SHALL complete startup without any unhandled exceptions or ERROR-level log entries.
2. WHEN the Backend starts, THE System SHALL run all pending Alembic migrations automatically before accepting requests.
3. WHEN the Health_Endpoint is called after startup, THE System SHALL return a response body containing `"status": "healthy"` and HTTP status 200.
4. IF a Migration fails during startup, THEN THE System SHALL log the migration error with full stack trace and exit with a non-zero code rather than starting in a broken state.
5. THE Backend SHALL expose a `/api/v1/health` endpoint that does not require authentication and returns database connectivity status, active Watcher count, and error count from the last 24 hours.

---

### Requirement 3: Lint, Typecheck, and Build Pass

**User Story:** As a developer, I want lint, typecheck, and build commands to pass cleanly, so that I can maintain code quality and catch errors before runtime.

#### Acceptance Criteria

1. THE System SHALL provide a `make lint` target that runs `ruff` (or `flake8`) on all Python source files and `eslint` on all TypeScript/TSX source files, exiting non-zero on any violation.
2. THE System SHALL provide a `make typecheck` target that runs `mypy` on the Backend and `tsc --noEmit` on the Frontend, exiting non-zero on any type error.
3. THE System SHALL provide a `make build` target that produces a production-ready Frontend bundle in `frontend/dist/` without errors or warnings.
4. WHEN `make lint` is executed on the repository, THE System SHALL produce zero lint errors (warnings are acceptable but must be documented).
5. WHEN `make typecheck` is executed, THE System SHALL produce zero type errors across Backend and Frontend.
6. WHEN `make build` is executed, THE System SHALL produce a complete Frontend bundle with no build errors.
7. THE System SHALL include a `make test` target that runs all unit, integration, and property-based tests and exits non-zero if any test fails.

---

### Requirement 4: Secrets Not Committed; Secure Defaults

**User Story:** As a security engineer, I want secrets to be absent from the repository and `.env.example` to be complete, so that no credentials are accidentally exposed.

#### Acceptance Criteria

1. THE System SHALL ensure that `.env`, `*.db`, `*.log`, `*.sqlite`, `*.sqlite3`, `htmlcov/`, `.hypothesis/`, and `__pycache__/` are listed in `.gitignore`.
2. THE System SHALL provide a root-level `.env.example` that documents every environment variable consumed by the Backend, with placeholder values and inline comments explaining each variable's purpose.
3. THE System SHALL NOT commit any file containing real credentials, API keys, passwords, or encryption keys to the repository.
4. WHEN `ENCRYPTION_KEY` or `SECRET_KEY` environment variables are absent or shorter than 32 characters, THE Backend SHALL refuse to start and log a descriptive error.
5. THE System SHALL provide a `scripts/generate_secrets.sh` (or equivalent `make generate-secrets` target) that generates cryptographically secure values for `ENCRYPTION_KEY` and `SECRET_KEY` and writes them to `.env`.
6. WHERE the application runs in production mode, THE Backend SHALL set `secure=True` and `httponly=True` on all session cookies.
7. THE System SHALL ensure that no PII (lead names, email addresses, phone numbers) appears in application log output at INFO level or above.

---

### Requirement 5: Consistent API Conventions, Validation, and Error Handling

**User Story:** As a frontend developer, I want all API endpoints to follow consistent conventions with proper validation and error responses, so that I can build reliable integrations.

#### Acceptance Criteria

1. THE Backend SHALL use a single unified error response schema `{"error": string, "message": string, "code": string, "details": object|null}` for all 4xx and 5xx responses across both `api/routes/` and `api/routers/`.
2. WHEN a request body fails Pydantic validation, THE Backend SHALL return HTTP 422 with the unified error schema listing each invalid field and reason.
3. WHEN a requested resource does not exist, THE Backend SHALL return HTTP 404 with the unified error schema.
4. WHEN an unauthenticated request reaches a protected endpoint, THE Backend SHALL return HTTP 401 with the unified error schema.
5. WHEN an authenticated user requests a resource belonging to a different Tenant, THE Backend SHALL return HTTP 403 with the unified error schema.
6. THE Backend SHALL apply input validation (type, length, format) to all request parameters and bodies using Pydantic models before reaching service or repository layers.
7. THE Backend SHALL use consistent HTTP method conventions: GET for reads, POST for creates, PUT/PATCH for updates, DELETE for deletes across all routers.
8. THE Backend SHALL consolidate the duplicate router structure (`api/routes/` and `api/routers/`) into a single consistent layout, or clearly document the separation with a naming convention that distinguishes platform-admin routes from agent-app routes.

---

### Requirement 6: Multi-Tenant Isolation

**User Story:** As a platform operator, I want tenant data to be strictly isolated, so that one agent cannot access another agent's leads, credentials, or settings.

#### Acceptance Criteria

1. THE Backend SHALL enforce that every database query for tenant-scoped resources (leads, credentials, settings, templates, watchers) includes a `tenant_id` or `agent_id` filter derived from the authenticated session, not from user-supplied request parameters.
2. WHEN an authenticated agent requests a lead that belongs to a different agent, THE Backend SHALL return HTTP 403 and SHALL NOT return any data from the other agent's record.
3. THE Backend SHALL enforce that Watcher start/stop operations can only be performed by the owning agent or a platform admin.
4. THE Backend SHALL enforce that credential read/write operations are scoped to the owning agent's session.
5. WHEN a platform admin queries the leads list, THE Backend SHALL return leads across all tenants with tenant identifiers included in the response.
6. THE System SHALL include at least one integration test per tenant-scoped resource type that verifies cross-tenant access returns HTTP 403.

---

### Requirement 7: Backend Architecture Standardization

**User Story:** As a backend developer, I want a clear, consistent layered architecture, so that I know where to add new features and can navigate the codebase quickly.

#### Acceptance Criteria

1. THE Backend SHALL organize code into four explicit layers: `api/routers/` (HTTP layer), `api/services/` (business logic), `api/repositories/` (data access), and `api/models/` (entities and schemas).
2. THE Backend SHALL ensure that Router modules contain no direct database queries; all database access SHALL go through Repository or Service modules.
3. THE Backend SHALL ensure that Service modules contain no FastAPI-specific imports (`Request`, `Response`, `Depends`); Services SHALL be framework-agnostic.
4. THE Backend SHALL provide a `api/dependencies/` module containing all reusable FastAPI `Depends` functions (authentication, database session, pagination).
5. THE Backend SHALL separate the Watcher/Worker module (`gmail_lead_sync/`) from the API layer with a clean interface; the API SHALL interact with the Watcher only through `WatcherRegistry`.
6. THE Backend SHALL remove or consolidate the duplicate `api/routes/agents.py` and any other route files that overlap with `api/routers/` equivalents.

---

### Requirement 8: Lead State Machine Consistency

**User Story:** As a product engineer, I want a single authoritative lead state machine, so that lead state transitions are predictable, logged, and idempotent.

#### Acceptance Criteria

1. THE System SHALL define all valid lead states (e.g., `NEW`, `INVITED`, `SUBMITTED`, `SCORED`, `HOT`, `WARM`, `NURTURE`, `CLOSED`) in a single `LeadState` enum in one canonical module.
2. THE System SHALL define all valid state transitions as a mapping in the Lead_State_Machine module; any transition not in the mapping SHALL be rejected.
3. WHEN a lead state transition is attempted, THE Lead_State_Machine SHALL validate the transition against the allowed mapping and raise a domain error if the transition is invalid.
4. WHEN a lead state transition succeeds, THE System SHALL write a `LeadStateEvent` record to the database containing: `lead_id`, `from_state`, `to_state`, `timestamp`, `triggered_by` (agent_id or "system"), and `reason`.
5. WHEN the Watcher processes an email that has already been processed (same message-id), THE Lead_State_Machine SHALL detect the duplicate and skip re-processing without changing lead state.
6. THE Lead_State_Machine SHALL be idempotent: applying the same transition twice SHALL result in the same final state as applying it once, with no duplicate `LeadStateEvent` records created.
7. THE System SHALL expose the lead event log via `GET /api/v1/agent/leads/{lead_id}/events` returning events in chronological order.

---

### Requirement 9: Frontend Restructure

**User Story:** As a frontend developer, I want the frontend source organized into clearly separated app directories with shared code centralized, so that I can navigate and extend either app without confusion.

#### Acceptance Criteria

1. THE Frontend SHALL organize source code into: `frontend/src/apps/agent/` (Agent_App), `frontend/src/apps/platform-admin/` (Platform_Admin), and `frontend/src/shared/` (shared UI components, API client, auth utilities, types, hooks).
2. THE Frontend SHALL move all files currently under `frontend/src/agent/` to `frontend/src/apps/agent/` and update all import paths accordingly.
3. THE Frontend SHALL move all files currently under `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/contexts/`, and `frontend/src/utils/` that are Platform_Admin-specific to `frontend/src/apps/platform-admin/`.
4. THE Frontend SHALL move all files that are used by both apps to `frontend/src/shared/`.
5. WHEN `make build` is executed after the restructure, THE Frontend build SHALL succeed with zero errors.
6. THE Frontend SHALL remove all Dead_Code files (unused components, unused hooks, unused utilities) identified during the restructure.
7. THE Frontend SHALL maintain a single `frontend/src/main.tsx` entry point that mounts both apps under their respective route prefixes (`/agent/*` and `/`).

---

### Requirement 10: Watcher/Worker Resilience

**User Story:** As a platform operator, I want the email watcher to be resilient to transient failures, so that lead ingestion continues reliably in production.

#### Acceptance Criteria

1. WHEN an IMAP connection fails, THE Watcher SHALL retry with exponential backoff starting at 5 seconds, doubling up to a maximum of 300 seconds, for up to 5 consecutive attempts before marking the Watcher as `failed`.
2. WHEN a Watcher is marked `failed`, THE Watcher_Registry SHALL log the failure with agent_id, error type, error message, and timestamp at ERROR level.
3. WHERE `ENABLE_AUTO_RESTART` is set to `true`, THE Watcher_Registry SHALL automatically restart a `failed` Watcher after a 60-second cooldown period.
4. THE Watcher SHALL record a `message_id` hash for every processed email and SHALL skip processing if the same `message_id` has already been processed (idempotency).
5. WHEN the Watcher processes an email, THE Watcher SHALL complete processing within 30 seconds or log a WARNING and continue to the next email.
6. THE Watcher SHALL emit a heartbeat log entry at DEBUG level every polling cycle, and the Health_Endpoint SHALL reflect the last heartbeat timestamp per agent.
7. IF an unhandled exception occurs inside the Watcher polling loop, THEN THE Watcher SHALL catch the exception, log it at ERROR level with full stack trace, and continue the polling loop rather than crashing.

---

### Requirement 11: Security Hardening

**User Story:** As a security engineer, I want the application to follow security best practices, so that it is safe to deploy in a production environment.

#### Acceptance Criteria

1. THE Backend SHALL store all Gmail App Passwords and IMAP credentials encrypted at rest using the `CredentialEncryption` service; plaintext credentials SHALL NOT be stored in the database.
2. THE Backend SHALL enforce RBAC on all platform-admin endpoints, returning HTTP 403 for requests from agent-role sessions.
3. THE Backend SHALL enforce RBAC on all agent-app endpoints, returning HTTP 403 for requests from platform-admin sessions attempting to act as agents (except explicit admin-override endpoints).
4. THE Backend SHALL sanitize all user-supplied string inputs before storing them to prevent stored XSS; HTML tags SHALL be stripped from lead name, email, and notes fields.
5. THE Backend SHALL set the following HTTP security headers on all responses: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
6. THE Backend SHALL rate-limit the `POST /api/v1/auth/login` and `POST /api/v1/agent/auth/login` endpoints to a maximum of 10 requests per minute per IP address, returning HTTP 429 on excess requests.
7. THE Backend SHALL validate that regex patterns submitted to lead source configuration cannot cause catastrophic backtracking by enforcing a configurable execution timeout (`REGEX_TIMEOUT_MS`).
8. THE Backend SHALL log all authentication failures (wrong password, expired session, invalid token) at WARNING level including the username attempted and source IP, but SHALL NOT log the attempted password.

---

### Requirement 12: Developer Experience and Documentation

**User Story:** As a new developer, I want complete documentation and a reliable setup process, so that I can run the project locally in under 15 minutes.

#### Acceptance Criteria

1. THE System SHALL provide a root-level `README.md` with: project overview, prerequisites (Python version, Node version, Docker), quick-start steps using One_Command_Startup, environment variable reference, and links to further documentation.
2. THE System SHALL provide a `docs/ARCHITECTURE.md` describing the backend layer structure, frontend app structure, database schema overview, and watcher/worker flow.
3. THE System SHALL provide a `CONTRIBUTING.md` describing how to run tests, how to add a new API endpoint, how to add a new frontend page, and the branching/PR process.
4. THE System SHALL provide a `SECURITY.md` describing the secrets management approach, credential encryption, session security, and how to report vulnerabilities.
5. THE System SHALL provide a root-level `.env.example` (distinct from `api/.env.example`) that is the single source of truth for all environment variables.
6. WHEN a new developer follows the README quick-start steps on a clean clone, THE System SHALL be fully operational within 15 minutes without requiring assistance.
7. THE System SHALL document all known test gaps in a `docs/TESTING_GAPS.md` file listing untested modules and the rationale for each gap.

---

### Requirement 13: Clean Clone Validation

**User Story:** As a release engineer, I want the clean-clone startup to be verified and documented, so that I can trust the one-command startup works on any machine.

#### Acceptance Criteria

1. THE System SHALL include a `scripts/validate_clean_clone.sh` script that: clones the repo to a temp directory, copies `.env.example` to `.env` with generated secrets, runs `docker compose up -d`, waits for the Health_Endpoint to return healthy, and reports pass/fail.
2. WHEN `scripts/validate_clean_clone.sh` is executed, THE System SHALL complete the validation within 120 seconds on a machine with Docker installed.
3. THE System SHALL document the clean-clone validation result in `docs/CLEAN_CLONE_VALIDATION.md` including the date, environment, and any known issues.
4. IF the clean-clone validation fails, THEN THE System SHALL log the specific step that failed and the error message to stdout.

---

### Requirement 14: CI/CD Baseline

**User Story:** As a team lead, I want a basic CI pipeline that runs on every push, so that regressions are caught automatically.

#### Acceptance Criteria

1. THE System SHALL provide a `.github/workflows/ci.yml` (or equivalent) that triggers on every push and pull request to the main branch.
2. WHEN the CI_Pipeline runs, THE System SHALL execute: dependency installation, `make lint`, `make typecheck`, and `make test` in sequence, failing the pipeline if any step exits non-zero.
3. THE CI_Pipeline SHALL cache Python and Node dependencies between runs to complete within 5 minutes on a standard GitHub Actions runner.
4. WHERE a Docker build step is included in CI, THE System SHALL build the Docker image and verify it starts successfully before marking the pipeline as passed.
5. THE System SHALL provide a CI status badge in `README.md` linking to the CI_Pipeline results.

---

### Requirement 15: Dead Code and File Cleanup

**User Story:** As a developer, I want the repository to contain only relevant, used code and files, so that I can navigate it without confusion.

#### Acceptance Criteria

1. THE System SHALL remove all root-level test artifact files (`test_connection.py`, `test_watcher_simple.py`, `test_template_body.txt`, `test_template_body_updated.txt`, `test_template.txt`, `sample_test_email.txt`, `gmail_lead_sync.db`, `gmail_lead_sync.log`) from the repository.
2. THE System SHALL remove or consolidate duplicate documentation files (`API_DOCUMENTATION.md`, `API_USAGE_GUIDE.md`, `BACKEND_API_REVIEW.md`, `BACKEND_COMPLETION_SUMMARY.md`, `FRONTEND_IMPLEMENTATION_PLAN.md`, `TESTING_GUIDE.md`, `TESTING_SUMMARY.md`) into the `docs/` directory or remove them if superseded.
3. THE System SHALL remove the `htmlcov/` directory from version control and add it to `.gitignore`.
4. THE System SHALL remove the `deployment/gmail-lead-sync.service` systemd unit file if Docker Compose is the canonical deployment method, or move it to `docs/deployment/` with documentation.
5. THE Backend SHALL remove all unused imports, unused variables, and unreachable code paths identified by the linter.
6. THE Frontend SHALL remove all unused component files, unused hook files, and unused utility files identified during the restructure.
7. THE System SHALL add `frontend/dist/` to `.gitignore` to prevent built assets from being committed.

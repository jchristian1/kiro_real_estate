# Architecture

## System Topology

The default supported runtime consists of four processes. In Docker Compose all four
start together with `docker compose up --build`. In bare local dev each runs in a
separate terminal.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Compose                              │
│                                                                     │
│  ┌──────────────────┐        ┌──────────────────────────────────┐  │
│  │  frontend        │        │  api                             │  │
│  │  React/nginx     │──────▶ │  FastAPI  :8000                  │  │
│  │  :80             │        │  HTTP requests only              │  │
│  └──────────────────┘        └──────────────┬───────────────────┘  │
│                                             │                       │
│                               ┌─────────────▼───────────────────┐  │
│                               │  postgres                        │  │
│                               │  PostgreSQL :5432                │  │
│                               └─────────────┬───────────────────┘  │
│                                             │                       │
│                               ┌─────────────▼───────────────────┐  │
│                               │  worker                          │  │
│                               │  Python background process       │  │
│                               │  owns WatcherRegistry            │  │
│                               │  polls watcher_control every 10s │  │
│                               │  writes watcher_status every 10s │  │
│                               └──────────────────────────────────┘  │
│                                             │                       │
│                                             ▼                       │
│                                        Gmail IMAP                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Process responsibilities

| Process | Owns | Does NOT own |
|---------|------|--------------|
| `api` | HTTP request handling, session auth, DB reads/writes for all API routes | Watcher lifecycle |
| `worker` | WatcherRegistry, all watcher start/stop/restart, reconciliation loop | HTTP serving |
| `frontend` | Static React build served by nginx | Any backend logic |
| `postgres` | Persistent data store | — |

### Watcher ownership

The **worker process owns all watcher lifecycle**. Evidence from code:

- `worker/main.py` docstring: "This process owns the WatcherRegistry and all watcher lifecycle."
- `worker/main.py` `run()`: creates `WatcherRegistry`, calls `_auto_start_watchers()`, runs `_reconciliation_loop()` every 10 seconds.
- `api/main.py` `startup_event()`: "Watcher auto-start is now the worker process's responsibility. The API process no longer owns watcher lifecycle."

The API coordinates with the worker through two DB tables:

- `watcher_control` — API writes desired state (`running` / `stopped`); worker reads and reconciles
- `watcher_status` — worker writes live status every ~10 seconds; API reads for health/status endpoints

There is no direct in-process communication between the API and the worker.

### Database

PostgreSQL is the default and required database for the full stack (api + worker).
SQLite is supported only when explicitly configured via `DATABASE_URL=sqlite:///...`
and only for running the API process alone without the worker. Both `api/main.py`
and `worker/main.py` log a `WARNING` at startup when SQLite is detected.

---

## Backend 4-Layer Structure

```
api/
├── routers/          # HTTP layer — FastAPI routes only, no business logic
│   ├── admin_*.py    # Platform-admin endpoints (require platform_admin role)
│   ├── agent_*.py    # Agent-app endpoints (require agent role)
│   └── public_*.py   # Unauthenticated public endpoints
│
├── services/         # Business logic — framework-agnostic Python
│   ├── watcher_registry.py
│   ├── lead_state_machine.py
│   ├── credential_encryption.py
│   └── ...
│
├── repositories/     # Data access — all SQLAlchemy queries live here
│   ├── lead_repository.py
│   ├── credential_repository.py
│   ├── agent_repository.py
│   └── ...
│
├── models/           # Entities and Pydantic schemas
│   ├── lead_models.py
│   ├── error_models.py
│   └── ...
│
└── dependencies/     # Reusable FastAPI Depends functions
    ├── auth.py       # get_current_agent, get_current_admin, require_role()
    ├── db.py         # get_db session generator
    └── pagination.py # get_pagination()
```

**Rules enforced by this structure:**

- Routers contain no direct database queries — all DB access goes through repositories or services.
- Services contain no FastAPI-specific imports (`Request`, `Response`, `Depends`).
- Repositories always include a `tenant_id` / `agent_id` filter — never trust user-supplied IDs alone.
- The API interacts with the watcher runtime only through the `watcher_control` and `watcher_status` DB tables.

### Request Flow

```
HTTP Request
    │
    ▼
api/routers/          ← validates input with Pydantic, calls service
    │
    ▼
api/services/         ← business logic, orchestrates repositories
    │
    ▼
api/repositories/     ← SQLAlchemy queries, always tenant-scoped
    │
    ▼
PostgreSQL Database
```

---

## Frontend App Structure

```
frontend/src/
├── apps/
│   ├── agent/                  # Agent-facing app
│   │   ├── api/                # Agent API client calls
│   │   ├── components/         # Agent-specific UI components
│   │   ├── contexts/           # Agent auth context
│   │   ├── hooks/              # Agent-specific hooks
│   │   └── pages/              # Agent pages (dashboard, leads, settings…)
│   │
│   └── platform-admin/         # Platform operator admin panel
│       ├── components/         # Admin-specific UI components
│       ├── contexts/           # Admin auth context
│       └── pages/              # Admin pages (agents, leads, templates…)
│
├── shared/                     # Code used by both apps
│   ├── api/
│   │   └── client.ts           # Base HTTP client (fetch wrapper)
│   ├── contexts/
│   │   ├── ThemeContext.tsx
│   │   └── ToastContext.tsx
│   ├── hooks/
│   │   └── useT.ts
│   └── utils/
│       └── theme.ts
│
├── main.tsx                    # Single entry point — mounts both apps
└── index.css
```

`main.tsx` mounts the platform-admin app at `/` and the agent app at `/agent/*`.

### Frontend serving

In Docker Compose the `frontend` service builds a static React bundle and serves it
via nginx on port 80. The API runs separately on port 8000.

In bare local dev `npm run dev` serves the frontend on port 5173 (cross-origin to
the API on port 8000 — handled by CORS config).

`api/main.py` also contains a static-file fallback route that serves `index.html`
from `STATIC_FILES_DIR` if that directory exists. This path is inactive in the
compose setup (the directory is empty) and exists for single-binary deployments
where the frontend build is co-located with the API.

---

## Database Schema Overview

### Core Tables (gmail_lead_sync/models.py)

**`leads`** — extracted lead records
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `name` | VARCHAR(255) | HTML-stripped on write |
| `phone` | VARCHAR(50) | |
| `source_email` | VARCHAR(255) | sender address |
| `lead_source_id` | INTEGER FK | → lead_sources |
| `gmail_uid` | VARCHAR(255) UNIQUE | original Gmail UID |
| `agent_id` | VARCHAR(255) | tenant scoping for watcher layer |
| `created_at` | DATETIME | |
| `response_sent` | BOOLEAN | |

**`lead_sources`** — regex parsing rules per sender
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `sender_email` | VARCHAR(255) UNIQUE | |
| `identifier_snippet` | VARCHAR(500) | must appear in email body |
| `name_regex` | VARCHAR(500) | capture group required |
| `phone_regex` | VARCHAR(500) | capture group required |
| `template_id` | INTEGER FK | → templates (nullable) |
| `auto_respond_enabled` | BOOLEAN | |

**`credentials`** — encrypted Gmail credentials
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `agent_id` | VARCHAR(255) UNIQUE | tenant key |
| `email_encrypted` | TEXT | Fernet-encrypted |
| `app_password_encrypted` | TEXT | Fernet-encrypted |
| `company_id` | INTEGER FK | → companies (nullable) |

**`processed_messages`** — watcher idempotency tracking
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `agent_id` | VARCHAR(255) | |
| `message_id_hash` | VARCHAR(64) | SHA-256 of Message-ID header |
| `processed_at` | DATETIME | |
| `lead_id` | INTEGER FK | → leads (nullable) |
| UNIQUE | `(agent_id, message_id_hash)` | prevents duplicate processing |

**`templates`** — email response templates
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `name` | VARCHAR(255) | |
| `subject` | VARCHAR(500) | |
| `body` | TEXT | supports `{lead_name}`, `{agent_name}`, etc. |

### Web UI Tables (api/models/web_ui_models.py)

**`users`** — platform admin and agent users
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `username` | VARCHAR(255) UNIQUE | |
| `password_hash` | VARCHAR(255) | bcrypt |
| `role` | VARCHAR(50) | `platform_admin` or `agent` |
| `company_id` | INTEGER FK | → companies (nullable) |

**`sessions`** — active user sessions
| Column | Type | Notes |
|--------|------|-------|
| `id` | VARCHAR(128) PK | HMAC-SHA256 digest of raw token |
| `user_id` | INTEGER FK | → users |
| `expires_at` | DATETIME | |

**`audit_logs`** — immutable admin action log
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `timestamp` | DATETIME | |
| `user_id` | INTEGER FK | → users |
| `action` | VARCHAR(100) | |
| `resource_type` | VARCHAR(50) | |
| `resource_id` | INTEGER | nullable |

### Watcher Coordination Tables (api/models/watcher_state_models.py)

**`watcher_control`** — desired state written by API, read by worker
| Column | Type | Notes |
|--------|------|-------|
| `agent_id` | VARCHAR PK | |
| `desired_status` | VARCHAR | `running` or `stopped` |
| `sync_requested_at` | DATETIME | nullable; worker clears after acting |
| `updated_at` | DATETIME | |

**`watcher_status`** — live state written by worker, read by API
| Column | Type | Notes |
|--------|------|-------|
| `agent_id` | VARCHAR PK | |
| `status` | VARCHAR | `running`, `stopped`, `failed`, `starting` |
| `last_heartbeat` | DATETIME | updated every ~10s by worker |
| `last_sync` | DATETIME | |
| `started_at` | DATETIME | |
| `error` | TEXT | nullable |

---

## Watcher / Worker Flow

### State Machine

```
[*] ──start_watcher()──▶ STARTING
                              │
              IMAP connect OK │  connect error
                              ▼         ▼
                          RUNNING    FAILED ◀──────────────────┐
                              │                                 │
              poll cycle OK   │  unhandled exception           │
                              ▼         ▼                       │
                          RUNNING    FAILED                     │
                              │                                 │
         stop_watcher() /     │                                 │
              shutdown        ▼                                 │
                          STOPPED    auto-restart (60s cooldown, max 5 attempts)
```

### Reconciliation Loop (worker/main.py)

The worker runs `_reconciliation_loop()` every 10 seconds:

1. Read all `watcher_control` rows.
2. For each row: start or stop the watcher to match `desired_status`.
3. Act on any pending `sync_requested_at` values; clear them after acting.
4. Write current in-memory watcher status back to `watcher_status` table.

### Polling Loop (WatcherRegistry._run_watcher)

1. Create a `GmailWatcher` instance with the agent's decrypted credentials.
2. Connect to Gmail IMAP (SSL :993).
3. On successful connection, set status → `RUNNING`, reset retry count.
4. Enter the main loop:
   - Update `last_heartbeat` timestamp.
   - Refresh lead sources from DB.
   - Call `watcher.process_unseen_emails()` wrapped in `asyncio.wait_for(timeout=30)`.
   - Sleep `SYNC_INTERVAL_SECONDS` (or wake early on manual sync trigger).
5. On `CancelledError` (graceful stop): set status → `STOPPED`.
6. On unrecoverable exception: set status → `FAILED`.
7. If `ENABLE_AUTO_RESTART=true`: schedule `_auto_restart_watcher(delay=60)`.

### Exponential Backoff

On IMAP connection failure the retry delay follows `min(5 × 2^(attempt−1), 300)` seconds:

| Attempt | Delay |
|---------|-------|
| 1 | 5s |
| 2 | 10s |
| 3 | 20s |
| 4 | 40s |
| 5 | 80s |

After 5 consecutive failures the watcher transitions to `FAILED`.

### Idempotency

Every processed email's `Message-ID` header is SHA-256 hashed and stored in
`processed_messages(agent_id, message_id_hash)` with a unique constraint. Before
processing, `GmailWatcher.is_email_processed()` checks this table. Duplicate emails
are silently skipped.

---

## Observability

### Health Endpoint

`GET /api/v1/health` (no auth required) reads from the `watcher_status` DB table
(written by the worker) and the `audit_logs` table:

```json
{
  "status": "healthy",
  "database": "connected",
  "db_dialect": "postgresql",
  "active_watchers": 2,
  "errors_last_24h": 0,
  "watchers": {
    "agent_42": {
      "status": "running",
      "last_heartbeat": "2024-01-15T10:30:00Z"
    }
  }
}
```

Returns HTTP 200 when healthy or degraded-but-reachable, HTTP 503 when the database
is unreachable. The `active_watchers` count and per-agent status are eventually
consistent — the worker updates `watcher_status` every ~10 seconds.

### Watcher Status Endpoint

`GET /api/v1/watchers/status` (auth required) reads the same `watcher_status` table
and returns per-agent status, heartbeats, last sync, and error details.

### Prometheus Metrics

`GET /metrics` (no auth required) exposes:

- `api_requests_total` — request count per endpoint/method/status (API process)
- `api_request_duration_seconds` — request duration histogram (API process)
- `api_errors_total` — error count per endpoint/status (API process)
- `watchers_active` — count of running watchers, read from `watcher_status` DB at scrape time (eventually consistent)

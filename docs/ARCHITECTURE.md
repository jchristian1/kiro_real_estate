# Architecture

## System Topology

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                         │
│                                                             │
│  ┌──────────────────┐        ┌──────────────────────────┐  │
│  │  Frontend        │        │  FastAPI Backend          │  │
│  │  React/Vite      │──────▶ │  :8000                   │  │
│  │  :80 (nginx)     │        │                          │  │
│  └──────────────────┘        └──────────┬───────────────┘  │
│                                         │                   │
│                               ┌─────────▼──────────┐       │
│                               │  SQLite Database   │       │
│                               │  gmail_lead_sync.db│       │
│                               └────────────────────┘       │
│                                         │                   │
│                               ┌─────────▼──────────┐       │
│                               │  Gmail Watcher     │       │
│                               │  asyncio tasks     │──────▶ Gmail IMAP
│                               └────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

The Gmail watcher runs as asyncio background tasks **inside** the FastAPI process, managed by `WatcherRegistry`. There is no separate container for the watcher.

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
- The API interacts with the Gmail watcher only through `WatcherRegistry`.

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
SQLite Database
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

**`processing_logs`** — email processing audit trail
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `gmail_uid` | VARCHAR(255) | |
| `sender_email` | VARCHAR(255) | |
| `status` | VARCHAR(50) | `success`, `failed`, `validation_failed`, … |
| `error_details` | TEXT | nullable |
| `lead_id` | INTEGER FK | → leads (nullable) |

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
| `id` | VARCHAR(64) PK | secure random token |
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

**`lead_state_transitions`** — lead state event log (gmail_lead_sync/preapproval)
| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `tenant_id` | INTEGER | |
| `lead_id` | INTEGER FK | → leads |
| `from_state` | VARCHAR | |
| `to_state` | VARCHAR | |
| `occurred_at` | DATETIME | |
| `actor_type` | VARCHAR | `agent` or `system` |
| `actor_id` | VARCHAR | |

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

### Polling Loop (WatcherRegistry._run_watcher)

1. Create a `GmailWatcher` instance with the agent's decrypted credentials.
2. Connect to Gmail IMAP (SSL :993).
3. On successful connection, set status → `RUNNING`, reset retry count.
4. Enter the main loop:
   - Update `last_heartbeat` timestamp; emit `DEBUG` log entry.
   - Refresh lead sources from DB.
   - Call `watcher.process_unseen_emails()` wrapped in `asyncio.wait_for(timeout=30)`.
   - On `TimeoutError`: log `WARNING`, continue to next cycle.
   - On any other exception: log `ERROR` with `agent_id`, `error_type`, full stack trace; sleep 60s; continue loop.
   - Sleep `SYNC_INTERVAL_SECONDS` (or wake early on manual sync trigger).
5. On `CancelledError` (graceful stop): set status → `STOPPED`.
6. On unrecoverable exception (e.g., IMAP auth failure): set status → `FAILED`; log `ERROR` with timestamp.
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

Every processed email's `Message-ID` header is SHA-256 hashed and stored in `processed_messages(agent_id, message_id_hash)` with a unique constraint. Before processing, `GmailWatcher.is_email_processed()` checks this table. Duplicate emails are silently skipped with no new `Lead` or `ProcessedMessage` rows created.

### Health Endpoint

`GET /api/v1/health` (no auth required) reads live data from `WatcherRegistry` and the database:

```json
{
  "status": "healthy",
  "database": "connected",
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

Returns HTTP 200 when healthy, HTTP 503 when the database is unreachable.

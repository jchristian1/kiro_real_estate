# Lead Intake & Workflow Platform

A multi-tenant SaaS platform for service businesses — real estate agencies, law firms, accounting practices, and similar teams — that monitors Gmail accounts via IMAP, extracts and qualifies leads, manages automated responses, and provides a full-featured admin panel — deployable with a single command.

---

## What it does

When a lead email arrives in a connected Gmail inbox, the system automatically:

1. Detects the email using configurable sender + keyword rules
2. Extracts the lead's name and phone number using regex patterns
3. Sends a personalized response email using a pre-built template
4. Records the lead in the database with full audit trail
5. (Optional) Sends the lead a qualification form link and scores their responses

Everything is managed through two separate web interfaces — one for platform operators and one for agents.

---

## Features

### Platform Admin Panel (`/admin`)

**Dashboard**
- Live system health status
- Active watcher count and per-agent status
- Error count over the last 24 hours
- Quick-access links to all management sections

**Agent Management**
- Create, update, and delete agents
- Store Gmail credentials encrypted at rest (Fernet AES-128)
- Start, stop, and manually trigger Gmail watchers per agent
- View watcher status (running / stopped / failed) with last heartbeat

**Lead Management**
- Paginated lead list with filters by agent, date range, and response status
- Lead detail view with full processing history
- CSV export with the same filters as the list view

**Lead Sources**
- Define parsing rules per Gmail sender address
- Configure identifier snippet, name regex, and phone regex
- Live regex tester — paste sample email text and see what gets extracted
- Version history with one-click rollback

**Email Templates**
- Create and manage response email templates
- Supported placeholders: `{lead_name}`, `{agent_name}`, `{agent_phone}`, `{agent_email}`
- Live preview with sample data
- Version history with one-click rollback

**Buyer Lead Qualification** (law firm / buyer intake)
- Form builder — create multi-question intake forms with single-choice questions and custom options
- Form versioning — publish new versions without breaking existing links
- Scoring engine — configure point-based rules per answer, set HOT/WARM/NURTURE thresholds
- Email templates — configure the invite email (with form link) and post-submission email per bucket (HOT/WARM/NURTURE)
- Lead state tracking — view each lead's progression through qualification states
- Simulation tab — test scoring rules against sample answers before going live
- Audit log — full history of all form and scoring changes

**Company Management**
- Create and manage companies (tenants)
- Assign an active qualification form version per company

**Settings**
- Configure sync interval, regex timeout, session timeout, max leads per page, auto-restart behavior

**Audit Logs**
- Immutable log of all admin actions with timestamp, user, action type, and affected resource

---

### Agent App (`/agent`)

**Onboarding Wizard** (7-step guided setup)
1. Create account
2. Set up profile (name, phone, display info)
3. Connect Gmail (email + app password)
4. Configure lead sources
5. Set up automation preferences
6. Configure email templates
7. Go live — start the watcher

**Dashboard**
- Summary of recent leads
- Watcher status indicator
- Quick stats (leads today, response rate)

**Leads**
- Paginated lead list with search and filters
- Lead detail page with full timeline of events
- Manual response trigger

**Reports**
- Lead volume over time
- Response rate metrics
- Source breakdown

**Settings**
- Account settings (profile, password)
- Automation settings (watcher on/off, sync interval)
- Lead source management
- Template management

---

### Public Qualification Form (`/qualify/{token}`)

- Token-based public URL sent to leads via email
- Renders the active form version for the company
- Collects answers and submits to the backend
- Triggers automatic scoring and sends a bucket-appropriate follow-up email
- Shows a "we'll be in touch" confirmation — no score or internal data exposed

---

### Backend & Infrastructure

**Runtime Architecture**
- Three separate processes: API server, background worker, and frontend
- API handles all HTTP requests; worker owns all background Gmail watching and pipeline execution
- Worker polls a `watcher_control` DB table every 10 seconds to start/stop watchers — no direct API↔worker coupling
- Both API and worker connect to the same PostgreSQL database

**Gmail IMAP Watcher**
- Per-agent asyncio background task running inside the worker process
- Polls Gmail IMAP on a configurable interval (default 5 minutes)
- Idempotency via SHA-256 hash of `Message-ID` header — duplicate emails are silently skipped
- Exponential backoff on connection failures (5s → 10s → 20s → 40s → 80s, max 5 attempts)
- Auto-restart after failure with 60-second cooldown (configurable via `ENABLE_AUTO_RESTART`)
- Graceful shutdown — all watchers stop cleanly on worker exit

**Security**
- Gmail credentials encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256)
- Session tokens stored as secure HTTP-only cookies
- bcrypt password hashing
- Rate limiting on all auth endpoints (slowapi)
- Security headers on all responses (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)
- Input sanitization — HTML stripped from all user-supplied fields
- Regex timeout protection — patterns that run longer than `REGEX_TIMEOUT_MS` are rejected

**Observability**
- Structured JSON logging on all requests and background tasks
- Prometheus metrics endpoint (`/metrics`) — request count, duration, error count, active watcher count (DB-backed)
- Health endpoint (`/api/v1/health`) — database connectivity, active watcher count, per-agent watcher status, 24h error count
- Watcher status endpoint (`/api/v1/watchers/status`) — per-agent watcher status, heartbeats, last sync

**Database**
- PostgreSQL is the default and required database for any multi-process deployment (api + worker)
- SQLite is supported only for single-process bare local dev — not safe when the worker runs alongside the API
- Alembic migrations work against both — set `DATABASE_URL` before running `alembic upgrade head`
- `psycopg2-binary` is included in `requirements.txt`; no extra install needed
- Migrations run automatically on startup via the Docker entrypoint

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Database | PostgreSQL (default runtime), SQLite (single-process local dev only) |
| Auth | Session cookies, bcrypt, Fernet encryption |
| Monitoring | Prometheus, structured JSON logs |
| Deployment | Docker, Docker Compose, nginx |

> Vertical-specific pipeline templates (Real Estate Buyer Pipeline, Law Firm Pipeline) are included as optional specializations. The core platform is vertical-agnostic.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/jchristian1/kiro_real_estate.git
cd kiro_real_estate

# 2. Create virtualenv and install dependencies (includes test tools)
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# 3. Create Postgres database
createdb kiro
createdb kiro_test   # for the Postgres test suite

# 4. Copy env — DATABASE_URL defaults to the compose Postgres URL.
#    For bare local dev (no Docker), change it to: postgresql://localhost/kiro
cp .env.example .env

# 5. Run migrations
.venv/bin/alembic upgrade head

# 6. Install frontend deps
npm install --prefix frontend
```

Then open **three terminals**:

```bash
# Terminal 1 — API
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Worker (Gmail watchers + pipeline execution)
.venv/bin/python -m worker.main

# Terminal 3 — Frontend
cd frontend && npm run dev
```

Frontend: http://localhost:5173 — API: http://localhost:8000

For Docker or Windows setup see [docs/FIRST_START.md](docs/FIRST_START.md).

---

## First Login

The app starts with an empty database. To create a dev admin account, run the seed command:

```bash
export DEV_ADMIN_PASSWORD='your-secure-password'
make seed-dev
```

Then log in at http://localhost:5173/admin with username `admin` and the password you set.

> Seeding only runs when `ENVIRONMENT=development` and `DEV_SEED=true` are both set.
> `make seed-dev` sets both automatically.

---

## Project Structure

```
├── api/                    # FastAPI backend (routers, services, repositories, models)
├── gmail_lead_sync/        # Gmail IMAP watcher + preapproval qualification engine
├── frontend/               # React/TypeScript frontend (platform-admin + agent apps)
├── migrations/             # Alembic database migrations
├── scripts/                # Seed data and utility scripts
├── docs/                   # Architecture, API reference, first-start guide
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/FIRST_START.md](docs/FIRST_START.md) | Step-by-step setup for macOS, Linux, and Windows |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System topology, backend layers, DB schema, watcher flow |
| [docs/API.md](docs/API.md) | API endpoint reference with request/response examples |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to run tests, add endpoints, branching process |
| [SECURITY.md](SECURITY.md) | Secrets management, credential encryption, vulnerability reporting |

---

## Makefile Targets

```bash
make up               # Build and start all services with Postgres (Docker)
make down             # Stop all services
make migrate          # Run pending Alembic migrations (uses DATABASE_URL)
make migrate-postgres # Run migrations against Postgres (DATABASE_URL must be set)
make seed-dev         # Seed dev data (requires ENVIRONMENT=development + DEV_ADMIN_PASSWORD)
make test             # Run unit test suite (SQLite in-memory, fast, no Postgres required)
make test-postgres    # Run Postgres-backed tests (requires POSTGRES_TEST_URL)
make lint             # Lint Python (ruff) and TypeScript (eslint)
make typecheck        # Type-check Python (mypy) and TypeScript (tsc)
make build            # Build the production frontend bundle
make generate-secrets # Generate ENCRYPTION_KEY and SECRET_KEY in .env
```

# Real Estate Lead Management SaaS

A multi-tenant SaaS platform for real estate agents and law firms that monitors Gmail accounts via IMAP, extracts and qualifies leads, manages automated responses, and provides a full-featured admin panel — deployable with a single command.

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

**Gmail IMAP Watcher**
- Per-agent asyncio background task running inside the FastAPI process
- Polls Gmail IMAP on a configurable interval (default 5 minutes)
- Idempotency via SHA-256 hash of `Message-ID` header — duplicate emails are silently skipped
- Exponential backoff on connection failures (5s → 10s → 20s → 40s → 80s, max 5 attempts)
- Auto-restart after failure with 60-second cooldown (configurable)
- Graceful shutdown — all watchers stop cleanly on app exit

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
- Prometheus metrics endpoint (`/metrics`) — request count, duration, error count, active watchers, leads processed
- Health endpoint (`/api/v1/health`) — database connectivity, active watcher count, 24h error count

**Database**
- SQLite with Alembic migrations
- Migrations run automatically on startup
- Seed data runs automatically on first boot (idempotent)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Database | SQLite |
| Auth | Session cookies, bcrypt, Fernet encryption |
| Monitoring | Prometheus, structured JSON logs |
| Deployment | Docker, Docker Compose, nginx |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/jchristian1/kiro_real_estate.git
cd kiro_real_estate
git checkout final-user-ui

# 2. Copy env and generate secrets
cp .env.example .env
# Fill in ENCRYPTION_KEY and SECRET_KEY in .env (see docs/FIRST_START.md)

# 3. Start everything
docker compose up --build
```

Frontend: http://localhost:80 — API: http://localhost:8000

For local development (without Docker) see [docs/FIRST_START.md](docs/FIRST_START.md) — covers macOS, Linux, and Windows.

---

## Default Login

| Role | Username | Password | URL |
|------|----------|----------|-----|
| Platform Admin | `admin` | `admin123` | http://localhost:5173/admin |
| Agent | sign up via UI | — | http://localhost:5173/agent |

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
make up               # Build and start all services (Docker)
make down             # Stop all services
make migrate          # Run pending Alembic migrations
make test             # Run SQLite-backed test suite (fast, no Postgres required)
make test-postgres    # Run Postgres-backed tests (requires POSTGRES_TEST_URL)
make lint             # Lint Python (ruff) and TypeScript (eslint)
make typecheck        # Type-check Python (mypy) and TypeScript (tsc)
make build            # Build the production frontend bundle
make generate-secrets # Generate ENCRYPTION_KEY and SECRET_KEY in .env
```

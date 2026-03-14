# Real Estate Lead Management SaaS

[![CI](https://github.com/your-org/your-repo/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/your-repo/actions/workflows/ci.yml)

A multi-tenant SaaS platform for real estate agents that monitors Gmail accounts via IMAP, extracts and scores leads, manages automated responses, and provides a full-featured admin panel — all deployable with a single command.

## Overview

The system consists of:

- **FastAPI backend** (`api/`) — platform-admin and agent-app REST API with 4-layer architecture
- **Gmail IMAP watcher** (`gmail_lead_sync/`) — per-agent background worker that ingests leads from Gmail
- **React/TypeScript frontend** (`frontend/src/`) — platform-admin panel and agent-facing app
- **SQLite + Alembic** — database with automatic migrations on startup
- **Docker Compose** — single-command containerized deployment

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.11+ |
| Node.js | 18+ |
| Docker | 24+ |
| Docker Compose | v2 (bundled with Docker Desktop) |

## Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd <repo-directory>

# 2. Copy the example env file and generate secrets
cp .env.example .env
make generate-secrets

# 3. Start all services (API + frontend + migrations)
make up

# 4. Verify the system is healthy
curl http://localhost:8000/api/v1/health
```

The health endpoint returns `{"status": "healthy", ...}` when everything is running. The frontend is served at `http://localhost:80` (production) or `http://localhost:5173` (dev).

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make up` | Build images and start all services in the background |
| `make down` | Stop and remove all containers |
| `make migrate` | Run pending Alembic database migrations |
| `make test` | Run the full test suite (unit + integration + property) |
| `make lint` | Run `ruff` (Python) and `eslint` (TypeScript) |
| `make typecheck` | Run `mypy` (Python) and `tsc --noEmit` (TypeScript) |
| `make build` | Build the production frontend bundle |
| `make generate-secrets` | Generate secure `ENCRYPTION_KEY` and `SECRET_KEY` in `.env` |

## Environment Variables

Copy `.env.example` to `.env` and fill in the values. Run `make generate-secrets` to auto-generate the required secret keys.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | yes | — | SQLite path, e.g. `sqlite:///./gmail_lead_sync.db` |
| `ENCRYPTION_KEY` | yes | — | Fernet key ≥ 32 chars for credential encryption at rest |
| `SECRET_KEY` | yes | — | Session signing key ≥ 32 chars |
| `API_HOST` | no | `0.0.0.0` | Host address the API server binds to |
| `API_PORT` | no | `8000` | Port the API server listens on |
| `CORS_ORIGINS` | no | `http://localhost:5173` | Comma-separated allowed CORS origins |
| `CORS_ALLOW_CREDENTIALS` | no | `true` | Allow cookies/auth headers in cross-origin requests |
| `SESSION_TIMEOUT_HOURS` | no | `24` | How long a user session remains valid (hours) |
| `SYNC_INTERVAL_SECONDS` | no | `300` | How often the Gmail watcher polls for new emails |
| `REGEX_TIMEOUT_MS` | no | `1000` | Max milliseconds allowed for regex pattern execution |
| `ENABLE_AUTO_RESTART` | no | `true` | Auto-restart failed watchers after 60s cooldown |
| `ENVIRONMENT` | no | `development` | Set to `production` to enable secure cookies |
| `LOG_LEVEL` | no | `INFO` | Python log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MAX_LEADS_PER_PAGE` | no | `50` | Maximum leads returned per paginated API response |
| `STATIC_FILES_DIR` | no | `../frontend/dist` | Path to compiled frontend static files |

> The backend refuses to start if `ENCRYPTION_KEY` or `SECRET_KEY` is absent or shorter than 32 characters.

## Further Documentation

- [Architecture](docs/ARCHITECTURE.md) — backend layers, frontend structure, database schema, watcher flow
- [API Reference](docs/API.md) — endpoint documentation with request/response examples
- [Contributing](CONTRIBUTING.md) — how to run tests, add endpoints, add pages, branching process
- [Security](SECURITY.md) — secrets management, credential encryption, vulnerability reporting
- [Testing Gaps](docs/TESTING_GAPS.md) — known untested modules and rationale
- [Clean Clone Validation](docs/CLEAN_CLONE_VALIDATION.md) — verified one-command startup result

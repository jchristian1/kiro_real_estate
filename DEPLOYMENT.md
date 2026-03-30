# Deployment Guide

This guide covers deploying the Lead Intake & Workflow Platform to a Linux server.
The supported deployment model is **Docker Compose** (api + worker + frontend + postgres).
A bare systemd deployment path is also documented for environments without Docker.

---

## Table of Contents

- [Architecture overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Docker Compose deployment (recommended)](#docker-compose-deployment-recommended)
- [Bare systemd deployment (without Docker)](#bare-systemd-deployment-without-docker)
- [Database management](#database-management)
- [Security best practices](#security-best-practices)
- [Monitoring and observability](#monitoring-and-observability)
- [Backup and recovery](#backup-and-recovery)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

---

## Architecture overview

The platform runs four processes. All four must be running for the system to work end-to-end.

| Process | Role |
|---------|------|
| `api` | FastAPI HTTP server — handles all browser/client requests |
| `worker` | Background process — owns all Gmail watcher lifecycle, reconciles watcher state every 10 seconds |
| `frontend` | nginx serving the compiled React app |
| `postgres` | PostgreSQL database — shared by api and worker |

**Worker ownership:** The worker process owns WatcherRegistry and all watcher start/stop/restart logic.
The API does not start or stop watchers directly. It writes desired state to the `watcher_control` table;
the worker reads that table and reconciles. The API reads live status from the `watcher_status` table
written by the worker.

**Database:** PostgreSQL is required for any deployment that runs both the api and worker.
SQLite is not safe for multi-process use — concurrent writes from api and worker will produce
`database is locked` errors.

> **SQLite policy for this guide:** SQLite may exist in the codebase for automated tests
> and limited single-process local development. This deployment guide does not support
> SQLite as a deployment target. PostgreSQL is the required database for all deployments
> described here.

---

## Prerequisites

### System requirements

- **OS**: Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+, or RHEL 8+)
- **Docker**: 24+ with Docker Compose v2
- **Memory**: 1 GB minimum, 2 GB recommended
- **Disk**: 5 GB minimum (more for logs and database growth)
- **Network**: Outbound access to Gmail IMAP (imap.gmail.com:993) and SMTP (smtp.gmail.com:587)

### Required credentials

- Gmail account with 2FA enabled and an App Password generated
- `ENCRYPTION_KEY` — Fernet key for encrypting Gmail credentials at rest
- `SECRET_KEY` — random secret for HMAC session token protection

---

## Docker Compose deployment (recommended)

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repo-directory>
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set the required values:

```bash
# Required secrets — generate with make generate-secrets
ENCRYPTION_KEY=<fernet-key>
SECRET_KEY=<32-char-random-string>

# Database — the compose Postgres service is reachable at host "postgres"
DATABASE_URL=postgresql://app:app@postgres:5432/kiro

# Runtime environment
ENVIRONMENT=production

# CORS — set to your actual frontend domain in production
CORS_ORIGINS=https://your-domain.com
```

Generate secrets:

```bash
make generate-secrets
```

### 3. Start all services

```bash
docker compose up --build -d
```

This starts all four services: postgres, api, worker, frontend.
Postgres starts first; the api waits for it to be healthy; the worker waits for both.
Database migrations run automatically on api container startup.

### 4. Create the first admin user

The application starts with an empty database. There is no automatic seeding in production.

Use the self-service registration endpoint to create the first company and admin account:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Your Company",
    "admin_username": "admin",
    "admin_password": "<your-secure-password>"
  }'
```

This creates a company and a `company_admin` user in one step. The admin can then log in
at `http://localhost:80/admin`.

> `make seed-dev` is a development-only command. It requires `ENVIRONMENT=development`
> and `DEV_SEED=true` and will refuse to run in production. Do not use it in a
> production or staging deployment.

### 5. Verify

```bash
curl http://localhost:8000/api/v1/health
curl -I http://localhost:80
```

### Service management

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f worker
docker compose restart worker
docker compose down
```

---

## Bare systemd deployment (without Docker)

Use this path if Docker is not available. You will run two systemd services: one for the
API and one for the worker.

### 1. Create a dedicated user

```bash
sudo useradd -r -s /bin/bash -m -d /opt/platform platform-svc
```

### 2. Install system dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git postgresql postgresql-contrib libpq-dev
```

**CentOS/RHEL:**
```bash
sudo dnf install -y python3.11 python3-pip git postgresql-server postgresql-contrib libpq-devel
sudo postgresql-setup --initdb
```

### 3. Set up PostgreSQL

```bash
sudo systemctl enable postgresql
sudo systemctl start postgresql

sudo -u postgres psql -c "CREATE USER platform WITH PASSWORD 'change-me';"
sudo -u postgres psql -c "CREATE DATABASE kiro OWNER platform;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE kiro TO platform;"
```

### 4. Clone and install

```bash
sudo su - platform-svc
git clone <repository-url> /opt/platform
cd /opt/platform
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configure environment

```bash
sudo nano /opt/platform/.env
```

```
ENCRYPTION_KEY=<fernet-key>
SECRET_KEY=<32-char-random-string>
DATABASE_URL=postgresql://platform:change-me@localhost:5432/kiro
ENVIRONMENT=production
CORS_ORIGINS=https://your-domain.com
LOG_LEVEL=INFO
```

```bash
sudo chmod 600 /opt/platform/.env
sudo chown platform-svc:platform-svc /opt/platform/.env
```

### 6. Run database migrations

```bash
source /opt/platform/venv/bin/activate
export $(grep -v '^#' /opt/platform/.env | xargs)
alembic upgrade head
```

### 7. Create systemd service — API

`/etc/systemd/system/platform-api.service`:

```ini
[Unit]
Description=Lead Intake Platform — API
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=platform-svc
Group=platform-svc
WorkingDirectory=/opt/platform
EnvironmentFile=/opt/platform/.env
ExecStart=/opt/platform/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/platform
StandardOutput=journal
StandardError=journal
SyslogIdentifier=platform-api

[Install]
WantedBy=multi-user.target
```

### 8. Create systemd service — Worker

`/etc/systemd/system/platform-worker.service`:

```ini
[Unit]
Description=Lead Intake Platform — Worker (watcher runtime)
After=network-online.target postgresql.service platform-api.service
Wants=network-online.target

[Service]
Type=simple
User=platform-svc
Group=platform-svc
WorkingDirectory=/opt/platform
EnvironmentFile=/opt/platform/.env
ExecStart=/opt/platform/venv/bin/python -m worker.main
Restart=always
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/platform
StandardOutput=journal
StandardError=journal
SyslogIdentifier=platform-worker

[Install]
WantedBy=multi-user.target
```

### 9. Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable platform-api platform-worker
sudo systemctl start platform-api platform-worker
sudo systemctl status platform-api platform-worker
```

### 10. Build and deploy frontend (optional)

```bash
cd /opt/platform/frontend
npm ci
VITE_API_BASE_URL=https://your-domain.com/api/v1 npm run build
sudo cp -r dist/* /opt/platform/static/
```

Set `STATIC_FILES_DIR=/opt/platform/static` in `.env` and restart the API.
The API will serve `index.html` for all non-API routes.

---

## Database management

### Migrations

Migrations run automatically on API startup. To run manually:

```bash
alembic upgrade head
alembic current
alembic history
alembic downgrade -1
```

### Backup

```bash
pg_dump $DATABASE_URL -Fc -f /opt/platform/backups/kiro_$(date +%Y%m%d_%H%M%S).dump
pg_restore -d $DATABASE_URL /opt/platform/backups/kiro_20240115_020000.dump
```

### Maintenance

```bash
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('kiro'));"
psql $DATABASE_URL -c "VACUUM ANALYZE;"
```

---

## Security best practices

- Store `ENCRYPTION_KEY` in the environment file with 600 permissions.
- Never commit secrets to version control.
- Use different keys for dev, staging, and production.
- Store a backup of `ENCRYPTION_KEY` in a secrets vault.
- To rotate the key: generate a new key, re-encrypt all stored credentials, update `.env`, restart services.

### Reverse proxy (nginx + TLS)

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Monitoring and observability

### Health endpoint

```bash
curl http://localhost:8000/api/v1/health
```

Returns database connectivity, active watcher count (from `watcher_status` DB table,
eventually consistent ~10s), and per-agent watcher status.
HTTP 200 = healthy or degraded-but-reachable. HTTP 503 = database unreachable.

### Prometheus metrics

```bash
curl http://localhost:8000/metrics
```

Exposes API request/duration/error metrics and `watchers_active` (DB-backed, eventually consistent).

### Logs

```bash
# Docker Compose
docker compose logs -f api
docker compose logs -f worker

# Systemd
sudo journalctl -u platform-api -f
sudo journalctl -u platform-worker -f
sudo journalctl -u platform-api --since "24 hours ago" | grep ERROR
```

### Watcher status

```bash
psql $DATABASE_URL -c "SELECT agent_id, status, last_heartbeat FROM watcher_status;"
```

---

## Backup and recovery

| Item | Frequency | Method |
|------|-----------|--------|
| PostgreSQL database | Daily | `pg_dump` |
| `.env` file | After each change | Secure copy to vault |
| `ENCRYPTION_KEY` | Once | Secrets vault |

**Recovery Time Objective:** ~1 hour
**Recovery Point Objective:** ~24 hours (daily backups)

---

## Maintenance

### Update application

```bash
# Docker Compose
docker compose pull
docker compose up --build -d

# Systemd
sudo systemctl stop platform-api platform-worker
git pull
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl start platform-api platform-worker
```

### Clean old data

```bash
psql $DATABASE_URL -c "DELETE FROM processing_logs WHERE timestamp < NOW() - INTERVAL '90 days';"
psql $DATABASE_URL -c "VACUUM ANALYZE;"
```

---

## Troubleshooting

**`DATABASE_URL is not set` on startup**
Set `DATABASE_URL` in `.env`. There is no default fallback.

**Worker logs `SQLite detected` warning**
Set `DATABASE_URL` to a PostgreSQL connection string. SQLite is not safe for multi-process use.

**`database is locked` errors**
Both api and worker are writing to a SQLite file. Switch to PostgreSQL.

**Watcher shows `stopped` after agent completes onboarding**
The worker reconciles every 10 seconds. Wait up to 10 seconds after Go Live.
Check `watcher_control` to confirm `desired_status = running`.

**Migration fails with `ALTER TABLE` error**
Some migrations use `ALTER COLUMN` which SQLite does not support. Use PostgreSQL.

**Service fails to start after reboot**
```bash
sudo systemctl enable platform-api platform-worker
```

---

## Additional resources

- [README.md](README.md) — quick start and feature overview
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system topology and process ownership
- [docs/FIRST_START.md](docs/FIRST_START.md) — step-by-step local dev setup
- [SECURITY.md](SECURITY.md) — secrets management and security policy

---

*This document reflects the current multi-process architecture (api + worker + frontend + postgres).*
*The legacy single-process gmail-lead-sync CLI deployment is no longer the supported path.*

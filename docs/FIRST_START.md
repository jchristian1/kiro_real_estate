# First Start Guide

Everything you need to go from a fresh clone to a running app on macOS, Linux, or Windows.

---

## How the system works

Three processes must run simultaneously:

| Process | Command | What it does |
|---------|---------|--------------|
| **API** | `uvicorn api.main:app` | Handles all HTTP requests from the frontend |
| **Worker** | `python -m worker.main` | Runs Gmail watchers, processes emails, executes pipelines |
| **Frontend** | `npm run dev` | Serves the React UI (dev mode) |

The worker is the "always-on background brain." Without it, emails are never picked up, leads are never created, and pipelines never execute. All three must be running for the system to work end-to-end.

---

## Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11+ | https://python.org/downloads |
| Node.js | 18+ | https://nodejs.org |
| npm | 9+ | bundled with Node.js |
| PostgreSQL | 14+ | https://postgresql.org/download (or Homebrew: `brew install postgresql@15`) |
| Git | any | https://git-scm.com |

> Windows users: use **PowerShell** or **Git Bash** for all commands. WSL2 also works and follows the Linux path.

---

## 1. Clone and checkout the branch

```bash
git clone https://github.com/jchristian1/kiro_real_estate.git
cd kiro_real_estate
git checkout feature-pipelines
```

---

## 2. Create the Python virtual environment

**macOS / Linux**
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

---

## 3. Set up PostgreSQL

PostgreSQL is the primary database. SQLite is only for running the automated test suite.

**macOS (Homebrew)**
```bash
brew services start postgresql@15
createdb gmail_lead_sync
createdb gmail_lead_sync_test   # for running tests
```

**Linux (Ubuntu/Debian)**
```bash
sudo systemctl start postgresql
sudo -u postgres createuser --superuser $USER
createdb gmail_lead_sync
createdb gmail_lead_sync_test
```

**Windows**
Use the PostgreSQL installer from https://postgresql.org/download/windows and create the databases via pgAdmin or psql.

---

## 4. Set up environment variables

**macOS / Linux**
```bash
cp .env.example .env
```

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
```

Open `.env` and set these values:

```bash
# Database — PostgreSQL (replace with your connection string if using a password)
DATABASE_URL=postgresql://localhost/gmail_lead_sync

# Test database — used by tests/postgres/ suite
POSTGRES_TEST_URL=postgresql://localhost/gmail_lead_sync_test

# Secrets — generate these (see commands below)
ENCRYPTION_KEY=<generate>
SECRET_KEY=<generate>
```

Generate the secrets:

**macOS / Linux**
```bash
# ENCRYPTION_KEY
.venv/bin/python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# SECRET_KEY
.venv/bin/python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Windows (PowerShell)**
```powershell
.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5. Run database migrations

**macOS / Linux**
```bash
.venv/bin/alembic upgrade head
```

**Windows (PowerShell)**
```powershell
.venv/Scripts/alembic upgrade head
```

This applies all migrations to the `gmail_lead_sync` Postgres database.

---

## 6. Seed the database

**macOS / Linux**
```bash
.venv/bin/python scripts/seed_data.py
```

**Windows (PowerShell)**
```powershell
.venv/Scripts/python scripts/seed_data.py
```

This creates:
- Admin user (`admin` / `admin123`) and viewer user (`viewer` / `viewer123`)
- Demo lead sources, leads, and templates

> The API also auto-seeds on first startup if no users exist, so this step is optional.

Safe to run multiple times — skips anything that already exists.

---

## 7. Install frontend dependencies

```bash
npm install --prefix frontend
```

Copy the frontend env file:

**macOS / Linux**
```bash
cp frontend/.env.example frontend/.env
```

**Windows (PowerShell)**
```powershell
Copy-Item frontend\.env.example frontend\.env
```

The default `frontend/.env` points to `http://localhost:8000/api/v1` which is correct for local dev.

---

## 8. Start all three processes

You need **three separate terminal windows/tabs** open in the project root.

### Terminal 1 — API

**macOS / Linux**
```bash
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Windows (PowerShell)**
```powershell
.venv/Scripts/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify it's running:
```bash
curl http://localhost:8000/api/v1/health
# → {"status": "healthy", "db_dialect": "postgresql", ...}
```

### Terminal 2 — Worker

**macOS / Linux**
```bash
.venv/bin/python -m worker.main
```

**Windows (PowerShell)**
```powershell
.venv\Scripts\python -m worker.main
```

The worker polls the `watcher_control` table every 10 seconds and starts/stops Gmail watchers based on what agents have configured. You'll see log output like:

```
INFO  [worker] Worker started
INFO  [worker] Starting watcher for agent 3
INFO  [api.services.watcher_registry] Watcher for agent 3 connected and running
```

### Terminal 3 — Frontend

```bash
cd frontend
npm run dev
```

Frontend runs at **http://localhost:5173**

---

## Login credentials

| Role | Username | Password | URL |
|------|----------|----------|-----|
| Platform Admin | `admin` | `admin123` | http://localhost:5173/admin |
| Agent | sign up via UI | — | http://localhost:5173/agent |

---

## Agent onboarding flow

When an agent signs up and goes through onboarding, they complete 7 steps:

1. **Account** — create email + password
2. **Profile** — name, phone, timezone, service area
3. **Gmail** — connect Gmail account with an app password
4. **Sources** — select which lead sources to monitor
5. **Automation** — configure scoring thresholds and SLA settings
6. **Templates** — set up email templates for each pipeline step
7. **Go Live** — final check, activates the watcher

After Go Live, the worker picks up the agent's watcher configuration and starts monitoring their Gmail inbox. Leads flow in automatically when matching emails arrive.

---

## Verifying the watcher is running

After an agent completes onboarding, check the database:

```bash
psql gmail_lead_sync -c "SELECT agent_id, status, last_heartbeat FROM watcher_status;"
```

You should see the agent's watcher with `status = running` and a recent `last_heartbeat` timestamp (updated every ~10 seconds by the worker).

---

## Docker (alternative to steps 2–8)

If you have Docker installed, steps 2–8 are replaced by a single command. Migrations and seed run automatically on startup.

**macOS / Linux**
```bash
cp .env.example .env
# Fill in ENCRYPTION_KEY and SECRET_KEY in .env (same as step 4)
# Set DATABASE_URL=postgresql://app:app@postgres:5432/gmail_lead_sync
docker compose --profile postgres up --build
```

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
docker compose --profile postgres up --build
```

Frontend: **http://localhost:80** — API: **http://localhost:8000**

The Docker setup starts the API, worker, and Postgres automatically. The frontend is served as a static build.

---

## Troubleshooting

**`ENCRYPTION_KEY` or `SECRET_KEY` error on startup**
Both keys must be at least 32 characters. Re-generate them using the commands in step 4.

**`connection refused` on `alembic upgrade head`**
PostgreSQL is not running. Start it with `brew services start postgresql@15` (macOS) or `sudo systemctl start postgresql` (Linux).

**`database "gmail_lead_sync" does not exist`**
Run `createdb gmail_lead_sync` from your terminal.

**`value too long for type character varying(64)` on login**
Run `alembic upgrade head` — this applies the migration that widens the sessions token column to 128 chars.

**`ForeignKeyViolation` when deleting an agent**
Run `alembic upgrade head` — Postgres enforces FK constraints that SQLite silently ignored.

**Emails not being picked up / leads not appearing**
The worker is not running. Open a second terminal and start it:
```bash
.venv/bin/python -m worker.main
```
Check `watcher_status` in the database to confirm the watcher is active.

**Worker starts but watcher shows `stopped`**
The agent hasn't completed onboarding. The watcher only starts after the agent reaches Go Live (step 7). Check `watcher_control` to see the desired state.

**`Multiple head revisions` on `alembic upgrade head`**
You are likely not on the correct branch. Run `git checkout feature-pipelines` and try again.

**Frontend shows blank page or API errors**
Make sure the backend is running on port 8000 and `frontend/.env` contains:
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

**Port 8000 already in use**
Change the port in `.env` (`API_PORT=8001`) and update `frontend/.env` to match:
```
VITE_API_BASE_URL=http://localhost:8001/api/v1
```

**`python3` not found on Windows**
Use `python` instead of `python3`. Make sure Python is added to your PATH during installation.

**Windows: `.venv\Scripts\...` gives "execution policy" error**
Run this once in PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

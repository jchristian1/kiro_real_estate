# First Start Guide

Everything you need to go from a fresh clone to a running app on macOS, Linux, or Windows.

---

## Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11+ | https://python.org/downloads |
| Node.js | 18+ | https://nodejs.org |
| npm | 9+ | bundled with Node.js |
| Git | any | https://git-scm.com |

> Windows users: use **PowerShell** or **Git Bash** for all commands. WSL2 also works and follows the Linux path.

---

## 1. Clone and checkout the branch

```bash
git clone https://github.com/jchristian1/kiro_real_estate.git
cd kiro_real_estate
git checkout final-user-ui
```

---

## 2. Create the Python virtual environment

**macOS / Linux**
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-api.txt
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -r requirements-api.txt
```

---

## 3. Set up environment variables

**macOS / Linux**
```bash
cp .env.example .env
```

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
```

Then generate secure keys:

**macOS / Linux**
```bash
# Generate ENCRYPTION_KEY
.venv/bin/python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate SECRET_KEY
.venv/bin/python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Windows (PowerShell)**
```powershell
# Generate ENCRYPTION_KEY
.venv\Scripts\python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate SECRET_KEY
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
```

Open `.env` in any text editor and replace the two placeholder values:

```
ENCRYPTION_KEY=<output from first command>
SECRET_KEY=<output from second command>
```

Everything else in `.env` can stay as-is for local development.

---

## 4. Run database migrations

**macOS / Linux**
```bash
.venv/bin/alembic upgrade head
```

**Windows (PowerShell)**
```powershell
.venv/Scripts/alembic upgrade head
```

This creates `gmail_lead_sync.db` (SQLite) and applies all migrations.

---

## 5. Seed the database

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
- NYSLegal company with the Law Firm intake form assigned
- Demo lead sources, leads, and templates

Safe to run multiple times — skips anything that already exists.

---

## 6. Install frontend dependencies

**macOS / Linux / Windows**
```bash
npm install --prefix frontend
```

Then copy the frontend env file:

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

## 7. Start the backend

**macOS / Linux**
```bash
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Windows (PowerShell)**
```powershell
.venv/Scripts/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify it's running (new terminal):

```bash
curl http://localhost:8000/api/v1/health
# → {"status": "healthy", ...}
```

---

## 8. Start the frontend

Open a **second terminal** in the project root:

**macOS / Linux / Windows**
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

## Docker (alternative to steps 2–8)

If you have Docker installed, steps 2–8 are replaced by a single command. Migrations and seed run automatically on startup.

**macOS / Linux**
```bash
cp .env.example .env
# Fill in ENCRYPTION_KEY and SECRET_KEY in .env (same as step 3)
docker compose up --build
```

**Windows (PowerShell)**
```powershell
Copy-Item .env.example .env
# Fill in ENCRYPTION_KEY and SECRET_KEY in .env (same as step 3)
docker compose up --build
```

Frontend: **http://localhost:80** — API: **http://localhost:8000**

---

## Troubleshooting

**`ENCRYPTION_KEY` or `SECRET_KEY` error on startup**
Both keys must be at least 32 characters. Re-generate them using the commands in step 3.

**`python3` not found on Windows**
Use `python` instead of `python3`. Make sure Python is added to your PATH during installation (check "Add Python to PATH" in the installer).

**`Multiple head revisions` on `alembic upgrade head`**
You are likely not on the correct branch. Run `git checkout final-user-ui` and try again.

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

**Seed fails with import errors**
Make sure you ran `pip install` from the repo root (not inside `api/` or `frontend/`) and that you are using the `.venv` Python, not the system Python.

**Windows: `.venv\Scripts\...` gives "execution policy" error**
Run this once in PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

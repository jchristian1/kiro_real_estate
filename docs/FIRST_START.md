# First Start Guide

Everything you need to go from a fresh clone to a running app.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

---

## Steps

### 1. Clone and checkout the branch

```bash
git clone https://github.com/jchristian1/kiro_real_estate.git
cd kiro_real_estate
git checkout final-user-ui
```

---

### 2. Create the Python virtual environment and install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-api.txt
```

---

### 3. Set up environment variables

```bash
cp .env.example .env
```

Then generate secure keys and paste them into `.env`:

```bash
# Generate ENCRYPTION_KEY
.venv/bin/python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate SECRET_KEY
.venv/bin/python3 -c "import secrets; print(secrets.token_hex(32))"
```

Open `.env` and replace the placeholder values:

```
ENCRYPTION_KEY=<output from first command>
SECRET_KEY=<output from second command>
```

Everything else in `.env` can stay as-is for local development.

---

### 4. Run database migrations

```bash
.venv/bin/alembic upgrade head
```

This creates the SQLite database (`gmail_lead_sync.db`) and applies all migrations.

---

### 5. Seed the database

```bash
.venv/bin/python scripts/seed_data.py
```

This creates:
- Admin user (`admin` / `admin123`) and viewer user (`viewer` / `viewer123`)
- NYSLegal company with the Law Firm intake form assigned
- Demo lead sources, leads, and templates

Safe to run multiple times — it skips anything that already exists.

---

### 6. Install frontend dependencies

```bash
npm install --prefix frontend
cp frontend/.env.example frontend/.env
```

The default `frontend/.env` points to `http://localhost:8000/api/v1` which is correct for local dev.

---

### 7. Start the backend

```bash
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify it's running:

```bash
curl http://localhost:8000/api/v1/health
# → {"status": "healthy", ...}
```

---

### 8. Start the frontend

In a separate terminal:

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

If you prefer Docker, steps 2–8 are replaced by a single command. Docker handles migrations and seed automatically on startup.

```bash
cp .env.example .env
# Fill in ENCRYPTION_KEY and SECRET_KEY in .env (same as step 3 above)

docker compose up --build
```

Frontend: **http://localhost:80** — API: **http://localhost:8000**

---

## Troubleshooting

**`ENCRYPTION_KEY` or `SECRET_KEY` error on startup**
The backend requires both keys to be at least 32 characters. Re-generate them using the commands in step 3.

**`Multiple head revisions` on `alembic upgrade head`**
Run `alembic heads` to see the heads. This should not happen on a clean clone — if it does, check that you are on the `final-user-ui` branch.

**Frontend shows blank page or API errors**
Make sure the backend is running on port 8000 and `frontend/.env` has `VITE_API_BASE_URL=http://localhost:8000/api/v1`.

**Seed fails with import errors**
Make sure you installed dependencies from the repo root (not inside `api/` or `frontend/`) and that your virtual environment is activated.

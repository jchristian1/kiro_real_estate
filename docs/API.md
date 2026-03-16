# Gmail Lead Sync — API Reference

The API is built with FastAPI and provides auto-generated interactive documentation.

## Interactive Docs

| URL | Description |
|-----|-------------|
| `/api/docs` | Swagger UI — try endpoints directly in the browser |
| `/api/redoc` | ReDoc — clean reference documentation |
| `/api/openapi.json` | Raw OpenAPI 3.0 schema |

---

## Quick Start

### 1. Set Up Environment

```bash
cp .env.example .env
# Edit .env and fill in ENCRYPTION_KEY, SECRET_KEY, etc.
# Or generate secrets automatically:
make generate-secrets
```

### 2. Start the Application

```bash
make up          # Docker Compose (recommended)
# or
alembic upgrade head
uvicorn api.main:app --reload --port 8000
```

### 3. Access the API

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

---

## Authentication

All endpoints (except `/api/v1/health` and `/metrics`) require an active session.

### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin", "password": "your-password"}
```

A `session_token` cookie is set on success. Browsers include it automatically in subsequent requests.

### Check Current User
```http
GET /api/v1/auth/me
```

### Logout
```http
POST /api/v1/auth/logout
```

### Demo Users (seed data)

| Username | Password | Role |
|----------|----------|------|
| `admin`  | `admin123` | platform_admin |
| `viewer` | `viewer123` | viewer |

---

## Endpoint Groups

| Prefix | Description |
|--------|-------------|
| `/api/v1/auth` | Login, logout, session management |
| `/api/v1/health` | System health status (no auth required) |
| `/api/v1/agents` | Gmail agent CRUD + credential management |
| `/api/v1/watchers` | Start/stop/sync background watchers |
| `/api/v1/lead-sources` | Lead source CRUD, regex testing, versioning |
| `/api/v1/templates` | Email template CRUD, preview, versioning |
| `/api/v1/leads` | Lead listing, filtering, CSV export |
| `/api/v1/audit-logs` | Audit log viewing and filtering |
| `/api/v1/settings` | Application settings management |
| `/metrics` | Prometheus metrics (no auth required) |

---

## Key Endpoints

### Health

```
GET /api/v1/health
```

Returns system status, database connectivity, active watcher count, and 24 h error count.

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

---

### Agents

```
POST   /api/v1/agents              Create agent (encrypts credentials)
GET    /api/v1/agents              List agents (credentials excluded)
GET    /api/v1/agents/{id}         Get agent details
PUT    /api/v1/agents/{id}         Update agent
DELETE /api/v1/agents/{id}         Delete agent (stops watcher)
```

**Create agent request:**
```json
{
  "agent_id": "my_agent",
  "email": "agent@example.com",
  "app_password": "gmail-app-password"
}
```

---

### Watchers

```
POST /api/v1/watchers/{agent_id}/start   Start watcher
POST /api/v1/watchers/{agent_id}/stop    Stop watcher
POST /api/v1/watchers/{agent_id}/sync    Trigger manual sync
GET  /api/v1/watchers/status             All watcher statuses
```

---

### Lead Sources

```
POST   /api/v1/lead-sources                  Create lead source
GET    /api/v1/lead-sources                  List lead sources
PUT    /api/v1/lead-sources/{id}             Update (creates version)
DELETE /api/v1/lead-sources/{id}             Delete
POST   /api/v1/lead-sources/test-regex       Test regex pattern
GET    /api/v1/lead-sources/{id}/versions    Version history
POST   /api/v1/lead-sources/{id}/rollback    Rollback to version
```

**Test regex request:**
```json
{
  "pattern": "Name:\\s*(.+)",
  "sample_text": "Name: John Doe\nPhone: 555-1234"
}
```

---

### Templates

```
POST   /api/v1/templates                 Create template
GET    /api/v1/templates                 List templates
PUT    /api/v1/templates/{id}            Update (creates version)
DELETE /api/v1/templates/{id}            Delete
POST   /api/v1/templates/preview         Preview with sample data
GET    /api/v1/templates/{id}/versions   Version history
POST   /api/v1/templates/{id}/rollback   Rollback to version
```

**Supported template placeholders:** `{lead_name}`, `{agent_name}`, `{agent_phone}`, `{agent_email}`

---

### Leads

```
GET /api/v1/leads          List leads (pagination + filters)
GET /api/v1/leads/{id}     Lead detail
GET /api/v1/leads/export   CSV export (same filters as list)
```

**Query parameters:** `page`, `per_page` (max 100), `agent_id`, `start_date`, `end_date`, `response_sent`

---

### Settings

```
GET /api/v1/settings    Get all settings
PUT /api/v1/settings    Update settings (partial updates supported)
```

| Setting | Type | Range | Default |
|---------|------|-------|---------|
| `sync_interval_seconds` | int | 60–3600 | 300 |
| `regex_timeout_ms` | int | 100–5000 | 1000 |
| `session_timeout_hours` | int | 1–168 | 24 |
| `max_leads_per_page` | int | 10–1000 | 50 |
| `enable_auto_restart` | bool | — | true |

---

## Error Responses

All 4xx/5xx responses use a unified schema:

```json
{
  "error": "Not Found",
  "message": "Agent with ID 'xyz' not found",
  "code": "NOT_FOUND_RESOURCE",
  "details": null
}
```

| HTTP Status | Code | Meaning |
|-------------|------|---------|
| 400 | `VALIDATION_ERROR` | Business rule validation failure |
| 401 | `AUTHENTICATION_ERROR` | Missing/invalid/expired session |
| 403 | `AUTHORIZATION_ERROR` | Insufficient role or cross-tenant access |
| 404 | `NOT_FOUND_RESOURCE` | Resource does not exist |
| 408 | `TIMEOUT_ERROR` | Operation timeout (e.g. regex) |
| 409 | `CONFLICT_ERROR` | Duplicate resource or conflicting state |
| 422 | `VALIDATION_ERROR` | Request body failed schema validation |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_SERVER_ERROR` | Unexpected server error |

---

## Troubleshooting

**Database connection errors**
```bash
alembic upgrade head
```

**Encryption key errors**
```bash
make generate-secrets   # writes ENCRYPTION_KEY and SECRET_KEY to .env
```

**Watcher not starting**
1. Verify agent credentials are valid Gmail App Passwords.
2. Check `GET /api/v1/watchers/status` for error details.
3. Review audit logs: `GET /api/v1/audit-logs`.

**Import errors**
```bash
pip install -r requirements-api.txt
python --version   # requires Python 3.11+
```

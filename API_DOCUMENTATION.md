# Gmail Lead Sync API Documentation

The API is built with FastAPI and provides auto-generated interactive documentation.

## Interactive Docs

| URL | Description |
|-----|-------------|
| `/api/docs` | Swagger UI — try endpoints directly in the browser |
| `/api/redoc` | ReDoc — clean reference documentation |
| `/api/openapi.json` | Raw OpenAPI 3.0 schema |

## Authentication

All endpoints (except `/api/v1/auth/login` and `/api/v1/health`) require an active session.

**Login:**
```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin", "password": "your-password"}
```

A `session_token` cookie is set on success. Include it in subsequent requests (browsers do this automatically).

**Check current user:**
```http
GET /api/v1/auth/me
```

**Logout:**
```http
POST /api/v1/auth/logout
```

## Endpoint Groups

| Prefix | Description |
|--------|-------------|
| `/api/v1/auth` | Login, logout, session management |
| `/api/v1/health` | System health status |
| `/api/v1/agents` | Gmail agent CRUD + credential management |
| `/api/v1/watchers` | Start/stop/sync background watchers |
| `/api/v1/lead-sources` | Lead source CRUD, regex testing, versioning |
| `/api/v1/templates` | Email template CRUD, preview, versioning |
| `/api/v1/leads` | Lead listing, filtering, CSV export |
| `/api/v1/audit-logs` | Audit log viewing and filtering |
| `/api/v1/settings` | Application settings management |
| `/metrics` | Prometheus metrics (no auth required) |

## Key Endpoints

### Health
```
GET /api/v1/health
```
Returns system status, database connectivity, active watcher count, and 24h error count.

### Agents
```
POST   /api/v1/agents              Create agent (encrypts credentials)
GET    /api/v1/agents              List agents (credentials excluded)
GET    /api/v1/agents/{id}         Get agent details
PUT    /api/v1/agents/{id}         Update agent
DELETE /api/v1/agents/{id}         Delete agent (stops watcher)
```

### Watchers
```
POST /api/v1/watchers/{agent_id}/start   Start watcher
POST /api/v1/watchers/{agent_id}/stop    Stop watcher
POST /api/v1/watchers/{agent_id}/sync    Trigger manual sync
GET  /api/v1/watchers/status             All watcher statuses
```

### Lead Sources
```
POST /api/v1/lead-sources                    Create lead source
GET  /api/v1/lead-sources                    List lead sources
PUT  /api/v1/lead-sources/{id}               Update (creates version)
DELETE /api/v1/lead-sources/{id}             Delete
POST /api/v1/lead-sources/test-regex         Test regex pattern
GET  /api/v1/lead-sources/{id}/versions      Version history
POST /api/v1/lead-sources/{id}/rollback      Rollback to version
```

### Templates
```
POST /api/v1/templates                   Create template
GET  /api/v1/templates                   List templates
PUT  /api/v1/templates/{id}              Update (creates version)
DELETE /api/v1/templates/{id}            Delete
POST /api/v1/templates/preview           Preview with sample data
GET  /api/v1/templates/{id}/versions     Version history
POST /api/v1/templates/{id}/rollback     Rollback to version
```

### Leads
```
GET /api/v1/leads          List leads (pagination + filters)
GET /api/v1/leads/{id}     Lead detail
GET /api/v1/leads/export   CSV export (same filters as list)
```

### Settings
```
GET /api/v1/settings    Get all settings
PUT /api/v1/settings    Update settings
```

Supported settings: `sync_interval_seconds`, `regex_timeout_ms`, `session_timeout_hours`, `max_leads_per_page`, `enable_auto_restart`.

## Error Responses

All errors return a consistent JSON structure:

```json
{
  "error": "Not Found",
  "message": "Agent with ID 'xyz' not found",
  "code": "NOT_FOUND_RESOURCE",
  "details": null
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 400 | Validation error or bad request |
| 401 | Not authenticated |
| 403 | Authenticated but not authorized |
| 404 | Resource not found |
| 409 | Conflict (e.g. duplicate agent ID) |
| 422 | Request body failed schema validation |
| 500 | Internal server error |

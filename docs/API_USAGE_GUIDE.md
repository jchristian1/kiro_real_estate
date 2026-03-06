# Gmail Lead Sync API - Usage Guide

## Quick Start

### 1. Setup Environment

```bash
# Set required environment variables
export DATABASE_URL="sqlite:///./gmail_lead_sync.db"
export ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export SECRET_KEY="your-32-character-secret-key"
export CORS_ORIGINS="http://localhost:3000,http://localhost:5173"
```

### 2. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Seed demo data (optional)
python scripts/seed_data.py
```

### 3. Start API Server

```bash
# Development mode
uvicorn api.main:app --reload --port 8000

# Production mode
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Access API Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

---

## Authentication

All API endpoints (except `/health` and `/metrics`) require authentication.

### Login Flow

1. **Create Session** (not yet implemented - use seed data users)
2. **Session Cookie**: API returns HTTP-only cookie with session token
3. **Authenticated Requests**: Include cookie in subsequent requests

### Demo Users (from seed data)

- **Admin**: username=`admin`, password=`admin123`
- **Viewer**: username=`viewer`, password=`viewer123`

---

## API Endpoints

### Health & Monitoring

#### GET /api/v1/health
Check system health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-03T00:00:00Z",
  "database": {
    "connected": true,
    "message": "Database connection active"
  },
  "watchers": {
    "active_count": 2,
    "heartbeats": {
      "agent1": "2026-03-03T00:00:00Z",
      "agent2": "2026-03-03T00:00:00Z"
    }
  },
  "errors": {
    "count_24h": 0,
    "recent_errors": []
  }
}
```

#### GET /metrics
Prometheus metrics endpoint.

**Response:** Prometheus text format

---

### Agent Management

#### POST /api/v1/agents
Create a new agent with encrypted credentials.

**Request:**
```json
{
  "agent_id": "my_agent",
  "email": "agent@example.com",
  "app_password": "gmail-app-password"
}
```

**Response:**
```json
{
  "agent_id": "my_agent",
  "email": "agent@example.com",
  "created_at": "2026-03-03T00:00:00Z"
}
```

#### GET /api/v1/agents
List all agents (credentials excluded).

**Response:**
```json
{
  "agents": [
    {
      "agent_id": "my_agent",
      "email": "agent@example.com",
      "created_at": "2026-03-03T00:00:00Z"
    }
  ]
}
```

#### GET /api/v1/agents/{agent_id}
Get agent details.

#### PUT /api/v1/agents/{agent_id}
Update agent email or password.

**Request:**
```json
{
  "email": "newemail@example.com",
  "app_password": "new-password"
}
```

#### DELETE /api/v1/agents/{agent_id}
Delete agent and stop associated watcher.

---

### Lead Source Management

#### POST /api/v1/lead-sources
Create a lead source with regex patterns.

**Request:**
```json
{
  "sender_email": "leads@zillow.com",
  "identifier_snippet": "New Lead",
  "name_regex": "Name:\\s*(.+)",
  "phone_regex": "Phone:\\s*([\\d-]+)",
  "template_id": 1,
  "auto_respond_enabled": true
}
```

#### GET /api/v1/lead-sources
List all lead sources.

#### POST /api/v1/lead-sources/test-regex
Test regex patterns against sample text.

**Request:**
```json
{
  "pattern": "Name:\\s*(.+)",
  "sample_text": "Name: John Doe\nPhone: 555-1234"
}
```

**Response:**
```json
{
  "matches": true,
  "groups": ["John Doe"],
  "error": null
}
```

#### GET /api/v1/lead-sources/{id}/versions
Get version history for lead source.

#### POST /api/v1/lead-sources/{id}/rollback
Rollback to a previous version.

**Request:**
```json
{
  "version_id": 5
}
```

---

### Template Management

#### POST /api/v1/templates
Create an email template.

**Request:**
```json
{
  "name": "Welcome Template",
  "subject": "Thank you, {lead_name}",
  "body": "Hi {lead_name},\n\nThanks for reaching out!\n\n{agent_name}\n{agent_phone}"
}
```

**Supported Placeholders:**
- `{lead_name}` - Lead's name
- `{agent_name}` - Agent's name
- `{agent_phone}` - Agent's phone
- `{agent_email}` - Agent's email

#### POST /api/v1/templates/preview
Preview template with sample data.

**Request:**
```json
{
  "subject": "Hello {lead_name}",
  "body": "Contact me at {agent_phone}",
  "sample_data": {
    "lead_name": "John Doe",
    "agent_name": "Jane Smith",
    "agent_phone": "555-1234",
    "agent_email": "jane@example.com"
  }
}
```

**Response:**
```json
{
  "subject": "Hello John Doe",
  "body": "Contact me at 555-1234"
}
```

#### GET /api/v1/templates/{id}/versions
Get version history.

#### POST /api/v1/templates/{id}/rollback
Rollback to previous version.

---

### Watcher Management

#### POST /api/v1/watchers/{agent_id}/start
Start Gmail watcher for agent.

**Response:**
```json
{
  "agent_id": "my_agent",
  "status": "running",
  "message": "Watcher started successfully"
}
```

#### POST /api/v1/watchers/{agent_id}/stop
Stop watcher.

#### POST /api/v1/watchers/{agent_id}/sync
Trigger manual sync.

#### GET /api/v1/watchers/status
Get status of all watchers.

**Response:**
```json
{
  "agent1": {
    "status": "running",
    "last_sync": "2026-03-03T00:00:00Z",
    "heartbeat": "2026-03-03T00:00:00Z",
    "error": null
  },
  "agent2": {
    "status": "stopped",
    "last_sync": null,
    "heartbeat": null,
    "error": null
  }
}
```

---

### Lead Viewing & Export

#### GET /api/v1/leads
List leads with pagination and filtering.

**Query Parameters:**
- `page` (default: 1)
- `per_page` (default: 50, max: 100)
- `agent_id` (optional)
- `start_date` (ISO format, optional)
- `end_date` (ISO format, optional)
- `response_sent` (true/false, optional)

**Example:**
```
GET /api/v1/leads?page=1&per_page=20&response_sent=true
```

**Response:**
```json
{
  "leads": [
    {
      "id": 1,
      "name": "John Doe",
      "phone": "555-1234",
      "source_email": "leads@zillow.com",
      "lead_source_id": 1,
      "gmail_uid": "abc123",
      "created_at": "2026-03-03T00:00:00Z",
      "updated_at": null,
      "response_sent": true,
      "response_status": "success"
    }
  ],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "pages": 5
}
```

#### GET /api/v1/leads/{id}
Get lead details.

#### GET /api/v1/leads/export
Export leads to CSV.

**Query Parameters:** Same as list endpoint

**Response:** CSV file download

---

### Audit Logs

#### GET /api/v1/audit-logs
List audit logs with filtering.

**Query Parameters:**
- `page` (default: 1)
- `per_page` (default: 50)
- `action` (optional: create, update, delete, etc.)
- `user_id` (optional)
- `start_date` (ISO format, optional)
- `end_date` (ISO format, optional)

**Response:**
```json
{
  "logs": [
    {
      "id": 1,
      "timestamp": "2026-03-03T00:00:00Z",
      "user_id": 1,
      "action": "create",
      "resource_type": "agent",
      "resource_id": "my_agent",
      "details": {"email": "agent@example.com"}
    }
  ],
  "total": 50,
  "page": 1,
  "per_page": 50,
  "pages": 1
}
```

---

### Settings Management

#### GET /api/v1/settings
Get all system settings.

**Response:**
```json
{
  "sync_interval_seconds": 300,
  "regex_timeout_ms": 1000,
  "session_timeout_hours": 24,
  "max_leads_per_page": 50,
  "enable_auto_restart": true
}
```

#### PUT /api/v1/settings
Update settings (partial updates supported).

**Request:**
```json
{
  "sync_interval_seconds": 600,
  "enable_auto_restart": false
}
```

**Validation Rules:**
- `sync_interval_seconds`: 60-3600
- `regex_timeout_ms`: 100-5000
- `session_timeout_hours`: 1-168
- `max_leads_per_page`: 10-1000
- `enable_auto_restart`: boolean

---

## Error Handling

All errors return structured JSON responses:

```json
{
  "error": "Validation Error",
  "message": "Invalid email format",
  "code": "VALIDATION_ERROR",
  "details": {
    "field": "email",
    "value": "invalid-email"
  }
}
```

### Error Codes

- `VALIDATION_ERROR` (400) - Invalid input
- `AUTHENTICATION_ERROR` (401) - Not authenticated
- `AUTHORIZATION_ERROR` (403) - Not authorized
- `NOT_FOUND_RESOURCE` (404) - Resource not found
- `CONFLICT_ERROR` (409) - Resource conflict
- `TIMEOUT_ERROR` (408) - Operation timeout
- `INTERNAL_SERVER_ERROR` (500) - Server error

---

## Rate Limiting

Currently not implemented. Consider adding for production:
- 100 requests per minute per IP
- 1000 requests per hour per user

---

## Best Practices

### Security
1. Always use HTTPS in production
2. Rotate ENCRYPTION_KEY and SECRET_KEY regularly
3. Use strong passwords for user accounts
4. Monitor audit logs for suspicious activity

### Performance
1. Use pagination for large datasets
2. Filter results to reduce response size
3. Cache frequently accessed data
4. Use connection pooling for database

### Monitoring
1. Check `/api/v1/health` endpoint regularly
2. Monitor `/metrics` with Prometheus
3. Set up alerts for error rates
4. Track watcher heartbeats

---

## Troubleshooting

### Database Connection Errors
```bash
# Check database file exists
ls -la gmail_lead_sync.db

# Run migrations
alembic upgrade head
```

### Encryption Key Errors
```bash
# Generate new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set environment variable
export ENCRYPTION_KEY="your-generated-key"
```

### Watcher Not Starting
1. Check agent credentials are valid
2. Verify Gmail API access
3. Check watcher logs in audit logs
4. Ensure no other watcher running for same agent

### Import Errors
```bash
# Install dependencies
pip install -r requirements-api.txt

# Check Python version (3.11+ required)
python --version
```

---

## Support

For issues or questions:
1. Check API documentation: http://localhost:8000/api/docs
2. Review audit logs: `GET /api/v1/audit-logs`
3. Check health status: `GET /api/v1/health`
4. Review application logs (JSON format)

---

## Next Steps

1. ✅ Backend API is ready
2. 🔄 Implement frontend React application
3. 🔄 Add user authentication endpoints
4. 🔄 Deploy to production
5. 🔄 Set up monitoring and alerts

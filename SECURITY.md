# Security

## Secrets Management

### Required secrets

The application requires two secrets at startup, both must be **≥ 32 characters**:

| Variable | Purpose |
|----------|---------|
| `ENCRYPTION_KEY` | Fernet key used to encrypt Gmail credentials at rest |
| `SECRET_KEY` | Key used to derive HMAC digests for session token protection at rest |

The backend refuses to start if either variable is absent or shorter than 32 characters, logging a descriptive error and exiting with code 1.

### Dev seed secrets

When running `make seed-dev`, one additional variable is required:

| Variable | Purpose |
|----------|---------|
| `DEV_ADMIN_PASSWORD` | Password for the seeded `admin` account |
| `DEV_VIEWER_PASSWORD` | (Optional) Password for the seeded `viewer` account; falls back to `DEV_ADMIN_PASSWORD` |

The seed script will exit with a clear error if `DEV_ADMIN_PASSWORD` is not set. No privileged account is ever created with a generated or hardcoded password. Passwords are never printed to structured logs.

### Generating secrets

```bash
# Writes fresh ENCRYPTION_KEY and SECRET_KEY into .env
make generate-secrets
```

`scripts/generate_secrets.sh` generates:
- `ENCRYPTION_KEY` — a Fernet key via `cryptography.fernet.Fernet.generate_key()` (URL-safe base64, 44 chars)
- `SECRET_KEY` — 64 hex characters from `secrets.token_hex(32)`

If `.env` does not exist it is created from `.env.example` first. Existing values for these two keys are replaced; all other `.env` entries are left untouched.

### What must never be committed

`.gitignore` excludes:

```
.env
*.db
*.sqlite
*.sqlite3
*.log
htmlcov/
.hypothesis/
__pycache__/
frontend/dist/
```

Run `git status` before committing to confirm no secrets are staged. The CI pipeline does not have access to real secrets — it uses generated placeholder values.

---

## Credential Encryption

Gmail App Passwords are encrypted with **AES-256-GCM** before being written to the database. Plaintext credentials are never stored or logged.

### How it works

1. A fresh random 96-bit nonce is generated for every encryption call (IND-CPA secure — encrypting the same password twice produces different ciphertexts).
2. The output format stored in the DB is: `base64( nonce || ciphertext_with_GCM_tag )`.
3. Decryption requires the same `ENCRYPTION_KEY`; if the key changes or the ciphertext is tampered with, decryption raises `ValueError`.

The encryption key is loaded exclusively from the `ENCRYPTION_KEY` environment variable — it is never hardcoded.

### Key rotation

If you need to rotate `ENCRYPTION_KEY`:

1. Generate a new key: `make generate-secrets` (or run `scripts/generate_secrets.sh`).
2. Re-encrypt all stored credentials using the old key to decrypt and the new key to re-encrypt.
3. Update `ENCRYPTION_KEY` in your deployment environment.
4. Restart the application.

There is no automated rotation tooling — this is a manual process.

---

## Session Security

Sessions are stored server-side in the `sessions` table. The session token is a cryptographically random 64-character string.

### Cookie settings

| Setting | Development | Production (`ENVIRONMENT=production`) |
|---------|-------------|---------------------------------------|
| `httponly` | `True` | `True` |
| `secure` | `False` | `True` (HTTPS only) |
| `samesite` | `lax` | `strict` |

Set `ENVIRONMENT=production` in `.env` to enable the stricter production cookie settings.

### Session expiry

Sessions expire after `SESSION_TIMEOUT_HOURS` (default: 24 hours). A background cleanup task removes expired sessions periodically.

### Authentication failure logging

Every failed login attempt is logged at `WARNING` level with:
- `username_attempted` — the username that was tried
- `source_ip` — the client IP address

The attempted password is **never** logged.

---

## Seeding Policy

The application never seeds data automatically on startup. Seeding is an explicit operator action.

**Conditions required to run the seed script:**
- `ENVIRONMENT=development` — seeding is blocked in any other environment
- `DEV_SEED=true` — explicit opt-in required
- `DEV_ADMIN_PASSWORD` — caller-supplied password for the admin account

If any condition is not met, the script exits with a descriptive error. No account is created silently.

**What is never done:**
- No hardcoded passwords anywhere in the codebase
- No generated passwords printed to structured logs
- No automatic seeding from `api/main.py` startup
- No automatic seeding from `docker-entrypoint.sh`

**Recommended dev workflow:**
```bash
export DEV_ADMIN_PASSWORD='your-secure-password'
make seed-dev
```

---

## CSRF Protection

The API uses HTTP-only session cookies for authentication. To prevent cross-site request forgery, a server-side origin validation middleware (`api/middleware/csrf.py`) is applied to all state-changing requests.

### How it works

On every `POST`, `PUT`, `PATCH`, or `DELETE` request the middleware reads the `Origin` header (falling back to `Referer` for older clients) and rejects the request with HTTP 403 if the origin is not in the `CORS_ORIGINS` allowlist.

Requests with no `Origin` or `Referer` header are allowed through — these are non-browser clients (curl, Postman, internal services) that cannot be exploited via CSRF.

### Exempt paths

The following paths are exempt because no session cookie exists at the time of the request:

| Path | Reason |
|------|--------|
| `POST /api/v1/auth/login` | Session does not exist yet |
| `POST /api/v1/agent/auth/login` | Session does not exist yet |
| `POST /api/v1/agent/auth/signup` | Session does not exist yet |
| `/api/v1/public/*` | Unauthenticated public form submission |
| `/api/v1/health`, `/metrics` | Read-only, no session required |

### Relationship to SameSite cookies

In production (`ENVIRONMENT=production`) cookies are set with `SameSite=strict` and `Secure=True`. Origin validation is a belt-and-suspenders layer that remains effective if the deployment topology changes (e.g. API and frontend on different subdomains, or a reverse proxy that strips cookie flags).

### Configuration

The allowlist is driven by the `CORS_ORIGINS` environment variable. Wildcard origins (`*`) are explicitly rejected by the middleware — a wildcard would defeat the purpose of origin validation.

---

## HTTP Security Headers

The following headers are set on every API response:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

---

## Rate Limiting

Login endpoints are rate-limited to **10 requests per minute per IP address**:

- `POST /api/v1/auth/login`
- `POST /api/v1/agent/auth/login`

Requests exceeding the limit receive HTTP 429 with the standard error response schema.

---

## Role-Based Access Control (RBAC)

All platform-admin endpoints (`/api/v1/admin/*`) require the `platform_admin` role. All agent-app endpoints (`/api/v1/agent/*`) require the `agent` role. Requests with the wrong role receive HTTP 403.

---

## Input Sanitization

All user-supplied string inputs for lead fields (`name`, `email`, `notes`) are sanitized with `bleach.clean(value, tags=[], strip=True)` before being stored, preventing stored XSS.

---

## Reporting Vulnerabilities

If you discover a security vulnerability, please **do not open a public GitHub issue**.

Instead, report it privately:

1. Email the maintainers at `security@your-org.example` with the subject line `[SECURITY] <brief description>`.
2. Include:
   - A description of the vulnerability and its potential impact
   - Steps to reproduce or a proof-of-concept (redact any real credentials)
   - The affected version or commit hash
3. You will receive an acknowledgement within 48 hours and a resolution timeline within 7 days.

We follow responsible disclosure — please give us reasonable time to patch before public disclosure.

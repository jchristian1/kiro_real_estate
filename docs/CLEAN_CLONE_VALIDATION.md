# Clean Clone Validation

## Result: PASS

| Field | Value |
|-------|-------|
| Date | 2026-03-13 |
| Validated by | `scripts/validate_clean_clone.sh` |
| Environment | macOS (darwin), Docker Desktop 4.x |
| Time to healthy | ~45s |
| Known issues | None |

## Steps Performed

1. Cloned repository to a temporary directory via `git clone --depth 1`.
2. Copied `.env.example` → `.env` and injected generated secrets using `openssl rand -hex 32` for both `ENCRYPTION_KEY` and `SECRET_KEY`.
3. Ran `docker compose up --build -d` — built the `api` and `frontend` images and started both containers.
4. Polled `GET http://localhost:8000/api/v1/health` every 5 seconds.
5. Health endpoint returned `{"status": "healthy", ...}` at ~45s — within the 120s timeout.

## Health Response

```json
{
  "status": "healthy",
  "database": "connected",
  "active_watchers": 0,
  "errors_last_24h": 0,
  "watchers": {}
}
```

## Known Issues

None. The system starts cleanly on a fresh clone with no manual intervention required beyond copying `.env.example` and generating secrets.

## Re-running Validation

```bash
# From the repository root
scripts/validate_clean_clone.sh

# Or against a specific remote URL
scripts/validate_clean_clone.sh https://github.com/your-org/your-repo.git
```

The script exits 0 on PASS and 1 on FAIL, printing container logs on failure to aid diagnosis.

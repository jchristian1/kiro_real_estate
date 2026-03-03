# API Services

This directory contains background services and utilities for the Web UI & API Layer.

## Session Cleanup Service

The session cleanup service automatically removes expired sessions from the database to prevent accumulation of stale session records.

### Features

- **Automatic cleanup**: Runs periodically in the background
- **Configurable interval**: Default 1 hour, can be customized
- **Graceful shutdown**: Properly stops when application shuts down
- **Error handling**: Continues running even if individual cleanup operations fail
- **Logging**: Comprehensive logging of cleanup operations

### Usage

#### Basic Usage in FastAPI Application

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.orm import Session
from api.services import SessionCleanupManager

# Database session factory
def get_db_session():
    """Context manager that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create cleanup manager
cleanup_manager = SessionCleanupManager(
    get_db_session=get_db_session,
    interval_seconds=3600  # Run every hour
)

# Application lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start session cleanup
    cleanup_manager.start()
    yield
    # Shutdown: Stop session cleanup
    await cleanup_manager.stop()

# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)
```

#### Manual Cleanup

You can also manually trigger cleanup operations:

```python
from api.services import cleanup_expired_sessions
from database import SessionLocal

# Manual cleanup
with SessionLocal() as db:
    deleted_count = await cleanup_expired_sessions(db)
    print(f"Deleted {deleted_count} expired sessions")
```

#### Custom Cleanup Interval

```python
# Run cleanup every 30 minutes
cleanup_manager = SessionCleanupManager(
    get_db_session=get_db_session,
    interval_seconds=1800  # 30 minutes
)
```

#### Checking Status

```python
# Check if cleanup task is running
if cleanup_manager.is_running():
    print("Session cleanup is active")
else:
    print("Session cleanup is not running")
```

### Configuration

The cleanup service can be configured via environment variables or directly in code:

- **Cleanup Interval**: Time between cleanup operations (default: 3600 seconds / 1 hour)
- **Session Expiry**: Session expiration time is configured in `api/auth.py` (default: 24 hours)

### How It Works

1. **Background Task**: The cleanup manager runs an asyncio background task
2. **Periodic Execution**: Task sleeps for the configured interval between cleanups
3. **Database Query**: Queries for sessions where `expires_at < current_time`
4. **Deletion**: Deletes all expired sessions in a single transaction
5. **Logging**: Logs the number of sessions deleted (or 0 if none)
6. **Error Handling**: Catches and logs errors, continues running

### Session Expiration

Sessions expire based on the `expires_at` timestamp:
- Set to 24 hours from creation by default
- Can be configured via `SESSION_EXPIRY_HOURS` in `api/auth.py`
- Sliding window: `last_accessed` is updated on each validation

### Testing

Comprehensive unit tests are available in `tests/unit/test_session_cleanup.py`:

```bash
# Run session cleanup tests
pytest tests/unit/test_session_cleanup.py -v

# Run with coverage
pytest tests/unit/test_session_cleanup.py --cov=api.services.session_cleanup
```

### Logging

The cleanup service logs the following events:

- **INFO**: Task start/stop, successful cleanups with count
- **DEBUG**: No expired sessions to clean up
- **WARNING**: Task not running when stop is called, graceful stop timeout
- **ERROR**: Errors during cleanup operations

Example log output:

```
INFO: Session cleanup task started (interval: 3600s)
INFO: Cleaned up 5 expired sessions
INFO: Session cleanup completed: 5 sessions removed
INFO: Session cleanup task stopped
```

### Performance Considerations

- **Database Load**: Cleanup queries are simple and indexed on `expires_at`
- **Transaction Size**: All expired sessions deleted in a single transaction
- **Interval**: Default 1-hour interval balances cleanup frequency with database load
- **Async**: Runs in background without blocking API requests

### Security

- **No Data Exposure**: Only deletes expired sessions, no data returned
- **Transaction Safety**: Uses database transactions for consistency
- **Error Isolation**: Errors in cleanup don't affect API operations

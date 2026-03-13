"""
Public health check endpoint — no authentication required.

GET /health  (mounted at /api/v1/health in main.py)

Returns system status including database connectivity, active watcher count,
errors in the last 24 hours, and per-agent watcher heartbeats.

Response schema:
    {
        "status": "healthy" | "degraded",
        "database": "connected" | "error",
        "active_watchers": int,
        "errors_last_24h": int,
        "watchers": {
            "<agent_id>": {
                "status": str,
                "last_heartbeat": str | null
            }
        }
    }

HTTP 200 when healthy or degraded-but-reachable.
HTTP 503 when the database is unreachable.

Requirements: 1.6, 2.3, 2.5
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class WatcherEntry(BaseModel):
    status: str
    last_heartbeat: Optional[str]


class HealthResponse(BaseModel):
    status: str                          # "healthy" | "degraded"
    database: str                        # "connected" | "error"
    active_watchers: int
    errors_last_24h: int
    watchers: Dict[str, WatcherEntry]


# ---------------------------------------------------------------------------
# Dependencies (imported lazily to avoid circular imports)
# ---------------------------------------------------------------------------

def get_db():
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_watcher_registry():
    from api.main import watcher_registry
    return watcher_registry


# Keep private aliases for backward compatibility
_get_db = get_db
_get_registry = get_watcher_registry


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: Session = Depends(get_db),
    registry=Depends(get_watcher_registry),
):
    """
    Public health check — no authentication required.

    Returns HTTP 200 with status "healthy" or "degraded" when the database
    is reachable.  Returns HTTP 503 when the database is unreachable.

    Requirements: 1.6, 2.3, 2.5
    """
    # ------------------------------------------------------------------
    # 1. Database connectivity
    # ------------------------------------------------------------------
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.error("Health check: database unreachable: %s", exc, exc_info=True)

    database_str = "connected" if db_ok else "error"

    # If DB is down return 503 immediately — no point querying further.
    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "error",
                "active_watchers": 0,
                "errors_last_24h": 0,
                "watchers": {},
            },
        )

    # ------------------------------------------------------------------
    # 2. Watcher info from WatcherRegistry
    # ------------------------------------------------------------------
    try:
        all_statuses = await registry.get_all_statuses()
    except Exception as exc:
        logger.error("Health check: could not retrieve watcher statuses: %s", exc, exc_info=True)
        all_statuses = {}

    active_watchers = 0
    watchers: Dict[str, WatcherEntry] = {}

    for agent_id, info in all_statuses.items():
        status_str = info.get("status", "unknown")
        last_heartbeat = info.get("last_heartbeat")  # already ISO string or None
        if status_str == "running":
            active_watchers += 1
        watchers[agent_id] = WatcherEntry(
            status=status_str,
            last_heartbeat=last_heartbeat,
        )

    # ------------------------------------------------------------------
    # 3. Error count from the last 24 hours (via AuditRepository)
    # ------------------------------------------------------------------
    errors_last_24h = 0
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        audit_repo = AuditRepository(db)
        errors_last_24h = audit_repo.count_errors_since(cutoff)
    except Exception as exc:
        logger.error("Health check: could not query error count: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # 4. Overall status
    # ------------------------------------------------------------------
    failed_watchers = sum(
        1 for info in all_statuses.values() if info.get("status") == "failed"
    )
    if failed_watchers > 0 or errors_last_24h > 50:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return HealthResponse(
        status=overall_status,
        database=database_str,
        active_watchers=active_watchers,
        errors_last_24h=errors_last_24h,
        watchers=watchers,
    )

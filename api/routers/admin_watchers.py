"""
Watcher control API endpoints (Phase 5C — DB-backed coordination).

The watcher runtime lives in the worker process. The API coordinates with
it through two DB tables:
  - watcher_control: API writes desired state; worker reconciles
  - watcher_status:  Worker writes live status; API reads for status endpoint

Endpoints:
- POST /api/v1/watchers/{agent_id}/start  — set desired_status=running
- POST /api/v1/watchers/{agent_id}/stop   — set desired_status=stopped
- POST /api/v1/watchers/{agent_id}/sync   — request immediate sync
- GET  /api/v1/watchers/status            — read live status from DB

Requirements:
- 4.1: Provide endpoints for starting, stopping, and triggering sync operations
- 4.5: Execute single sync operation when manual sync is triggered
- 4.6: Display real-time Watcher status for each Agent
- 4.7: Track Watcher heartbeats and last sync timestamps
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from api.dependencies.auth import require_role
from api.dependencies.db import get_db
from api.exceptions import NotFoundException
from api.models.error_models import ErrorCode
from api.models.web_ui_models import User
from api.models.watcher_models import (
    WatcherStartResponse,
    WatcherStatusListResponse,
    WatcherStatusResponse,
    WatcherStopResponse,
    WatcherSyncResponse,
)
from api.repositories import CredentialRepository
from api.repositories.watcher_coordination_repository import (
    WatcherControlRepository,
    WatcherStatusRepository,
)
from api.services.audit_log import record_audit_log


router = APIRouter(dependencies=[Depends(require_role("company_admin"))])


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authentication dependency."""
    from api.auth import get_current_user as _auth
    return _auth(request, db)


def _assert_agent_access(agent_id: str, current_user: User, db: Session) -> None:
    """
    Validate that the authenticated user can access the specified agent.

    Platform admins can access all agents. Company-scoped admins can only
    access agents in their own company.
    """
    if getattr(current_user, "role", None) in ("admin", "platform_admin"):
        return

    cred_repo = CredentialRepository(db)
    credentials = cred_repo.get_by_agent_id(agent_id)

    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    if credentials.company_id != current_user.company_id:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )


def _require_agent_credentials(agent_id: str, db: Session):
    """Return credentials or raise 404."""
    cred_repo = CredentialRepository(db)
    credentials = cred_repo.get_by_agent_id(agent_id)
    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    return credentials


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------


@router.post(
    "/watchers/{agent_id}/start",
    response_model=WatcherStartResponse,
    status_code=status.HTTP_200_OK,
)
async def start_watcher(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Request the worker to start a watcher for the specified agent.

    Sets desired_status=running in watcher_control. The worker will
    start the watcher on its next reconciliation cycle (~10s).

    Requirements: 4.1, 4.2, 4.4, 4.8, 6.1, 6.2
    """
    _assert_agent_access(agent_id, current_user, db)
    credentials = _require_agent_credentials(agent_id, db)

    ctrl_repo = WatcherControlRepository(db)
    ctrl_repo.set_desired_status(agent_id, "running")

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="watcher_start_requested",
        resource_type="watcher",
        resource_id=credentials.id,
        details=f"Requested watcher start for agent {agent_id}",
    )

    # Return current DB status (may still show stopped until worker reconciles)
    status_repo = WatcherStatusRepository(db)
    status_row = status_repo.get(agent_id)
    current_status = status_row.status if status_row else "starting"
    started_at = (
        status_row.started_at.isoformat() + "Z"
        if status_row and status_row.started_at
        else datetime.utcnow().isoformat() + "Z"
    )

    return WatcherStartResponse(
        agent_id=agent_id,
        status=current_status,
        started_at=started_at,
        message=f"Watcher start requested for agent '{agent_id}'. Worker will start it shortly.",
    )


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------


@router.post(
    "/watchers/{agent_id}/stop",
    response_model=WatcherStopResponse,
    status_code=status.HTTP_200_OK,
)
async def stop_watcher(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Request the worker to stop a watcher for the specified agent.

    Sets desired_status=stopped in watcher_control. The worker will
    stop the watcher on its next reconciliation cycle (~10s).

    Requirements: 4.1, 4.3, 4.8, 6.1, 6.2
    """
    _assert_agent_access(agent_id, current_user, db)
    credentials = _require_agent_credentials(agent_id, db)

    ctrl_repo = WatcherControlRepository(db)
    ctrl_repo.set_desired_status(agent_id, "stopped")

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="watcher_stop_requested",
        resource_type="watcher",
        resource_id=credentials.id,
        details=f"Requested watcher stop for agent {agent_id}",
    )

    return WatcherStopResponse(
        agent_id=agent_id,
        status="stopping",
        message=f"Watcher stop requested for agent '{agent_id}'. Worker will stop it shortly.",
    )


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


@router.post(
    "/watchers/{agent_id}/sync",
    response_model=WatcherSyncResponse,
    status_code=status.HTTP_200_OK,
)
async def trigger_sync(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Request an immediate sync for the specified agent.

    Sets sync_requested_at in watcher_control. The worker will trigger
    an immediate sync cycle on its next reconciliation pass (~10s).

    Requirements: 4.1, 4.5, 4.8, 6.1, 6.2
    """
    _assert_agent_access(agent_id, current_user, db)
    credentials = _require_agent_credentials(agent_id, db)

    ctrl_repo = WatcherControlRepository(db)
    ctrl_repo.request_sync(agent_id)

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="watcher_sync_requested",
        resource_type="watcher",
        resource_id=credentials.id,
        details=f"Requested manual sync for agent {agent_id}",
    )

    timestamp = datetime.now(timezone.utc).isoformat()

    return WatcherSyncResponse(
        agent_id=agent_id,
        sync_triggered=True,
        timestamp=timestamp,
        message=f"Sync requested for agent '{agent_id}'. Worker will execute it shortly.",
    )


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get(
    "/watchers/status",
    response_model=WatcherStatusListResponse,
    status_code=status.HTTP_200_OK,
)
async def get_all_watcher_statuses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the live status of all watchers from the DB.

    Reads from watcher_status table written by the worker process.
    Status is eventually-consistent (updated every ~10s by the worker).

    Requirements: 4.6, 4.7
    """
    status_repo = WatcherStatusRepository(db)
    rows = status_repo.list_all()

    watchers = [
        WatcherStatusResponse(
            agent_id=row.agent_id,
            status=row.status,
            last_heartbeat=row.last_heartbeat.isoformat() + "Z" if row.last_heartbeat else None,
            last_sync=row.last_sync.isoformat() + "Z" if row.last_sync else None,
            error=row.error,
            started_at=row.started_at.isoformat() + "Z" if row.started_at else None,
        )
        for row in rows
    ]

    return WatcherStatusListResponse(watchers=watchers)

"""
Settings management API endpoints.

Endpoints:
- GET /api/v1/settings - Retrieve all settings
- PUT /api/v1/settings - Update settings (partial updates supported)
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from api.models.web_ui_models import User
from api.models.settings_models import SettingsResponse, SettingsUpdateRequest
from api.services.audit_log import record_audit_log
from api.repositories.settings_repository import SettingsRepository

router = APIRouter()

DEFAULT_SETTINGS = {
    'sync_interval_seconds': '300',
    'regex_timeout_ms': '1000',
    'session_timeout_hours': '24',
    'max_leads_per_page': '50',
    'enable_auto_restart': 'true',
}


def get_db():
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    from api.auth import get_current_user as auth_get_current_user
    return auth_get_current_user(request, db)


def _build_response(repo: SettingsRepository) -> SettingsResponse:
    return SettingsResponse(
        sync_interval_seconds=int(repo.get_value('sync_interval_seconds', DEFAULT_SETTINGS['sync_interval_seconds'])),
        regex_timeout_ms=int(repo.get_value('regex_timeout_ms', DEFAULT_SETTINGS['regex_timeout_ms'])),
        session_timeout_hours=int(repo.get_value('session_timeout_hours', DEFAULT_SETTINGS['session_timeout_hours'])),
        max_leads_per_page=int(repo.get_value('max_leads_per_page', DEFAULT_SETTINGS['max_leads_per_page'])),
        enable_auto_restart=repo.get_value('enable_auto_restart', DEFAULT_SETTINGS['enable_auto_restart']).lower() == 'true',
    )


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all system settings. Requirements: 18.1"""
    return _build_response(SettingsRepository(db))


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    settings_data: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update system settings. Requirements: 18.2, 18.3, 18.4"""
    repo = SettingsRepository(db)
    updated_settings = []

    if settings_data.sync_interval_seconds is not None:
        repo.upsert('sync_interval_seconds', str(settings_data.sync_interval_seconds), current_user.id)
        updated_settings.append('sync_interval_seconds')

    if settings_data.regex_timeout_ms is not None:
        repo.upsert('regex_timeout_ms', str(settings_data.regex_timeout_ms), current_user.id)
        updated_settings.append('regex_timeout_ms')

    if settings_data.session_timeout_hours is not None:
        repo.upsert('session_timeout_hours', str(settings_data.session_timeout_hours), current_user.id)
        updated_settings.append('session_timeout_hours')

    if settings_data.max_leads_per_page is not None:
        repo.upsert('max_leads_per_page', str(settings_data.max_leads_per_page), current_user.id)
        updated_settings.append('max_leads_per_page')

    if settings_data.enable_auto_restart is not None:
        repo.upsert('enable_auto_restart', str(settings_data.enable_auto_restart).lower(), current_user.id)
        updated_settings.append('enable_auto_restart')

    if updated_settings:
        record_audit_log(
            db_session=db,
            user_id=current_user.id,
            action="settings_updated",
            resource_type="settings",
            resource_id=None,
            details=f"Updated settings: {', '.join(updated_settings)}",
        )

    return _build_response(repo)

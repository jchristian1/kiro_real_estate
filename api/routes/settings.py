"""
Settings management API endpoints.

This module provides REST API endpoints for managing system-wide configuration
settings that can be modified at runtime.

All endpoints require authentication and record audit logs for all modifications.

Endpoints:
- GET /api/v1/settings - Retrieve all settings
- PUT /api/v1/settings - Update settings (partial updates supported)
"""

from typing import Dict
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from api.models.web_ui_models import User, Setting
from api.models.settings_models import (
    SettingsResponse,
    SettingsUpdateRequest
)
from api.services.audit_log import record_audit_log


router = APIRouter()


# Default setting values
DEFAULT_SETTINGS = {
    'sync_interval_seconds': '300',
    'regex_timeout_ms': '1000',
    'session_timeout_hours': '24',
    'max_leads_per_page': '50',
    'enable_auto_restart': 'true'
}


# Dependencies that will be injected by FastAPI
def get_db():
    """Database dependency - will be overridden in tests."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authentication dependency - will be overridden in tests."""
    from api.auth import get_current_user as auth_get_current_user
    return auth_get_current_user(request, db)


def get_setting_value(db: Session, key: str, default: str) -> str:
    """
    Get a setting value from the database or return default.
    
    Args:
        db: Database session
        key: Setting key
        default: Default value if not found
        
    Returns:
        Setting value as string
    """
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        return setting.value
    return default


def upsert_setting(db: Session, key: str, value: str, user_id: int) -> None:
    """
    Insert or update a setting value.
    
    Args:
        db: Database session
        key: Setting key
        value: Setting value (as string)
        user_id: User ID performing the update
    """
    from datetime import datetime
    
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        # Update existing setting
        setting.value = value
        setting.updated_at = datetime.utcnow()
        setting.updated_by = user_id
    else:
        # Insert new setting
        setting = Setting(
            key=key,
            value=value,
            updated_at=datetime.utcnow(),
            updated_by=user_id
        )
        db.add(setting)


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all system settings.
    
    Returns all configurable settings with their current values.
    If a setting is not in the database, returns the default value.
    
    Args:
        db: Database session
        current_user: Authenticated user
        
    Returns:
        All settings with proper type conversion
        
    Requirements:
        - 18.1: Provide endpoints for reading system settings
    """
    # Retrieve all settings from database or use defaults
    sync_interval = int(get_setting_value(db, 'sync_interval_seconds', DEFAULT_SETTINGS['sync_interval_seconds']))
    regex_timeout = int(get_setting_value(db, 'regex_timeout_ms', DEFAULT_SETTINGS['regex_timeout_ms']))
    session_timeout = int(get_setting_value(db, 'session_timeout_hours', DEFAULT_SETTINGS['session_timeout_hours']))
    max_leads = int(get_setting_value(db, 'max_leads_per_page', DEFAULT_SETTINGS['max_leads_per_page']))
    auto_restart = get_setting_value(db, 'enable_auto_restart', DEFAULT_SETTINGS['enable_auto_restart']).lower() == 'true'
    
    return SettingsResponse(
        sync_interval_seconds=sync_interval,
        regex_timeout_ms=regex_timeout,
        session_timeout_hours=session_timeout,
        max_leads_per_page=max_leads,
        enable_auto_restart=auto_restart
    )


@router.put("/settings", response_model=SettingsResponse)
def update_settings(
    settings_data: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update system settings.
    
    Supports partial updates - only provided settings will be updated.
    All setting values are validated before storage.
    Records audit logs for each setting modification.
    
    Args:
        settings_data: Settings update request data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Updated settings
        
    Requirements:
        - 18.2: Provide endpoints for updating system settings
        - 18.3: Validate setting values before storage
        - 18.4: Record audit logs for settings modifications
    """
    updated_settings = []
    
    # Update each provided setting
    if settings_data.sync_interval_seconds is not None:
        upsert_setting(db, 'sync_interval_seconds', str(settings_data.sync_interval_seconds), current_user.id)
        updated_settings.append('sync_interval_seconds')
    
    if settings_data.regex_timeout_ms is not None:
        upsert_setting(db, 'regex_timeout_ms', str(settings_data.regex_timeout_ms), current_user.id)
        updated_settings.append('regex_timeout_ms')
    
    if settings_data.session_timeout_hours is not None:
        upsert_setting(db, 'session_timeout_hours', str(settings_data.session_timeout_hours), current_user.id)
        updated_settings.append('session_timeout_hours')
    
    if settings_data.max_leads_per_page is not None:
        upsert_setting(db, 'max_leads_per_page', str(settings_data.max_leads_per_page), current_user.id)
        updated_settings.append('max_leads_per_page')
    
    if settings_data.enable_auto_restart is not None:
        upsert_setting(db, 'enable_auto_restart', str(settings_data.enable_auto_restart).lower(), current_user.id)
        updated_settings.append('enable_auto_restart')
    
    # Commit all changes
    db.commit()
    
    # Record audit log for settings modification
    if updated_settings:
        record_audit_log(
            db_session=db,
            user_id=current_user.id,
            action="settings_updated",
            resource_type="settings",
            resource_id=None,
            details=f"Updated settings: {', '.join(updated_settings)}"
        )
    
    # Return updated settings
    return get_settings(db=db, current_user=current_user)

"""
Pydantic models for settings API endpoints.

This module defines request and response models for system settings
management endpoints.

All models include comprehensive input validation to ensure setting values
are within acceptable ranges.

Requirements:
- 18.1: Provide endpoints for reading system settings
- 18.2: Provide endpoints for updating system settings
- 18.3: Validate setting values before storage
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class SettingValue(BaseModel):
    """
    Model for a single setting value.
    
    Attributes:
        key: Setting key
        value: Setting value (as string, will be parsed based on key)
        updated_at: Last update timestamp
        updated_by: User ID who last updated the setting
    """
    key: str
    value: str
    updated_at: datetime
    updated_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class SettingsResponse(BaseModel):
    """
    Response model for retrieving all settings.
    
    Returns settings as key-value pairs with proper type conversion.
    
    Attributes:
        sync_interval_seconds: Default sync interval for watchers (60-3600)
        regex_timeout_ms: Regex execution timeout (100-5000)
        session_timeout_hours: Session expiration time (1-168)
        max_leads_per_page: Pagination limit (10-1000)
        enable_auto_restart: Auto-restart failed watchers
    """
    sync_interval_seconds: int
    regex_timeout_ms: int
    session_timeout_hours: int
    max_leads_per_page: int
    enable_auto_restart: bool


class SettingsUpdateRequest(BaseModel):
    """
    Request model for updating settings.
    
    All fields are optional to support partial updates.
    Each field has validation to ensure values are within acceptable ranges.
    
    Attributes:
        sync_interval_seconds: Default sync interval for watchers (60-3600)
        regex_timeout_ms: Regex execution timeout (100-5000)
        session_timeout_hours: Session expiration time (1-168)
        max_leads_per_page: Pagination limit (10-1000)
        enable_auto_restart: Auto-restart failed watchers
    """
    sync_interval_seconds: Optional[int] = Field(
        None,
        ge=60,
        le=3600,
        description="Default sync interval for watchers in seconds (60-3600)"
    )
    regex_timeout_ms: Optional[int] = Field(
        None,
        ge=100,
        le=5000,
        description="Regex execution timeout in milliseconds (100-5000)"
    )
    session_timeout_hours: Optional[int] = Field(
        None,
        ge=1,
        le=168,
        description="Session expiration time in hours (1-168, max 1 week)"
    )
    max_leads_per_page: Optional[int] = Field(
        None,
        ge=10,
        le=1000,
        description="Maximum leads per page for pagination (10-1000)"
    )
    enable_auto_restart: Optional[bool] = Field(
        None,
        description="Enable auto-restart for failed watchers"
    )

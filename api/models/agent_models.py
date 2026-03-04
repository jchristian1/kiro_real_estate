"""
Pydantic models for agent API endpoints.

This module defines request and response models for agent management
endpoints including creation, updates, and listing.

All models include comprehensive input validation and sanitization to protect
against malicious input and ensure data integrity.

Requirements:
- 1.5: Validate email format and required fields
- 10.1: Sanitize all user input before processing
- 10.4: Enforce maximum length limits on all text fields
- 10.5: Validate email addresses against RFC 5322 format
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator

from api.utils.validation import (
    validate_agent_id_field,
    validate_email_field,
    validate_password_field,
    MAX_AGENT_ID_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH
)


class AgentCreateRequest(BaseModel):
    """
    Request model for creating a new agent.
    """
    agent_id: str = Field(
        ...,
        min_length=1,
        max_length=MAX_AGENT_ID_LENGTH,
        description="Unique agent identifier (alphanumeric, hyphens, underscores, dots)"
    )
    email: EmailStr = Field(
        ...,
        max_length=MAX_EMAIL_LENGTH,
        description="Gmail email address (RFC 5322 compliant)"
    )
    app_password: str = Field(
        ...,
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH,
        description="Gmail app-specific password"
    )
    display_name: Optional[str] = Field(None, max_length=255, description="Agent display name for templates")
    phone: Optional[str] = Field(None, max_length=50, description="Agent phone number for templates")
    company_id: Optional[int] = Field(None, description="Company this agent belongs to")
    
    # Validators for sanitization and additional validation
    _validate_agent_id = validator('agent_id', allow_reuse=True)(validate_agent_id_field)
    _validate_email = validator('email', allow_reuse=True)(validate_email_field)
    _validate_password = validator('app_password', allow_reuse=True)(validate_password_field)


class AgentUpdateRequest(BaseModel):
    """
    Request model for updating an existing agent.
    """
    email: Optional[EmailStr] = Field(
        None,
        max_length=MAX_EMAIL_LENGTH,
        description="New Gmail email address (RFC 5322 compliant)"
    )
    app_password: Optional[str] = Field(
        None,
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH,
        description="New Gmail app-specific password"
    )
    display_name: Optional[str] = Field(None, max_length=255, description="Agent display name for templates")
    phone: Optional[str] = Field(None, max_length=50, description="Agent phone number for templates")
    company_id: Optional[int] = Field(None, description="Company this agent belongs to")
    
    # Validators for sanitization and additional validation
    _validate_email = validator('email', allow_reuse=True)(validate_email_field)
    _validate_password = validator('app_password', allow_reuse=True)(validate_password_field)


class AgentResponse(BaseModel):
    """
    Response model for agent details.
    
    Note: Credentials are never included in responses for security.
    """
    id: int
    agent_id: str
    email: str
    display_name: Optional[str] = None
    phone: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    watcher_status: Optional[str] = None
    
    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """
    Response model for listing agents.
    
    Attributes:
        agents: List of agent details
    """
    agents: list[AgentResponse]


class AgentDeleteResponse(BaseModel):
    """
    Response model for agent deletion.
    
    Attributes:
        message: Success message
    """
    message: str

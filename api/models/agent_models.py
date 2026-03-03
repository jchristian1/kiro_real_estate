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
    
    Includes comprehensive validation:
    - Agent ID: Alphanumeric with hyphens, underscores, dots only
    - Email: RFC 5322 compliant format (via EmailStr)
    - Password: Non-empty with sanitization
    
    All fields are sanitized to remove null bytes and control characters.
    
    Attributes:
        agent_id: Unique identifier for the agent
        email: Gmail email address (validated against RFC 5322)
        app_password: Gmail app-specific password
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
    
    # Validators for sanitization and additional validation
    _validate_agent_id = validator('agent_id', allow_reuse=True)(validate_agent_id_field)
    _validate_email = validator('email', allow_reuse=True)(validate_email_field)
    _validate_password = validator('app_password', allow_reuse=True)(validate_password_field)


class AgentUpdateRequest(BaseModel):
    """
    Request model for updating an existing agent.
    
    Includes comprehensive validation for optional fields:
    - Email: RFC 5322 compliant format (via EmailStr)
    - Password: Non-empty with sanitization
    
    All fields are sanitized to remove null bytes and control characters.
    
    Attributes:
        email: Optional new Gmail email address
        app_password: Optional new Gmail app-specific password
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
    
    # Validators for sanitization and additional validation
    _validate_email = validator('email', allow_reuse=True)(validate_email_field)
    _validate_password = validator('app_password', allow_reuse=True)(validate_password_field)


class AgentResponse(BaseModel):
    """
    Response model for agent details.
    
    Note: Credentials are never included in responses for security.
    
    Attributes:
        id: Database ID
        agent_id: Unique agent identifier
        email: Gmail email address (decrypted but safe to return)
        created_at: Creation timestamp
        updated_at: Last update timestamp
        watcher_status: Optional watcher status (running, stopped, etc.)
    """
    id: int
    agent_id: str
    email: str
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

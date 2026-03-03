"""
Pydantic models for lead source API endpoints.

This module defines request and response models for lead source management
endpoints including creation, updates, and listing.

All models include comprehensive input validation and sanitization to protect
against malicious input and ensure data integrity.

Requirements:
- 2.1: Provide endpoints for creating, reading, updating, and deleting Lead_Source records
- 2.2: Validate regex pattern syntax
- 10.1: Sanitize all user input before processing
- 10.4: Enforce maximum length limits on all text fields
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, validator
import re

from api.utils.validation import (
    sanitize_string,
    sanitize_email,
    MAX_EMAIL_LENGTH,
    MAX_TEXT_FIELD_LENGTH,
    MAX_BODY_LENGTH
)


def validate_regex_pattern(pattern: str) -> str:
    """
    Validate regex pattern syntax.
    
    Args:
        pattern: Regex pattern to validate
        
    Returns:
        Sanitized pattern
        
    Raises:
        ValueError: If regex pattern is invalid
        
    Requirements:
        - 2.2: Validate regex pattern syntax
    """
    # Sanitize the pattern
    sanitized = sanitize_string(pattern, max_length=MAX_TEXT_FIELD_LENGTH)
    
    if len(sanitized) == 0:
        raise ValueError("Regex pattern cannot be empty")
    
    # Validate regex syntax by attempting to compile
    try:
        re.compile(sanitized)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern: {str(e)}")
    
    return sanitized


class LeadSourceCreateRequest(BaseModel):
    """
    Request model for creating a new lead source.
    
    Includes comprehensive validation:
    - Sender email: RFC 5322 compliant format
    - Identifier snippet: Non-empty string
    - Name regex: Valid regex pattern
    - Phone regex: Valid regex pattern
    - Template ID: Optional integer
    - Auto respond enabled: Boolean flag
    
    All fields are sanitized to remove null bytes and control characters.
    
    Attributes:
        sender_email: Email address of the lead source sender
        identifier_snippet: Text snippet to identify lead emails
        name_regex: Regex pattern to extract lead name
        phone_regex: Regex pattern to extract lead phone
        template_id: Optional template ID for auto-responses
        auto_respond_enabled: Whether auto-response is enabled
    """
    sender_email: EmailStr = Field(
        ...,
        max_length=MAX_EMAIL_LENGTH,
        description="Email address of the lead source sender (RFC 5322 compliant)"
    )
    identifier_snippet: str = Field(
        ...,
        min_length=1,
        max_length=MAX_TEXT_FIELD_LENGTH,
        description="Text snippet to identify lead emails"
    )
    name_regex: str = Field(
        ...,
        min_length=1,
        max_length=MAX_TEXT_FIELD_LENGTH,
        description="Regex pattern to extract lead name"
    )
    phone_regex: str = Field(
        ...,
        min_length=1,
        max_length=MAX_TEXT_FIELD_LENGTH,
        description="Regex pattern to extract lead phone"
    )
    template_id: Optional[int] = Field(
        None,
        description="Optional template ID for auto-responses"
    )
    auto_respond_enabled: bool = Field(
        False,
        description="Whether auto-response is enabled"
    )
    
    # Validators for sanitization and validation
    @validator('sender_email')
    def validate_sender_email(cls, v):
        if v is None:
            return v
        return sanitize_email(v)
    
    @validator('identifier_snippet')
    def validate_identifier_snippet(cls, v):
        if v is None:
            return v
        return sanitize_string(v, max_length=MAX_TEXT_FIELD_LENGTH)
    
    @validator('name_regex')
    def validate_name_regex(cls, v):
        if v is None:
            return v
        return validate_regex_pattern(v)
    
    @validator('phone_regex')
    def validate_phone_regex(cls, v):
        if v is None:
            return v
        return validate_regex_pattern(v)


class LeadSourceUpdateRequest(BaseModel):
    """
    Request model for updating an existing lead source.
    
    All fields are optional. Includes comprehensive validation:
    - Sender email: RFC 5322 compliant format
    - Identifier snippet: Non-empty string
    - Name regex: Valid regex pattern
    - Phone regex: Valid regex pattern
    - Template ID: Optional integer
    - Auto respond enabled: Boolean flag
    
    All fields are sanitized to remove null bytes and control characters.
    
    Attributes:
        sender_email: Optional new email address
        identifier_snippet: Optional new identifier snippet
        name_regex: Optional new name regex pattern
        phone_regex: Optional new phone regex pattern
        template_id: Optional new template ID
        auto_respond_enabled: Optional new auto-respond flag
    """
    sender_email: Optional[EmailStr] = Field(
        None,
        max_length=MAX_EMAIL_LENGTH,
        description="New email address of the lead source sender"
    )
    identifier_snippet: Optional[str] = Field(
        None,
        min_length=1,
        max_length=MAX_TEXT_FIELD_LENGTH,
        description="New text snippet to identify lead emails"
    )
    name_regex: Optional[str] = Field(
        None,
        min_length=1,
        max_length=MAX_TEXT_FIELD_LENGTH,
        description="New regex pattern to extract lead name"
    )
    phone_regex: Optional[str] = Field(
        None,
        min_length=1,
        max_length=MAX_TEXT_FIELD_LENGTH,
        description="New regex pattern to extract lead phone"
    )
    template_id: Optional[int] = Field(
        None,
        description="New template ID for auto-responses"
    )
    auto_respond_enabled: Optional[bool] = Field(
        None,
        description="New auto-response enabled flag"
    )
    
    # Validators for sanitization and validation
    @validator('sender_email')
    def validate_sender_email(cls, v):
        if v is None:
            return v
        return sanitize_email(v)
    
    @validator('identifier_snippet')
    def validate_identifier_snippet(cls, v):
        if v is None:
            return v
        return sanitize_string(v, max_length=MAX_TEXT_FIELD_LENGTH)
    
    @validator('name_regex')
    def validate_name_regex(cls, v):
        if v is None:
            return v
        return validate_regex_pattern(v)
    
    @validator('phone_regex')
    def validate_phone_regex(cls, v):
        if v is None:
            return v
        return validate_regex_pattern(v)


class LeadSourceResponse(BaseModel):
    """
    Response model for lead source details.
    
    Attributes:
        id: Database ID
        sender_email: Email address of the lead source sender
        identifier_snippet: Text snippet to identify lead emails
        name_regex: Regex pattern to extract lead name
        phone_regex: Regex pattern to extract lead phone
        template_id: Optional template ID for auto-responses
        auto_respond_enabled: Whether auto-response is enabled
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: int
    sender_email: str
    identifier_snippet: str
    name_regex: str
    phone_regex: str
    template_id: Optional[int] = None
    auto_respond_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LeadSourceListResponse(BaseModel):
    """
    Response model for listing lead sources.
    
    Attributes:
        lead_sources: List of lead source details
    """
    lead_sources: list[LeadSourceResponse]


class LeadSourceDeleteResponse(BaseModel):
    """
    Response model for lead source deletion.
    
    Attributes:
        message: Success message
    """
    message: str


class RegexTestRequest(BaseModel):
    """
    Request model for testing regex patterns.
    
    Allows administrators to test regex patterns against sample text before
    deploying them in lead source configurations.
    
    Attributes:
        pattern: Regex pattern to test
        sample_text: Sample text to test the pattern against
    """
    pattern: str = Field(
        ...,
        min_length=1,
        max_length=MAX_TEXT_FIELD_LENGTH,
        description="Regex pattern to test"
    )
    sample_text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_BODY_LENGTH,
        description="Sample text to test the pattern against"
    )
    
    @validator('pattern')
    def validate_pattern(cls, v):
        if v is None:
            return v
        return validate_regex_pattern(v)
    
    @validator('sample_text')
    def validate_sample_text(cls, v):
        if v is None:
            return v
        return sanitize_string(v, max_length=MAX_BODY_LENGTH)


class RegexTestResponse(BaseModel):
    """
    Response model for regex testing results.
    
    Attributes:
        matched: Whether the pattern matched the sample text
        groups: List of captured groups (empty if no match)
        match_text: The matched text (None if no match)
    """
    matched: bool = Field(
        ...,
        description="Whether the pattern matched the sample text"
    )
    groups: list[str] = Field(
        default_factory=list,
        description="List of captured groups from the match"
    )
    match_text: Optional[str] = Field(
        None,
        description="The matched text"
    )



class RegexProfileVersionResponse(BaseModel):
    """
    Response model for regex profile version details.
    
    Attributes:
        version: Version number
        name_regex: Regex pattern to extract lead name
        phone_regex: Regex pattern to extract lead phone
        identifier_snippet: Text snippet to identify lead emails
        created_at: Creation timestamp
        created_by: User ID who created this version
    """
    version: int
    name_regex: str
    phone_regex: str
    identifier_snippet: str
    created_at: datetime
    created_by: int
    
    class Config:
        from_attributes = True


class RegexProfileVersionListResponse(BaseModel):
    """
    Response model for listing regex profile versions.
    
    Attributes:
        versions: List of version details
    """
    versions: list[RegexProfileVersionResponse]


class RegexProfileRollbackRequest(BaseModel):
    """
    Request model for rolling back to a specific regex profile version.
    
    Attributes:
        version: Version number to rollback to
    """
    version: int = Field(
        ...,
        ge=1,
        description="Version number to rollback to"
    )


class RegexProfileRollbackResponse(BaseModel):
    """
    Response model for regex profile rollback.
    
    Attributes:
        message: Success message
        new_version: New version number after rollback
        lead_source: Updated lead source details
    """
    message: str
    new_version: int
    lead_source: LeadSourceResponse

"""
Template management API request/response models.

This module defines Pydantic models for template CRUD operations including:
- Template creation and update requests
- Template response models
- Template validation (header injection, placeholders)

Requirements:
- 3.1: Provide endpoints for creating, reading, updating, and deleting Template records
- 3.2: Validate against email header injection patterns
- 3.4: Validate that all placeholders in templates are supported
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re

from api.utils.validation import sanitize_string, MAX_BODY_LENGTH


# Supported template placeholders
SUPPORTED_PLACEHOLDERS = {'{lead_name}', '{agent_name}', '{agent_phone}', '{agent_email}'}


class TemplateCreateRequest(BaseModel):
    """
    Request model for creating a new template.
    
    Validates:
    - Name: Non-empty template identifier
    - Subject: Non-empty email subject line (no newlines for header injection protection)
    - Body: Non-empty email body with only supported placeholders
    
    Requirements:
        - 3.1: Provide endpoints for creating Template records
        - 3.2: Validate against email header injection patterns
        - 3.4: Validate that all placeholders in templates are supported
    """
    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    
    @validator('name')
    def validate_name(cls, v):
        """Sanitize and validate template name."""
        return sanitize_string(v, max_length=255)
    
    @validator('subject')
    def validate_subject(cls, v):
        """
        Validate subject line for email header injection.
        
        Email header injection occurs when newline characters (\r\n, \n, \r)
        are inserted into header fields, allowing attackers to inject additional
        headers or body content.
        
        Requirements:
            - 3.2: Validate against email header injection patterns
            - 10.2: Validate Template against email header injection patterns
        """
        sanitized = sanitize_string(v, max_length=500)
        
        # Check for newline characters that could enable header injection
        if '\r' in sanitized or '\n' in sanitized:
            raise ValueError(
                'Subject line cannot contain newline characters (potential header injection)'
            )
        
        return sanitized
    
    @validator('body')
    def validate_body(cls, v):
        """
        Validate template body and placeholders.
        
        Ensures only supported placeholders are used in the template body.
        
        Requirements:
            - 3.4: Validate that all placeholders in templates are supported
            - 3.5: Display available placeholders for template creation
        """
        sanitized = sanitize_string(v, max_length=MAX_BODY_LENGTH)
        
        # Find all placeholders in the body
        found_placeholders = set(re.findall(r'\{[^}]+\}', sanitized))
        
        # Check for unsupported placeholders
        invalid = found_placeholders - SUPPORTED_PLACEHOLDERS
        if invalid:
            raise ValueError(
                f'Invalid placeholders: {", ".join(sorted(invalid))}. '
                f'Supported placeholders: {", ".join(sorted(SUPPORTED_PLACEHOLDERS))}'
            )
        
        return sanitized
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Welcome Template",
                "subject": "Thank you for your inquiry",
                "body": "Hi {lead_name},\n\nThank you for reaching out. "
                       "I'm {agent_name} and I'll be happy to assist you.\n\n"
                       "You can reach me at {agent_phone} or {agent_email}.\n\n"
                       "Best regards,\n{agent_name}"
            }
        }


class TemplateUpdateRequest(BaseModel):
    """
    Request model for updating an existing template.
    
    All fields are optional - only provided fields will be updated.
    Creates a new version when updated.
    
    Requirements:
        - 3.1: Provide endpoints for updating Template records
        - 3.6: Maintain version history for Template modifications
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    body: Optional[str] = Field(None, min_length=1)
    
    @validator('name')
    def validate_name(cls, v):
        """Sanitize and validate template name."""
        if v is None:
            return v
        return sanitize_string(v, max_length=255)
    
    @validator('subject')
    def validate_subject(cls, v):
        """Validate subject line for email header injection."""
        if v is None:
            return v
        
        sanitized = sanitize_string(v, max_length=500)
        
        # Check for newline characters
        if '\r' in sanitized or '\n' in sanitized:
            raise ValueError(
                'Subject line cannot contain newline characters (potential header injection)'
            )
        
        return sanitized
    
    @validator('body')
    def validate_body(cls, v):
        """Validate template body and placeholders."""
        if v is None:
            return v
        
        sanitized = sanitize_string(v, max_length=MAX_BODY_LENGTH)
        
        # Find all placeholders in the body
        found_placeholders = set(re.findall(r'\{[^}]+\}', sanitized))
        
        # Check for unsupported placeholders
        invalid = found_placeholders - SUPPORTED_PLACEHOLDERS
        if invalid:
            raise ValueError(
                f'Invalid placeholders: {", ".join(sorted(invalid))}. '
                f'Supported placeholders: {", ".join(sorted(SUPPORTED_PLACEHOLDERS))}'
            )
        
        return sanitized


class TemplateResponse(BaseModel):
    """
    Response model for template details.
    
    Returns complete template information including metadata.
    """
    id: int
    name: str
    subject: str
    body: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": 1,
                "name": "Welcome Template",
                "subject": "Thank you for your inquiry",
                "body": "Hi {lead_name},\n\nThank you for reaching out...",
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z"
            }
        }


class TemplateListResponse(BaseModel):
    """
    Response model for listing templates.
    
    Returns a list of all templates.
    """
    templates: list[TemplateResponse]
    
    class Config:
        schema_extra = {
            "example": {
                "templates": [
                    {
                        "id": 1,
                        "name": "Welcome Template",
                        "subject": "Thank you for your inquiry",
                        "body": "Hi {lead_name}...",
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:00:00Z"
                    }
                ]
            }
        }


class TemplateDeleteResponse(BaseModel):
    """
    Response model for template deletion.
    
    Returns a success message after deletion.
    """
    message: str
    
    class Config:
        schema_extra = {
            "example": {
                "message": "Template 'Welcome Template' deleted successfully"
            }
        }


class TemplatePreviewRequest(BaseModel):
    """
    Request model for template preview.
    
    Accepts subject and body to render with sample data.
    
    Requirements:
        - 13.1: Provide endpoint for rendering Template preview with sample data
        - 13.2: Substitute all placeholders with sample values
    """
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    
    @validator('subject')
    def validate_subject(cls, v):
        """Validate subject line for email header injection."""
        sanitized = sanitize_string(v, max_length=500)
        
        # Check for newline characters
        if '\r' in sanitized or '\n' in sanitized:
            raise ValueError(
                'Subject line cannot contain newline characters (potential header injection)'
            )
        
        return sanitized
    
    @validator('body')
    def validate_body(cls, v):
        """Validate template body and placeholders."""
        sanitized = sanitize_string(v, max_length=MAX_BODY_LENGTH)
        
        # Find all placeholders in the body
        found_placeholders = set(re.findall(r'\{[^}]+\}', sanitized))
        
        # Check for unsupported placeholders
        invalid = found_placeholders - SUPPORTED_PLACEHOLDERS
        if invalid:
            raise ValueError(
                f'Invalid placeholders: {", ".join(sorted(invalid))}. '
                f'Supported placeholders: {", ".join(sorted(SUPPORTED_PLACEHOLDERS))}'
            )
        
        return sanitized
    
    class Config:
        schema_extra = {
            "example": {
                "subject": "Thank you {lead_name}",
                "body": "Hi {lead_name},\n\nThank you for reaching out. "
                       "I'm {agent_name} and I'll be happy to assist you.\n\n"
                       "You can reach me at {agent_phone} or {agent_email}."
            }
        }


class TemplatePreviewResponse(BaseModel):
    """
    Response model for template preview.
    
    Returns rendered template with sample data substituted.
    
    Requirements:
        - 13.2: Substitute all placeholders with sample values
        - 10.7: Escape HTML content in user-generated text
    """
    subject: str
    body: str
    
    class Config:
        schema_extra = {
            "example": {
                "subject": "Thank you John Doe",
                "body": "Hi John Doe,\n\nThank you for reaching out. "
                       "I'm Agent Smith and I'll be happy to assist you.\n\n"
                       "You can reach me at 555-9999 or agent@example.com."
            }
        }


class TemplateVersionResponse(BaseModel):
    """
    Response model for template version details.
    
    Attributes:
        version: Version number
        name: Template name at this version
        subject: Template subject at this version
        body: Template body at this version
        created_at: Creation timestamp
        created_by: User ID who created this version
    """
    version: int
    name: str
    subject: str
    body: str
    created_at: datetime
    created_by: int
    
    class Config:
        from_attributes = True


class TemplateVersionListResponse(BaseModel):
    """
    Response model for listing template versions.
    
    Attributes:
        versions: List of version details
    """
    versions: list[TemplateVersionResponse]


class TemplateRollbackRequest(BaseModel):
    """
    Request model for rolling back to a specific template version.
    
    Attributes:
        version: Version number to rollback to
    """
    version: int = Field(
        ...,
        ge=1,
        description="Version number to rollback to"
    )


class TemplateRollbackResponse(BaseModel):
    """
    Response model for template rollback.
    
    Attributes:
        message: Success message
        new_version: New version number after rollback
        template: Updated template details
    """
    message: str
    new_version: int
    template: TemplateResponse


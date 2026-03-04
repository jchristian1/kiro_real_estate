"""
Input validation and sanitization utilities for the API layer.

This module provides comprehensive input validation and sanitization functions
to protect against malicious input, injection attacks, and data integrity issues.

Requirements:
- 10.1: Sanitize all user input before processing
- 10.4: Enforce maximum length limits on all text fields
- 10.5: Validate email addresses against RFC 5322 format
"""

import re
from typing import Optional
from pydantic import validator


# Maximum length limits for various fields
MAX_AGENT_ID_LENGTH = 255
MAX_EMAIL_LENGTH = 320  # RFC 5321 maximum email length
MAX_PASSWORD_LENGTH = 1000  # App passwords can be long
MAX_TEXT_FIELD_LENGTH = 500
MAX_BODY_LENGTH = 10000


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a string input by removing potentially dangerous characters.
    
    Removes:
    - Null bytes (\x00) which can cause string processing issues
    - Other control characters (except newlines and tabs)
    - Leading and trailing whitespace
    
    Args:
        value: String to sanitize
        max_length: Optional maximum length to enforce
        
    Returns:
        Sanitized string
        
    Raises:
        ValueError: If string exceeds max_length after sanitization
        
    Requirements:
        - 10.1: Sanitize all user input before processing
        - 10.4: Enforce maximum length limits on all text fields
    """
    if not isinstance(value, str):
        raise ValueError("Value must be a string")
    
    # Remove null bytes
    sanitized = value.replace('\x00', '')
    
    # Remove control characters except newline (\n), carriage return (\r), and tab (\t)
    # Control characters are in the range \x00-\x1f and \x7f-\x9f
    sanitized = ''.join(
        char for char in sanitized
        if char not in ('\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07', '\x08',
                       '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12', '\x13',
                       '\x14', '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a', '\x1b',
                       '\x1c', '\x1d', '\x1e', '\x1f', '\x7f')
    )
    
    # Strip leading and trailing whitespace
    sanitized = sanitized.strip()
    
    # Enforce maximum length if specified
    if max_length is not None and len(sanitized) > max_length:
        raise ValueError(f"String exceeds maximum length of {max_length} characters")
    
    return sanitized


def sanitize_agent_id(agent_id: str) -> str:
    """
    Sanitize and validate agent ID.
    
    Agent IDs should be alphanumeric with optional hyphens, underscores, and dots.
    
    Args:
        agent_id: Agent ID to sanitize
        
    Returns:
        Sanitized agent ID
        
    Raises:
        ValueError: If agent ID is invalid or too long
        
    Requirements:
        - 10.1: Sanitize all user input before processing
        - 10.4: Enforce maximum length limits on all text fields
    """
    # First apply general sanitization
    sanitized = sanitize_string(agent_id, max_length=MAX_AGENT_ID_LENGTH)
    
    # Check if empty after sanitization
    if len(sanitized) == 0:
        raise ValueError("Agent ID cannot be empty")
    
    # Validate format: alphanumeric, hyphens, underscores, dots
    if not re.match(r'^[a-zA-Z0-9._-]+$', sanitized):
        raise ValueError(
            "Agent ID must contain only alphanumeric characters, hyphens, underscores, and dots"
        )
    
    return sanitized


def sanitize_email(email: str) -> str:
    """
    Sanitize email address.
    
    Note: Pydantic's EmailStr validator already validates against RFC 5322,
    but we still sanitize for control characters and enforce length limits.
    
    Args:
        email: Email address to sanitize
        
    Returns:
        Sanitized email address
        
    Raises:
        ValueError: If email exceeds maximum length
        
    Requirements:
        - 10.1: Sanitize all user input before processing
        - 10.4: Enforce maximum length limits on all text fields
        - 10.5: Validate email addresses against RFC 5322 format
    """
    # Apply general sanitization with email-specific max length
    sanitized = sanitize_string(email, max_length=MAX_EMAIL_LENGTH)
    
    if len(sanitized) == 0:
        raise ValueError("Email cannot be empty")
    
    return sanitized


def sanitize_password(password: str) -> str:
    """
    Sanitize password/app password.
    
    Passwords can contain various characters, but we still remove null bytes
    and enforce length limits.
    
    Args:
        password: Password to sanitize
        
    Returns:
        Sanitized password
        
    Raises:
        ValueError: If password is empty or exceeds maximum length
        
    Requirements:
        - 10.1: Sanitize all user input before processing
        - 10.4: Enforce maximum length limits on all text fields
    """
    if not isinstance(password, str):
        raise ValueError("Password must be a string")
    
    # Remove null bytes but preserve other characters (passwords can have special chars)
    sanitized = password.replace('\x00', '')
    
    # Don't strip whitespace from passwords (it might be intentional)
    
    # Enforce maximum length
    if len(sanitized) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password exceeds maximum length of {MAX_PASSWORD_LENGTH} characters")
    
    if len(sanitized) == 0:
        raise ValueError("Password cannot be empty")
    
    return sanitized


def create_string_validator(max_length: int):
    """
    Create a Pydantic validator for string fields with sanitization.
    
    This factory function creates validators that can be used in Pydantic models
    to automatically sanitize and validate string inputs.
    
    Args:
        max_length: Maximum allowed length for the string
        
    Returns:
        Validator function for use with Pydantic's @validator decorator
        
    Example:
        class MyModel(BaseModel):
            name: str
            
            _validate_name = validator('name', allow_reuse=True)(
                create_string_validator(max_length=255)
            )
    """
    def validate_string(cls, v):
        if v is None:
            return v
        return sanitize_string(v, max_length=max_length)
    
    return validate_string


# Pydantic validators for common fields
def validate_agent_id_field(cls, v):
    """Pydantic validator for agent_id fields."""
    if v is None:
        return v
    return sanitize_agent_id(v)


def validate_email_field(cls, v):
    """Pydantic validator for email fields (used after EmailStr validation)."""
    if v is None:
        return v
    return sanitize_email(v)


def validate_password_field(cls, v):
    """Pydantic validator for password fields."""
    if v is None or v == '':
        return None
    return sanitize_password(v)

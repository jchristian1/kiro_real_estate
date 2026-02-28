"""
Pydantic validation models for Gmail Lead Sync Engine.

This module provides validation models for lead data, lead source configuration,
and template configuration. All models enforce data integrity before database
insertion.
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
import re


class LeadData(BaseModel):
    """
    Validation model for lead information extracted from emails.
    
    Validates:
    - Name: Non-empty string with whitespace stripped
    - Phone: Contains at least 7 digits with formatting characters allowed
    - Source email: Valid email address format
    """
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=7, max_length=50)
    source_email: EmailStr
    
    @validator('phone')
    def validate_phone(cls, v):
        """
        Validate phone number format.
        
        Rules:
        - Allow digits, spaces, hyphens, parentheses, and optional + prefix
        - Must contain at least 7 digits (excluding formatting characters)
        
        Args:
            v: Phone number string to validate
            
        Returns:
            Validated phone number string
            
        Raises:
            ValueError: If phone format is invalid or has fewer than 7 digits
        """
        # Pattern: ^\+?[\d\s\-\(\)]+$
        # - ^\+? : Optional + prefix for international numbers
        # - [\d\s\-\(\)]+ : One or more digits, spaces, hyphens, or parentheses
        # - $ : End of string
        if not re.match(r'^\+?[\d\s\-\(\)]+$', v):
            raise ValueError('Phone must contain only digits and formatting characters')
        
        # Ensure at least 7 digits (strip all non-digit characters)
        digits = re.sub(r'\D', '', v)
        if len(digits) < 7:
            raise ValueError('Phone must contain at least 7 digits')
        
        return v
    
    @validator('name')
    def validate_name(cls, v):
        """
        Validate and normalize name field.
        
        Strips leading and trailing whitespace from the name.
        
        Args:
            v: Name string to validate
            
        Returns:
            Name with whitespace stripped
        """
        return v.strip()


class LeadSourceConfig(BaseModel):
    """
    Validation model for lead source configuration.
    
    Validates:
    - Sender email: Valid email address format
    - Identifier snippet: Non-empty string to verify email relevance
    - Name regex: Valid regex pattern for extracting lead name
    - Phone regex: Valid regex pattern for extracting phone number
    - Template ID: Optional reference to response template
    - Auto-respond enabled: Boolean flag for automated responses
    """
    sender_email: EmailStr
    identifier_snippet: str = Field(..., min_length=1, max_length=500)
    name_regex: str = Field(..., min_length=1, max_length=500)
    phone_regex: str = Field(..., min_length=1, max_length=500)
    template_id: Optional[int] = None
    auto_respond_enabled: bool = False
    
    @validator('name_regex', 'phone_regex')
    def validate_regex(cls, v):
        """
        Validate regex pattern syntax.
        
        Ensures the regex pattern can be compiled without errors.
        
        Args:
            v: Regex pattern string to validate
            
        Returns:
            Validated regex pattern string
            
        Raises:
            ValueError: If regex pattern has invalid syntax
        """
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f'Invalid regex pattern: {e}')
        return v


class TemplateConfig(BaseModel):
    """
    Validation model for email response templates.
    
    Validates:
    - Name: Non-empty template identifier
    - Subject: Non-empty email subject line
    - Body: Non-empty email body with only supported placeholders
    
    Supported placeholders:
    - {lead_name}: Extracted lead name
    - {agent_name}: Agent's name from configuration
    - {agent_phone}: Agent's phone number
    - {agent_email}: Agent's email address
    """
    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    
    @validator('body')
    def validate_placeholders(cls, v):
        """
        Validate template placeholders.
        
        Ensures only supported placeholders are used in the template body.
        
        Args:
            v: Template body string to validate
            
        Returns:
            Validated template body string
            
        Raises:
            ValueError: If unsupported placeholders are found
        """
        allowed_placeholders = {'{lead_name}', '{agent_name}', '{agent_phone}', '{agent_email}'}
        # Pattern: \{[^}]+\} matches any text within curly braces
        found_placeholders = set(re.findall(r'\{[^}]+\}', v))
        invalid = found_placeholders - allowed_placeholders
        if invalid:
            raise ValueError(f'Invalid placeholders: {invalid}. Allowed: {allowed_placeholders}')
        return v

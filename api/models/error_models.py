"""
Error response models for structured API error handling.

This module defines Pydantic models for consistent error responses across
all API endpoints. Error responses include error codes, messages, and
optional details for debugging.

Error Code Categories:
- AUTH_xxx: Authentication and authorization errors (401, 403)
- VALIDATION_xxx: Input validation errors (400, 422)
- NOT_FOUND_xxx: Resource not found errors (404)
- CONFLICT_xxx: Resource conflict errors (409)
- INTERNAL_xxx: Internal server errors (500)
- TIMEOUT_xxx: Operation timeout errors (408)
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """
    Detailed error information for a specific field or validation error.
    
    Attributes:
        field: The field name that caused the error (optional)
        message: Human-readable error message
        code: Machine-readable error code
    """
    field: Optional[str] = Field(None, description="Field name that caused the error")
    message: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code")


class ErrorResponse(BaseModel):
    """
    Standard error response model for all API errors.
    
    This model provides a consistent structure for error responses across
    all endpoints, making it easier for clients to handle errors uniformly.
    
    Attributes:
        error: High-level error category (e.g., "Validation Error", "Not Found")
        message: Human-readable error message for end users
        code: Machine-readable error code for programmatic handling
        details: Optional list of detailed error information
        request_id: Optional request ID for tracking (future enhancement)
    
    Example:
        {
            "error": "Validation Error",
            "message": "Invalid email format",
            "code": "VALIDATION_EMAIL_FORMAT",
            "details": [
                {
                    "field": "email",
                    "message": "Email must be a valid RFC 5322 address",
                    "code": "INVALID_EMAIL"
                }
            ]
        }
    """
    error: str = Field(..., description="High-level error category")
    message: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code")
    details: Optional[List[ErrorDetail]] = Field(None, description="Detailed error information")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")


# Common error codes
class ErrorCode:
    """
    Standard error codes used across the API.
    
    These codes provide machine-readable identifiers for different error
    conditions, enabling clients to handle specific errors programmatically.
    """
    
    # Authentication errors (401)
    AUTH_NOT_AUTHENTICATED = "AUTH_NOT_AUTHENTICATED"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_SESSION_EXPIRED = "AUTH_SESSION_EXPIRED"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    
    # Authorization errors (403)
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_INSUFFICIENT_PERMISSIONS"
    
    # Validation errors (400, 422)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    VALIDATION_EMAIL_FORMAT = "VALIDATION_EMAIL_FORMAT"
    VALIDATION_REGEX_SYNTAX = "VALIDATION_REGEX_SYNTAX"
    VALIDATION_REGEX_TIMEOUT = "VALIDATION_REGEX_TIMEOUT"
    VALIDATION_TEMPLATE_INJECTION = "VALIDATION_TEMPLATE_INJECTION"
    VALIDATION_INVALID_PLACEHOLDER = "VALIDATION_INVALID_PLACEHOLDER"
    VALIDATION_REQUIRED_FIELD = "VALIDATION_REQUIRED_FIELD"
    VALIDATION_MAX_LENGTH = "VALIDATION_MAX_LENGTH"
    VALIDATION_INVALID_VALUE = "VALIDATION_INVALID_VALUE"
    
    # Not found errors (404)
    NOT_FOUND_RESOURCE = "NOT_FOUND_RESOURCE"
    NOT_FOUND_AGENT = "NOT_FOUND_AGENT"
    NOT_FOUND_LEAD_SOURCE = "NOT_FOUND_LEAD_SOURCE"
    NOT_FOUND_TEMPLATE = "NOT_FOUND_TEMPLATE"
    NOT_FOUND_LEAD = "NOT_FOUND_LEAD"
    NOT_FOUND_USER = "NOT_FOUND_USER"
    NOT_FOUND_SESSION = "NOT_FOUND_SESSION"
    
    # Conflict errors (409)
    CONFLICT_RESOURCE_EXISTS = "CONFLICT_RESOURCE_EXISTS"
    CONFLICT_WATCHER_RUNNING = "CONFLICT_WATCHER_RUNNING"
    CONFLICT_DUPLICATE_AGENT = "CONFLICT_DUPLICATE_AGENT"
    
    # Internal errors (500)
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    INTERNAL_DATABASE_ERROR = "INTERNAL_DATABASE_ERROR"
    INTERNAL_ENCRYPTION_ERROR = "INTERNAL_ENCRYPTION_ERROR"
    INTERNAL_WATCHER_ERROR = "INTERNAL_WATCHER_ERROR"
    
    # Timeout errors (408)
    TIMEOUT_REGEX_EXECUTION = "TIMEOUT_REGEX_EXECUTION"
    TIMEOUT_OPERATION = "TIMEOUT_OPERATION"


def create_error_response(
    error: str,
    message: str,
    code: str,
    details: Optional[List[Dict[str, Any]]] = None,
    request_id: Optional[str] = None
) -> ErrorResponse:
    """
    Helper function to create standardized error responses.
    
    Args:
        error: High-level error category
        message: Human-readable error message
        code: Machine-readable error code
        details: Optional list of detailed error information
        request_id: Optional request ID for tracking
    
    Returns:
        ErrorResponse: Structured error response
    
    Example:
        >>> error = create_error_response(
        ...     error="Validation Error",
        ...     message="Invalid email format",
        ...     code=ErrorCode.VALIDATION_EMAIL_FORMAT,
        ...     details=[{
        ...         "field": "email",
        ...         "message": "Email must be valid",
        ...         "code": "INVALID_EMAIL"
        ...     }]
        ... )
    """
    error_details = None
    if details:
        error_details = [ErrorDetail(**detail) for detail in details]
    
    return ErrorResponse(
        error=error,
        message=message,
        code=code,
        details=error_details,
        request_id=request_id
    )

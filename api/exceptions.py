"""
Custom exception classes for the Gmail Lead Sync API.

This module defines custom exceptions that map to specific HTTP status codes
and error responses. These exceptions can be raised throughout the application
and will be handled by the global exception handler to return structured
error responses.

Usage:
    from api.exceptions import ValidationException, NotFoundException
    
    # Raise validation error
    raise ValidationException(
        message="Invalid email format",
        code=ErrorCode.VALIDATION_EMAIL_FORMAT,
        details=[{"field": "email", "message": "Must be valid RFC 5322 address"}]
    )
    
    # Raise not found error
    raise NotFoundException(
        message="Agent not found",
        code=ErrorCode.NOT_FOUND_AGENT
    )
"""

from typing import Optional, List, Dict, Any


class APIException(Exception):
    """
    Base exception class for all API exceptions.
    
    All custom exceptions should inherit from this class to ensure
    consistent error handling across the application.
    
    Attributes:
        message: Human-readable error message
        code: Machine-readable error code
        status_code: HTTP status code
        details: Optional list of detailed error information
    """
    
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 500,
        details: Optional[List[Dict[str, Any]]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(self.message)


class AuthenticationException(APIException):
    """
    Exception for authentication failures (401).
    
    Raised when a user fails to authenticate or provides invalid credentials.
    
    Example:
        raise AuthenticationException(
            message="Invalid credentials",
            code=ErrorCode.AUTH_INVALID_CREDENTIALS
        )
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTH_NOT_AUTHENTICATED",
        details: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=401,
            details=details
        )


class AuthorizationException(APIException):
    """
    Exception for authorization failures (403).
    
    Raised when an authenticated user lacks permissions for an operation.
    
    Example:
        raise AuthorizationException(
            message="Insufficient permissions",
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS
        )
    """
    
    def __init__(
        self,
        message: str = "Access forbidden",
        code: str = "AUTH_FORBIDDEN",
        details: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=403,
            details=details
        )


class ValidationException(APIException):
    """
    Exception for validation errors (400).
    
    Raised when input validation fails (e.g., invalid email, regex syntax error).
    
    Example:
        raise ValidationException(
            message="Invalid email format",
            code=ErrorCode.VALIDATION_EMAIL_FORMAT,
            details=[{
                "field": "email",
                "message": "Email must be a valid RFC 5322 address",
                "code": "INVALID_EMAIL"
            }]
        )
    """
    
    def __init__(
        self,
        message: str = "Validation error",
        code: str = "VALIDATION_ERROR",
        details: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=400,
            details=details
        )


class NotFoundException(APIException):
    """
    Exception for resource not found errors (404).
    
    Raised when a requested resource does not exist.
    
    Example:
        raise NotFoundException(
            message="Agent not found",
            code=ErrorCode.NOT_FOUND_AGENT
        )
    """
    
    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND_RESOURCE",
        details: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=404,
            details=details
        )


class ConflictException(APIException):
    """
    Exception for resource conflict errors (409).
    
    Raised when an operation conflicts with existing state (e.g., duplicate resource).
    
    Example:
        raise ConflictException(
            message="Watcher already running for this agent",
            code=ErrorCode.CONFLICT_WATCHER_RUNNING
        )
    """
    
    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT_RESOURCE_EXISTS",
        details: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=409,
            details=details
        )


class TimeoutException(APIException):
    """
    Exception for operation timeout errors (408).
    
    Raised when an operation exceeds its time limit (e.g., regex execution timeout).
    
    Example:
        raise TimeoutException(
            message="Regex execution timeout (1000ms exceeded)",
            code=ErrorCode.TIMEOUT_REGEX_EXECUTION
        )
    """
    
    def __init__(
        self,
        message: str = "Operation timeout",
        code: str = "TIMEOUT_OPERATION",
        details: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=408,
            details=details
        )


class InternalServerException(APIException):
    """
    Exception for internal server errors (500).
    
    Raised when an unexpected error occurs that is not the client's fault.
    
    Note: This exception should be used sparingly. Most internal errors
    should be caught and logged by the global exception handler.
    
    Example:
        raise InternalServerException(
            message="Database connection failed",
            code=ErrorCode.INTERNAL_DATABASE_ERROR
        )
    """
    
    def __init__(
        self,
        message: str = "Internal server error",
        code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=500,
            details=details
        )

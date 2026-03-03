"""
Unit tests for error handling and structured error responses.

Tests cover:
- Error response model creation
- Custom exception classes
- Exception handler behavior
- Error code constants
- Structured error response format
"""

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from unittest.mock import Mock, MagicMock

from api.models.error_models import (
    ErrorResponse,
    ErrorDetail,
    ErrorCode,
    create_error_response
)
from api.exceptions import (
    APIException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
    NotFoundException,
    ConflictException,
    TimeoutException,
    InternalServerException
)


class TestErrorModels:
    """Test error response models."""
    
    def test_error_detail_creation(self):
        """Test ErrorDetail model creation."""
        detail = ErrorDetail(
            field="email",
            message="Invalid email format",
            code="INVALID_EMAIL"
        )
        
        assert detail.field == "email"
        assert detail.message == "Invalid email format"
        assert detail.code == "INVALID_EMAIL"
    
    def test_error_detail_without_field(self):
        """Test ErrorDetail without field name."""
        detail = ErrorDetail(
            message="General error",
            code="GENERAL_ERROR"
        )
        
        assert detail.field is None
        assert detail.message == "General error"
    
    def test_error_response_creation(self):
        """Test ErrorResponse model creation."""
        response = ErrorResponse(
            error="Validation Error",
            message="Invalid input",
            code="VALIDATION_ERROR"
        )
        
        assert response.error == "Validation Error"
        assert response.message == "Invalid input"
        assert response.code == "VALIDATION_ERROR"
        assert response.details is None
        assert response.request_id is None
    
    def test_error_response_with_details(self):
        """Test ErrorResponse with detailed errors."""
        details = [
            ErrorDetail(
                field="email",
                message="Invalid format",
                code="INVALID_EMAIL"
            )
        ]
        
        response = ErrorResponse(
            error="Validation Error",
            message="Invalid input",
            code="VALIDATION_ERROR",
            details=details
        )
        
        assert len(response.details) == 1
        assert response.details[0].field == "email"
    
    def test_create_error_response_helper(self):
        """Test create_error_response helper function."""
        response = create_error_response(
            error="Not Found",
            message="Resource not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
        
        assert isinstance(response, ErrorResponse)
        assert response.error == "Not Found"
        assert response.message == "Resource not found"
        assert response.code == ErrorCode.NOT_FOUND_RESOURCE
    
    def test_create_error_response_with_details(self):
        """Test create_error_response with details."""
        response = create_error_response(
            error="Validation Error",
            message="Invalid input",
            code=ErrorCode.VALIDATION_ERROR,
            details=[{
                "field": "email",
                "message": "Invalid format",
                "code": "INVALID_EMAIL"
            }]
        )
        
        assert len(response.details) == 1
        assert response.details[0].field == "email"


class TestErrorCodes:
    """Test error code constants."""
    
    def test_authentication_error_codes(self):
        """Test authentication error codes exist."""
        assert hasattr(ErrorCode, "AUTH_NOT_AUTHENTICATED")
        assert hasattr(ErrorCode, "AUTH_INVALID_CREDENTIALS")
        assert hasattr(ErrorCode, "AUTH_SESSION_EXPIRED")
        assert hasattr(ErrorCode, "AUTH_INVALID_TOKEN")
    
    def test_validation_error_codes(self):
        """Test validation error codes exist."""
        assert hasattr(ErrorCode, "VALIDATION_ERROR")
        assert hasattr(ErrorCode, "VALIDATION_EMAIL_FORMAT")
        assert hasattr(ErrorCode, "VALIDATION_REGEX_SYNTAX")
        assert hasattr(ErrorCode, "VALIDATION_REGEX_TIMEOUT")
    
    def test_not_found_error_codes(self):
        """Test not found error codes exist."""
        assert hasattr(ErrorCode, "NOT_FOUND_RESOURCE")
        assert hasattr(ErrorCode, "NOT_FOUND_AGENT")
        assert hasattr(ErrorCode, "NOT_FOUND_TEMPLATE")
    
    def test_internal_error_codes(self):
        """Test internal error codes exist."""
        assert hasattr(ErrorCode, "INTERNAL_SERVER_ERROR")
        assert hasattr(ErrorCode, "INTERNAL_DATABASE_ERROR")


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_api_exception_base(self):
        """Test base APIException class."""
        exc = APIException(
            message="Test error",
            code="TEST_ERROR",
            status_code=400
        )
        
        assert exc.message == "Test error"
        assert exc.code == "TEST_ERROR"
        assert exc.status_code == 400
        assert exc.details == []
    
    def test_api_exception_with_details(self):
        """Test APIException with details."""
        details = [{"field": "test", "message": "error", "code": "TEST"}]
        exc = APIException(
            message="Test error",
            code="TEST_ERROR",
            status_code=400,
            details=details
        )
        
        assert len(exc.details) == 1
        assert exc.details[0]["field"] == "test"
    
    def test_authentication_exception(self):
        """Test AuthenticationException defaults."""
        exc = AuthenticationException()
        
        assert exc.status_code == 401
        assert exc.message == "Authentication failed"
        assert exc.code == "AUTH_NOT_AUTHENTICATED"
    
    def test_authentication_exception_custom(self):
        """Test AuthenticationException with custom message."""
        exc = AuthenticationException(
            message="Invalid credentials",
            code=ErrorCode.AUTH_INVALID_CREDENTIALS
        )
        
        assert exc.status_code == 401
        assert exc.message == "Invalid credentials"
        assert exc.code == ErrorCode.AUTH_INVALID_CREDENTIALS
    
    def test_authorization_exception(self):
        """Test AuthorizationException defaults."""
        exc = AuthorizationException()
        
        assert exc.status_code == 403
        assert exc.message == "Access forbidden"
    
    def test_validation_exception(self):
        """Test ValidationException defaults."""
        exc = ValidationException()
        
        assert exc.status_code == 400
        assert exc.message == "Validation error"
        assert exc.code == "VALIDATION_ERROR"
    
    def test_validation_exception_with_details(self):
        """Test ValidationException with field details."""
        details = [{
            "field": "email",
            "message": "Invalid format",
            "code": "INVALID_EMAIL"
        }]
        
        exc = ValidationException(
            message="Invalid email",
            code=ErrorCode.VALIDATION_EMAIL_FORMAT,
            details=details
        )
        
        assert exc.status_code == 400
        assert len(exc.details) == 1
    
    def test_not_found_exception(self):
        """Test NotFoundException defaults."""
        exc = NotFoundException()
        
        assert exc.status_code == 404
        assert exc.message == "Resource not found"
    
    def test_not_found_exception_custom(self):
        """Test NotFoundException with custom message."""
        exc = NotFoundException(
            message="Agent not found",
            code=ErrorCode.NOT_FOUND_AGENT
        )
        
        assert exc.status_code == 404
        assert exc.message == "Agent not found"
        assert exc.code == ErrorCode.NOT_FOUND_AGENT
    
    def test_conflict_exception(self):
        """Test ConflictException defaults."""
        exc = ConflictException()
        
        assert exc.status_code == 409
        assert exc.message == "Resource conflict"
    
    def test_timeout_exception(self):
        """Test TimeoutException defaults."""
        exc = TimeoutException()
        
        assert exc.status_code == 408
        assert exc.message == "Operation timeout"
    
    def test_timeout_exception_custom(self):
        """Test TimeoutException with custom message."""
        exc = TimeoutException(
            message="Regex execution timeout",
            code=ErrorCode.TIMEOUT_REGEX_EXECUTION
        )
        
        assert exc.status_code == 408
        assert exc.message == "Regex execution timeout"
    
    def test_internal_server_exception(self):
        """Test InternalServerException defaults."""
        exc = InternalServerException()
        
        assert exc.status_code == 500
        assert exc.message == "Internal server error"


class TestExceptionHandlers:
    """Test exception handler behavior."""
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request object."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/api/v1/test"
        request.client = Mock()
        request.client.host = "127.0.0.1"
        return request
    
    def test_api_exception_handler_response_structure(self, mock_request):
        """Test that API exception handler returns correct structure."""
        from api.main import api_exception_handler
        
        exc = ValidationException(
            message="Invalid input",
            code=ErrorCode.VALIDATION_ERROR
        )
        
        # Call handler (it's async, so we need to await it)
        import asyncio
        response = asyncio.run(api_exception_handler(mock_request, exc))
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        # Check response body structure
        body = response.body.decode()
        assert "Invalid input" in body
        assert ErrorCode.VALIDATION_ERROR in body
    
    def test_value_error_handler_response(self, mock_request):
        """Test that ValueError is converted to validation error."""
        from api.main import value_error_handler
        
        exc = ValueError("Invalid value provided")
        
        import asyncio
        response = asyncio.run(value_error_handler(mock_request, exc))
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        
        body = response.body.decode()
        assert "Invalid value provided" in body
    
    def test_global_exception_handler_no_sensitive_info(self, mock_request):
        """Test that global handler doesn't expose sensitive information."""
        from api.main import global_exception_handler
        
        # Simulate an exception with sensitive information
        exc = Exception("Database password: secret123")
        
        import asyncio
        response = asyncio.run(global_exception_handler(mock_request, exc))
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        
        # Check that sensitive info is NOT in response
        body = response.body.decode()
        assert "secret123" not in body
        assert "Database password" not in body
        
        # Check that generic message is present
        assert "unexpected error occurred" in body.lower()


class TestErrorResponseSerialization:
    """Test error response serialization."""
    
    def test_error_response_to_dict(self):
        """Test ErrorResponse serialization to dict."""
        response = ErrorResponse(
            error="Test Error",
            message="Test message",
            code="TEST_CODE"
        )
        
        data = response.model_dump()
        
        assert data["error"] == "Test Error"
        assert data["message"] == "Test message"
        assert data["code"] == "TEST_CODE"
        assert data["details"] is None
    
    def test_error_response_with_details_to_dict(self):
        """Test ErrorResponse with details serialization."""
        details = [
            ErrorDetail(
                field="email",
                message="Invalid",
                code="INVALID"
            )
        ]
        
        response = ErrorResponse(
            error="Validation Error",
            message="Invalid input",
            code="VALIDATION_ERROR",
            details=details
        )
        
        data = response.model_dump()
        
        assert len(data["details"]) == 1
        assert data["details"][0]["field"] == "email"
        assert data["details"][0]["message"] == "Invalid"

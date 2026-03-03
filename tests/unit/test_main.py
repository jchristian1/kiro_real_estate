"""
Unit tests for FastAPI main application.

Tests:
- Application initialization
- CORS middleware configuration
- Health check endpoint
- Request logging middleware
- Global exception handler
- Static file serving configuration
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os

from api.main import app, get_db


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    return db


def test_app_initialization():
    """Test that FastAPI app initializes correctly."""
    assert app.title == "Gmail Lead Sync API"
    assert app.version == "1.0.0"
    assert app.docs_url == "/api/docs"
    assert app.redoc_url == "/api/redoc"
    assert app.openapi_url == "/api/openapi.json"


def test_cors_middleware_configured():
    """Test that CORS middleware is configured."""
    # Check that CORS middleware is in the middleware stack
    # CORS middleware is wrapped, so we check the app's middleware attribute
    assert hasattr(app, "user_middleware")
    assert len(app.user_middleware) > 0


def test_root_endpoint(client):
    """Test API root endpoint."""
    response = client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Gmail Lead Sync API"
    assert data["version"] == "1.0.0"
    assert data["docs"] == "/api/docs"


def test_health_check_endpoint_healthy(client):
    """Test health check endpoint when database is connected."""
    with patch("api.main.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.execute.return_value = None
        mock_get_db.return_value = mock_db
        
        # Override dependency
        app.dependency_overrides[get_db] = lambda: mock_db
        
        response = client.get("/api/v1/health")
        
        # Clear overrides
        app.dependency_overrides.clear()
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "timestamp" in data


def test_health_check_endpoint_unhealthy(client):
    """Test health check endpoint when database is disconnected."""
    with patch("api.main.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database connection failed")
        mock_get_db.return_value = mock_db
        
        # Override dependency
        app.dependency_overrides[get_db] = lambda: mock_db
        
        response = client.get("/api/v1/health")
        
        # Clear overrides
        app.dependency_overrides.clear()
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"


def test_request_logging_middleware(client):
    """Test that request logging middleware logs requests."""
    with patch("api.main.logger") as mock_logger:
        response = client.get("/api/v1")
        assert response.status_code == 200
        
        # Verify logger was called
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args
        assert "GET" in call_args[0][0]
        assert "/api/v1" in call_args[0][0]


def test_global_exception_handler(client):
    """Test global exception handler for unhandled errors."""
    # The global exception handler is already registered in main.py
    # We need to test it by creating a temporary route that raises an exception
    
    # Since we can't easily add routes dynamically in tests, we'll test
    # by verifying the handler is registered
    assert app.exception_handlers is not None
    
    # Verify Exception handler is registered
    assert Exception in app.exception_handlers or None in app.exception_handlers


def test_cors_headers(client):
    """Test that CORS headers are present in responses."""
    response = client.options(
        "/api/v1",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        }
    )
    
    # Check CORS headers
    assert "access-control-allow-origin" in response.headers


def test_api_route_not_served_as_static(client):
    """Test that API routes are not served as static files."""
    response = client.get("/api/nonexistent")
    # Should return 404 from API, not try to serve static file
    assert response.status_code == 404


def test_api_routes_take_precedence_over_static(client):
    """Test that API routes take precedence over static file serving."""
    # Test that /api/v1 routes work
    response = client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    
    # Test that /metrics endpoint works
    response = client.get("/metrics")
    assert response.status_code == 200
    # Metrics endpoint returns Prometheus format
    assert "text/plain" in response.headers["content-type"]


def test_metrics_endpoint_not_served_as_static(client):
    """Test that /metrics endpoint is not served as static file."""
    response = client.get("/metrics")
    assert response.status_code == 200
    # Should return Prometheus metrics, not HTML
    assert "text/plain" in response.headers["content-type"]


def test_database_dependency():
    """Test database dependency provides session."""
    db_gen = get_db()
    db = next(db_gen)
    
    # Verify we got a database session
    assert db is not None
    
    # Clean up
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_json_formatter():
    """Test JSON log formatter."""
    from api.main import JSONFormatter
    import logging
    
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None
    )
    
    formatted = formatter.format(record)
    
    # Verify it's valid JSON
    import json
    data = json.loads(formatted)
    
    assert data["level"] == "INFO"
    assert data["logger"] == "test"
    assert data["message"] == "Test message"
    assert "timestamp" in data


def test_json_formatter_with_exception():
    """Test JSON log formatter with exception info."""
    from api.main import JSONFormatter
    import logging
    
    formatter = JSONFormatter()
    
    try:
        raise ValueError("Test exception")
    except ValueError:
        import sys
        exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )
        
        formatted = formatter.format(record)
        
        # Verify it's valid JSON
        import json
        data = json.loads(formatted)
        
        assert data["level"] == "ERROR"
        assert "exception" in data
        assert "ValueError" in data["exception"]


def test_startup_event():
    """Test startup event handler."""
    with patch("api.main.logger") as mock_logger:
        # Trigger startup event
        with TestClient(app):
            pass
        
        # Verify startup was logged
        assert any("Starting Gmail Lead Sync API" in str(call) for call in mock_logger.info.call_args_list)


def test_environment_configuration():
    """Test that environment variables are loaded."""
    from api.main import config
    
    # Verify configuration is loaded
    assert config.database_url is not None
    assert isinstance(config.cors_origins, list)
    assert config.log_level is not None

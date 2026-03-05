"""
FastAPI application entry point for Gmail Lead Sync Web UI & API Layer.

This module initializes the FastAPI application with:
- CORS middleware for cross-origin requests
- Session cookie middleware
- Structured JSON logging
- API routes mounted under /api/v1 prefix
- Static file serving for frontend (production mode)
- Health check and metrics endpoints

Environment Configuration:
- DATABASE_URL: SQLite database path
- CORS_ORIGINS: Comma-separated list of allowed origins
- CORS_ALLOW_CREDENTIALS: Enable credentials in CORS
- STATIC_FILES_DIR: Directory for frontend static files
- API_HOST: Host to bind to (default: 0.0.0.0)
- API_PORT: Port to bind to (default: 8000)
- LOG_LEVEL: Logging level (default: INFO)
"""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from gmail_lead_sync.models import Base
from api.models.web_ui_models import User, Session as SessionModel
from api.models.error_models import ErrorResponse, ErrorCode, create_error_response
from api.config import load_config, Config
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


# Load and validate configuration
# For testing, use minimal configuration if required env vars are missing
encryption_key = os.getenv("ENCRYPTION_KEY", "")
secret_key = os.getenv("SECRET_KEY", "")

if not encryption_key or not secret_key:
    # Use test configuration with minimal valid values
    # Generate a valid Fernet key for testing
    from cryptography.fernet import Fernet
    test_encryption_key = Fernet.generate_key().decode() if not encryption_key else encryption_key
    test_secret_key = "b" * 32 if not secret_key else secret_key
    
    config = Config(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./test_config.db"),
        encryption_key=test_encryption_key,
        secret_key=test_secret_key
    )
else:
    try:
        config = load_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)


# Configure structured JSON logging
class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    
    Outputs log records as JSON objects with timestamp, level, message,
    and additional context fields.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        return json.dumps(log_data)


# Set up logging
logger = logging.getLogger("api")
logger.setLevel(getattr(logging, config.log_level))

# Console handler with JSON formatting
console_handler = logging.StreamHandler()
console_handler.setFormatter(JSONFormatter())
logger.addHandler(console_handler)

# Also propagate gmail_lead_sync logs through the same handler
for module_logger_name in ['gmail_lead_sync', 'api.services.watcher_registry']:
    module_logger = logging.getLogger(module_logger_name)
    module_logger.setLevel(getattr(logging, config.log_level))
    module_logger.addHandler(console_handler)
    module_logger.propagate = False


# Prometheus metrics
# Requirements: 29.2, 29.3, 29.4, 29.5, 29.6
# Use try-except to avoid duplicate registration errors in tests
try:
    api_requests_total = Counter(
        'api_requests_total',
        'Total API requests',
        ['endpoint', 'method', 'status']
    )
except ValueError:
    # Metric already registered (happens in tests)
    from prometheus_client import REGISTRY
    api_requests_total = REGISTRY._names_to_collectors['api_requests_total']

try:
    api_request_duration_seconds = Histogram(
        'api_request_duration_seconds',
        'API request duration in seconds',
        ['endpoint', 'method']
    )
except ValueError:
    from prometheus_client import REGISTRY
    api_request_duration_seconds = REGISTRY._names_to_collectors['api_request_duration_seconds']

try:
    api_errors_total = Counter(
        'api_errors_total',
        'Total API errors',
        ['endpoint', 'status']
    )
except ValueError:
    from prometheus_client import REGISTRY
    api_errors_total = REGISTRY._names_to_collectors['api_errors_total']

try:
    watchers_active = Gauge(
        'watchers_active',
        'Number of active watchers'
    )
except ValueError:
    from prometheus_client import REGISTRY
    watchers_active = REGISTRY._names_to_collectors['watchers_active']

try:
    leads_processed_total = Counter(
        'leads_processed_total',
        'Total leads processed'
    )
except ValueError:
    from prometheus_client import REGISTRY
    leads_processed_total = REGISTRY._names_to_collectors['leads_processed_total']


def increment_leads_processed(count: int = 1) -> None:
    """
    Increment the leads processed counter.
    
    This function should be called whenever leads are processed.
    For now, it's a placeholder that can be integrated with the
    watcher or lead processing logic.
    
    Args:
        count: Number of leads processed (default: 1)
        
    Requirements: 29.5
    """
    leads_processed_total.inc(count)


# Database setup
engine = create_engine(
    config.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in config.database_url else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Database dependency
def get_db() -> Session:
    """
    FastAPI dependency for database sessions.
    
    Yields a database session and ensures it's closed after use.
    
    Example:
        @app.get("/api/v1/example")
        def example(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create FastAPI application
app = FastAPI(
    title="Gmail Lead Sync API",
    description="REST API for Gmail Lead Sync Web UI",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=config.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log all HTTP requests with structured logging.
    
    Logs request method, path, status code, and duration.
    Also tracks Prometheus metrics for requests.
    
    Requirements: 29.2, 29.3, 29.6
    """
    start_time = datetime.utcnow()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = (datetime.utcnow() - start_time).total_seconds()
    
    # Extract endpoint path (normalize IDs to avoid high cardinality)
    endpoint = request.url.path
    # Normalize paths with IDs (e.g., /api/v1/agents/123 -> /api/v1/agents/{id})
    import re
    endpoint = re.sub(r'/\d+', '/{id}', endpoint)
    
    # Track Prometheus metrics (skip /metrics endpoint to avoid recursion)
    if endpoint != "/metrics":
        # Track request count
        api_requests_total.labels(
            endpoint=endpoint,
            method=request.method,
            status=str(response.status_code)
        ).inc()
        
        # Track request duration
        api_request_duration_seconds.labels(
            endpoint=endpoint,
            method=request.method
        ).observe(duration)
        
        # Track errors (4xx and 5xx)
        if response.status_code >= 400:
            api_errors_total.labels(
                endpoint=endpoint,
                status=str(response.status_code)
            ).inc()
    
    # Log request
    logger.info(
        f"{request.method} {request.url.path} - {response.status_code}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_seconds": duration,
            "client_host": request.client.host if request.client else None
        }
    )
    
    return response


# Custom exception handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """
    Handler for custom API exceptions.
    
    Converts APIException instances to structured error responses with
    appropriate HTTP status codes.
    
    Args:
        request: The incoming request
        exc: The APIException instance
    
    Returns:
        JSONResponse with structured error information
    """
    # Log the error with context
    logger.warning(
        f"API exception: {exc.message}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "error_code": exc.code,
            "status_code": exc.status_code,
            "exception_type": type(exc).__name__
        }
    )
    
    # Create structured error response
    error_response = create_error_response(
        error=type(exc).__name__.replace("Exception", " Error"),
        message=exc.message,
        code=exc.code,
        details=exc.details
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    Handler for ValueError exceptions.
    
    Converts ValueError to a validation error response.
    
    Args:
        request: The incoming request
        exc: The ValueError instance
    
    Returns:
        JSONResponse with validation error information
    """
    logger.warning(
        f"Value error: {str(exc)}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "exception_type": "ValueError"
        }
    )
    
    error_response = create_error_response(
        error="Validation Error",
        message=str(exc),
        code=ErrorCode.VALIDATION_ERROR
    )
    
    return JSONResponse(
        status_code=400,
        content=error_response.model_dump()
    )


# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    
    Returns a generic error message to clients and logs the full exception
    server-side for debugging. This ensures no sensitive information is
    exposed in error responses.
    
    Args:
        request: The incoming request
        exc: The unhandled exception
    
    Returns:
        JSONResponse with generic error message
    """
    # Log the full exception with stack trace
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
            "client_host": request.client.host if request.client else None
        }
    )
    
    # Return generic error response (no sensitive information)
    error_response = create_error_response(
        error="Internal Server Error",
        message="An unexpected error occurred. Please contact support if the issue persists.",
        code=ErrorCode.INTERNAL_SERVER_ERROR
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


# Health check endpoint is now in api/routes/health.py


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    This endpoint does NOT require authentication to allow
    Prometheus scraper to collect metrics.
    
    Metrics tracked:
    - api_requests_total: Counter for request count per endpoint, method, and status
    - api_request_duration_seconds: Histogram for request duration per endpoint and method
    - api_errors_total: Counter for error count per endpoint and status
    - watchers_active: Gauge for active watcher count
    - leads_processed_total: Counter for total leads processed
    
    Requirements: 8.2, 29.1, 29.2, 29.3, 29.4, 29.5, 29.6, 29.7
    """
    # Update watcher count gauge
    try:
        watcher_statuses = await watcher_registry.get_all_statuses()
        active_count = sum(
            1 for info in watcher_statuses.values()
            if info["status"] == "running"
        )
        watchers_active.set(active_count)
    except Exception as e:
        logger.error(f"Error updating watcher count metric: {e}", exc_info=True)
    
    # Generate Prometheus text format
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Root endpoint
@app.get("/api/v1")
async def root():
    """API root endpoint."""
    return {
        "message": "Gmail Lead Sync API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }


# Initialize WatcherRegistry
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
from api.services.watcher_registry import WatcherRegistry

# Create global WatcherRegistry instance
credentials_store = EncryptedDBCredentialsStore(SessionLocal(), encryption_key=config.encryption_key)
watcher_registry = WatcherRegistry(
    get_db_session=SessionLocal,
    credentials_store=credentials_store
)

# Mount API routes
from api.routes import audit, agents, lead_sources, templates, watchers, leads, health, settings, auth, companies
from api.routes.public_submission import router as public_submission_router
from api.auth import get_current_user

# Create wrapper for get_current_user that works with FastAPI dependency injection
def get_current_user_wrapper(request: Request, db: Session = Depends(get_db)) -> User:
    """Wrapper for get_current_user that uses FastAPI dependency injection."""
    return get_current_user(request, db)

# Include routers
# Public router — no auth middleware
app.include_router(public_submission_router)

app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(audit.router, prefix="/api/v1", tags=["Audit Logs"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(lead_sources.router, prefix="/api/v1", tags=["Lead Sources"])
app.include_router(templates.router, prefix="/api/v1", tags=["Templates"])
app.include_router(watchers.router, prefix="/api/v1", tags=["Watchers"])
app.include_router(leads.router, prefix="/api/v1", tags=["Leads"])
app.include_router(settings.router, prefix="/api/v1", tags=["Settings"])
app.include_router(companies.router, prefix="/api/v1", tags=["Companies"])


# Static file serving for frontend (production mode)
# Requirements: 12.6, 28.1, 28.2, 28.3, 28.4
if os.path.exists(config.static_files_dir):
    # Check if assets directory exists
    assets_dir = os.path.join(config.static_files_dir, "assets")
    if os.path.exists(assets_dir):
        # Mount static assets with cache headers
        # Cache-Control: public, max-age=31536000 (1 year) for immutable assets
        class CachedStaticFiles(StaticFiles):
            """StaticFiles subclass that adds cache headers."""
            
            async def get_response(self, path: str, scope):
                """Override to add cache headers to responses."""
                response = await super().get_response(path, scope)
                # Set cache headers for static assets (1 year)
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
                return response
        
        app.mount("/assets", CachedStaticFiles(directory=assets_dir), name="assets")
    
    # Serve index.html for all non-API routes (client-side routing)
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """
        Serve frontend index.html for all non-API routes.
        
        This enables client-side routing in the React application.
        API routes under /api/v1 prefix take precedence over this catch-all route.
        
        Cache headers:
        - index.html: Cache-Control: no-cache (always revalidate)
        - Static assets (/assets): Cache-Control: public, max-age=31536000 (1 year)
        
        Requirements: 28.2, 28.3, 28.4
        """
        # Don't serve index.html for API routes or metrics
        if full_path.startswith("api/") or full_path == "metrics":
            return JSONResponse(
                status_code=404,
                content={"error": "Not found"}
            )
        
        # Serve index.html with no-cache header
        index_path = os.path.join(config.static_files_dir, "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r") as f:
                content = f.read()
            
            # Return with no-cache header to ensure fresh content
            return Response(
                content=content,
                media_type="text/html",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        
        return JSONResponse(
            status_code=404,
            content={"error": "Frontend not found"}
        )


# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    
    Logs configuration and performs initialization tasks.
    """
    logger.info("Starting Gmail Lead Sync API")
    config.log_config(logger)


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown event handler.
    
    Performs cleanup tasks before shutdown including stopping all watchers.
    """
    logger.info("Shutting down Gmail Lead Sync API")
    
    # Stop all watchers gracefully
    try:
        await watcher_registry.stop_all()
    except Exception as e:
        logger.error(f"Error stopping watchers during shutdown: {e}", exc_info=True)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=config.api_host,
        port=config.api_port,
        reload=True,
        log_level=config.log_level.lower()
    )

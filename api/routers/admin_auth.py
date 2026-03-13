"""
Authentication routes for Web UI & API Layer.

This module provides REST API endpoints for:
- User login with username/password
- User logout with session invalidation
- Current user information retrieval

All endpoints use HTTP-only secure cookies for session management.
"""

from fastapi import APIRouter, Depends, Response, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import logging

from api.auth import (
    authenticate_user,
    create_session,
    invalidate_session,
    get_session_token_from_cookie,
    set_session_cookie,
    clear_session_cookie,
    get_current_user
)
from api.dependencies.db import get_db
from api.models.web_ui_models import User
from api.models.error_models import ErrorCode
from api.exceptions import AuthenticationException
from api.utils.rate_limiter import limiter

logger = logging.getLogger("api.auth")


router = APIRouter()


# Request/Response models
class LoginRequest(BaseModel):
    """Login request model."""
    username: str = Field(..., min_length=1, max_length=255, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class UserResponse(BaseModel):
    """User response model (excludes password hash)."""
    id: int
    username: str
    role: str
    company_id: int | None = None
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Login response model."""
    user: UserResponse


class LogoutResponse(BaseModel):
    """Logout response model."""
    message: str


@router.post("/auth/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def login(
    request: Request,
    request_body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and create session.

    Rate limited to 10 requests/minute per IP.

    Requirements: 6.2, 6.3, 6.5, 11.6
    """
    # Authenticate user
    user = authenticate_user(db, request_body.username, request_body.password)

    if not user:
        # Log auth failure — username and IP only, never the password (Req 11.8)
        source_ip = request.client.host if request.client else "unknown"
        logger.warning(
            "Authentication failure",
            extra={
                "username_attempted": request_body.username,
                "source_ip": source_ip,
                "endpoint": "/api/v1/auth/login",
            },
        )
        raise AuthenticationException(
            message="Invalid username or password",
            code=ErrorCode.AUTH_INVALID_CREDENTIALS
        )

    # Create session
    session = create_session(db, user.id)

    # Set session cookie
    set_session_cookie(response, session.id)

    # Return user info (exclude password hash)
    return LoginResponse(
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            company_id=user.company_id,
        )
    )


@router.post("/auth/logout", response_model=LogoutResponse, status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Logout user and invalidate session.
    
    Extracts session token from cookie, invalidates it in the database,
    and clears the session cookie.
    
    Args:
        request: FastAPI request object for reading cookie
        response: FastAPI response object for clearing cookie
        db: Database session
    
    Returns:
        LogoutResponse with success message
    
    Requirements: 26.5, 26.6
    """
    # Extract session token from cookie
    token = get_session_token_from_cookie(request)
    
    if token:
        # Invalidate session in database
        invalidate_session(db, token)
    
    # Clear session cookie
    clear_session_cookie(response)
    
    return LogoutResponse(message="Logged out successfully")


@router.get("/auth/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_me(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user information.
    
    Validates session token from cookie and returns user information.
    
    Args:
        request: FastAPI request object for reading cookie
        db: Database session
    
    Returns:
        UserResponse with current user information
    
    Raises:
        AuthenticationException: 401 if not authenticated
    
    Requirements: 6.4, 6.8
    """
    # Get current user (validates session)
    user = get_current_user(request, db)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        company_id=user.company_id,
    )

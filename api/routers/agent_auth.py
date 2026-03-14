"""
Agent authentication routes for the agent-app.

Provides:
- POST /api/v1/agent/auth/signup  — create agent account, auto-login, set session cookie
- POST /api/v1/agent/auth/login   — verify credentials, create session, set cookie
- POST /api/v1/agent/auth/logout  — invalidate session, clear cookie
- GET  /api/v1/agent/auth/me      — return current agent info (requires valid session)

Requirements: 1.1, 1.2, 1.3, 1.5, 2.1, 2.2, 2.3, 2.5, 2.6
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
import logging
import os

import bcrypt
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from api.dependencies.db import get_db
from api.repositories import AgentRepository, AgentSessionRepository
from api.utils.rate_limiter import limiter
from gmail_lead_sync.agent_models import AgentSession

logger = logging.getLogger("api.auth")

# Session cookie configuration (mirrors design.md spec)
AGENT_SESSION_COOKIE_NAME = "agent_session"
AGENT_SESSION_EXPIRY_DAYS = 30
AGENT_SESSION_TOKEN_BYTES = 64  # 64-byte cryptographically secure token

router = APIRouter(prefix="/agent/auth", tags=["Agent Auth"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    """Signup request body."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: Optional[str] = Field(default="", max_length=255)

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SignupResponse(BaseModel):
    """Signup success response (201)."""
    agent_user_id: int
    email: str
    onboarding_step: int


class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login success response (200)."""
    agent_user_id: int
    full_name: str
    onboarding_completed: bool


class MeResponse(BaseModel):
    """GET /me response (200)."""
    agent_user_id: int
    email: str
    full_name: str
    onboarding_completed: bool
    onboarding_step: int


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _create_agent_session(db: Session, agent_user_id: int) -> AgentSession:
    """Create a new 64-byte secure session for an agent."""
    token = secrets.token_hex(AGENT_SESSION_TOKEN_BYTES)
    expires_at = datetime.utcnow() + timedelta(days=AGENT_SESSION_EXPIRY_DAYS)
    session_repo = AgentSessionRepository(db)
    return session_repo.create_session(agent_user_id, token, expires_at)


def _set_agent_session_cookie(response: Response, token: str) -> None:
    """Set the agent session cookie per design spec.

    In production (ENVIRONMENT=production): secure=True, samesite="strict".
    In development: secure=False, samesite="lax".

    Requirements: 4.6
    """
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key=AGENT_SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_production,
        samesite="strict" if is_production else "lax",
        max_age=AGENT_SESSION_EXPIRY_DAYS * 24 * 3600,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=SignupResponse,
    responses={
        409: {"model": ErrorResponse, "description": "Email already exists"},
        422: {"description": "Validation error (e.g. password too short)"},
    },
)
async def signup(
    body: SignupRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Create a new agent account, auto-login, and return a session cookie.

    - Hashes password with bcrypt
    - Returns 409 if email already registered
    - Returns 422 if password < 8 characters (handled by Pydantic)
    - On success: creates AgentUser + AgentSession, sets `agent_session` cookie

    Requirements: 1.1, 1.2, 1.3, 1.5
    """
    # Hash password
    password_hash = _hash_password(body.password)

    # Create agent user via repository (handles duplicate email check)
    agent_repo = AgentRepository(db)
    agent_user, created = agent_repo.create_with_duplicate_check(
        email=body.email,
        password_hash=password_hash,
        full_name=body.full_name or "",
    )
    if not created:
        return Response(
            content='{"error": "EMAIL_ALREADY_EXISTS"}',
            status_code=status.HTTP_409_CONFLICT,
            media_type="application/json",
        )

    # Auto-login: create session and set cookie
    session = _create_agent_session(db, agent_user.id)
    _set_agent_session_cookie(response, session.id)

    return SignupResponse(
        agent_user_id=agent_user.id,
        email=agent_user.email,
        onboarding_step=agent_user.onboarding_step,
    )


# ---------------------------------------------------------------------------
# Helper: look up a valid (non-expired) session from cookie
# ---------------------------------------------------------------------------

def _get_session(db: Session, token: Optional[str]) -> Optional[AgentSession]:
    """Return the AgentSession for *token* if it exists and has not expired."""
    if not token:
        return None
    session_repo = AgentSessionRepository(db)
    return session_repo.get_valid_session(token)


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Verify email + password, create a new session, and set the session cookie.

    Rate limited to 10 requests/minute per IP.

    Requirements: 2.1, 2.2, 2.6, 11.6
    """
    # Look up agent by email
    agent_repo = AgentRepository(db)
    agent_user = agent_repo.get_by_email(body.email)

    # Verify password (constant-time via bcrypt)
    if agent_user is None or not bcrypt.checkpw(
        body.password.encode("utf-8"), agent_user.password_hash.encode("utf-8")
    ):
        # Log auth failure — email and IP only, never the password (Req 11.8)
        source_ip = request.client.host if request.client else "unknown"
        logger.warning(
            "Authentication failure",
            extra={
                "username_attempted": body.email,
                "source_ip": source_ip,
                "endpoint": "/api/v1/agent/auth/login",
            },
        )
        return Response(
            content='{"error": "INVALID_CREDENTIALS"}',
            status_code=status.HTTP_401_UNAUTHORIZED,
            media_type="application/json",
        )

    # Create session and set cookie
    session = _create_agent_session(db, agent_user.id)
    _set_agent_session_cookie(response, session.id)

    return LoginResponse(
        agent_user_id=agent_user.id,
        full_name=agent_user.full_name,
        onboarding_completed=agent_user.onboarding_completed,
    )


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
)
async def logout(
    response: Response,
    db: Session = Depends(get_db),
    agent_session: Optional[str] = Cookie(default=None, alias=AGENT_SESSION_COOKIE_NAME),
):
    """
    Invalidate the current session and clear the session cookie.

    - Deletes the session record from the DB (if present).
    - Clears the cookie regardless of whether a session existed.

    Requirements: 2.3
    """
    if agent_session:
        session_repo = AgentSessionRepository(db)
        session_repo.delete_session(agent_session)

    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.delete_cookie(
        key=AGENT_SESSION_COOKIE_NAME,
        httponly=True,
        secure=is_production,
        samesite="strict" if is_production else "lax",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=MeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
    },
)
async def me(
    db: Session = Depends(get_db),
    agent_session: Optional[str] = Cookie(default=None, alias=AGENT_SESSION_COOKIE_NAME),
):
    """
    Return the currently authenticated agent's profile.

    - Returns 401 if the session cookie is missing or the session is expired/invalid.

    Requirements: 2.5
    """
    session = _get_session(db, agent_session)
    if session is None:
        from api.exceptions import AuthenticationException
        from api.models.error_models import ErrorCode
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED,
        )

    agent_user = AgentSessionRepository(db).get_agent_by_id(session.agent_user_id)
    if agent_user is None:
        from api.exceptions import AuthenticationException
        from api.models.error_models import ErrorCode
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED,
        )
    return MeResponse(
        agent_user_id=agent_user.id,
        email=agent_user.email,
        full_name=agent_user.full_name,
        onboarding_completed=agent_user.onboarding_completed,
        onboarding_step=agent_user.onboarding_step,
    )

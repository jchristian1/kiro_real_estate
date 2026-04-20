"""
Agent authentication routes for the agent-app.

Provides:
- POST /api/v1/agent/auth/login   — verify credentials, create session, set cookie
- POST /api/v1/agent/auth/logout  — invalidate session, clear cookie
- GET  /api/v1/agent/auth/me      — return current agent info (requires valid session)

Agent accounts are created by company admins, not by self-signup.
The POST /signup endpoint has been removed (PR A1).

Requirements: 2.1, 2.2, 2.3, 2.5, 2.6
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
import logging
import os

import bcrypt
from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from api.dependencies.db import get_db
from api.repositories import AgentRepository, AgentSessionRepository
from api.utils.rate_limiter import limiter
from gmail_lead_sync.agent_models import AgentSession

logger = logging.getLogger("api.auth")

AGENT_SESSION_COOKIE_NAME = "agent_session"
AGENT_SESSION_EXPIRY_DAYS = 30
AGENT_SESSION_TOKEN_BYTES = 64

router = APIRouter(prefix="/agent/auth", tags=["Agent Auth"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    agent_user_id: int
    full_name: str
    onboarding_completed: bool


class MeResponse(BaseModel):
    agent_user_id: int
    email: str
    full_name: str
    onboarding_completed: bool


class ErrorResponse(BaseModel):
    error: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_agent_session(db: Session, agent_user_id: int) -> AgentSession:
    token = secrets.token_hex(AGENT_SESSION_TOKEN_BYTES)
    expires_at = datetime.utcnow() + timedelta(days=AGENT_SESSION_EXPIRY_DAYS)
    return AgentSessionRepository(db).create_session(agent_user_id, token, expires_at)


def _set_agent_session_cookie(response: Response, token: str) -> None:
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key=AGENT_SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_production,
        samesite="strict" if is_production else "lax",
        max_age=AGENT_SESSION_EXPIRY_DAYS * 24 * 3600,
    )


def _get_session(db: Session, token: Optional[str]) -> Optional[AgentSession]:
    if not token:
        return None
    return AgentSessionRepository(db).get_valid_session(token)


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
    """Verify email + password, create session, set cookie. Rate limited 10/min."""
    agent_repo = AgentRepository(db)
    agent_user = agent_repo.get_by_email(body.email)

    if agent_user is None or not bcrypt.checkpw(
        body.password.encode("utf-8"), agent_user.password_hash.encode("utf-8")
    ):
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

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    db: Session = Depends(get_db),
    agent_session: Optional[str] = Cookie(default=None, alias=AGENT_SESSION_COOKIE_NAME),
):
    """Invalidate session and clear cookie."""
    if agent_session:
        AgentSessionRepository(db).delete_session(agent_session)

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
    responses={401: {"model": ErrorResponse, "description": "Missing or invalid session"}},
)
async def me(
    db: Session = Depends(get_db),
    agent_session: Optional[str] = Cookie(default=None, alias=AGENT_SESSION_COOKIE_NAME),
):
    """Return the currently authenticated agent's profile."""
    from api.exceptions import AuthenticationException
    from api.models.error_models import ErrorCode

    session = _get_session(db, agent_session)
    if session is None:
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED,
        )

    agent_user = AgentSessionRepository(db).get_agent_by_id(session.agent_user_id)
    if agent_user is None:
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED,
        )

    return MeResponse(
        agent_user_id=agent_user.id,
        email=agent_user.email,
        full_name=agent_user.full_name,
        onboarding_completed=agent_user.onboarding_completed,
    )

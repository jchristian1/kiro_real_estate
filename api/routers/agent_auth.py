"""
Agent authentication routes for the agent-app.

Provides:
- POST /api/v1/agent/auth/signup — create agent account, auto-login, set session cookie

Requirements: 1.1, 1.2, 1.3, 1.5
"""

import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.main import get_db
from gmail_lead_sync.agent_models import AgentUser, AgentSession

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
    full_name: str = Field(..., min_length=1, max_length=255)

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
    token = secrets.token_hex(AGENT_SESSION_TOKEN_BYTES)  # 128-char hex = 64 bytes
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent_user_id,
        created_at=now,
        expires_at=now + timedelta(days=AGENT_SESSION_EXPIRY_DAYS),
        last_accessed=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _set_agent_session_cookie(response: Response, token: str) -> None:
    """Set the agent session cookie per design spec."""
    response.set_cookie(
        key=AGENT_SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
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

    # Create agent user
    agent_user = AgentUser(
        email=body.email,
        password_hash=password_hash,
        full_name=body.full_name,
        onboarding_step=0,
        onboarding_completed=False,
        created_at=datetime.utcnow(),
    )
    db.add(agent_user)

    try:
        db.flush()  # Detect unique constraint violation before commit
    except IntegrityError:
        db.rollback()
        return Response(
            content='{"error": "EMAIL_ALREADY_EXISTS"}',
            status_code=status.HTTP_409_CONFLICT,
            media_type="application/json",
        )

    db.commit()
    db.refresh(agent_user)

    # Auto-login: create session and set cookie
    session = _create_agent_session(db, agent_user.id)
    _set_agent_session_cookie(response, session.id)

    return SignupResponse(
        agent_user_id=agent_user.id,
        email=agent_user.email,
        onboarding_step=agent_user.onboarding_step,
    )

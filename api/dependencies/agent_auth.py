"""
FastAPI dependency for agent session authentication.

Provides `get_current_agent` — a reusable dependency that validates the
`agent_session` cookie and returns the authenticated `AgentUser`.

Usage:
    from api.dependencies.agent_auth import get_current_agent

    @router.get("/some-protected-route")
    def protected(agent: AgentUser = Depends(get_current_agent)):
        ...

Requirements: 2.4
"""

from datetime import datetime
from typing import Optional

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from api.exceptions import AuthenticationException
from api.models.error_models import ErrorCode
from api.main import get_db
from gmail_lead_sync.agent_models import AgentSession, AgentUser

# Must match the cookie name used in agent_auth.py
AGENT_SESSION_COOKIE_NAME = "agent_session"


def get_current_agent(
    db: Session = Depends(get_db),
    agent_session: Optional[str] = Cookie(
        default=None, alias=AGENT_SESSION_COOKIE_NAME
    ),
) -> AgentUser:
    """
    Validate the `agent_session` cookie and return the authenticated AgentUser.

    - Raises HTTP 401 (AuthenticationException) if the cookie is missing.
    - Raises HTTP 401 (AuthenticationException) if the session does not exist in the DB.
    - Raises HTTP 401 (AuthenticationException) if the session has expired.
    - Returns the `AgentUser` associated with the valid session.

    Requirements: 2.4
    """
    if not agent_session:
        raise AuthenticationException(
            message="Authentication required",
            code=ErrorCode.AUTH_NOT_AUTHENTICATED,
        )

    now = datetime.utcnow()
    session = (
        db.query(AgentSession)
        .filter(
            AgentSession.id == agent_session,
            AgentSession.expires_at > now,
        )
        .first()
    )

    if session is None:
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED,
        )

    agent_user = (
        db.query(AgentUser)
        .filter(AgentUser.id == session.agent_user_id)
        .first()
    )

    if agent_user is None:
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED,
        )

    return agent_user

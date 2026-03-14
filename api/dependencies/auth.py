"""
Authentication and authorisation dependencies.

Provides reusable FastAPI `Depends` callables for:
- `get_current_agent`  — validates the `agent_session` cookie → AgentUser
- `get_current_admin`  — validates the `session_token` cookie → User (admin)
- `require_role(role)` — factory that returns a dependency enforcing a role

Usage:
    from api.dependencies.auth import get_current_agent, get_current_admin, require_role

    @router.get("/agent/resource")
    def agent_route(agent: AgentUser = Depends(get_current_agent)):
        ...

    @router.get("/admin/resource")
    def admin_route(user: User = Depends(get_current_admin)):
        ...

    # At router level:
    router = APIRouter(dependencies=[Depends(require_role("platform_admin"))])

Requirements: 7.4, 11.2, 11.3
"""

from datetime import datetime
from typing import Callable, Optional

from fastapi import Cookie, Depends, Request
from sqlalchemy.orm import Session

from api.dependencies.db import get_db
from api.exceptions import AuthenticationException, AuthorizationException
from api.models.error_models import ErrorCode

# Re-export get_current_agent from the existing module so existing imports
# from api.dependencies.agent_auth keep working unchanged.
from api.dependencies.agent_auth import get_current_agent  # noqa: F401

AGENT_SESSION_COOKIE_NAME = "agent_session"
ADMIN_SESSION_COOKIE_NAME = "session_token"


def get_current_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> "User":  # type: ignore[name-defined]  # noqa: F821
    """
    Validate the `session_token` cookie and return the authenticated admin User.

    - Raises HTTP 401 if the cookie is missing or the session is invalid/expired.
    - Raises HTTP 403 if the authenticated user does not have the `admin` or
      `platform_admin` role.

    Requirements: 7.4, 11.2
    """
    from api.auth import get_session_token_from_cookie, validate_session
    from api.models.web_ui_models import User

    token = get_session_token_from_cookie(request)
    if not token:
        raise AuthenticationException(
            message="Authentication required",
            code=ErrorCode.AUTH_NOT_AUTHENTICATED,
        )

    session = validate_session(db, token)
    if session is None:
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED,
        )

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None:
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED,
        )

    if user.role not in ("admin", "platform_admin"):
        raise AuthorizationException(
            message="Admin access required",
            code=ErrorCode.AUTH_FORBIDDEN,
        )

    return user


def require_role(role: str) -> Callable:
    """
    Factory that returns a FastAPI dependency enforcing a specific role.

    Supports two role families:
    - ``"platform_admin"`` / ``"admin"`` — validated via the admin session cookie
      (``session_token``).  The dependency returns the authenticated ``User``.
    - ``"agent"`` — validated via the agent session cookie (``agent_session``).
      The dependency returns the authenticated ``AgentUser``.

    Usage::

        router = APIRouter(dependencies=[Depends(require_role("platform_admin"))])

        @router.get("/resource")
        def resource(user = Depends(require_role("agent"))):
            ...

    Requirements: 7.4, 11.2, 11.3
    """

    if role in ("platform_admin", "admin"):

        def _require_admin(
            request: Request,
            db: Session = Depends(get_db),
        ):
            return get_current_admin(request, db)

        return _require_admin

    elif role == "agent":

        def _require_agent(
            db: Session = Depends(get_db),
            agent_session: Optional[str] = Cookie(
                default=None, alias=AGENT_SESSION_COOKIE_NAME
            ),
        ):
            from gmail_lead_sync.agent_models import AgentSession, AgentUser

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

        return _require_agent

    else:
        raise ValueError(f"Unknown role: {role!r}. Expected 'platform_admin', 'admin', or 'agent'.")

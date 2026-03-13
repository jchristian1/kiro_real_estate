"""
Authentication module for Web UI & API Layer.

This module provides authentication functionality including:
- User login with bcrypt password validation
- Session token generation (cryptographically secure)
- Session validation and expiration checking
- Logout with session invalidation
- Authentication dependency for protected routes

Security features:
- bcrypt password hashing with automatic salt generation
- Cryptographically secure session tokens (64 bytes)
- 24-hour session expiration with sliding window
- HTTP-only secure cookies for session management
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Response, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from api.models.web_ui_models import User, Session as SessionModel
from api.models.error_models import ErrorCode
from api.exceptions import AuthenticationException


# Security configuration
SESSION_COOKIE_NAME = "session_token"
SESSION_EXPIRY_HOURS = 24
TOKEN_BYTES = 64  # 64 bytes = 512 bits of entropy

# HTTP Bearer for optional token-based auth (future expansion)
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with automatic salt generation.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Bcrypt password hash as string
        
    Example:
        >>> hashed = hash_password("my_secure_password")
        >>> verify_password("my_secure_password", hashed)
        True
    """
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    password_bytes = password.encode('utf-8')
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verify a password against a bcrypt hash.
    
    Args:
        plain_password: Plain text password to verify
        password_hash: Bcrypt hash to verify against
        
    Returns:
        True if password matches hash, False otherwise
        
    Example:
        >>> hashed = hash_password("secret")
        >>> verify_password("secret", hashed)
        True
        >>> verify_password("wrong", hashed)
        False
    """
    password_bytes = plain_password.encode('utf-8')
    hash_bytes = password_hash.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hash_bytes)


def generate_session_token() -> str:
    """
    Generate a cryptographically secure random session token.
    
    Uses secrets.token_hex() which is suitable for security-sensitive
    applications like session tokens and password reset tokens.
    
    Returns:
        Hex-encoded random token (128 characters for 64 bytes)
        
    Example:
        >>> token = generate_session_token()
        >>> len(token)
        128
    """
    return secrets.token_hex(TOKEN_BYTES)


def create_session(db: Session, user_id: int) -> SessionModel:
    """
    Create a new session for a user.
    
    Generates a cryptographically secure session token and stores it
    in the database with expiration time.
    
    Args:
        db: Database session
        user_id: ID of the user to create session for
        
    Returns:
        Created SessionModel instance
        
    Raises:
        ValueError: If user_id is invalid
    """
    # Generate secure session token
    token = generate_session_token()
    
    # Calculate expiration time
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=SESSION_EXPIRY_HOURS)
    
    # Create session record
    session = SessionModel(
        id=token,
        user_id=user_id,
        created_at=now,
        expires_at=expires_at,
        last_accessed=now
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return session


def get_session(db: Session, token: str) -> Optional[SessionModel]:
    """
    Retrieve a session by token.
    
    Args:
        db: Database session
        token: Session token to look up
        
    Returns:
        SessionModel if found, None otherwise
    """
    return db.query(SessionModel).filter(SessionModel.id == token).first()


def validate_session(db: Session, token: str) -> Optional[SessionModel]:
    """
    Validate a session token and check expiration.
    
    Updates last_accessed timestamp if session is valid.
    
    Args:
        db: Database session
        token: Session token to validate
        
    Returns:
        SessionModel if valid and not expired, None otherwise
    """
    session = get_session(db, token)
    
    if not session:
        return None
    
    # Check if session has expired
    now = datetime.utcnow()
    if now > session.expires_at:
        # Session expired, delete it
        db.delete(session)
        db.commit()
        return None
    
    # Update last accessed time (sliding window)
    session.last_accessed = now
    db.commit()
    
    return session


def invalidate_session(db: Session, token: str) -> bool:
    """
    Invalidate a session by deleting it from the database.
    
    Args:
        db: Database session
        token: Session token to invalidate
        
    Returns:
        True if session was found and deleted, False otherwise
    """
    session = get_session(db, token)
    
    if not session:
        return False
    
    db.delete(session)
    db.commit()
    return True


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password.
    
    Args:
        db: Database session
        username: Username to authenticate
        password: Plain text password to verify
        
    Returns:
        User object if authentication successful, None otherwise
    """
    # Find user by username
    user = db.query(User).filter(User.username == username).first()
    
    if not user:
        return None
    
    # Verify password
    if not verify_password(password, user.password_hash):
        return None
    
    return user


def get_session_token_from_cookie(request: Request) -> Optional[str]:
    """
    Extract session token from HTTP-only cookie.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Session token if present in cookie, None otherwise
    """
    return request.cookies.get(SESSION_COOKIE_NAME)


def set_session_cookie(response: Response, token: str) -> None:
    """
    Set session token in HTTP-only secure cookie.

    In production (ENVIRONMENT=production): secure=True, httponly=True, samesite="strict".
    In development: secure=False, samesite="lax".

    Requirements: 4.6
    """
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_production,
        samesite="strict" if is_production else "lax",
        max_age=SESSION_EXPIRY_HOURS * 3600
    )


def clear_session_cookie(response: Response) -> None:
    """
    Clear session cookie from response.

    Requirements: 4.6
    """
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=is_production,
        samesite="strict" if is_production else "lax"
    )


# Dependency for protected routes
def get_current_user(
    request: Request,
    db: Session
) -> User:
    """
    FastAPI dependency for protected routes.
    
    Validates session token from cookie and returns the authenticated user.
    Raises AuthenticationException if authentication fails.
    
    Args:
        request: FastAPI request object
        db: Database session (injected by FastAPI)
        
    Returns:
        Authenticated User object
        
    Raises:
        AuthenticationException: 401 if authentication fails
        
    Example:
        @app.get("/api/v1/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"message": f"Hello {user.username}"}
    """
    # Extract session token from cookie
    token = get_session_token_from_cookie(request)
    
    if not token:
        raise AuthenticationException(
            message="Not authenticated",
            code=ErrorCode.AUTH_NOT_AUTHENTICATED
        )
    
    # Validate session
    session = validate_session(db, token)
    
    if not session:
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED
        )
    
    # Get user from session
    user = db.query(User).filter(User.id == session.user_id).first()
    
    if not user:
        raise AuthenticationException(
            message="User not found",
            code=ErrorCode.AUTH_INVALID_TOKEN
        )
    
    return user


# Optional: Dependency for routes that need user ID only
def get_current_user_id(
    request: Request,
    db: Session
) -> int:
    """
    FastAPI dependency that returns only the user ID.
    
    Lighter weight alternative to get_current_user when only ID is needed.
    
    Args:
        request: FastAPI request object
        db: Database session (injected by FastAPI)
        
    Returns:
        User ID
        
    Raises:
        AuthenticationException: 401 if authentication fails
    """
    user = get_current_user(request, db)
    return user.id

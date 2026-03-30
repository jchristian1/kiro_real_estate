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
- HMAC-SHA256 token derivation: raw token is set in the cookie, only the
  HMAC digest is stored in the DB — a DB read does not yield usable tokens
- 24-hour session expiration with sliding window
- HTTP-only secure cookies for session management
"""

import hashlib
import hmac
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


def derive_session_digest(secret_key: str, raw_token: str) -> str:
    """
    Derive the value stored in the DB from a raw session token.

    The raw token is placed in the cookie; only this HMAC-SHA256 digest is
    persisted.  A DB read therefore does not yield a usable session token.

    Args:
        secret_key: Application secret key (from config.secret_key)
        raw_token:  Raw session token as returned by generate_session_token()

    Returns:
        64-character lowercase hex string (SHA-256 output)
    """
    return hmac.new(
        secret_key.encode(),
        raw_token.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_session(db: Session, user_id: int, secret_key: str) -> SessionModel:
    """
    Create a new session for a user.

    Generates a cryptographically secure raw session token, derives an
    HMAC-SHA256 digest, stores the digest in the DB, and returns a
    SessionModel whose ``id`` field holds the digest.  The caller is
    responsible for placing the raw token in the cookie via
    ``set_session_cookie(response, raw_token)``.

    Args:
        db: Database session
        user_id: ID of the user to create session for
        secret_key: Application secret key used to derive the stored digest

    Returns:
        Created SessionModel instance (id == HMAC digest, not the raw token)

    Raises:
        ValueError: If user_id is invalid
    """
    raw_token = generate_session_token()
    stored_digest = derive_session_digest(secret_key, raw_token)

    now = datetime.utcnow()
    expires_at = now + timedelta(hours=SESSION_EXPIRY_HOURS)

    session = SessionModel(
        id=stored_digest,
        user_id=user_id,
        created_at=now,
        expires_at=expires_at,
        last_accessed=now,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    # Attach the raw token so the caller can set it in the cookie.
    # This attribute is NOT persisted — it exists only for this request.
    session._raw_token = raw_token  # type: ignore[attr-defined]

    return session


def get_session(db: Session, digest: str) -> Optional[SessionModel]:
    """
    Retrieve a session by its stored HMAC digest.

    Args:
        db: Database session
        digest: HMAC-SHA256 digest as stored in the DB

    Returns:
        SessionModel if found, None otherwise
    """
    return db.query(SessionModel).filter(SessionModel.id == digest).first()


def validate_session(db: Session, raw_token: str, secret_key: str) -> Optional[SessionModel]:
    """
    Validate a raw session token from the cookie and check expiration.

    Derives the HMAC digest from the raw token, looks it up in the DB,
    and updates last_accessed if valid.

    Args:
        db: Database session
        raw_token: Raw session token read from the cookie
        secret_key: Application secret key used to derive the stored digest

    Returns:
        SessionModel if valid and not expired, None otherwise
    """
    digest = derive_session_digest(secret_key, raw_token)
    session = get_session(db, digest)

    if not session:
        return None

    now = datetime.utcnow()
    if now > session.expires_at:
        db.delete(session)
        db.commit()
        return None

    session.last_accessed = now
    db.commit()

    return session


def invalidate_session(db: Session, raw_token: str, secret_key: str) -> bool:
    """
    Invalidate a session by deleting it from the database.

    Derives the HMAC digest from the raw token and deletes the matching row.

    Args:
        db: Database session
        raw_token: Raw session token read from the cookie
        secret_key: Application secret key used to derive the stored digest

    Returns:
        True if session was found and deleted, False otherwise
    """
    digest = derive_session_digest(secret_key, raw_token)
    session = get_session(db, digest)

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
    db: Session,
    secret_key: str,
) -> User:
    """
    FastAPI dependency for protected routes.

    Validates the raw session token from the cookie by deriving its HMAC
    digest and looking it up in the DB.  Raises AuthenticationException if
    authentication fails.

    Args:
        request: FastAPI request object
        db: Database session (injected by FastAPI)
        secret_key: Application secret key for HMAC digest derivation

    Returns:
        Authenticated User object

    Raises:
        AuthenticationException: 401 if authentication fails
    """
    token = get_session_token_from_cookie(request)

    if not token:
        raise AuthenticationException(
            message="Not authenticated",
            code=ErrorCode.AUTH_NOT_AUTHENTICATED
        )

    session = validate_session(db, token, secret_key)

    if not session:
        raise AuthenticationException(
            message="Invalid or expired session",
            code=ErrorCode.AUTH_SESSION_EXPIRED
        )

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
    db: Session,
    secret_key: str,
) -> int:
    """
    FastAPI dependency that returns only the user ID.

    Lighter weight alternative to get_current_user when only ID is needed.

    Args:
        request: FastAPI request object
        db: Database session (injected by FastAPI)
        secret_key: Application secret key for HMAC digest derivation

    Returns:
        User ID

    Raises:
        AuthenticationException: 401 if authentication fails
    """
    user = get_current_user(request, db, secret_key)
    return user.id

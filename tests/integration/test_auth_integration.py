"""
Integration tests for authentication module.

Tests the complete authentication flow with a real database:
- User creation with password hashing
- Login and session creation
- Session validation
- Logout and session invalidation
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base
from api.models.web_ui_models import User, Session as SessionModel
from api.auth import (
    hash_password,
    authenticate_user,
    create_session,
    validate_session,
    invalidate_session
)


@pytest.fixture
def db_session():
    """Create an in-memory database for testing."""
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user in the database."""
    password = "test_password_123"
    user = User(
        username="testuser",
        password_hash=hash_password(password),
        role="admin"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user, password


class TestAuthenticationIntegration:
    """Integration tests for complete authentication flow."""
    
    def test_complete_login_flow(self, db_session, test_user):
        """Test complete login flow: authenticate -> create session -> validate."""
        user, password = test_user
        
        # Step 1: Authenticate user
        authenticated_user = authenticate_user(db_session, user.username, password)
        assert authenticated_user is not None
        assert authenticated_user.id == user.id
        assert authenticated_user.username == user.username
        
        # Step 2: Create session
        session = create_session(db_session, authenticated_user.id)
        assert session is not None
        assert len(session.id) == 128  # 64 bytes hex encoded
        assert session.user_id == user.id
        
        # Step 3: Validate session
        validated_session = validate_session(db_session, session.id)
        assert validated_session is not None
        assert validated_session.id == session.id
        assert validated_session.user_id == user.id
    
    def test_complete_logout_flow(self, db_session, test_user):
        """Test complete logout flow: create session -> invalidate."""
        user, _ = test_user
        
        # Create session
        session = create_session(db_session, user.id)
        token = session.id
        
        # Verify session exists
        assert validate_session(db_session, token) is not None
        
        # Invalidate session
        result = invalidate_session(db_session, token)
        assert result is True
        
        # Verify session no longer exists
        assert validate_session(db_session, token) is None
    
    def test_failed_login_wrong_password(self, db_session, test_user):
        """Test login fails with wrong password."""
        user, _ = test_user
        
        authenticated_user = authenticate_user(db_session, user.username, "wrong_password")
        assert authenticated_user is None
    
    def test_failed_login_nonexistent_user(self, db_session):
        """Test login fails with nonexistent user."""
        authenticated_user = authenticate_user(db_session, "nonexistent", "password")
        assert authenticated_user is None
    
    def test_session_expiration(self, db_session, test_user):
        """Test that expired sessions are invalidated."""
        user, _ = test_user
        
        # Create session with expired time
        now = datetime.utcnow()
        expired_session = SessionModel(
            id="expired_token_123",
            user_id=user.id,
            created_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),  # Expired 1 hour ago
            last_accessed=now - timedelta(hours=2)
        )
        db_session.add(expired_session)
        db_session.commit()
        
        # Try to validate expired session
        result = validate_session(db_session, expired_session.id)
        assert result is None
        
        # Verify session was deleted
        session_in_db = db_session.query(SessionModel).filter(
            SessionModel.id == expired_session.id
        ).first()
        assert session_in_db is None
    
    def test_multiple_sessions_per_user(self, db_session, test_user):
        """Test that a user can have multiple active sessions."""
        user, _ = test_user
        
        # Create multiple sessions
        session1 = create_session(db_session, user.id)
        session2 = create_session(db_session, user.id)
        
        # Both sessions should be valid
        assert validate_session(db_session, session1.id) is not None
        assert validate_session(db_session, session2.id) is not None
        
        # Sessions should have different tokens
        assert session1.id != session2.id
    
    def test_session_last_accessed_update(self, db_session, test_user):
        """Test that session last_accessed is updated on validation."""
        user, _ = test_user
        
        # Create session
        session = create_session(db_session, user.id)
        original_last_accessed = session.last_accessed
        
        # Wait a moment and validate
        import time
        time.sleep(0.1)
        
        validated_session = validate_session(db_session, session.id)
        
        # last_accessed should be updated
        assert validated_session.last_accessed > original_last_accessed
    
    def test_password_hash_uniqueness(self, db_session):
        """Test that same password produces different hashes for different users."""
        password = "same_password"
        
        user1 = User(
            username="user1",
            password_hash=hash_password(password),
            role="admin"
        )
        user2 = User(
            username="user2",
            password_hash=hash_password(password),
            role="admin"
        )
        
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        # Hashes should be different (due to different salts)
        assert user1.password_hash != user2.password_hash
        
        # But both should authenticate with the same password
        assert authenticate_user(db_session, "user1", password) is not None
        assert authenticate_user(db_session, "user2", password) is not None

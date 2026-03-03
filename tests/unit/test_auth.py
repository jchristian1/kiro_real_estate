"""
Unit tests for authentication module.

Tests cover:
- Password hashing and verification
- Session token generation
- Session creation and validation
- Session expiration
- User authentication
- Cookie handling
- Authentication dependency
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from api.auth import (
    hash_password,
    verify_password,
    generate_session_token,
    create_session,
    get_session,
    validate_session,
    invalidate_session,
    authenticate_user,
    get_session_token_from_cookie,
    set_session_cookie,
    clear_session_cookie,
    get_current_user,
    SESSION_COOKIE_NAME,
    SESSION_EXPIRY_HOURS,
    TOKEN_BYTES
)
from api.exceptions import AuthenticationException
from api.models.web_ui_models import User, Session as SessionModel
from fastapi import Request, Response


class TestPasswordHashing:
    """Tests for password hashing and verification."""
    
    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string."""
        password = "test_password_123"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_hash_password_different_each_time(self):
        """Test that hashing the same password produces different hashes (due to salt)."""
        password = "test_password_123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """Test that verify_password returns True for correct password."""
        password = "correct_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test that verify_password returns False for incorrect password."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False
    
    def test_verify_password_empty_string(self):
        """Test password verification with empty string."""
        password = ""
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("not_empty", hashed) is False
    
    def test_hash_password_special_characters(self):
        """Test password hashing with special characters."""
        password = "p@ssw0rd!#$%^&*()"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


class TestSessionTokenGeneration:
    """Tests for session token generation."""
    
    def test_generate_session_token_returns_string(self):
        """Test that generate_session_token returns a string."""
        token = generate_session_token()
        assert isinstance(token, str)
    
    def test_generate_session_token_correct_length(self):
        """Test that token has correct length (128 hex chars for 64 bytes)."""
        token = generate_session_token()
        assert len(token) == TOKEN_BYTES * 2  # Hex encoding doubles length
    
    def test_generate_session_token_unique(self):
        """Test that generated tokens are unique."""
        tokens = [generate_session_token() for _ in range(100)]
        assert len(set(tokens)) == 100  # All unique
    
    def test_generate_session_token_hex_format(self):
        """Test that token contains only hex characters."""
        token = generate_session_token()
        assert all(c in '0123456789abcdef' for c in token)


class TestSessionManagement:
    """Tests for session creation, validation, and invalidation."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db
    
    @pytest.fixture
    def test_user_id(self):
        """Test user ID."""
        return 1
    
    def test_create_session(self, mock_db, test_user_id):
        """Test session creation."""
        session = create_session(mock_db, test_user_id)
        
        assert session.user_id == test_user_id
        assert len(session.id) == TOKEN_BYTES * 2
        assert session.created_at is not None
        assert session.expires_at is not None
        assert session.last_accessed is not None
        
        # Check expiration is set correctly
        expected_expiry = session.created_at + timedelta(hours=SESSION_EXPIRY_HOURS)
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 1
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
    
    def test_get_session_found(self, mock_db):
        """Test getting an existing session."""
        token = "test_token_123"
        mock_session = SessionModel(
            id=token,
            user_id=1,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            last_accessed=datetime.utcnow()
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        
        result = get_session(mock_db, token)
        
        assert result == mock_session
        mock_db.query.assert_called_once_with(SessionModel)
    
    def test_get_session_not_found(self, mock_db):
        """Test getting a non-existent session."""
        token = "nonexistent_token"
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = get_session(mock_db, token)
        
        assert result is None
    
    def test_validate_session_valid(self, mock_db):
        """Test validating a valid, non-expired session."""
        token = "valid_token"
        now = datetime.utcnow()
        mock_session = SessionModel(
            id=token,
            user_id=1,
            created_at=now - timedelta(hours=1),
            expires_at=now + timedelta(hours=23),
            last_accessed=now - timedelta(minutes=5)
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        
        result = validate_session(mock_db, token)
        
        assert result == mock_session
        # Verify last_accessed was updated
        assert (datetime.utcnow() - result.last_accessed).total_seconds() < 1
        mock_db.commit.assert_called()
    
    def test_validate_session_expired(self, mock_db):
        """Test validating an expired session."""
        token = "expired_token"
        now = datetime.utcnow()
        mock_session = SessionModel(
            id=token,
            user_id=1,
            created_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),  # Expired 1 hour ago
            last_accessed=now - timedelta(hours=2)
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        
        result = validate_session(mock_db, token)
        
        assert result is None
        # Verify session was deleted
        mock_db.delete.assert_called_once_with(mock_session)
        mock_db.commit.assert_called()
    
    def test_validate_session_not_found(self, mock_db):
        """Test validating a non-existent session."""
        token = "nonexistent_token"
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = validate_session(mock_db, token)
        
        assert result is None
        mock_db.delete.assert_not_called()
    
    def test_invalidate_session_success(self, mock_db):
        """Test invalidating an existing session."""
        token = "token_to_invalidate"
        mock_session = SessionModel(
            id=token,
            user_id=1,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            last_accessed=datetime.utcnow()
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        
        result = invalidate_session(mock_db, token)
        
        assert result is True
        mock_db.delete.assert_called_once_with(mock_session)
        mock_db.commit.assert_called()
    
    def test_invalidate_session_not_found(self, mock_db):
        """Test invalidating a non-existent session."""
        token = "nonexistent_token"
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = invalidate_session(mock_db, token)
        
        assert result is False
        mock_db.delete.assert_not_called()


class TestUserAuthentication:
    """Tests for user authentication."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        return db
    
    def test_authenticate_user_success(self, mock_db):
        """Test successful user authentication."""
        username = "testuser"
        password = "correct_password"
        password_hash = hash_password(password)
        
        mock_user = User(
            id=1,
            username=username,
            password_hash=password_hash,
            role="admin"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        result = authenticate_user(mock_db, username, password)
        
        assert result == mock_user
    
    def test_authenticate_user_wrong_password(self, mock_db):
        """Test authentication with wrong password."""
        username = "testuser"
        correct_password = "correct_password"
        wrong_password = "wrong_password"
        password_hash = hash_password(correct_password)
        
        mock_user = User(
            id=1,
            username=username,
            password_hash=password_hash,
            role="admin"
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        result = authenticate_user(mock_db, username, wrong_password)
        
        assert result is None
    
    def test_authenticate_user_not_found(self, mock_db):
        """Test authentication with non-existent user."""
        username = "nonexistent"
        password = "any_password"
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = authenticate_user(mock_db, username, password)
        
        assert result is None


class TestCookieHandling:
    """Tests for cookie handling functions."""
    
    def test_get_session_token_from_cookie_present(self):
        """Test extracting session token from cookie."""
        token = "test_session_token"
        mock_request = Mock(spec=Request)
        mock_request.cookies = {SESSION_COOKIE_NAME: token}
        
        result = get_session_token_from_cookie(mock_request)
        
        assert result == token
    
    def test_get_session_token_from_cookie_missing(self):
        """Test extracting session token when cookie is missing."""
        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        
        result = get_session_token_from_cookie(mock_request)
        
        assert result is None
    
    def test_set_session_cookie(self):
        """Test setting session cookie."""
        token = "test_session_token"
        mock_response = Mock(spec=Response)
        
        set_session_cookie(mock_response, token)
        
        mock_response.set_cookie.assert_called_once()
        call_kwargs = mock_response.set_cookie.call_args[1]
        
        assert call_kwargs['key'] == SESSION_COOKIE_NAME
        assert call_kwargs['value'] == token
        assert call_kwargs['httponly'] is True
        assert call_kwargs['secure'] is True
        assert call_kwargs['samesite'] == "lax"
        assert call_kwargs['max_age'] == SESSION_EXPIRY_HOURS * 3600
    
    def test_clear_session_cookie(self):
        """Test clearing session cookie."""
        mock_response = Mock(spec=Response)
        
        clear_session_cookie(mock_response)
        
        mock_response.delete_cookie.assert_called_once()
        call_kwargs = mock_response.delete_cookie.call_args[1]
        
        assert call_kwargs['key'] == SESSION_COOKIE_NAME
        assert call_kwargs['httponly'] is True
        assert call_kwargs['secure'] is True
        assert call_kwargs['samesite'] == "lax"


class TestAuthenticationDependency:
    """Tests for FastAPI authentication dependency."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = Mock(spec=Request)
        request.cookies = {}
        return request
    
    def test_get_current_user_success(self, mock_db, mock_request):
        """Test successful authentication via dependency."""
        token = "valid_token"
        mock_request.cookies = {SESSION_COOKIE_NAME: token}
        
        now = datetime.utcnow()
        mock_session = SessionModel(
            id=token,
            user_id=1,
            created_at=now,
            expires_at=now + timedelta(hours=24),
            last_accessed=now
        )
        
        mock_user = User(
            id=1,
            username="testuser",
            password_hash="hash",
            role="admin"
        )
        
        # Setup mock query chain for session
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_session,  # First call for validate_session
            mock_user      # Second call for get user
        ]
        
        result = get_current_user(mock_request, mock_db)
        
        assert result == mock_user
    
    def test_get_current_user_no_cookie(self, mock_db, mock_request):
        """Test authentication fails when no cookie present."""
        mock_request.cookies = {}
        
        with pytest.raises(AuthenticationException) as exc_info:
            get_current_user(mock_request, mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.message
    
    def test_get_current_user_invalid_session(self, mock_db, mock_request):
        """Test authentication fails with invalid session."""
        token = "invalid_token"
        mock_request.cookies = {SESSION_COOKIE_NAME: token}
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(AuthenticationException) as exc_info:
            get_current_user(mock_request, mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Invalid or expired session" in exc_info.value.message
    
    def test_get_current_user_expired_session(self, mock_db, mock_request):
        """Test authentication fails with expired session."""
        token = "expired_token"
        mock_request.cookies = {SESSION_COOKIE_NAME: token}
        
        now = datetime.utcnow()
        mock_session = SessionModel(
            id=token,
            user_id=1,
            created_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),  # Expired
            last_accessed=now - timedelta(hours=2)
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        
        with pytest.raises(AuthenticationException) as exc_info:
            get_current_user(mock_request, mock_db)
        
        assert exc_info.value.status_code == 401
        assert "Invalid or expired session" in exc_info.value.message

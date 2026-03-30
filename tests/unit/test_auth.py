"""
Unit tests for authentication module.

Tests cover:
- Password hashing and verification
- Session token generation
- HMAC digest derivation (derive_session_digest)
- Session creation and validation
- Session expiration
- User authentication
- Cookie handling
- Authentication dependency
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from api.auth import (
    hash_password,
    verify_password,
    generate_session_token,
    derive_session_digest,
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
    TOKEN_BYTES,
)
from api.exceptions import AuthenticationException
from api.models.web_ui_models import User, Session as SessionModel
from fastapi import Request, Response

# Fixed test secret used across all tests that need one.
TEST_SECRET = "unit-test-secret-key-at-least-32-chars!!"


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_returns_string(self):
        hashed = hash_password("test_password_123")
        assert isinstance(hashed, str) and len(hashed) > 0

    def test_hash_password_different_each_time(self):
        password = "test_password_123"
        assert hash_password(password) != hash_password(password)

    def test_verify_password_correct(self):
        password = "correct_password"
        assert verify_password(password, hash_password(password)) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_empty_string(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("not_empty", hashed) is False

    def test_hash_password_special_characters(self):
        password = "p@ssw0rd!#$%^&*()"
        assert verify_password(password, hash_password(password)) is True


class TestSessionTokenGeneration:
    """Tests for session token generation."""

    def test_generate_session_token_returns_string(self):
        assert isinstance(generate_session_token(), str)

    def test_generate_session_token_correct_length(self):
        assert len(generate_session_token()) == TOKEN_BYTES * 2

    def test_generate_session_token_unique(self):
        tokens = [generate_session_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_generate_session_token_hex_format(self):
        assert all(c in '0123456789abcdef' for c in generate_session_token())


class TestDeriveSessionDigest:
    """Tests for HMAC digest derivation."""

    def test_digest_is_64_hex_chars(self):
        digest = derive_session_digest(TEST_SECRET, "some_raw_token")
        assert len(digest) == 64
        assert all(c in '0123456789abcdef' for c in digest)

    def test_digest_is_deterministic(self):
        raw = generate_session_token()
        assert derive_session_digest(TEST_SECRET, raw) == derive_session_digest(TEST_SECRET, raw)

    def test_different_tokens_produce_different_digests(self):
        raw1 = generate_session_token()
        raw2 = generate_session_token()
        assert derive_session_digest(TEST_SECRET, raw1) != derive_session_digest(TEST_SECRET, raw2)

    def test_different_secrets_produce_different_digests(self):
        raw = generate_session_token()
        d1 = derive_session_digest("secret-one-padded-to-32-chars-xx", raw)
        d2 = derive_session_digest("secret-two-padded-to-32-chars-xx", raw)
        assert d1 != d2

    def test_digest_differs_from_raw_token(self):
        raw = generate_session_token()
        assert derive_session_digest(TEST_SECRET, raw) != raw


class TestSessionManagement:
    """Tests for session creation, validation, and invalidation."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        return db

    def test_create_session_stores_digest_not_raw_token(self, mock_db):
        """The DB id must be the HMAC digest, not the raw token."""
        session = create_session(mock_db, user_id=1, secret_key=TEST_SECRET)
        raw_token = session._raw_token

        assert raw_token is not None
        assert len(raw_token) == TOKEN_BYTES * 2
        # id stored in DB is the digest
        assert session.id == derive_session_digest(TEST_SECRET, raw_token)
        assert session.id != raw_token

    def test_create_session_sets_user_id_and_expiry(self, mock_db):
        session = create_session(mock_db, user_id=42, secret_key=TEST_SECRET)
        assert session.user_id == 42
        expected_expiry = session.created_at + timedelta(hours=SESSION_EXPIRY_HOURS)
        assert abs((session.expires_at - expected_expiry).total_seconds()) < 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()

    def test_get_session_found(self, mock_db):
        digest = "a" * 64
        mock_session = SessionModel(
            id=digest, user_id=1,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            last_accessed=datetime.utcnow(),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        assert get_session(mock_db, digest) == mock_session

    def test_get_session_not_found(self, mock_db):
        assert get_session(mock_db, "nonexistent") is None

    def test_validate_session_valid(self, mock_db):
        """validate_session derives the digest and returns the session if valid."""
        raw_token = generate_session_token()
        digest = derive_session_digest(TEST_SECRET, raw_token)
        now = datetime.utcnow()
        mock_session = SessionModel(
            id=digest, user_id=1,
            created_at=now - timedelta(hours=1),
            expires_at=now + timedelta(hours=23),
            last_accessed=now - timedelta(minutes=5),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = validate_session(mock_db, raw_token, TEST_SECRET)

        assert result == mock_session
        assert (datetime.utcnow() - result.last_accessed).total_seconds() < 1
        mock_db.commit.assert_called()

    def test_validate_session_wrong_token_returns_none(self, mock_db):
        """A wrong raw token produces a different digest → not found → None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert validate_session(mock_db, "wrong_raw_token", TEST_SECRET) is None

    def test_validate_session_expired(self, mock_db):
        raw_token = generate_session_token()
        digest = derive_session_digest(TEST_SECRET, raw_token)
        now = datetime.utcnow()
        mock_session = SessionModel(
            id=digest, user_id=1,
            created_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),
            last_accessed=now - timedelta(hours=2),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = validate_session(mock_db, raw_token, TEST_SECRET)

        assert result is None
        mock_db.delete.assert_called_once_with(mock_session)
        mock_db.commit.assert_called()

    def test_validate_session_not_found(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = validate_session(mock_db, generate_session_token(), TEST_SECRET)
        assert result is None
        mock_db.delete.assert_not_called()

    def test_invalidate_session_success(self, mock_db):
        raw_token = generate_session_token()
        digest = derive_session_digest(TEST_SECRET, raw_token)
        mock_session = SessionModel(
            id=digest, user_id=1,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            last_accessed=datetime.utcnow(),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session

        result = invalidate_session(mock_db, raw_token, TEST_SECRET)

        assert result is True
        mock_db.delete.assert_called_once_with(mock_session)
        mock_db.commit.assert_called()

    def test_invalidate_session_not_found(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert invalidate_session(mock_db, generate_session_token(), TEST_SECRET) is False
        mock_db.delete.assert_not_called()


class TestUserAuthentication:
    """Tests for user authentication."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_authenticate_user_success(self, mock_db):
        password = "correct_password"
        mock_user = User(id=1, username="testuser",
                         password_hash=hash_password(password), role="admin")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        assert authenticate_user(mock_db, "testuser", password) == mock_user

    def test_authenticate_user_wrong_password(self, mock_db):
        mock_user = User(id=1, username="testuser",
                         password_hash=hash_password("correct"), role="admin")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        assert authenticate_user(mock_db, "testuser", "wrong") is None

    def test_authenticate_user_not_found(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        assert authenticate_user(mock_db, "nonexistent", "any") is None


class TestCookieHandling:
    """Tests for cookie handling functions."""

    def test_get_session_token_from_cookie_present(self):
        mock_request = Mock(spec=Request)
        mock_request.cookies = {SESSION_COOKIE_NAME: "some_token"}
        assert get_session_token_from_cookie(mock_request) == "some_token"

    def test_get_session_token_from_cookie_missing(self):
        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        assert get_session_token_from_cookie(mock_request) is None

    def test_set_session_cookie(self):
        import os
        mock_response = Mock(spec=Response)
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            set_session_cookie(mock_response, "tok")
        kw = mock_response.set_cookie.call_args[1]
        assert kw['key'] == SESSION_COOKIE_NAME
        assert kw['value'] == "tok"
        assert kw['httponly'] is True
        assert kw['secure'] is True
        assert kw['max_age'] == SESSION_EXPIRY_HOURS * 3600

    def test_clear_session_cookie(self):
        import os
        mock_response = Mock(spec=Response)
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            clear_session_cookie(mock_response)
        kw = mock_response.delete_cookie.call_args[1]
        assert kw['key'] == SESSION_COOKIE_NAME
        assert kw['httponly'] is True
        assert kw['secure'] is True


class TestAuthenticationDependency:
    """Tests for FastAPI authentication dependency."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_request(self):
        request = Mock(spec=Request)
        request.cookies = {}
        return request

    def test_get_current_user_success(self, mock_db, mock_request):
        raw_token = generate_session_token()
        digest = derive_session_digest(TEST_SECRET, raw_token)
        mock_request.cookies = {SESSION_COOKIE_NAME: raw_token}
        now = datetime.utcnow()
        mock_session = SessionModel(
            id=digest, user_id=1,
            created_at=now,
            expires_at=now + timedelta(hours=24),
            last_accessed=now,
        )
        mock_user = User(id=1, username="testuser", password_hash="hash", role="admin")
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_session,
            mock_user,
        ]
        result = get_current_user(mock_request, mock_db, TEST_SECRET)
        assert result == mock_user

    def test_get_current_user_no_cookie(self, mock_db, mock_request):
        mock_request.cookies = {}
        with pytest.raises(AuthenticationException) as exc_info:
            get_current_user(mock_request, mock_db, TEST_SECRET)
        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.message

    def test_get_current_user_invalid_session(self, mock_db, mock_request):
        mock_request.cookies = {SESSION_COOKIE_NAME: generate_session_token()}
        mock_db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(AuthenticationException) as exc_info:
            get_current_user(mock_request, mock_db, TEST_SECRET)
        assert exc_info.value.status_code == 401
        assert "Invalid or expired session" in exc_info.value.message

    def test_get_current_user_expired_session(self, mock_db, mock_request):
        raw_token = generate_session_token()
        digest = derive_session_digest(TEST_SECRET, raw_token)
        mock_request.cookies = {SESSION_COOKIE_NAME: raw_token}
        now = datetime.utcnow()
        mock_session = SessionModel(
            id=digest, user_id=1,
            created_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),
            last_accessed=now - timedelta(hours=2),
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        with pytest.raises(AuthenticationException) as exc_info:
            get_current_user(mock_request, mock_db, TEST_SECRET)
        assert exc_info.value.status_code == 401
        assert "Invalid or expired session" in exc_info.value.message

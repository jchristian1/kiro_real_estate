"""
Unit tests for authentication routes.

Tests cover:
- Login endpoint with valid and invalid credentials
- Logout endpoint
- Get current user endpoint
- Cookie handling in responses
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from api.main import app, get_db
from api.auth import hash_password, SESSION_COOKIE_NAME
from gmail_lead_sync.models import Base
from api.models.web_ui_models import User, Session as SessionModel


# Create test database
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override get_db dependency
def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def test_db():
    """Create test database and tables."""
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_user(test_db):
    """Create a test user."""
    user = User(
        username="testuser",
        password_hash=hash_password("testpassword"),
        role="admin"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def client():
    """Create test client."""
    return TestClient(app)


class TestLoginEndpoint:
    """Tests for POST /auth/login endpoint."""
    
    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "user" in data
        assert data["user"]["id"] == test_user.id
        assert data["user"]["username"] == "testuser"
        assert data["user"]["role"] == "admin"
        
        # Check that password hash is not included
        assert "password_hash" not in data["user"]
        
        # Check that session cookie is set
        assert SESSION_COOKIE_NAME in response.cookies
        session_token = response.cookies[SESSION_COOKIE_NAME]
        assert len(session_token) > 0
    
    def test_login_invalid_username(self, client, test_user):
        """Test login with invalid username."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "nonexistent",
                "password": "testpassword"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "message" in data
        assert "Invalid username or password" in data["message"]
    
    def test_login_invalid_password(self, client, test_user):
        """Test login with invalid password."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "message" in data
        assert "Invalid username or password" in data["message"]
    
    def test_login_missing_username(self, client):
        """Test login with missing username."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "password": "testpassword"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_login_missing_password(self, client):
        """Test login with missing password."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_login_empty_username(self, client):
        """Test login with empty username."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "",
                "password": "testpassword"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_login_empty_password(self, client):
        """Test login with empty password."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": ""
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestLogoutEndpoint:
    """Tests for POST /auth/logout endpoint."""
    
    def test_logout_success(self, client, test_user, test_db):
        """Test successful logout."""
        # First login to get a session
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        assert login_response.status_code == 200
        session_token = login_response.cookies[SESSION_COOKIE_NAME]
        
        # Verify session exists in database
        session = test_db.query(SessionModel).filter(SessionModel.id == session_token).first()
        assert session is not None
        
        # Now logout
        logout_response = client.post("/api/v1/auth/logout")
        
        assert logout_response.status_code == 200
        data = logout_response.json()
        assert data["message"] == "Logged out successfully"
        
        # Verify session is deleted from database
        session = test_db.query(SessionModel).filter(SessionModel.id == session_token).first()
        assert session is None
        
        # Verify cookie is cleared (empty or expired)
        # Note: TestClient may not perfectly simulate cookie clearing
    
    def test_logout_without_session(self, client):
        """Test logout without an active session."""
        response = client.post("/api/v1/auth/logout")
        
        # Should still succeed (idempotent)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logged out successfully"


class TestGetMeEndpoint:
    """Tests for GET /auth/me endpoint."""
    
    def test_get_me_success(self, client, test_user):
        """Test getting current user info with valid session."""
        # First login to get a session
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        assert login_response.status_code == 200
        
        # Now get current user
        me_response = client.get("/api/v1/auth/me")
        
        assert me_response.status_code == 200
        data = me_response.json()
        
        assert data["id"] == test_user.id
        assert data["username"] == "testuser"
        assert data["role"] == "admin"
        assert "password_hash" not in data
    
    def test_get_me_no_session(self, client):
        """Test getting current user without session."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        data = response.json()
        assert "message" in data
        assert "Not authenticated" in data["message"]
    
    def test_get_me_invalid_session(self, client):
        """Test getting current user with invalid session token."""
        # Set invalid session cookie
        client.cookies.set(SESSION_COOKIE_NAME, "invalid_token_12345")
        
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        data = response.json()
        assert "message" in data
        assert "Invalid or expired session" in data["message"]
    
    def test_get_me_expired_session(self, client, test_user, test_db):
        """Test getting current user with expired session."""
        # Create an expired session manually
        now = datetime.utcnow()
        expired_session = SessionModel(
            id="expired_token_12345",
            user_id=test_user.id,
            created_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),  # Expired 1 hour ago
            last_accessed=now - timedelta(hours=2)
        )
        test_db.add(expired_session)
        test_db.commit()
        
        # Set expired session cookie
        client.cookies.set(SESSION_COOKIE_NAME, expired_session.id)
        
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        data = response.json()
        assert "message" in data
        assert "Invalid or expired session" in data["message"]
        
        # Verify expired session was deleted
        session = test_db.query(SessionModel).filter(SessionModel.id == expired_session.id).first()
        assert session is None


class TestAuthenticationFlow:
    """Integration tests for complete authentication flow."""
    
    def test_complete_auth_flow(self, client, test_user, test_db):
        """Test complete authentication flow: login -> get me -> logout."""
        # Step 1: Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        assert login_response.status_code == 200
        assert SESSION_COOKIE_NAME in login_response.cookies
        
        # Step 2: Get current user
        me_response = client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "testuser"
        
        # Step 3: Logout
        logout_response = client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 200
        
        # Step 4: Verify can't access protected endpoint after logout
        me_response_after_logout = client.get("/api/v1/auth/me")
        assert me_response_after_logout.status_code == 401
    
    def test_session_persistence(self, client, test_user):
        """Test that session persists across multiple requests."""
        # Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "testuser",
                "password": "testpassword"
            }
        )
        assert login_response.status_code == 200
        
        # Make multiple requests with the same session
        for _ in range(3):
            me_response = client.get("/api/v1/auth/me")
            assert me_response.status_code == 200
            assert me_response.json()["username"] == "testuser"

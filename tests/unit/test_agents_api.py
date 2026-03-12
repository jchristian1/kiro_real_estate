"""
Unit tests for agent management API endpoints.

Tests cover:
- Agent creation with credential encryption
- Agent listing (credentials excluded)
- Agent detail retrieval
- Agent updates
- Agent deletion
- Validation errors
- Authentication requirements
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gmail_lead_sync.models import Base, Credentials
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
from api.models.web_ui_models import User, Session as SessionModel
from api.models import web_ui_models  # Import to register models with Base
from api.main import app, get_db
from api.auth import hash_password, create_session


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool  # Use StaticPool to share connection across tests
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Test encryption key (valid Fernet key - 32 bytes URL-safe base64-encoded)
TEST_ENCRYPTION_KEY = "msZUufDiUiwjj5KmOrO8bSWktWtpzng4N7D3iqHS4Yg="


@pytest.fixture(scope="function")
def db_engine():
    """Create a shared database engine for testing."""
    # Import all models to ensure they're registered with Base
    from api.models import web_ui_models  # noqa: F401
    
    # Create all tables
    Base.metadata.create_all(test_engine)
    
    yield test_engine
    
    # Don't drop tables here - let each test clean up its own data


@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    session = TestSessionLocal()
    
    # Clean up credentials table before each test
    session.query(Credentials).delete()
    session.commit()
    
    yield session
    session.rollback()  # Rollback any uncommitted changes
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    # Check if user already exists
    existing_user = db_session.query(User).filter(User.username == "testuser").first()
    if existing_user:
        return existing_user
    
    user = User(
        username="testuser",
        password_hash=hash_password("testpass"),
        role="admin"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_session(db_session, test_user):
    """Create an authenticated session."""
    session = create_session(db_session, test_user.id)
    return session


@pytest.fixture
def client(db_session, test_user, auth_session):
    """Create a test client with authentication."""
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    def override_get_current_user() -> User:
        """Mock authentication - returns test user."""
        return test_user
    
    def override_get_credentials_store() -> EncryptedDBCredentialsStore:
        """Mock credentials store with test encryption key."""
        return EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
    
    # Import the dependencies from the agents module
    from api.routers import admin_agents as agents
    from api.main import get_db as main_get_db
    
    # Override dependencies
    app.dependency_overrides[main_get_db] = override_get_db
    app.dependency_overrides[agents.get_db] = override_get_db
    app.dependency_overrides[agents.get_current_user] = override_get_current_user
    app.dependency_overrides[agents.get_credentials_store] = override_get_credentials_store
    
    client = TestClient(app)
    client.cookies.set("session_token", auth_session.id)
    
    yield client
    
    app.dependency_overrides.clear()


class TestCreateAgent:
    """Tests for POST /api/v1/agents endpoint."""
    
    def test_create_agent_success(self, client, db_session):
        """Test successful agent creation with credential encryption."""
        response = client.post(
            "/api/v1/agents",
            json={
                "agent_id": "agent1",
                "email": "agent1@example.com",
                "app_password": "test-app-password"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert data["agent_id"] == "agent1"
        assert data["email"] == "agent1@example.com"
        assert "app_password" not in data  # Password should not be in response
        assert "id" in data
        assert "created_at" in data
        
        # Verify credentials are encrypted in database
        creds = db_session.query(Credentials).filter(Credentials.agent_id == "agent1").first()
        assert creds is not None
        assert creds.email_encrypted != "agent1@example.com"  # Should be encrypted
        assert creds.app_password_encrypted != "test-app-password"  # Should be encrypted
        
        # Verify credentials can be decrypted
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        email, password = store.get_credentials("agent1")
        assert email == "agent1@example.com"
        assert password == "test-app-password"
    
    def test_create_agent_duplicate_id(self, client, db_session):
        """Test creating agent with duplicate agent_id fails."""
        # Create first agent
        client.post(
            "/api/v1/agents",
            json={
                "agent_id": "agent1",
                "email": "agent1@example.com",
                "app_password": "password1"
            }
        )
        
        # Try to create duplicate
        response = client.post(
            "/api/v1/agents",
            json={
                "agent_id": "agent1",
                "email": "agent2@example.com",
                "app_password": "password2"
            }
        )
        
        assert response.status_code == 409  # Conflict
        data = response.json()
        assert "already exists" in data["message"].lower()
    
    def test_create_agent_invalid_email(self, client):
        """Test creating agent with invalid email format fails."""
        response = client.post(
            "/api/v1/agents",
            json={
                "agent_id": "agent1",
                "email": "not-an-email",
                "app_password": "password"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_create_agent_missing_fields(self, client):
        """Test creating agent with missing required fields fails."""
        response = client.post(
            "/api/v1/agents",
            json={
                "agent_id": "agent1"
                # Missing email and app_password
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestListAgents:
    """Tests for GET /api/v1/agents endpoint."""
    
    def test_list_agents_empty(self, client):
        """Test listing agents when none exist."""
        response = client.get("/api/v1/agents")
        
        if response.status_code != 200:
            print(f"Response: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["agents"] == []
    
    def test_list_agents_multiple(self, client, db_session):
        """Test listing multiple agents."""
        # Create multiple agents
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "agent1@example.com", "pass1")
        store.store_credentials("agent2", "agent2@example.com", "pass2")
        store.store_credentials("agent3", "agent3@example.com", "pass3")
        
        response = client.get("/api/v1/agents")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["agents"]) == 3
        
        # Verify agents are returned with emails but not passwords
        agent_ids = [agent["agent_id"] for agent in data["agents"]]
        assert "agent1" in agent_ids
        assert "agent2" in agent_ids
        assert "agent3" in agent_ids
        
        # Verify no passwords in response
        for agent in data["agents"]:
            assert "app_password" not in agent
            assert "email" in agent
    
    def test_list_agents_excludes_credentials(self, client, db_session):
        """Test that listing agents excludes decrypted credentials."""
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "agent1@example.com", "secret-password")
        
        response = client.get("/api/v1/agents")
        
        assert response.status_code == 200
        data = response.json()
        
        # Email is safe to return, but password should not be present
        assert data["agents"][0]["email"] == "agent1@example.com"
        assert "app_password" not in data["agents"][0]
        assert "password" not in str(data).lower()


class TestGetAgent:
    """Tests for GET /api/v1/agents/{agent_id} endpoint."""
    
    def test_get_agent_success(self, client, db_session):
        """Test getting agent details."""
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "agent1@example.com", "password")
        
        response = client.get("/api/v1/agents/agent1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "agent1"
        assert data["email"] == "agent1@example.com"
        assert "app_password" not in data
    
    def test_get_agent_not_found(self, client):
        """Test getting non-existent agent returns 404."""
        response = client.get("/api/v1/agents/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()


class TestUpdateAgent:
    """Tests for PUT /api/v1/agents/{agent_id} endpoint."""
    
    def test_update_agent_email(self, client, db_session):
        """Test updating agent email."""
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "old@example.com", "password")
        
        response = client.put(
            "/api/v1/agents/agent1",
            json={"email": "new@example.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"
        
        # Verify in database
        email, password = store.get_credentials("agent1")
        assert email == "new@example.com"
        assert password == "password"  # Password unchanged
    
    def test_update_agent_password(self, client, db_session):
        """Test updating agent password."""
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "agent1@example.com", "oldpass")
        
        response = client.put(
            "/api/v1/agents/agent1",
            json={"app_password": "newpass"}
        )
        
        assert response.status_code == 200
        
        # Verify in database
        email, password = store.get_credentials("agent1")
        assert email == "agent1@example.com"  # Email unchanged
        assert password == "newpass"
    
    def test_update_agent_both_fields(self, client, db_session):
        """Test updating both email and password."""
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "old@example.com", "oldpass")
        
        response = client.put(
            "/api/v1/agents/agent1",
            json={
                "email": "new@example.com",
                "app_password": "newpass"
            }
        )
        
        assert response.status_code == 200
        
        # Verify in database
        email, password = store.get_credentials("agent1")
        assert email == "new@example.com"
        assert password == "newpass"
    
    def test_update_agent_no_fields(self, client, db_session):
        """Test updating agent with no fields fails."""
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "agent1@example.com", "password")
        
        response = client.put("/api/v1/agents/agent1", json={})
        
        assert response.status_code == 400  # Validation error
        data = response.json()
        assert "no fields" in data["message"].lower()
    
    def test_update_agent_not_found(self, client):
        """Test updating non-existent agent returns 404."""
        response = client.put(
            "/api/v1/agents/nonexistent",
            json={"email": "new@example.com"}
        )
        
        assert response.status_code == 404


class TestDeleteAgent:
    """Tests for DELETE /api/v1/agents/{agent_id} endpoint."""
    
    def test_delete_agent_success(self, client, db_session):
        """Test successful agent deletion."""
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "agent1@example.com", "password")
        
        response = client.delete("/api/v1/agents/agent1")
        
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"].lower()
        
        # Verify agent is deleted from database
        creds = db_session.query(Credentials).filter(Credentials.agent_id == "agent1").first()
        assert creds is None
    
    def test_delete_agent_not_found(self, client):
        """Test deleting non-existent agent returns 404."""
        response = client.delete("/api/v1/agents/nonexistent")
        
        assert response.status_code == 404
    
    def test_delete_agent_records_audit_log(self, client, db_session):
        """Test that agent deletion records an audit log entry."""
        from api.models.web_ui_models import AuditLog
        
        store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
        store.store_credentials("agent1", "agent1@example.com", "password")
        
        # Get the credentials ID before deletion
        creds = db_session.query(Credentials).filter(Credentials.agent_id == "agent1").first()
        creds_id = creds.id
        
        # Delete the agent
        response = client.delete("/api/v1/agents/agent1")
        assert response.status_code == 200
        
        # Verify audit log entry was created
        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.action == "agent_deleted",
            AuditLog.resource_type == "agent",
            AuditLog.resource_id == creds_id
        ).first()
        
        assert audit_entry is not None
        assert audit_entry.action == "agent_deleted"
        assert audit_entry.resource_type == "agent"
        assert audit_entry.resource_id == creds_id
        assert "agent1" in audit_entry.details.lower()


class TestAgentAuthentication:
    """Tests for authentication requirements on agent endpoints."""
    
    def test_create_agent_requires_auth(self):
        """Test that creating agent requires authentication."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/agents",
            json={
                "agent_id": "agent1",
                "email": "agent1@example.com",
                "app_password": "password"
            }
        )
        
        # Should fail without authentication
        assert response.status_code in [401, 403]
    
    def test_list_agents_requires_auth(self):
        """Test that listing agents requires authentication."""
        client = TestClient(app)
        response = client.get("/api/v1/agents")
        
        # Should fail without authentication
        assert response.status_code in [401, 403]

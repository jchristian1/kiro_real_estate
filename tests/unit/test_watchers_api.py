"""
Unit tests for watcher control API endpoints.

Tests cover:
- Starting watchers for agents
- Stopping watchers
- Triggering manual sync operations
- Getting watcher status for all agents
- Validation errors
- Authentication requirements
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, MagicMock, patch

from gmail_lead_sync.models import Base, Credentials
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
from api.models.web_ui_models import User, Session as SessionModel
from api.models import web_ui_models  # Import to register models with Base
from api.main import app, get_db
from api.auth import hash_password, create_session
from api.services.watcher_registry import WatcherRegistry, WatcherStatus


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
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


@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    session = TestSessionLocal()
    
    # Clean up credentials table before each test
    session.query(Credentials).delete()
    session.commit()
    
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
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
def test_agent(db_session):
    """Create a test agent with credentials."""
    store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
    store.store_credentials(
        agent_id="test_agent",
        email="test@example.com",
        app_password="test-password"
    )
    return db_session.query(Credentials).filter(Credentials.agent_id == "test_agent").first()


@pytest.fixture
def mock_watcher_registry():
    """Create a mock WatcherRegistry for testing."""
    registry = MagicMock(spec=WatcherRegistry)
    
    # Mock async methods
    registry.start_watcher = AsyncMock(return_value=True)
    registry.stop_watcher = AsyncMock(return_value=True)
    registry.trigger_sync = AsyncMock(return_value=True)
    registry.get_status = AsyncMock(return_value={
        "agent_id": "test_agent",
        "status": "running",
        "last_heartbeat": "2024-01-15T10:00:00Z",
        "last_sync": "2024-01-15T09:59:00Z",
        "error": None,
        "started_at": "2024-01-15T09:00:00Z"
    })
    registry.get_all_statuses = AsyncMock(return_value={
        "test_agent": {
            "agent_id": "test_agent",
            "status": "running",
            "last_heartbeat": "2024-01-15T10:00:00Z",
            "last_sync": "2024-01-15T09:59:00Z",
            "error": None,
            "started_at": "2024-01-15T09:00:00Z"
        }
    })
    
    return registry


@pytest.fixture
def client(db_session, test_user, auth_session, mock_watcher_registry):
    """Create a test client with authentication and mocked watcher registry."""
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    def override_get_current_user() -> User:
        """Mock authentication - returns test user."""
        return test_user
    
    def override_get_watcher_registry():
        """Mock watcher registry."""
        return mock_watcher_registry
    
    # Import the dependencies
    from api.routes import watchers
    from api.main import get_db as main_get_db
    
    # Override dependencies
    app.dependency_overrides[main_get_db] = override_get_db
    app.dependency_overrides[watchers.get_db] = override_get_db
    app.dependency_overrides[watchers.get_current_user] = override_get_current_user
    app.dependency_overrides[watchers.get_watcher_registry] = override_get_watcher_registry
    
    client = TestClient(app)
    client.cookies.set("session_token", auth_session.id)
    
    yield client
    
    app.dependency_overrides.clear()


class TestStartWatcher:
    """Tests for POST /api/v1/watchers/{agent_id}/start endpoint."""
    
    def test_start_watcher_success(self, client, test_agent, mock_watcher_registry):
        """Test successfully starting a watcher."""
        response = client.post("/api/v1/watchers/test_agent/start")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["agent_id"] == "test_agent"
        assert data["status"] == "running"
        assert "started_at" in data
        assert "message" in data
        assert "started successfully" in data["message"].lower()
        
        # Verify registry was called
        mock_watcher_registry.start_watcher.assert_called_once_with("test_agent")
    
    def test_start_watcher_agent_not_found(self, client, mock_watcher_registry):
        """Test starting watcher for non-existent agent fails."""
        response = client.post("/api/v1/watchers/nonexistent/start")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
        
        # Verify registry was not called
        mock_watcher_registry.start_watcher.assert_not_called()
    
    def test_start_watcher_already_running(self, client, test_agent, mock_watcher_registry):
        """Test starting watcher that's already running fails."""
        # Mock registry to return False (already running)
        mock_watcher_registry.start_watcher.return_value = False
        
        response = client.post("/api/v1/watchers/test_agent/start")
        
        assert response.status_code == 409  # Conflict
        data = response.json()
        assert "already running" in data["message"].lower()


class TestStopWatcher:
    """Tests for POST /api/v1/watchers/{agent_id}/stop endpoint."""
    
    def test_stop_watcher_success(self, client, test_agent, mock_watcher_registry):
        """Test successfully stopping a watcher."""
        response = client.post("/api/v1/watchers/test_agent/stop")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["agent_id"] == "test_agent"
        assert data["status"] == "stopped"
        assert "message" in data
        assert "stopped successfully" in data["message"].lower()
        
        # Verify registry was called
        mock_watcher_registry.stop_watcher.assert_called_once_with("test_agent")
    
    def test_stop_watcher_agent_not_found(self, client, mock_watcher_registry):
        """Test stopping watcher for non-existent agent fails."""
        response = client.post("/api/v1/watchers/nonexistent/stop")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
        
        # Verify registry was not called
        mock_watcher_registry.stop_watcher.assert_not_called()
    
    def test_stop_watcher_not_running(self, client, test_agent, mock_watcher_registry):
        """Test stopping watcher that's not running fails."""
        # Mock registry to return False (not running)
        mock_watcher_registry.stop_watcher.return_value = False
        
        response = client.post("/api/v1/watchers/test_agent/stop")
        
        assert response.status_code == 404
        data = response.json()
        assert "no running watcher" in data["message"].lower()


class TestTriggerSync:
    """Tests for POST /api/v1/watchers/{agent_id}/sync endpoint."""
    
    def test_trigger_sync_success(self, client, test_agent, mock_watcher_registry):
        """Test successfully triggering a manual sync."""
        response = client.post("/api/v1/watchers/test_agent/sync")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["agent_id"] == "test_agent"
        assert data["sync_triggered"] is True
        assert "timestamp" in data
        assert "message" in data
        assert "triggered successfully" in data["message"].lower()
        
        # Verify registry was called
        mock_watcher_registry.trigger_sync.assert_called_once_with("test_agent")
    
    def test_trigger_sync_agent_not_found(self, client, mock_watcher_registry):
        """Test triggering sync for non-existent agent fails."""
        response = client.post("/api/v1/watchers/nonexistent/sync")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
        
        # Verify registry was not called
        mock_watcher_registry.trigger_sync.assert_not_called()
    
    def test_trigger_sync_watcher_not_running(self, client, test_agent, mock_watcher_registry):
        """Test triggering sync when watcher not running fails."""
        # Mock registry to return False (not running)
        mock_watcher_registry.trigger_sync.return_value = False
        
        response = client.post("/api/v1/watchers/test_agent/sync")
        
        assert response.status_code == 400  # Validation error
        data = response.json()
        assert "not running" in data["message"].lower()


class TestGetWatcherStatus:
    """Tests for GET /api/v1/watchers/status endpoint."""
    
    def test_get_all_statuses_success(self, client, test_agent, mock_watcher_registry):
        """Test successfully getting all watcher statuses."""
        response = client.get("/api/v1/watchers/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "watchers" in data
        assert len(data["watchers"]) == 1
        
        watcher = data["watchers"][0]
        assert watcher["agent_id"] == "test_agent"
        assert watcher["status"] == "running"
        assert watcher["last_heartbeat"] == "2024-01-15T10:00:00Z"
        assert watcher["last_sync"] == "2024-01-15T09:59:00Z"
        assert watcher["error"] is None
        assert watcher["started_at"] == "2024-01-15T09:00:00Z"
        
        # Verify registry was called
        mock_watcher_registry.get_all_statuses.assert_called_once()
    
    def test_get_all_statuses_empty(self, client, mock_watcher_registry):
        """Test getting statuses when no watchers are running."""
        # Mock empty registry
        mock_watcher_registry.get_all_statuses.return_value = {}
        
        response = client.get("/api/v1/watchers/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "watchers" in data
        assert len(data["watchers"]) == 0
    
    def test_get_all_statuses_multiple_watchers(self, client, mock_watcher_registry):
        """Test getting statuses for multiple watchers."""
        # Mock multiple watchers
        mock_watcher_registry.get_all_statuses.return_value = {
            "agent1": {
                "agent_id": "agent1",
                "status": "running",
                "last_heartbeat": "2024-01-15T10:00:00Z",
                "last_sync": "2024-01-15T09:59:00Z",
                "error": None,
                "started_at": "2024-01-15T09:00:00Z"
            },
            "agent2": {
                "agent_id": "agent2",
                "status": "stopped",
                "last_heartbeat": None,
                "last_sync": "2024-01-15T08:00:00Z",
                "error": None,
                "started_at": None
            },
            "agent3": {
                "agent_id": "agent3",
                "status": "failed",
                "last_heartbeat": "2024-01-15T09:30:00Z",
                "last_sync": "2024-01-15T09:29:00Z",
                "error": "Connection timeout",
                "started_at": "2024-01-15T09:00:00Z"
            }
        }
        
        response = client.get("/api/v1/watchers/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["watchers"]) == 3
        
        # Verify each watcher
        agent_ids = [w["agent_id"] for w in data["watchers"]]
        assert "agent1" in agent_ids
        assert "agent2" in agent_ids
        assert "agent3" in agent_ids
        
        # Find failed watcher and verify error
        failed_watcher = next(w for w in data["watchers"] if w["agent_id"] == "agent3")
        assert failed_watcher["status"] == "failed"
        assert failed_watcher["error"] == "Connection timeout"


class TestAuthentication:
    """Tests for authentication requirements on watcher endpoints."""
    
    def test_start_watcher_requires_auth(self, db_session, test_agent):
        """Test that starting watcher requires authentication."""
        # Create client without authentication
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        from api.main import get_db as main_get_db
        app.dependency_overrides[main_get_db] = override_get_db
        
        client = TestClient(app)
        response = client.post("/api/v1/watchers/test_agent/start")
        
        assert response.status_code == 401
        
        app.dependency_overrides.clear()
    
    def test_stop_watcher_requires_auth(self, db_session, test_agent):
        """Test that stopping watcher requires authentication."""
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        from api.main import get_db as main_get_db
        app.dependency_overrides[main_get_db] = override_get_db
        
        client = TestClient(app)
        response = client.post("/api/v1/watchers/test_agent/stop")
        
        assert response.status_code == 401
        
        app.dependency_overrides.clear()
    
    def test_get_status_requires_auth(self, db_session):
        """Test that getting watcher status requires authentication."""
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        from api.main import get_db as main_get_db
        app.dependency_overrides[main_get_db] = override_get_db
        
        client = TestClient(app)
        response = client.get("/api/v1/watchers/status")
        
        assert response.status_code == 401
        
        app.dependency_overrides.clear()
    
    def test_trigger_sync_requires_auth(self, db_session, test_agent):
        """Test that triggering sync requires authentication."""
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        from api.main import get_db as main_get_db
        app.dependency_overrides[main_get_db] = override_get_db
        
        client = TestClient(app)
        response = client.post("/api/v1/watchers/test_agent/sync")
        
        assert response.status_code == 401
        
        app.dependency_overrides.clear()


class TestAuditLogging:
    """Tests for audit logging of watcher operations."""
    
    def test_start_watcher_creates_audit_log(self, client, test_agent, db_session, mock_watcher_registry):
        """Test that starting a watcher creates an audit log entry."""
        from api.models.web_ui_models import AuditLog
        
        # Count audit logs before
        before_count = db_session.query(AuditLog).count()
        
        # Start watcher
        response = client.post("/api/v1/watchers/test_agent/start")
        assert response.status_code == 200
        
        # Verify audit log was created
        after_count = db_session.query(AuditLog).count()
        assert after_count == before_count + 1
        
        # Verify audit log details
        audit_log = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert audit_log.action == "watcher_started"
        assert audit_log.resource_type == "watcher"
        assert "test_agent" in audit_log.details
    
    def test_stop_watcher_creates_audit_log(self, client, test_agent, db_session, mock_watcher_registry):
        """Test that stopping a watcher creates an audit log entry."""
        from api.models.web_ui_models import AuditLog
        
        # Count audit logs before
        before_count = db_session.query(AuditLog).count()
        
        # Stop watcher
        response = client.post("/api/v1/watchers/test_agent/stop")
        assert response.status_code == 200
        
        # Verify audit log was created
        after_count = db_session.query(AuditLog).count()
        assert after_count == before_count + 1
        
        # Verify audit log details
        audit_log = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert audit_log.action == "watcher_stopped"
        assert audit_log.resource_type == "watcher"
        assert "test_agent" in audit_log.details
    
    def test_trigger_sync_creates_audit_log(self, client, test_agent, db_session, mock_watcher_registry):
        """Test that triggering sync creates an audit log entry."""
        from api.models.web_ui_models import AuditLog
        
        # Count audit logs before
        before_count = db_session.query(AuditLog).count()
        
        # Trigger sync
        response = client.post("/api/v1/watchers/test_agent/sync")
        assert response.status_code == 200
        
        # Verify audit log was created
        after_count = db_session.query(AuditLog).count()
        assert after_count == before_count + 1
        
        # Verify audit log details
        audit_log = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert audit_log.action == "watcher_sync_triggered"
        assert audit_log.resource_type == "watcher"
        assert "test_agent" in audit_log.details


class TestWatcherStatusDetails:
    """Tests for watcher status response details."""
    
    def test_status_includes_all_fields(self, client, mock_watcher_registry):
        """Test that status response includes all expected fields."""
        response = client.get("/api/v1/watchers/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "watchers" in data
        assert len(data["watchers"]) == 1
        
        watcher = data["watchers"][0]
        
        # Verify all required fields are present
        required_fields = [
            "agent_id", "status", "last_heartbeat", 
            "last_sync", "error", "started_at"
        ]
        for field in required_fields:
            assert field in watcher, f"Missing field: {field}"
    
    def test_status_with_failed_watcher(self, client, mock_watcher_registry):
        """Test status response for a failed watcher."""
        # Mock a failed watcher
        mock_watcher_registry.get_all_statuses.return_value = {
            "test_agent": {
                "agent_id": "test_agent",
                "status": "failed",
                "last_heartbeat": "2024-01-15T10:00:00Z",
                "last_sync": "2024-01-15T09:59:00Z",
                "error": "Connection timeout",
                "started_at": "2024-01-15T09:00:00Z"
            }
        }
        
        response = client.get("/api/v1/watchers/status")
        
        assert response.status_code == 200
        data = response.json()
        
        watcher = data["watchers"][0]
        assert watcher["status"] == "failed"
        assert watcher["error"] == "Connection timeout"
    
    def test_status_with_stopped_watcher(self, client, mock_watcher_registry):
        """Test status response for a stopped watcher."""
        # Mock a stopped watcher
        mock_watcher_registry.get_all_statuses.return_value = {
            "test_agent": {
                "agent_id": "test_agent",
                "status": "stopped",
                "last_heartbeat": None,
                "last_sync": "2024-01-15T09:59:00Z",
                "error": None,
                "started_at": None
            }
        }
        
        response = client.get("/api/v1/watchers/status")
        
        assert response.status_code == 200
        data = response.json()
        
        watcher = data["watchers"][0]
        assert watcher["status"] == "stopped"
        assert watcher["last_heartbeat"] is None
        assert watcher["started_at"] is None

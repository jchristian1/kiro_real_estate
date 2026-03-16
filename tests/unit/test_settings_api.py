"""
Unit tests for settings management API endpoints.

Tests cover:
- Settings retrieval with defaults
- Settings updates (partial and full)
- Validation of setting values
- Audit log recording for settings modifications
- Authentication requirements
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gmail_lead_sync.models import Base
from api.models.web_ui_models import User, Setting, AuditLog
from api.main import app
from api.auth import hash_password, create_session


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool  # Use StaticPool to share connection across tests
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_engine():
    """Create a shared database engine for testing."""
    # Import all models to ensure they're registered with Base
    
    # Create all tables
    Base.metadata.create_all(test_engine)
    
    yield test_engine


@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    session = TestSessionLocal()
    
    # Clean up settings and audit logs before each test
    session.query(Setting).delete()
    session.query(AuditLog).delete()
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
    
    # Import the dependencies from the settings module
    from api.routers import admin_settings as settings
    from api.main import get_db as main_get_db
    
    # Override dependencies
    app.dependency_overrides[main_get_db] = override_get_db
    app.dependency_overrides[settings.get_db] = override_get_db
    app.dependency_overrides[settings.get_current_user] = override_get_current_user
    
    client = TestClient(app)
    client.cookies.set("session_token", auth_session.id)
    
    yield client
    
    app.dependency_overrides.clear()


class TestGetSettings:
    """Tests for GET /api/v1/settings endpoint."""
    
    def test_get_settings_with_defaults(self, client, db_session):
        """Test retrieving settings returns defaults when no settings in database."""
        response = client.get("/api/v1/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify default values
        assert data["sync_interval_seconds"] == 300
        assert data["regex_timeout_ms"] == 1000
        assert data["session_timeout_hours"] == 24
        assert data["max_leads_per_page"] == 50
        assert data["enable_auto_restart"] is True
    
    def test_get_settings_with_custom_values(self, client, db_session, test_user):
        """Test retrieving settings returns custom values from database."""
        # Insert custom settings
        settings = [
            Setting(key="sync_interval_seconds", value="600", updated_by=test_user.id),
            Setting(key="regex_timeout_ms", value="2000", updated_by=test_user.id),
            Setting(key="session_timeout_hours", value="48", updated_by=test_user.id),
            Setting(key="max_leads_per_page", value="100", updated_by=test_user.id),
            Setting(key="enable_auto_restart", value="false", updated_by=test_user.id)
        ]
        for setting in settings:
            db_session.add(setting)
        db_session.commit()
        
        response = client.get("/api/v1/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify custom values
        assert data["sync_interval_seconds"] == 600
        assert data["regex_timeout_ms"] == 2000
        assert data["session_timeout_hours"] == 48
        assert data["max_leads_per_page"] == 100
        assert data["enable_auto_restart"] is False
    
    def test_get_settings_mixed_defaults_and_custom(self, client, db_session, test_user):
        """Test retrieving settings with some custom and some default values."""
        # Insert only some custom settings
        db_session.add(Setting(key="sync_interval_seconds", value="900", updated_by=test_user.id))
        db_session.add(Setting(key="max_leads_per_page", value="200", updated_by=test_user.id))
        db_session.commit()
        
        response = client.get("/api/v1/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify mixed values
        assert data["sync_interval_seconds"] == 900  # Custom
        assert data["regex_timeout_ms"] == 1000  # Default
        assert data["session_timeout_hours"] == 24  # Default
        assert data["max_leads_per_page"] == 200  # Custom
        assert data["enable_auto_restart"] is True  # Default


class TestUpdateSettings:
    """Tests for PUT /api/v1/settings endpoint."""
    
    def test_update_single_setting(self, client, db_session, test_user):
        """Test updating a single setting."""
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 600}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify updated value
        assert data["sync_interval_seconds"] == 600
        # Verify other settings remain at defaults
        assert data["regex_timeout_ms"] == 1000
        assert data["session_timeout_hours"] == 24
        assert data["max_leads_per_page"] == 50
        assert data["enable_auto_restart"] is True
        
        # Verify setting is in database
        setting = db_session.query(Setting).filter(Setting.key == "sync_interval_seconds").first()
        assert setting is not None
        assert setting.value == "600"
        assert setting.updated_by == test_user.id
        
        # Verify audit log was created
        audit_log = db_session.query(AuditLog).filter(
            AuditLog.action == "settings_updated"
        ).first()
        assert audit_log is not None
        assert audit_log.user_id == test_user.id
        assert "sync_interval_seconds" in audit_log.details
    
    def test_update_multiple_settings(self, client, db_session, test_user):
        """Test updating multiple settings at once."""
        response = client.put(
            "/api/v1/settings",
            json={
                "sync_interval_seconds": 900,
                "regex_timeout_ms": 2500,
                "max_leads_per_page": 75
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all updated values
        assert data["sync_interval_seconds"] == 900
        assert data["regex_timeout_ms"] == 2500
        assert data["max_leads_per_page"] == 75
        # Verify unchanged settings
        assert data["session_timeout_hours"] == 24
        assert data["enable_auto_restart"] is True
        
        # Verify all settings are in database
        assert db_session.query(Setting).filter(Setting.key == "sync_interval_seconds").first().value == "900"
        assert db_session.query(Setting).filter(Setting.key == "regex_timeout_ms").first().value == "2500"
        assert db_session.query(Setting).filter(Setting.key == "max_leads_per_page").first().value == "75"
        
        # Verify audit log includes all updated settings
        audit_log = db_session.query(AuditLog).filter(
            AuditLog.action == "settings_updated"
        ).first()
        assert audit_log is not None
        assert "sync_interval_seconds" in audit_log.details
        assert "regex_timeout_ms" in audit_log.details
        assert "max_leads_per_page" in audit_log.details
    
    def test_update_boolean_setting(self, client, db_session):
        """Test updating boolean setting."""
        response = client.put(
            "/api/v1/settings",
            json={"enable_auto_restart": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify boolean value
        assert data["enable_auto_restart"] is False
        
        # Verify setting is stored as lowercase string in database
        setting = db_session.query(Setting).filter(Setting.key == "enable_auto_restart").first()
        assert setting.value == "false"
    
    def test_update_existing_setting(self, client, db_session, test_user):
        """Test updating a setting that already exists in database."""
        # Create initial setting
        db_session.add(Setting(key="sync_interval_seconds", value="600", updated_by=test_user.id))
        db_session.commit()
        
        # Update the setting
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 1200}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sync_interval_seconds"] == 1200
        
        # Verify only one setting record exists (update, not insert)
        settings = db_session.query(Setting).filter(Setting.key == "sync_interval_seconds").all()
        assert len(settings) == 1
        assert settings[0].value == "1200"


class TestSettingsValidation:
    """Tests for settings validation."""
    
    def test_sync_interval_below_minimum(self, client):
        """Test sync_interval_seconds below minimum (60) fails."""
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 30}
        )
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    def test_sync_interval_above_maximum(self, client):
        """Test sync_interval_seconds above maximum (3600) fails."""
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 5000}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_regex_timeout_below_minimum(self, client):
        """Test regex_timeout_ms below minimum (100) fails."""
        response = client.put(
            "/api/v1/settings",
            json={"regex_timeout_ms": 50}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_regex_timeout_above_maximum(self, client):
        """Test regex_timeout_ms above maximum (5000) fails."""
        response = client.put(
            "/api/v1/settings",
            json={"regex_timeout_ms": 10000}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_session_timeout_below_minimum(self, client):
        """Test session_timeout_hours below minimum (1) fails."""
        response = client.put(
            "/api/v1/settings",
            json={"session_timeout_hours": 0}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_session_timeout_above_maximum(self, client):
        """Test session_timeout_hours above maximum (168) fails."""
        response = client.put(
            "/api/v1/settings",
            json={"session_timeout_hours": 200}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_max_leads_below_minimum(self, client):
        """Test max_leads_per_page below minimum (10) fails."""
        response = client.put(
            "/api/v1/settings",
            json={"max_leads_per_page": 5}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_max_leads_above_maximum(self, client):
        """Test max_leads_per_page above maximum (1000) fails."""
        response = client.put(
            "/api/v1/settings",
            json={"max_leads_per_page": 2000}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_valid_boundary_values(self, client):
        """Test valid boundary values for all settings."""
        # Test minimum values
        response = client.put(
            "/api/v1/settings",
            json={
                "sync_interval_seconds": 60,
                "regex_timeout_ms": 100,
                "session_timeout_hours": 1,
                "max_leads_per_page": 10
            }
        )
        assert response.status_code == 200
        
        # Test maximum values
        response = client.put(
            "/api/v1/settings",
            json={
                "sync_interval_seconds": 3600,
                "regex_timeout_ms": 5000,
                "session_timeout_hours": 168,
                "max_leads_per_page": 1000
            }
        )
        assert response.status_code == 200


class TestSettingsAuditLog:
    """Tests for audit log recording on settings modifications."""
    
    def test_audit_log_created_on_update(self, client, db_session, test_user):
        """Test that audit log is created when settings are updated."""
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 600}
        )
        
        assert response.status_code == 200
        
        # Verify audit log was created
        audit_logs = db_session.query(AuditLog).filter(
            AuditLog.action == "settings_updated"
        ).all()
        assert len(audit_logs) == 1
        
        audit_log = audit_logs[0]
        assert audit_log.user_id == test_user.id
        assert audit_log.resource_type == "settings"
        assert audit_log.resource_id is None  # Settings don't have a specific ID
        assert "sync_interval_seconds" in audit_log.details
    
    def test_audit_log_includes_all_updated_settings(self, client, db_session):
        """Test that audit log details include all updated settings."""
        response = client.put(
            "/api/v1/settings",
            json={
                "sync_interval_seconds": 600,
                "regex_timeout_ms": 2000,
                "enable_auto_restart": False
            }
        )
        
        assert response.status_code == 200
        
        # Verify audit log includes all settings
        audit_log = db_session.query(AuditLog).filter(
            AuditLog.action == "settings_updated"
        ).first()
        assert audit_log is not None
        assert "sync_interval_seconds" in audit_log.details
        assert "regex_timeout_ms" in audit_log.details
        assert "enable_auto_restart" in audit_log.details
    
    def test_no_audit_log_when_no_settings_updated(self, client, db_session):
        """Test that no audit log is created when no settings are provided."""
        # This should not create an audit log since no settings are updated
        response = client.put(
            "/api/v1/settings",
            json={}
        )
        
        assert response.status_code == 200
        
        # Verify no audit log was created
        audit_logs = db_session.query(AuditLog).filter(
            AuditLog.action == "settings_updated"
        ).all()
        assert len(audit_logs) == 0


class TestSettingsAuthentication:
    """Tests for authentication requirements on settings endpoints."""
    
    def test_get_settings_requires_authentication(self, db_session):
        """Test that GET /api/v1/settings requires authentication."""
        # Create client without authentication
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        from api.main import get_db as main_get_db
        app.dependency_overrides[main_get_db] = override_get_db
        
        client = TestClient(app)
        response = client.get("/api/v1/settings")
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
        
        app.dependency_overrides.clear()
    
    def test_update_settings_requires_authentication(self, db_session):
        """Test that PUT /api/v1/settings requires authentication."""
        # Create client without authentication
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        from api.main import get_db as main_get_db
        app.dependency_overrides[main_get_db] = override_get_db
        
        client = TestClient(app)
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 600}
        )
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
        
        app.dependency_overrides.clear()


class TestSettingsEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_update_with_invalid_data_type(self, client):
        """Test updating setting with invalid data type (string instead of int)."""
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": "not_a_number"}
        )
        
        # Should return 422 Validation error
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_update_with_null_value(self, client):
        """Test updating setting with null value is ignored."""
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": None}
        )
        
        # Should succeed and return defaults (null values are ignored)
        assert response.status_code == 200
        data = response.json()
        assert data["sync_interval_seconds"] == 300  # Default value
    
    def test_update_with_unknown_setting(self, client):
        """Test updating with unknown setting key is ignored."""
        response = client.put(
            "/api/v1/settings",
            json={
                "sync_interval_seconds": 600,
                "unknown_setting": "value"
            }
        )
        
        # Should succeed and ignore unknown setting
        assert response.status_code == 200
        data = response.json()
        assert data["sync_interval_seconds"] == 600
        assert "unknown_setting" not in data
    
    def test_update_all_settings_at_once(self, client, db_session, test_user):
        """Test updating all settings in a single request."""
        response = client.put(
            "/api/v1/settings",
            json={
                "sync_interval_seconds": 1800,
                "regex_timeout_ms": 3000,
                "session_timeout_hours": 72,
                "max_leads_per_page": 500,
                "enable_auto_restart": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all settings were updated
        assert data["sync_interval_seconds"] == 1800
        assert data["regex_timeout_ms"] == 3000
        assert data["session_timeout_hours"] == 72
        assert data["max_leads_per_page"] == 500
        assert data["enable_auto_restart"] is False
        
        # Verify all settings are in database
        assert db_session.query(Setting).count() == 5
    
    def test_update_boolean_with_string_true(self, client, db_session):
        """Test updating boolean setting with string 'true' is coerced to boolean."""
        response = client.put(
            "/api/v1/settings",
            json={"enable_auto_restart": "true"}
        )
        
        # Pydantic coerces string "true" to boolean True
        assert response.status_code == 200
        data = response.json()
        assert data["enable_auto_restart"] is True
        
        # Verify it's stored correctly in database
        setting = db_session.query(Setting).filter(Setting.key == "enable_auto_restart").first()
        assert setting.value == "true"
    
    def test_get_settings_after_multiple_updates(self, client, db_session, test_user):
        """Test retrieving settings after multiple sequential updates."""
        # First update
        client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 600}
        )
        
        # Second update (different setting)
        client.put(
            "/api/v1/settings",
            json={"regex_timeout_ms": 2000}
        )
        
        # Third update (update first setting again)
        client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 900}
        )
        
        # Get settings
        response = client.get("/api/v1/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify latest values
        assert data["sync_interval_seconds"] == 900  # Latest update
        assert data["regex_timeout_ms"] == 2000  # From second update
        assert data["session_timeout_hours"] == 24  # Default
    
    def test_validation_error_includes_field_name(self, client):
        """Test that validation errors include the field name."""
        response = client.put(
            "/api/v1/settings",
            json={"sync_interval_seconds": 5000}  # Above maximum
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Pydantic validation errors include field location
        assert any("sync_interval_seconds" in str(error) for error in data["detail"])

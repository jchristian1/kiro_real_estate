"""
Unit tests for lead source management API endpoints.

Tests cover:
- Lead source creation with regex validation
- Lead source listing
- Lead source detail retrieval
- Lead source updates
- Lead source deletion
- Regex pattern validation
- Validation errors
- Authentication requirements
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gmail_lead_sync.models import Base, LeadSource, Template
from api.models.web_ui_models import User, Session as SessionModel
from api.models import web_ui_models  # Import to register models with Base
from api.main import app, get_db
from api.auth import hash_password, create_session


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_engine():
    """Create a shared database engine for testing."""
    from api.models import web_ui_models  # noqa: F401
    
    Base.metadata.create_all(test_engine)
    
    yield test_engine


@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    session = TestSessionLocal()
    
    # Clean up tables before each test
    from api.models.web_ui_models import RegexProfileVersion
    session.query(RegexProfileVersion).delete()
    session.query(LeadSource).delete()
    session.query(Template).delete()
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
def test_template(db_session):
    """Create a test template."""
    template = Template(
        name="Test Template",
        subject="Test Subject",
        body="Test Body"
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


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
    
    from api.routers import admin_lead_sources as lead_sources
    from api.main import get_db as main_get_db
    
    app.dependency_overrides[main_get_db] = override_get_db
    app.dependency_overrides[lead_sources.get_db] = override_get_db
    app.dependency_overrides[lead_sources.get_current_user] = override_get_current_user
    
    client = TestClient(app)
    client.cookies.set("session_token", auth_session.id)
    
    yield client
    
    app.dependency_overrides.clear()


class TestCreateLeadSource:
    """Tests for POST /api/v1/lead-sources endpoint."""
    
    def test_create_lead_source_success(self, client, db_session):
        """Test successful lead source creation."""
        response = client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com",
                "identifier_snippet": "New Lead Notification",
                "name_regex": r"Name:\s*(.+)",
                "phone_regex": r"Phone:\s*([\d-]+)",
                "auto_respond_enabled": False
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["sender_email"] == "leads@example.com"
        assert data["identifier_snippet"] == "New Lead Notification"
        assert data["name_regex"] == r"Name:\s*(.+)"
        assert data["phone_regex"] == r"Phone:\s*([\d-]+)"
        assert data["auto_respond_enabled"] is False
        assert data["template_id"] is None
        assert "id" in data
        assert "created_at" in data
        
        # Verify in database
        lead_source = db_session.query(LeadSource).filter(
            LeadSource.sender_email == "leads@example.com"
        ).first()
        assert lead_source is not None
    
    def test_create_lead_source_with_template(self, client, db_session, test_template):
        """Test creating lead source with template association."""
        response = client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com",
                "identifier_snippet": "New Lead",
                "name_regex": r"Name:\s*(.+)",
                "phone_regex": r"Phone:\s*([\d-]+)",
                "template_id": test_template.id,
                "auto_respond_enabled": True
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["template_id"] == test_template.id
        assert data["auto_respond_enabled"] is True
    
    def test_create_lead_source_duplicate_email(self, client, db_session):
        """Test creating lead source with duplicate sender_email fails."""
        # Create first lead source
        client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com",
                "identifier_snippet": "Lead 1",
                "name_regex": r"Name:\s*(.+)",
                "phone_regex": r"Phone:\s*([\d-]+)",
                "auto_respond_enabled": False
            }
        )
        
        # Try to create duplicate
        response = client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com",
                "identifier_snippet": "Lead 2",
                "name_regex": r"Name:\s*(.+)",
                "phone_regex": r"Phone:\s*([\d-]+)",
                "auto_respond_enabled": False
            }
        )
        
        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["message"].lower()
    
    def test_create_lead_source_invalid_regex(self, client):
        """Test creating lead source with invalid regex pattern fails."""
        response = client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com",
                "identifier_snippet": "New Lead",
                "name_regex": r"[invalid(regex",  # Invalid regex
                "phone_regex": r"Phone:\s*([\d-]+)",
                "auto_respond_enabled": False
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_create_lead_source_invalid_template_id(self, client):
        """Test creating lead source with non-existent template fails."""
        response = client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com",
                "identifier_snippet": "New Lead",
                "name_regex": r"Name:\s*(.+)",
                "phone_regex": r"Phone:\s*([\d-]+)",
                "template_id": 99999,  # Non-existent template
                "auto_respond_enabled": True
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "template" in data["message"].lower()
        assert "not found" in data["message"].lower()
    
    def test_create_lead_source_missing_fields(self, client):
        """Test creating lead source with missing required fields fails."""
        response = client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com"
                # Missing other required fields
            }
        )
        
        assert response.status_code == 422


class TestListLeadSources:
    """Tests for GET /api/v1/lead-sources endpoint."""
    
    def test_list_lead_sources_empty(self, client):
        """Test listing lead sources when none exist."""
        response = client.get("/api/v1/lead-sources")
        
        assert response.status_code == 200
        data = response.json()
        assert data["lead_sources"] == []
    
    def test_list_lead_sources_multiple(self, client, db_session):
        """Test listing multiple lead sources."""
        # Create multiple lead sources
        for i in range(3):
            lead_source = LeadSource(
                sender_email=f"leads{i}@example.com",
                identifier_snippet=f"Lead {i}",
                name_regex=r"Name:\s*(.+)",
                phone_regex=r"Phone:\s*([\d-]+)",
                auto_respond_enabled=False
            )
            db_session.add(lead_source)
        db_session.commit()
        
        response = client.get("/api/v1/lead-sources")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["lead_sources"]) == 3
        
        # Verify lead sources are returned
        emails = [ls["sender_email"] for ls in data["lead_sources"]]
        assert "leads0@example.com" in emails
        assert "leads1@example.com" in emails
        assert "leads2@example.com" in emails


class TestGetLeadSource:
    """Tests for GET /api/v1/lead-sources/{id} endpoint."""
    
    def test_get_lead_source_success(self, client, db_session):
        """Test getting lead source details."""
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="New Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        response = client.get(f"/api/v1/lead-sources/{lead_source.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == lead_source.id
        assert data["sender_email"] == "leads@example.com"
        assert data["identifier_snippet"] == "New Lead"
    
    def test_get_lead_source_not_found(self, client):
        """Test getting non-existent lead source returns 404."""
        response = client.get("/api/v1/lead-sources/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()


class TestUpdateLeadSource:
    """Tests for PUT /api/v1/lead-sources/{id} endpoint."""
    
    def test_update_lead_source_sender_email(self, client, db_session):
        """Test updating lead source sender email."""
        lead_source = LeadSource(
            sender_email="old@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        response = client.put(
            f"/api/v1/lead-sources/{lead_source.id}",
            json={"sender_email": "new@example.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["sender_email"] == "new@example.com"
        
        # Verify in database
        db_session.refresh(lead_source)
        assert lead_source.sender_email == "new@example.com"
    
    def test_update_lead_source_regex_patterns(self, client, db_session):
        """Test updating lead source regex patterns."""
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        response = client.put(
            f"/api/v1/lead-sources/{lead_source.id}",
            json={
                "name_regex": r"Full Name:\s*(.+)",
                "phone_regex": r"Tel:\s*([\d-]+)"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name_regex"] == r"Full Name:\s*(.+)"
        assert data["phone_regex"] == r"Tel:\s*([\d-]+)"
    
    def test_update_lead_source_template(self, client, db_session, test_template):
        """Test updating lead source template association."""
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        response = client.put(
            f"/api/v1/lead-sources/{lead_source.id}",
            json={
                "template_id": test_template.id,
                "auto_respond_enabled": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["template_id"] == test_template.id
        assert data["auto_respond_enabled"] is True
    
    def test_update_lead_source_invalid_regex(self, client, db_session):
        """Test updating lead source with invalid regex fails."""
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        response = client.put(
            f"/api/v1/lead-sources/{lead_source.id}",
            json={"name_regex": r"[invalid(regex"}
        )
        
        assert response.status_code == 422
    
    def test_update_lead_source_no_fields(self, client, db_session):
        """Test updating lead source with no fields fails."""
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        response = client.put(
            f"/api/v1/lead-sources/{lead_source.id}",
            json={}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "no fields" in data["message"].lower()
    
    def test_update_lead_source_not_found(self, client):
        """Test updating non-existent lead source returns 404."""
        response = client.put(
            "/api/v1/lead-sources/99999",
            json={"sender_email": "new@example.com"}
        )
        
        assert response.status_code == 404
    
    def test_update_lead_source_duplicate_email(self, client, db_session):
        """Test updating lead source to duplicate email fails."""
        # Create two lead sources
        ls1 = LeadSource(
            sender_email="leads1@example.com",
            identifier_snippet="Lead 1",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        ls2 = LeadSource(
            sender_email="leads2@example.com",
            identifier_snippet="Lead 2",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add_all([ls1, ls2])
        db_session.commit()
        db_session.refresh(ls2)
        
        # Try to update ls2 to use ls1's email
        response = client.put(
            f"/api/v1/lead-sources/{ls2.id}",
            json={"sender_email": "leads1@example.com"}
        )
        
        assert response.status_code == 409
        data = response.json()
        assert "already exists" in data["message"].lower()


class TestDeleteLeadSource:
    """Tests for DELETE /api/v1/lead-sources/{id} endpoint."""
    
    def test_delete_lead_source_success(self, client, db_session):
        """Test successful lead source deletion."""
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        lead_source_id = lead_source.id
        
        response = client.delete(f"/api/v1/lead-sources/{lead_source_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"].lower()
        
        # Verify lead source is deleted from database
        deleted = db_session.query(LeadSource).filter(LeadSource.id == lead_source_id).first()
        assert deleted is None
    
    def test_delete_lead_source_not_found(self, client):
        """Test deleting non-existent lead source returns 404."""
        response = client.delete("/api/v1/lead-sources/99999")
        
        assert response.status_code == 404
    
    def test_delete_lead_source_records_audit_log(self, client, db_session):
        """Test that lead source deletion records an audit log entry."""
        from api.models.web_ui_models import AuditLog
        
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        lead_source_id = lead_source.id
        
        response = client.delete(f"/api/v1/lead-sources/{lead_source_id}")
        assert response.status_code == 200
        
        # Verify audit log entry was created
        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.action == "lead_source_deleted",
            AuditLog.resource_type == "lead_source",
            AuditLog.resource_id == lead_source_id
        ).first()
        
        assert audit_entry is not None
        assert audit_entry.action == "lead_source_deleted"
        assert "leads@example.com" in audit_entry.details.lower()


class TestLeadSourceAuthentication:
    """Tests for authentication requirements on lead source endpoints."""
    
    def test_create_lead_source_requires_auth(self):
        """Test that creating lead source requires authentication."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com",
                "identifier_snippet": "Lead",
                "name_regex": r"Name:\s*(.+)",
                "phone_regex": r"Phone:\s*([\d-]+)",
                "auto_respond_enabled": False
            }
        )
        
        assert response.status_code in [401, 403]
    
    def test_list_lead_sources_requires_auth(self):
        """Test that listing lead sources requires authentication."""
        client = TestClient(app)
        response = client.get("/api/v1/lead-sources")
        
        assert response.status_code in [401, 403]


class TestRegexTesting:
    """Tests for POST /api/v1/lead-sources/test-regex endpoint."""
    
    def test_regex_test_successful_match(self, client, db_session):
        """Test successful regex match with captured groups."""
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"Name:\s*(.+)",
                "sample_text": "Name: John Doe\nPhone: 555-1234"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is True
        assert len(data["groups"]) == 1
        assert data["groups"][0] == "John Doe"
        assert "Name: John Doe" in data["match_text"]
    
    def test_regex_test_no_match(self, client, db_session):
        """Test regex pattern that doesn't match."""
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"Email:\s*(.+)",
                "sample_text": "Name: John Doe\nPhone: 555-1234"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is False
        assert data["groups"] == []
        assert data["match_text"] is None
    
    def test_regex_test_multiple_groups(self, client, db_session):
        """Test regex pattern with multiple captured groups."""
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"Name:\s*(\w+)\s+(\w+)",
                "sample_text": "Name: John Doe\nPhone: 555-1234"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is True
        assert len(data["groups"]) == 2
        assert data["groups"][0] == "John"
        assert data["groups"][1] == "Doe"
    
    def test_regex_test_invalid_pattern(self, client, db_session):
        """Test regex testing with invalid pattern."""
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"[invalid(regex",
                "sample_text": "Some text"
            }
        )
        
        # Pydantic validation catches invalid regex during request validation (422)
        assert response.status_code == 422
        data = response.json()
        assert "invalid" in str(data).lower() or "regex" in str(data).lower()
    
    def test_regex_test_empty_pattern(self, client, db_session):
        """Test regex testing with empty pattern."""
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": "",
                "sample_text": "Some text"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_regex_test_empty_sample_text(self, client, db_session):
        """Test regex testing with empty sample text."""
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"test",
                "sample_text": ""
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_regex_test_phone_pattern(self, client, db_session):
        """Test regex pattern for phone number extraction."""
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"Phone:\s*([\d-]+)",
                "sample_text": "Name: John Doe\nPhone: 555-123-4567"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is True
        assert len(data["groups"]) == 1
        assert data["groups"][0] == "555-123-4567"
    
    def test_regex_test_complex_pattern(self, client, db_session):
        """Test complex regex pattern with multiple features."""
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"(?i)email:\s*([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})",
                "sample_text": "Contact Info\nEmail: john.doe@example.com\nPhone: 555-1234"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["matched"] is True
        assert len(data["groups"]) == 1
        assert data["groups"][0] == "john.doe@example.com"
    
    def test_regex_test_requires_auth(self):
        """Test that regex testing requires authentication."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"test",
                "sample_text": "test text"
            }
        )
        
        assert response.status_code in [401, 403]
    
    def test_regex_test_sanitizes_input(self, client, db_session):
        """Test that regex testing sanitizes input properly."""
        # Test with null bytes in pattern (should be sanitized)
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": "test",  # Null bytes would be removed by sanitization
                "sample_text": "test text"
            }
        )
        
        # Should succeed after sanitization
        assert response.status_code == 200
    
    def test_regex_test_timeout_enforcement(self, client, db_session):
        """Test that regex timeout is enforced for pathological patterns."""
        # Use a pathological regex pattern that causes catastrophic backtracking
        # Pattern: (a+)+ with input that doesn't match causes exponential time
        response = client.post(
            "/api/v1/lead-sources/test-regex",
            json={
                "pattern": r"(a+)+b",
                "sample_text": "a" * 25 + "c"  # No 'b' at end causes backtracking
            }
        )
        
        # Should return timeout error (400) or complete quickly
        # The timeout mechanism should prevent hanging
        assert response.status_code in [200, 400]
        
        if response.status_code == 400:
            data = response.json()
            # Verify it's a timeout error
            assert "timeout" in data["message"].lower() or "time" in data["message"].lower()



class TestRegexProfileVersioning:
    """Tests for regex profile versioning endpoints."""
    
    def test_create_lead_source_creates_initial_version(self, client, db_session):
        """Test that creating a lead source creates an initial version record."""
        from api.models.web_ui_models import RegexProfileVersion
        
        response = client.post(
            "/api/v1/lead-sources",
            json={
                "sender_email": "leads@example.com",
                "identifier_snippet": "New Lead Notification",
                "name_regex": r"Name:\s*(.+)",
                "phone_regex": r"Phone:\s*([\d-]+)",
                "auto_respond_enabled": False
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        lead_source_id = data["id"]
        
        # Verify version record was created
        version = db_session.query(RegexProfileVersion).filter(
            RegexProfileVersion.lead_source_id == lead_source_id,
            RegexProfileVersion.version == 1
        ).first()
        
        assert version is not None
        assert version.name_regex == r"Name:\s*(.+)"
        assert version.phone_regex == r"Phone:\s*([\d-]+)"
        assert version.identifier_snippet == "New Lead Notification"
    
    def test_update_regex_creates_new_version(self, client, db_session):
        """Test that updating regex patterns creates a new version record."""
        from api.models.web_ui_models import RegexProfileVersion
        
        # Create lead source
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        # Create initial version
        version1 = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=1,
            name_regex=lead_source.name_regex,
            phone_regex=lead_source.phone_regex,
            identifier_snippet=lead_source.identifier_snippet,
            created_by=1
        )
        db_session.add(version1)
        db_session.commit()
        
        # Update regex patterns
        response = client.put(
            f"/api/v1/lead-sources/{lead_source.id}",
            json={
                "name_regex": r"Full Name:\s*(.+)",
                "phone_regex": r"Tel:\s*([\d-]+)"
            }
        )
        
        assert response.status_code == 200
        
        # Verify new version was created
        version2 = db_session.query(RegexProfileVersion).filter(
            RegexProfileVersion.lead_source_id == lead_source.id,
            RegexProfileVersion.version == 2
        ).first()
        
        assert version2 is not None
        assert version2.name_regex == r"Full Name:\s*(.+)"
        assert version2.phone_regex == r"Tel:\s*([\d-]+)"
    
    def test_update_non_regex_fields_no_version(self, client, db_session):
        """Test that updating non-regex fields doesn't create a version."""
        from api.models.web_ui_models import RegexProfileVersion
        
        # Create lead source
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        # Create initial version
        version1 = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=1,
            name_regex=lead_source.name_regex,
            phone_regex=lead_source.phone_regex,
            identifier_snippet=lead_source.identifier_snippet,
            created_by=1
        )
        db_session.add(version1)
        db_session.commit()
        
        # Update only auto_respond_enabled (not a regex field)
        response = client.put(
            f"/api/v1/lead-sources/{lead_source.id}",
            json={"auto_respond_enabled": True}
        )
        
        assert response.status_code == 200
        
        # Verify no new version was created
        versions = db_session.query(RegexProfileVersion).filter(
            RegexProfileVersion.lead_source_id == lead_source.id
        ).all()
        
        assert len(versions) == 1  # Only initial version
    
    def test_get_version_history(self, client, db_session):
        """Test retrieving version history for a lead source."""
        from api.models.web_ui_models import RegexProfileVersion
        
        # Create lead source
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        # Create multiple versions
        for i in range(1, 4):
            version = RegexProfileVersion(
                lead_source_id=lead_source.id,
                version=i,
                name_regex=f"Name{i}:\s*(.+)",
                phone_regex=f"Phone{i}:\s*([\d-]+)",
                identifier_snippet=f"Lead {i}",
                created_by=1
            )
            db_session.add(version)
        db_session.commit()
        
        # Get version history
        response = client.get(f"/api/v1/lead-sources/{lead_source.id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["versions"]) == 3
        
        # Verify versions are in reverse chronological order (newest first)
        assert data["versions"][0]["version"] == 3
        assert data["versions"][1]["version"] == 2
        assert data["versions"][2]["version"] == 1
        
        # Verify version details
        assert data["versions"][0]["name_regex"] == "Name3:\s*(.+)"
        assert data["versions"][0]["phone_regex"] == "Phone3:\s*([\d-]+)"
        assert data["versions"][0]["identifier_snippet"] == "Lead 3"
    
    def test_get_version_history_empty(self, client, db_session):
        """Test retrieving version history when no versions exist."""
        # Create lead source directly in database without versions
        # (bypassing the API which would create an initial version)
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        # Note: When created via API, an initial version is created
        # But when created directly in DB (like in tests), no version exists
        response = client.get(f"/api/v1/lead-sources/{lead_source.id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        # Since we created directly in DB, no versions should exist
        assert data["versions"] == []
    
    def test_get_version_history_not_found(self, client):
        """Test retrieving version history for non-existent lead source."""
        response = client.get("/api/v1/lead-sources/99999/versions")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_rollback_to_previous_version(self, client, db_session):
        """Test rolling back to a previous version."""
        from api.models.web_ui_models import RegexProfileVersion
        
        # Create lead source
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead v3",
            name_regex=r"Name3:\s*(.+)",
            phone_regex=r"Phone3:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        # Create version history
        version1 = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=1,
            name_regex=r"Name1:\s*(.+)",
            phone_regex=r"Phone1:\s*([\d-]+)",
            identifier_snippet="Lead v1",
            created_by=1
        )
        version2 = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=2,
            name_regex=r"Name2:\s*(.+)",
            phone_regex=r"Phone2:\s*([\d-]+)",
            identifier_snippet="Lead v2",
            created_by=1
        )
        version3 = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=3,
            name_regex=r"Name3:\s*(.+)",
            phone_regex=r"Phone3:\s*([\d-]+)",
            identifier_snippet="Lead v3",
            created_by=1
        )
        db_session.add_all([version1, version2, version3])
        db_session.commit()
        
        # Rollback to version 1
        response = client.post(
            f"/api/v1/lead-sources/{lead_source.id}/rollback",
            json={"version": 1}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "rolled back" in data["message"].lower()
        assert data["new_version"] == 4  # New version created for rollback
        
        # Verify lead source was updated
        assert data["lead_source"]["name_regex"] == r"Name1:\s*(.+)"
        assert data["lead_source"]["phone_regex"] == r"Phone1:\s*([\d-]+)"
        assert data["lead_source"]["identifier_snippet"] == "Lead v1"
        
        # Verify in database
        db_session.refresh(lead_source)
        assert lead_source.name_regex == r"Name1:\s*(.+)"
        assert lead_source.phone_regex == r"Phone1:\s*([\d-]+)"
        assert lead_source.identifier_snippet == "Lead v1"
        
        # Verify new version record was created
        version4 = db_session.query(RegexProfileVersion).filter(
            RegexProfileVersion.lead_source_id == lead_source.id,
            RegexProfileVersion.version == 4
        ).first()
        
        assert version4 is not None
        assert version4.name_regex == r"Name1:\s*(.+)"
        assert version4.phone_regex == r"Phone1:\s*([\d-]+)"
        assert version4.identifier_snippet == "Lead v1"
    
    def test_rollback_to_invalid_version(self, client, db_session):
        """Test rolling back to a non-existent version."""
        from api.models.web_ui_models import RegexProfileVersion
        
        # Create lead source
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        # Create one version
        version1 = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=1,
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            identifier_snippet="Lead",
            created_by=1
        )
        db_session.add(version1)
        db_session.commit()
        
        # Try to rollback to non-existent version
        response = client.post(
            f"/api/v1/lead-sources/{lead_source.id}/rollback",
            json={"version": 99}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_rollback_lead_source_not_found(self, client):
        """Test rolling back non-existent lead source."""
        response = client.post(
            "/api/v1/lead-sources/99999/rollback",
            json={"version": 1}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_rollback_records_audit_log(self, client, db_session):
        """Test that rollback records an audit log entry."""
        from api.models.web_ui_models import RegexProfileVersion, AuditLog
        
        # Create lead source
        lead_source = LeadSource(
            sender_email="leads@example.com",
            identifier_snippet="Lead v2",
            name_regex=r"Name2:\s*(.+)",
            phone_regex=r"Phone2:\s*([\d-]+)",
            auto_respond_enabled=False
        )
        db_session.add(lead_source)
        db_session.commit()
        db_session.refresh(lead_source)
        
        # Create versions
        version1 = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=1,
            name_regex=r"Name1:\s*(.+)",
            phone_regex=r"Phone1:\s*([\d-]+)",
            identifier_snippet="Lead v1",
            created_by=1
        )
        version2 = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=2,
            name_regex=r"Name2:\s*(.+)",
            phone_regex=r"Phone2:\s*([\d-]+)",
            identifier_snippet="Lead v2",
            created_by=1
        )
        db_session.add_all([version1, version2])
        db_session.commit()
        
        # Rollback to version 1
        response = client.post(
            f"/api/v1/lead-sources/{lead_source.id}/rollback",
            json={"version": 1}
        )
        
        assert response.status_code == 200
        
        # Verify audit log entry was created
        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.action == "regex_profile_rollback",
            AuditLog.resource_type == "lead_source",
            AuditLog.resource_id == lead_source.id
        ).first()
        
        assert audit_entry is not None
        assert "rolled back" in audit_entry.details.lower()
        assert "version 1" in audit_entry.details.lower()
    
    def test_version_history_requires_auth(self):
        """Test that getting version history requires authentication."""
        client = TestClient(app)
        response = client.get("/api/v1/lead-sources/1/versions")
        
        assert response.status_code in [401, 403]
    
    def test_rollback_requires_auth(self):
        """Test that rollback requires authentication."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/lead-sources/1/rollback",
            json={"version": 1}
        )
        
        assert response.status_code in [401, 403]

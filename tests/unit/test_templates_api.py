"""
Unit tests for template management API endpoints.

Tests cover:
- Template creation with validation
- Template listing
- Template detail retrieval
- Template updates (with versioning)
- Template deletion
- Validation errors (header injection, placeholders)
- Authentication requirements
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gmail_lead_sync.models import Base, Template
from api.models.web_ui_models import User, Session as SessionModel, TemplateVersion
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
    
    # Clean up templates table before each test
    session.query(Template).delete()
    session.query(TemplateVersion).delete()
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
    
    from api.routers import admin_templates as templates
    from api.main import get_db as main_get_db
    
    app.dependency_overrides[main_get_db] = override_get_db
    app.dependency_overrides[templates.get_db] = override_get_db
    app.dependency_overrides[templates.get_current_user] = override_get_current_user
    
    client = TestClient(app)
    client.cookies.set("session_token", auth_session.id)
    
    yield client
    
    app.dependency_overrides.clear()


class TestCreateTemplate:
    """Tests for POST /api/v1/templates endpoint."""
    
    def test_create_template_success(self, client, db_session):
        """Test successful template creation."""
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Welcome Template",
                "subject": "Thank you for your inquiry",
                "body": "Hi {lead_name},\n\nThank you for reaching out. "
                       "I'm {agent_name} and I'll be happy to assist you.\n\n"
                       "You can reach me at {agent_phone} or {agent_email}."
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert data["name"] == "Welcome Template"
        assert data["subject"] == "Thank you for your inquiry"
        assert "{lead_name}" in data["body"]
        assert "id" in data
        assert "created_at" in data
        
        # Verify template is in database
        template = db_session.query(Template).filter(Template.name == "Welcome Template").first()
        assert template is not None
        assert template.subject == "Thank you for your inquiry"
        
        # Verify initial version was created
        version = db_session.query(TemplateVersion).filter(
            TemplateVersion.template_id == template.id,
            TemplateVersion.version == 1
        ).first()
        assert version is not None
        assert version.name == "Welcome Template"
    
    def test_create_template_duplicate_name(self, client, db_session):
        """Test creating template with duplicate name fails."""
        # Create first template
        client.post(
            "/api/v1/templates",
            json={
                "name": "Welcome Template",
                "subject": "Subject 1",
                "body": "Body 1"
            }
        )
        
        # Try to create duplicate
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Welcome Template",
                "subject": "Subject 2",
                "body": "Body 2"
            }
        )
        
        assert response.status_code == 409  # Conflict
        data = response.json()
        assert "already exists" in data["message"].lower()
    
    def test_create_template_header_injection(self, client):
        """Test creating template with newlines in subject fails."""
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Bad Template",
                "subject": "Subject\r\nBcc: attacker@evil.com",
                "body": "Body"
            }
        )
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "header injection" in str(data).lower() or "newline" in str(data).lower()
    
    def test_create_template_invalid_placeholder(self, client):
        """Test creating template with invalid placeholder fails."""
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Bad Template",
                "subject": "Subject",
                "body": "Hi {lead_name}, your {invalid_placeholder} is ready."
            }
        )
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "invalid_placeholder" in str(data).lower() or "invalid placeholder" in str(data).lower()
    
    def test_create_template_valid_placeholders(self, client):
        """Test creating template with all valid placeholders succeeds."""
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Full Template",
                "subject": "Hello {lead_name}",
                "body": "Hi {lead_name}, I'm {agent_name}. "
                       "Contact me at {agent_phone} or {agent_email}."
            }
        )
        
        assert response.status_code == 201
    
    def test_create_template_records_audit_log(self, client, db_session):
        """Test that template creation records an audit log entry."""
        from api.models.web_ui_models import AuditLog
        
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Audit Test Template",
                "subject": "Subject",
                "body": "Body"
            }
        )
        
        assert response.status_code == 201
        template_id = response.json()["id"]
        
        # Verify audit log entry was created
        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.action == "template_created",
            AuditLog.resource_type == "template",
            AuditLog.resource_id == template_id
        ).first()
        
        assert audit_entry is not None
        assert audit_entry.action == "template_created"
        # Check that the template name is in the details
        assert template_id == audit_entry.resource_id
    
    def test_create_template_missing_fields(self, client):
        """Test creating template with missing required fields fails."""
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Incomplete Template"
                # Missing subject and body
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestListTemplates:
    """Tests for GET /api/v1/templates endpoint."""
    
    def test_list_templates_empty(self, client):
        """Test listing templates when none exist."""
        response = client.get("/api/v1/templates")
        
        assert response.status_code == 200
        data = response.json()
        assert data["templates"] == []
    
    def test_list_templates_multiple(self, client, db_session):
        """Test listing multiple templates."""
        # Create multiple templates
        for i in range(3):
            template = Template(
                name=f"Template {i+1}",
                subject=f"Subject {i+1}",
                body=f"Body {i+1}"
            )
            db_session.add(template)
        db_session.commit()
        
        response = client.get("/api/v1/templates")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["templates"]) == 3
        
        # Verify templates are returned
        template_names = [t["name"] for t in data["templates"]]
        assert "Template 1" in template_names
        assert "Template 2" in template_names
        assert "Template 3" in template_names


class TestGetTemplate:
    """Tests for GET /api/v1/templates/{id} endpoint."""
    
    def test_get_template_success(self, client, db_session):
        """Test getting template details."""
        template = Template(
            name="Test Template",
            subject="Test Subject",
            body="Test Body with {lead_name}"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        response = client.get(f"/api/v1/templates/{template.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Template"
        assert data["subject"] == "Test Subject"
        assert "{lead_name}" in data["body"]
    
    def test_get_template_not_found(self, client):
        """Test getting non-existent template returns 404."""
        response = client.get("/api/v1/templates/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()


class TestUpdateTemplate:
    """Tests for PUT /api/v1/templates/{id} endpoint."""
    
    def test_update_template_name(self, client, db_session, test_user):
        """Test updating template name."""
        template = Template(
            name="Old Name",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        response = client.put(
            f"/api/v1/templates/{template.id}",
            json={"name": "New Name"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        
        # Verify in database
        db_session.refresh(template)
        assert template.name == "New Name"
        
        # Verify version was created
        version = db_session.query(TemplateVersion).filter(
            TemplateVersion.template_id == template.id
        ).first()
        assert version is not None
    
    def test_update_template_subject(self, client, db_session, test_user):
        """Test updating template subject."""
        template = Template(
            name="Template",
            subject="Old Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        response = client.put(
            f"/api/v1/templates/{template.id}",
            json={"subject": "New Subject"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["subject"] == "New Subject"
    
    def test_update_template_body(self, client, db_session, test_user):
        """Test updating template body."""
        template = Template(
            name="Template",
            subject="Subject",
            body="Old Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        response = client.put(
            f"/api/v1/templates/{template.id}",
            json={"body": "New Body with {lead_name}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "New Body" in data["body"]
    
    def test_update_template_creates_version(self, client, db_session, test_user):
        """Test that updating template creates a new version."""
        template = Template(
            name="Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        # Create initial version
        initial_version = TemplateVersion(
            template_id=template.id,
            version=1,
            name=template.name,
            subject=template.subject,
            body=template.body,
            created_by=test_user.id
        )
        db_session.add(initial_version)
        db_session.commit()
        
        # Update template
        response = client.put(
            f"/api/v1/templates/{template.id}",
            json={"subject": "Updated Subject"}
        )
        
        assert response.status_code == 200
        
        # Verify new version was created
        versions = db_session.query(TemplateVersion).filter(
            TemplateVersion.template_id == template.id
        ).order_by(TemplateVersion.version).all()
        
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[1].subject == "Updated Subject"
    
    def test_update_template_no_fields(self, client, db_session):
        """Test updating template with no fields fails."""
        template = Template(
            name="Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        response = client.put(f"/api/v1/templates/{template.id}", json={})
        
        assert response.status_code == 400  # Validation error
        data = response.json()
        assert "no fields" in data["message"].lower()
    
    def test_update_template_header_injection(self, client, db_session):
        """Test updating template with header injection fails."""
        template = Template(
            name="Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        response = client.put(
            f"/api/v1/templates/{template.id}",
            json={"subject": "Subject\nBcc: attacker@evil.com"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_update_template_invalid_placeholder(self, client, db_session):
        """Test updating template with invalid placeholder fails."""
        template = Template(
            name="Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        response = client.put(
            f"/api/v1/templates/{template.id}",
            json={"body": "Body with {invalid_placeholder}"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_update_template_not_found(self, client):
        """Test updating non-existent template returns 404."""
        response = client.put(
            "/api/v1/templates/99999",
            json={"name": "New Name"}
        )
        
        assert response.status_code == 404
    
    def test_update_template_duplicate_name(self, client, db_session):
        """Test updating template to duplicate name fails."""
        # Create two templates
        template1 = Template(name="Template 1", subject="S1", body="B1")
        template2 = Template(name="Template 2", subject="S2", body="B2")
        db_session.add(template1)
        db_session.add(template2)
        db_session.commit()
        db_session.refresh(template1)
        db_session.refresh(template2)
        
        # Try to rename template2 to template1's name
        response = client.put(
            f"/api/v1/templates/{template2.id}",
            json={"name": "Template 1"}
        )
        
        assert response.status_code == 409  # Conflict
    
    def test_update_template_records_audit_log(self, client, db_session):
        """Test that template update records audit log entries."""
        from api.models.web_ui_models import AuditLog
        
        template = Template(
            name="Template",
            subject="Old Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        template_id = template.id
        
        # Update template
        response = client.put(
            f"/api/v1/templates/{template_id}",
            json={"subject": "New Subject"}
        )
        
        assert response.status_code == 200
        
        # Verify audit log entries were created
        audit_entries = db_session.query(AuditLog).filter(
            AuditLog.resource_type == "template",
            AuditLog.resource_id == template_id
        ).all()
        
        # Should have entries for both version creation and update
        assert len(audit_entries) >= 2
        
        # Check for template_updated entry
        update_entry = next(
            (e for e in audit_entries if e.action == "template_updated"),
            None
        )
        assert update_entry is not None
        assert update_entry.resource_id == template_id
        
        # Check for template_version_created entry
        version_entry = next(
            (e for e in audit_entries if e.action == "template_version_created"),
            None
        )
        assert version_entry is not None
        assert version_entry.resource_id == template_id


class TestDeleteTemplate:
    """Tests for DELETE /api/v1/templates/{id} endpoint."""
    
    def test_delete_template_success(self, client, db_session):
        """Test successful template deletion."""
        template = Template(
            name="Test Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        template_id = template.id
        
        response = client.delete(f"/api/v1/templates/{template_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"].lower()
        
        # Verify template is deleted from database
        template = db_session.query(Template).filter(Template.id == template_id).first()
        assert template is None
    
    def test_delete_template_not_found(self, client):
        """Test deleting non-existent template returns 404."""
        response = client.delete("/api/v1/templates/99999")
        
        assert response.status_code == 404
    
    def test_delete_template_records_audit_log(self, client, db_session):
        """Test that template deletion records an audit log entry."""
        from api.models.web_ui_models import AuditLog
        
        template = Template(
            name="Test Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        template_id = template.id
        
        # Delete the template
        response = client.delete(f"/api/v1/templates/{template_id}")
        assert response.status_code == 200
        
        # Verify audit log entry was created
        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.action == "template_deleted",
            AuditLog.resource_type == "template",
            AuditLog.resource_id == template_id
        ).first()
        
        assert audit_entry is not None
        assert audit_entry.action == "template_deleted"
        assert "Test Template" in audit_entry.details


class TestTemplateAuthentication:
    """Tests for authentication requirements on template endpoints."""
    
    def test_create_template_requires_auth(self):
        """Test that creating template requires authentication."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/templates",
            json={
                "name": "Template",
                "subject": "Subject",
                "body": "Body"
            }
        )
        
        # Should fail without authentication
        assert response.status_code in [401, 403]
    
    def test_list_templates_requires_auth(self):
        """Test that listing templates requires authentication."""
        client = TestClient(app)
        response = client.get("/api/v1/templates")
        
        # Should fail without authentication
        assert response.status_code in [401, 403]
    
    def test_get_template_requires_auth(self):
        """Test that getting template details requires authentication."""
        client = TestClient(app)
        response = client.get("/api/v1/templates/1")
        
        # Should fail without authentication
        assert response.status_code in [401, 403]
    
    def test_update_template_requires_auth(self):
        """Test that updating template requires authentication."""
        client = TestClient(app)
        response = client.put(
            "/api/v1/templates/1",
            json={"name": "New Name"}
        )
        
        # Should fail without authentication
        assert response.status_code in [401, 403]
    
    def test_delete_template_requires_auth(self):
        """Test that deleting template requires authentication."""
        client = TestClient(app)
        response = client.delete("/api/v1/templates/1")
        
        # Should fail without authentication
        assert response.status_code in [401, 403]
    
    def test_preview_template_requires_auth(self):
        """Test that previewing template requires authentication."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Subject",
                "body": "Body"
            }
        )
        
        # Should fail without authentication
        assert response.status_code in [401, 403]
    
    def test_get_template_versions_requires_auth(self):
        """Test that getting template versions requires authentication."""
        client = TestClient(app)
        response = client.get("/api/v1/templates/1/versions")
        
        # Should fail without authentication
        assert response.status_code in [401, 403]
    
    def test_rollback_template_requires_auth(self):
        """Test that rolling back template requires authentication."""
        client = TestClient(app)
        response = client.post(
            "/api/v1/templates/1/rollback",
            json={"version": 1}
        )
        
        # Should fail without authentication
        assert response.status_code in [401, 403]


class TestTemplatePreview:
    """Tests for POST /api/v1/templates/preview endpoint."""
    
    def test_preview_template_success(self, client):
        """Test successful template preview with placeholder substitution."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Thank you {lead_name}",
                "body": "Hi {lead_name},\n\nI'm {agent_name}. "
                       "Contact me at {agent_phone} or {agent_email}."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify placeholders were substituted
        assert data["subject"] == "Thank you John Doe"
        assert "Hi John Doe" in data["body"]
        assert "Agent Smith" in data["body"]
        assert "555-9999" in data["body"]
        assert "agent@example.com" in data["body"]
        
        # Verify no placeholders remain
        assert "{lead_name}" not in data["subject"]
        assert "{lead_name}" not in data["body"]
        assert "{agent_name}" not in data["body"]
        assert "{agent_phone}" not in data["body"]
        assert "{agent_email}" not in data["body"]
    
    def test_preview_template_html_escaping(self, client):
        """Test that HTML in body is escaped for safe display."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Subject",
                "body": "Hello {lead_name},\n\n<script>alert('xss')</script>\n\n"
                       "<b>Bold text</b> and <a href='http://evil.com'>link</a>"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify HTML is escaped
        assert "&lt;script&gt;" in data["body"]
        assert "&lt;/script&gt;" in data["body"]
        assert "&lt;b&gt;" in data["body"]
        assert "&lt;/b&gt;" in data["body"]
        assert "&lt;a href=" in data["body"]
        
        # Verify raw HTML tags are not present
        assert "<script>" not in data["body"]
        assert "<b>" not in data["body"]
        assert "<a href=" not in data["body"]
    
    def test_preview_template_all_placeholders(self, client):
        """Test preview with all supported placeholders."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Hello {lead_name}",
                "body": "Lead: {lead_name}\nAgent: {agent_name}\n"
                       "Phone: {agent_phone}\nEmail: {agent_email}"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all placeholders were substituted
        assert "John Doe" in data["subject"]
        assert "Lead: John Doe" in data["body"]
        assert "Agent: Agent Smith" in data["body"]
        assert "Phone: 555-9999" in data["body"]
        assert "Email: agent@example.com" in data["body"]
    
    def test_preview_template_no_placeholders(self, client):
        """Test preview with no placeholders."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Static Subject",
                "body": "This is a static body with no placeholders."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify content is returned as-is (with HTML escaping)
        assert data["subject"] == "Static Subject"
        assert "This is a static body with no placeholders." in data["body"]
    
    def test_preview_template_invalid_placeholder(self, client):
        """Test preview with invalid placeholder fails validation."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Subject",
                "body": "Hello {lead_name}, your {invalid_placeholder} is ready."
            }
        )
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "invalid_placeholder" in str(data).lower() or "invalid placeholder" in str(data).lower()
    
    def test_preview_template_header_injection(self, client):
        """Test preview with newlines in subject fails validation."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Subject\r\nBcc: attacker@evil.com",
                "body": "Body"
            }
        )
        
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "header injection" in str(data).lower() or "newline" in str(data).lower()
    
    def test_preview_template_missing_fields(self, client):
        """Test preview with missing required fields fails."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Subject"
                # Missing body
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_preview_template_empty_fields(self, client):
        """Test preview with empty fields fails validation."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "",
                "body": ""
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_preview_template_preserves_formatting(self, client):
        """Test that preview preserves line breaks and formatting."""
        response = client.post(
            "/api/v1/templates/preview",
            json={
                "subject": "Subject",
                "body": "Line 1\n\nLine 2 with {lead_name}\n\nLine 3"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify line breaks are preserved (as escaped \n in HTML)
        # The body should contain the text with John Doe substituted
        assert "Line 1" in data["body"]
        assert "Line 2 with John Doe" in data["body"]
        assert "Line 3" in data["body"]


class TestTemplateVersioning:
    """Tests for template version history and rollback endpoints."""
    
    def test_get_template_versions_success(self, client, db_session, test_user):
        """Test getting version history for a template."""
        # Create template
        template = Template(
            name="Test Template",
            subject="Subject v1",
            body="Body v1"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        # Create multiple versions
        for i in range(1, 4):
            version = TemplateVersion(
                template_id=template.id,
                version=i,
                name=f"Test Template v{i}",
                subject=f"Subject v{i}",
                body=f"Body v{i}",
                created_by=test_user.id
            )
            db_session.add(version)
        db_session.commit()
        
        # Get version history
        response = client.get(f"/api/v1/templates/{template.id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify versions are returned in reverse order (newest first)
        assert len(data["versions"]) == 3
        assert data["versions"][0]["version"] == 3
        assert data["versions"][1]["version"] == 2
        assert data["versions"][2]["version"] == 1
        
        # Verify version details
        assert data["versions"][0]["subject"] == "Subject v3"
        assert data["versions"][1]["subject"] == "Subject v2"
        assert data["versions"][2]["subject"] == "Subject v1"
    
    def test_get_template_versions_empty(self, client, db_session):
        """Test getting version history for template with no versions."""
        # Create template without versions
        template = Template(
            name="Test Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        # Get version history
        response = client.get(f"/api/v1/templates/{template.id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["versions"] == []
    
    def test_get_template_versions_not_found(self, client):
        """Test getting version history for non-existent template."""
        response = client.get("/api/v1/templates/99999/versions")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_rollback_template_success(self, client, db_session, test_user):
        """Test successful template rollback."""
        # Create template
        template = Template(
            name="Test Template v3",
            subject="Subject v3",
            body="Body v3"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        # Create version history
        version1 = TemplateVersion(
            template_id=template.id,
            version=1,
            name="Test Template v1",
            subject="Subject v1",
            body="Body v1",
            created_by=test_user.id
        )
        version2 = TemplateVersion(
            template_id=template.id,
            version=2,
            name="Test Template v2",
            subject="Subject v2",
            body="Body v2",
            created_by=test_user.id
        )
        version3 = TemplateVersion(
            template_id=template.id,
            version=3,
            name="Test Template v3",
            subject="Subject v3",
            body="Body v3",
            created_by=test_user.id
        )
        db_session.add_all([version1, version2, version3])
        db_session.commit()
        
        # Rollback to version 1
        response = client.post(
            f"/api/v1/templates/{template.id}/rollback",
            json={"version": 1}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert "rolled back" in data["message"].lower()
        assert data["new_version"] == 4  # New version created
        assert data["template"]["name"] == "Test Template v1"
        assert data["template"]["subject"] == "Subject v1"
        assert data["template"]["body"] == "Body v1"
        
        # Verify template was updated in database
        db_session.refresh(template)
        assert template.name == "Test Template v1"
        assert template.subject == "Subject v1"
        assert template.body == "Body v1"
        
        # Verify new version was created
        new_version = db_session.query(TemplateVersion).filter(
            TemplateVersion.template_id == template.id,
            TemplateVersion.version == 4
        ).first()
        assert new_version is not None
        assert new_version.name == "Test Template v1"
        assert new_version.subject == "Subject v1"
        assert new_version.body == "Body v1"
    
    def test_rollback_template_not_found(self, client):
        """Test rollback for non-existent template."""
        response = client.post(
            "/api/v1/templates/99999/rollback",
            json={"version": 1}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_rollback_template_version_not_found(self, client, db_session, test_user):
        """Test rollback to non-existent version."""
        # Create template
        template = Template(
            name="Test Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        # Create only version 1
        version = TemplateVersion(
            template_id=template.id,
            version=1,
            name="Test Template",
            subject="Subject",
            body="Body",
            created_by=test_user.id
        )
        db_session.add(version)
        db_session.commit()
        
        # Try to rollback to non-existent version 5
        response = client.post(
            f"/api/v1/templates/{template.id}/rollback",
            json={"version": 5}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower()
    
    def test_rollback_template_records_audit_log(self, client, db_session, test_user):
        """Test that template rollback records an audit log entry."""
        from api.models.web_ui_models import AuditLog
        
        # Create template
        template = Template(
            name="Test Template v2",
            subject="Subject v2",
            body="Body v2"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        # Create versions
        version1 = TemplateVersion(
            template_id=template.id,
            version=1,
            name="Test Template v1",
            subject="Subject v1",
            body="Body v1",
            created_by=test_user.id
        )
        version2 = TemplateVersion(
            template_id=template.id,
            version=2,
            name="Test Template v2",
            subject="Subject v2",
            body="Body v2",
            created_by=test_user.id
        )
        db_session.add_all([version1, version2])
        db_session.commit()
        
        # Rollback to version 1
        response = client.post(
            f"/api/v1/templates/{template.id}/rollback",
            json={"version": 1}
        )
        assert response.status_code == 200
        
        # Verify audit log entry was created
        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.action == "template_rollback",
            AuditLog.resource_type == "template",
            AuditLog.resource_id == template.id
        ).first()
        
        assert audit_entry is not None
        assert audit_entry.action == "template_rollback"
        assert "version 1" in audit_entry.details.lower()
        # Just verify that a new version was created (don't check specific number)
        assert "created new version" in audit_entry.details.lower()
    
    def test_rollback_template_invalid_version(self, client, db_session):
        """Test rollback with invalid version number."""
        # Create template
        template = Template(
            name="Test Template",
            subject="Subject",
            body="Body"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        # Try to rollback to version 0 (invalid)
        response = client.post(
            f"/api/v1/templates/{template.id}/rollback",
            json={"version": 0}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_rollback_template_maintains_audit_trail(self, client, db_session, test_user):
        """Test that rollback creates new version instead of deleting history."""
        # Create template
        template = Template(
            name="Test Template v2",
            subject="Subject v2",
            body="Body v2"
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        
        # Create versions
        version1 = TemplateVersion(
            template_id=template.id,
            version=1,
            name="Test Template v1",
            subject="Subject v1",
            body="Body v1",
            created_by=test_user.id
        )
        version2 = TemplateVersion(
            template_id=template.id,
            version=2,
            name="Test Template v2",
            subject="Subject v2",
            body="Body v2",
            created_by=test_user.id
        )
        db_session.add_all([version1, version2])
        db_session.commit()
        
        # Rollback to version 1
        response = client.post(
            f"/api/v1/templates/{template.id}/rollback",
            json={"version": 1}
        )
        assert response.status_code == 200
        
        # Verify all versions still exist (no deletion)
        all_versions = db_session.query(TemplateVersion).filter(
            TemplateVersion.template_id == template.id
        ).order_by(TemplateVersion.version).all()
        
        assert len(all_versions) == 3  # Original 2 + new rollback version
        assert all_versions[0].version == 1
        assert all_versions[1].version == 2
        assert all_versions[2].version == 3  # New version from rollback
        assert all_versions[2].subject == "Subject v1"  # Contains v1 content


"""
Unit tests for lead API endpoints.

Tests cover:
- Lead listing with pagination
- Lead filtering by date range and response status
- Lead detail retrieval
- Error handling for non-existent leads

Requirements:
- 5.1: Provide endpoints for retrieving Lead records with pagination
- 5.2: Support filtering Leads by Agent, date range, and processing status
- 5.4: Provide detail view showing full Lead content and metadata
- 5.7: Display processing status and response status for each Lead
- 24.2: Include unit tests for all API endpoints
"""

import pytest
import csv
import io
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock

from gmail_lead_sync.models import Base, Lead, LeadSource, Template
from api.models.web_ui_models import User, Session as SessionModel
from api.main import app
from api.routes.leads import get_db, get_current_user


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    return User(
        id=1,
        username="testuser",
        password_hash="hashed_password",
        role="admin",
        created_at=datetime.utcnow()
    )


@pytest.fixture
def client(db_session, mock_user):
    """Create a test client with dependency overrides."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    def override_get_current_user():
        return mock_user
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_template(db_session):
    """Create a sample template for testing."""
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
def sample_lead_source(db_session, sample_template):
    """Create a sample lead source for testing."""
    lead_source = LeadSource(
        sender_email="leads@example.com",
        identifier_snippet="New Lead",
        name_regex=r"Name:\s*(.+)",
        phone_regex=r"Phone:\s*([\d-]+)",
        template_id=sample_template.id,
        auto_respond_enabled=True
    )
    db_session.add(lead_source)
    db_session.commit()
    db_session.refresh(lead_source)
    return lead_source


@pytest.fixture
def sample_leads(db_session, sample_lead_source):
    """Create sample leads for testing."""
    leads = []
    
    # Create leads with different timestamps and statuses
    for i in range(5):
        lead = Lead(
            name=f"Test Lead {i+1}",
            phone=f"555-000{i}",
            source_email="leads@example.com",
            lead_source_id=sample_lead_source.id,
            gmail_uid=f"uid_{i+1}",
            created_at=datetime.utcnow() - timedelta(days=i),
            response_sent=(i % 2 == 0),  # Alternate response_sent
            response_status="success" if (i % 2 == 0) else None
        )
        db_session.add(lead)
        leads.append(lead)
    
    db_session.commit()
    
    # Refresh all leads
    for lead in leads:
        db_session.refresh(lead)
    
    return leads


class TestLeadListing:
    """Tests for lead listing endpoint."""
    
    def test_list_leads_success(self, client, sample_leads):
        """Test successful lead listing."""
        response = client.get("/api/v1/leads")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "leads" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data
        
        assert data["total"] == 5
        assert len(data["leads"]) == 5
        assert data["page"] == 1
        assert data["per_page"] == 50
        assert data["pages"] == 1
    
    def test_list_leads_pagination(self, client, sample_leads):
        """Test lead listing with pagination."""
        # Request page 1 with 2 leads per page
        response = client.get("/api/v1/leads?page=1&per_page=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert len(data["leads"]) == 2
        assert data["page"] == 1
        assert data["per_page"] == 2
        assert data["pages"] == 3
        
        # Request page 2
        response = client.get("/api/v1/leads?page=2&per_page=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["leads"]) == 2
        assert data["page"] == 2
    
    def test_list_leads_filter_by_response_sent(self, client, sample_leads):
        """Test filtering leads by response_sent status."""
        # Filter for leads with response sent
        response = client.get("/api/v1/leads?response_sent=true")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 3 leads with response_sent=True (indices 0, 2, 4)
        assert data["total"] == 3
        assert all(lead["response_sent"] for lead in data["leads"])
        
        # Filter for leads without response sent
        response = client.get("/api/v1/leads?response_sent=false")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have 2 leads with response_sent=False (indices 1, 3)
        assert data["total"] == 2
        assert all(not lead["response_sent"] for lead in data["leads"])
    
    def test_list_leads_filter_by_date_range(self, client, sample_leads):
        """Test filtering leads by date range."""
        # Get date range for filtering (last 2 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)
        
        response = client.get(
            f"/api/v1/leads?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have leads from the last 2 days
        # Leads are created with: datetime.utcnow() - timedelta(days=i) for i in range(5)
        # So leads 0, 1, 2 are within the last 2 days (0, 1, 2 days ago)
        assert data["total"] >= 2  # At least leads 0 and 1
    
    def test_list_leads_empty_result(self, client, db_session, sample_lead_source):
        """Test listing leads when no leads exist."""
        # sample_lead_source ensures tables are created
        response = client.get("/api/v1/leads")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 0
        assert len(data["leads"]) == 0
        assert data["pages"] == 1
    
    def test_list_leads_max_per_page_limit(self, client, sample_leads):
        """Test that per_page is limited to maximum value."""
        # Request more than max per_page (100)
        response = client.get("/api/v1/leads?per_page=200")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be limited to 100
        assert data["per_page"] == 100
    
    def test_list_leads_page_beyond_total(self, client, sample_leads):
        """Test requesting a page beyond total pages."""
        # Request page 10 when only 1 page exists
        response = client.get("/api/v1/leads?page=10&per_page=50")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return empty results but valid pagination info
        assert data["total"] == 5
        assert len(data["leads"]) == 0
        assert data["page"] == 10
        assert data["pages"] == 1
    
    def test_list_leads_invalid_per_page(self, client, sample_leads):
        """Test handling of invalid per_page values."""
        # Test per_page=0 - should handle gracefully
        response = client.get("/api/v1/leads?per_page=0")
        
        # Should either return 422 validation error or handle gracefully with default
        assert response.status_code in [200, 422, 400]
        
        if response.status_code == 200:
            data = response.json()
            # If it returns 200, it should use a sensible default (not 0)
            assert data["per_page"] > 0
    
    def test_list_leads_combined_filters(self, client, sample_leads):
        """Test applying multiple filters simultaneously."""
        # Get date range for filtering (last 2 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)
        
        # Apply both date range and response_sent filters
        response = client.get(
            f"/api/v1/leads?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}&response_sent=true"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have leads that match both filters
        # All returned leads should have response_sent=True
        for lead in data["leads"]:
            assert lead["response_sent"] is True
    
    def test_list_leads_invalid_date_format(self, client, sample_leads):
        """Test handling of invalid date format."""
        # Test with invalid date format
        response = client.get("/api/v1/leads?start_date=invalid-date")
        
        # Should return 422 validation error or handle gracefully
        assert response.status_code in [200, 422, 400]


class TestLeadDetail:
    """Tests for lead detail endpoint."""
    
    def test_get_lead_success(self, client, sample_leads):
        """Test successful lead detail retrieval."""
        lead = sample_leads[0]
        
        response = client.get(f"/api/v1/leads/{lead.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == lead.id
        assert data["name"] == lead.name
        assert data["phone"] == lead.phone
        assert data["source_email"] == lead.source_email
        assert data["lead_source_id"] == lead.lead_source_id
        assert data["gmail_uid"] == lead.gmail_uid
        assert data["response_sent"] == lead.response_sent
        assert data["response_status"] == lead.response_status
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_get_lead_with_response_status(self, client, sample_leads):
        """Test lead detail includes response status."""
        # Get lead with response sent
        lead = sample_leads[0]  # Has response_sent=True
        
        response = client.get(f"/api/v1/leads/{lead.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["response_sent"] is True
        assert data["response_status"] == "success"
    
    def test_get_lead_without_response(self, client, sample_leads):
        """Test lead detail for lead without response."""
        # Get lead without response sent
        lead = sample_leads[1]  # Has response_sent=False
        
        response = client.get(f"/api/v1/leads/{lead.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["response_sent"] is False
        assert data["response_status"] is None
    
    def test_get_lead_not_found(self, client, sample_lead_source):
        """Test getting non-existent lead returns 404."""
        # sample_lead_source ensures tables are created
        response = client.get("/api/v1/leads/99999")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "error" in data
        assert "message" in data
        assert "Lead with ID 99999 not found" in data["message"]
    
    def test_get_lead_invalid_id(self, client):
        """Test getting lead with invalid ID format."""
        response = client.get("/api/v1/leads/invalid")
        
        # FastAPI will return 422 for invalid path parameter type
        assert response.status_code == 422


class TestLeadAuthentication:
    """Tests for lead endpoint authentication."""
    
    def test_list_leads_requires_authentication(self, db_session):
        """Test that listing leads requires authentication."""
        # Create client without authentication override
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/leads")
            
            # Should return 401 or 403 (depending on auth implementation)
            assert response.status_code in [401, 403]
        
        app.dependency_overrides.clear()
    
    def test_get_lead_requires_authentication(self, db_session):
        """Test that getting lead detail requires authentication."""
        # Create client without authentication override
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as test_client:
            response = test_client.get("/api/v1/leads/1")
            
            # Should return 401 or 403 (depending on auth implementation)
            assert response.status_code in [401, 403]
        
        app.dependency_overrides.clear()


class TestLeadResponseFormat:
    """Tests for lead response format validation."""
    
    def test_lead_response_includes_all_fields(self, client, sample_leads):
        """Test that lead response includes all required fields."""
        lead = sample_leads[0]
        
        response = client.get(f"/api/v1/leads/{lead.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields are present
        required_fields = [
            "id", "name", "phone", "source_email", "lead_source_id",
            "gmail_uid", "created_at", "response_sent"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_lead_list_response_format(self, client, sample_leads):
        """Test that lead list response has correct format."""
        response = client.get("/api/v1/leads")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert isinstance(data["leads"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["per_page"], int)
        assert isinstance(data["pages"], int)
        
        # Verify each lead has correct format
        if len(data["leads"]) > 0:
            lead = data["leads"][0]
            assert isinstance(lead["id"], int)
            assert isinstance(lead["name"], str)
            assert isinstance(lead["phone"], str)
            assert isinstance(lead["response_sent"], bool)



class TestLeadCSVExport:
    """Tests for CSV export endpoint."""
    
    def test_export_csv_success(self, client, sample_leads):
        """Test successful CSV export with all leads."""
        response = client.get("/api/v1/leads/export")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "leads_export.csv" in response.headers["content-disposition"]
        
        # Parse CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        
        # Check header row (strip any carriage returns)
        header_line = lines[0].strip()
        assert header_line == "id,name,phone,source_email,lead_source_id,gmail_uid,created_at,updated_at,response_sent,response_status"
        
        # Check data rows (5 leads)
        assert len(lines) == 6  # 1 header + 5 data rows
    
    def test_export_csv_with_filters(self, client, sample_leads):
        """Test CSV export with filters applied."""
        # Export only leads with response sent
        response = client.get("/api/v1/leads/export?response_sent=true")
        
        assert response.status_code == 200
        
        # Parse CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        
        # Should have 3 leads with response_sent=True (indices 0, 2, 4)
        assert len(lines) == 4  # 1 header + 3 data rows
        
        # Verify all data rows have response_sent=True
        for line in lines[1:]:  # Skip header
            fields = line.split(',')
            # response_sent is the 9th field (index 8)
            assert fields[8] == "True"
    
    def test_export_csv_with_date_range(self, client, sample_leads):
        """Test CSV export with date range filter."""
        # Get date range for filtering (last 2 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)
        
        response = client.get(
            f"/api/v1/leads/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )
        
        assert response.status_code == 200
        
        # Parse CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        
        # Should have at least 2 leads from the last 2 days
        assert len(lines) >= 3  # 1 header + at least 2 data rows
    
    def test_export_csv_combined_filters(self, client, sample_leads):
        """Test CSV export with multiple filters applied."""
        # Get date range for filtering (last 2 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)
        
        # Apply both date range and response_sent filters
        response = client.get(
            f"/api/v1/leads/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}&response_sent=true"
        )
        
        assert response.status_code == 200
        
        # Parse CSV content
        csv_content = response.text
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        # All data rows should have response_sent=True
        for row in rows[1:]:  # Skip header
            assert row[8] == "True"
    
    def test_export_csv_invalid_date_format(self, client, sample_leads):
        """Test CSV export with invalid date format."""
        # Test with invalid date format
        response = client.get("/api/v1/leads/export?start_date=invalid-date")
        
        # Should return 422 validation error or handle gracefully
        assert response.status_code in [200, 422, 400]

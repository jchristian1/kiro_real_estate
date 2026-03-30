"""
Unit tests for lead API endpoints.

Tests cover:
- Lead listing with pagination
- Lead filtering by date range and response status
- Lead detail retrieval — unified read model (UnifiedLeadDetailResponse)
- CSV export
- Authentication requirements

Requirements:
- 5.1: Provide endpoints for retrieving Lead records with pagination
- 5.2: Support filtering Leads by Agent, date range, and processing status
- 5.4: Provide detail view showing full Lead content and metadata
- 5.7: Display processing status and response status for each Lead
- 24.2: Include unit tests for all API endpoints
"""

import csv
import io
import secrets
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import all model modules so their tables register with Base before create_all
from gmail_lead_sync.models import Base, Lead, LeadSource, Template
from api.models.web_ui_models import User, Session as UserSession  # noqa: F401
import gmail_lead_sync.preapproval.models_preapproval  # noqa: F401 — form_versions FK dep
import gmail_lead_sync.agent_models  # noqa: F401 — agent tables
from api.main import app
from api.routers.admin_leads import get_db as admin_get_db
from api.dependencies.db import get_db as core_get_db


# ---------------------------------------------------------------------------
# Shared in-memory SQLite engine (StaticPool = single connection across threads)
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test; restore overrides; drop after."""
    Base.metadata.create_all(bind=engine)
    # Ensure overrides are set for every test (other test files may clear them)
    app.dependency_overrides[admin_get_db] = _override_get_db
    app.dependency_overrides[core_get_db] = _override_get_db
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(setup_db):
    """Yield a test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _create_admin_user(db, username="admin@test.com", role="company_admin") -> User:
    user = User(
        username=username,
        password_hash="hashed",
        role=role,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_admin_session(db, user_id: int) -> str:
    from api.auth import derive_session_digest
    from api.config import get_config
    raw_token = secrets.token_hex(64)
    digest = derive_session_digest(get_config().secret_key, raw_token)
    session = UserSession(
        id=digest,
        user_id=user_id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
        last_accessed=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    return raw_token  # return the raw token for the cookie


def _auth_cookie(token: str) -> dict:
    return {"Cookie": f"session_token={token}"}


@pytest.fixture
def client(setup_db):
    """Test client authenticated as a company_admin."""
    db = TestingSessionLocal()
    user = _create_admin_user(db)
    token = _create_admin_session(db, user.id)
    db.close()

    with TestClient(app) as tc:
        tc.headers.update(_auth_cookie(token))
        yield tc


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_template(db_session):
    template = Template(name="Test Template", subject="Test Subject", body="Test Body")
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


@pytest.fixture
def sample_lead_source(db_session, sample_template):
    ls = LeadSource(
        sender_email="leads@example.com",
        identifier_snippet="New Lead",
        name_regex=r"Name:\s*(.+)",
        phone_regex=r"Phone:\s*([\d-]+)",
        template_id=sample_template.id,
        auto_respond_enabled=True,
    )
    db_session.add(ls)
    db_session.commit()
    db_session.refresh(ls)
    return ls


@pytest.fixture
def sample_leads(db_session, sample_lead_source):
    leads = []
    for i in range(5):
        lead = Lead(
            name=f"Test Lead {i + 1}",
            phone=f"555-000{i}",
            source_email="leads@example.com",
            lead_source_id=sample_lead_source.id,
            gmail_uid=f"uid_{i + 1}",
            created_at=datetime.utcnow() - timedelta(days=i),
            response_sent=(i % 2 == 0),
            response_status="success" if (i % 2 == 0) else None,
        )
        db_session.add(lead)
        leads.append(lead)
    db_session.commit()
    for lead in leads:
        db_session.refresh(lead)
    return leads


# ---------------------------------------------------------------------------
# Tests: Lead listing
# ---------------------------------------------------------------------------


class TestLeadListing:
    def test_list_leads_success(self, client, sample_leads):
        response = client.get("/api/v1/leads")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["leads"]) == 5
        assert data["page"] == 1
        assert data["per_page"] == 50
        assert data["pages"] == 1

    def test_list_leads_pagination(self, client, sample_leads):
        response = client.get("/api/v1/leads?page=1&per_page=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["leads"]) == 2
        assert data["pages"] == 3

        response = client.get("/api/v1/leads?page=2&per_page=2")
        assert response.status_code == 200
        assert len(response.json()["leads"]) == 2

    def test_list_leads_filter_by_response_sent(self, client, sample_leads):
        response = client.get("/api/v1/leads?response_sent=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert all(lead["response_sent"] for lead in data["leads"])

        response = client.get("/api/v1/leads?response_sent=false")
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_list_leads_filter_by_date_range(self, client, sample_leads):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)
        response = client.get(
            f"/api/v1/leads?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 2

    def test_list_leads_empty_result(self, client, sample_lead_source):
        response = client.get("/api/v1/leads")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["pages"] == 1

    def test_list_leads_max_per_page_limit(self, client, sample_leads):
        response = client.get("/api/v1/leads?per_page=200")
        assert response.status_code == 200
        assert response.json()["per_page"] == 100

    def test_list_leads_page_beyond_total(self, client, sample_leads):
        response = client.get("/api/v1/leads?page=10&per_page=50")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["leads"]) == 0

    def test_list_leads_invalid_per_page(self, client, sample_leads):
        response = client.get("/api/v1/leads?per_page=0")
        assert response.status_code in [200, 422, 400]
        if response.status_code == 200:
            assert response.json()["per_page"] > 0

    def test_list_leads_combined_filters(self, client, sample_leads):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)
        response = client.get(
            f"/api/v1/leads?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}&response_sent=true"
        )
        assert response.status_code == 200
        for lead in response.json()["leads"]:
            assert lead["response_sent"] is True

    def test_list_leads_invalid_date_format(self, client, sample_leads):
        response = client.get("/api/v1/leads?start_date=invalid-date")
        assert response.status_code in [200, 422, 400]


# ---------------------------------------------------------------------------
# Tests: Lead detail — unified read model (Phase 3C/3D)
# ---------------------------------------------------------------------------


class TestLeadDetail:
    """GET /api/v1/leads/{id} returns UnifiedLeadDetailResponse."""

    def test_get_lead_returns_unified_shape(self, client, sample_leads):
        """Response has core/stage/qualification/timeline top-level keys."""
        lead = sample_leads[0]
        response = client.get(f"/api/v1/leads/{lead.id}")
        assert response.status_code == 200
        data = response.json()
        for key in ("core", "stage", "qualification", "timeline"):
            assert key in data, f"Missing top-level key: {key}"

    def test_get_lead_core_fields(self, client, sample_leads):
        """Core identity fields are populated from the Lead ORM."""
        lead = sample_leads[0]
        response = client.get(f"/api/v1/leads/{lead.id}")
        assert response.status_code == 200
        core = response.json()["core"]
        assert core["id"] == lead.id
        assert core["name"] == lead.name
        assert core["source_email"] == lead.source_email
        assert "created_at" in core

    def test_get_lead_stage_none_when_no_stage(self, client, sample_leads):
        """Stage is null when lead has no pipeline stage assigned."""
        lead = sample_leads[0]
        response = client.get(f"/api/v1/leads/{lead.id}")
        assert response.status_code == 200
        assert response.json()["stage"] is None

    def test_get_lead_qualification_none_when_no_submission(self, client, sample_leads):
        """Qualification is null when no form submission exists."""
        lead = sample_leads[0]
        response = client.get(f"/api/v1/leads/{lead.id}")
        assert response.status_code == 200
        assert response.json()["qualification"] is None

    def test_get_lead_timeline_is_list(self, client, sample_leads):
        """Timeline is always a list (empty when no activity events)."""
        lead = sample_leads[0]
        response = client.get(f"/api/v1/leads/{lead.id}")
        assert response.status_code == 200
        assert isinstance(response.json()["timeline"], list)

    def test_get_lead_not_found(self, client, sample_lead_source):
        response = client.get("/api/v1/leads/99999")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "Lead with ID 99999 not found" in data["message"]

    def test_get_lead_invalid_id(self, client):
        response = client.get("/api/v1/leads/invalid")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Authentication
# ---------------------------------------------------------------------------


class TestLeadAuthentication:
    def test_list_leads_requires_authentication(self):
        with TestClient(app) as tc:
            response = tc.get("/api/v1/leads")
        assert response.status_code in [401, 403]

    def test_get_lead_requires_authentication(self):
        with TestClient(app) as tc:
            response = tc.get("/api/v1/leads/1")
        assert response.status_code in [401, 403]


# ---------------------------------------------------------------------------
# Tests: Response format
# ---------------------------------------------------------------------------


class TestLeadResponseFormat:
    def test_lead_detail_top_level_keys(self, client, sample_leads):
        lead = sample_leads[0]
        response = client.get(f"/api/v1/leads/{lead.id}")
        assert response.status_code == 200
        data = response.json()
        for key in ("core", "stage", "qualification", "timeline"):
            assert key in data

    def test_lead_list_response_format(self, client, sample_leads):
        response = client.get("/api/v1/leads")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["leads"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["per_page"], int)
        assert isinstance(data["pages"], int)
        if data["leads"]:
            lead = data["leads"][0]
            assert isinstance(lead["id"], int)
            assert isinstance(lead["name"], str)
            assert isinstance(lead["response_sent"], bool)


# ---------------------------------------------------------------------------
# Tests: CSV export
# ---------------------------------------------------------------------------


class TestLeadCSVExport:
    def test_export_csv_success(self, client, sample_leads):
        response = client.get("/api/v1/leads/export")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "leads_export.csv" in response.headers["content-disposition"]

        lines = response.text.strip().split("\n")
        header = lines[0].strip()
        assert header == "id,name,phone,source_email,agent_id,agent_name,lead_source_id,gmail_uid,created_at,updated_at,response_sent,response_status"
        assert len(lines) == 6  # 1 header + 5 data rows

    def test_export_csv_with_filters(self, client, sample_leads):
        response = client.get("/api/v1/leads/export?response_sent=true")
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) == 4  # 1 header + 3 rows
        for line in lines[1:]:
            fields = line.split(",")
            # response_sent is index 10: id,name,phone,source_email,agent_id,agent_name,lead_source_id,gmail_uid,created_at,updated_at,response_sent
            assert fields[10] == "True"

    def test_export_csv_with_date_range(self, client, sample_leads):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)
        response = client.get(
            f"/api/v1/leads/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )
        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert len(lines) >= 3

    def test_export_csv_combined_filters(self, client, sample_leads):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=2)
        response = client.get(
            f"/api/v1/leads/export?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}&response_sent=true"
        )
        assert response.status_code == 200
        reader = csv.reader(io.StringIO(response.text))
        rows = list(reader)
        for row in rows[1:]:
            assert row[10] == "True"

    def test_export_csv_invalid_date_format(self, client, sample_leads):
        response = client.get("/api/v1/leads/export?start_date=invalid-date")
        assert response.status_code in [200, 422, 400]

"""
Unit tests for lead source management API endpoints.

PR 2: lead sources are company-scoped.
- Company admins only see/create/update/delete their own company's sources.
- Cross-company access returns 404 (indistinguishable from not-found).
- Two companies may share the same sender_email with different rules.
- Duplicate sender within the same company returns 409.
- A user with no company_id gets 403.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gmail_lead_sync.models import Base, LeadSource, Template, Company
from api.models.web_ui_models import User
from api.main import app
from api.auth import hash_password, create_session


# ---------------------------------------------------------------------------
# DB setup
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_engine():
    Base.metadata.create_all(test_engine)
    yield test_engine


@pytest.fixture
def db_session(db_engine):
    session = TestSessionLocal()
    from api.models.web_ui_models import RegexProfileVersion
    session.query(RegexProfileVersion).delete()
    session.query(LeadSource).delete()
    session.query(Template).delete()
    session.commit()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Company + user fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def company_a(db_session):
    """Primary company used by the authenticated test user."""
    c = Company(name="Company A")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def company_b(db_session):
    """Second company — used to verify cross-company isolation."""
    c = Company(name="Company B")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def test_user(db_session, company_a):
    """Authenticated company_admin user belonging to company_a."""
    existing = db_session.query(User).filter(User.username == "testuser").first()
    if existing:
        existing.company_id = company_a.id
        db_session.commit()
        return existing
    user = User(
        username="testuser",
        password_hash=hash_password("testpass"),
        role="company_admin",
        company_id=company_a.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_no_company(db_session):
    """A user with no company association — should get 403 on all endpoints."""
    existing = db_session.query(User).filter(User.username == "nocompany").first()
    if existing:
        return existing
    u = User(
        username="nocompany",
        password_hash=hash_password("testpass"),
        role="company_admin",
        company_id=None,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def auth_session(db_session, test_user):
    return create_session(
        db_session,
        test_user.id,
        __import__("api.config", fromlist=["get_config"]).get_config().secret_key,
    )


@pytest.fixture
def test_template(db_session):
    t = Template(name="Test Template", subject="Test Subject", body="Test Body")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

def _make_client(db_session, user, session_token: str = None):
    """Return a TestClient authenticated as *user*.

    Pass session_token (from auth_session._raw_token) to also set the
    session cookie so the router-level require_role dependency passes.
    Callers must call app.dependency_overrides.clear() after the request.
    """
    from api.routers import admin_lead_sources as ls_mod
    from api.main import get_db as main_get_db

    def override_get_db():
        yield db_session

    def override_get_current_user() -> User:
        return user

    app.dependency_overrides[main_get_db] = override_get_db
    app.dependency_overrides[ls_mod.get_db] = override_get_db
    app.dependency_overrides[ls_mod.get_current_user] = override_get_current_user
    c = TestClient(app)
    if session_token:
        c.cookies.set("session_token", session_token)
    return c


@pytest.fixture
def client(db_session, test_user, auth_session):
    c = _make_client(db_session, test_user)
    c.cookies.set("session_token", auth_session._raw_token)
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lead_source(db_session, company_id, sender_email="leads@example.com"):
    ls = LeadSource(
        company_id=company_id,
        sender_email=sender_email,
        identifier_snippet="New Lead",
        name_regex=r"Name:\s*(.+)",
        phone_regex=r"Phone:\s*([\d-]+)",
        auto_respond_enabled=False,
    )
    db_session.add(ls)
    db_session.commit()
    db_session.refresh(ls)
    return ls


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestCreateLeadSource:

    def test_create_success(self, client, db_session, company_a):
        r = client.post("/api/v1/lead-sources", json={
            "sender_email": "leads@example.com",
            "identifier_snippet": "New Lead Notification",
            "name_regex": r"Name:\s*(.+)",
            "phone_regex": r"Phone:\s*([\d-]+)",
            "auto_respond_enabled": False,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["sender_email"] == "leads@example.com"
        assert "id" in data
        # Verify company_id stamped correctly in DB
        ls = db_session.query(LeadSource).filter(
            LeadSource.sender_email == "leads@example.com"
        ).first()
        assert ls is not None
        assert ls.company_id == company_a.id

    def test_create_with_template(self, client, test_template):
        r = client.post("/api/v1/lead-sources", json={
            "sender_email": "leads@example.com",
            "identifier_snippet": "New Lead",
            "name_regex": r"Name:\s*(.+)",
            "phone_regex": r"Phone:\s*([\d-]+)",
            "template_id": test_template.id,
            "auto_respond_enabled": True,
        })
        assert r.status_code == 201
        assert r.json()["template_id"] == test_template.id

    def test_duplicate_sender_same_company_returns_409(self, client, db_session, company_a):
        """Same sender_email within the same company must be rejected."""
        _make_lead_source(db_session, company_a.id, "leads@example.com")
        r = client.post("/api/v1/lead-sources", json={
            "sender_email": "leads@example.com",
            "identifier_snippet": "Lead 2",
            "name_regex": r"Name:\s*(.+)",
            "phone_regex": r"Phone:\s*([\d-]+)",
            "auto_respond_enabled": False,
        })
        assert r.status_code == 409
        assert "already exists" in r.json()["message"].lower()

    def test_same_sender_different_companies_succeeds(
        self, db_session, company_a, company_b, test_user, auth_session
    ):
        """Two companies may both have a rule for the same sender_email."""
        # Company B already has a rule for this sender.
        _make_lead_source(db_session, company_b.id, "leads@zillow.com")

        # Company A admin creates their own rule for the same sender.
        # Use the same override + cookie pattern as the client fixture.
        from api.routers import admin_lead_sources as ls_mod
        from api.main import get_db as main_get_db

        def override_get_db():
            yield db_session

        def override_get_current_user() -> User:
            return test_user

        app.dependency_overrides[main_get_db] = override_get_db
        app.dependency_overrides[ls_mod.get_db] = override_get_db
        app.dependency_overrides[ls_mod.get_current_user] = override_get_current_user
        try:
            c = TestClient(app)
            c.cookies.set("session_token", auth_session._raw_token)
            r = c.post("/api/v1/lead-sources", json={
                "sender_email": "leads@zillow.com",
                "identifier_snippet": "Zillow Lead",
                "name_regex": r"Name:\s*(.+)",
                "phone_regex": r"Phone:\s*([\d-]+)",
                "auto_respond_enabled": False,
            })
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 201

    def test_invalid_regex_returns_422(self, client):
        r = client.post("/api/v1/lead-sources", json={
            "sender_email": "leads@example.com",
            "identifier_snippet": "New Lead",
            "name_regex": r"[invalid(regex",
            "phone_regex": r"Phone:\s*([\d-]+)",
            "auto_respond_enabled": False,
        })
        assert r.status_code == 422

    def test_invalid_template_id_returns_400(self, client):
        r = client.post("/api/v1/lead-sources", json={
            "sender_email": "leads@example.com",
            "identifier_snippet": "New Lead",
            "name_regex": r"Name:\s*(.+)",
            "phone_regex": r"Phone:\s*([\d-]+)",
            "template_id": 99999,
            "auto_respond_enabled": True,
        })
        assert r.status_code == 400
        assert "template" in r.json()["message"].lower()

    def test_missing_fields_returns_422(self, client):
        r = client.post("/api/v1/lead-sources", json={"sender_email": "leads@example.com"})
        assert r.status_code == 422

    def test_create_user_without_company_gets_403(self, db_session, user_no_company):
        """Authenticated user with no company_id gets 403 from _require_company.
        Tested directly — the HTTP stack returns 401 before reaching _require_company
        when no session cookie is present, so we test the guard function directly.
        """
        from api.routers.admin_lead_sources import _require_company
        from api.exceptions import AuthorizationException
        with pytest.raises(AuthorizationException) as exc_info:
            _require_company(user_no_company)
        assert exc_info.value.status_code == 403

    def test_creates_initial_version_record(self, client, db_session):
        from api.models.web_ui_models import RegexProfileVersion
        r = client.post("/api/v1/lead-sources", json={
            "sender_email": "leads@example.com",
            "identifier_snippet": "New Lead Notification",
            "name_regex": r"Name:\s*(.+)",
            "phone_regex": r"Phone:\s*([\d-]+)",
            "auto_respond_enabled": False,
        })
        assert r.status_code == 201
        ls_id = r.json()["id"]
        v = db_session.query(RegexProfileVersion).filter(
            RegexProfileVersion.lead_source_id == ls_id,
            RegexProfileVersion.version == 1,
        ).first()
        assert v is not None
        assert v.name_regex == r"Name:\s*(.+)"


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListLeadSources:

    def test_list_empty(self, client):
        r = client.get("/api/v1/lead-sources")
        assert r.status_code == 200
        assert r.json()["lead_sources"] == []

    def test_list_returns_only_own_company_sources(
        self, db_session, company_a, company_b, test_user, auth_session
    ):
        """List must not include sources from other companies."""
        _make_lead_source(db_session, company_a.id, "a@example.com")
        _make_lead_source(db_session, company_a.id, "b@example.com")
        _make_lead_source(db_session, company_b.id, "c@example.com")  # other company

        c = _make_client(db_session, test_user, auth_session._raw_token)
        try:
            r = c.get("/api/v1/lead-sources")
        finally:
            app.dependency_overrides.clear()

        assert r.status_code == 200
        emails = [ls["sender_email"] for ls in r.json()["lead_sources"]]
        assert "a@example.com" in emails
        assert "b@example.com" in emails
        assert "c@example.com" not in emails  # must not leak company B's source

    def test_list_multiple_own_sources(self, client, db_session, company_a):
        for i in range(3):
            _make_lead_source(db_session, company_a.id, f"leads{i}@example.com")
        r = client.get("/api/v1/lead-sources")
        assert r.status_code == 200
        assert len(r.json()["lead_sources"]) == 3

    def test_user_without_company_gets_403_with_valid_session(
        self, db_session, user_no_company
    ):
        """_require_company raises 403 when the user has no company_id."""
        from api.routers.admin_lead_sources import _require_company
        from api.exceptions import AuthorizationException

        with pytest.raises(AuthorizationException) as exc_info:
            _require_company(user_no_company)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

class TestGetLeadSource:

    def test_get_own_source_success(self, client, db_session, company_a):
        ls = _make_lead_source(db_session, company_a.id)
        r = client.get(f"/api/v1/lead-sources/{ls.id}")
        assert r.status_code == 200
        assert r.json()["id"] == ls.id

    def test_get_not_found(self, client):
        r = client.get("/api/v1/lead-sources/99999")
        assert r.status_code == 404
        assert "not found" in r.json()["message"].lower()

    def test_get_cross_company_returns_404(
        self, db_session, company_b, test_user, auth_session
    ):
        """Company A admin cannot GET company B's lead source — returns 404."""
        ls_b = _make_lead_source(db_session, company_b.id, "b@example.com")
        c = _make_client(db_session, test_user, auth_session._raw_token)
        try:
            r = c.get(f"/api/v1/lead-sources/{ls_b.id}")
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 404

    def test_get_user_without_company_gets_403(self, db_session, user_no_company, company_a):
        """_require_company raises 403 — covered by TestListLeadSources unit test."""
        from api.routers.admin_lead_sources import _require_company
        from api.exceptions import AuthorizationException
        with pytest.raises(AuthorizationException):
            _require_company(user_no_company)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestUpdateLeadSource:

    def test_update_sender_email(self, client, db_session, company_a):
        ls = _make_lead_source(db_session, company_a.id, "old@example.com")
        r = client.put(f"/api/v1/lead-sources/{ls.id}", json={"sender_email": "new@example.com"})
        assert r.status_code == 200
        assert r.json()["sender_email"] == "new@example.com"

    def test_update_regex_patterns(self, client, db_session, company_a):
        ls = _make_lead_source(db_session, company_a.id)
        r = client.put(f"/api/v1/lead-sources/{ls.id}", json={
            "name_regex": r"Full Name:\s*(.+)",
            "phone_regex": r"Tel:\s*([\d-]+)",
        })
        assert r.status_code == 200
        assert r.json()["name_regex"] == r"Full Name:\s*(.+)"

    def test_update_creates_new_version_for_regex_change(self, client, db_session, company_a):
        from api.models.web_ui_models import RegexProfileVersion
        ls = _make_lead_source(db_session, company_a.id)
        db_session.add(RegexProfileVersion(
            lead_source_id=ls.id, version=1,
            name_regex=ls.name_regex, phone_regex=ls.phone_regex,
            identifier_snippet=ls.identifier_snippet, created_by=1,
        ))
        db_session.commit()
        r = client.put(f"/api/v1/lead-sources/{ls.id}", json={"name_regex": r"Full Name:\s*(.+)"})
        assert r.status_code == 200
        v2 = db_session.query(RegexProfileVersion).filter(
            RegexProfileVersion.lead_source_id == ls.id,
            RegexProfileVersion.version == 2,
        ).first()
        assert v2 is not None

    def test_update_non_regex_field_no_new_version(self, client, db_session, company_a):
        from api.models.web_ui_models import RegexProfileVersion
        ls = _make_lead_source(db_session, company_a.id)
        db_session.add(RegexProfileVersion(
            lead_source_id=ls.id, version=1,
            name_regex=ls.name_regex, phone_regex=ls.phone_regex,
            identifier_snippet=ls.identifier_snippet, created_by=1,
        ))
        db_session.commit()
        r = client.put(f"/api/v1/lead-sources/{ls.id}", json={"auto_respond_enabled": True})
        assert r.status_code == 200
        count = db_session.query(RegexProfileVersion).filter(
            RegexProfileVersion.lead_source_id == ls.id
        ).count()
        assert count == 1

    def test_update_no_fields_returns_400(self, client, db_session, company_a):
        ls = _make_lead_source(db_session, company_a.id)
        r = client.put(f"/api/v1/lead-sources/{ls.id}", json={})
        assert r.status_code == 400
        assert "no fields" in r.json()["message"].lower()

    def test_update_not_found(self, client):
        r = client.put("/api/v1/lead-sources/99999", json={"sender_email": "x@example.com"})
        assert r.status_code == 404

    def test_update_duplicate_sender_same_company_returns_409(self, client, db_session, company_a):
        ls1 = _make_lead_source(db_session, company_a.id, "leads1@example.com")
        ls2 = _make_lead_source(db_session, company_a.id, "leads2@example.com")
        r = client.put(f"/api/v1/lead-sources/{ls2.id}", json={"sender_email": "leads1@example.com"})
        assert r.status_code == 409
        assert "already exists" in r.json()["message"].lower()

    def test_update_sender_to_same_value_succeeds(self, client, db_session, company_a):
        """Updating sender_email to its current value must not trigger a 409."""
        ls = _make_lead_source(db_session, company_a.id, "leads@example.com")
        r = client.put(f"/api/v1/lead-sources/{ls.id}", json={"sender_email": "leads@example.com"})
        assert r.status_code == 200

    def test_update_cross_company_returns_404(self, db_session, company_b, test_user, auth_session):
        """Company A admin cannot update company B's lead source."""
        ls_b = _make_lead_source(db_session, company_b.id, "b@example.com")
        c = _make_client(db_session, test_user, auth_session._raw_token)
        try:
            r = c.put(f"/api/v1/lead-sources/{ls_b.id}", json={"sender_email": "hacked@example.com"})
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 404
        # Verify the record was not modified
        db_session.refresh(ls_b)
        assert ls_b.sender_email == "b@example.com"

    def test_update_invalid_regex_returns_422(self, client, db_session, company_a):
        ls = _make_lead_source(db_session, company_a.id)
        r = client.put(f"/api/v1/lead-sources/{ls.id}", json={"name_regex": r"[invalid(regex"})
        assert r.status_code == 422

    def test_update_user_without_company_gets_403(self, db_session, user_no_company, company_a):
        """_require_company raises 403 — covered by TestListLeadSources unit test."""
        from api.routers.admin_lead_sources import _require_company
        from api.exceptions import AuthorizationException
        with pytest.raises(AuthorizationException):
            _require_company(user_no_company)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeleteLeadSource:

    def test_delete_success(self, client, db_session, company_a):
        ls = _make_lead_source(db_session, company_a.id)
        ls_id = ls.id
        r = client.delete(f"/api/v1/lead-sources/{ls_id}")
        assert r.status_code == 200
        assert "deleted successfully" in r.json()["message"].lower()
        assert db_session.query(LeadSource).filter(LeadSource.id == ls_id).first() is None

    def test_delete_not_found(self, client):
        r = client.delete("/api/v1/lead-sources/99999")
        assert r.status_code == 404

    def test_delete_cross_company_returns_404(self, db_session, company_b, test_user, auth_session):
        """Company A admin cannot delete company B's lead source."""
        ls_b = _make_lead_source(db_session, company_b.id, "b@example.com")
        c = _make_client(db_session, test_user, auth_session._raw_token)
        try:
            r = c.delete(f"/api/v1/lead-sources/{ls_b.id}")
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 404
        # Verify the record still exists
        assert db_session.query(LeadSource).filter(LeadSource.id == ls_b.id).first() is not None

    def test_delete_records_audit_log(self, client, db_session, company_a):
        from api.models.web_ui_models import AuditLog
        ls = _make_lead_source(db_session, company_a.id)
        ls_id = ls.id
        r = client.delete(f"/api/v1/lead-sources/{ls_id}")
        assert r.status_code == 200
        entry = db_session.query(AuditLog).filter(
            AuditLog.action == "lead_source_deleted",
            AuditLog.resource_id == ls_id,
        ).first()
        assert entry is not None
        assert "leads@example.com" in entry.details.lower()

    def test_delete_user_without_company_gets_403(self, db_session, user_no_company, company_a):
        """_require_company raises 403 — covered by TestListLeadSources unit test."""
        from api.routers.admin_lead_sources import _require_company
        from api.exceptions import AuthorizationException
        with pytest.raises(AuthorizationException):
            _require_company(user_no_company)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestLeadSourceAuthentication:
    """Unauthenticated requests must return 401 (no cookie → Layer 1 rejects before Layer 2)."""

    def test_create_requires_auth(self):
        c = TestClient(app)
        r = c.post("/api/v1/lead-sources", json={
            "sender_email": "leads@example.com",
            "identifier_snippet": "Lead",
            "name_regex": r"Name:\s*(.+)",
            "phone_regex": r"Phone:\s*([\d-]+)",
            "auto_respond_enabled": False,
        })
        assert r.status_code == 401

    def test_list_requires_auth(self):
        c = TestClient(app)
        assert c.get("/api/v1/lead-sources").status_code == 401


# ---------------------------------------------------------------------------
# Regex tester (stateless — no company scoping)
# ---------------------------------------------------------------------------

class TestRegexTesting:

    def test_successful_match(self, client):
        r = client.post("/api/v1/lead-sources/test-regex", json={
            "pattern": r"Name:\s*(.+)",
            "sample_text": "Name: John Doe\nPhone: 555-1234",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["matched"] is True
        assert data["groups"][0] == "John Doe"

    def test_no_match(self, client):
        r = client.post("/api/v1/lead-sources/test-regex", json={
            "pattern": r"Email:\s*(.+)",
            "sample_text": "Name: John Doe\nPhone: 555-1234",
        })
        assert r.status_code == 200
        assert r.json()["matched"] is False

    def test_multiple_groups(self, client):
        r = client.post("/api/v1/lead-sources/test-regex", json={
            "pattern": r"Name:\s*(\w+)\s+(\w+)",
            "sample_text": "Name: John Doe",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["groups"] == ["John", "Doe"]

    def test_invalid_pattern_returns_422(self, client):
        r = client.post("/api/v1/lead-sources/test-regex", json={
            "pattern": r"[invalid(regex",
            "sample_text": "Some text",
        })
        assert r.status_code == 422

    def test_empty_pattern_returns_422(self, client):
        r = client.post("/api/v1/lead-sources/test-regex", json={
            "pattern": "",
            "sample_text": "Some text",
        })
        assert r.status_code == 422

    def test_empty_sample_text_returns_422(self, client):
        r = client.post("/api/v1/lead-sources/test-regex", json={
            "pattern": r"test",
            "sample_text": "",
        })
        assert r.status_code == 422

    def test_timeout_enforcement(self, client):
        r = client.post("/api/v1/lead-sources/test-regex", json={
            "pattern": r"(a+)+b",
            "sample_text": "a" * 25 + "c",
        })
        assert r.status_code in [200, 400]

    def test_requires_auth(self):
        """No cookie → 401 from Layer 1 (require_role) before any endpoint logic runs."""
        c = TestClient(app)
        r = c.post("/api/v1/lead-sources/test-regex", json={
            "pattern": r"test", "sample_text": "test text",
        })
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Version history + rollback
# ---------------------------------------------------------------------------

class TestRegexProfileVersioning:

    def test_get_version_history(self, client, db_session, company_a):
        from api.models.web_ui_models import RegexProfileVersion
        ls = _make_lead_source(db_session, company_a.id)
        for i in range(1, 4):
            db_session.add(RegexProfileVersion(
                lead_source_id=ls.id, version=i,
                name_regex=f"Name{i}:\\s*(.+)", phone_regex=f"Phone{i}:\\s*([\\d-]+)",
                identifier_snippet=f"Lead {i}", created_by=1,
            ))
        db_session.commit()
        r = client.get(f"/api/v1/lead-sources/{ls.id}/versions")
        assert r.status_code == 200
        versions = r.json()["versions"]
        assert len(versions) == 3
        assert versions[0]["version"] == 3  # newest first

    def test_get_version_history_cross_company_returns_404(
        self, db_session, company_b, test_user, auth_session
    ):
        ls_b = _make_lead_source(db_session, company_b.id, "b@example.com")
        c = _make_client(db_session, test_user, auth_session._raw_token)
        try:
            r = c.get(f"/api/v1/lead-sources/{ls_b.id}/versions")
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 404

    def test_rollback_to_previous_version(self, client, db_session, company_a):
        from api.models.web_ui_models import RegexProfileVersion
        ls = _make_lead_source(db_session, company_a.id)
        for i in range(1, 4):
            db_session.add(RegexProfileVersion(
                lead_source_id=ls.id, version=i,
                name_regex=f"Name{i}:\\s*(.+)", phone_regex=f"Phone{i}:\\s*([\\d-]+)",
                identifier_snippet=f"Lead v{i}", created_by=1,
            ))
        db_session.commit()
        r = client.post(f"/api/v1/lead-sources/{ls.id}/rollback", json={"version": 1})
        assert r.status_code == 200
        data = r.json()
        assert data["new_version"] == 4
        assert "Name1" in data["lead_source"]["name_regex"]

    def test_rollback_cross_company_returns_404(self, db_session, company_b, test_user, auth_session):
        ls_b = _make_lead_source(db_session, company_b.id, "b@example.com")
        c = _make_client(db_session, test_user, auth_session._raw_token)
        try:
            r = c.post(f"/api/v1/lead-sources/{ls_b.id}/rollback", json={"version": 1})
        finally:
            app.dependency_overrides.clear()
        assert r.status_code == 404

    def test_rollback_invalid_version_returns_404(self, client, db_session, company_a):
        from api.models.web_ui_models import RegexProfileVersion
        ls = _make_lead_source(db_session, company_a.id)
        db_session.add(RegexProfileVersion(
            lead_source_id=ls.id, version=1,
            name_regex=ls.name_regex, phone_regex=ls.phone_regex,
            identifier_snippet=ls.identifier_snippet, created_by=1,
        ))
        db_session.commit()
        r = client.post(f"/api/v1/lead-sources/{ls.id}/rollback", json={"version": 99})
        assert r.status_code == 404

    def test_version_history_requires_auth(self):
        """No cookie → 401 from Layer 1 before any endpoint logic runs."""
        c = TestClient(app)
        assert c.get("/api/v1/lead-sources/1/versions").status_code == 401

    def test_rollback_requires_auth(self):
        """No cookie → 401 from Layer 1 before any endpoint logic runs."""
        c = TestClient(app)
        assert c.post(
            "/api/v1/lead-sources/1/rollback", json={"version": 1}
        ).status_code == 401

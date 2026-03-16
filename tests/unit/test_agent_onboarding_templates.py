"""
Unit tests for PUT /api/v1/agent/onboarding/templates.

Requirements: 8.4, 8.5
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from api.routers.agent_auth import AGENT_SESSION_COOKIE_NAME
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import AgentTemplate, AgentUser
from gmail_lead_sync.models import Base

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

TEMPLATES_URL = "/api/v1/agent/onboarding/templates"
SIGNUP_URL = "/api/v1/agent/auth/signup"

VALID_TEMPLATE = {
    "template_type": "INITIAL_INVITE",
    "subject": "Hi {lead_name}, let's connect!",
    "body": "Hello {lead_name}, I'm {agent_name}. Call me at {agent_phone}.",
    "tone": "PROFESSIONAL",
}

ALL_FOUR_TEMPLATES = [
    {
        "template_type": "INITIAL_INVITE",
        "subject": "Hi {lead_name}",
        "body": "From {agent_name}",
        "tone": "PROFESSIONAL",
    },
    {
        "template_type": "POST_HOT",
        "subject": "Follow up for {lead_name}",
        "body": "Contact {agent_email}",
        "tone": "FRIENDLY",
    },
    {
        "template_type": "POST_WARM",
        "subject": "Checking in",
        "body": "Fill out {form_link}",
        "tone": "SHORT",
    },
    {
        "template_type": "POST_NURTURE",
        "subject": "Staying in touch",
        "body": "Call {agent_phone}",
        "tone": "PROFESSIONAL",
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def authenticated_client(client):
    resp = client.post(
        SIGNUP_URL,
        json={"email": "agent@example.com", "password": "securepass123", "full_name": "Test Agent"},
    )
    assert resp.status_code == 201
    token = resp.cookies[AGENT_SESSION_COOKIE_NAME]
    client.cookies.set(AGENT_SESSION_COOKIE_NAME, token)
    return client


@pytest.fixture
def agent_id(authenticated_client):
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter_by(email="agent@example.com").first()
    aid = agent.id
    db.close()
    return aid


# ---------------------------------------------------------------------------
# 1. Authentication guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_returns_401(self, client):
        resp = client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Success path (Requirement 8.4)
# ---------------------------------------------------------------------------

class TestTemplatesSuccess:
    def test_returns_200(self, authenticated_client):
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})
        assert resp.status_code == 200

    def test_response_body(self, authenticated_client):
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})
        data = resp.json()
        assert data["ok"] is True
        assert data["onboarding_step"] == 6

    def test_template_persisted(self, authenticated_client, agent_id):
        authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})

        db = TestingSessionLocal()
        tmpl = (
            db.query(AgentTemplate)
            .filter_by(agent_user_id=agent_id, template_type="INITIAL_INVITE")
            .first()
        )
        db.close()

        assert tmpl is not None
        assert tmpl.subject == VALID_TEMPLATE["subject"]
        assert tmpl.body == VALID_TEMPLATE["body"]
        assert tmpl.tone == "PROFESSIONAL"
        assert tmpl.is_active is True
        assert tmpl.version == 1

    def test_all_four_templates_persisted(self, authenticated_client, agent_id):
        authenticated_client.put(TEMPLATES_URL, json={"templates": ALL_FOUR_TEMPLATES})

        db = TestingSessionLocal()
        templates = db.query(AgentTemplate).filter_by(agent_user_id=agent_id).all()
        db.close()

        assert len(templates) == 4
        types = {t.template_type for t in templates}
        assert types == {"INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"}

    def test_onboarding_step_advanced_to_6(self, authenticated_client, agent_id):
        authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        db.close()

        assert agent.onboarding_step == 6

    def test_onboarding_step_not_regressed(self, authenticated_client, agent_id):
        """If step is already > 6, it should not be reduced."""
        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        agent.onboarding_step = 7
        db.commit()
        db.close()

        authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        db.close()
        assert agent.onboarding_step == 7

    def test_empty_templates_list_advances_step(self, authenticated_client, agent_id):
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": []})
        assert resp.status_code == 200
        assert resp.json()["onboarding_step"] == 6


# ---------------------------------------------------------------------------
# 3. Upsert behaviour — version increments on update (Requirement 8.4)
# ---------------------------------------------------------------------------

class TestTemplatesUpsert:
    def test_second_call_updates_not_duplicates(self, authenticated_client, agent_id):
        authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})
        updated = {**VALID_TEMPLATE, "subject": "Updated subject"}
        authenticated_client.put(TEMPLATES_URL, json={"templates": [updated]})

        db = TestingSessionLocal()
        templates = (
            db.query(AgentTemplate)
            .filter_by(agent_user_id=agent_id, template_type="INITIAL_INVITE")
            .all()
        )
        db.close()

        assert len(templates) == 1
        assert templates[0].subject == "Updated subject"

    def test_version_increments_on_update(self, authenticated_client, agent_id):
        authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})
        authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})

        db = TestingSessionLocal()
        tmpl = (
            db.query(AgentTemplate)
            .filter_by(agent_user_id=agent_id, template_type="INITIAL_INVITE")
            .first()
        )
        db.close()

        assert tmpl.version == 2

    def test_version_starts_at_1_on_create(self, authenticated_client, agent_id):
        authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})

        db = TestingSessionLocal()
        tmpl = (
            db.query(AgentTemplate)
            .filter_by(agent_user_id=agent_id, template_type="INITIAL_INVITE")
            .first()
        )
        db.close()

        assert tmpl.version == 1

    def test_tone_updated_on_second_call(self, authenticated_client, agent_id):
        authenticated_client.put(TEMPLATES_URL, json={"templates": [VALID_TEMPLATE]})
        updated = {**VALID_TEMPLATE, "tone": "FRIENDLY"}
        authenticated_client.put(TEMPLATES_URL, json={"templates": [updated]})

        db = TestingSessionLocal()
        tmpl = (
            db.query(AgentTemplate)
            .filter_by(agent_user_id=agent_id, template_type="INITIAL_INVITE")
            .first()
        )
        db.close()

        assert tmpl.tone == "FRIENDLY"


# ---------------------------------------------------------------------------
# 4. Placeholder validation (Requirement 8.5)
# ---------------------------------------------------------------------------

class TestPlaceholderValidation:
    def test_unsupported_placeholder_in_subject_returns_422(self, authenticated_client):
        bad = {**VALID_TEMPLATE, "subject": "Hi {unknown_field}"}
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})
        assert resp.status_code == 422

    def test_unsupported_placeholder_error_code(self, authenticated_client):
        bad = {**VALID_TEMPLATE, "subject": "Hi {unknown_field}"}
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})
        assert resp.json()["error"] == "INVALID_PLACEHOLDER"

    def test_unsupported_placeholder_in_body_returns_422(self, authenticated_client):
        bad = {**VALID_TEMPLATE, "body": "Call {bad_placeholder} now"}
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})
        assert resp.status_code == 422

    def test_detail_mentions_invalid_placeholder(self, authenticated_client):
        bad = {**VALID_TEMPLATE, "subject": "Hi {mystery_field}"}
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})
        assert "mystery_field" in resp.json()["detail"]

    def test_all_supported_placeholders_accepted(self, authenticated_client):
        tmpl = {
            "template_type": "INITIAL_INVITE",
            "subject": "{lead_name} from {agent_name}",
            "body": "Phone: {agent_phone}, Email: {agent_email}, Form: {form_link}",
            "tone": "PROFESSIONAL",
        }
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [tmpl]})
        assert resp.status_code == 200

    def test_no_placeholders_accepted(self, authenticated_client):
        tmpl = {
            "template_type": "INITIAL_INVITE",
            "subject": "Hello there",
            "body": "Plain text body with no placeholders.",
            "tone": "SHORT",
        }
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [tmpl]})
        assert resp.status_code == 200

    def test_invalid_placeholder_in_second_template_returns_422(self, authenticated_client):
        """Validation should catch bad placeholders in any template, not just the first."""
        templates = [
            VALID_TEMPLATE,
            {**VALID_TEMPLATE, "template_type": "POST_HOT", "body": "See {bad_field}"},
        ]
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": templates})
        assert resp.status_code == 422
        assert resp.json()["error"] == "INVALID_PLACEHOLDER"

    def test_no_db_writes_on_validation_failure(self, authenticated_client, agent_id):
        """On 422, no templates should be persisted."""
        bad = {**VALID_TEMPLATE, "subject": "Hi {unknown_field}"}
        authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})

        db = TestingSessionLocal()
        count = db.query(AgentTemplate).filter_by(agent_user_id=agent_id).count()
        db.close()

        assert count == 0


# ---------------------------------------------------------------------------
# 5. Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_invalid_template_type_returns_422(self, authenticated_client):
        bad = {**VALID_TEMPLATE, "template_type": "UNKNOWN_TYPE"}
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})
        assert resp.status_code == 422

    def test_invalid_tone_returns_422(self, authenticated_client):
        bad = {**VALID_TEMPLATE, "tone": "CASUAL"}
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})
        assert resp.status_code == 422

    def test_empty_subject_returns_422(self, authenticated_client):
        bad = {**VALID_TEMPLATE, "subject": ""}
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})
        assert resp.status_code == 422

    def test_empty_body_returns_422(self, authenticated_client):
        bad = {**VALID_TEMPLATE, "body": ""}
        resp = authenticated_client.put(TEMPLATES_URL, json={"templates": [bad]})
        assert resp.status_code == 422

"""
Unit tests for PUT /api/v1/agent/onboarding/automation.

Requirements: 7.1
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from api.routers.agent_auth import AGENT_SESSION_COOKIE_NAME
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import AgentPreferences, AgentUser, BuyerAutomationConfig
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

AUTOMATION_URL = "/api/v1/agent/onboarding/automation"
SIGNUP_URL = "/api/v1/agent/auth/signup"

VALID_PAYLOAD = {
    "hot_threshold": 80,
    "warm_threshold": 50,
    "sla_minutes_hot": 15,
    "enable_tour_question": True,
    "working_hours_start": "08:00",
    "working_hours_end": "20:00",
}


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
        resp = client.put(AUTOMATION_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Success path (Requirement 7.1)
# ---------------------------------------------------------------------------

class TestAutomationSuccess:
    def test_returns_200(self, authenticated_client):
        resp = authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 200

    def test_response_body(self, authenticated_client):
        resp = authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)
        data = resp.json()
        assert data["ok"] is True
        assert data["onboarding_step"] == 5

    def test_buyer_automation_config_created(self, authenticated_client, agent_id):
        authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)

        db = TestingSessionLocal()
        config = db.query(BuyerAutomationConfig).filter_by(agent_user_id=agent_id).first()
        db.close()

        assert config is not None
        assert config.hot_threshold == 80
        assert config.warm_threshold == 50
        assert config.enable_tour_question is True

    def test_agent_preferences_created_with_sla(self, authenticated_client, agent_id):
        authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)

        db = TestingSessionLocal()
        prefs = db.query(AgentPreferences).filter_by(agent_user_id=agent_id).first()
        db.close()

        assert prefs is not None
        assert prefs.sla_minutes_hot == 15
        assert prefs.enable_tour_question is True

    def test_preferences_linked_to_config(self, authenticated_client, agent_id):
        authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)

        db = TestingSessionLocal()
        prefs = db.query(AgentPreferences).filter_by(agent_user_id=agent_id).first()
        config = db.query(BuyerAutomationConfig).filter_by(agent_user_id=agent_id).first()
        db.close()

        assert prefs.buyer_automation_config_id == config.id

    def test_working_hours_persisted(self, authenticated_client, agent_id):
        authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)

        db = TestingSessionLocal()
        prefs = db.query(AgentPreferences).filter_by(agent_user_id=agent_id).first()
        db.close()

        assert prefs.quiet_hours_start is not None
        assert prefs.quiet_hours_end is not None
        assert prefs.quiet_hours_start.hour == 8
        assert prefs.quiet_hours_end.hour == 20

    def test_onboarding_step_advanced_to_5(self, authenticated_client, agent_id):
        authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        db.close()

        assert agent.onboarding_step == 5

    def test_onboarding_step_not_regressed(self, authenticated_client, agent_id):
        """If step is already > 5, it should not be reduced."""
        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        agent.onboarding_step = 6
        db.commit()
        db.close()

        authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        db.close()
        assert agent.onboarding_step == 6


# ---------------------------------------------------------------------------
# 3. Idempotency — second call updates existing records
# ---------------------------------------------------------------------------

class TestAutomationIdempotency:
    def test_second_call_updates_config(self, authenticated_client, agent_id):
        authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)
        authenticated_client.put(AUTOMATION_URL, json={**VALID_PAYLOAD, "hot_threshold": 90})

        db = TestingSessionLocal()
        configs = db.query(BuyerAutomationConfig).filter_by(agent_user_id=agent_id).all()
        db.close()

        assert len(configs) == 1
        assert configs[0].hot_threshold == 90

    def test_second_call_updates_preferences(self, authenticated_client, agent_id):
        authenticated_client.put(AUTOMATION_URL, json=VALID_PAYLOAD)
        authenticated_client.put(AUTOMATION_URL, json={**VALID_PAYLOAD, "sla_minutes_hot": 60})

        db = TestingSessionLocal()
        prefs_list = db.query(AgentPreferences).filter_by(agent_user_id=agent_id).all()
        db.close()

        assert len(prefs_list) == 1
        assert prefs_list[0].sla_minutes_hot == 60


# ---------------------------------------------------------------------------
# 4. Optional fields
# ---------------------------------------------------------------------------

class TestOptionalFields:
    def test_without_working_hours(self, authenticated_client, agent_id):
        payload = {k: v for k, v in VALID_PAYLOAD.items()
                   if k not in ("working_hours_start", "working_hours_end")}
        resp = authenticated_client.put(AUTOMATION_URL, json=payload)
        assert resp.status_code == 200

    def test_tour_question_disabled(self, authenticated_client, agent_id):
        resp = authenticated_client.put(
            AUTOMATION_URL, json={**VALID_PAYLOAD, "enable_tour_question": False}
        )
        assert resp.status_code == 200

        db = TestingSessionLocal()
        config = db.query(BuyerAutomationConfig).filter_by(agent_user_id=agent_id).first()
        prefs = db.query(AgentPreferences).filter_by(agent_user_id=agent_id).first()
        db.close()

        assert config.enable_tour_question is False
        assert prefs.enable_tour_question is False


# ---------------------------------------------------------------------------
# 5. Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_hot_threshold_below_60_returns_422(self, authenticated_client):
        resp = authenticated_client.put(AUTOMATION_URL, json={**VALID_PAYLOAD, "hot_threshold": 59})
        assert resp.status_code == 422

    def test_hot_threshold_above_95_returns_422(self, authenticated_client):
        resp = authenticated_client.put(AUTOMATION_URL, json={**VALID_PAYLOAD, "hot_threshold": 96})
        assert resp.status_code == 422

    def test_hot_threshold_at_boundary_60(self, authenticated_client):
        resp = authenticated_client.put(AUTOMATION_URL, json={**VALID_PAYLOAD, "hot_threshold": 60})
        assert resp.status_code == 200

    def test_hot_threshold_at_boundary_95(self, authenticated_client):
        resp = authenticated_client.put(AUTOMATION_URL, json={**VALID_PAYLOAD, "hot_threshold": 95})
        assert resp.status_code == 200

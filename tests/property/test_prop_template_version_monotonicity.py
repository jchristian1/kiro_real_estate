"""
Property-based tests for template version monotonicity.

Feature: agent-app

**Property 19: Template Version Monotonicity** — each save increments version
by exactly 1. Starting from version N, after K saves the version is N + K.

**Validates: Requirements 14.2**
"""

import secrets
import uuid
from datetime import datetime

import bcrypt
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentSession, AgentUser
from gmail_lead_sync.models import Base


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    db_name = f"test_{uuid.uuid4().hex}"
    engine = create_engine(
        f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent_with_session(db) -> tuple:
    """Create an agent and return (agent_id, session_token)."""
    email = f"agent_{uuid.uuid4().hex[:8]}@test.com"
    password_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=email,
        password_hash=password_hash,
        full_name="Test Agent",
        onboarding_step=6,
        onboarding_completed=True,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    agent_id = agent.id  # capture before session closes

    token = secrets.token_hex(64)
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent_id,
        created_at=now,
        expires_at=now.replace(year=now.year + 1),
    )
    db.add(session)
    db.commit()

    return agent_id, token


# ---------------------------------------------------------------------------
# Property 19: Template Version Monotonicity
# ---------------------------------------------------------------------------


VALID_TYPES = ["INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"]


class TestProperty19TemplateVersionMonotonicity:
    """
    Property 19: Each save to a template increments version by exactly 1.

    For any sequence of K saves to the same template type, the final version
    equals K (first save creates version=1, each subsequent save increments by 1).
    """

    @given(
        template_type=st.sampled_from(VALID_TYPES),
        num_saves=st.integers(min_value=1, max_value=10),
        subject=st.text(min_size=1, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789").map(lambda s: s or "subject"),
        body=st.text(min_size=1, max_size=500, alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789").map(lambda s: s or "body"),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_each_save_increments_version_by_one(
        self, setup_db, template_type, num_saves, subject, body
    ):
        """
        For any template type and any number of saves K:
        - First save → version == 1
        - Each subsequent save → version increments by exactly 1
        - After K saves → version == K
        """
        db = setup_db()
        agent_id, token = _create_agent_with_session(db)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})

        payload = {"subject": subject or "Subject", "body": body or "Body", "tone": "PROFESSIONAL"}

        for k in range(1, num_saves + 1):
            resp = client.put(f"/api/v1/agent/templates/{template_type}", json=payload)
            assert resp.status_code == 200, f"Save {k} failed: {resp.text}"
            data = resp.json()
            assert data["version"] == k, (
                f"After save {k}, expected version={k} but got version={data['version']}"
            )

    @given(
        num_saves=st.integers(min_value=2, max_value=8),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_version_is_monotonically_increasing(self, setup_db, num_saves):
        """
        Versions returned by successive saves form a strictly increasing sequence
        1, 2, 3, ..., K with no gaps or repeats.
        """
        db = setup_db()
        agent_id, token = _create_agent_with_session(db)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})
        payload = {"subject": "Test Subject", "body": "Test body content", "tone": "PROFESSIONAL"}

        versions = []
        for _ in range(num_saves):
            resp = client.put("/api/v1/agent/templates/INITIAL_INVITE", json=payload)
            assert resp.status_code == 200
            versions.append(resp.json()["version"])

        # Versions must be strictly increasing with step 1
        for i in range(1, len(versions)):
            assert versions[i] == versions[i - 1] + 1, (
                f"Version jump from {versions[i-1]} to {versions[i]} is not exactly +1"
            )

    @given(
        template_type=st.sampled_from(VALID_TYPES),
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_first_save_always_creates_version_one(self, setup_db, template_type):
        """
        The very first save for any template type always produces version=1,
        regardless of template type.
        """
        db = setup_db()
        agent_id, token = _create_agent_with_session(db)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})
        payload = {"subject": "Initial Subject", "body": "Initial body", "tone": "FRIENDLY"}

        resp = client.put(f"/api/v1/agent/templates/{template_type}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["version"] == 1, (
            f"First save of {template_type} should produce version=1, "
            f"got {resp.json()['version']}"
        )

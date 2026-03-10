"""
Property-based tests for watcher admin lock.

Feature: agent-app

**Property 8: Watcher Admin Lock** — when `watcher_admin_override = TRUE`,
any toggle request returns 403 with `error: "ADMIN_LOCKED"` regardless of
the `enabled` value sent in the request body.

**Validates: Requirements 16.6**
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
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser
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


def _create_agent_with_session(db, watcher_admin_override: bool = False) -> tuple:
    """Create an agent with preferences and return (agent, session_token)."""
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

    prefs = AgentPreferences(
        agent_user_id=agent.id,
        hot_threshold=80,
        warm_threshold=50,
        sla_minutes_hot=5,
        watcher_enabled=True,
        watcher_admin_override=watcher_admin_override,
        created_at=datetime.utcnow(),
    )
    db.add(prefs)
    db.commit()

    token = secrets.token_hex(64)
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent.id,
        created_at=now,
        expires_at=now.replace(year=now.year + 1),
    )
    db.add(session)
    db.commit()

    return agent, token


# ---------------------------------------------------------------------------
# Property 8: Watcher Admin Lock
# ---------------------------------------------------------------------------


class TestProperty8WatcherAdminLock:
    """
    Property 8: When watcher_admin_override = TRUE, any toggle request returns
    403 with error: "ADMIN_LOCKED" regardless of the enabled value.
    """

    @given(enabled=st.booleans())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_locked_returns_403_for_any_enabled_value(self, setup_db, enabled):
        """
        For any value of `enabled` (True or False), when watcher_admin_override
        is TRUE the endpoint must return 403 with error: "ADMIN_LOCKED".
        """
        db = setup_db()
        _, token = _create_agent_with_session(db, watcher_admin_override=True)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})
        resp = client.patch("/api/v1/agent/account/watcher", json={"enabled": enabled})

        assert resp.status_code == 403, (
            f"Expected 403 when admin_override=True and enabled={enabled}, "
            f"got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        # Detail may be nested under "detail" key by FastAPI
        detail = body.get("detail", body)
        assert detail.get("error") == "ADMIN_LOCKED", (
            f"Expected error='ADMIN_LOCKED', got: {body}"
        )

    @given(enabled=st.booleans())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_admin_lock_allows_toggle(self, setup_db, enabled):
        """
        Contrast: when watcher_admin_override is FALSE, toggle succeeds (200)
        and the watcher state reflects the requested value.
        """
        db = setup_db()
        _, token = _create_agent_with_session(db, watcher_admin_override=False)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})
        resp = client.patch("/api/v1/agent/account/watcher", json={"enabled": enabled})

        assert resp.status_code == 200, (
            f"Expected 200 when admin_override=False and enabled={enabled}, "
            f"got {resp.status_code}: {resp.text}"
        )
        assert resp.json()["watcher_enabled"] == enabled

    @given(
        first_enabled=st.booleans(),
        second_enabled=st.booleans(),
    )
    @settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_lock_is_immutable_across_multiple_requests(
        self, setup_db, first_enabled, second_enabled
    ):
        """
        Multiple consecutive toggle attempts while admin_override=True all
        return 403 — the lock cannot be bypassed by repeated requests.
        """
        db = setup_db()
        _, token = _create_agent_with_session(db, watcher_admin_override=True)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})

        for attempt, enabled in enumerate([first_enabled, second_enabled], start=1):
            resp = client.patch("/api/v1/agent/account/watcher", json={"enabled": enabled})
            assert resp.status_code == 403, (
                f"Attempt {attempt}: expected 403 for admin-locked watcher, "
                f"got {resp.status_code}"
            )
            detail = resp.json().get("detail", resp.json())
            assert detail.get("error") == "ADMIN_LOCKED"

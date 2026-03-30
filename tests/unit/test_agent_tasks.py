"""
Unit tests for agent task endpoints.

Tests cover:
- POST /api/v1/agent/leads/{lead_id}/tasks  — create task
- GET  /api/v1/agent/leads/{lead_id}/tasks  — list tasks
- PATCH /api/v1/agent/tasks/{task_id}       — update task
- DELETE /api/v1/agent/tasks/{task_id}      — delete task
- Tenant isolation: agents cannot access each other's tasks
- V1 rule: completing a task does NOT move the lead stage
"""

import secrets
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentSession, AgentUser
from gmail_lead_sync.models import Base, Lead, LeadSource

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
client = TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    ls = LeadSource(
        sender_email="leads@test.com",
        identifier_snippet="Lead",
        name_regex=r"Name:\s*(.+)",
        phone_regex=r"Phone:\s*([\d-]+)",
    )
    db.add(ls)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(email: str = None) -> tuple[int, str]:
    db = TestingSessionLocal()
    agent = AgentUser(
        email=email or f"agent_{secrets.token_hex(4)}@test.com",
        password_hash="hashed",
        full_name="Test Agent",
        onboarding_step=6,
        onboarding_completed=True,
    )
    db.add(agent)
    db.flush()
    token = secrets.token_hex(64)
    session = AgentSession(
        id=token,
        agent_user_id=agent.id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1),
        last_accessed=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    agent_id = agent.id
    db.close()
    return agent_id, token


def _create_lead(agent_user_id: int) -> int:
    db = TestingSessionLocal()
    lead = Lead(
        name="Test Lead",
        phone="555-0000",
        source_email="leads@test.com",
        lead_source_id=1,
        gmail_uid=f"uid-{secrets.token_hex(8)}",
        agent_user_id=agent_user_id,
    )
    db.add(lead)
    db.commit()
    lead_id = lead.id
    db.close()
    return lead_id


def _auth(token: str) -> dict:
    return {"agent_session": token}


# ---------------------------------------------------------------------------
# Tests: create task
# ---------------------------------------------------------------------------


def test_create_task_success():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)

    resp = client.post(
        f"/api/v1/agent/leads/{lead_id}/tasks",
        json={"title": "Call the lead"},
        cookies=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["ok"] is True
    assert data["task"]["title"] == "Call the lead"
    assert data["task"]["status"] == "open"
    assert data["task"]["source"] == "manual"
    assert data["task"]["lead_id"] == lead_id
    assert data["task"]["agent_user_id"] == agent_id


def test_create_task_with_description_and_due():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)

    resp = client.post(
        f"/api/v1/agent/leads/{lead_id}/tasks",
        json={
            "title": "Send follow-up email",
            "description": "Use the warm template",
            "due_at": "2026-12-31T10:00:00",
        },
        cookies=_auth(token),
    )
    assert resp.status_code == 201
    task = resp.json()["task"]
    assert task["description"] == "Use the warm template"
    assert task["due_at"] is not None


def test_create_task_unauthenticated():
    resp = client.post("/api/v1/agent/leads/1/tasks", json={"title": "x"})
    assert resp.status_code == 401


def test_create_task_empty_title_rejected():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)
    resp = client.post(
        f"/api/v1/agent/leads/{lead_id}/tasks",
        json={"title": ""},
        cookies=_auth(token),
    )
    assert resp.status_code == 422


def test_create_task_wrong_lead_returns_404():
    """Agent cannot create a task on another agent's lead."""
    agent_a_id, token_a = _create_agent()
    agent_b_id, _ = _create_agent()
    lead_b_id = _create_lead(agent_b_id)

    resp = client.post(
        f"/api/v1/agent/leads/{lead_b_id}/tasks",
        json={"title": "Sneaky task"},
        cookies=_auth(token_a),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: list tasks
# ---------------------------------------------------------------------------


def test_list_tasks_empty():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)

    resp = client.get(f"/api/v1/agent/leads/{lead_id}/tasks", cookies=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["tasks"] == []
    assert data["total"] == 0


def test_list_tasks_returns_own_tasks():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)

    client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Task 1"}, cookies=_auth(token))
    client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Task 2"}, cookies=_auth(token))

    resp = client.get(f"/api/v1/agent/leads/{lead_id}/tasks", cookies=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_list_tasks_filter_by_status():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)

    r1 = client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Open task"}, cookies=_auth(token))
    task_id = r1.json()["task"]["id"]
    client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Another open"}, cookies=_auth(token))

    # Mark one done
    client.patch(f"/api/v1/agent/tasks/{task_id}", json={"status": "done"}, cookies=_auth(token))

    open_resp = client.get(f"/api/v1/agent/leads/{lead_id}/tasks?status=open", cookies=_auth(token))
    done_resp = client.get(f"/api/v1/agent/leads/{lead_id}/tasks?status=done", cookies=_auth(token))

    assert open_resp.json()["total"] == 1
    assert done_resp.json()["total"] == 1


def test_list_tasks_tenant_isolation():
    """Agent A cannot list tasks on Agent B's lead."""
    agent_a_id, token_a = _create_agent()
    agent_b_id, _ = _create_agent()
    lead_b_id = _create_lead(agent_b_id)

    resp = client.get(f"/api/v1/agent/leads/{lead_b_id}/tasks", cookies=_auth(token_a))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: update task
# ---------------------------------------------------------------------------


def test_update_task_title():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)
    r = client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Old title"}, cookies=_auth(token))
    task_id = r.json()["task"]["id"]

    resp = client.patch(f"/api/v1/agent/tasks/{task_id}", json={"title": "New title"}, cookies=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["title"] == "New title"


def test_complete_task_sets_completed_at():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)
    r = client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Do something"}, cookies=_auth(token))
    task_id = r.json()["task"]["id"]

    resp = client.patch(f"/api/v1/agent/tasks/{task_id}", json={"status": "done"}, cookies=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["completed_at"] is not None


def test_completing_task_does_not_move_lead_stage():
    """V1 rule: completing a task must NOT change the lead's stage."""
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)

    # Record initial stage
    db = TestingSessionLocal()
    lead_before = db.query(Lead).filter(Lead.id == lead_id).first()
    stage_before = lead_before.current_stage_id
    db.close()

    r = client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Do something"}, cookies=_auth(token))
    task_id = r.json()["task"]["id"]
    client.patch(f"/api/v1/agent/tasks/{task_id}", json={"status": "done"}, cookies=_auth(token))

    db = TestingSessionLocal()
    lead_after = db.query(Lead).filter(Lead.id == lead_id).first()
    stage_after = lead_after.current_stage_id
    db.close()

    assert stage_before == stage_after


def test_reopen_task_clears_completed_at():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)
    r = client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Task"}, cookies=_auth(token))
    task_id = r.json()["task"]["id"]

    client.patch(f"/api/v1/agent/tasks/{task_id}", json={"status": "done"}, cookies=_auth(token))
    resp = client.patch(f"/api/v1/agent/tasks/{task_id}", json={"status": "open"}, cookies=_auth(token))
    assert resp.json()["status"] == "open"
    assert resp.json()["completed_at"] is None


def test_update_task_wrong_agent_returns_404():
    agent_a_id, token_a = _create_agent()
    agent_b_id, token_b = _create_agent()
    lead_a_id = _create_lead(agent_a_id)

    r = client.post(f"/api/v1/agent/leads/{lead_a_id}/tasks", json={"title": "A's task"}, cookies=_auth(token_a))
    task_id = r.json()["task"]["id"]

    resp = client.patch(f"/api/v1/agent/tasks/{task_id}", json={"title": "Hijacked"}, cookies=_auth(token_b))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: delete task
# ---------------------------------------------------------------------------


def test_delete_task_success():
    agent_id, token = _create_agent()
    lead_id = _create_lead(agent_id)
    r = client.post(f"/api/v1/agent/leads/{lead_id}/tasks", json={"title": "Delete me"}, cookies=_auth(token))
    task_id = r.json()["task"]["id"]

    resp = client.delete(f"/api/v1/agent/tasks/{task_id}", cookies=_auth(token))
    assert resp.status_code == 204

    list_resp = client.get(f"/api/v1/agent/leads/{lead_id}/tasks", cookies=_auth(token))
    assert list_resp.json()["total"] == 0


def test_delete_task_wrong_agent_returns_404():
    agent_a_id, token_a = _create_agent()
    agent_b_id, token_b = _create_agent()
    lead_a_id = _create_lead(agent_a_id)

    r = client.post(f"/api/v1/agent/leads/{lead_a_id}/tasks", json={"title": "A's task"}, cookies=_auth(token_a))
    task_id = r.json()["task"]["id"]

    resp = client.delete(f"/api/v1/agent/tasks/{task_id}", cookies=_auth(token_b))
    assert resp.status_code == 404

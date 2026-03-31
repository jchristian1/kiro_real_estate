"""
Unit tests for watcher control API endpoints (Phase 5C — DB-backed).

The API no longer owns the watcher runtime. It writes desired state to
watcher_control and reads live status from watcher_status. Tests verify:
- Start/stop/sync write the correct DB rows
- Status endpoint reads from watcher_status table
- Audit log actions match the new naming convention
- Authentication is enforced
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gmail_lead_sync.models import Base, Credentials
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
from api.models.web_ui_models import User
from api.models.watcher_state_models import WatcherControl, WatcherStatus
from api.main import app
from api.auth import hash_password, create_session


TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
TEST_ENCRYPTION_KEY = "msZUufDiUiwjj5KmOrO8bSWktWtpzng4N7D3iqHS4Yg="


@pytest.fixture(scope="function")
def db_engine():
    Base.metadata.create_all(test_engine)
    yield test_engine


@pytest.fixture
def db_session(db_engine):
    session = TestSessionLocal()
    session.query(Credentials).delete()
    session.query(WatcherControl).delete()
    session.query(WatcherStatus).delete()
    session.commit()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def test_user(db_session):
    existing = db_session.query(User).filter(User.username == "testuser").first()
    if existing:
        return existing
    user = User(username="testuser", password_hash=hash_password("testpass"), role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_session(db_session, test_user):
    return create_session(db_session, test_user.id, __import__("api.config", fromlist=["get_config"]).get_config().secret_key)


@pytest.fixture
def test_agent(db_session):
    store = EncryptedDBCredentialsStore(db_session, encryption_key=TEST_ENCRYPTION_KEY)
    store.store_credentials(
        agent_id="test_agent",
        email="test@example.com",
        app_password="test-password",
    )
    return db_session.query(Credentials).filter(Credentials.agent_id == "test_agent").first()


@pytest.fixture
def client(db_session, test_user, auth_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user() -> User:
        return test_user

    from api.routers import admin_watchers as watchers
    from api.dependencies.db import get_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[watchers.get_db] = override_get_db
    app.dependency_overrides[watchers.get_current_user] = override_get_current_user

    c = TestClient(app)
    c.cookies.set("session_token", auth_session._raw_token)
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------


class TestStartWatcher:
    def test_start_watcher_success(self, client, test_agent, db_session):
        response = client.post("/api/v1/watchers/test_agent/start")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test_agent"
        assert "message" in data
        assert "requested" in data["message"].lower()

        # Verify DB row was written
        ctrl = db_session.query(WatcherControl).filter_by(agent_id="test_agent").first()
        assert ctrl is not None
        assert ctrl.desired_status == "running"

    def test_start_watcher_agent_not_found(self, client):
        response = client.post("/api/v1/watchers/nonexistent/start")
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()

    def test_start_watcher_idempotent(self, client, test_agent, db_session):
        """Calling start twice is fine — just upserts the row."""
        client.post("/api/v1/watchers/test_agent/start")
        response = client.post("/api/v1/watchers/test_agent/start")
        assert response.status_code == 200

        rows = db_session.query(WatcherControl).filter_by(agent_id="test_agent").all()
        assert len(rows) == 1
        assert rows[0].desired_status == "running"


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------


class TestStopWatcher:
    def test_stop_watcher_success(self, client, test_agent, db_session):
        response = client.post("/api/v1/watchers/test_agent/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test_agent"
        assert data["status"] == "stopping"
        assert "requested" in data["message"].lower()

        ctrl = db_session.query(WatcherControl).filter_by(agent_id="test_agent").first()
        assert ctrl is not None
        assert ctrl.desired_status == "stopped"

    def test_stop_watcher_agent_not_found(self, client):
        response = client.post("/api/v1/watchers/nonexistent/stop")
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


class TestTriggerSync:
    def test_trigger_sync_success(self, client, test_agent, db_session):
        response = client.post("/api/v1/watchers/test_agent/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test_agent"
        assert data["sync_triggered"] is True
        assert "timestamp" in data
        assert "requested" in data["message"].lower()

        ctrl = db_session.query(WatcherControl).filter_by(agent_id="test_agent").first()
        assert ctrl is not None
        assert ctrl.sync_requested_at is not None

    def test_trigger_sync_agent_not_found(self, client):
        response = client.post("/api/v1/watchers/nonexistent/sync")
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class TestGetWatcherStatus:
    def test_get_all_statuses_empty(self, client):
        response = client.get("/api/v1/watchers/status")
        assert response.status_code == 200
        data = response.json()
        assert data["watchers"] == []

    def test_get_all_statuses_with_db_rows(self, client, db_session):
        now = datetime(2024, 1, 15, 10, 0, 0)
        db_session.add(WatcherStatus(
            agent_id="test_agent",
            status="running",
            last_heartbeat=now,
            last_sync=now,
            started_at=now,
            error=None,
            updated_at=now,
        ))
        db_session.commit()

        response = client.get("/api/v1/watchers/status")
        assert response.status_code == 200
        data = response.json()

        assert len(data["watchers"]) == 1
        w = data["watchers"][0]
        assert w["agent_id"] == "test_agent"
        assert w["status"] == "running"
        assert w["error"] is None

    def test_get_all_statuses_multiple(self, client, db_session):
        now = datetime(2024, 1, 15, 10, 0, 0)
        for agent_id, st in [("a1", "running"), ("a2", "stopped"), ("a3", "failed")]:
            db_session.add(WatcherStatus(
                agent_id=agent_id,
                status=st,
                error="timeout" if st == "failed" else None,
                updated_at=now,
            ))
        db_session.commit()

        response = client.get("/api/v1/watchers/status")
        assert response.status_code == 200
        data = response.json()
        assert len(data["watchers"]) == 3

        ids = {w["agent_id"] for w in data["watchers"]}
        assert ids == {"a1", "a2", "a3"}

        failed = next(w for w in data["watchers"] if w["agent_id"] == "a3")
        assert failed["status"] == "failed"
        assert failed["error"] == "timeout"

    def test_status_includes_all_fields(self, client, db_session):
        now = datetime(2024, 1, 15, 10, 0, 0)
        db_session.add(WatcherStatus(
            agent_id="test_agent",
            status="running",
            last_heartbeat=now,
            last_sync=now,
            started_at=now,
            error=None,
            updated_at=now,
        ))
        db_session.commit()

        response = client.get("/api/v1/watchers/status")
        w = response.json()["watchers"][0]
        for field in ["agent_id", "status", "last_heartbeat", "last_sync", "error", "started_at"]:
            assert field in w, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


class TestAuditLogging:
    def test_start_creates_audit_log(self, client, test_agent, db_session):
        from api.models.web_ui_models import AuditLog
        before = db_session.query(AuditLog).count()

        response = client.post("/api/v1/watchers/test_agent/start")
        assert response.status_code == 200

        after = db_session.query(AuditLog).count()
        assert after == before + 1

        log = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert log.action == "watcher_start_requested"
        assert log.resource_type == "watcher"
        assert "test_agent" in log.details

    def test_stop_creates_audit_log(self, client, test_agent, db_session):
        from api.models.web_ui_models import AuditLog
        before = db_session.query(AuditLog).count()

        response = client.post("/api/v1/watchers/test_agent/stop")
        assert response.status_code == 200

        after = db_session.query(AuditLog).count()
        assert after == before + 1

        log = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert log.action == "watcher_stop_requested"
        assert log.resource_type == "watcher"

    def test_sync_creates_audit_log(self, client, test_agent, db_session):
        from api.models.web_ui_models import AuditLog
        before = db_session.query(AuditLog).count()

        response = client.post("/api/v1/watchers/test_agent/sync")
        assert response.status_code == 200

        after = db_session.query(AuditLog).count()
        assert after == before + 1

        log = db_session.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert log.action == "watcher_sync_requested"
        assert log.resource_type == "watcher"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class TestAuthentication:
    def _unauthenticated_client(self, db_session):
        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        from api.dependencies.db import get_db
        app.dependency_overrides[get_db] = override_get_db
        c = TestClient(app)
        yield c
        app.dependency_overrides.clear()

    def test_start_requires_auth(self, db_session, test_agent):
        from api.dependencies.db import get_db
        app.dependency_overrides[get_db] = lambda: (yield db_session)
        c = TestClient(app)
        response = c.post("/api/v1/watchers/test_agent/start")
        assert response.status_code == 401
        app.dependency_overrides.clear()

    def test_stop_requires_auth(self, db_session, test_agent):
        from api.dependencies.db import get_db
        app.dependency_overrides[get_db] = lambda: (yield db_session)
        c = TestClient(app)
        response = c.post("/api/v1/watchers/test_agent/stop")
        assert response.status_code == 401
        app.dependency_overrides.clear()

    def test_sync_requires_auth(self, db_session, test_agent):
        from api.dependencies.db import get_db
        app.dependency_overrides[get_db] = lambda: (yield db_session)
        c = TestClient(app)
        response = c.post("/api/v1/watchers/test_agent/sync")
        assert response.status_code == 401
        app.dependency_overrides.clear()

    def test_status_requires_auth(self, db_session):
        from api.dependencies.db import get_db
        app.dependency_overrides[get_db] = lambda: (yield db_session)
        c = TestClient(app)
        response = c.get("/api/v1/watchers/status")
        assert response.status_code == 401
        app.dependency_overrides.clear()

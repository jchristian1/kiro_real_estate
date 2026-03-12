"""
Unit tests for audit log API endpoints.

Tests the audit log REST API including:
- Listing audit logs with pagination
- Filtering by action type, user_id, and date range
- Authentication requirements
"""

import pytest
from datetime import datetime, timedelta
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from gmail_lead_sync.models import Base
from api.models.web_ui_models import User, Session as SessionModel, AuditLog
from api.main import app, get_db
from api.auth import create_session, hash_password


@pytest.fixture(scope="function")
def db_engine():
    """Create a shared database engine for testing."""
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    
    # Import all models to ensure they're registered with Base
    from api.models import web_ui_models  # noqa: F401
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    
    # Create test users
    user1 = User(
        username='testuser1',
        password_hash=hash_password('password123'),
        role='admin'
    )
    user2 = User(
        username='testuser2',
        password_hash=hash_password('password456'),
        role='admin'
    )
    session.add(user1)
    session.add(user2)
    session.commit()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture
def client(db_session):
    """Create a test client with database dependency override."""
    # Create a generator function that yields the same session
    def override_get_db():
        yield db_session
    
    def override_get_current_user() -> User:
        """Mock authentication - returns first user."""
        # Use the db_session directly
        return db_session.query(User).first()
    
    # Import the dependency functions from the audit router
    from api.routers.admin_audit import get_db_dependency, get_current_user_dependency
    
    # Override dependencies at the app level
    app.dependency_overrides[get_db_dependency] = override_get_db
    app.dependency_overrides[get_current_user_dependency] = override_get_current_user
    
    # Create test client
    client = TestClient(app)
    
    yield client
    
    # Clean up - clear overrides
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_user(db_session):
    """Create an authenticated user session."""
    user = db_session.query(User).filter_by(username='testuser1').first()
    session = create_session(db_session, user.id)
    return user, session


def test_list_audit_logs_empty(client, db_session, authenticated_user):
    """Test listing audit logs when no logs exist."""
    user, session = authenticated_user
    
    response = client.get("/api/v1/audit-logs")
    
    assert response.status_code == 200
    data = response.json()
    assert data["logs"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["per_page"] == 100
    assert data["pages"] == 0


def test_list_audit_logs_basic(client, db_session, authenticated_user):
    """Test listing audit logs with basic pagination."""
    user, session = authenticated_user
    
    # Create test audit logs
    for i in range(5):
        log = AuditLog(
            timestamp=datetime.utcnow(),
            user_id=user.id,
            action=f'action_{i}',
            resource_type='test',
            resource_id=i,
            details=f'Test log {i}'
        )
        db_session.add(log)
    db_session.commit()
    
    response = client.get(
        "/api/v1/audit-logs",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 5
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["per_page"] == 100
    assert data["pages"] == 1
    
    # Verify logs are ordered by timestamp descending (most recent first)
    timestamps = [log["timestamp"] for log in data["logs"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_list_audit_logs_pagination(client, db_session, authenticated_user):
    """Test audit log pagination."""
    user, session = authenticated_user
    
    # Create 25 test audit logs
    for i in range(25):
        log = AuditLog(
            timestamp=datetime.utcnow() + timedelta(seconds=i),
            user_id=user.id,
            action=f'action_{i}',
            resource_type='test',
            resource_id=i
        )
        db_session.add(log)
    db_session.commit()
    
    # Get first page (10 items per page)
    response = client.get(
        "/api/v1/audit-logs?page=1&per_page=10",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 10
    assert data["total"] == 25
    assert data["page"] == 1
    assert data["per_page"] == 10
    assert data["pages"] == 3
    
    # Get second page
    response = client.get(
        "/api/v1/audit-logs?page=2&per_page=10",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 10
    assert data["page"] == 2
    
    # Get third page (only 5 items)
    response = client.get(
        "/api/v1/audit-logs?page=3&per_page=10",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 5
    assert data["page"] == 3


def test_list_audit_logs_filter_by_action(client, db_session, authenticated_user):
    """Test filtering audit logs by action type."""
    user, session = authenticated_user
    
    # Create audit logs with different actions
    actions = ['agent_created', 'agent_updated', 'template_created', 'agent_created']
    for action in actions:
        log = AuditLog(
            timestamp=datetime.utcnow(),
            user_id=user.id,
            action=action,
            resource_type='test',
            resource_id=1
        )
        db_session.add(log)
    db_session.commit()
    
    # Filter by action
    response = client.get(
        "/api/v1/audit-logs?action=agent_created",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 2
    assert data["total"] == 2
    assert all(log["action"] == "agent_created" for log in data["logs"])


def test_list_audit_logs_filter_by_user_id(client, db_session, authenticated_user):
    """Test filtering audit logs by user ID."""
    user1, session = authenticated_user
    user2 = db_session.query(User).filter_by(username='testuser2').first()
    
    # Create audit logs for different users
    for i in range(3):
        log = AuditLog(
            timestamp=datetime.utcnow(),
            user_id=user1.id,
            action='action_user1',
            resource_type='test',
            resource_id=i
        )
        db_session.add(log)
    
    for i in range(2):
        log = AuditLog(
            timestamp=datetime.utcnow(),
            user_id=user2.id,
            action='action_user2',
            resource_type='test',
            resource_id=i
        )
        db_session.add(log)
    db_session.commit()
    
    # Filter by user1
    response = client.get(
        f"/api/v1/audit-logs?user_id={user1.id}",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 3
    assert data["total"] == 3
    assert all(log["user_id"] == user1.id for log in data["logs"])
    
    # Filter by user2
    response = client.get(
        f"/api/v1/audit-logs?user_id={user2.id}",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 2
    assert data["total"] == 2
    assert all(log["user_id"] == user2.id for log in data["logs"])


def test_list_audit_logs_filter_by_date_range(client, db_session, authenticated_user):
    """Test filtering audit logs by date range."""
    user, session = authenticated_user
    
    # Create audit logs with different timestamps
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    
    log1 = AuditLog(
        timestamp=base_time,
        user_id=user.id,
        action='action_1',
        resource_type='test',
        resource_id=1
    )
    log2 = AuditLog(
        timestamp=base_time + timedelta(days=1),
        user_id=user.id,
        action='action_2',
        resource_type='test',
        resource_id=2
    )
    log3 = AuditLog(
        timestamp=base_time + timedelta(days=2),
        user_id=user.id,
        action='action_3',
        resource_type='test',
        resource_id=3
    )
    db_session.add_all([log1, log2, log3])
    db_session.commit()
    
    # Filter by start_date
    start_date = (base_time + timedelta(days=1)).isoformat()
    response = client.get(
        f"/api/v1/audit-logs?start_date={start_date}",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 2
    assert data["total"] == 2
    
    # Filter by end_date
    end_date = (base_time + timedelta(days=1)).isoformat()
    response = client.get(
        f"/api/v1/audit-logs?end_date={end_date}",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 2
    assert data["total"] == 2
    
    # Filter by date range
    start_date = base_time.isoformat()
    end_date = (base_time + timedelta(days=1)).isoformat()
    response = client.get(
        f"/api/v1/audit-logs?start_date={start_date}&end_date={end_date}",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 2
    assert data["total"] == 2


def test_list_audit_logs_multiple_filters(client, db_session, authenticated_user):
    """Test filtering audit logs with multiple filters combined."""
    user1, session = authenticated_user
    user2 = db_session.query(User).filter_by(username='testuser2').first()
    
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    
    # Create various audit logs
    logs = [
        AuditLog(timestamp=base_time, user_id=user1.id, action='agent_created', resource_type='agent', resource_id=1),
        AuditLog(timestamp=base_time + timedelta(days=1), user_id=user1.id, action='agent_created', resource_type='agent', resource_id=2),
        AuditLog(timestamp=base_time + timedelta(days=2), user_id=user2.id, action='agent_created', resource_type='agent', resource_id=3),
        AuditLog(timestamp=base_time + timedelta(days=1), user_id=user1.id, action='template_created', resource_type='template', resource_id=1),
    ]
    db_session.add_all(logs)
    db_session.commit()
    
    # Filter by action and user_id
    response = client.get(
        f"/api/v1/audit-logs?action=agent_created&user_id={user1.id}",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 2
    assert data["total"] == 2
    assert all(log["action"] == "agent_created" and log["user_id"] == user1.id for log in data["logs"])


def test_list_audit_logs_includes_username(client, db_session, authenticated_user):
    """Test that audit log responses include username."""
    user, session = authenticated_user
    
    # Create an audit log
    log = AuditLog(
        timestamp=datetime.utcnow(),
        user_id=user.id,
        action='test_action',
        resource_type='test',
        resource_id=1,
        details='Test details'
    )
    db_session.add(log)
    db_session.commit()
    
    response = client.get(
        "/api/v1/audit-logs",
        
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) == 1
    assert data["logs"][0]["username"] == "testuser1"
    assert data["logs"][0]["user_id"] == user.id
    assert data["logs"][0]["action"] == "test_action"
    assert data["logs"][0]["resource_type"] == "test"
    assert data["logs"][0]["resource_id"] == 1
    assert data["logs"][0]["details"] == "Test details"


def test_list_audit_logs_invalid_page(client, db_session, authenticated_user):
    """Test that invalid page numbers are rejected."""
    user, session = authenticated_user
    
    # Page must be >= 1
    response = client.get(
        "/api/v1/audit-logs?page=0",
        
    )
    
    assert response.status_code == 422  # Validation error


def test_list_audit_logs_invalid_per_page(client, db_session, authenticated_user):
    """Test that invalid per_page values are rejected."""
    user, session = authenticated_user
    
    # per_page must be >= 1 and <= 500
    response = client.get(
        "/api/v1/audit-logs?per_page=0",
        
    )
    
    assert response.status_code == 422  # Validation error
    
    response = client.get(
        "/api/v1/audit-logs?per_page=1000",
        
    )
    
    assert response.status_code == 422  # Validation error

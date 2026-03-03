"""
Unit tests for audit log recording service.

Tests the audit log recording functionality including:
- Basic audit log creation
- Recording with optional fields
- Timestamp recording
- Append-only behavior
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base
from api.models.web_ui_models import User, AuditLog
from api.services.audit_log import record_audit_log


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create a test user
    user = User(
        username='testuser',
        password_hash='hashed_password',
        role='admin'
    )
    session.add(user)
    session.commit()
    
    yield session
    
    session.close()


def test_record_audit_log_basic(db_session):
    """Test basic audit log recording with all fields."""
    # Get the test user
    user = db_session.query(User).filter_by(username='testuser').first()
    
    # Record an audit log entry
    audit_entry = record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='agent_created',
        resource_type='agent',
        resource_id=1,
        details='Created agent agent1 with email agent1@example.com'
    )
    
    # Verify the entry was created
    assert audit_entry.id is not None
    assert audit_entry.user_id == user.id
    assert audit_entry.action == 'agent_created'
    assert audit_entry.resource_type == 'agent'
    assert audit_entry.resource_id == 1
    assert audit_entry.details == 'Created agent agent1 with email agent1@example.com'
    assert isinstance(audit_entry.timestamp, datetime)


def test_record_audit_log_without_resource_id(db_session):
    """Test audit log recording without resource_id."""
    user = db_session.query(User).filter_by(username='testuser').first()
    
    audit_entry = record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='login_success',
        resource_type='session',
        details='User logged in successfully'
    )
    
    assert audit_entry.id is not None
    assert audit_entry.user_id == user.id
    assert audit_entry.action == 'login_success'
    assert audit_entry.resource_type == 'session'
    assert audit_entry.resource_id is None
    assert audit_entry.details == 'User logged in successfully'


def test_record_audit_log_without_details(db_session):
    """Test audit log recording without details."""
    user = db_session.query(User).filter_by(username='testuser').first()
    
    audit_entry = record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='template_deleted',
        resource_type='template',
        resource_id=5
    )
    
    assert audit_entry.id is not None
    assert audit_entry.user_id == user.id
    assert audit_entry.action == 'template_deleted'
    assert audit_entry.resource_type == 'template'
    assert audit_entry.resource_id == 5
    assert audit_entry.details is None


def test_record_audit_log_minimal(db_session):
    """Test audit log recording with minimal required fields."""
    user = db_session.query(User).filter_by(username='testuser').first()
    
    audit_entry = record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='settings_updated',
        resource_type='settings'
    )
    
    assert audit_entry.id is not None
    assert audit_entry.user_id == user.id
    assert audit_entry.action == 'settings_updated'
    assert audit_entry.resource_type == 'settings'
    assert audit_entry.resource_id is None
    assert audit_entry.details is None


def test_record_audit_log_timestamp(db_session):
    """Test that audit log records current timestamp."""
    user = db_session.query(User).filter_by(username='testuser').first()
    
    before = datetime.utcnow()
    audit_entry = record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='watcher_started',
        resource_type='watcher',
        resource_id=1
    )
    after = datetime.utcnow()
    
    # Verify timestamp is between before and after
    assert before <= audit_entry.timestamp <= after


def test_record_multiple_audit_logs(db_session):
    """Test recording multiple audit log entries (append-only behavior)."""
    user = db_session.query(User).filter_by(username='testuser').first()
    
    # Record multiple entries
    entry1 = record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='agent_created',
        resource_type='agent',
        resource_id=1
    )
    
    entry2 = record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='agent_updated',
        resource_type='agent',
        resource_id=1
    )
    
    entry3 = record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='agent_deleted',
        resource_type='agent',
        resource_id=1
    )
    
    # Verify all entries exist
    all_entries = db_session.query(AuditLog).all()
    assert len(all_entries) == 3
    assert entry1.id != entry2.id != entry3.id
    
    # Verify entries are in chronological order
    assert entry1.timestamp <= entry2.timestamp <= entry3.timestamp


def test_record_audit_log_various_actions(db_session):
    """Test recording various action types."""
    user = db_session.query(User).filter_by(username='testuser').first()
    
    actions = [
        ('agent_created', 'agent', 1),
        ('agent_updated', 'agent', 1),
        ('agent_deleted', 'agent', 1),
        ('template_created', 'template', 2),
        ('template_updated', 'template', 2),
        ('template_deleted', 'template', 2),
        ('template_rollback', 'template', 2),
        ('lead_source_created', 'lead_source', 3),
        ('lead_source_updated', 'lead_source', 3),
        ('lead_source_deleted', 'lead_source', 3),
        ('watcher_started', 'watcher', 1),
        ('watcher_stopped', 'watcher', 1),
        ('watcher_sync', 'watcher', 1),
        ('settings_updated', 'settings', None),
        ('login_success', 'session', None),
        ('login_failed', 'session', None),
        ('logout', 'session', None),
    ]
    
    for action, resource_type, resource_id in actions:
        entry = record_audit_log(
            db_session=db_session,
            user_id=user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id
        )
        assert entry.action == action
        assert entry.resource_type == resource_type
        assert entry.resource_id == resource_id


def test_record_audit_log_persists_to_database(db_session):
    """Test that audit log entries are persisted to the database."""
    user = db_session.query(User).filter_by(username='testuser').first()
    
    # Record an entry
    record_audit_log(
        db_session=db_session,
        user_id=user.id,
        action='agent_created',
        resource_type='agent',
        resource_id=1,
        details='Test entry'
    )
    
    # Query the database directly
    entries = db_session.query(AuditLog).filter_by(action='agent_created').all()
    assert len(entries) == 1
    assert entries[0].details == 'Test entry'

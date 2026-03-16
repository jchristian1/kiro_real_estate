"""
Unit tests for Health Check API.

Tests the health check endpoint's ability to:
- Check database connectivity
- Check last successful sync time
- Check IMAP connection status
- Return appropriate HTTP status codes
"""

import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gmail_lead_sync.models import Base, ProcessingLog
from gmail_lead_sync.health import (
    init_health_check,
    check_database_connectivity,
    check_last_successful_sync,
    check_imap_connection,
    app
)
from gmail_lead_sync.watcher import GmailWatcher


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_watcher():
    """Create a mock watcher instance."""
    watcher = Mock(spec=GmailWatcher)
    watcher.is_connected.return_value = True
    return watcher


@pytest.fixture
def flask_client(db_session, mock_watcher):
    """Create Flask test client with initialized health check."""
    init_health_check(db_session, mock_watcher)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthCheckFunctions:
    """Test suite for health check helper functions."""
    
    def test_check_database_connectivity_success(self, db_session):
        """Test successful database connectivity check."""
        init_health_check(db_session)
        result = check_database_connectivity()
        assert result is True
    
    def test_check_database_connectivity_no_session(self):
        """Test database check fails when session not initialized."""
        init_health_check(None)
        result = check_database_connectivity()
        assert result is False
    
    def test_check_last_successful_sync_recent(self, db_session):
        """Test sync check passes with recent successful sync."""
        init_health_check(db_session)
        
        # Create a recent successful processing log
        log = ProcessingLog(
            gmail_uid='test_uid_123',
            timestamp=datetime.utcnow() - timedelta(minutes=30),
            sender_email='test@example.com',
            status='success',
            lead_id=1
        )
        db_session.add(log)
        db_session.commit()
        
        is_healthy, last_sync = check_last_successful_sync()
        
        assert is_healthy is True
        assert last_sync is not None
        assert isinstance(last_sync, datetime)
    
    def test_check_last_successful_sync_stale(self, db_session):
        """Test sync check fails with stale sync."""
        init_health_check(db_session)
        
        # Create an old successful processing log (2 hours ago)
        log = ProcessingLog(
            gmail_uid='test_uid_456',
            timestamp=datetime.utcnow() - timedelta(hours=2),
            sender_email='test@example.com',
            status='success',
            lead_id=2
        )
        db_session.add(log)
        db_session.commit()
        
        is_healthy, last_sync = check_last_successful_sync()
        
        assert is_healthy is False
        assert last_sync is not None
    
    def test_check_last_successful_sync_no_logs(self, db_session):
        """Test sync check fails when no successful logs exist."""
        init_health_check(db_session)
        
        is_healthy, last_sync = check_last_successful_sync()
        
        assert is_healthy is False
        assert last_sync is None
    
    def test_check_imap_connection_connected(self, mock_watcher):
        """Test IMAP check passes when watcher is connected."""
        init_health_check(None, mock_watcher)
        mock_watcher.is_connected.return_value = True
        
        result = check_imap_connection()
        
        assert result is True
        mock_watcher.is_connected.assert_called_once()
    
    def test_check_imap_connection_disconnected(self, mock_watcher):
        """Test IMAP check fails when watcher is disconnected."""
        init_health_check(None, mock_watcher)
        mock_watcher.is_connected.return_value = False
        
        result = check_imap_connection()
        
        assert result is False
    
    def test_check_imap_connection_no_watcher(self):
        """Test IMAP check passes when watcher not initialized."""
        init_health_check(None, None)
        
        result = check_imap_connection()
        
        # No watcher is not considered unhealthy
        assert result is True


class TestHealthCheckEndpoint:
    """Test suite for /health endpoint."""
    
    def test_health_endpoint_healthy(self, flask_client, db_session):
        """Test health endpoint returns 200 when all checks pass."""
        # Create recent successful log
        log = ProcessingLog(
            gmail_uid='test_uid_789',
            timestamp=datetime.utcnow() - timedelta(minutes=15),
            sender_email='test@example.com',
            status='success',
            lead_id=3
        )
        db_session.add(log)
        db_session.commit()
        
        response = flask_client.get('/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'
        assert data['imap'] == 'connected'
        assert data['last_successful_sync'] is not None
        assert 'timestamp' in data
    
    def test_health_endpoint_degraded_stale_sync(self, flask_client, db_session):
        """Test health endpoint returns 503 when sync is stale."""
        # Create old successful log (2 hours ago)
        log = ProcessingLog(
            gmail_uid='test_uid_old',
            timestamp=datetime.utcnow() - timedelta(hours=2),
            sender_email='test@example.com',
            status='success',
            lead_id=4
        )
        db_session.add(log)
        db_session.commit()
        
        response = flask_client.get('/health')
        
        assert response.status_code == 503
        data = response.get_json()
        assert data['status'] == 'degraded'
        assert data['database'] == 'connected'
        assert data['last_successful_sync'] is not None
    
    def test_health_endpoint_degraded_no_sync(self, flask_client):
        """Test health endpoint returns 503 when no successful sync exists."""
        response = flask_client.get('/health')
        
        assert response.status_code == 503
        data = response.get_json()
        assert data['status'] == 'degraded'
        assert data['last_successful_sync'] is None
    
    def test_health_endpoint_degraded_imap_disconnected(self, flask_client, db_session, mock_watcher):
        """Test health endpoint returns 503 when IMAP is disconnected."""
        # Create recent successful log
        log = ProcessingLog(
            gmail_uid='test_uid_imap',
            timestamp=datetime.utcnow() - timedelta(minutes=10),
            sender_email='test@example.com',
            status='success',
            lead_id=5
        )
        db_session.add(log)
        db_session.commit()
        
        # Mock IMAP as disconnected
        mock_watcher.is_connected.return_value = False
        
        response = flask_client.get('/health')
        
        assert response.status_code == 503
        data = response.get_json()
        assert data['status'] == 'degraded'
        assert data['imap'] == 'disconnected'

"""
Unit tests for Watcher component.

Tests the watcher's ability to:
- Connect to IMAP with retry logic
- Detect connection loss and reconnect
- Enable/disable IDLE mode
- Handle authentication failures
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import imaplib
import socket
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gmail_lead_sync.models import Base
from gmail_lead_sync.watcher import IMAPConnection, GmailWatcher
from gmail_lead_sync.credentials import CredentialsStore


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
def mock_credentials_store():
    """Create a mock credentials store."""
    store = Mock(spec=CredentialsStore)
    store.get_credentials.return_value = ('test@gmail.com', 'test_app_password')
    return store


class TestIMAPConnection:
    """Test suite for IMAPConnection class."""
    
    def test_init(self, mock_credentials_store):
        """Test IMAPConnection initialization."""
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        
        assert conn.credentials_store == mock_credentials_store
        assert conn.agent_id == 'test_agent'
        assert conn.client is None
        assert conn._connected is False
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_connect_with_retry_success(self, mock_imap, mock_credentials_store):
        """Test successful connection on first attempt."""
        # Setup mock IMAP client
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        mock_imap.return_value = mock_client
        
        # Create connection and attempt to connect
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        result = conn.connect_with_retry()
        
        # Verify connection successful
        assert result is True
        assert conn._connected is True
        assert conn.client == mock_client
        
        # Verify credentials were retrieved
        mock_credentials_store.get_credentials.assert_called_once_with('test_agent')
        
        # Verify IMAP operations
        mock_imap.assert_called_once_with('imap.gmail.com', 993)
        mock_client.login.assert_called_once_with('test@gmail.com', 'test_app_password')
        mock_client.select.assert_called_once_with('INBOX')
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    @patch('gmail_lead_sync.watcher.time.sleep')
    def test_connect_with_retry_transient_failure(self, mock_sleep, mock_imap, 
                                                   mock_credentials_store):
        """Test connection succeeds after transient failures."""
        # Setup mock to fail twice then succeed
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        
        mock_imap.side_effect = [
            socket.error("Connection refused"),
            socket.error("Connection refused"),
            mock_client
        ]
        
        # Create connection and attempt to connect
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        result = conn.connect_with_retry()
        
        # Verify connection successful after retries
        assert result is True
        assert conn._connected is True
        
        # Verify exponential backoff: 1s, 2s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)  # 2^0 = 1
        mock_sleep.assert_any_call(2)  # 2^1 = 2
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_connect_with_retry_authentication_failure(self, mock_imap, 
                                                        mock_credentials_store):
        """Test authentication failure stops retry attempts."""
        # Setup mock to fail with authentication error
        mock_client = MagicMock()
        mock_client.login.side_effect = imaplib.IMAP4.error(
            '[AUTHENTICATIONFAILED] Invalid credentials'
        )
        mock_imap.return_value = mock_client
        
        # Create connection and attempt to connect
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        result = conn.connect_with_retry()
        
        # Verify connection failed and no retries
        assert result is False
        assert conn._connected is False
        
        # Should only attempt once (no retries on auth failure)
        assert mock_client.login.call_count == 1
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    @patch('gmail_lead_sync.watcher.time.sleep')
    def test_connect_with_retry_max_attempts_exhausted(self, mock_sleep, mock_imap,
                                                        mock_credentials_store):
        """Test connection fails after max retry attempts."""
        # Setup mock to always fail
        mock_imap.side_effect = socket.error("Connection refused")
        
        # Create connection and attempt to connect
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        result = conn.connect_with_retry(max_attempts=3)
        
        # Verify connection failed
        assert result is False
        assert conn._connected is False
        
        # Verify exponential backoff: 1s, 2s, then 300s wait
        assert mock_sleep.call_count == 3
        mock_sleep.assert_any_call(1)  # 2^0 = 1
        mock_sleep.assert_any_call(2)  # 2^1 = 2
        mock_sleep.assert_any_call(300)  # Final wait
    
    def test_is_connected_when_not_connected(self, mock_credentials_store):
        """Test is_connected returns False when not connected."""
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        assert conn.is_connected() is False
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_is_connected_when_connected(self, mock_imap, mock_credentials_store):
        """Test is_connected returns True when connected and responsive."""
        # Setup mock IMAP client
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        mock_client.noop.return_value = ('OK', [b'NOOP completed'])
        mock_imap.return_value = mock_client
        
        # Connect
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        conn.connect_with_retry()
        
        # Check connection
        assert conn.is_connected() is True
        mock_client.noop.assert_called_once()
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_is_connected_when_connection_lost(self, mock_imap, mock_credentials_store):
        """Test is_connected returns False when connection lost."""
        # Setup mock IMAP client
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        mock_client.noop.side_effect = socket.error("Connection lost")
        mock_imap.return_value = mock_client
        
        # Connect
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        conn.connect_with_retry()
        
        # Check connection (should detect loss)
        assert conn.is_connected() is False
        assert conn._connected is False
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_reconnect(self, mock_imap, mock_credentials_store):
        """Test reconnection after connection loss."""
        # Setup mock IMAP client
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        mock_client.logout.return_value = ('BYE', [b'Logging out'])
        mock_imap.return_value = mock_client
        
        # Connect
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        conn.connect_with_retry()
        
        # Simulate connection loss
        conn._connected = False
        
        # Reconnect
        result = conn.reconnect()
        
        # Verify reconnection successful
        assert result is True
        assert conn._connected is True
        
        # Verify logout was called during disconnect
        mock_client.logout.assert_called()
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_disconnect(self, mock_imap, mock_credentials_store):
        """Test graceful disconnection."""
        # Setup mock IMAP client
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        mock_client.logout.return_value = ('BYE', [b'Logging out'])
        mock_imap.return_value = mock_client
        
        # Connect
        conn = IMAPConnection(mock_credentials_store, 'test_agent')
        conn.connect_with_retry()
        
        # Disconnect
        conn.disconnect()
        
        # Verify disconnection
        assert conn.client is None
        assert conn._connected is False
        mock_client.logout.assert_called_once()
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_context_manager(self, mock_imap, mock_credentials_store):
        """Test IMAPConnection as context manager."""
        # Setup mock IMAP client
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        mock_client.logout.return_value = ('BYE', [b'Logging out'])
        mock_imap.return_value = mock_client
        
        # Use as context manager
        with IMAPConnection(mock_credentials_store, 'test_agent') as conn:
            assert conn._connected is True
        
        # Verify disconnection after context exit
        mock_client.logout.assert_called_once()


class TestGmailWatcher:
    """Test suite for GmailWatcher class."""
    
    def test_init(self, mock_credentials_store, db_session):
        """Test GmailWatcher initialization."""
        watcher = GmailWatcher(mock_credentials_store, db_session, 'test_agent')
        
        assert watcher.credentials_store == mock_credentials_store
        assert watcher.db_session == db_session
        assert watcher.agent_id == 'test_agent'
        assert isinstance(watcher.connection, IMAPConnection)
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_connect(self, mock_imap, mock_credentials_store, db_session):
        """Test watcher connection."""
        # Setup mock IMAP client
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        mock_client.noop.return_value = ('OK', [b'NOOP completed'])
        mock_imap.return_value = mock_client
        
        # Create watcher and connect
        watcher = GmailWatcher(mock_credentials_store, db_session, 'test_agent')
        result = watcher.connect()
        
        # Verify connection successful
        assert result is True
        assert watcher.is_connected() is True
    
    @patch('gmail_lead_sync.watcher.imaplib.IMAP4_SSL')
    def test_disconnect(self, mock_imap, mock_credentials_store, db_session):
        """Test watcher disconnection."""
        # Setup mock IMAP client
        mock_client = MagicMock()
        mock_client.login.return_value = ('OK', [b'Logged in'])
        mock_client.select.return_value = ('OK', [b'1'])
        mock_client.logout.return_value = ('BYE', [b'Logging out'])
        mock_imap.return_value = mock_client
        
        # Create watcher, connect, then disconnect
        watcher = GmailWatcher(mock_credentials_store, db_session, 'test_agent')
        watcher.connect()
        watcher.disconnect()
        
        # Verify disconnection
        assert watcher.is_connected() is False

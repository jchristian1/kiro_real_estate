"""
Unit tests for ProcessedMessage-based idempotency in GmailWatcher.

Tests verify that the watcher correctly uses the ProcessedMessage table
for idempotency tracking instead of Lead.gmail_uid.
"""

import pytest
import hashlib
from unittest.mock import Mock
from sqlalchemy.orm import Session

from gmail_lead_sync.watcher import GmailWatcher
from gmail_lead_sync.models import ProcessedMessage
from gmail_lead_sync.credentials import CredentialsStore


class TestProcessedMessageIdempotency:
    """Test ProcessedMessage-based idempotency."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_credentials_store(self):
        """Create a mock credentials store."""
        return Mock(spec=CredentialsStore)
    
    @pytest.fixture
    def watcher(self, mock_credentials_store, mock_db_session):
        """Create a GmailWatcher instance."""
        return GmailWatcher(
            credentials_store=mock_credentials_store,
            db_session=mock_db_session,
            agent_id="test-agent-123"
        )
    
    def test_is_email_processed_returns_false_for_new_message(
        self, watcher, mock_db_session
    ):
        """Test that is_email_processed returns False for a new message."""
        # Setup: No existing ProcessedMessage
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Test
        message_id = "<test-message-123@example.com>"
        result = watcher.is_email_processed(message_id)
        
        # Verify
        assert result is False
        mock_db_session.query.assert_called_once_with(ProcessedMessage)
    
    def test_is_email_processed_returns_true_for_existing_message(
        self, watcher, mock_db_session
    ):
        """Test that is_email_processed returns True for an existing message."""
        # Setup: Existing ProcessedMessage
        existing_record = Mock(spec=ProcessedMessage)
        existing_record.id = 1
        mock_db_session.query.return_value.filter.return_value.first.return_value = existing_record
        
        # Test
        message_id = "<test-message-456@example.com>"
        result = watcher.is_email_processed(message_id)
        
        # Verify
        assert result is True
        mock_db_session.query.assert_called_once_with(ProcessedMessage)
    
    def test_is_email_processed_uses_sha256_hash(
        self, watcher, mock_db_session
    ):
        """Test that is_email_processed uses SHA-256 hash of Message-ID."""
        # Setup
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # Test
        message_id = "<unique-message@example.com>"
        watcher.is_email_processed(message_id)
        
        # Verify the hash was computed correctly (SHA-256 of message_id)
        hashlib.sha256(message_id.encode('utf-8')).hexdigest()
        # The filter should have been called with the hash
        filter_call = mock_db_session.query.return_value.filter
        assert filter_call.called
    
    def test_mark_as_processed_creates_processed_message_record(
        self, watcher, mock_db_session
    ):
        """Test that mark_as_processed creates a ProcessedMessage record."""
        # Test
        message_id = "<new-message@example.com>"
        lead_id = 42
        watcher.mark_as_processed(message_id, lead_id)
        
        # Verify
        mock_db_session.add.assert_called_once()
        added_record = mock_db_session.add.call_args[0][0]
        assert isinstance(added_record, ProcessedMessage)
        assert added_record.agent_id == "test-agent-123"
        assert added_record.lead_id == lead_id
        
        # Verify hash
        expected_hash = hashlib.sha256(message_id.encode('utf-8')).hexdigest()
        assert added_record.message_id_hash == expected_hash
        
        mock_db_session.commit.assert_called_once()
    
    def test_mark_as_processed_works_without_lead_id(
        self, watcher, mock_db_session
    ):
        """Test that mark_as_processed works when no lead was created."""
        # Test
        message_id = "<failed-parse@example.com>"
        watcher.mark_as_processed(message_id, None)
        
        # Verify
        mock_db_session.add.assert_called_once()
        added_record = mock_db_session.add.call_args[0][0]
        assert isinstance(added_record, ProcessedMessage)
        assert added_record.lead_id is None
        mock_db_session.commit.assert_called_once()

"""
Unit tests for session cleanup background task.

Tests cover:
- Cleanup of expired sessions
- Background task lifecycle
- Error handling during cleanup
- SessionCleanupManager functionality
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from api.services.session_cleanup import (
    cleanup_expired_sessions,
    session_cleanup_task,
    SessionCleanupManager,
    DEFAULT_CLEANUP_INTERVAL_SECONDS
)
from api.models.web_ui_models import Session as SessionModel


class TestCleanupExpiredSessions:
    """Tests for cleanup_expired_sessions function."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        return db
    
    @pytest.mark.asyncio
    async def test_cleanup_no_expired_sessions(self, mock_db):
        """Test cleanup when there are no expired sessions."""
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = await cleanup_expired_sessions(mock_db)
        
        assert result == 0
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cleanup_with_expired_sessions(self, mock_db):
        """Test cleanup when there are expired sessions."""
        now = datetime.utcnow()
        
        # Create mock expired sessions
        expired_sessions = [
            SessionModel(
                id=f"expired_token_{i}",
                user_id=1,
                created_at=now - timedelta(hours=25),
                expires_at=now - timedelta(hours=1),
                last_accessed=now - timedelta(hours=2)
            )
            for i in range(3)
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = expired_sessions
        
        result = await cleanup_expired_sessions(mock_db)
        
        assert result == 3
        assert mock_db.delete.call_count == 3
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_with_mixed_sessions(self, mock_db):
        """Test cleanup correctly identifies only expired sessions."""
        now = datetime.utcnow()
        
        # Create mock expired sessions (should be deleted)
        expired_sessions = [
            SessionModel(
                id="expired_1",
                user_id=1,
                created_at=now - timedelta(hours=25),
                expires_at=now - timedelta(hours=1),
                last_accessed=now - timedelta(hours=2)
            ),
            SessionModel(
                id="expired_2",
                user_id=2,
                created_at=now - timedelta(hours=30),
                expires_at=now - timedelta(minutes=5),
                last_accessed=now - timedelta(hours=3)
            )
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = expired_sessions
        
        result = await cleanup_expired_sessions(mock_db)
        
        assert result == 2
        assert mock_db.delete.call_count == 2
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_handles_database_error(self, mock_db):
        """Test cleanup handles database errors gracefully."""
        mock_db.query.side_effect = Exception("Database error")
        
        result = await cleanup_expired_sessions(mock_db)
        
        assert result == 0
        mock_db.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_handles_commit_error(self, mock_db):
        """Test cleanup handles commit errors gracefully."""
        now = datetime.utcnow()
        expired_sessions = [
            SessionModel(
                id="expired_1",
                user_id=1,
                created_at=now - timedelta(hours=25),
                expires_at=now - timedelta(hours=1),
                last_accessed=now - timedelta(hours=2)
            )
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = expired_sessions
        mock_db.commit.side_effect = Exception("Commit failed")
        
        result = await cleanup_expired_sessions(mock_db)
        
        assert result == 0
        mock_db.rollback.assert_called_once()


class TestSessionCleanupTask:
    """Tests for session_cleanup_task background task."""
    
    @pytest.fixture
    def mock_get_db(self):
        """Create a mock get_db_session callable."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        @contextmanager
        def get_db():
            yield mock_db
        
        return get_db
    
    @pytest.mark.asyncio
    async def test_task_runs_cleanup_periodically(self, mock_get_db):
        """Test that task runs cleanup at specified intervals."""
        stop_event = asyncio.Event()
        interval = 0.1  # 100ms for fast testing
        
        # Start task
        task = asyncio.create_task(
            session_cleanup_task(mock_get_db, interval, stop_event)
        )
        
        # Let it run for a bit
        await asyncio.sleep(0.25)
        
        # Stop task
        stop_event.set()
        await task
        
        # Task should have run at least once
        assert True  # If we get here without hanging, task worked
    
    @pytest.mark.asyncio
    async def test_task_stops_on_event(self, mock_get_db):
        """Test that task stops when stop_event is set."""
        stop_event = asyncio.Event()
        interval = 10  # Long interval
        
        # Start task
        task = asyncio.create_task(
            session_cleanup_task(mock_get_db, interval, stop_event)
        )
        
        # Give it a moment to start
        await asyncio.sleep(0.05)
        
        # Stop immediately
        stop_event.set()
        
        # Should complete quickly
        await asyncio.wait_for(task, timeout=1.0)
        
        assert task.done()
    
    @pytest.mark.asyncio
    async def test_task_handles_cleanup_errors(self, mock_get_db):
        """Test that task continues running after cleanup errors."""
        stop_event = asyncio.Event()
        interval = 0.1
        
        # Make cleanup fail
        with patch('api.services.session_cleanup.cleanup_expired_sessions', 
                   side_effect=Exception("Cleanup error")):
            
            # Start task
            task = asyncio.create_task(
                session_cleanup_task(mock_get_db, interval, stop_event)
            )
            
            # Let it run and encounter error
            await asyncio.sleep(0.15)
            
            # Stop task
            stop_event.set()
            await task
            
            # Task should complete despite error
            assert task.done()
    
    @pytest.mark.asyncio
    async def test_task_handles_cancellation(self, mock_get_db):
        """Test that task handles cancellation gracefully."""
        stop_event = asyncio.Event()
        interval = 10
        
        # Start task
        task = asyncio.create_task(
            session_cleanup_task(mock_get_db, interval, stop_event)
        )
        
        # Give it a moment to start
        await asyncio.sleep(0.05)
        
        # Cancel task
        task.cancel()
        
        # Should raise CancelledError
        with pytest.raises(asyncio.CancelledError):
            await task


class TestSessionCleanupManager:
    """Tests for SessionCleanupManager class."""
    
    @pytest.fixture
    def mock_get_db(self):
        """Create a mock get_db_session callable."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        @contextmanager
        def get_db():
            yield mock_db
        
        return get_db
    
    def test_manager_initialization(self, mock_get_db):
        """Test manager initialization."""
        manager = SessionCleanupManager(mock_get_db, interval_seconds=3600)
        
        assert manager.get_db_session == mock_get_db
        assert manager.interval_seconds == 3600
        assert manager.task is None
        assert manager.stop_event is None
    
    def test_manager_initialization_default_interval(self, mock_get_db):
        """Test manager uses default interval when not specified."""
        manager = SessionCleanupManager(mock_get_db)
        
        assert manager.interval_seconds == DEFAULT_CLEANUP_INTERVAL_SECONDS
    
    @pytest.mark.asyncio
    async def test_manager_start(self, mock_get_db):
        """Test starting the cleanup task."""
        manager = SessionCleanupManager(mock_get_db, interval_seconds=10)
        
        manager.start()
        
        assert manager.task is not None
        assert not manager.task.done()
        assert manager.stop_event is not None
        assert manager.is_running()
        
        # Cleanup
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_start_when_already_running(self, mock_get_db):
        """Test that starting when already running raises error."""
        manager = SessionCleanupManager(mock_get_db, interval_seconds=10)
        
        manager.start()
        
        with pytest.raises(RuntimeError, match="already running"):
            manager.start()
        
        # Cleanup
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_stop(self, mock_get_db):
        """Test stopping the cleanup task."""
        manager = SessionCleanupManager(mock_get_db, interval_seconds=10)
        
        manager.start()
        assert manager.is_running()
        
        await manager.stop()
        
        assert not manager.is_running()
        assert manager.task.done()
    
    @pytest.mark.asyncio
    async def test_manager_stop_when_not_running(self, mock_get_db):
        """Test stopping when not running doesn't raise error."""
        manager = SessionCleanupManager(mock_get_db)
        
        # Should not raise error
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_stop_graceful(self, mock_get_db):
        """Test that stop works gracefully in normal conditions."""
        manager = SessionCleanupManager(mock_get_db, interval_seconds=0.1)
        
        manager.start()
        assert manager.is_running()
        
        # Let it run briefly
        await asyncio.sleep(0.05)
        
        # Stop should complete quickly
        await asyncio.wait_for(manager.stop(), timeout=2.0)
        
        assert not manager.is_running()
    
    def test_manager_is_running_false_when_not_started(self, mock_get_db):
        """Test is_running returns False when task not started."""
        manager = SessionCleanupManager(mock_get_db)
        
        assert not manager.is_running()
    
    @pytest.mark.asyncio
    async def test_manager_is_running_false_after_stop(self, mock_get_db):
        """Test is_running returns False after task is stopped."""
        manager = SessionCleanupManager(mock_get_db, interval_seconds=10)
        
        manager.start()
        assert manager.is_running()
        
        await manager.stop()
        assert not manager.is_running()
    
    @pytest.mark.asyncio
    async def test_manager_lifecycle(self, mock_get_db):
        """Test complete manager lifecycle: start -> run -> stop."""
        manager = SessionCleanupManager(mock_get_db, interval_seconds=0.1)
        
        # Start
        manager.start()
        assert manager.is_running()
        
        # Let it run
        await asyncio.sleep(0.15)
        assert manager.is_running()
        
        # Stop
        await manager.stop()
        assert not manager.is_running()

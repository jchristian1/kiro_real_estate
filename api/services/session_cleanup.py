"""
Session cleanup background task.

This module provides a background task that periodically removes expired
sessions from the database to prevent accumulation of stale session records.

The cleanup task runs at a configurable interval and deletes all sessions
where expires_at < current time.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.models.web_ui_models import Session as SessionModel


logger = logging.getLogger(__name__)


# Default cleanup interval: 1 hour
DEFAULT_CLEANUP_INTERVAL_SECONDS = 3600


async def cleanup_expired_sessions(db: Session) -> int:
    """
    Delete all expired sessions from the database.
    
    Args:
        db: Database session
        
    Returns:
        Number of sessions deleted
        
    Example:
        >>> deleted_count = await cleanup_expired_sessions(db)
        >>> print(f"Deleted {deleted_count} expired sessions")
    """
    try:
        now = datetime.utcnow()
        
        # Query for expired sessions
        expired_sessions = db.query(SessionModel).filter(
            SessionModel.expires_at < now
        ).all()
        
        count = len(expired_sessions)
        
        if count > 0:
            # Delete expired sessions
            for session in expired_sessions:
                db.delete(session)
            
            db.commit()
            logger.info(f"Cleaned up {count} expired sessions")
        else:
            logger.debug("No expired sessions to clean up")
        
        return count
        
    except Exception as e:
        logger.error(f"Error during session cleanup: {e}", exc_info=True)
        db.rollback()
        return 0


async def session_cleanup_task(
    get_db_session: callable,
    interval_seconds: int = DEFAULT_CLEANUP_INTERVAL_SECONDS,
    stop_event: Optional[asyncio.Event] = None
) -> None:
    """
    Background task that periodically cleans up expired sessions.
    
    This task runs in a loop, sleeping for the specified interval between
    cleanup operations. It can be gracefully stopped using the stop_event.
    
    Args:
        get_db_session: Callable that returns a database session (context manager)
        interval_seconds: Time to wait between cleanup operations (default: 3600)
        stop_event: Optional asyncio.Event to signal task shutdown
        
    Example:
        >>> stop_event = asyncio.Event()
        >>> task = asyncio.create_task(
        ...     session_cleanup_task(get_db, interval_seconds=3600, stop_event=stop_event)
        ... )
        >>> # Later, to stop the task:
        >>> stop_event.set()
        >>> await task
    """
    logger.info(f"Session cleanup task started (interval: {interval_seconds}s)")
    
    if stop_event is None:
        stop_event = asyncio.Event()
    
    try:
        while not stop_event.is_set():
            # Wait for the interval or until stop is signaled
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval_seconds
                )
                # If we get here, stop was signaled
                break
            except asyncio.TimeoutError:
                # Timeout is expected - time to run cleanup
                pass
            
            # Run cleanup
            try:
                with get_db_session() as db:
                    deleted_count = await cleanup_expired_sessions(db)
                    
                    if deleted_count > 0:
                        logger.info(f"Session cleanup completed: {deleted_count} sessions removed")
                        
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}", exc_info=True)
                # Continue running despite errors
    
    except asyncio.CancelledError:
        logger.info("Session cleanup task cancelled")
        raise
    
    finally:
        logger.info("Session cleanup task stopped")


class SessionCleanupManager:
    """
    Manager for the session cleanup background task.
    
    Provides methods to start and stop the cleanup task, and tracks its state.
    """
    
    def __init__(self, get_db_session: callable, interval_seconds: int = DEFAULT_CLEANUP_INTERVAL_SECONDS):
        """
        Initialize the session cleanup manager.
        
        Args:
            get_db_session: Callable that returns a database session (context manager)
            interval_seconds: Time to wait between cleanup operations (default: 3600)
        """
        self.get_db_session = get_db_session
        self.interval_seconds = interval_seconds
        self.task: Optional[asyncio.Task] = None
        self.stop_event: Optional[asyncio.Event] = None
    
    def start(self) -> None:
        """
        Start the session cleanup background task.
        
        Raises:
            RuntimeError: If task is already running
        """
        if self.task is not None and not self.task.done():
            raise RuntimeError("Session cleanup task is already running")
        
        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(
            session_cleanup_task(
                self.get_db_session,
                self.interval_seconds,
                self.stop_event
            )
        )
        logger.info("Session cleanup manager started")
    
    async def stop(self) -> None:
        """
        Stop the session cleanup background task gracefully.
        
        Waits for the task to complete before returning.
        """
        if self.task is None or self.task.done():
            logger.warning("Session cleanup task is not running")
            return
        
        logger.info("Stopping session cleanup task...")
        self.stop_event.set()
        
        try:
            await asyncio.wait_for(self.task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Session cleanup task did not stop gracefully, cancelling...")
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        logger.info("Session cleanup manager stopped")
    
    def is_running(self) -> bool:
        """
        Check if the cleanup task is currently running.
        
        Returns:
            True if task is running, False otherwise
        """
        return self.task is not None and not self.task.done()

"""
Watcher registry for managing background Gmail watcher tasks.

This module provides a registry for managing background tasks that run
GmailWatcher instances. It handles watcher lifecycle (start, stop, status),
prevents multiple concurrent watchers for the same agent, and tracks
heartbeat and sync timestamps.

Requirements: 4.2, 4.3, 4.4, 4.7, 20.1, 20.2
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass

from sqlalchemy.orm import Session

from gmail_lead_sync.watcher import GmailWatcher
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore


logger = logging.getLogger(__name__)


class WatcherStatus(str, Enum):
    """Status of a watcher task."""
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    STARTING = "starting"


@dataclass
class WatcherInfo:
    """Information about a watcher task."""
    agent_id: str
    status: WatcherStatus
    task: Optional[asyncio.Task]
    last_heartbeat: Optional[datetime]
    last_sync: Optional[datetime]
    error: Optional[str]
    started_at: Optional[datetime]
    retry_count: int = 0
    last_error: Optional[str] = None


class WatcherRegistry:
    """
    Registry for managing background watcher tasks.
    
    This class maintains a dictionary of active watchers keyed by agent_id,
    tracks watcher status, heartbeat timestamps, and last sync timestamps.
    It prevents starting multiple watchers for the same agent and provides
    methods for watcher lifecycle management.
    
    Requirements: 4.2, 4.3, 4.4, 4.7, 20.1, 20.2, 20.3, 20.4, 20.5, 8.7
    """
    
    MAX_RETRIES = 3
    RETRY_DELAYS = [10, 30, 60]  # Exponential backoff in seconds
    
    def __init__(self, get_db_session: callable, credentials_store: EncryptedDBCredentialsStore):
        """
        Initialize the watcher registry.
        
        Args:
            get_db_session: Callable that returns a database session (context manager)
            credentials_store: Store for retrieving Gmail credentials
        """
        self._watchers: Dict[str, WatcherInfo] = {}
        self._lock = asyncio.Lock()
        self.get_db_session = get_db_session
        self.credentials_store = credentials_store
        logger.info("WatcherRegistry initialized")
    
    async def start_watcher(self, agent_id: str) -> bool:
        """
        Start a watcher background task for the specified agent.
        
        This method creates a new background task that runs the GmailWatcher
        for the specified agent. It prevents starting multiple concurrent
        watchers for the same agent. When manually started, retry count is reset.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            True if watcher was started successfully, False if already running
            
        Requirements: 4.2, 4.4, 20.5
        """
        async with self._lock:
            # Check if watcher already exists and is running
            if agent_id in self._watchers:
                watcher_info = self._watchers[agent_id]
                if watcher_info.status in (WatcherStatus.RUNNING, WatcherStatus.STARTING):
                    logger.warning(f"Watcher for agent {agent_id} is already {watcher_info.status}")
                    return False
            
            # Create watcher info (reset retry count on manual start)
            watcher_info = WatcherInfo(
                agent_id=agent_id,
                status=WatcherStatus.STARTING,
                task=None,
                last_heartbeat=None,
                last_sync=None,
                error=None,
                started_at=datetime.utcnow(),
                retry_count=0,
                last_error=None
            )
            
            # Create background task
            task = asyncio.create_task(self._run_watcher(agent_id))
            watcher_info.task = task
            
            # Store in registry
            self._watchers[agent_id] = watcher_info
            
            logger.info(f"Started watcher for agent {agent_id}")
            return True
    
    async def stop_watcher(self, agent_id: str) -> bool:
        """
        Gracefully stop the watcher task for the specified agent.
        
        This method cancels the background task and waits for it to complete.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            True if watcher was stopped successfully, False if not running
            
        Requirements: 4.3
        """
        async with self._lock:
            if agent_id not in self._watchers:
                logger.warning(f"No watcher found for agent {agent_id}")
                return False
            
            watcher_info = self._watchers[agent_id]
            
            if watcher_info.status == WatcherStatus.STOPPED:
                logger.warning(f"Watcher for agent {agent_id} is already stopped")
                return False
            
            # Cancel the task
            if watcher_info.task and not watcher_info.task.done():
                logger.info(f"Stopping watcher for agent {agent_id}")
                watcher_info.task.cancel()
                
                try:
                    await asyncio.wait_for(watcher_info.task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Watcher for agent {agent_id} did not stop gracefully")
                except asyncio.CancelledError:
                    pass
            
            # Update status
            watcher_info.status = WatcherStatus.STOPPED
            watcher_info.task = None
            
            logger.info(f"Stopped watcher for agent {agent_id}")
            return True
    
    async def get_status(self, agent_id: str) -> Optional[Dict]:
        """
        Get the current status of a watcher.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            Dictionary with status information, or None if watcher not found
            
        Requirements: 4.7
        """
        async with self._lock:
            if agent_id not in self._watchers:
                return None
            
            watcher_info = self._watchers[agent_id]
            
            return {
                "agent_id": agent_id,
                "status": watcher_info.status.value,
                "last_heartbeat": watcher_info.last_heartbeat.isoformat() if watcher_info.last_heartbeat else None,
                "last_sync": watcher_info.last_sync.isoformat() if watcher_info.last_sync else None,
                "error": watcher_info.error,
                "started_at": watcher_info.started_at.isoformat() if watcher_info.started_at else None,
                "retry_count": watcher_info.retry_count,
                "last_error": watcher_info.last_error
            }
    
    async def get_all_statuses(self) -> Dict[str, Dict]:
        """
        Get the status of all watchers.
        
        Returns:
            Dictionary mapping agent_id to status information
            
        Requirements: 4.7
        """
        async with self._lock:
            statuses = {}
            for agent_id, watcher_info in self._watchers.items():
                statuses[agent_id] = {
                    "agent_id": agent_id,
                    "status": watcher_info.status.value,
                    "last_heartbeat": watcher_info.last_heartbeat.isoformat() if watcher_info.last_heartbeat else None,
                    "last_sync": watcher_info.last_sync.isoformat() if watcher_info.last_sync else None,
                    "error": watcher_info.error,
                    "started_at": watcher_info.started_at.isoformat() if watcher_info.started_at else None,
                    "retry_count": watcher_info.retry_count,
                    "last_error": watcher_info.last_error
                }
            return statuses
    
    async def trigger_sync(self, agent_id: str) -> bool:
        """
        Trigger a manual sync operation for the specified agent.
        
        This method signals the watcher to perform an immediate sync
        operation outside of its normal schedule.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            True if sync was triggered successfully, False if watcher not running
        """
        async with self._lock:
            if agent_id not in self._watchers:
                logger.warning(f"No watcher found for agent {agent_id}")
                return False
            
            watcher_info = self._watchers[agent_id]
            
            if watcher_info.status != WatcherStatus.RUNNING:
                logger.warning(f"Watcher for agent {agent_id} is not running (status: {watcher_info.status})")
                return False
            
            # For now, we'll just log the sync trigger
            # In a full implementation, this would signal the watcher task
            logger.info(f"Manual sync triggered for agent {agent_id}")
            return True
    
    async def stop_all(self) -> None:
        """
        Stop all running watchers gracefully.
        
        This method is called during application shutdown to ensure
        all background tasks are properly terminated.
        
        Requirements: 20.3
        """
        logger.info("Stopping all watchers...")
        
        async with self._lock:
            agent_ids = list(self._watchers.keys())
        
        # Stop each watcher (releases lock between stops)
        for agent_id in agent_ids:
            try:
                await self.stop_watcher(agent_id)
            except Exception as e:
                logger.error(f"Error stopping watcher for agent {agent_id}: {e}", exc_info=True)
        
        logger.info("All watchers stopped")
    
    async def _run_watcher(self, agent_id: str) -> None:
        """
        Background task that runs the GmailWatcher for an agent.
        
        This method runs in a loop, periodically checking for new emails
        and updating heartbeat timestamps. It handles errors and updates
        the watcher status accordingly. Failed watchers are automatically
        restarted up to MAX_RETRIES times with exponential backoff.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 8.7
        """
        logger.info(f"Watcher task started for agent {agent_id}")
        
        watcher = None
        
        try:
            # Create database session
            with self.get_db_session() as db_session:
                # Create GmailWatcher instance
                watcher = GmailWatcher(
                    credentials_store=self.credentials_store,
                    db_session=db_session,
                    agent_id=agent_id
                )
                
                # Connect to Gmail
                if not watcher.connect():
                    raise Exception("Failed to connect to Gmail IMAP server")
                
                # Update status to running
                async with self._lock:
                    if agent_id in self._watchers:
                        self._watchers[agent_id].status = WatcherStatus.RUNNING
                        self._watchers[agent_id].last_heartbeat = datetime.utcnow()
                        self._watchers[agent_id].error = None
                
                logger.info(f"Watcher for agent {agent_id} connected and running")
                
                # Get list of lead source senders
                from gmail_lead_sync.models import LeadSource
                lead_sources = db_session.query(LeadSource).all()
                sender_list = [ls.sender_email for ls in lead_sources]
                
                if not sender_list:
                    logger.warning(f"No lead sources configured for agent {agent_id}")
                
                # Main monitoring loop
                while True:
                    try:
                        # Update heartbeat
                        async with self._lock:
                            if agent_id in self._watchers:
                                self._watchers[agent_id].last_heartbeat = datetime.utcnow()
                        
                        # Process unseen emails
                        if sender_list:
                            watcher.process_unseen_emails(sender_list)
                            
                            # Update last sync timestamp
                            async with self._lock:
                                if agent_id in self._watchers:
                                    self._watchers[agent_id].last_sync = datetime.utcnow()
                        
                        # Sleep for 60 seconds before next check
                        await asyncio.sleep(60)
                        
                    except asyncio.CancelledError:
                        logger.info(f"Watcher task for agent {agent_id} cancelled")
                        raise
                    
                    except Exception as e:
                        logger.error(f"Error in watcher loop for agent {agent_id}: {e}", exc_info=True)
                        # Continue running despite errors
                        await asyncio.sleep(60)
        
        except asyncio.CancelledError:
            logger.info(f"Watcher task for agent {agent_id} cancelled")
            # Update status
            async with self._lock:
                if agent_id in self._watchers:
                    self._watchers[agent_id].status = WatcherStatus.STOPPED
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Fatal error in watcher task for agent {agent_id}: {error_msg}", exc_info=True)
            
            # Update status to failed and record error
            async with self._lock:
                if agent_id in self._watchers:
                    watcher_info = self._watchers[agent_id]
                    watcher_info.status = WatcherStatus.FAILED
                    watcher_info.error = error_msg
                    watcher_info.last_error = error_msg
                    
                    # Check if we should retry
                    if watcher_info.retry_count < self.MAX_RETRIES:
                        retry_delay = self.RETRY_DELAYS[min(watcher_info.retry_count, len(self.RETRY_DELAYS) - 1)]
                        watcher_info.retry_count += 1
                        
                        logger.info(
                            f"Scheduling auto-restart for agent {agent_id} "
                            f"(retry {watcher_info.retry_count}/{self.MAX_RETRIES}) "
                            f"in {retry_delay} seconds"
                        )
                        
                        # Schedule restart after delay
                        asyncio.create_task(self._auto_restart_watcher(agent_id, retry_delay))
                    else:
                        logger.error(
                            f"Watcher for agent {agent_id} failed permanently after "
                            f"{self.MAX_RETRIES} retries. Error: {error_msg}"
                        )
        
        finally:
            # Disconnect from Gmail
            if watcher:
                try:
                    watcher.disconnect()
                    logger.info(f"Watcher for agent {agent_id} disconnected")
                except Exception as e:
                    logger.error(f"Error disconnecting watcher for agent {agent_id}: {e}", exc_info=True)
            
            logger.info(f"Watcher task stopped for agent {agent_id}")
    
    async def _auto_restart_watcher(self, agent_id: str, delay: int) -> None:
        """
        Automatically restart a failed watcher after a delay.
        
        This method is called when a watcher fails and has retries remaining.
        It waits for the specified delay, then attempts to restart the watcher.
        
        Args:
            agent_id: Unique identifier for the agent
            delay: Delay in seconds before restarting
            
        Requirements: 20.4, 20.5
        """
        try:
            logger.info(f"Waiting {delay} seconds before restarting watcher for agent {agent_id}")
            await asyncio.sleep(delay)
            
            async with self._lock:
                if agent_id not in self._watchers:
                    logger.warning(f"Watcher for agent {agent_id} no longer exists, skipping restart")
                    return
                
                watcher_info = self._watchers[agent_id]
                
                # Check if watcher was manually stopped
                if watcher_info.status == WatcherStatus.STOPPED:
                    logger.info(f"Watcher for agent {agent_id} was manually stopped, skipping restart")
                    return
                
                # Update status to starting
                watcher_info.status = WatcherStatus.STARTING
                watcher_info.error = None
                watcher_info.started_at = datetime.utcnow()
                
                # Create new background task
                task = asyncio.create_task(self._run_watcher(agent_id))
                watcher_info.task = task
                
                logger.info(f"Auto-restarting watcher for agent {agent_id} (attempt {watcher_info.retry_count})")
        
        except Exception as e:
            logger.error(f"Error during auto-restart for agent {agent_id}: {e}", exc_info=True)

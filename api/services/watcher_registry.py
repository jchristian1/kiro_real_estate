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
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass


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
    sync_event: Optional[asyncio.Event] = None


class WatcherRegistry:
    """
    Registry for managing background watcher tasks.
    
    This class maintains a dictionary of active watchers keyed by agent_id,
    tracks watcher status, heartbeat timestamps, and last sync timestamps.
    It prevents starting multiple watchers for the same agent and provides
    methods for watcher lifecycle management.
    
    Requirements: 4.2, 4.3, 4.4, 4.7, 20.1, 20.2, 20.3, 20.4, 20.5, 8.7
    """
    
    MAX_RETRIES = 5
    
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
                last_error=None,
                sync_event=asyncio.Event()
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
        
        Sets the sync event to wake the watcher loop immediately.
        
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
            
            # Signal the watcher loop to run immediately
            if watcher_info.sync_event:
                watcher_info.sync_event.set()
            
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
        """
        logger.info(f"Watcher task started for agent {agent_id}")
        
        watcher = None
        db_session = None
        
        try:
            # Create database session (SessionLocal() returns a plain session, not a context manager)
            db_session = self.get_db_session()
            
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
                    self._watchers[agent_id].retry_count = 0  # Reset retry count on successful connection
            
            logger.info(f"Watcher for agent {agent_id} connected and running")
            
            # Get list of lead source senders
            from gmail_lead_sync.models import LeadSource
            lead_sources = db_session.query(LeadSource).all()
            sender_list = [ls.sender_email for ls in lead_sources]
            
            if not sender_list:
                logger.warning(f"No lead sources configured for agent {agent_id}")
            
            # Main monitoring loop
            cycle = 0
            while True:
                try:
                    cycle += 1
                    # Update heartbeat and emit DEBUG-level heartbeat log entry
                    async with self._lock:
                        if agent_id in self._watchers:
                            self._watchers[agent_id].last_heartbeat = datetime.utcnow()
                    logger.debug(f"Watcher heartbeat: agent_id={agent_id}, cycle={cycle}")
                    
                    # Refresh sender list each cycle in case lead sources changed
                    lead_sources = db_session.query(LeadSource).all()
                    sender_list = [ls.sender_email for ls in lead_sources]
                    
                    # Process unseen emails
                    if sender_list:
                        try:
                            await asyncio.wait_for(
                                asyncio.to_thread(watcher.process_unseen_emails, sender_list),
                                timeout=30,
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"process_unseen_emails timed out after 30s for agent_id={agent_id}; skipping cycle"
                            )
                            continue

                        # Update last sync timestamp
                        async with self._lock:
                            if agent_id in self._watchers:
                                self._watchers[agent_id].last_sync = datetime.utcnow()
                    
                    # Wait 60 seconds or until a manual sync is triggered
                    async with self._lock:
                        sync_event = self._watchers[agent_id].sync_event if agent_id in self._watchers else None
                    if sync_event:
                        sync_event.clear()
                        try:
                            await asyncio.wait_for(sync_event.wait(), timeout=60)
                        except asyncio.TimeoutError:
                            pass  # Normal 60s cycle
                    else:
                        await asyncio.sleep(60)
                    
                except asyncio.CancelledError:
                    logger.info(f"Watcher task for agent {agent_id} cancelled")
                    raise
                
                except Exception as e:
                    logger.error(
                        f"Unhandled error in watcher polling loop: agent_id={agent_id}, "
                        f"error_type={type(e).__name__}, error={e}",
                        exc_info=True,
                    )
                    await asyncio.sleep(60)
        
        except asyncio.CancelledError:
            logger.info(f"Watcher task for agent {agent_id} cancelled")
            async with self._lock:
                if agent_id in self._watchers:
                    self._watchers[agent_id].status = WatcherStatus.STOPPED
        
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            failed_at = datetime.now(timezone.utc)

            # Requirement 10.2: log ERROR with agent_id, error_type, message, and timestamp
            logger.error(
                f"Watcher FAILED: agent_id={agent_id}, error_type={error_type}, "
                f"error={error_msg}, timestamp={failed_at.isoformat()}",
                exc_info=True,
            )

            async with self._lock:
                if agent_id in self._watchers:
                    watcher_info = self._watchers[agent_id]
                    watcher_info.status = WatcherStatus.FAILED
                    watcher_info.error = error_msg
                    watcher_info.last_error = error_msg

                    # Requirement 10.3: auto-restart after 60s cooldown only when ENABLE_AUTO_RESTART=true
                    enable_auto_restart = os.getenv("ENABLE_AUTO_RESTART", "true").lower() in ("true", "1", "yes")
                    if enable_auto_restart:
                        logger.info(
                            f"Scheduling auto-restart for agent {agent_id} after 60s cooldown "
                            f"(retry {watcher_info.retry_count + 1}/{self.MAX_RETRIES})"
                        )
                        asyncio.create_task(self._auto_restart_watcher(agent_id, delay=60))
                    else:
                        logger.info(
                            f"Auto-restart disabled (ENABLE_AUTO_RESTART is not true); "
                            f"watcher for agent {agent_id} remains FAILED"
                        )
        
        finally:
            if watcher:
                try:
                    watcher.disconnect()
                    logger.info(f"Watcher for agent {agent_id} disconnected")
                except Exception as e:
                    logger.error(f"Error disconnecting watcher for agent {agent_id}: {e}", exc_info=True)
            if db_session:
                try:
                    db_session.close()
                except Exception:
                    pass
            logger.info(f"Watcher task stopped for agent {agent_id}")
    
    async def _auto_restart_watcher(self, agent_id: str, delay: int) -> None:
        """
        Automatically restart a failed watcher after a cooldown delay.

        Waits for ``delay`` seconds, then restarts the watcher unless it was
        manually stopped or has exceeded MAX_RETRIES.

        Args:
            agent_id: Unique identifier for the agent
            delay: Cooldown delay in seconds before restarting

        Requirements: 10.3
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

                # Enforce max retries
                if watcher_info.retry_count >= self.MAX_RETRIES:
                    logger.error(
                        f"Watcher for agent {agent_id} has exceeded MAX_RETRIES ({self.MAX_RETRIES}); "
                        f"not restarting"
                    )
                    return

                watcher_info.retry_count += 1

                # Update status to starting
                watcher_info.status = WatcherStatus.STARTING
                watcher_info.error = None
                watcher_info.started_at = datetime.utcnow()
                watcher_info.sync_event = asyncio.Event()

                # Create new background task
                task = asyncio.create_task(self._run_watcher(agent_id))
                watcher_info.task = task

                logger.info(
                    f"Auto-restarting watcher for agent {agent_id} "
                    f"(attempt {watcher_info.retry_count}/{self.MAX_RETRIES})"
                )

        except Exception as e:
            logger.error(f"Error during auto-restart for agent {agent_id}: {e}", exc_info=True)

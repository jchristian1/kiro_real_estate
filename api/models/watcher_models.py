"""
Pydantic models for watcher API endpoints.

This module defines request and response models for watcher control
endpoints including start, stop, sync, and status operations.

Requirements:
- 4.1: Provide endpoints for starting, stopping, and triggering sync operations
- 4.6: Display real-time Watcher status for each Agent
- 4.7: Track Watcher heartbeats and last sync timestamps
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class WatcherStartResponse(BaseModel):
    """
    Response model for starting a watcher.
    
    Attributes:
        agent_id: Agent identifier
        status: Current watcher status
        started_at: Timestamp when watcher was started
        message: Success message
    """
    agent_id: str
    status: str
    started_at: str
    message: str


class WatcherStopResponse(BaseModel):
    """
    Response model for stopping a watcher.
    
    Attributes:
        agent_id: Agent identifier
        status: Current watcher status
        message: Success message
    """
    agent_id: str
    status: str
    message: str


class WatcherSyncResponse(BaseModel):
    """
    Response model for triggering a manual sync.
    
    Attributes:
        agent_id: Agent identifier
        sync_triggered: Whether sync was successfully triggered
        timestamp: Timestamp when sync was triggered
        message: Success message
    """
    agent_id: str
    sync_triggered: bool
    timestamp: str
    message: str


class WatcherStatusResponse(BaseModel):
    """
    Response model for a single watcher's status.
    
    Attributes:
        agent_id: Agent identifier
        status: Current watcher status (running, stopped, failed, starting)
        last_heartbeat: Timestamp of last heartbeat (ISO format)
        last_sync: Timestamp of last sync operation (ISO format)
        error: Error message if watcher failed
        started_at: Timestamp when watcher was started (ISO format)
    """
    agent_id: str
    status: str
    last_heartbeat: Optional[str] = None
    last_sync: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None


class WatcherStatusListResponse(BaseModel):
    """
    Response model for listing all watcher statuses.
    
    Attributes:
        watchers: List of watcher status information
    """
    watchers: List[WatcherStatusResponse]

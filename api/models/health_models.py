"""
Pydantic models for health check API endpoints.
"""

from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class DatabaseStatus(BaseModel):
    """Database connection status information."""
    connected: bool = Field(..., description="Whether database connection is active")
    message: Optional[str] = Field(None, description="Status message or error details")


class WatcherHealthStatus(BaseModel):
    """Watcher health status information."""
    active_count: int = Field(..., description="Number of currently active watchers")
    heartbeats: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Dictionary mapping agent_id to last heartbeat timestamp (ISO format)"
    )


class ErrorSummary(BaseModel):
    """Error summary for the last 24 hours."""
    count_24h: int = Field(..., description="Number of errors in the last 24 hours")
    recent_errors: List[str] = Field(
        default_factory=list,
        description="List of recent error messages (limited to 10)"
    )


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Overall system status: healthy, degraded, or unhealthy")
    timestamp: str = Field(..., description="Current timestamp in ISO format")
    database: DatabaseStatus = Field(..., description="Database connection status")
    watchers: WatcherHealthStatus = Field(..., description="Watcher health status")
    errors: ErrorSummary = Field(..., description="Error summary for last 24 hours")

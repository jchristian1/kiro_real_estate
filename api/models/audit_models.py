"""
Pydantic models for audit log API endpoints.

This module defines request and response models for audit log operations.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """
    Response model for a single audit log entry.
    
    Includes all audit log fields plus the username for display.
    """
    id: int = Field(..., description="Audit log entry ID")
    timestamp: datetime = Field(..., description="Timestamp of the action")
    user_id: int = Field(..., description="ID of the user who performed the action")
    username: str = Field(..., description="Username of the user who performed the action")
    action: str = Field(..., description="Action type (e.g., 'agent_created', 'template_updated')")
    resource_type: str = Field(..., description="Type of resource affected (e.g., 'agent', 'template')")
    resource_id: Optional[int] = Field(None, description="ID of the affected resource")
    details: Optional[str] = Field(None, description="Additional details about the action")
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """
    Response model for paginated audit log list.
    
    Includes pagination metadata and list of audit log entries.
    """
    logs: List[AuditLogResponse] = Field(..., description="List of audit log entries")
    total: int = Field(..., description="Total number of audit log entries matching filters")
    page: int = Field(..., description="Current page number (1-indexed)")
    per_page: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")

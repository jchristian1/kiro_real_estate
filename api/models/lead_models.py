"""
Pydantic models for lead API endpoints.

This module defines request and response models for lead viewing and export
endpoints including listing, detail view, and CSV export.

Requirements:
- 5.1: Provide endpoints for retrieving Lead records with pagination
- 5.2: Support filtering Leads by Agent, date range, and processing status
- 5.4: Provide detail view showing full Lead content and metadata
- 5.7: Display processing status and response status for each Lead
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class LeadResponse(BaseModel):
    """Response model for lead details."""
    id: int
    name: str
    phone: str
    source_email: str
    lead_source_id: int
    gmail_uid: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    response_sent: bool
    response_status: Optional[str] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LeadListResponse(BaseModel):
    """
    Response model for listing leads with pagination.
    
    Attributes:
        leads: List of lead details
        total: Total number of leads matching filters
        page: Current page number
        per_page: Number of leads per page
        pages: Total number of pages
    """
    leads: list[LeadResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# Unified lead detail response models (Phase 3C)
# ---------------------------------------------------------------------------


class LeadCoreInfoResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    source_email: str
    created_at: datetime
    property_address: Optional[str] = None
    listing_url: Optional[str] = None
    lead_source_name: Optional[str] = None
    agent_current_state: Optional[str] = None
    last_agent_action_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LeadStageInfoResponse(BaseModel):
    stage_id: int
    stage_name: str
    stage_key: str
    stage_color: str
    stage_category: str
    stage_entered_at: Optional[datetime] = None


class ScoreFactorResponse(BaseModel):
    label: str
    points: int
    met: bool


class LeadQualificationSummaryResponse(BaseModel):
    score: int
    bucket: str
    explanation_text: Optional[str] = None
    breakdown: List[ScoreFactorResponse] = []
    submitted_at: Optional[datetime] = None
    invitation_sent_at: Optional[datetime] = None


class ActivityTimelineEntryResponse(BaseModel):
    id: int
    event_type: str
    actor_source: Optional[str] = None
    metadata: Dict[str, Any] = {}
    occurred_at: datetime


class UnifiedLeadDetailResponse(BaseModel):
    """Unified lead detail — single coherent object for agent and admin views."""
    core: LeadCoreInfoResponse
    stage: Optional[LeadStageInfoResponse] = None
    qualification: Optional[LeadQualificationSummaryResponse] = None
    timeline: List[ActivityTimelineEntryResponse] = []

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

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class LeadResponse(BaseModel):
    """
    Response model for lead details.
    
    Attributes:
        id: Database ID
        name: Lead name extracted from email
        phone: Lead phone number extracted from email
        source_email: Email address that sent the lead
        lead_source_id: ID of the lead source configuration used
        gmail_uid: Unique Gmail message ID
        created_at: When the lead was created
        updated_at: When the lead was last updated
        response_sent: Whether an automated response was sent
        response_status: Status of the response (success, failed, etc.)
    """
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
    
    class Config:
        from_attributes = True


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

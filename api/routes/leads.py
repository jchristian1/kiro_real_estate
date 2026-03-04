"""
Lead viewing and export API endpoints.

This module provides REST API endpoints for viewing and exporting leads including:
- Listing leads with pagination and filtering
- Getting lead details
- Exporting leads to CSV

All endpoints require authentication and integrate with the existing
Lead model from the CLI system.

Endpoints:
- GET /api/v1/leads - List leads with pagination and filtering
- GET /api/v1/leads/{id} - Get lead details
- GET /api/v1/leads/export - Export leads to CSV
"""

from typing import Optional
import csv
import io
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from gmail_lead_sync.models import Lead, LeadSource, Credentials
from api.models.web_ui_models import User
from api.models.lead_models import (
    LeadResponse,
    LeadListResponse
)
from api.models.error_models import ErrorCode
from api.exceptions import NotFoundException


router = APIRouter()


# Dependencies that will be injected by FastAPI
def get_db():
    """Database dependency - will be overridden in tests."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authentication dependency - will be overridden in tests."""
    from api.auth import get_current_user as auth_get_current_user
    return auth_get_current_user(request, db)


def _enrich_lead(lead: Lead, db: Session) -> LeadResponse:
    """Build a LeadResponse enriched with agent_id, agent_name, and company info."""
    agent_name = None
    company_id = None
    company_name = None
    if lead.agent_id:
        creds = db.query(Credentials).filter(Credentials.agent_id == lead.agent_id).first()
        if creds:
            agent_name = creds.display_name or creds.agent_id
            company_id = creds.company_id
            if creds.company:
                company_name = creds.company.name

    return LeadResponse(
        id=lead.id,
        name=lead.name,
        phone=lead.phone,
        source_email=lead.source_email,
        lead_source_id=lead.lead_source_id,
        gmail_uid=lead.gmail_uid,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        response_sent=lead.response_sent,
        response_status=lead.response_status,
        agent_id=lead.agent_id,
        agent_name=agent_name,
        company_id=company_id,
        company_name=company_name,
    )


@router.get("/leads", response_model=LeadListResponse)
def list_leads(
    page: int = 1,
    per_page: int = 50,
    agent_id: Optional[str] = None,
    company_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    response_sent: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List leads with pagination and filtering.
    
    Supports filtering by:
    - agent_id: Filter by agent (via lead_source)
    - start_date: Filter by creation date (from)
    - end_date: Filter by creation date (to)
    - response_sent: Filter by response status
    
    Args:
        page: Page number (1-indexed)
        per_page: Number of leads per page (max 100)
        agent_id: Optional agent ID filter
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)
        response_sent: Optional response sent filter
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Paginated list of leads
        
    Requirements:
        - 5.1: Provide endpoints for retrieving Lead records with pagination
        - 5.2: Support filtering Leads by Agent, date range, and processing status
        - 5.3: Display table of Leads with sortable columns
    """
    # Enforce max per_page limit and minimum value
    per_page = max(1, min(per_page, 100))
    
    # Build query
    query = db.query(Lead)
    
    # Apply filters
    if agent_id:
        query = query.filter(Lead.agent_id == agent_id)
    
    if company_id:
        from gmail_lead_sync.models import Credentials as Creds
        agent_ids = [c.agent_id for c in db.query(Creds).filter(Creds.company_id == company_id).all()]
        query = query.filter(Lead.agent_id.in_(agent_ids))
    
    if start_date:
        from datetime import datetime
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        query = query.filter(Lead.created_at >= start_dt)
    
    if end_date:
        from datetime import datetime
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        query = query.filter(Lead.created_at <= end_dt)
    
    if response_sent is not None:
        query = query.filter(Lead.response_sent == response_sent)
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    pages = (total + per_page - 1) // per_page if total > 0 else 1
    offset = (page - 1) * per_page
    
    # Get paginated results
    leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(per_page).all()
    
    lead_responses = [_enrich_lead(lead, db) for lead in leads]
    
    return LeadListResponse(
        leads=lead_responses,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )


@router.get("/leads/export")
def export_leads_csv(
    agent_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    response_sent: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export leads to CSV format with filtering.
    
    Applies the same filters as the list endpoint and returns a CSV file
    with all lead fields properly escaped for download.
    
    Args:
        agent_id: Optional agent ID filter
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)
        response_sent: Optional response sent filter
        db: Database session
        current_user: Authenticated user
        
    Returns:
        CSV file download with Content-Type and Content-Disposition headers
        
    Requirements:
        - 5.5: Provide endpoint for exporting Leads to CSV format
        - 5.6: Include all requested fields in CSV export
        - 19.1: Provide endpoint for exporting Lead records to CSV format
        - 19.2: Apply same filters as current Lead view
        - 19.3: Include headers in CSV export
        - 19.4: Properly escape CSV special characters in exported data
    """
    # Build query with same filters as list endpoint
    query = db.query(Lead)
    
    # Apply filters
    if agent_id:
        query = query.filter(Lead.agent_id == agent_id)
    
    if start_date:
        from datetime import datetime
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        query = query.filter(Lead.created_at >= start_dt)
    
    if end_date:
        from datetime import datetime
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        query = query.filter(Lead.created_at <= end_dt)
    
    if response_sent is not None:
        query = query.filter(Lead.response_sent == response_sent)
    
    # Get all matching leads (no pagination for export)
    leads = query.order_by(Lead.created_at.desc()).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    
    # Write header row
    writer.writerow([
        'id', 'name', 'phone', 'source_email', 'agent_id', 'agent_name',
        'lead_source_id', 'gmail_uid', 'created_at', 'updated_at',
        'response_sent', 'response_status'
    ])
    
    # Write data rows
    for lead in leads:
        enriched = _enrich_lead(lead, db)
        writer.writerow([
            lead.id, lead.name, lead.phone, lead.source_email,
            enriched.agent_id or '', enriched.agent_name or '',
            lead.lead_source_id, lead.gmail_uid,
            lead.created_at.isoformat() if lead.created_at else '',
            lead.updated_at.isoformat() if lead.updated_at else '',
            lead.response_sent,
            lead.response_status if lead.response_status else ''
        ])
    
    # Get CSV content
    csv_content = output.getvalue()
    output.close()
    
    # Return as streaming response with appropriate headers
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=leads_export.csv"
        }
    )


@router.get("/leads/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get full details for a specific lead.
    
    Returns complete lead information including all content and metadata,
    processing status, and response status.
    
    Args:
        lead_id: Lead ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Lead details with full content and metadata
        
    Raises:
        NotFoundException: If lead not found
        
    Requirements:
        - 5.4: Provide detail view showing full Lead content and metadata
        - 5.7: Display processing status and response status for each Lead
    """
    # Find lead
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    
    if not lead:
        raise NotFoundException(
            message=f"Lead with ID {lead_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    return _enrich_lead(lead, db)

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
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.models.lead_models import (
    LeadResponse,
    LeadListResponse,
    UnifiedLeadDetailResponse,
    LeadCoreInfoResponse,
    LeadStageInfoResponse,
    LeadQualificationSummaryResponse,
    ScoreFactorResponse,
    ActivityTimelineEntryResponse,
)
from api.models.error_models import ErrorCode
from api.exceptions import NotFoundException
from api.repositories import LeadRepository, CredentialRepository
from api.dependencies.auth import require_role


router = APIRouter(dependencies=[Depends(require_role("company_admin"))])


# Dependencies that will be injected by FastAPI
def get_db():
    """Database dependency - will be overridden in tests."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Authentication dependency - will be overridden in tests."""
    from api.auth import get_current_user as auth_get_current_user
    from api.config import get_config
    return auth_get_current_user(request, db, get_config().secret_key)


def _enrich_lead(lead, cred_repo: CredentialRepository) -> LeadResponse:
    """Build a LeadResponse enriched with agent_id, agent_name, and company info."""
    agent_name = None
    company_id = None
    company_name = None
    if lead.agent_id:
        creds = cred_repo.get_by_agent_id(lead.agent_id)
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
    current_user=Depends(get_current_user)
):
    """
    List leads with pagination and filtering.

    Requirements:
        - 5.1: Provide endpoints for retrieving Lead records with pagination
        - 5.2: Support filtering Leads by Agent, date range, and processing status
    """
    per_page = max(1, min(per_page, 100))

    lead_repo = LeadRepository(db)
    cred_repo = CredentialRepository(db)

    # Resolve company_id → list of agent_ids
    company_agent_ids: Optional[list[str]] = None
    if company_id:
        company_creds = cred_repo.get_by_company_id(company_id)
        company_agent_ids = [c.agent_id for c in company_creds]

    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None
    if start_date:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    if end_date:
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

    leads, total = lead_repo.list_with_filters(
        agent_id=agent_id,
        company_agent_ids=company_agent_ids,
        start_date=start_dt,
        end_date=end_dt,
        response_sent=response_sent,
        skip=(page - 1) * per_page,
        limit=per_page,
    )

    pages = (total + per_page - 1) // per_page if total > 0 else 1
    lead_responses = [_enrich_lead(lead, cred_repo) for lead in leads]

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
    current_user=Depends(get_current_user)
):
    """
    Export leads to CSV format with filtering.

    Requirements:
        - 5.5: Provide endpoint for exporting Leads to CSV format
    """
    lead_repo = LeadRepository(db)
    cred_repo = CredentialRepository(db)

    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None
    if start_date:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    if end_date:
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

    leads, _ = lead_repo.list_with_filters(
        agent_id=agent_id,
        start_date=start_dt,
        end_date=end_dt,
        response_sent=response_sent,
        limit=10000,  # large limit for export
    )

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        'id', 'name', 'phone', 'source_email', 'agent_id', 'agent_name',
        'lead_source_id', 'gmail_uid', 'created_at', 'updated_at',
        'response_sent', 'response_status'
    ])

    for lead in leads:
        enriched = _enrich_lead(lead, cred_repo)
        writer.writerow([
            lead.id, lead.name, lead.phone, lead.source_email,
            enriched.agent_id or '', enriched.agent_name or '',
            lead.lead_source_id, lead.gmail_uid,
            lead.created_at.isoformat() if lead.created_at else '',
            lead.updated_at.isoformat() if lead.updated_at else '',
            lead.response_sent,
            lead.response_status if lead.response_status else ''
        ])

    csv_content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=leads_export.csv"
        }
    )


@router.get("/leads/{lead_id}", response_model=UnifiedLeadDetailResponse)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Get full details for a specific lead — unified read model.

    Returns core identity, current pipeline stage, qualification summary,
    and activity timeline. Delegates assembly to lead_detail_service.

    Requirements:
        - 5.4: Provide detail view showing full Lead content and metadata
    """
    from api.services.lead_detail_service import assemble_lead_detail

    lead_repo = LeadRepository(db)
    lead = lead_repo.get_by_agent_id_str(lead_id)
    if not lead:
        raise NotFoundException(
            message=f"Lead with ID {lead_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )

    company_id = getattr(lead, "company_id", None)
    detail = assemble_lead_detail(db, lead_id=lead_id, company_id=company_id)
    if detail is None:
        raise NotFoundException(
            message=f"Lead with ID {lead_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )

    return UnifiedLeadDetailResponse(
        core=LeadCoreInfoResponse(
            id=detail.core.id,
            name=detail.core.name,
            phone=detail.core.phone,
            source_email=detail.core.source_email,
            created_at=detail.core.created_at,
            property_address=detail.core.property_address,
            listing_url=detail.core.listing_url,
            lead_source_name=detail.core.lead_source_name,
            agent_current_state=detail.core.agent_current_state,
            last_agent_action_at=detail.core.last_agent_action_at,
        ),
        stage=LeadStageInfoResponse(
            stage_id=detail.stage.stage_id,
            stage_name=detail.stage.stage_name,
            stage_key=detail.stage.stage_key,
            stage_color=detail.stage.stage_color,
            stage_category=detail.stage.stage_category,
            stage_entered_at=detail.stage.stage_entered_at,
        ) if detail.stage else None,
        qualification=LeadQualificationSummaryResponse(
            score=detail.qualification.score,
            bucket=detail.qualification.bucket,
            explanation_text=detail.qualification.explanation_text,
            breakdown=[
                ScoreFactorResponse(label=f.label, points=f.points, met=f.met)
                for f in detail.qualification.breakdown
            ],
            submitted_at=detail.qualification.submitted_at,
            invitation_sent_at=detail.qualification.invitation_sent_at,
        ) if detail.qualification else None,
        timeline=[
            ActivityTimelineEntryResponse(
                id=e.id,
                event_type=e.event_type,
                actor_source=e.actor_source,
                metadata=e.metadata,
                occurred_at=e.occurred_at,
            )
            for e in detail.timeline
        ],
    )

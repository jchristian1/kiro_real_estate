"""
Lead source management API endpoints.

Endpoints:
- POST /api/v1/lead-sources - Create new lead source
- GET /api/v1/lead-sources - List all lead sources
- GET /api/v1/lead-sources/{id} - Get lead source details
- PUT /api/v1/lead-sources/{id} - Update lead source
- DELETE /api/v1/lead-sources/{id} - Delete lead source
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from api.models.web_ui_models import User
from api.models.lead_source_models import (
    LeadSourceCreateRequest,
    LeadSourceUpdateRequest,
    LeadSourceResponse,
    LeadSourceListResponse,
    LeadSourceDeleteResponse,
    RegexTestRequest,
    RegexTestResponse,
    RegexProfileVersionResponse,
    RegexProfileVersionListResponse,
    RegexProfileRollbackRequest,
    RegexProfileRollbackResponse,
)
from api.models.error_models import ErrorCode
from api.exceptions import ValidationException, NotFoundException, ConflictException
from api.services.audit_log import record_audit_log
from api.utils.regex_tester import test_regex_pattern, RegexTimeoutError
from api.repositories.lead_source_repository import (
    LeadSourceRepository,
    LeadSourceCreate,
    LeadSourceUpdate,
    RegexProfileVersionRepository,
    TemplateExistenceRepository,
)
from api.dependencies.auth import require_role

router = APIRouter(dependencies=[Depends(require_role("platform_admin"))])


def _get_regex_timeout_ms() -> int:
    """Read REGEX_TIMEOUT_MS from config, defaulting to 1000ms. Requirements: 11.7"""
    import os
    try:
        return int(os.getenv("REGEX_TIMEOUT_MS", "1000"))
    except (ValueError, TypeError):
        return 1000


def get_db():
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    from api.auth import get_current_user as auth_get_current_user
    return auth_get_current_user(request, db)


@router.post("/lead-sources", response_model=LeadSourceResponse, status_code=status.HTTP_201_CREATED)
def create_lead_source(
    lead_source_data: LeadSourceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new lead source. Requirements: 2.1, 2.2, 2.6"""
    ls_repo = LeadSourceRepository(db)
    tmpl_repo = TemplateExistenceRepository(db)
    ver_repo = RegexProfileVersionRepository(db)

    # Check for duplicate sender_email
    existing_sources = ls_repo.list_all(limit=10000)
    if any(s.sender_email == lead_source_data.sender_email for s in existing_sources):
        raise ConflictException(
            message=f"Lead source with sender email '{lead_source_data.sender_email}' already exists",
            code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
        )

    if lead_source_data.template_id is not None and not tmpl_repo.exists(lead_source_data.template_id):
        raise ValidationException(
            message=f"Template with ID {lead_source_data.template_id} not found",
            code=ErrorCode.VALIDATION_ERROR,
        )

    lead_source = ls_repo.create(LeadSourceCreate(
        sender_email=lead_source_data.sender_email,
        identifier_snippet=lead_source_data.identifier_snippet,
        name_regex=lead_source_data.name_regex,
        phone_regex=lead_source_data.phone_regex,
        template_id=lead_source_data.template_id,
        auto_respond_enabled=lead_source_data.auto_respond_enabled,
    ))

    ver_repo.create(lead_source, current_user.id)

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="lead_source_created",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=f"Created lead source for {lead_source_data.sender_email}",
    )
    return LeadSourceResponse.from_orm(lead_source)


@router.get("/lead-sources", response_model=LeadSourceListResponse)
def list_lead_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all lead sources. Requirements: 2.1"""
    ls_repo = LeadSourceRepository(db)
    lead_sources = ls_repo.list_all(limit=10000)
    return LeadSourceListResponse(lead_sources=[LeadSourceResponse.from_orm(ls) for ls in lead_sources])


@router.get("/lead-sources/{lead_source_id}", response_model=LeadSourceResponse)
def get_lead_source(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific lead source. Requirements: 2.1"""
    ls_repo = LeadSourceRepository(db)
    lead_source = ls_repo.get_by_id(lead_source_id)
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    return LeadSourceResponse.from_orm(lead_source)


@router.put("/lead-sources/{lead_source_id}", response_model=LeadSourceResponse)
def update_lead_source(
    lead_source_id: int,
    lead_source_data: LeadSourceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing lead source. Requirements: 2.1, 2.2, 2.6, 2.7"""
    ls_repo = LeadSourceRepository(db)
    tmpl_repo = TemplateExistenceRepository(db)
    ver_repo = RegexProfileVersionRepository(db)

    lead_source = ls_repo.get_by_id(lead_source_id)
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    has_updates = any([
        lead_source_data.sender_email is not None,
        lead_source_data.identifier_snippet is not None,
        lead_source_data.name_regex is not None,
        lead_source_data.phone_regex is not None,
        lead_source_data.template_id is not None,
        lead_source_data.auto_respond_enabled is not None,
    ])
    if not has_updates:
        raise ValidationException(message="No fields to update", code=ErrorCode.VALIDATION_ERROR)

    if lead_source_data.sender_email is not None:
        all_sources = ls_repo.list_all(limit=10000)
        if any(s.sender_email == lead_source_data.sender_email and s.id != lead_source_id for s in all_sources):
            raise ConflictException(
                message=f"Lead source with sender email '{lead_source_data.sender_email}' already exists",
                code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
            )

    if lead_source_data.template_id is not None and not tmpl_repo.exists(lead_source_data.template_id):
        raise ValidationException(
            message=f"Template with ID {lead_source_data.template_id} not found",
            code=ErrorCode.VALIDATION_ERROR,
        )

    updated_fields = [
        f for f, v in [
            ("sender_email", lead_source_data.sender_email),
            ("identifier_snippet", lead_source_data.identifier_snippet),
            ("name_regex", lead_source_data.name_regex),
            ("phone_regex", lead_source_data.phone_regex),
            ("template_id", lead_source_data.template_id),
            ("auto_respond_enabled", lead_source_data.auto_respond_enabled),
        ] if v is not None
    ]

    regex_fields_updated = any([
        lead_source_data.name_regex is not None,
        lead_source_data.phone_regex is not None,
        lead_source_data.identifier_snippet is not None,
    ])

    lead_source = ls_repo.update(lead_source_id, LeadSourceUpdate(
        sender_email=lead_source_data.sender_email,
        identifier_snippet=lead_source_data.identifier_snippet,
        name_regex=lead_source_data.name_regex,
        phone_regex=lead_source_data.phone_regex,
        template_id=lead_source_data.template_id,
        auto_respond_enabled=lead_source_data.auto_respond_enabled,
    ))

    if regex_fields_updated:
        new_version = ver_repo.create(lead_source, current_user.id)
        record_audit_log(
            db_session=db,
            user_id=current_user.id,
            action="regex_profile_version_created",
            resource_type="lead_source",
            resource_id=lead_source.id,
            details=f"Created regex profile version {new_version} for lead source {lead_source_id}",
        )

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="lead_source_updated",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=f"Updated lead source {lead_source_id} ({', '.join(updated_fields)})",
    )
    return LeadSourceResponse.from_orm(lead_source)


@router.delete("/lead-sources/{lead_source_id}", response_model=LeadSourceDeleteResponse)
def delete_lead_source(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a lead source. Requirements: 2.1, 2.7"""
    ls_repo = LeadSourceRepository(db)
    lead_source = ls_repo.get_by_id(lead_source_id)
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    sender_email = lead_source.sender_email
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="lead_source_deleted",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=f"Deleted lead source for {sender_email}",
    )
    ls_repo.delete(lead_source_id)
    return LeadSourceDeleteResponse(message=f"Lead source for '{sender_email}' deleted successfully")


@router.post("/lead-sources/test-regex", response_model=RegexTestResponse)
def test_regex(
    test_data: RegexTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test a regex pattern against sample text. Requirements: 2.3, 2.4, 11.7, 14.1-14.4"""
    try:
        matched, groups, match_text = test_regex_pattern(
            pattern=test_data.pattern,
            text=test_data.sample_text,
            timeout_ms=_get_regex_timeout_ms(),
        )
        return RegexTestResponse(matched=matched, groups=groups, match_text=match_text)
    except RegexTimeoutError:
        raise ValidationException(
            message=f"Regex execution timeout ({_get_regex_timeout_ms()}ms exceeded)",
            code=ErrorCode.VALIDATION_ERROR,
        )
    except ValueError as e:
        raise ValidationException(message=str(e), code=ErrorCode.VALIDATION_ERROR)


@router.get("/lead-sources/{lead_source_id}/versions", response_model=RegexProfileVersionListResponse)
def get_lead_source_versions(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get version history for a lead source's regex profile. Requirements: 9.3"""
    ls_repo = LeadSourceRepository(db)
    ver_repo = RegexProfileVersionRepository(db)

    if not ls_repo.get_by_id(lead_source_id):
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    versions = ver_repo.list_for_source(lead_source_id)
    return RegexProfileVersionListResponse(
        versions=[RegexProfileVersionResponse.from_orm(v) for v in versions]
    )


@router.post("/lead-sources/{lead_source_id}/rollback", response_model=RegexProfileRollbackResponse)
def rollback_lead_source(
    lead_source_id: int,
    rollback_data: RegexProfileRollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rollback a lead source's regex profile to a specific version. Requirements: 9.4, 9.7"""
    ls_repo = LeadSourceRepository(db)
    ver_repo = RegexProfileVersionRepository(db)

    lead_source = ls_repo.get_by_id(lead_source_id)
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    target_version = ver_repo.get_by_version(lead_source_id, rollback_data.version)
    if not target_version:
        raise NotFoundException(
            message=f"Version {rollback_data.version} not found for lead source {lead_source_id}",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    lead_source = ls_repo.update(lead_source_id, LeadSourceUpdate(
        name_regex=target_version.name_regex,
        phone_regex=target_version.phone_regex,
        identifier_snippet=target_version.identifier_snippet,
    ))

    new_version = ver_repo.create(lead_source, current_user.id)

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="regex_profile_rollback",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=f"Rolled back lead source {lead_source_id} to version {rollback_data.version} (created new version {new_version})",
    )
    return RegexProfileRollbackResponse(
        message=f"Successfully rolled back to version {rollback_data.version}",
        new_version=new_version,
        lead_source=LeadSourceResponse.from_orm(lead_source),
    )

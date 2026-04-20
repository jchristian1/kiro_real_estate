"""
Lead source management API endpoints.

All endpoints are company-scoped: a company admin can only create, read,
update, and delete lead sources that belong to their own company.
company_id is derived from the authenticated user — it is never accepted
from the request body.

Cross-company access returns 404 (indistinguishable from not-found) to
avoid leaking tenant information.

Note on platform-admin global management
-----------------------------------------
Platform-level visibility and management of lead sources across all companies
will be added later via separate platform-panel endpoints.  These admin routes
are intentionally scoped to a single company and will not be extended to
support cross-company access.

Endpoints:
- POST   /api/v1/lead-sources
- GET    /api/v1/lead-sources
- GET    /api/v1/lead-sources/{id}
- PUT    /api/v1/lead-sources/{id}
- DELETE /api/v1/lead-sources/{id}
- POST   /api/v1/lead-sources/test-regex
- GET    /api/v1/lead-sources/{id}/versions
- POST   /api/v1/lead-sources/{id}/rollback
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
from api.exceptions import (
    ValidationException,
    NotFoundException,
    ConflictException,
    AuthorizationException,
)
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

router = APIRouter(dependencies=[Depends(require_role("company_admin"))])


def _get_regex_timeout_ms() -> int:
    """Read REGEX_TIMEOUT_MS from config, defaulting to 1000ms."""
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
    from api.config import get_config
    return auth_get_current_user(request, db, get_config().secret_key)


def _require_company(user: User) -> int:
    """Return the user's company_id or raise 403 if not set.

    A user with no company association cannot manage company-scoped resources.
    This guards every endpoint that writes or reads tenant data.
    """
    if user.company_id is None:
        raise AuthorizationException(
            message="Your account is not associated with a company. "
                    "Contact a platform administrator.",
            code=ErrorCode.AUTH_FORBIDDEN,
        )
    return user.company_id


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post(
    "/lead-sources",
    response_model=LeadSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lead_source(
    lead_source_data: LeadSourceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new lead source for the authenticated user's company."""
    company_id = _require_company(current_user)

    ls_repo = LeadSourceRepository(db)
    tmpl_repo = TemplateExistenceRepository(db)
    ver_repo = RegexProfileVersionRepository(db)

    # Duplicate check: scoped to this company only.
    # Two companies may share the same sender_email with different rules.
    if ls_repo.get_by_sender_and_company(lead_source_data.sender_email, company_id):
        raise ConflictException(
            message=f"A lead source for '{lead_source_data.sender_email}' already exists "
                    f"in your company.",
            code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
        )

    if lead_source_data.template_id is not None and not tmpl_repo.exists(
        lead_source_data.template_id
    ):
        raise ValidationException(
            message=f"Template with ID {lead_source_data.template_id} not found",
            code=ErrorCode.VALIDATION_ERROR,
        )

    lead_source = ls_repo.create(
        LeadSourceCreate(
            company_id=company_id,
            sender_email=lead_source_data.sender_email,
            identifier_snippet=lead_source_data.identifier_snippet,
            name_regex=lead_source_data.name_regex,
            phone_regex=lead_source_data.phone_regex,
            template_id=lead_source_data.template_id,
            auto_respond_enabled=lead_source_data.auto_respond_enabled,
        )
    )

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


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/lead-sources", response_model=LeadSourceListResponse)
def list_lead_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all lead sources belonging to the authenticated user's company."""
    company_id = _require_company(current_user)
    ls_repo = LeadSourceRepository(db)
    lead_sources = ls_repo.list_for_company(company_id, limit=10000)
    return LeadSourceListResponse(
        lead_sources=[LeadSourceResponse.from_orm(ls) for ls in lead_sources]
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@router.get("/lead-sources/{lead_source_id}", response_model=LeadSourceResponse)
def get_lead_source(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a lead source by ID, scoped to the authenticated user's company."""
    company_id = _require_company(current_user)
    ls_repo = LeadSourceRepository(db)
    lead_source = ls_repo.get_by_id(lead_source_id, company_id)
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    return LeadSourceResponse.from_orm(lead_source)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@router.put("/lead-sources/{lead_source_id}", response_model=LeadSourceResponse)
def update_lead_source(
    lead_source_id: int,
    lead_source_data: LeadSourceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a lead source, scoped to the authenticated user's company."""
    company_id = _require_company(current_user)

    ls_repo = LeadSourceRepository(db)
    tmpl_repo = TemplateExistenceRepository(db)
    ver_repo = RegexProfileVersionRepository(db)

    lead_source = ls_repo.get_by_id(lead_source_id, company_id)
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
        raise ValidationException(
            message="No fields to update", code=ErrorCode.VALIDATION_ERROR
        )

    # Duplicate sender check: scoped to this company, excluding the current record.
    if lead_source_data.sender_email is not None:
        existing = ls_repo.get_by_sender_and_company(
            lead_source_data.sender_email, company_id
        )
        if existing and existing.id != lead_source_id:
            raise ConflictException(
                message=f"A lead source for '{lead_source_data.sender_email}' already exists "
                        f"in your company.",
                code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
            )

    if lead_source_data.template_id is not None and not tmpl_repo.exists(
        lead_source_data.template_id
    ):
        raise ValidationException(
            message=f"Template with ID {lead_source_data.template_id} not found",
            code=ErrorCode.VALIDATION_ERROR,
        )

    updated_fields = [
        f
        for f, v in [
            ("sender_email", lead_source_data.sender_email),
            ("identifier_snippet", lead_source_data.identifier_snippet),
            ("name_regex", lead_source_data.name_regex),
            ("phone_regex", lead_source_data.phone_regex),
            ("template_id", lead_source_data.template_id),
            ("auto_respond_enabled", lead_source_data.auto_respond_enabled),
        ]
        if v is not None
    ]

    regex_fields_updated = any([
        lead_source_data.name_regex is not None,
        lead_source_data.phone_regex is not None,
        lead_source_data.identifier_snippet is not None,
    ])

    update_kwargs = {}
    if lead_source_data.sender_email is not None:
        update_kwargs["sender_email"] = lead_source_data.sender_email
    if lead_source_data.identifier_snippet is not None:
        update_kwargs["identifier_snippet"] = lead_source_data.identifier_snippet
    if lead_source_data.name_regex is not None:
        update_kwargs["name_regex"] = lead_source_data.name_regex
    if lead_source_data.phone_regex is not None:
        update_kwargs["phone_regex"] = lead_source_data.phone_regex
    if lead_source_data.template_id is not None:
        update_kwargs["template_id"] = lead_source_data.template_id
    if lead_source_data.auto_respond_enabled is not None:
        update_kwargs["auto_respond_enabled"] = lead_source_data.auto_respond_enabled

    lead_source = ls_repo.update(lead_source_id, company_id, LeadSourceUpdate(**update_kwargs))

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


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/lead-sources/{lead_source_id}", response_model=LeadSourceDeleteResponse)
def delete_lead_source(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a lead source, scoped to the authenticated user's company."""
    company_id = _require_company(current_user)

    ls_repo = LeadSourceRepository(db)
    lead_source = ls_repo.get_by_id(lead_source_id, company_id)
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
    ls_repo.delete(lead_source_id, company_id)
    return LeadSourceDeleteResponse(
        message=f"Lead source for '{sender_email}' deleted successfully"
    )


# ---------------------------------------------------------------------------
# Regex tester (no company scoping needed — stateless utility)
# ---------------------------------------------------------------------------

@router.post("/lead-sources/test-regex", response_model=RegexTestResponse)
def test_regex(
    test_data: RegexTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test a regex pattern against sample text."""
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


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

@router.get(
    "/lead-sources/{lead_source_id}/versions",
    response_model=RegexProfileVersionListResponse,
)
def get_lead_source_versions(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get version history for a lead source's regex profile."""
    company_id = _require_company(current_user)
    ls_repo = LeadSourceRepository(db)
    ver_repo = RegexProfileVersionRepository(db)

    if not ls_repo.get_by_id(lead_source_id, company_id):
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    versions = ver_repo.list_for_source(lead_source_id)
    return RegexProfileVersionListResponse(
        versions=[RegexProfileVersionResponse.from_orm(v) for v in versions]
    )


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

@router.post(
    "/lead-sources/{lead_source_id}/rollback",
    response_model=RegexProfileRollbackResponse,
)
def rollback_lead_source(
    lead_source_id: int,
    rollback_data: RegexProfileRollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rollback a lead source's regex profile to a specific version."""
    company_id = _require_company(current_user)

    ls_repo = LeadSourceRepository(db)
    ver_repo = RegexProfileVersionRepository(db)

    lead_source = ls_repo.get_by_id(lead_source_id, company_id)
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

    lead_source = ls_repo.update(
        lead_source_id,
        company_id,
        LeadSourceUpdate(
            name_regex=target_version.name_regex,
            phone_regex=target_version.phone_regex,
            identifier_snippet=target_version.identifier_snippet,
        ),
    )

    new_version = ver_repo.create(lead_source, current_user.id)

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="regex_profile_rollback",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=(
            f"Rolled back lead source {lead_source_id} to version "
            f"{rollback_data.version} (created new version {new_version})"
        ),
    )
    return RegexProfileRollbackResponse(
        message=f"Successfully rolled back to version {rollback_data.version}",
        new_version=new_version,
        lead_source=LeadSourceResponse.from_orm(lead_source),
    )

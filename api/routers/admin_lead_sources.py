"""
Lead source management API endpoints.

This module provides REST API endpoints for managing lead sources including:
- Creating lead sources with regex validation
- Listing all lead sources
- Getting lead source details
- Updating lead source configuration
- Deleting lead sources

All endpoints require authentication and integrate with the existing
LeadSource model from the CLI system.

Endpoints:
- POST /api/v1/lead-sources - Create new lead source
- GET /api/v1/lead-sources - List all lead sources
- GET /api/v1/lead-sources/{id} - Get lead source details
- PUT /api/v1/lead-sources/{id} - Update lead source
- DELETE /api/v1/lead-sources/{id} - Delete lead source
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from gmail_lead_sync.models import LeadSource, Template
from api.models.web_ui_models import User, RegexProfileVersion
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
    RegexProfileRollbackResponse
)
from api.models.error_models import ErrorCode
from api.exceptions import (
    ValidationException,
    NotFoundException,
    ConflictException
)
from api.services.audit_log import record_audit_log
from api.utils.regex_tester import test_regex_pattern, RegexTimeoutError


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


def _create_regex_profile_version(
    db: Session,
    lead_source: LeadSource,
    user_id: int
) -> int:
    """
    Create a new version record for a lead source's regex profile.
    
    Args:
        db: Database session
        lead_source: Lead source to create version for
        user_id: User ID creating the version
        
    Returns:
        New version number
        
    Requirements:
        - 9.1: Maintain version history for Regex_Profile modifications
        - 9.2: Create new version record when Regex_Profile is updated
    """
    # Get the latest version number for this lead source
    latest_version = db.query(RegexProfileVersion).filter(
        RegexProfileVersion.lead_source_id == lead_source.id
    ).order_by(RegexProfileVersion.version.desc()).first()
    
    # Calculate new version number
    new_version = (latest_version.version + 1) if latest_version else 1
    
    # Create version record
    version_record = RegexProfileVersion(
        lead_source_id=lead_source.id,
        version=new_version,
        name_regex=lead_source.name_regex,
        phone_regex=lead_source.phone_regex,
        identifier_snippet=lead_source.identifier_snippet,
        created_by=user_id
    )
    
    db.add(version_record)
    
    return new_version


@router.post("/lead-sources", response_model=LeadSourceResponse, status_code=status.HTTP_201_CREATED)
def create_lead_source(
    lead_source_data: LeadSourceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new lead source with regex validation.
    
    Validates regex patterns before storage to ensure they are syntactically
    correct. Also validates that the template_id exists if provided.
    
    Args:
        lead_source_data: Lead source creation request data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Created lead source details
        
    Raises:
        ConflictException: If sender_email already exists
        ValidationException: If regex patterns are invalid or template not found
        
    Requirements:
        - 2.1: Provide endpoints for creating Lead_Source records
        - 2.2: Validate regex pattern syntax
        - 2.6: Sanitize all user input in Lead_Source configurations
    """
    # Check if sender_email already exists
    existing = db.query(LeadSource).filter(
        LeadSource.sender_email == lead_source_data.sender_email
    ).first()
    
    if existing:
        raise ConflictException(
            message=f"Lead source with sender email '{lead_source_data.sender_email}' already exists",
            code=ErrorCode.CONFLICT_RESOURCE_EXISTS
        )
    
    # Validate template_id if provided
    if lead_source_data.template_id is not None:
        template = db.query(Template).filter(Template.id == lead_source_data.template_id).first()
        if not template:
            raise ValidationException(
                message=f"Template with ID {lead_source_data.template_id} not found",
                code=ErrorCode.VALIDATION_ERROR
            )
    
    # Create lead source
    lead_source = LeadSource(
        sender_email=lead_source_data.sender_email,
        identifier_snippet=lead_source_data.identifier_snippet,
        name_regex=lead_source_data.name_regex,
        phone_regex=lead_source_data.phone_regex,
        template_id=lead_source_data.template_id,
        auto_respond_enabled=lead_source_data.auto_respond_enabled
    )
    
    db.add(lead_source)
    db.commit()
    db.refresh(lead_source)
    
    # Create initial version record
    _create_regex_profile_version(db, lead_source, current_user.id)
    db.commit()
    
    # Record audit log
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="lead_source_created",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=f"Created lead source for {lead_source_data.sender_email}"
    )
    
    return LeadSourceResponse.from_orm(lead_source)


@router.get("/lead-sources", response_model=LeadSourceListResponse)
def list_lead_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all lead sources.
    
    Returns all configured lead sources ordered by creation date (newest first).
    
    Args:
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of all lead sources
        
    Requirements:
        - 2.1: Provide endpoints for reading Lead_Source records
    """
    # Get all lead sources
    lead_sources = db.query(LeadSource).order_by(LeadSource.created_at.desc()).all()
    
    # Build response list
    lead_source_responses = [
        LeadSourceResponse.from_orm(ls) for ls in lead_sources
    ]
    
    return LeadSourceListResponse(lead_sources=lead_source_responses)


@router.get("/lead-sources/{lead_source_id}", response_model=LeadSourceResponse)
def get_lead_source(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details for a specific lead source.
    
    Returns lead source configuration including regex patterns and template
    association.
    
    Args:
        lead_source_id: Lead source ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Lead source details
        
    Raises:
        NotFoundException: If lead source not found
        
    Requirements:
        - 2.1: Provide endpoints for reading Lead_Source records
    """
    # Find lead source
    lead_source = db.query(LeadSource).filter(LeadSource.id == lead_source_id).first()
    
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    return LeadSourceResponse.from_orm(lead_source)


@router.put("/lead-sources/{lead_source_id}", response_model=LeadSourceResponse)
def update_lead_source(
    lead_source_id: int,
    lead_source_data: LeadSourceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing lead source's configuration.
    
    Can update any field including regex patterns, template association, and
    auto-respond settings. Validates regex patterns before storage.
    
    Args:
        lead_source_id: Lead source ID
        lead_source_data: Update request data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Updated lead source details
        
    Raises:
        NotFoundException: If lead source not found
        ValidationException: If no fields to update, regex invalid, or template not found
        ConflictException: If sender_email conflicts with another lead source
        
    Requirements:
        - 2.1: Provide endpoints for updating Lead_Source records
        - 2.2: Validate regex pattern syntax
        - 2.6: Sanitize all user input in Lead_Source configurations
        - 2.7: Record all Lead_Source modification operations
    """
    # Find lead source
    lead_source = db.query(LeadSource).filter(LeadSource.id == lead_source_id).first()
    
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Check if any fields to update
    has_updates = any([
        lead_source_data.sender_email is not None,
        lead_source_data.identifier_snippet is not None,
        lead_source_data.name_regex is not None,
        lead_source_data.phone_regex is not None,
        lead_source_data.template_id is not None,
        lead_source_data.auto_respond_enabled is not None
    ])
    
    if not has_updates:
        raise ValidationException(
            message="No fields to update",
            code=ErrorCode.VALIDATION_ERROR
        )
    
    # Track what was updated for audit log
    updated_fields = []
    
    # Update sender_email if provided
    if lead_source_data.sender_email is not None:
        # Check for conflicts with other lead sources
        existing = db.query(LeadSource).filter(
            LeadSource.sender_email == lead_source_data.sender_email,
            LeadSource.id != lead_source_id
        ).first()
        
        if existing:
            raise ConflictException(
                message=f"Lead source with sender email '{lead_source_data.sender_email}' already exists",
                code=ErrorCode.CONFLICT_RESOURCE_EXISTS
            )
        
        lead_source.sender_email = lead_source_data.sender_email
        updated_fields.append("sender_email")
    
    # Update identifier_snippet if provided
    if lead_source_data.identifier_snippet is not None:
        lead_source.identifier_snippet = lead_source_data.identifier_snippet
        updated_fields.append("identifier_snippet")
    
    # Update name_regex if provided
    if lead_source_data.name_regex is not None:
        lead_source.name_regex = lead_source_data.name_regex
        updated_fields.append("name_regex")
    
    # Update phone_regex if provided
    if lead_source_data.phone_regex is not None:
        lead_source.phone_regex = lead_source_data.phone_regex
        updated_fields.append("phone_regex")
    
    # Update template_id if provided
    if lead_source_data.template_id is not None:
        # Validate template exists
        template = db.query(Template).filter(Template.id == lead_source_data.template_id).first()
        if not template:
            raise ValidationException(
                message=f"Template with ID {lead_source_data.template_id} not found",
                code=ErrorCode.VALIDATION_ERROR
            )
        
        lead_source.template_id = lead_source_data.template_id
        updated_fields.append("template_id")
    
    # Update auto_respond_enabled if provided
    if lead_source_data.auto_respond_enabled is not None:
        lead_source.auto_respond_enabled = lead_source_data.auto_respond_enabled
        updated_fields.append("auto_respond_enabled")
    
    # Check if regex profile fields were updated (requires versioning)
    regex_fields_updated = any([
        lead_source_data.name_regex is not None,
        lead_source_data.phone_regex is not None,
        lead_source_data.identifier_snippet is not None
    ])
    
    # Commit changes
    db.commit()
    db.refresh(lead_source)
    
    # Create version record if regex profile was updated
    if regex_fields_updated:
        new_version = _create_regex_profile_version(db, lead_source, current_user.id)
        db.commit()
        
        # Record audit log for version change
        record_audit_log(
            db_session=db,
            user_id=current_user.id,
            action="regex_profile_version_created",
            resource_type="lead_source",
            resource_id=lead_source.id,
            details=f"Created regex profile version {new_version} for lead source {lead_source_id}"
        )
    
    # Record audit log for update
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="lead_source_updated",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=f"Updated lead source {lead_source_id} ({', '.join(updated_fields)})"
    )
    
    return LeadSourceResponse.from_orm(lead_source)


@router.delete("/lead-sources/{lead_source_id}", response_model=LeadSourceDeleteResponse)
def delete_lead_source(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a lead source.
    
    Removes the lead source configuration from the database. Note that this
    does not delete associated leads - they will remain in the database.
    
    Args:
        lead_source_id: Lead source ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Success message
        
    Raises:
        NotFoundException: If lead source not found
        
    Requirements:
        - 2.1: Provide endpoints for deleting Lead_Source records
        - 2.7: Record all Lead_Source deletion operations
    """
    # Find lead source
    lead_source = db.query(LeadSource).filter(LeadSource.id == lead_source_id).first()
    
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Store sender_email for response message
    sender_email = lead_source.sender_email
    
    # Record audit log before deletion
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="lead_source_deleted",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=f"Deleted lead source for {sender_email}"
    )
    
    # Delete lead source
    db.delete(lead_source)
    db.commit()
    
    return LeadSourceDeleteResponse(
        message=f"Lead source for '{sender_email}' deleted successfully"
    )


@router.post("/lead-sources/test-regex", response_model=RegexTestResponse)
def test_regex(
    test_data: RegexTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Test a regex pattern against sample text with timeout protection.
    
    Allows administrators to validate regex patterns before deploying them in
    lead source configurations. Enforces a 1000ms timeout to protect against
    ReDoS (Regular Expression Denial of Service) attacks.
    
    Args:
        test_data: Regex test request containing pattern and sample text
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Test results including match status, captured groups, and matched text
        
    Raises:
        ValidationException: If regex pattern is invalid or timeout occurs
        
    Requirements:
        - 2.3: Provide regex testing harness for validating patterns
        - 2.4: Enforce timeout of 1000 milliseconds for regex execution
        - 14.1: Provide endpoint for testing regex patterns against sample text
        - 14.2: Return match results and captured groups
        - 14.3: Enforce timeout of 1000 milliseconds for regex execution
        - 14.4: Return timeout error if regex execution exceeds timeout
    """
    try:
        # Test regex with 1000ms timeout
        matched, groups, match_text = test_regex_pattern(
            pattern=test_data.pattern,
            text=test_data.sample_text,
            timeout_ms=1000
        )
        
        return RegexTestResponse(
            matched=matched,
            groups=groups,
            match_text=match_text
        )
        
    except RegexTimeoutError:
        raise ValidationException(
            message="Regex execution timeout (1000ms exceeded)",
            code=ErrorCode.VALIDATION_ERROR
        )
    except ValueError as e:
        # Invalid regex pattern
        raise ValidationException(
            message=str(e),
            code=ErrorCode.VALIDATION_ERROR
        )



@router.get("/lead-sources/{lead_source_id}/versions", response_model=RegexProfileVersionListResponse)
def get_lead_source_versions(
    lead_source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get version history for a lead source's regex profile.
    
    Returns all versions of the regex profile in reverse chronological order
    (newest first), allowing administrators to review changes and select
    versions for rollback.
    
    Args:
        lead_source_id: Lead source ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of all regex profile versions
        
    Raises:
        NotFoundException: If lead source not found
        
    Requirements:
        - 9.3: Provide endpoint for retrieving Regex_Profile version history
    """
    # Verify lead source exists
    lead_source = db.query(LeadSource).filter(LeadSource.id == lead_source_id).first()
    
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Get all versions for this lead source
    versions = db.query(RegexProfileVersion).filter(
        RegexProfileVersion.lead_source_id == lead_source_id
    ).order_by(RegexProfileVersion.version.desc()).all()
    
    # Build response list
    version_responses = [
        RegexProfileVersionResponse.from_orm(v) for v in versions
    ]
    
    return RegexProfileVersionListResponse(versions=version_responses)


@router.post("/lead-sources/{lead_source_id}/rollback", response_model=RegexProfileRollbackResponse)
def rollback_lead_source(
    lead_source_id: int,
    rollback_data: RegexProfileRollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rollback a lead source's regex profile to a specific version.
    
    Restores the regex patterns (name_regex, phone_regex, identifier_snippet)
    from the specified version and creates a new version record to maintain
    the complete audit trail.
    
    Args:
        lead_source_id: Lead source ID
        rollback_data: Rollback request containing target version
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Success message with new version number and updated lead source
        
    Raises:
        NotFoundException: If lead source or version not found
        
    Requirements:
        - 9.4: Restore specified version when Regex_Profile rollback is requested
        - 9.7: Record all Regex_Profile rollbacks in audit log
    """
    # Verify lead source exists
    lead_source = db.query(LeadSource).filter(LeadSource.id == lead_source_id).first()
    
    if not lead_source:
        raise NotFoundException(
            message=f"Lead source with ID {lead_source_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Find the target version
    target_version = db.query(RegexProfileVersion).filter(
        RegexProfileVersion.lead_source_id == lead_source_id,
        RegexProfileVersion.version == rollback_data.version
    ).first()
    
    if not target_version:
        raise NotFoundException(
            message=f"Version {rollback_data.version} not found for lead source {lead_source_id}",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Update lead source with values from target version
    lead_source.name_regex = target_version.name_regex
    lead_source.phone_regex = target_version.phone_regex
    lead_source.identifier_snippet = target_version.identifier_snippet
    
    db.commit()
    db.refresh(lead_source)
    
    # Create new version record for the rollback
    new_version = _create_regex_profile_version(db, lead_source, current_user.id)
    db.commit()
    
    # Record audit log for rollback
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="regex_profile_rollback",
        resource_type="lead_source",
        resource_id=lead_source.id,
        details=f"Rolled back lead source {lead_source_id} to version {rollback_data.version} (created new version {new_version})"
    )
    
    return RegexProfileRollbackResponse(
        message=f"Successfully rolled back to version {rollback_data.version}",
        new_version=new_version,
        lead_source=LeadSourceResponse.from_orm(lead_source)
    )

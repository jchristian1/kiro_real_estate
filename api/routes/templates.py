"""
Template management API endpoints.

This module provides REST API endpoints for managing email templates including:
- Creating templates with validation
- Listing all templates
- Getting template details
- Updating templates (creates new version)
- Deleting templates
- Previewing templates with sample data

All endpoints require authentication and integrate with the existing
Template model from the CLI system.

Endpoints:
- POST /api/v1/templates - Create new template
- GET /api/v1/templates - List all templates
- GET /api/v1/templates/{id} - Get template details
- PUT /api/v1/templates/{id} - Update template (creates new version)
- DELETE /api/v1/templates/{id} - Delete template
- POST /api/v1/templates/preview - Preview template with sample data
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from gmail_lead_sync.models import Template
from api.models.web_ui_models import User, TemplateVersion
from api.models.template_models import (
    TemplateCreateRequest,
    TemplateUpdateRequest,
    TemplateResponse,
    TemplateListResponse,
    TemplateDeleteResponse,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateVersionResponse,
    TemplateVersionListResponse,
    TemplateRollbackRequest,
    TemplateRollbackResponse
)
from api.models.error_models import ErrorCode
from api.exceptions import (
    ValidationException,
    NotFoundException,
    ConflictException
)
from api.services.audit_log import record_audit_log


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


def _create_template_version(
    db: Session,
    template: Template,
    user_id: int
) -> int:
    """
    Create a new version record for a template.
    
    Args:
        db: Database session
        template: Template to create version for
        user_id: User ID creating the version
        
    Returns:
        New version number
        
    Requirements:
        - 3.6: Maintain version history for Template modifications
    """
    # Get the latest version number for this template
    latest_version = db.query(TemplateVersion).filter(
        TemplateVersion.template_id == template.id
    ).order_by(TemplateVersion.version.desc()).first()
    
    # Calculate new version number
    new_version = (latest_version.version + 1) if latest_version else 1
    
    # Create version record
    version_record = TemplateVersion(
        template_id=template.id,
        version=new_version,
        name=template.name,
        subject=template.subject,
        body=template.body,
        created_by=user_id
    )
    
    db.add(version_record)
    
    return new_version


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    template_data: TemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new template with validation.
    
    Validates template against email header injection patterns and ensures
    only supported placeholders are used. Creates an initial version record.
    
    Args:
        template_data: Template creation request data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Created template details
        
    Raises:
        ConflictException: If template name already exists
        ValidationException: If validation fails (handled by Pydantic)
        
    Requirements:
        - 3.1: Provide endpoints for creating Template records
        - 3.2: Validate against email header injection patterns
        - 3.4: Validate that all placeholders in templates are supported
        - 3.6: Maintain version history for Template modifications
        - 3.8: Record all Template creation operations
    """
    # Check if template name already exists
    existing = db.query(Template).filter(Template.name == template_data.name).first()
    
    if existing:
        raise ConflictException(
            message=f"Template with name '{template_data.name}' already exists",
            code=ErrorCode.CONFLICT_RESOURCE_EXISTS
        )
    
    # Create template
    template = Template(
        name=template_data.name,
        subject=template_data.subject,
        body=template_data.body
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    # Create initial version record
    _create_template_version(db, template, current_user.id)
    db.commit()
    
    # Record audit log
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_created",
        resource_type="template",
        resource_id=template.id,
        details=f"Created template '{template_data.name}'"
    )
    
    return TemplateResponse.from_orm(template)


@router.get("/templates", response_model=TemplateListResponse)
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all templates.
    
    Returns all configured templates ordered by creation date (newest first).
    
    Args:
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of all templates
        
    Requirements:
        - 3.1: Provide endpoints for reading Template records
    """
    # Get all templates
    templates = db.query(Template).order_by(Template.created_at.desc()).all()
    
    # Build response list
    template_responses = [
        TemplateResponse.from_orm(t) for t in templates
    ]
    
    return TemplateListResponse(templates=template_responses)


@router.get("/templates/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details for a specific template.
    
    Returns template configuration including name, subject, and body.
    
    Args:
        template_id: Template ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Template details
        
    Raises:
        NotFoundException: If template not found
        
    Requirements:
        - 3.1: Provide endpoints for reading Template records
    """
    # Find template
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    return TemplateResponse.from_orm(template)


@router.put("/templates/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    template_data: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing template's configuration.
    
    Can update name, subject, and/or body. Creates a new version record to
    maintain complete history for rollback capability.
    
    Args:
        template_id: Template ID
        template_data: Update request data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Updated template details
        
    Raises:
        NotFoundException: If template not found
        ValidationException: If no fields to update or validation fails
        ConflictException: If template name conflicts with another template
        
    Requirements:
        - 3.1: Provide endpoints for updating Template records
        - 3.2: Validate against email header injection patterns
        - 3.4: Validate that all placeholders in templates are supported
        - 3.6: Maintain version history for Template modifications
        - 3.8: Record all Template modification operations
    """
    # Find template
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Check if any fields to update
    has_updates = any([
        template_data.name is not None,
        template_data.subject is not None,
        template_data.body is not None
    ])
    
    if not has_updates:
        raise ValidationException(
            message="No fields to update",
            code=ErrorCode.VALIDATION_ERROR
        )
    
    # Track what was updated for audit log
    updated_fields = []
    
    # Update name if provided
    if template_data.name is not None:
        # Check for conflicts with other templates
        existing = db.query(Template).filter(
            Template.name == template_data.name,
            Template.id != template_id
        ).first()
        
        if existing:
            raise ConflictException(
                message=f"Template with name '{template_data.name}' already exists",
                code=ErrorCode.CONFLICT_RESOURCE_EXISTS
            )
        
        template.name = template_data.name
        updated_fields.append("name")
    
    # Update subject if provided
    if template_data.subject is not None:
        template.subject = template_data.subject
        updated_fields.append("subject")
    
    # Update body if provided
    if template_data.body is not None:
        template.body = template_data.body
        updated_fields.append("body")
    
    # Commit changes
    db.commit()
    db.refresh(template)
    
    # Create version record for the update
    new_version = _create_template_version(db, template, current_user.id)
    db.commit()
    
    # Record audit log for version change
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_version_created",
        resource_type="template",
        resource_id=template.id,
        details=f"Created template version {new_version} for template {template_id}"
    )
    
    # Record audit log for update
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_updated",
        resource_type="template",
        resource_id=template.id,
        details=f"Updated template {template_id} ({', '.join(updated_fields)})"
    )
    
    return TemplateResponse.from_orm(template)


@router.delete("/templates/{template_id}", response_model=TemplateDeleteResponse)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a template.
    
    Removes the template from the database. Note that this will also cascade
    delete all version history for the template.
    
    Args:
        template_id: Template ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Success message
        
    Raises:
        NotFoundException: If template not found
        
    Requirements:
        - 3.1: Provide endpoints for deleting Template records
        - 3.8: Record all Template deletion operations
    """
    # Find template
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Store template name for response message
    template_name = template.name
    
    # Record audit log before deletion
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_deleted",
        resource_type="template",
        resource_id=template.id,
        details=f"Deleted template '{template_name}'"
    )
    
    # Delete template (cascade will delete version history)
    db.delete(template)
    db.commit()
    
    return TemplateDeleteResponse(
        message=f"Template '{template_name}' deleted successfully"
    )


@router.post("/templates/preview", response_model=TemplatePreviewResponse)
def preview_template(
    preview_data: TemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview a template with sample data.
    
    Substitutes all placeholders with sample values and escapes HTML in the body
    for safe display. This allows users to see how a template will look before
    saving it.
    
    Sample data used:
    - {lead_name}: "John Doe"
    - {agent_name}: "Agent Smith"
    - {agent_phone}: "555-9999"
    - {agent_email}: "agent@example.com"
    
    Args:
        preview_data: Template preview request data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Rendered template with sample data
        
    Requirements:
        - 3.3: Provide a template preview feature with sample placeholder data
        - 10.7: Escape HTML content in user-generated text displayed in Web_UI
        - 13.1: Provide endpoint for rendering Template preview with sample data
        - 13.2: Substitute all placeholders with sample values
        - 13.3: Display rendered Template preview in the template editor
    """
    import html
    
    # Sample data for placeholders
    sample_data = {
        '{lead_name}': 'John Doe',
        '{agent_name}': 'Agent Smith',
        '{agent_phone}': '555-9999',
        '{agent_email}': 'agent@example.com'
    }
    
    # Substitute placeholders in subject
    rendered_subject = preview_data.subject
    for placeholder, value in sample_data.items():
        rendered_subject = rendered_subject.replace(placeholder, value)
    
    # Substitute placeholders in body
    rendered_body = preview_data.body
    for placeholder, value in sample_data.items():
        rendered_body = rendered_body.replace(placeholder, value)
    
    # Escape HTML in body for safe display
    # Note: We escape after substitution to preserve the template structure
    rendered_body = html.escape(rendered_body)
    
    return TemplatePreviewResponse(
        subject=rendered_subject,
        body=rendered_body
    )


@router.get("/templates/{template_id}/versions", response_model=TemplateVersionListResponse)
def get_template_versions(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get version history for a template.
    
    Returns all versions of the template in reverse chronological order
    (newest first), allowing administrators to review changes and select
    versions for rollback.
    
    Args:
        template_id: Template ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of all template versions
        
    Raises:
        NotFoundException: If template not found
        
    Requirements:
        - 3.6: Maintain version history for Template modifications
    """
    # Verify template exists
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Get all versions for this template
    versions = db.query(TemplateVersion).filter(
        TemplateVersion.template_id == template_id
    ).order_by(TemplateVersion.version.desc()).all()
    
    # Build response list
    version_responses = [
        TemplateVersionResponse.from_orm(v) for v in versions
    ]
    
    return TemplateVersionListResponse(versions=version_responses)


@router.post("/templates/{template_id}/rollback", response_model=TemplateRollbackResponse)
def rollback_template(
    template_id: int,
    rollback_data: TemplateRollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Rollback a template to a specific version.
    
    Restores the template content (name, subject, body) from the specified
    version and creates a new version record to maintain the complete audit
    trail.
    
    Args:
        template_id: Template ID
        rollback_data: Rollback request containing target version
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Success message with new version number and updated template
        
    Raises:
        NotFoundException: If template or version not found
        
    Requirements:
        - 3.7: Support rollback to previous versions
        - 3.8: Record all Template rollback operations
    """
    # Verify template exists
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Find the target version
    target_version = db.query(TemplateVersion).filter(
        TemplateVersion.template_id == template_id,
        TemplateVersion.version == rollback_data.version
    ).first()
    
    if not target_version:
        raise NotFoundException(
            message=f"Version {rollback_data.version} not found for template {template_id}",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Update template with values from target version
    template.name = target_version.name
    template.subject = target_version.subject
    template.body = target_version.body
    
    db.commit()
    db.refresh(template)
    
    # Create new version record for the rollback
    new_version = _create_template_version(db, template, current_user.id)
    db.commit()
    
    # Record audit log for rollback
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_rollback",
        resource_type="template",
        resource_id=template.id,
        details=f"Rolled back template {template_id} to version {rollback_data.version} (created new version {new_version})"
    )
    
    return TemplateRollbackResponse(
        message=f"Successfully rolled back to version {rollback_data.version}",
        new_version=new_version,
        template=TemplateResponse.from_orm(template)
    )


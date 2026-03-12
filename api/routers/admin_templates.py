"""
Template management API endpoints.

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

from api.models.web_ui_models import User
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
    TemplateRollbackResponse,
)
from api.models.error_models import ErrorCode
from api.exceptions import ValidationException, NotFoundException, ConflictException
from api.services.audit_log import record_audit_log
from api.repositories.template_repository import AdminTemplateRepository

router = APIRouter()


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


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    template_data: TemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new template. Requirements: 3.1, 3.2, 3.4, 3.6, 3.8"""
    repo = AdminTemplateRepository(db)

    if repo.get_by_name(template_data.name):
        raise ConflictException(
            message=f"Template with name '{template_data.name}' already exists",
            code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
        )

    template = repo.create(template_data.name, template_data.subject, template_data.body)
    repo.create_version(template, current_user.id)

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_created",
        resource_type="template",
        resource_id=template.id,
        details=f"Created template '{template_data.name}'",
    )
    return TemplateResponse.from_orm(template)


@router.get("/templates", response_model=TemplateListResponse)
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all templates. Requirements: 3.1"""
    repo = AdminTemplateRepository(db)
    templates = repo.list_all()
    return TemplateListResponse(templates=[TemplateResponse.from_orm(t) for t in templates])


@router.get("/templates/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific template. Requirements: 3.1"""
    repo = AdminTemplateRepository(db)
    template = repo.get_by_id(template_id)
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    return TemplateResponse.from_orm(template)


@router.put("/templates/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    template_data: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing template. Requirements: 3.1, 3.2, 3.4, 3.6, 3.8"""
    repo = AdminTemplateRepository(db)

    template = repo.get_by_id(template_id)
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    has_updates = any([
        template_data.name is not None,
        template_data.subject is not None,
        template_data.body is not None,
    ])
    if not has_updates:
        raise ValidationException(message="No fields to update", code=ErrorCode.VALIDATION_ERROR)

    if template_data.name is not None:
        conflict = repo.get_by_name_excluding(template_data.name, template_id)
        if conflict:
            raise ConflictException(
                message=f"Template with name '{template_data.name}' already exists",
                code=ErrorCode.CONFLICT_RESOURCE_EXISTS,
            )

    updated_fields = []
    if template_data.name is not None:
        updated_fields.append("name")
    if template_data.subject is not None:
        updated_fields.append("subject")
    if template_data.body is not None:
        updated_fields.append("body")

    template = repo.update(template_id, template_data.name, template_data.subject, template_data.body)
    new_version = repo.create_version(template, current_user.id)

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_version_created",
        resource_type="template",
        resource_id=template.id,
        details=f"Created template version {new_version} for template {template_id}",
    )
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_updated",
        resource_type="template",
        resource_id=template.id,
        details=f"Updated template {template_id} ({', '.join(updated_fields)})",
    )
    return TemplateResponse.from_orm(template)


@router.delete("/templates/{template_id}", response_model=TemplateDeleteResponse)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a template. Requirements: 3.1, 3.8"""
    repo = AdminTemplateRepository(db)
    template = repo.get_by_id(template_id)
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    template_name = template.name
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_deleted",
        resource_type="template",
        resource_id=template.id,
        details=f"Deleted template '{template_name}'",
    )
    repo.delete(template_id)
    return TemplateDeleteResponse(message=f"Template '{template_name}' deleted successfully")


@router.post("/templates/preview", response_model=TemplatePreviewResponse)
def preview_template(
    preview_data: TemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview a template with sample data. Requirements: 3.3, 13.1, 13.2, 13.3"""
    import html

    sample_data = {
        '{lead_name}': 'John Doe',
        '{agent_name}': 'Agent Smith',
        '{agent_phone}': '555-9999',
        '{agent_email}': 'agent@example.com',
    }

    rendered_subject = preview_data.subject
    rendered_body = preview_data.body
    for placeholder, value in sample_data.items():
        rendered_subject = rendered_subject.replace(placeholder, value)
        rendered_body = rendered_body.replace(placeholder, value)

    rendered_body = html.escape(rendered_body)
    return TemplatePreviewResponse(subject=rendered_subject, body=rendered_body)


@router.get("/templates/{template_id}/versions", response_model=TemplateVersionListResponse)
def get_template_versions(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get version history for a template. Requirements: 3.6"""
    repo = AdminTemplateRepository(db)
    if not repo.get_by_id(template_id):
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    versions = repo.list_versions(template_id)
    return TemplateVersionListResponse(
        versions=[TemplateVersionResponse.from_orm(v) for v in versions]
    )


@router.post("/templates/{template_id}/rollback", response_model=TemplateRollbackResponse)
def rollback_template(
    template_id: int,
    rollback_data: TemplateRollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rollback a template to a specific version. Requirements: 3.7, 3.8"""
    repo = AdminTemplateRepository(db)

    template = repo.get_by_id(template_id)
    if not template:
        raise NotFoundException(
            message=f"Template with ID {template_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    target_version = repo.get_version_by_number(template_id, rollback_data.version)
    if not target_version:
        raise NotFoundException(
            message=f"Version {rollback_data.version} not found for template {template_id}",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    template = repo.update(template_id, target_version.name, target_version.subject, target_version.body)
    new_version = repo.create_version(template, current_user.id)

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="template_rollback",
        resource_type="template",
        resource_id=template.id,
        details=f"Rolled back template {template_id} to version {rollback_data.version} (created new version {new_version})",
    )
    return TemplateRollbackResponse(
        message=f"Successfully rolled back to version {rollback_data.version}",
        new_version=new_version,
        template=TemplateResponse.from_orm(template),
    )

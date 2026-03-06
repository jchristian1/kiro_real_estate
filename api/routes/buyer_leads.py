"""
Admin API routes for buyer lead qualification — form template CRUD and version management.

Mounted under /api/v1/buyer-leads/ (registered in main.py).

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 17.1, 17.2
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.exceptions import NotFoundException, ValidationException
from api.models.error_models import ErrorCode
from api.models.web_ui_models import User
from gmail_lead_sync.models import Lead
from gmail_lead_sync.preapproval.models_preapproval import (
    FormLogicRule,
    FormQuestion,
    FormTemplate,
    FormVersion,
    ScoringConfig,
    ScoringVersion,
)
from gmail_lead_sync.preapproval.scoring_engine import ScoringEngine

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Shared dependencies (same pattern as companies.py / leads.py)
# ---------------------------------------------------------------------------

def get_db():
    """Database dependency — overridden in tests."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authentication dependency — overridden in tests."""
    from api.auth import get_current_user as auth_get_current_user
    return auth_get_current_user(request, db)


# ---------------------------------------------------------------------------
# Tenant isolation helper
# ---------------------------------------------------------------------------

def _assert_tenant(tid: int, current_user: User) -> None:
    """
    Enforce tenant isolation (Req 17.1, 17.2).

    Raises NotFoundException (404) — not 403 — to prevent tenant enumeration.
    Admin role bypasses tenant isolation.
    """
    if getattr(current_user, 'role', None) == 'admin':
        return
    if current_user.company_id != tid:
        raise NotFoundException(
            message="Tenant not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class FormQuestionCreate(BaseModel):
    question_key: str
    type: str  # single_choice | multi_select | free_text | phone | email
    label: str
    required: bool = True
    options_json: str | None = None
    order: int
    validation_json: str | None = None


class FormLogicRuleCreate(BaseModel):
    rule_json: str


class PublishFormVersionRequest(BaseModel):
    questions: list[FormQuestionCreate]
    logic_rules: list[FormLogicRuleCreate] = []


class CreateFormTemplateRequest(BaseModel):
    name: str
    intent_type: str = "BUY"


class UpdateFormTemplateRequest(BaseModel):
    name: str | None = None
    status: str | None = None


# ---------------------------------------------------------------------------
# Form Template CRUD  (Req 2.1)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/forms")
def list_form_templates(
    tid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all FormTemplate records for the authenticated tenant (Req 2.1, 17.1)."""
    _assert_tenant(tid, current_user)
    templates = (
        db.query(FormTemplate)
        .filter(FormTemplate.tenant_id == tid)
        .order_by(FormTemplate.created_at.desc())
        .all()
    )
    return [_template_to_dict(t) for t in templates]


@router.post("/tenants/{tid}/forms", status_code=status.HTTP_201_CREATED)
def create_form_template(
    tid: int,
    body: CreateFormTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new FormTemplate for the tenant (Req 2.1)."""
    _assert_tenant(tid, current_user)
    template = FormTemplate(
        tenant_id=tid,
        intent_type=body.intent_type,
        name=body.name,
        status="draft",
        created_at=datetime.utcnow(),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _template_to_dict(template)


@router.get("/tenants/{tid}/forms/{fid}")
def get_form_template(
    tid: int,
    fid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single FormTemplate; 404 if not found or wrong tenant (Req 2.1, 17.2)."""
    _assert_tenant(tid, current_user)
    template = _get_template_or_404(db, tid, fid)
    return _template_to_dict(template)


@router.put("/tenants/{tid}/forms/{fid}")
def update_form_template(
    tid: int,
    fid: int,
    body: UpdateFormTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update FormTemplate name or status (Req 2.1)."""
    _assert_tenant(tid, current_user)
    template = _get_template_or_404(db, tid, fid)
    if body.name is not None:
        template.name = body.name
    if body.status is not None:
        template.status = body.status
    db.commit()
    db.refresh(template)
    return _template_to_dict(template)


@router.delete("/tenants/{tid}/forms/{fid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_form_template(
    tid: int,
    fid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a FormTemplate (Req 2.1)."""
    _assert_tenant(tid, current_user)
    template = _get_template_or_404(db, tid, fid)
    db.delete(template)
    db.commit()


# ---------------------------------------------------------------------------
# Form Version management  (Req 2.2 – 2.8)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/forms/{fid}/versions")
def list_form_versions(
    tid: int,
    fid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all FormVersion records for a template (Req 2.2)."""
    _assert_tenant(tid, current_user)
    _get_template_or_404(db, tid, fid)
    versions = (
        db.query(FormVersion)
        .filter(FormVersion.template_id == fid)
        .order_by(FormVersion.version_number.desc())
        .all()
    )
    return [_version_to_dict(v) for v in versions]


@router.post("/tenants/{tid}/forms/{fid}/versions", status_code=status.HTTP_201_CREATED)
def publish_form_version(
    tid: int,
    fid: int,
    body: PublishFormVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Publish a new FormVersion (Req 2.2, 2.3, 2.5, 2.6, 2.7, 2.8).

    - Validates unique question_keys (Req 2.7)
    - Validates question types (Req 2.6)
    - Snapshots questions + logic rules into schema_json (Req 2.2)
    - Sets is_active=True on new version, False on all others (Req 2.3, 2.5)
    - Sets published_at = now() (Req 2.2)
    """
    _assert_tenant(tid, current_user)
    template = _get_template_or_404(db, tid, fid)

    # Req 2.7 — validate unique question_keys
    keys = [q.question_key for q in body.questions]
    if len(keys) != len(set(keys)):
        raise ValidationException(
            message="Duplicate question_key values are not allowed within a form version",
            code="VALIDATION_ERROR",
        )

    # Req 2.6 — validate question types
    valid_types = {"single_choice", "multi_select", "free_text", "phone", "email"}
    for q in body.questions:
        if q.type not in valid_types:
            raise ValidationException(
                message=f"Invalid question type '{q.type}'. Must be one of: {', '.join(sorted(valid_types))}",
                code="VALIDATION_ERROR",
            )

    # Req 2.8 — validate logic rule JSON is parseable
    for rule in body.logic_rules:
        try:
            json.loads(rule.rule_json)
        except json.JSONDecodeError as exc:
            raise ValidationException(
                message=f"Invalid logic rule JSON: {exc}",
                code="VALIDATION_ERROR",
            )

    # Determine next version number
    last_version = (
        db.query(FormVersion)
        .filter(FormVersion.template_id == fid)
        .order_by(FormVersion.version_number.desc())
        .first()
    )
    next_version_number = (last_version.version_number + 1) if last_version else 1

    # Req 2.2 — snapshot questions + logic rules into schema_json
    schema_snapshot: dict[str, Any] = {
        "questions": [q.model_dump() for q in body.questions],
        "logic_rules": [r.model_dump() for r in body.logic_rules],
    }

    now = datetime.utcnow()

    # Req 2.3, 2.5 — deactivate all existing versions for this template
    db.query(FormVersion).filter(FormVersion.template_id == fid).update(
        {"is_active": False}, synchronize_session="fetch"
    )

    # Create new active version
    version = FormVersion(
        template_id=fid,
        version_number=next_version_number,
        schema_json=json.dumps(schema_snapshot),
        created_at=now,
        published_at=now,
        is_active=True,
    )
    db.add(version)
    db.flush()  # get version.id before inserting children

    # Persist FormQuestion rows
    for q in body.questions:
        db.add(FormQuestion(
            form_version_id=version.id,
            question_key=q.question_key,
            type=q.type,
            label=q.label,
            required=q.required,
            options_json=q.options_json,
            order=q.order,
            validation_json=q.validation_json,
        ))

    # Persist FormLogicRule rows (Req 2.8)
    for rule in body.logic_rules:
        db.add(FormLogicRule(
            form_version_id=version.id,
            rule_json=rule.rule_json,
        ))

    db.commit()
    db.refresh(version)
    return _version_to_dict(version)


@router.post("/tenants/{tid}/forms/{fid}/versions/{vid}/rollback")
def rollback_form_version(
    tid: int,
    fid: int,
    vid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Rollback to a previous FormVersion (Req 2.4, 2.5).

    Sets is_active=True on the target version and False on all others.
    """
    _assert_tenant(tid, current_user)
    _get_template_or_404(db, tid, fid)  # ensures template belongs to tenant

    target = (
        db.query(FormVersion)
        .filter(FormVersion.id == vid, FormVersion.template_id == fid)
        .first()
    )
    if not target:
        raise NotFoundException(
            message=f"FormVersion {vid} not found for form {fid}",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    # Req 2.4, 2.5 — deactivate all, then activate target
    db.query(FormVersion).filter(FormVersion.template_id == fid).update(
        {"is_active": False}, synchronize_session="fetch"
    )
    target.is_active = True
    db.commit()
    db.refresh(target)
    return _version_to_dict(target)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_template_or_404(db: Session, tid: int, fid: int) -> FormTemplate:
    """Fetch FormTemplate filtered by both id and tenant_id; raise 404 otherwise."""
    template = (
        db.query(FormTemplate)
        .filter(FormTemplate.id == fid, FormTemplate.tenant_id == tid)
        .first()
    )
    if not template:
        raise NotFoundException(
            message=f"FormTemplate {fid} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    return template


def _template_to_dict(t: FormTemplate) -> dict:
    return {
        "id": t.id,
        "tenant_id": t.tenant_id,
        "intent_type": t.intent_type,
        "name": t.name,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _version_to_dict(v: FormVersion) -> dict:
    return {
        "id": v.id,
        "template_id": v.template_id,
        "version_number": v.version_number,
        "schema_json": v.schema_json,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "published_at": v.published_at.isoformat() if v.published_at else None,
    }


# ---------------------------------------------------------------------------
# Scoring — Pydantic request models  (Req 6.1 – 6.5)
# ---------------------------------------------------------------------------

class CreateScoringConfigRequest(BaseModel):
    name: str
    intent_type: str = "BUY"


class ScoringRuleCreate(BaseModel):
    source: str = "answer"  # "answer" | "metadata"
    key: str
    answer_value: Any
    points: int
    reason: str = ""


class PublishScoringVersionRequest(BaseModel):
    rules: list[ScoringRuleCreate]
    thresholds: dict[str, int]  # {"HOT": 80, "WARM": 50}


class SimulateRequest(BaseModel):
    answers: dict[str, Any]
    metadata: dict[str, Any] = {}
    intent_type: str = "BUY"


# ---------------------------------------------------------------------------
# Scoring Config CRUD  (Req 6.1)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/scoring")
def list_scoring_configs(
    tid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all ScoringConfig records for the authenticated tenant (Req 6.1, 17.1)."""
    _assert_tenant(tid, current_user)
    configs = (
        db.query(ScoringConfig)
        .filter(ScoringConfig.tenant_id == tid)
        .order_by(ScoringConfig.created_at.desc())
        .all()
    )
    return [_scoring_config_to_dict(c) for c in configs]


@router.post("/tenants/{tid}/scoring", status_code=status.HTTP_201_CREATED)
def create_scoring_config(
    tid: int,
    body: CreateScoringConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new ScoringConfig for the tenant (Req 6.1)."""
    _assert_tenant(tid, current_user)
    config = ScoringConfig(
        tenant_id=tid,
        intent_type=body.intent_type,
        name=body.name,
        created_at=datetime.utcnow(),
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return _scoring_config_to_dict(config)


@router.put("/tenants/{tid}/scoring/{sid}")
def update_scoring_config(
    tid: int,
    sid: int,
    body: CreateScoringConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a ScoringConfig (Req 6.1)."""
    _assert_tenant(tid, current_user)
    config = _get_scoring_config_or_404(db, tid, sid)
    config.name = body.name
    db.commit()
    db.refresh(config)
    return _scoring_config_to_dict(config)


@router.delete("/tenants/{tid}/scoring/{sid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scoring_config(
    tid: int,
    sid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a ScoringConfig and all its versions (Req 6.1)."""
    _assert_tenant(tid, current_user)
    config = _get_scoring_config_or_404(db, tid, sid)
    db.delete(config)
    db.commit()


@router.post("/tenants/{tid}/scoring/{sid}/versions/{vid}/rollback")
def rollback_scoring_version(
    tid: int,
    sid: int,
    vid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rollback to a previous ScoringVersion."""
    _assert_tenant(tid, current_user)
    _get_scoring_config_or_404(db, tid, sid)
    target = (
        db.query(ScoringVersion)
        .filter(ScoringVersion.id == vid, ScoringVersion.scoring_config_id == sid)
        .first()
    )
    if not target:
        raise NotFoundException(
            message=f"ScoringVersion {vid} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    db.query(ScoringVersion).filter(ScoringVersion.scoring_config_id == sid).update(
        {"is_active": False}, synchronize_session="fetch"
    )
    target.is_active = True
    db.commit()
    db.refresh(target)
    return _scoring_version_to_dict(target)


# ---------------------------------------------------------------------------
# Scoring Version management  (Req 6.2, 6.3, 6.4)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/scoring/{sid}/versions")
def list_scoring_versions(
    tid: int,
    sid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all ScoringVersion records for a config (Req 6.2)."""
    _assert_tenant(tid, current_user)
    _get_scoring_config_or_404(db, tid, sid)
    versions = (
        db.query(ScoringVersion)
        .filter(ScoringVersion.scoring_config_id == sid)
        .order_by(ScoringVersion.version_number.desc())
        .all()
    )
    return [_scoring_version_to_dict(v) for v in versions]


@router.post("/tenants/{tid}/scoring/{sid}/versions", status_code=status.HTTP_201_CREATED)
def publish_scoring_version(
    tid: int,
    sid: int,
    body: PublishScoringVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Publish a new ScoringVersion (Req 6.2, 6.3, 6.4).

    - Validates thresholds: HOT > WARM >= 0 (Req 6.4)
    - Sets is_active=True on new version, False on all others (Req 6.2, 6.3)
    - Sets published_at = now()
    """
    _assert_tenant(tid, current_user)
    scoring_config = _get_scoring_config_or_404(db, tid, sid)

    # Req 6.4 — validate thresholds
    thresholds = body.thresholds
    if "HOT" not in thresholds or "WARM" not in thresholds:
        raise ValidationException(
            message="thresholds must contain both 'HOT' and 'WARM' keys",
            code="VALIDATION_ERROR",
        )
    if not (thresholds["HOT"] > thresholds["WARM"] >= 0):
        raise ValidationException(
            message="thresholds must satisfy: HOT > WARM >= 0",
            code="VALIDATION_ERROR",
        )

    # Determine next version number
    last_version = (
        db.query(ScoringVersion)
        .filter(ScoringVersion.scoring_config_id == sid)
        .order_by(ScoringVersion.version_number.desc())
        .first()
    )
    next_version_number = (last_version.version_number + 1) if last_version else 1

    now = datetime.utcnow()

    # Req 6.2, 6.3 — deactivate all existing versions for this config
    db.query(ScoringVersion).filter(ScoringVersion.scoring_config_id == sid).update(
        {"is_active": False}, synchronize_session="fetch"
    )

    version = ScoringVersion(
        scoring_config_id=sid,
        version_number=next_version_number,
        rules_json=json.dumps([r.model_dump() for r in body.rules]),
        thresholds_json=json.dumps(thresholds),
        created_at=now,
        published_at=now,
        is_active=True,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return _scoring_version_to_dict(version)


# ---------------------------------------------------------------------------
# Simulation endpoint  (Req 6.5, 15.2)
# ---------------------------------------------------------------------------

@router.post("/tenants/{tid}/simulate")
def simulate_scoring(
    tid: int,
    body: SimulateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compute score without persisting; return ScoreResult (Req 6.5, 15.2).

    Uses the active ScoringVersion for the tenant's intent_type.
    """
    _assert_tenant(tid, current_user)

    # Resolve active ScoringVersion for this tenant + intent_type
    active_version = (
        db.query(ScoringVersion)
        .join(ScoringConfig)
        .filter(
            ScoringConfig.tenant_id == tid,
            ScoringConfig.intent_type == body.intent_type,
            ScoringVersion.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not active_version:
        raise NotFoundException(
            message=f"No active scoring version found for tenant {tid} and intent_type {body.intent_type}",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    engine = ScoringEngine()
    result = engine.compute(
        answers=body.answers,
        scoring_version=active_version,
        metadata=body.metadata,
    )

    return {
        "total": result.total,
        "bucket": result.bucket.value,
        "breakdown": [
            {
                "question_key": item.question_key,
                "answer": item.answer,
                "points": item.points,
                "reason": item.reason,
            }
            for item in result.breakdown
        ],
        "explanation": result.explanation,
    }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _get_scoring_config_or_404(db: Session, tid: int, sid: int) -> ScoringConfig:
    """Fetch ScoringConfig filtered by both id and tenant_id; raise 404 otherwise."""
    config = (
        db.query(ScoringConfig)
        .filter(ScoringConfig.id == sid, ScoringConfig.tenant_id == tid)
        .first()
    )
    if not config:
        raise NotFoundException(
            message=f"ScoringConfig {sid} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    return config


def _scoring_config_to_dict(c: ScoringConfig) -> dict:
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "intent_type": c.intent_type,
        "name": c.name,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _scoring_version_to_dict(v: ScoringVersion) -> dict:
    return {
        "id": v.id,
        "scoring_config_id": v.scoring_config_id,
        "version_number": v.version_number,
        "rules_json": v.rules_json,
        "thresholds_json": v.thresholds_json,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "published_at": v.published_at.isoformat() if v.published_at else None,
    }


# ---------------------------------------------------------------------------
# Message Templates — Pydantic request models  (Req 7.1, 7.5, 7.6)
# ---------------------------------------------------------------------------

class CreateMessageTemplateRequest(BaseModel):
    key: str  # MessageTemplateKey value: "INITIAL_INVITE_EMAIL" | "POST_SUBMISSION_EMAIL"
    intent_type: str = "BUY"


class PublishMessageTemplateVersionRequest(BaseModel):
    subject_template: str
    body_template: str
    variants_json: str | None = None  # JSON string for POST_SUBMISSION_EMAIL variants


class PreviewRequest(BaseModel):
    subject_template: str
    body_template: str
    sample_context: dict[str, str] = {}
    context: dict[str, str] = {}  # alias accepted from frontend


# ---------------------------------------------------------------------------
# Message Template CRUD  (Req 7.1)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/message-templates")
def list_message_templates(
    tid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all MessageTemplate records for the authenticated tenant (Req 7.1, 17.1)."""
    _assert_tenant(tid, current_user)
    from gmail_lead_sync.preapproval.models_preapproval import MessageTemplate
    templates = (
        db.query(MessageTemplate)
        .filter(MessageTemplate.tenant_id == tid)
        .order_by(MessageTemplate.created_at.desc())
        .all()
    )
    return [_message_template_to_dict(t) for t in templates]


@router.get("/tenants/{tid}/message-templates/{mid}")
def get_message_template(
    tid: int,
    mid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single MessageTemplate (Req 7.1, 17.2)."""
    _assert_tenant(tid, current_user)
    template = _get_message_template_or_404(db, tid, mid)
    return _message_template_to_dict(template)


@router.get("/tenants/{tid}/message-templates/{mid}/versions")
def list_message_template_versions(
    tid: int,
    mid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all MessageTemplateVersion records for a template (Req 7.2)."""
    from gmail_lead_sync.preapproval.models_preapproval import MessageTemplateVersion
    _assert_tenant(tid, current_user)
    _get_message_template_or_404(db, tid, mid)
    versions = (
        db.query(MessageTemplateVersion)
        .filter(MessageTemplateVersion.template_id == mid)
        .order_by(MessageTemplateVersion.version_number.desc())
        .all()
    )
    return [_message_template_version_to_dict(v) for v in versions]


@router.post("/tenants/{tid}/message-templates", status_code=status.HTTP_201_CREATED)
def create_message_template(
    tid: int,
    body: CreateMessageTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new MessageTemplate for the tenant (Req 7.1)."""
    _assert_tenant(tid, current_user)
    from gmail_lead_sync.preapproval.models_preapproval import MessageTemplate
    template = MessageTemplate(
        tenant_id=tid,
        intent_type=body.intent_type,
        key=body.key,
        created_at=datetime.utcnow(),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _message_template_to_dict(template)


# ---------------------------------------------------------------------------
# Message Template Version management  (Req 7.2, 7.3, 7.5, 7.6, 17.8)
# ---------------------------------------------------------------------------

@router.post("/tenants/{tid}/message-templates/{mid}/versions", status_code=status.HTTP_201_CREATED)
def publish_message_template_version(
    tid: int,
    mid: int,
    body: PublishMessageTemplateVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Publish a new MessageTemplateVersion (Req 7.2, 7.3, 7.5, 7.6, 17.8).

    - Req 7.6 / 17.8: Reject subject_template (and variant subjects) containing newline characters
    - Req 7.5: Validate all {{variable}} tokens against SUPPORTED_VARS
    - Req 7.2, 7.3: Set is_active=True on new version, False on all others for same template_id
    - Sets published_at = now()
    """
    import re as _re
    _assert_tenant(tid, current_user)
    from gmail_lead_sync.preapproval.models_preapproval import MessageTemplate, MessageTemplateVersion
    from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine

    msg_template = _get_message_template_or_404(db, tid, mid)

    # Req 7.6 / 17.8 — reject subject_template containing newline characters
    if "\n" in body.subject_template or "\r" in body.subject_template:
        raise ValidationException(
            message="subject_template must not contain newline characters",
            code="VALIDATION_ERROR",
        )

    # Collect all text to validate for unknown variables
    texts_to_validate = [body.subject_template, body.body_template]

    # Parse and validate variants_json if provided
    variants: dict | None = None
    if body.variants_json is not None:
        try:
            variants = json.loads(body.variants_json)
        except json.JSONDecodeError as exc:
            raise ValidationException(
                message=f"Invalid variants_json: {exc}",
                code="VALIDATION_ERROR",
            )
        # Req 7.6 / 17.8 — reject variant subjects containing newline characters
        for variant_key, variant_data in variants.items():
            variant_subject = variant_data.get("subject", "")
            if variant_subject and ("\n" in variant_subject or "\r" in variant_subject):
                raise ValidationException(
                    message=f"Variant '{variant_key}' subject must not contain newline characters",
                    code="VALIDATION_ERROR",
                )
            texts_to_validate.append(variant_subject)
            texts_to_validate.append(variant_data.get("body", ""))

    # Req 7.5 — validate all {{variable}} tokens against SUPPORTED_VARS
    _var_re = _re.compile(r"\{\{([\w.]+)\}\}")
    all_vars: set[str] = set()
    for text in texts_to_validate:
        all_vars.update(_var_re.findall(text))

    unknown_vars = all_vars - TemplateRenderEngine.SUPPORTED_VARS
    if unknown_vars:
        raise ValidationException(
            message=f"Template contains unknown variable(s): {', '.join(sorted(unknown_vars))}",
            code="VALIDATION_ERROR",
        )

    # Determine next version number
    last_version = (
        db.query(MessageTemplateVersion)
        .filter(MessageTemplateVersion.template_id == mid)
        .order_by(MessageTemplateVersion.version_number.desc())
        .first()
    )
    next_version_number = (last_version.version_number + 1) if last_version else 1

    now = datetime.utcnow()

    # Req 7.2, 7.3 — deactivate all existing versions for this template
    db.query(MessageTemplateVersion).filter(MessageTemplateVersion.template_id == mid).update(
        {"is_active": False}, synchronize_session="fetch"
    )

    version = MessageTemplateVersion(
        template_id=mid,
        version_number=next_version_number,
        subject_template=body.subject_template,
        body_template=body.body_template,
        variants_json=body.variants_json,
        created_at=now,
        published_at=now,
        is_active=True,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return _message_template_version_to_dict(version)


# ---------------------------------------------------------------------------
# Message Template Preview  (Req 7.5, 8.1)
# ---------------------------------------------------------------------------

@router.post("/tenants/{tid}/message-templates/preview")
def preview_message_template(
    tid: int,
    body: PreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Render subject/body templates with sample context without persisting (Req 7.5, 8.1).

    Returns {subject, body}.
    """
    _assert_tenant(tid, current_user)
    from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine

    engine = TemplateRenderEngine()
    merged_context = {**body.context, **body.sample_context}
    result = engine.preview(
        subject_template=body.subject_template,
        body_template=body.body_template,
        sample_context=merged_context,
    )
    return {"subject": result.subject, "body": result.body}


@router.post("/tenants/{tid}/message-templates/{mid}/preview")
def preview_message_template_by_id(
    tid: int,
    mid: int,
    body: PreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview endpoint scoped to a specific template (Req 7.5, 8.1)."""
    _assert_tenant(tid, current_user)
    _get_message_template_or_404(db, tid, mid)
    from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine

    engine = TemplateRenderEngine()
    merged_context = {**body.context, **body.sample_context}
    result = engine.preview(
        subject_template=body.subject_template,
        body_template=body.body_template,
        sample_context=merged_context,
    )
    return {"subject": result.subject, "body": result.body}


# ---------------------------------------------------------------------------
# Message Template helpers
# ---------------------------------------------------------------------------

def _get_message_template_or_404(db: Session, tid: int, mid: int):
    """Fetch MessageTemplate filtered by both id and tenant_id; raise 404 otherwise."""
    from gmail_lead_sync.preapproval.models_preapproval import MessageTemplate
    template = (
        db.query(MessageTemplate)
        .filter(MessageTemplate.id == mid, MessageTemplate.tenant_id == tid)
        .first()
    )
    if not template:
        raise NotFoundException(
            message=f"MessageTemplate {mid} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    return template


def _message_template_to_dict(t) -> dict:
    return {
        "id": t.id,
        "tenant_id": t.tenant_id,
        "intent_type": t.intent_type,
        "key": t.key,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _message_template_version_to_dict(v) -> dict:
    return {
        "id": v.id,
        "template_id": v.template_id,
        "version_number": v.version_number,
        "subject_template": v.subject_template,
        "body_template": v.body_template,
        "variants_json": v.variants_json,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "published_at": v.published_at.isoformat() if v.published_at else None,
    }


# ---------------------------------------------------------------------------
# Lead State Monitoring  (Req 14.1, 14.2, 14.3)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/leads/states")
def list_lead_states(
    tid: int,
    state: str | None = None,
    bucket: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Paginated leads table with current_state, filterable by state and bucket (Req 14.1, 14.2).

    Tenant isolation: leads are linked to a tenant via agent_id → credentials.company_id.
    Bucket filter joins through form_submissions → submission_scores.
    """
    from sqlalchemy import func
    from gmail_lead_sync.models import Credentials
    from gmail_lead_sync.preapproval.models_preapproval import (
        FormSubmission,
        SubmissionScore,
    )

    _assert_tenant(tid, current_user)

    # Resolve agent_ids that belong to this tenant
    agent_ids = [
        c.agent_id
        for c in db.query(Credentials).filter(Credentials.company_id == tid).all()
    ]

    query = db.query(Lead).filter(Lead.agent_id.in_(agent_ids))

    if state is not None:
        query = query.filter(Lead.current_state == state)

    if bucket is not None:
        # Join through the most recent submission score for this lead
        query = (
            query
            .join(FormSubmission, FormSubmission.lead_id == Lead.id)
            .join(SubmissionScore, SubmissionScore.submission_id == FormSubmission.id)
            .filter(SubmissionScore.bucket == bucket)
        )

    total = query.count()
    leads = (
        query
        .order_by(Lead.current_state_updated_at.desc().nullslast(), Lead.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "lead_id": lead.id,
                "name": lead.name,
                "source_email": lead.source_email,
                "current_state": lead.current_state,
                "current_state_updated_at": (
                    lead.current_state_updated_at.isoformat()
                    if lead.current_state_updated_at
                    else None
                ),
            }
            for lead in leads
        ],
    }


@router.get("/tenants/{tid}/leads/funnel")
def get_leads_funnel(
    tid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Count of leads at each state for this tenant (Req 14.3).

    Returns: {"NEW_EMAIL_RECEIVED": 10, "FORM_INVITE_CREATED": 8, ...}
    """
    from sqlalchemy import func
    from gmail_lead_sync.models import Credentials

    _assert_tenant(tid, current_user)

    agent_ids = [
        c.agent_id
        for c in db.query(Credentials).filter(Credentials.company_id == tid).all()
    ]

    rows = (
        db.query(Lead.current_state, func.count(Lead.id).label("count"))
        .filter(Lead.agent_id.in_(agent_ids), Lead.current_state.isnot(None))
        .group_by(Lead.current_state)
        .all()
    )

    return {row.current_state: row.count for row in rows}


# ---------------------------------------------------------------------------
# Audit Log  (Req 16.1, 16.2, 16.3)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/audit")
def get_audit_log(
    tid: int,
    lead_id: int | None = None,
    event_type: str | None = None,  # "state_transition" | "interaction"
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Filterable audit log combining LeadStateTransition and LeadInteraction records (Req 16.1, 16.2, 16.3).

    Filters: lead_id, event_type ("state_transition" | "interaction"), date_from/date_to (ISO date strings).
    Returns paginated list sorted by occurred_at descending.
    """
    from datetime import date as _date
    from gmail_lead_sync.preapproval.models_preapproval import (
        LeadInteraction,
        LeadStateTransition,
    )

    _assert_tenant(tid, current_user)

    # Parse date range
    dt_from: datetime | None = None
    dt_to: datetime | None = None
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
        except ValueError:
            raise ValidationException(
                message=f"Invalid date_from format: '{date_from}'. Use ISO 8601.",
                code="VALIDATION_ERROR",
            )
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
        except ValueError:
            raise ValidationException(
                message=f"Invalid date_to format: '{date_to}'. Use ISO 8601.",
                code="VALIDATION_ERROR",
            )

    entries: list[dict] = []

    include_transitions = event_type in (None, "state_transition")
    include_interactions = event_type in (None, "interaction")

    if include_transitions:
        q = db.query(LeadStateTransition).filter(LeadStateTransition.tenant_id == tid)
        if lead_id is not None:
            q = q.filter(LeadStateTransition.lead_id == lead_id)
        if dt_from is not None:
            q = q.filter(LeadStateTransition.occurred_at >= dt_from)
        if dt_to is not None:
            q = q.filter(LeadStateTransition.occurred_at <= dt_to)
        for row in q.all():
            entries.append({
                "event_type": "state_transition",
                "id": row.id,
                "lead_id": row.lead_id,
                "tenant_id": row.tenant_id,
                "from_state": row.from_state,
                "to_state": row.to_state,
                "actor_type": row.actor_type,
                "actor_id": row.actor_id,
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                "metadata_json": row.metadata_json,
            })

    if include_interactions:
        q = db.query(LeadInteraction).filter(LeadInteraction.tenant_id == tid)
        if lead_id is not None:
            q = q.filter(LeadInteraction.lead_id == lead_id)
        if dt_from is not None:
            q = q.filter(LeadInteraction.occurred_at >= dt_from)
        if dt_to is not None:
            q = q.filter(LeadInteraction.occurred_at <= dt_to)
        for row in q.all():
            entries.append({
                "event_type": "interaction",
                "id": row.id,
                "lead_id": row.lead_id,
                "tenant_id": row.tenant_id,
                "channel": row.channel,
                "direction": row.direction,
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
                "metadata_json": row.metadata_json,
                "content_text": row.content_text,
            })

    # Sort merged list by occurred_at descending
    entries.sort(key=lambda e: e["occurred_at"] or "", reverse=True)

    total = len(entries)
    start = (page - 1) * page_size
    page_items = entries[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": page_items,
    }

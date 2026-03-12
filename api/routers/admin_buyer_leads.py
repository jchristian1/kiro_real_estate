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
from gmail_lead_sync.preapproval.scoring_engine import ScoringEngine
from api.repositories.buyer_leads_repository import (
    FormTemplateRepository,
    FormVersionRepository,
    ScoringConfigRepository,
    ScoringVersionRepository,
    MessageTemplateRepository,
    BuyerLeadsQueryRepository,
)
from api.dependencies.auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_role("platform_admin"))])


# ---------------------------------------------------------------------------
# Shared dependencies
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Tenant isolation helper
# ---------------------------------------------------------------------------

def _assert_tenant(tid: int, current_user: User) -> None:
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
    type: str
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
    _assert_tenant(tid, current_user)
    repo = FormTemplateRepository(db)
    return [_template_to_dict(t) for t in repo.list_for_tenant(tid)]


@router.post("/tenants/{tid}/forms", status_code=status.HTTP_201_CREATED)
def create_form_template(
    tid: int,
    body: CreateFormTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = FormTemplateRepository(db)
    template = repo.create(tid, body.intent_type, body.name)
    return _template_to_dict(template)


@router.get("/tenants/{tid}/forms/{fid}")
def get_form_template(
    tid: int,
    fid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = FormTemplateRepository(db)
    template = repo.get_by_id(fid, tid)
    if not template:
        raise NotFoundException(message=f"FormTemplate {fid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    return _template_to_dict(template)


@router.put("/tenants/{tid}/forms/{fid}")
def update_form_template(
    tid: int,
    fid: int,
    body: UpdateFormTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = FormTemplateRepository(db)
    template = repo.update(fid, tid, name=body.name, status=body.status)
    if not template:
        raise NotFoundException(message=f"FormTemplate {fid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    return _template_to_dict(template)


@router.delete("/tenants/{tid}/forms/{fid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_form_template(
    tid: int,
    fid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = FormTemplateRepository(db)
    if not repo.delete(fid, tid):
        raise NotFoundException(message=f"FormTemplate {fid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)


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
    _assert_tenant(tid, current_user)
    ft_repo = FormTemplateRepository(db)
    if not ft_repo.get_by_id(fid, tid):
        raise NotFoundException(message=f"FormTemplate {fid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    fv_repo = FormVersionRepository(db)
    return [_version_to_dict(v) for v in fv_repo.list_for_template(fid)]


@router.post("/tenants/{tid}/forms/{fid}/versions", status_code=status.HTTP_201_CREATED)
def publish_form_version(
    tid: int,
    fid: int,
    body: PublishFormVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    ft_repo = FormTemplateRepository(db)
    if not ft_repo.get_by_id(fid, tid):
        raise NotFoundException(message=f"FormTemplate {fid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    # Req 2.7 — validate unique question_keys
    keys = [q.question_key for q in body.questions]
    if len(keys) != len(set(keys)):
        raise ValidationException(message="Duplicate question_key values are not allowed", code="VALIDATION_ERROR")

    # Req 2.6 — validate question types
    valid_types = {"single_choice", "multi_select", "free_text", "phone", "email"}
    for q in body.questions:
        if q.type not in valid_types:
            raise ValidationException(
                message=f"Invalid question type '{q.type}'. Must be one of: {', '.join(sorted(valid_types))}",
                code="VALIDATION_ERROR",
            )

    # Req 2.8 — validate logic rule JSON
    for rule in body.logic_rules:
        try:
            json.loads(rule.rule_json)
        except json.JSONDecodeError as exc:
            raise ValidationException(message=f"Invalid logic rule JSON: {exc}", code="VALIDATION_ERROR")

    fv_repo = FormVersionRepository(db)
    last_version = fv_repo.get_latest(fid)
    next_version_number = (last_version.version_number + 1) if last_version else 1

    schema_snapshot: dict[str, Any] = {
        "questions": [q.model_dump() for q in body.questions],
        "logic_rules": [r.model_dump() for r in body.logic_rules],
    }

    fv_repo.deactivate_all(fid)
    version = fv_repo.create(
        template_id=fid,
        version_number=next_version_number,
        schema_json=json.dumps(schema_snapshot),
        questions=body.questions,
        logic_rules=body.logic_rules,
    )
    return _version_to_dict(version)


@router.post("/tenants/{tid}/forms/{fid}/versions/{vid}/rollback")
def rollback_form_version(
    tid: int,
    fid: int,
    vid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    ft_repo = FormTemplateRepository(db)
    if not ft_repo.get_by_id(fid, tid):
        raise NotFoundException(message=f"FormTemplate {fid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    fv_repo = FormVersionRepository(db)
    target = fv_repo.activate(vid, fid)
    if not target:
        raise NotFoundException(message=f"FormVersion {vid} not found for form {fid}", code=ErrorCode.NOT_FOUND_RESOURCE)
    return _version_to_dict(target)


# ---------------------------------------------------------------------------
# Scoring — Pydantic request models  (Req 6.1 – 6.5)
# ---------------------------------------------------------------------------

class CreateScoringConfigRequest(BaseModel):
    name: str
    intent_type: str = "BUY"


class ScoringRuleCreate(BaseModel):
    source: str = "answer"
    key: str
    answer_value: Any
    points: int
    reason: str = ""


class PublishScoringVersionRequest(BaseModel):
    rules: list[ScoringRuleCreate]
    thresholds: dict[str, int]


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
    _assert_tenant(tid, current_user)
    repo = ScoringConfigRepository(db)
    return [_scoring_config_to_dict(c) for c in repo.list_for_tenant(tid)]


@router.post("/tenants/{tid}/scoring", status_code=status.HTTP_201_CREATED)
def create_scoring_config(
    tid: int,
    body: CreateScoringConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = ScoringConfigRepository(db)
    config = repo.create(tid, body.intent_type, body.name)
    return _scoring_config_to_dict(config)


@router.put("/tenants/{tid}/scoring/{sid}")
def update_scoring_config(
    tid: int,
    sid: int,
    body: CreateScoringConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = ScoringConfigRepository(db)
    config = repo.update_name(sid, tid, body.name)
    if not config:
        raise NotFoundException(message=f"ScoringConfig {sid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    return _scoring_config_to_dict(config)


@router.delete("/tenants/{tid}/scoring/{sid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scoring_config(
    tid: int,
    sid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = ScoringConfigRepository(db)
    if not repo.delete(sid, tid):
        raise NotFoundException(message=f"ScoringConfig {sid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)


@router.post("/tenants/{tid}/scoring/{sid}/versions/{vid}/rollback")
def rollback_scoring_version(
    tid: int,
    sid: int,
    vid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    sc_repo = ScoringConfigRepository(db)
    if not sc_repo.get_by_id(sid, tid):
        raise NotFoundException(message=f"ScoringConfig {sid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    sv_repo = ScoringVersionRepository(db)
    target = sv_repo.activate(vid, sid)
    if not target:
        raise NotFoundException(message=f"ScoringVersion {vid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
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
    _assert_tenant(tid, current_user)
    sc_repo = ScoringConfigRepository(db)
    if not sc_repo.get_by_id(sid, tid):
        raise NotFoundException(message=f"ScoringConfig {sid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    sv_repo = ScoringVersionRepository(db)
    return [_scoring_version_to_dict(v) for v in sv_repo.list_for_config(sid)]


@router.post("/tenants/{tid}/scoring/{sid}/versions", status_code=status.HTTP_201_CREATED)
def publish_scoring_version(
    tid: int,
    sid: int,
    body: PublishScoringVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    sc_repo = ScoringConfigRepository(db)
    if not sc_repo.get_by_id(sid, tid):
        raise NotFoundException(message=f"ScoringConfig {sid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    thresholds = body.thresholds
    if "HOT" not in thresholds or "WARM" not in thresholds:
        raise ValidationException(message="thresholds must contain both 'HOT' and 'WARM' keys", code="VALIDATION_ERROR")
    if not (thresholds["HOT"] > thresholds["WARM"] >= 0):
        raise ValidationException(message="thresholds must satisfy: HOT > WARM >= 0", code="VALIDATION_ERROR")

    sv_repo = ScoringVersionRepository(db)
    last_version = sv_repo.get_latest(sid)
    next_version_number = (last_version.version_number + 1) if last_version else 1

    sv_repo.deactivate_all(sid)
    version = sv_repo.create(
        config_id=sid,
        version_number=next_version_number,
        rules_json=json.dumps([r.model_dump() for r in body.rules]),
        thresholds_json=json.dumps(thresholds),
    )
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
    _assert_tenant(tid, current_user)
    sc_repo = ScoringConfigRepository(db)
    active_version = sc_repo.get_active_version_for_intent(tid, body.intent_type)
    if not active_version:
        raise NotFoundException(
            message=f"No active scoring version found for tenant {tid} and intent_type {body.intent_type}",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )

    engine = ScoringEngine()
    result = engine.compute(answers=body.answers, scoring_version=active_version, metadata=body.metadata)

    return {
        "total": result.total,
        "bucket": result.bucket.value,
        "breakdown": [
            {"question_key": item.question_key, "answer": item.answer, "points": item.points, "reason": item.reason}
            for item in result.breakdown
        ],
        "explanation": result.explanation,
    }


# ---------------------------------------------------------------------------
# Message Templates — Pydantic request models  (Req 7.1, 7.5, 7.6)
# ---------------------------------------------------------------------------

class CreateMessageTemplateRequest(BaseModel):
    key: str
    intent_type: str = "BUY"


class PublishMessageTemplateVersionRequest(BaseModel):
    subject_template: str
    body_template: str
    variants_json: str | None = None


class PreviewRequest(BaseModel):
    subject_template: str
    body_template: str
    sample_context: dict[str, str] = {}
    context: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Message Template CRUD  (Req 7.1)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/message-templates")
def list_message_templates(
    tid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = MessageTemplateRepository(db)
    return [_message_template_to_dict(t) for t in repo.list_for_tenant(tid)]


@router.get("/tenants/{tid}/message-templates/{mid}")
def get_message_template(
    tid: int,
    mid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = MessageTemplateRepository(db)
    template = repo.get_by_id(mid, tid)
    if not template:
        raise NotFoundException(message=f"MessageTemplate {mid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    return _message_template_to_dict(template)


@router.get("/tenants/{tid}/message-templates/{mid}/versions")
def list_message_template_versions(
    tid: int,
    mid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = MessageTemplateRepository(db)
    if not repo.get_by_id(mid, tid):
        raise NotFoundException(message=f"MessageTemplate {mid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    return [_message_template_version_to_dict(v) for v in repo.list_versions(mid)]


@router.post("/tenants/{tid}/message-templates", status_code=status.HTTP_201_CREATED)
def create_message_template(
    tid: int,
    body: CreateMessageTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = MessageTemplateRepository(db)
    template = repo.create(tid, body.intent_type, body.key)
    return _message_template_to_dict(template)


@router.put("/tenants/{tid}/message-templates/{mid}")
def update_message_template(
    tid: int,
    mid: int,
    body: CreateMessageTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = MessageTemplateRepository(db)
    template = repo.update(mid, tid, body.key, body.intent_type)
    if not template:
        raise NotFoundException(message=f"MessageTemplate {mid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    return _message_template_to_dict(template)


@router.delete("/tenants/{tid}/message-templates/{mid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message_template(
    tid: int,
    mid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = MessageTemplateRepository(db)
    if not repo.delete(mid, tid):
        raise NotFoundException(message=f"MessageTemplate {mid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)


@router.post("/tenants/{tid}/message-templates/{mid}/versions/{vid}/rollback")
def rollback_message_template_version(
    tid: int,
    mid: int,
    vid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = MessageTemplateRepository(db)
    if not repo.get_by_id(mid, tid):
        raise NotFoundException(message=f"MessageTemplate {mid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    target = repo.activate_version(vid, mid)
    if not target:
        raise NotFoundException(message=f"MessageTemplateVersion {vid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    return _message_template_version_to_dict(target)


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
    import re as _re
    _assert_tenant(tid, current_user)
    from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine

    repo = MessageTemplateRepository(db)
    if not repo.get_by_id(mid, tid):
        raise NotFoundException(message=f"MessageTemplate {mid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    if "\n" in body.subject_template or "\r" in body.subject_template:
        raise ValidationException(message="subject_template must not contain newline characters", code="VALIDATION_ERROR")

    texts_to_validate = [body.subject_template, body.body_template]
    variants: dict | None = None
    if body.variants_json is not None:
        try:
            variants = json.loads(body.variants_json)
        except json.JSONDecodeError as exc:
            raise ValidationException(message=f"Invalid variants_json: {exc}", code="VALIDATION_ERROR")
        for variant_key, variant_data in variants.items():
            variant_subject = variant_data.get("subject", "")
            if variant_subject and ("\n" in variant_subject or "\r" in variant_subject):
                raise ValidationException(
                    message=f"Variant '{variant_key}' subject must not contain newline characters",
                    code="VALIDATION_ERROR",
                )
            texts_to_validate.extend([variant_subject, variant_data.get("body", "")])

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

    last_version = repo.get_latest_version(mid)
    next_version_number = (last_version.version_number + 1) if last_version else 1

    repo.deactivate_all_versions(mid)
    version = repo.create_version(
        template_id=mid,
        version_number=next_version_number,
        subject_template=body.subject_template,
        body_template=body.body_template,
        variants_json=body.variants_json,
    )
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
    _assert_tenant(tid, current_user)
    from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine
    engine = TemplateRenderEngine()
    merged_context = {**body.context, **body.sample_context}
    result = engine.preview(subject_template=body.subject_template, body_template=body.body_template, sample_context=merged_context)
    return {"subject": result.subject, "body": result.body}


@router.post("/tenants/{tid}/message-templates/{mid}/preview")
def preview_message_template_by_id(
    tid: int,
    mid: int,
    body: PreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)
    repo = MessageTemplateRepository(db)
    if not repo.get_by_id(mid, tid):
        raise NotFoundException(message=f"MessageTemplate {mid} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine
    engine = TemplateRenderEngine()
    merged_context = {**body.context, **body.sample_context}
    result = engine.preview(subject_template=body.subject_template, body_template=body.body_template, sample_context=merged_context)
    return {"subject": result.subject, "body": result.body}


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
    _assert_tenant(tid, current_user)
    query_repo = BuyerLeadsQueryRepository(db)
    agent_ids = query_repo.get_agent_ids_for_tenant(tid)
    leads, total = query_repo.list_leads_by_state(agent_ids, state=state, bucket=bucket, page=page, page_size=page_size)
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
                    lead.current_state_updated_at.isoformat() if lead.current_state_updated_at else None
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
    _assert_tenant(tid, current_user)
    query_repo = BuyerLeadsQueryRepository(db)
    agent_ids = query_repo.get_agent_ids_for_tenant(tid)
    return query_repo.get_leads_funnel(agent_ids)


# ---------------------------------------------------------------------------
# Lead History
# ---------------------------------------------------------------------------

@router.get("/leads/{lead_id}/history")
def get_lead_history(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query_repo = BuyerLeadsQueryRepository(db)
    return query_repo.get_lead_history(lead_id)


# ---------------------------------------------------------------------------
# Audit Log  (Req 16.1, 16.2, 16.3)
# ---------------------------------------------------------------------------

@router.get("/tenants/{tid}/audit")
def get_audit_log(
    tid: int,
    lead_id: int | None = None,
    event_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_tenant(tid, current_user)

    dt_from: datetime | None = None
    dt_to: datetime | None = None
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
        except ValueError:
            raise ValidationException(message=f"Invalid date_from format: '{date_from}'. Use ISO 8601.", code="VALIDATION_ERROR")
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
        except ValueError:
            raise ValidationException(message=f"Invalid date_to format: '{date_to}'. Use ISO 8601.", code="VALIDATION_ERROR")

    query_repo = BuyerLeadsQueryRepository(db)
    entries = query_repo.get_audit_entries(tid, lead_id=lead_id, event_type=event_type, dt_from=dt_from, dt_to=dt_to)

    total = len(entries)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "items": entries[start: start + page_size]}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _template_to_dict(t) -> dict:
    return {
        "id": t.id,
        "tenant_id": t.tenant_id,
        "intent_type": t.intent_type,
        "name": t.name,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _version_to_dict(v) -> dict:
    return {
        "id": v.id,
        "template_id": v.template_id,
        "version_number": v.version_number,
        "schema_json": v.schema_json,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "published_at": v.published_at.isoformat() if v.published_at else None,
    }


def _scoring_config_to_dict(c) -> dict:
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "intent_type": c.intent_type,
        "name": c.name,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _scoring_version_to_dict(v) -> dict:
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

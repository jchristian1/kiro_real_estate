"""
Event handlers for the Buyer Lead Qualification pipeline.

These handlers are called exclusively by the pipeline engine (_execute_step).
They are pure domain operations — no pipeline event firing, no side-effect
routing. The pipeline is the single source of truth for all email sending
and stage transitions.

on_buyer_lead_email_received — creates a FormInvitation and sends the form email.
on_buyer_form_submitted      — validates, scores, and fires pipeline events.
"""

from __future__ import annotations

import json as _json
import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

from gmail_lead_sync.models import Credentials, Lead
from gmail_lead_sync.preapproval.invitation_service import FormInvitationService
from gmail_lead_sync.preapproval.models_preapproval import (
    Channel,
    FormSubmission,
    FormTemplate,
    FormVersion,
    IntentType,
    LeadInteraction,
    MessageTemplate,
    MessageTemplateKey,
    MessageTemplateVersion,
    ScoringConfig,
    ScoringVersion,
    SubmissionAnswer,
    SubmissionScore,
)
from gmail_lead_sync.preapproval.scoring_engine import ScoringEngine
from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_invitation_service = FormInvitationService()
_template_engine = TemplateRenderEngine()
_scoring_engine = ScoringEngine()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_form_url(raw_token: str) -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/public/buyer-qualification/{raw_token}"


def _resolve_active_form_version(
    db: Session,
    tenant_id: int,
    intent_type: IntentType = IntentType.BUY,
) -> FormVersion | None:
    return (
        db.query(FormVersion)
        .join(FormTemplate, FormVersion.template_id == FormTemplate.id)
        .filter(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.intent_type == intent_type.value,
            FormVersion.is_active.is_(True),
        )
        .first()
    )


def _resolve_active_message_template(
    db: Session,
    tenant_id: int,
    intent_type: IntentType,
    key: MessageTemplateKey,
) -> MessageTemplateVersion | None:
    return (
        db.query(MessageTemplateVersion)
        .join(MessageTemplate, MessageTemplateVersion.template_id == MessageTemplate.id)
        .filter(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.intent_type == intent_type.value,
            MessageTemplate.key == key.value,
            MessageTemplateVersion.is_active.is_(True),
        )
        .first()
    )


def _resolve_agent_template(
    db: Session,
    tenant_id: int,
    template_type: str,
) -> tuple[str, str] | None:
    try:
        from gmail_lead_sync.agent_models import AgentUser, AgentTemplate
        agent = db.query(AgentUser).filter(AgentUser.company_id == tenant_id).first()
        if agent is None:
            return None
        row = (
            db.query(AgentTemplate)
            .filter(
                AgentTemplate.agent_user_id == agent.id,
                AgentTemplate.template_type == template_type,
                AgentTemplate.is_active.is_(True),
            )
            .first()
        )
        if row is None:
            return None
        return row.subject, row.body
    except Exception as exc:
        logger.warning("Could not resolve AgentTemplate tenant=%d type=%s: %s", tenant_id, template_type, exc)
        return None


def _render_agent_template(subject_tpl: str, body_tpl: str, context: dict) -> tuple[str, str]:
    mapping = {
        "{lead_name}": context.get("lead_name", ""),
        "{agent_name}": context.get("agent_name", ""),
        "{agent_phone}": context.get("agent_phone", ""),
        "{agent_email}": context.get("agent_email", ""),
        "{form_link}": context.get("form_link", ""),
    }
    subject, body = subject_tpl, body_tpl
    for placeholder, value in mapping.items():
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)
    return subject, body


def _get_tenant_email_credentials(db: Session, tenant_id: int) -> tuple[str, str] | None:
    creds = db.query(Credentials).filter(Credentials.company_id == tenant_id).first()
    if creds is None:
        return None
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if encryption_key:
        from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
        store = EncryptedDBCredentialsStore(db, encryption_key)
        return store.get_credentials(creds.agent_id)
    return creds.email_encrypted, creds.app_password_encrypted


def _send_email(to_address: str, subject: str, body: str, from_address: str, app_password: str) -> bool:
    from gmail_lead_sync.responder import AutoResponder
    responder = object.__new__(AutoResponder)
    return responder.send_email(
        to_address=to_address,
        subject=subject,
        body=body,
        from_address=from_address,
        app_password=app_password,
    )


def _resolve_active_scoring_version(
    db: Session,
    tenant_id: int,
    intent_type: IntentType = IntentType.BUY,
) -> ScoringVersion | None:
    return (
        db.query(ScoringVersion)
        .join(ScoringConfig, ScoringVersion.scoring_config_id == ScoringConfig.id)
        .filter(
            ScoringConfig.tenant_id == tenant_id,
            ScoringConfig.intent_type == intent_type.value,
            ScoringVersion.is_active.is_(True),
        )
        .first()
    )


def _validate_answers(answers_payload: dict, form_version: FormVersion) -> None:
    schema = _json.loads(form_version.schema_json)
    questions = schema if isinstance(schema, list) else schema.get("questions", [])
    errors: dict[str, str] = {}
    for q in questions:
        key = q.get("question_key") or q.get("key")
        if q.get("required", False) and key not in answers_payload:
            errors[key] = "This field is required."
    if errors:
        raise ValueError(errors)


# ---------------------------------------------------------------------------
# Handler: send qualification form
# ---------------------------------------------------------------------------

def on_buyer_lead_email_received(
    db: Session,
    tenant_id: int,
    lead_id: int,
    parsed_metadata: dict,
) -> None:
    """Create a FormInvitation and send the qualification form email.

    Called exclusively by the pipeline engine (send_qualification_form action).
    Does NOT fire any pipeline events — the pipeline is already running.

    Steps:
    1. Resolve active FormVersion; return if none.
    2. Create FormInvitation (raw token for URL).
    3. Render email via AdminTemplate or AgentTemplate or MessageTemplate.
    4. Send email via tenant SMTP credentials.
    5. Mark invitation.sent_at; update lead.agent_current_state.
    6. Record outbound LeadInteraction.
    """
    # 1. Resolve active FormVersion
    form_version = _resolve_active_form_version(db, tenant_id, IntentType.BUY)
    if form_version is None:
        logger.warning("No active BUY form for tenant %d, skipping invite (lead_id=%d)", tenant_id, lead_id)
        return

    # 2. Create FormInvitation
    raw_token, invitation = _invitation_service.create_invitation(
        db, tenant_id=tenant_id, lead_id=lead_id, form_version_id=form_version.id,
    )

    # 3. Render email
    lead: Lead = db.get(Lead, lead_id)
    if lead is None:
        logger.error("Lead %d not found, cannot send form invite", lead_id)
        return

    first_name = lead.name.split()[0] if lead.name else ""
    from sqlalchemy import text as _text
    tenant_row = db.execute(_text("SELECT name FROM companies WHERE id = :tid"), {"tid": tenant_id}).fetchone()
    tenant_name = tenant_row[0] if tenant_row else ""

    agent_tpl = _resolve_agent_template(db, tenant_id, "INITIAL_INVITE")
    if agent_tpl is not None:
        from gmail_lead_sync.agent_models import AgentUser as _AgentUser
        _agent = db.query(_AgentUser).filter(_AgentUser.company_id == tenant_id).first()
        rendered_subject, rendered_body = _render_agent_template(
            agent_tpl[0], agent_tpl[1],
            {
                "lead_name": lead.name or first_name,
                "agent_name": (_agent.full_name if _agent else tenant_name) or "",
                "agent_phone": (_agent.phone if _agent else "") or "",
                "agent_email": (_agent.email if _agent else "") or "",
                "form_link": _build_form_url(raw_token),
            },
        )
    else:
        msg_version = _resolve_active_message_template(
            db, tenant_id=tenant_id, intent_type=IntentType.BUY,
            key=MessageTemplateKey.INITIAL_INVITE_EMAIL,
        )
        if msg_version is None:
            logger.error(
                "No active INITIAL_INVITE_EMAIL template for tenant %d (lead_id=%d); skipping.",
                tenant_id, lead_id,
            )
            db.add(LeadInteraction(
                tenant_id=tenant_id, lead_id=lead_id,
                intent_type=IntentType.BUY.value, channel=Channel.EMAIL.value,
                direction="outbound", occurred_at=datetime.utcnow(),
                content_text="[ERROR: no active INITIAL_INVITE_EMAIL template]",
            ))
            db.commit()
            return
        rendered_obj = _template_engine.render(
            msg_version,
            {
                "lead.first_name": first_name,
                "lead.email": lead.source_email,
                "form.link": _build_form_url(raw_token),
                "tenant.name": tenant_name,
                **parsed_metadata,
            },
        )
        rendered_subject, rendered_body = rendered_obj.subject, rendered_obj.body

    # 4. Send email
    creds = _get_tenant_email_credentials(db, tenant_id)
    if creds is None:
        logger.error("No SMTP credentials for tenant %d; cannot send form invite (lead_id=%d).", tenant_id, lead_id)
    else:
        _send_email(lead.source_email, rendered_subject, rendered_body, creds[0], creds[1])

    # 5. Mark invitation sent + update lead state
    invitation.sent_at = datetime.utcnow()
    lead.agent_current_state = "INVITE_SENT"
    db.commit()

    # 6. Record outbound interaction
    db.add(LeadInteraction(
        tenant_id=tenant_id, lead_id=lead_id,
        intent_type=IntentType.BUY.value, channel=Channel.EMAIL.value,
        direction="outbound", occurred_at=datetime.utcnow(),
        content_text=rendered_subject,
    ))
    db.commit()

    logger.info("Form invite sent: tenant=%d lead=%d invitation=%d", tenant_id, lead_id, invitation.id)


# ---------------------------------------------------------------------------
# Handler: form submission
# ---------------------------------------------------------------------------

def on_buyer_form_submitted(
    db: Session,
    raw_token: str,
    answers_payload: dict,
    request_metadata: dict,
) -> dict:
    """Validate token, persist submission, score, and fire pipeline events.

    Does NOT send any emails — the pipeline handles all post-submission
    emails via send_bucket_followup_email / send_email_template rules.

    Returns:
        {"submission_id": int, "score": {"total", "bucket", "explanation"} | None}

    Raises:
        TokenNotFoundError, TokenUsedError, TokenExpiredError, ValueError
    """
    # 1. Validate token
    invitation = _invitation_service.validate_token(db, raw_token)

    # 2. Validate answers
    form_version: FormVersion = db.get(FormVersion, invitation.form_version_id)
    _validate_answers(answers_payload, form_version)

    # 3. Persist FormSubmission + SubmissionAnswer rows
    now = datetime.utcnow()
    submission = FormSubmission(
        tenant_id=invitation.tenant_id,
        lead_id=invitation.lead_id,
        intent_type=IntentType.BUY.value,
        form_version_id=invitation.form_version_id,
        invitation_id=invitation.id,
        submitted_at=now,
        user_agent=request_metadata.get("user_agent"),
        device_type=request_metadata.get("device_type"),
        time_to_submit_seconds=request_metadata.get("time_to_submit_seconds"),
        lead_source=request_metadata.get("lead_source"),
        property_address=request_metadata.get("property_address"),
        listing_url=request_metadata.get("listing_url"),
        repeat_inquiry_count=request_metadata.get("repeat_inquiry_count", 0),
        raw_payload_json=_json.dumps(answers_payload),
    )
    db.add(submission)
    db.flush()

    for question_key, answer_value in answers_payload.items():
        db.add(SubmissionAnswer(
            submission_id=submission.id,
            question_key=question_key,
            answer_value_json=_json.dumps(answer_value),
        ))

    # 4. Mark token used
    invitation.used_at = now

    # 5. Update lead state
    lead: Lead = db.get(Lead, invitation.lead_id)
    if lead is not None:
        lead.agent_current_state = "FORM_SUBMITTED"
    db.flush()

    # 6. Resolve ScoringVersion
    scoring_version = _resolve_active_scoring_version(db, invitation.tenant_id, IntentType.BUY)
    if scoring_version is None:
        logger.warning(
            "No active BUY scoring version for tenant %d; lead %d left unscored (submission=%d).",
            invitation.tenant_id, invitation.lead_id, submission.id,
        )
        db.commit()
        _fire_post_submission_events(db, invitation.lead_id, invitation.tenant_id, bucket=None)
        return {"submission_id": submission.id, "score": None}

    # 7. Compute score
    score_result = _scoring_engine.compute(
        answers_payload,
        scoring_version,
        {
            "property_address": request_metadata.get("property_address"),
            "listing_url": request_metadata.get("listing_url"),
            "lead_source": request_metadata.get("lead_source"),
            "repeat_inquiry_count": request_metadata.get("repeat_inquiry_count", 0),
        },
    )

    # 8. Persist SubmissionScore + update Lead
    submission.scoring_version_id = scoring_version.id
    breakdown_serializable = [
        {"question_key": i.question_key, "answer": i.answer, "points": i.points, "reason": i.reason}
        for i in score_result.breakdown
    ]
    db.add(SubmissionScore(
        submission_id=submission.id,
        total_score=score_result.total,
        bucket=score_result.bucket.value,
        breakdown_json=_json.dumps(breakdown_serializable),
        explanation_text=score_result.explanation,
    ))

    if lead is not None:
        lead.score = score_result.total
        lead.score_bucket = score_result.bucket.value
        lead.score_breakdown = _json.dumps({"factors": breakdown_serializable})
        lead.agent_current_state = "SCORED"

    db.commit()

    logger.info(
        "Form submitted and scored: tenant=%d lead=%d submission=%d bucket=%s score=%d",
        invitation.tenant_id, invitation.lead_id, submission.id,
        score_result.bucket.value, score_result.total,
    )

    # 9. Fire pipeline events — pipeline handles all post-submission emails
    _fire_post_submission_events(db, invitation.lead_id, invitation.tenant_id, bucket=score_result.bucket.value)

    return {
        "submission_id": submission.id,
        "score": {
            "total": score_result.total,
            "bucket": score_result.bucket.value,
            "explanation": score_result.explanation,
        },
    }


def _fire_post_submission_events(db: Session, lead_id: int, tenant_id: int, bucket: str | None) -> None:
    """Fire qualification_form_submitted + bucket pipeline events."""
    try:
        from api.models.pipeline_models import BuiltInEventType
        from api.services.lead_stage_transition_engine import fire_event

        fire_event(db, lead_id, BuiltInEventType.qualification_form_submitted, {"tenant_id": tenant_id})

        if bucket is not None:
            bucket_event_map = {
                "HOT": BuiltInEventType.qualification_bucket_hot,
                "WARM": BuiltInEventType.qualification_bucket_warm,
                "NURTURE": BuiltInEventType.qualification_bucket_nurture,
            }
            bucket_event = bucket_event_map.get(bucket)
            if bucket_event:
                fire_event(db, lead_id, bucket_event, {"tenant_id": tenant_id})
    except Exception as exc:
        logger.warning("Pipeline fire_event failed after form submitted for lead %d: %s", lead_id, exc, exc_info=True)

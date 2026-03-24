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

from gmail_lead_sync.models import Lead
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

def build_form_url(raw_token: str) -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/public/buyer-qualification/{raw_token}"

# Keep underscore alias for internal callers that haven't been updated yet
_build_form_url = build_form_url


def resolve_active_form_version(
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

# Keep underscore alias for internal callers that haven't been updated yet
_resolve_active_form_version = resolve_active_form_version


def get_or_create_form_link(db: Session, tenant_id: int, lead_id: int) -> str:
    """Return a form invitation URL for the given lead/tenant.

    Public interface for callers that need a {form_link} value but are not
    themselves qualification-module code (e.g. the generic email handler).

    Creates a FormInvitation token if an active BUY form version exists.
    Falls back to the generic public qualification URL if no active form is
    configured for the tenant.

    Ownership: qualification module owns all invitation/token creation.
    """
    base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
    fallback = f"{base_url}/public/buyer-qualification"

    form_version = resolve_active_form_version(db, tenant_id, IntentType.BUY)
    if form_version is None:
        return fallback

    try:
        raw_token, _ = _invitation_service.create_invitation(
            db,
            tenant_id=tenant_id,
            lead_id=lead_id,
            form_version_id=form_version.id,
        )
        return build_form_url(raw_token)
    except Exception as exc:
        logger.warning(
            "get_or_create_form_link: could not create invitation "
            "for lead %s tenant %s: %s — using fallback URL",
            lead_id, tenant_id, exc,
        )
        return fallback


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


_invite_service = None


def _get_invite_service():
    global _invite_service
    if _invite_service is None:
        from api.communications.qualification_invite import QualificationInviteService
        _invite_service = QualificationInviteService()
    return _invite_service


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
# Lazy singletons — avoid circular imports at module load
# ---------------------------------------------------------------------------

_delivery = None
_renderer = None


def _get_delivery():
    global _delivery
    if _delivery is None:
        from api.communications.email_delivery import EmailDeliveryService
        _delivery = EmailDeliveryService()
    return _delivery


def _get_renderer():
    global _renderer
    if _renderer is None:
        from api.communications.template_render import TemplateRenderService
        _renderer = TemplateRenderService()
    return _renderer


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

    Delegates invite creation, rendering, and delivery to QualificationInviteService.
    Retains ownership of:
      - Lead state mutation (agent_current_state)
      - LeadInteraction recording
      - Activity emission
    """
    result = _get_invite_service().send_invite(
        db=db,
        tenant_id=tenant_id,
        lead_id=lead_id,
        parsed_metadata=parsed_metadata,
    )

    if result.skipped:
        return

    # Load lead for state mutation and interaction logging
    lead: Lead = db.get(Lead, lead_id)
    if lead is None:
        logger.error("Lead %d not found after invite send — cannot update state", lead_id)
        return

    if result.rendered_subject is None:
        # No template was configured — record error interaction and bail
        db.add(LeadInteraction(
            tenant_id=tenant_id, lead_id=lead_id,
            intent_type=IntentType.BUY.value, channel=Channel.EMAIL.value,
            direction="outbound", occurred_at=datetime.utcnow(),
            content_text="[ERROR: no active INITIAL_INVITE_EMAIL template]",
        ))
        db.commit()
        return

    # Update lead state
    lead.agent_current_state = "INVITE_SENT"
    db.commit()

    # Record outbound interaction
    db.add(LeadInteraction(
        tenant_id=tenant_id, lead_id=lead_id,
        intent_type=IntentType.BUY.value, channel=Channel.EMAIL.value,
        direction="outbound", occurred_at=datetime.utcnow(),
        content_text=result.rendered_subject,
    ))
    db.commit()

    # Record structured activity — only when email was actually sent.
    if result.sent:
        try:
            from api.services.lead_activity import record_activity
            record_activity(
                db,
                lead_id=lead_id,
                event_type="qualification_form_sent",
                company_id=tenant_id,
                actor_source="qualification",
                metadata={
                    "invitation_id": result.invitation_id,
                    "form_version_id": result.form_version_id,
                },
            )
        except Exception as exc:
            logger.warning(
                "on_buyer_lead_email_received: record_activity failed for lead %s: %s",
                lead_id, exc,
            )

    logger.info(
        "Form invite sent: tenant=%d lead=%d invitation=%d sent=%s",
        tenant_id, lead_id, result.invitation_id, result.sent,
    )


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
        try:
            from api.services.lead_activity import record_activity
            record_activity(
                db,
                lead_id=invitation.lead_id,
                event_type="qualification_form_submitted",
                company_id=invitation.tenant_id,
                actor_source="qualification",
                metadata={"submission_id": submission.id, "scored": False},
            )
        except Exception as exc:
            logger.warning(
                "on_buyer_form_submitted (unscored): record_activity failed for lead %s: %s",
                invitation.lead_id, exc,
            )
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

    # Record structured activity for form submission and bucket assignment.
    try:
        from api.services.lead_activity import record_activity
        record_activity(
            db,
            lead_id=invitation.lead_id,
            event_type="qualification_form_submitted",
            company_id=invitation.tenant_id,
            actor_source="qualification",
            metadata={"submission_id": submission.id},
        )
        record_activity(
            db,
            lead_id=invitation.lead_id,
            event_type="qualification_bucket_assigned",
            company_id=invitation.tenant_id,
            actor_source="qualification",
            metadata={
                "bucket": score_result.bucket.value,
                "score": score_result.total,
                "submission_id": submission.id,
            },
        )
    except Exception as exc:
        logger.warning(
            "on_buyer_form_submitted: record_activity failed for lead %s: %s",
            invitation.lead_id, exc,
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
    """Delegate post-submission pipeline events to the orchestrator."""
    from api.orchestration.lead_lifecycle_orchestrator import fire_post_submission_events
    fire_post_submission_events(db, lead_id, tenant_id, bucket)

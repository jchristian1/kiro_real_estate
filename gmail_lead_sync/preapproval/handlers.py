"""
Event handlers for the Buyer Lead Qualification pipeline.

on_buyer_lead_email_received — triggered when a new buyer lead email arrives.
  Resolves the active FormVersion, creates a FormInvitation, renders and sends
  the INITIAL_INVITE_EMAIL, and records the outbound LeadInteraction.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

from gmail_lead_sync.models import Credentials, Lead
from gmail_lead_sync.preapproval.invitation_service import FormInvitationService
from gmail_lead_sync.preapproval.models_preapproval import (
    Channel,
    FormTemplate,
    FormVersion,
    IntentType,
    LeadInteraction,
    LeadState,
    MessageTemplate,
    MessageTemplateKey,
    MessageTemplateVersion,
)
from gmail_lead_sync.preapproval.state_machine import LeadStateMachine
from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Email sending helper (thin wrapper around AutoResponder.send_email)
# ---------------------------------------------------------------------------

def _send_email(
    to_address: str,
    subject: str,
    body: str,
    from_address: str,
    app_password: str,
) -> bool:
    """Send an email via Gmail SMTP using the existing AutoResponder logic."""
    from gmail_lead_sync.responder import AutoResponder

    # send_email is a pure method — instantiate minimally to call it.
    responder = object.__new__(AutoResponder)
    return responder.send_email(
        to_address=to_address,
        subject=subject,
        body=body,
        from_address=from_address,
        app_password=app_password,
    )


# ---------------------------------------------------------------------------
# Module-level service singletons (stateless — safe to share)
# ---------------------------------------------------------------------------

_state_machine = LeadStateMachine()
_invitation_service = FormInvitationService()
_template_engine = TemplateRenderEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_form_url(raw_token: str) -> str:
    """Return the public submission URL containing *raw_token*.

    The base URL is read from the ``PUBLIC_BASE_URL`` environment variable,
    defaulting to ``http://localhost:5173`` (Vite dev server).  The path
    matches the React route defined in App.tsx.
    """
    base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/public/buyer-qualification/{raw_token}"


def _resolve_active_form_version(
    db: Session,
    tenant_id: int,
    intent_type: IntentType = IntentType.BUY,
) -> FormVersion | None:
    """Return the active FormVersion for *tenant_id* + *intent_type*, or None."""
    return (
        db.query(FormVersion)
        .join(FormTemplate, FormVersion.template_id == FormTemplate.id)
        .filter(
            FormTemplate.tenant_id == tenant_id,
            FormTemplate.intent_type == intent_type.value,
            FormVersion.is_active.is_(True),
        )
        .one_or_none()
    )


def _resolve_active_message_template(
    db: Session,
    tenant_id: int,
    intent_type: IntentType,
    key: MessageTemplateKey,
) -> MessageTemplateVersion | None:
    """Return the active MessageTemplateVersion for the given key, or None."""
    return (
        db.query(MessageTemplateVersion)
        .join(MessageTemplate, MessageTemplateVersion.template_id == MessageTemplate.id)
        .filter(
            MessageTemplate.tenant_id == tenant_id,
            MessageTemplate.intent_type == intent_type.value,
            MessageTemplate.key == key.value,
            MessageTemplateVersion.is_active.is_(True),
        )
        .one_or_none()
    )


def _get_tenant_email_credentials(db: Session, tenant_id: int) -> tuple[str, str] | None:
    """Return (from_email, app_password) for the tenant, or None if not found."""
    creds = (
        db.query(Credentials)
        .filter(Credentials.company_id == tenant_id)
        .first()
    )
    if creds is None:
        return None

    # Decrypt using EncryptedDBCredentialsStore if an encryption key is set;
    # fall back to treating the stored values as plain text (dev/test mode).
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if encryption_key:
        from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
        store = EncryptedDBCredentialsStore(db, encryption_key)
        return store.get_credentials(creds.agent_id)

    # Plain-text fallback (no encryption key configured)
    return creds.email_encrypted, creds.app_password_encrypted


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def on_buyer_lead_email_received(
    db: Session,
    tenant_id: int,
    lead_id: int,
    parsed_metadata: dict,
) -> None:
    """Handle a new buyer lead email by initiating the qualification pipeline.

    Algorithm (Req 9.1 – 9.5):
    1. Resolve active FormVersion for tenant + BUY intent.
       Log warning and return if none (Req 9.1, 9.2).
    2. Transition lead → FORM_INVITE_CREATED (Req 9.3).
    3. Create FormInvitation; raw token returned for URL embedding (Req 9.5).
    4. Resolve active INITIAL_INVITE_EMAIL MessageTemplateVersion.
       Log error and return if none (Req 9.3).
    5. Build render context including {{form.link}} (Req 9.5).
    6. Render template and send email (Req 9.3).
    7. Set invitation.sent_at, transition → FORM_INVITE_SENT (Req 9.3).
    8. Record outbound LeadInteraction with rendered subject (Req 9.4).

    Args:
        db: SQLAlchemy session.
        tenant_id: Owning tenant (company) ID.
        lead_id: Target lead ID.
        parsed_metadata: Arbitrary metadata extracted from the inbound email
            (e.g. property_address, listing_url, lead_source).  Merged into
            the template render context.
    """
    # ------------------------------------------------------------------
    # 1. Resolve active FormVersion (Req 9.1)
    # ------------------------------------------------------------------
    form_version = _resolve_active_form_version(db, tenant_id, IntentType.BUY)
    if form_version is None:
        logger.warning(
            "No active BUY form for tenant %d, skipping invite (lead_id=%d)",
            tenant_id,
            lead_id,
        )
        return  # Req 9.2 — no further action

    # ------------------------------------------------------------------
    # 2. Transition: NULL → NEW_EMAIL_RECEIVED → FORM_INVITE_CREATED (Req 9.3)
    # ------------------------------------------------------------------
    _state_machine.transition(
        db,
        tenant_id=tenant_id,
        lead_id=lead_id,
        intent_type=IntentType.BUY,
        to_state=LeadState.NEW_EMAIL_RECEIVED,
    )
    _state_machine.transition(
        db,
        tenant_id=tenant_id,
        lead_id=lead_id,
        intent_type=IntentType.BUY,
        to_state=LeadState.FORM_INVITE_CREATED,
    )

    # ------------------------------------------------------------------
    # 3. Create FormInvitation; raw token for URL (Req 9.5)
    # ------------------------------------------------------------------
    raw_token, invitation = _invitation_service.create_invitation(
        db,
        tenant_id=tenant_id,
        lead_id=lead_id,
        form_version_id=form_version.id,
    )

    # ------------------------------------------------------------------
    # 4. Resolve active INITIAL_INVITE_EMAIL template (Req 9.3)
    # ------------------------------------------------------------------
    msg_version = _resolve_active_message_template(
        db,
        tenant_id=tenant_id,
        intent_type=IntentType.BUY,
        key=MessageTemplateKey.INITIAL_INVITE_EMAIL,
    )
    if msg_version is None:
        logger.error(
            "No active INITIAL_INVITE_EMAIL template for tenant %d (lead_id=%d); "
            "skipping invite email.",
            tenant_id,
            lead_id,
        )
        # Record a failed interaction so the audit trail reflects the attempt
        db.add(
            LeadInteraction(
                tenant_id=tenant_id,
                lead_id=lead_id,
                intent_type=IntentType.BUY.value,
                channel=Channel.EMAIL.value,
                direction="outbound",
                occurred_at=datetime.utcnow(),
                content_text="[ERROR: no active INITIAL_INVITE_EMAIL template]",
            )
        )
        db.commit()
        return

    # ------------------------------------------------------------------
    # 5. Build render context (Req 9.5)
    # ------------------------------------------------------------------
    lead: Lead = db.get(Lead, lead_id)
    first_name = lead.name.split()[0] if lead.name else ""

    # Resolve tenant name for {{tenant.name}}
    from sqlalchemy import text as _text
    tenant_row = db.execute(_text("SELECT name FROM companies WHERE id = :tid"), {"tid": tenant_id}).fetchone()
    tenant_name = tenant_row[0] if tenant_row else ""

    context: dict = {
        "lead.first_name": first_name,
        "lead.email": lead.source_email,
        "form.link": _build_form_url(raw_token),
        "tenant.name": tenant_name,
        **parsed_metadata,
    }

    # ------------------------------------------------------------------
    # 6. Render template (Req 9.3)
    # ------------------------------------------------------------------
    rendered = _template_engine.render(msg_version, context)

    # ------------------------------------------------------------------
    # 6b. Send email via tenant SMTP credentials
    # ------------------------------------------------------------------
    creds = _get_tenant_email_credentials(db, tenant_id)
    if creds is None:
        logger.error(
            "No SMTP credentials found for tenant %d; cannot send invite email "
            "(lead_id=%d).",
            tenant_id,
            lead_id,
        )
    else:
        from_email, app_password = creds
        _send_email(
            to_address=lead.source_email,
            subject=rendered.subject,
            body=rendered.body,
            from_address=from_email,
            app_password=app_password,
        )

    # ------------------------------------------------------------------
    # 7. Mark invitation sent; transition → FORM_INVITE_SENT (Req 9.3)
    # ------------------------------------------------------------------
    invitation.sent_at = datetime.utcnow()
    # Update agent_current_state so agent-app inbox reflects the invite
    _lead_invite: Lead = db.get(Lead, lead_id)
    if _lead_invite is not None:
        _lead_invite.agent_current_state = "INVITE_SENT"
    db.commit()

    _state_machine.transition(
        db,
        tenant_id=tenant_id,
        lead_id=lead_id,
        intent_type=IntentType.BUY,
        to_state=LeadState.FORM_INVITE_SENT,
    )

    # ------------------------------------------------------------------
    # 7b. Insert INVITE_SENT lead event (Requirement 20.1)
    # ------------------------------------------------------------------
    try:
        from gmail_lead_sync.lead_event_utils import insert_lead_event
        insert_lead_event(
            db=db,
            lead_id=lead_id,
            event_type="INVITE_SENT",
            payload_dict={
                "subject": rendered.subject,
                "body": rendered.body,
            },
        )
        db.commit()
    except Exception as _exc:
        logger.error(
            "Failed to insert INVITE_SENT event for lead %d: %s",
            lead_id,
            _exc,
            exc_info=True,
        )

    # ------------------------------------------------------------------
    # 8. Record outbound LeadInteraction (Req 9.4)
    # ------------------------------------------------------------------
    db.add(
        LeadInteraction(
            tenant_id=tenant_id,
            lead_id=lead_id,
            intent_type=IntentType.BUY.value,
            channel=Channel.EMAIL.value,
            direction="outbound",
            occurred_at=datetime.utcnow(),
            content_text=rendered.subject,  # subject only — Req 10.4 / 17.6
        )
    )
    db.commit()

    logger.info(
        "Buyer lead invite sent: tenant=%d lead=%d invitation=%d",
        tenant_id,
        lead_id,
        invitation.id,
    )


# ---------------------------------------------------------------------------
# Additional imports for on_buyer_form_submitted
# ---------------------------------------------------------------------------
# (imported at module level below — added here as a note; actual imports are
#  at the top of the file via the append to the import block)


# ---------------------------------------------------------------------------
# Scoring engine singleton
# ---------------------------------------------------------------------------

from gmail_lead_sync.preapproval.scoring_engine import ScoringEngine  # noqa: E402

_scoring_engine = ScoringEngine()


# ---------------------------------------------------------------------------
# Additional helpers
# ---------------------------------------------------------------------------

def _resolve_active_scoring_version(
    db: Session,
    tenant_id: int,
    intent_type: IntentType = IntentType.BUY,
):
    """Return the active ScoringVersion for *tenant_id* + *intent_type*, or None."""
    from gmail_lead_sync.preapproval.models_preapproval import ScoringConfig, ScoringVersion

    return (
        db.query(ScoringVersion)
        .join(ScoringConfig, ScoringVersion.scoring_config_id == ScoringConfig.id)
        .filter(
            ScoringConfig.tenant_id == tenant_id,
            ScoringConfig.intent_type == intent_type.value,
            ScoringVersion.is_active.is_(True),
        )
        .one_or_none()
    )


def _validate_answers(answers_payload: dict, form_version) -> None:
    """Validate *answers_payload* against the required questions in *form_version*.

    Raises:
        ValueError: with a dict of field-level errors if any required question
            is missing from *answers_payload*.
    """
    import json as _json

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
# Handler: on_buyer_form_submitted
# ---------------------------------------------------------------------------

def on_buyer_form_submitted(
    db: Session,
    raw_token: str,
    answers_payload: dict,
    request_metadata: dict,
) -> dict:
    """Handle a buyer's form submission through the full qualification pipeline.

    Algorithm (Req 4.3, 5.1, 5.11, 10.1–10.4):
    1.  Validate token via invitation_service (raises TokenNotFoundError |
        TokenUsedError | TokenExpiredError).
    2.  Validate answers against the FormVersion schema (raises ValueError).
    3.  Persist FormSubmission + SubmissionAnswer rows; flush to get IDs.
    4.  Mark token used (invitation.used_at = now()).
    5.  Transition: FORM_INVITE_SENT → FORM_SUBMITTED.
    6.  Resolve active ScoringVersion; if none, log warning and return partial
        result (Req 5.11).
    7.  Compute score via scoring_engine.
    8.  Persist SubmissionScore; commit.
    9.  Transition: FORM_SUBMITTED → SCORED.
    10. Resolve active POST_SUBMISSION_EMAIL template; if none, log error,
        record failed interaction, and return (Req 7.9).
    11. Render template with bucket variant; send email.
    12. Transition: SCORED → POST_SUBMISSION_EMAIL_SENT.
    13. Record outbound LeadInteraction (subject only — Req 10.4).
    14. Commit and return SubmitResult.

    Args:
        db: SQLAlchemy session.
        raw_token: The raw URL-safe token from the submission URL.
        answers_payload: Dict of question_key → answer value.
        request_metadata: Dict with optional keys: user_agent, device_type,
            time_to_submit_seconds, lead_source, property_address,
            listing_url, repeat_inquiry_count.

    Returns:
        Dict with keys ``submission_id`` and ``score`` (total, bucket,
        explanation).

    Raises:
        TokenNotFoundError: Token hash not found in DB.
        TokenUsedError: Token has already been consumed.
        TokenExpiredError: Token has passed its expiry time.
        ValueError: Answers fail schema validation.
    """
    import json as _json

    from gmail_lead_sync.preapproval.models_preapproval import (
        FormSubmission,
        FormVersion,
        SubmissionAnswer,
        SubmissionScore,
    )

    # ------------------------------------------------------------------
    # 1. Validate token (Req 3.4, 4.2)
    # ------------------------------------------------------------------
    invitation = _invitation_service.validate_token(db, raw_token)

    # ------------------------------------------------------------------
    # 2. Validate answers against form version schema (Req 4.2)
    # ------------------------------------------------------------------
    form_version: FormVersion = db.get(FormVersion, invitation.form_version_id)
    _validate_answers(answers_payload, form_version)

    # ------------------------------------------------------------------
    # 3. Persist FormSubmission + SubmissionAnswer rows (Req 4.3)
    # ------------------------------------------------------------------
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
        # Req 17.5: raw_payload_json stored but never logged
        raw_payload_json=_json.dumps(answers_payload),
    )
    db.add(submission)
    db.flush()  # populate submission.id

    for question_key, answer_value in answers_payload.items():
        db.add(
            SubmissionAnswer(
                submission_id=submission.id,
                question_key=question_key,
                answer_value_json=_json.dumps(answer_value),
            )
        )

    # ------------------------------------------------------------------
    # 4. Mark token used (Req 3.5, 20.3)
    # ------------------------------------------------------------------
    invitation.used_at = datetime.utcnow()

    # ------------------------------------------------------------------
    # 5. Transition: FORM_INVITE_SENT → FORM_SUBMITTED (Req 10.1)
    # ------------------------------------------------------------------
    _state_machine.transition(
        db,
        tenant_id=invitation.tenant_id,
        lead_id=invitation.lead_id,
        intent_type=IntentType.BUY,
        to_state=LeadState.FORM_SUBMITTED,
    )

    # ------------------------------------------------------------------
    # 5b. Insert FORM_SUBMITTED lead event (Requirement 20.1)
    # ------------------------------------------------------------------
    try:
        from gmail_lead_sync.lead_event_utils import insert_lead_event
        insert_lead_event(
            db=db,
            lead_id=invitation.lead_id,
            event_type="FORM_SUBMITTED",
            payload_dict={"answers": answers_payload},
        )
        db.flush()
    except Exception as _exc:
        logger.error(
            "Failed to insert FORM_SUBMITTED event for lead %d: %s",
            invitation.lead_id,
            _exc,
            exc_info=True,
        )

    # Update agent_current_state so agent-app inbox reflects form submission
    _lead_form: Lead = db.get(Lead, invitation.lead_id)
    if _lead_form is not None:
        _lead_form.agent_current_state = "FORM_SUBMITTED"
    db.flush()

    # ------------------------------------------------------------------
    # 6. Resolve active ScoringVersion (Req 5.11)
    # ------------------------------------------------------------------
    scoring_version = _resolve_active_scoring_version(db, invitation.tenant_id, IntentType.BUY)
    if scoring_version is None:
        logger.warning(
            "No active BUY scoring version for tenant %d; leaving lead %d in "
            "FORM_SUBMITTED state (submission_id=%d).",
            invitation.tenant_id,
            invitation.lead_id,
            submission.id,
        )
        db.commit()
        return {"submission_id": submission.id, "score": None}

    # ------------------------------------------------------------------
    # 7. Compute score (Req 5.1)
    # ------------------------------------------------------------------
    metadata: dict = {
        "property_address": request_metadata.get("property_address"),
        "listing_url": request_metadata.get("listing_url"),
        "lead_source": request_metadata.get("lead_source"),
        "repeat_inquiry_count": request_metadata.get("repeat_inquiry_count", 0),
    }
    score_result = _scoring_engine.compute(answers_payload, scoring_version, metadata)

    # ------------------------------------------------------------------
    # 8. Persist SubmissionScore; link scoring_version to submission (Req 4.3, 20.4)
    # ------------------------------------------------------------------
    submission.scoring_version_id = scoring_version.id

    breakdown_serializable = [
        {
            "question_key": item.question_key,
            "answer": item.answer,
            "points": item.points,
            "reason": item.reason,
        }
        for item in score_result.breakdown
    ]

    db.add(
        SubmissionScore(
            submission_id=submission.id,
            total_score=score_result.total,
            bucket=score_result.bucket.value,
            breakdown_json=_json.dumps(breakdown_serializable),
            explanation_text=score_result.explanation,
        )
    )

    # ------------------------------------------------------------------
    # 8b. Write score back to Lead row for agent-app visibility
    # ------------------------------------------------------------------
    _lead_for_score: Lead = db.get(Lead, invitation.lead_id)
    if _lead_for_score is not None:
        _lead_for_score.score = score_result.total
        _lead_for_score.score_bucket = score_result.bucket.value
        _lead_for_score.score_breakdown = _json.dumps({
            "factors": breakdown_serializable,
        })
        _lead_for_score.agent_current_state = "SCORED"

    db.commit()

    # ------------------------------------------------------------------
    # 9. Transition: FORM_SUBMITTED → SCORED (Req 10.1)
    # ------------------------------------------------------------------
    _state_machine.transition(
        db,
        tenant_id=invitation.tenant_id,
        lead_id=invitation.lead_id,
        intent_type=IntentType.BUY,
        to_state=LeadState.SCORED,
    )

    # ------------------------------------------------------------------
    # 10. Resolve active POST_SUBMISSION_EMAIL template (Req 7.9)
    # ------------------------------------------------------------------
    msg_version = _resolve_active_message_template(
        db,
        tenant_id=invitation.tenant_id,
        intent_type=IntentType.BUY,
        key=MessageTemplateKey.POST_SUBMISSION_EMAIL,
    )
    if msg_version is None:
        logger.error(
            "No active POST_SUBMISSION_EMAIL template for tenant %d (lead_id=%d); "
            "skipping post-submission email.",
            invitation.tenant_id,
            invitation.lead_id,
        )
        db.add(
            LeadInteraction(
                tenant_id=invitation.tenant_id,
                lead_id=invitation.lead_id,
                intent_type=IntentType.BUY.value,
                channel=Channel.EMAIL.value,
                direction="outbound",
                occurred_at=datetime.utcnow(),
                content_text="[ERROR: no active POST_SUBMISSION_EMAIL template]",
            )
        )
        db.commit()
        return {
            "submission_id": submission.id,
            "score": {
                "total": score_result.total,
                "bucket": score_result.bucket.value,
                "explanation": score_result.explanation,
            },
        }

    # ------------------------------------------------------------------
    # 11. Render template with bucket variant and send email (Req 10.2)
    # ------------------------------------------------------------------
    lead: Lead = db.get(Lead, invitation.lead_id)
    first_name = lead.name.split()[0] if lead.name else ""

    from sqlalchemy import text as _text
    tenant_row = db.execute(_text("SELECT name FROM companies WHERE id = :tid"), {"tid": invitation.tenant_id}).fetchone()
    tenant_name = tenant_row[0] if tenant_row else ""

    context: dict = {
        "lead.first_name": first_name,
        "lead.email": lead.source_email,
        "score.total": str(score_result.total),
        "score.bucket": score_result.bucket.value,
        "score.explanation": score_result.explanation,
        "tenant.name": tenant_name,
        **{k: str(v) for k, v in request_metadata.items() if v is not None},
    }

    rendered = _template_engine.render(
        msg_version,
        context,
        variant_key=score_result.bucket.value,  # Req 10.2
    )

    creds = _get_tenant_email_credentials(db, invitation.tenant_id)
    if creds is None:
        logger.error(
            "No SMTP credentials for tenant %d; cannot send POST_SUBMISSION_EMAIL "
            "(lead_id=%d).",
            invitation.tenant_id,
            invitation.lead_id,
        )
    else:
        from_email, app_password = creds
        _send_email(
            to_address=lead.source_email,
            subject=rendered.subject,
            body=rendered.body,
            from_address=from_email,
            app_password=app_password,
        )

    # ------------------------------------------------------------------
    # 12. Transition: SCORED → POST_SUBMISSION_EMAIL_SENT (Req 10.1)
    # ------------------------------------------------------------------
    _state_machine.transition(
        db,
        tenant_id=invitation.tenant_id,
        lead_id=invitation.lead_id,
        intent_type=IntentType.BUY,
        to_state=LeadState.POST_SUBMISSION_EMAIL_SENT,
    )

    # ------------------------------------------------------------------
    # 12b. Insert POST_EMAIL_SENT lead event (Requirement 20.1)
    # ------------------------------------------------------------------
    try:
        from gmail_lead_sync.lead_event_utils import insert_lead_event
        insert_lead_event(
            db=db,
            lead_id=invitation.lead_id,
            event_type="POST_EMAIL_SENT",
            payload_dict={
                "subject": rendered.subject,
                "body": rendered.body,
            },
        )
        db.flush()
    except Exception as _exc:
        logger.error(
            "Failed to insert POST_EMAIL_SENT event for lead %d: %s",
            invitation.lead_id,
            _exc,
            exc_info=True,
        )

    # ------------------------------------------------------------------
    # 13. Record outbound LeadInteraction — subject only (Req 10.3, 10.4)
    # ------------------------------------------------------------------
    db.add(
        LeadInteraction(
            tenant_id=invitation.tenant_id,
            lead_id=invitation.lead_id,
            intent_type=IntentType.BUY.value,
            channel=Channel.EMAIL.value,
            direction="outbound",
            occurred_at=datetime.utcnow(),
            content_text=rendered.subject,  # Req 10.4 / 17.6: subject only
        )
    )
    db.commit()

    logger.info(
        "Buyer form submitted and scored: tenant=%d lead=%d submission=%d "
        "bucket=%s score=%d",
        invitation.tenant_id,
        invitation.lead_id,
        submission.id,
        score_result.bucket.value,
        score_result.total,
    )

    # ------------------------------------------------------------------
    # 14. Return SubmitResult (Req 4.4)
    # ------------------------------------------------------------------
    return {
        "submission_id": submission.id,
        "score": {
            "total": score_result.total,
            "bucket": score_result.bucket.value,
            "explanation": score_result.explanation,
        },
    }

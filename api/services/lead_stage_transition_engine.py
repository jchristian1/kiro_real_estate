"""
LeadStageTransitionEngine — Orchestration service for pipeline lifecycle events.

Receives platform lifecycle events, resolves event-to-stage mappings, evaluates
automation rules, and delegates to existing platform services. This is the single
coordination point across all pipeline services.

Business rules:
- If no active pipeline exists for the lead's company, return silently (Req 6.2).
- If lead has no current_stage_id, assign the pipeline's default stage first (Req 6.7).
- Apply event mapping if it exists and is_enabled=True (Req 6.3).
- Skip event mapping if is_enabled=False (Req 6.4).
- Evaluate automation rules in ascending position order (Req 6.5).
- On action step failure: log to audit log and continue remaining steps (Req 6.6, 12.3, 12.4).
- Write audit log entry for every stage transition and every action executed (Req 6.8).

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 12.3, 12.4
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from api.models.pipeline_models import (
    BuiltInEventType,
    ChangeSource,
    PipelineStage,
)
from api.services.audit_log import record_audit_log
from api.services.lead_stage_service import assign_initial_stage, move_stage
from api.services.pipeline_action_rule_service import evaluate_rules
from api.services.pipeline_event_mapping_service import get_mapping
from api.services.pipeline_service import get_active_pipeline

logger = logging.getLogger(__name__)

# Sentinel user_id used for system-generated audit log entries.
_SYSTEM_USER_ID = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_company_id(db: Session, lead_id: int) -> Optional[int]:
    """
    Resolve the company_id for a lead.

    Tries lead.company_id first (patched by agent_models), then falls back to
    lead.lead_source.company_id if the lead source carries a company reference.
    Returns None if neither is available.
    """
    # Import here to avoid circular imports at module load time.
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        return None

    # Direct company_id column (patched by agent_models).
    company_id = getattr(lead, "company_id", None)
    if company_id:
        return company_id

    # Fallback: resolve via lead_source relationship.
    lead_source = getattr(lead, "lead_source", None)
    if lead_source is not None:
        source_company_id = getattr(lead_source, "company_id", None)
        if source_company_id:
            return source_company_id

    # Fallback: resolve via agent_user relationship.
    agent_user = getattr(lead, "agent_user", None)
    if agent_user is not None:
        agent_company_id = getattr(agent_user, "company_id", None)
        if agent_company_id:
            return agent_company_id

    return None


def _get_default_stage(db: Session, pipeline_id: int) -> Optional[PipelineStage]:
    """Return the default stage for *pipeline_id*, or None if none is set."""
    return (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.is_default.is_(True),
        )
        .first()
    )


def _get_lead_and_tenant(db: Session, lead_id: int):
    """Return (lead, tenant_id) or raise ValueError if lead not found."""
    from gmail_lead_sync.models import Lead
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")
    tenant_id = _get_company_id(db, lead_id)
    if tenant_id is None:
        raise ValueError(f"Cannot resolve company_id for lead {lead_id}")
    return lead, tenant_id


def _get_smtp_creds(db: Session, tenant_id: int):
    """Return (from_email, app_password) for tenant, or raise ValueError."""
    import os as _os
    from gmail_lead_sync.models import Credentials
    creds = db.query(Credentials).filter(Credentials.company_id == tenant_id).first()
    if creds is None:
        raise ValueError(f"No SMTP credentials for tenant {tenant_id}")
    encryption_key = _os.environ.get("ENCRYPTION_KEY")
    if encryption_key:
        from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
        store = EncryptedDBCredentialsStore(db, encryption_key)
        return store.get_credentials(creds.agent_id)
    return creds.email_encrypted, creds.app_password_encrypted


def _send_email_via_smtp(to_address: str, subject: str, body: str, from_address: str, app_password: str) -> None:
    """Send email via Gmail SMTP using AutoResponder."""
    from gmail_lead_sync.responder import AutoResponder
    responder = object.__new__(AutoResponder)
    ok = responder.send_email(
        to_address=to_address,
        subject=subject,
        body=body,
        from_address=from_address,
        app_password=app_password,
    )
    if not ok:
        raise RuntimeError(f"SMTP send failed to {to_address}")


def _render_admin_template(db: Session, template_id, lead, tenant_id: int) -> tuple[str, str]:
    """Fetch an AdminTemplate by ID and render it with lead/agent placeholders.

    For {form_link}, creates a real FormInvitation and embeds the token URL.
    Falls back to the base URL if no active form version exists for the tenant.
    """
    from api.repositories.template_repository import AdminTemplateRepository
    from gmail_lead_sync.agent_models import AgentUser
    import os as _os

    repo = AdminTemplateRepository(db)
    tpl = repo.get_by_id(int(template_id))
    if tpl is None:
        raise ValueError(f"AdminTemplate {template_id} not found")

    agent = db.query(AgentUser).filter(AgentUser.company_id == tenant_id).first()
    base_url = _os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")

    # Build a real form link with a token if the template uses {form_link}
    form_link = f"{base_url}/public/buyer-qualification"
    if "{form_link}" in tpl.subject or "{form_link}" in tpl.body:
        try:
            from gmail_lead_sync.preapproval.handlers import (
                _resolve_active_form_version, _build_form_url,
            )
            from gmail_lead_sync.preapproval.invitation_service import FormInvitationService
            from gmail_lead_sync.preapproval.models_preapproval import IntentType
            form_version = _resolve_active_form_version(db, tenant_id, IntentType.BUY)
            if form_version is not None:
                raw_token, _ = FormInvitationService().create_invitation(
                    db, tenant_id=tenant_id, lead_id=lead.id,
                    form_version_id=form_version.id,
                )
                form_link = _build_form_url(raw_token)
        except Exception as _fe:
            logger.warning(
                "Could not create form invitation for lead %s tenant %s: %s",
                lead.id, tenant_id, _fe,
            )

    mapping = {
        "{lead_name}": lead.name or "",
        "{agent_name}": (agent.full_name if agent else "") or "",
        "{agent_phone}": (agent.phone if agent else "") or "",
        "{agent_email}": (agent.email if agent else "") or "",
        "{form_link}": form_link,
    }
    subject = tpl.subject
    body = tpl.body
    for placeholder, value in mapping.items():
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)
    return subject, body


def _execute_step(
    db: Session,
    lead_id: int,
    pipeline_id: int,
    rule_id: int,
    step,
    context: dict,
) -> None:
    """
    Execute a single automation rule step.

    Raises an exception on failure so the caller can catch and log it.
    """
    action_type = step.action_type.value if hasattr(step.action_type, "value") else step.action_type
    config: dict = {}
    try:
        config = json.loads(step.action_config_json)
    except (json.JSONDecodeError, TypeError):
        pass

    if action_type == "send_email_template":
        template_id = config.get("template_id")
        if template_id is None:
            raise ValueError("send_email_template: missing template_id in action_config_json")

        lead, tenant_id = _get_lead_and_tenant(db, lead_id)
        subject, body = _render_admin_template(db, template_id, lead, tenant_id)
        from_email, app_password = _get_smtp_creds(db, tenant_id)
        _send_email_via_smtp(lead.source_email, subject, body, from_email, app_password)
        logger.info(
            "Pipeline action: send_email_template sent lead_id=%s template_id=%s",
            lead_id, template_id,
        )

    elif action_type == "send_qualification_form":
        lead, tenant_id = _get_lead_and_tenant(db, lead_id)
        # Delegate to the existing on_buyer_lead_email_received handler which
        # creates the invitation, renders the template, and sends the email.
        try:
            from gmail_lead_sync.preapproval.handlers import on_buyer_lead_email_received
            on_buyer_lead_email_received(
                db=db,
                tenant_id=tenant_id,
                lead_id=lead_id,
                parsed_metadata=context,
                skip_pipeline_events=True,  # prevent recursive pipeline event firing
            )
            logger.info(
                "Pipeline action: send_qualification_form sent lead_id=%s tenant_id=%s",
                lead_id, tenant_id,
            )
        except Exception as exc:
            raise RuntimeError(f"send_qualification_form failed for lead {lead_id}: {exc}") from exc

    elif action_type == "send_bucket_followup_email":
        template_id = config.get("template_id")
        lead, tenant_id = _get_lead_and_tenant(db, lead_id)

        if template_id:
            # Use the explicitly configured template
            subject, body = _render_admin_template(db, template_id, lead, tenant_id)
        else:
            # Fall back to the bucket-specific AgentTemplate (POST_HOT / POST_WARM / POST_NURTURE)
            bucket = getattr(lead, "score_bucket", None)
            if bucket is None:
                raise ValueError(f"send_bucket_followup_email: lead {lead_id} has no score_bucket")
            from gmail_lead_sync.preapproval.handlers import (
                _resolve_agent_template, _render_agent_template, _build_form_url,
            )
            from gmail_lead_sync.agent_models import AgentUser
            _bucket_to_type = {"HOT": "POST_HOT", "WARM": "POST_WARM", "NURTURE": "POST_NURTURE"}
            tpl_type = _bucket_to_type.get(bucket.upper())
            if tpl_type is None:
                raise ValueError(f"send_bucket_followup_email: unknown bucket '{bucket}'")
            agent_tpl = _resolve_agent_template(db, tenant_id, tpl_type)
            if agent_tpl is None:
                raise ValueError(f"No active {tpl_type} AgentTemplate for tenant {tenant_id}")
            agent = db.query(AgentUser).filter(AgentUser.company_id == tenant_id).first()
            agent_context = {
                "lead_name": lead.name or "",
                "agent_name": (agent.full_name if agent else "") or "",
                "agent_phone": (agent.phone if agent else "") or "",
                "agent_email": (agent.email if agent else "") or "",
                "form_link": "",
            }
            subject, body = _render_agent_template(agent_tpl[0], agent_tpl[1], agent_context)

        from_email, app_password = _get_smtp_creds(db, tenant_id)
        _send_email_via_smtp(lead.source_email, subject, body, from_email, app_password)
        logger.info(
            "Pipeline action: send_bucket_followup_email sent lead_id=%s",
            lead_id,
        )

    elif action_type == "move_to_stage":
        stage_id = config.get("stage_id")
        if stage_id is None:
            raise ValueError("move_to_stage: missing stage_id in action_config_json")
        move_stage(db, lead_id, int(stage_id), ChangeSource.automation)
        logger.info(
            "Pipeline action: move_to_stage lead_id=%s stage_id=%s",
            lead_id, stage_id,
        )

    else:
        logger.warning(
            "Unknown action_type '%s' for step %s in rule %s — skipping",
            action_type, step.id, rule_id,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fire_event(
    db: Session,
    lead_id: int,
    event_type: BuiltInEventType,
    context: dict,
) -> None:
    """
    Fire a lifecycle event for a lead, triggering stage transitions and automation rules.

    Steps:
    1. Load the lead and resolve its company_id.
    2. Look up the active pipeline for the company; return silently if none (Req 6.2).
    3. If lead has no current_stage_id, assign the default stage (Req 6.7).
    4. Look up the event mapping; if enabled, move the lead to the mapped stage (Req 6.3/6.4).
    5. Evaluate automation rules and execute each matching rule's steps in order (Req 6.5).
    6. On step failure: log to audit log and continue (Req 6.6, 12.3, 12.4).
    7. Write audit log entries for all transitions and actions (Req 6.8).

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 12.3, 12.4
    """
    from gmail_lead_sync.models import Lead

    # ------------------------------------------------------------------
    # 1. Load lead
    # ------------------------------------------------------------------
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        logger.warning("fire_event: lead %s not found, skipping", lead_id)
        return

    # ------------------------------------------------------------------
    # 2. Resolve company_id and active pipeline (Req 6.1, 6.2)
    # ------------------------------------------------------------------
    company_id = _get_company_id(db, lead_id)
    if company_id is None:
        logger.warning(
            "fire_event: cannot resolve company_id for lead %s, skipping", lead_id
        )
        return

    pipeline = get_active_pipeline(db, company_id)
    if pipeline is None:
        # No active pipeline — return silently per Req 6.2.
        return

    pipeline_id = pipeline.id

    # ------------------------------------------------------------------
    # 3. Assign initial stage if lead has none (Req 6.7)
    # ------------------------------------------------------------------
    if lead.current_stage_id is None:
        default_stage = _get_default_stage(db, pipeline_id)
        if default_stage is not None:
            assign_initial_stage(db, lead_id, pipeline_id, default_stage.id)
            # Refresh lead to reflect updated current_stage_id.
            db.refresh(lead)
            record_audit_log(
                db_session=db,
                user_id=_SYSTEM_USER_ID,
                action="lead_stage_assigned",
                resource_type="lead",
                resource_id=lead_id,
                details=(
                    f"Lead {lead_id} assigned to initial stage {default_stage.id} "
                    f"('{default_stage.name}') in pipeline {pipeline_id} "
                    f"via event '{event_type.value}'"
                ),
            )
        else:
            logger.warning(
                "fire_event: pipeline %s has no default stage; skipping initial assignment for lead %s",
                pipeline_id,
                lead_id,
            )

    # ------------------------------------------------------------------
    # 4. Apply event mapping (Req 6.3, 6.4)
    # ------------------------------------------------------------------
    mapping = get_mapping(db, pipeline_id, event_type)
    stage_entered: Optional[int] = None  # track if we moved to a new stage
    if mapping is not None:
        if mapping.is_enabled:
            move_stage(db, lead_id, mapping.target_stage_id, ChangeSource.event)
            db.refresh(lead)
            stage_entered = mapping.target_stage_id
            record_audit_log(
                db_session=db,
                user_id=_SYSTEM_USER_ID,
                action="lead_stage_moved",
                resource_type="lead",
                resource_id=lead_id,
                details=(
                    f"Lead {lead_id} moved to stage {mapping.target_stage_id} "
                    f"via event mapping for '{event_type.value}' "
                    f"in pipeline {pipeline_id}"
                ),
            )
        # If is_enabled=False, do nothing (Req 6.4).

    # ------------------------------------------------------------------
    # 5. Evaluate automation rules (Req 6.5)
    #
    # Evaluate both:
    #   a) on_event rules matching this event_type
    #   b) on_stage_enter rules matching the lead's current stage
    #      (fires when the lead just entered a new stage via event mapping)
    # ------------------------------------------------------------------
    matching_rules = evaluate_rules(db, pipeline_id, event_type.value, lead, stage_just_entered_id=stage_entered)

    for rule in matching_rules:
        steps = sorted(rule.steps, key=lambda s: s.position)
        for step in steps:
            try:
                _execute_step(db, lead_id, pipeline_id, rule.id, step, context)
                # Write audit log for successful action (Req 6.8).
                record_audit_log(
                    db_session=db,
                    user_id=_SYSTEM_USER_ID,
                    action="pipeline_action_executed",
                    resource_type="pipeline_action_rule_step",
                    resource_id=step.id,
                    details=(
                        f"Rule {rule.id} ('{rule.name}') step {step.id} "
                        f"action_type='{step.action_type.value if hasattr(step.action_type, 'value') else step.action_type}' "
                        f"executed for lead {lead_id} on event '{event_type.value}'"
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                # Log failure and continue remaining steps (Req 6.6, 12.3, 12.4).
                error_msg = str(exc)
                logger.error(
                    "Pipeline action step failed: rule_id=%s step_id=%s lead_id=%s error=%s",
                    rule.id,
                    step.id,
                    lead_id,
                    error_msg,
                )
                record_audit_log(
                    db_session=db,
                    user_id=_SYSTEM_USER_ID,
                    action="pipeline_action_failed",
                    resource_type="pipeline_action_rule_step",
                    resource_id=step.id,
                    details=(
                        f"Rule {rule.id} step {step.id} FAILED for lead {lead_id} "
                        f"on event '{event_type.value}': {error_msg}"
                    ),
                )
                # Continue to next step — do NOT re-raise.

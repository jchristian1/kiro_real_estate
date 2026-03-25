"""
send_email_template / send_bucket_followup_email action handler.

Validates config, resolves tenant credentials via EmailDeliveryService,
renders the AdminTemplate via TemplateRenderService, and sends via SMTP.

Config schema:
    { "template_id": <int> }
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from api.communications.email_delivery import EmailDeliveryService
from api.communications.template_render import TemplateRenderService
from api.pipelines.handlers.base import ActionResult, resolve_lead_company_id

logger = logging.getLogger(__name__)

_delivery = EmailDeliveryService()
_renderer = TemplateRenderService()


class SendEmailTemplateHandler:
    """Handles send_email_template and send_bucket_followup_email actions.

    Both action types share identical execution logic — they differ only in
    semantic intent (general template vs. bucket-specific follow-up).
    """

    def execute(
        self,
        db: Session,
        lead_id: int,
        config: dict,
        context: dict,
    ) -> ActionResult:
        template_id = config.get("template_id")
        if template_id is None:
            return ActionResult(
                success=False,
                error="send_email_template: missing template_id in action_config_json",
            )

        try:
            template_id = int(template_id)
        except (TypeError, ValueError):
            return ActionResult(
                success=False,
                error=f"send_email_template: template_id must be an integer, got {template_id!r}",
            )

        try:
            from gmail_lead_sync.models import Lead

            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead is None:
                return ActionResult(success=False, error=f"Lead {lead_id} not found")

            tenant_id = resolve_lead_company_id(db, lead_id)
            if tenant_id is None:
                return ActionResult(
                    success=False,
                    error=f"Cannot resolve company_id for lead {lead_id}",
                )

            subject, body = _renderer.render_admin_template(db, template_id, lead, tenant_id)

            ok = _delivery.send(db, tenant_id, lead.source_email, subject, body)
            if not ok:
                return ActionResult(
                    success=False,
                    error=f"send_email_template: delivery failed for lead {lead_id}",
                )

            logger.info(
                "send_email_template: sent lead_id=%s template_id=%s",
                lead_id, template_id,
            )

            # Record structured activity — after successful send.
            try:
                from api.services.lead_activity import record_activity
                record_activity(
                    db,
                    lead_id=lead_id,
                    event_type="response_email_sent",
                    company_id=tenant_id,
                    actor_source="pipeline",
                    metadata={"template_id": template_id, "to": lead.source_email},
                )
            except Exception as _ae:
                logger.warning(
                    "send_email_template: record_activity failed for lead %s: %s",
                    lead_id, _ae,
                )

            return ActionResult(
                success=True,
                metadata={"template_id": template_id, "to": lead.source_email},
            )

        except Exception as exc:
            return ActionResult(success=False, error=str(exc))

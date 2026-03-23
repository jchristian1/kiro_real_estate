"""
send_email_template / send_bucket_followup_email action handler.

Validates config, resolves tenant credentials, renders the AdminTemplate,
and sends via SMTP. All email-sending logic for pipeline rules lives here.

Config schema:
    { "template_id": <int> }
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from api.pipelines.handlers.base import ActionResult, resolve_lead_company_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers (owned by this handler — not shared with the engine)
# ---------------------------------------------------------------------------


def _get_smtp_credentials(db: Session, tenant_id: int) -> tuple[str, str]:
    from gmail_lead_sync.models import Credentials

    creds = db.query(Credentials).filter(Credentials.company_id == tenant_id).first()
    if creds is None:
        raise ValueError(f"No SMTP credentials for tenant {tenant_id}")
    encryption_key = os.environ.get("ENCRYPTION_KEY")
    if encryption_key:
        from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
        store = EncryptedDBCredentialsStore(db, encryption_key)
        return store.get_credentials(creds.agent_id)
    return creds.email_encrypted, creds.app_password_encrypted


def _render_admin_template(
    db: Session, template_id: int, lead, tenant_id: int
) -> tuple[str, str]:
    """Render AdminTemplate with lead/agent placeholders.

    Handles {form_link} by delegating to the qualification module's public
    interface (get_or_create_form_link). This handler does not create
    qualification invitations/tokens directly.
    Returns (subject, body). Raises ValueError if template not found.
    """
    from api.repositories.template_repository import AdminTemplateRepository
    from gmail_lead_sync.agent_models import AgentUser

    repo = AdminTemplateRepository(db)
    tpl = repo.get_by_id(template_id)
    if tpl is None:
        raise ValueError(f"AdminTemplate {template_id} not found")

    agent = db.query(AgentUser).filter(AgentUser.company_id == tenant_id).first()

    form_link = ""
    if "{form_link}" in tpl.subject or "{form_link}" in tpl.body:
        from gmail_lead_sync.preapproval.handlers import get_or_create_form_link
        form_link = get_or_create_form_link(db, tenant_id, lead.id)

    placeholders = {
        "{lead_name}": lead.name or "",
        "{agent_name}": (agent.full_name if agent else "") or "",
        "{agent_phone}": (agent.phone if agent else "") or "",
        "{agent_email}": (agent.email if agent else "") or "",
        "{form_link}": form_link,
    }
    subject, body = tpl.subject, tpl.body
    for key, value in placeholders.items():
        subject = subject.replace(key, value)
        body = body.replace(key, value)
    return subject, body


def _send_via_smtp(
    to_address: str, subject: str, body: str, from_address: str, app_password: str
) -> None:
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


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


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

            subject, body = _render_admin_template(db, template_id, lead, tenant_id)
            from_email, app_password = _get_smtp_credentials(db, tenant_id)
            _send_via_smtp(lead.source_email, subject, body, from_email, app_password)

            logger.info(
                "send_email_template: sent lead_id=%s template_id=%s",
                lead_id, template_id,
            )
            return ActionResult(
                success=True,
                metadata={"template_id": template_id, "to": lead.source_email},
            )

        except Exception as exc:
            return ActionResult(success=False, error=str(exc))

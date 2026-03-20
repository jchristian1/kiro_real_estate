"""
CommunicationsService — Pure email rendering and sending.

This module owns exactly one responsibility: given a rendered subject + body
and SMTP credentials, send the email.  It also provides helpers to render
AdminTemplate rows with lead/agent placeholders (including {form_link}).

No business logic lives here.  No pipeline events are fired here.
No stage transitions happen here.  This module is a leaf — it depends on
nothing in api.services except the template repository.

Public surface:
    render_admin_template(db, template_id, lead, tenant_id) -> (subject, body)
    send_email(to, subject, body, from_address, app_password) -> None
    get_smtp_credentials(db, tenant_id) -> (from_email, app_password)
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from gmail_lead_sync.models import Lead

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SMTP credentials
# ---------------------------------------------------------------------------


def get_smtp_credentials(db: Session, tenant_id: int) -> tuple[str, str]:
    """Return (from_email, app_password) for *tenant_id*.

    Raises ValueError if no credentials are found.
    """
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


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------


def send_email(
    to_address: str,
    subject: str,
    body: str,
    from_address: str,
    app_password: str,
) -> None:
    """Send *subject* / *body* to *to_address* via Gmail SMTP.

    Raises RuntimeError if the send fails.
    """
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
# Template rendering
# ---------------------------------------------------------------------------


def render_admin_template(
    db: Session,
    template_id: int,
    lead: "Lead",
    tenant_id: int,
) -> tuple[str, str]:
    """Fetch AdminTemplate *template_id* and render it with lead/agent placeholders.

    Handles {form_link} by creating a real FormInvitation token URL when the
    active form version exists for the tenant.  Falls back to the public base
    URL if no active form version is found.

    Returns (subject, body).
    Raises ValueError if the template does not exist.
    """
    from api.repositories.template_repository import AdminTemplateRepository
    from gmail_lead_sync.agent_models import AgentUser

    repo = AdminTemplateRepository(db)
    tpl = repo.get_by_id(int(template_id))
    if tpl is None:
        raise ValueError(f"AdminTemplate {template_id} not found")

    agent = db.query(AgentUser).filter(AgentUser.company_id == tenant_id).first()
    base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")

    form_link = f"{base_url}/public/buyer-qualification"
    if "{form_link}" in tpl.subject or "{form_link}" in tpl.body:
        form_link = _build_form_link(db, tenant_id, lead.id, base_url)

    placeholders = {
        "{lead_name}": lead.name or "",
        "{agent_name}": (agent.full_name if agent else "") or "",
        "{agent_phone}": (agent.phone if agent else "") or "",
        "{agent_email}": (agent.email if agent else "") or "",
        "{form_link}": form_link,
    }

    subject = tpl.subject
    body = tpl.body
    for key, value in placeholders.items():
        subject = subject.replace(key, value)
        body = body.replace(key, value)

    return subject, body


def _build_form_link(db: Session, tenant_id: int, lead_id: int, base_url: str) -> str:
    """Create a FormInvitation and return its token URL.

    Falls back to the bare public URL on any error.
    """
    try:
        from gmail_lead_sync.preapproval.invitation_service import FormInvitationService
        from gmail_lead_sync.preapproval.models_preapproval import FormTemplate, FormVersion, IntentType

        form_version = (
            db.query(FormVersion)
            .join(FormTemplate, FormVersion.template_id == FormTemplate.id)
            .filter(
                FormTemplate.tenant_id == tenant_id,
                FormTemplate.intent_type == IntentType.BUY.value,
                FormVersion.is_active.is_(True),
            )
            .first()
        )
        if form_version is None:
            return f"{base_url}/public/buyer-qualification"

        raw_token, _ = FormInvitationService().create_invitation(
            db,
            tenant_id=tenant_id,
            lead_id=lead_id,
            form_version_id=form_version.id,
        )
        return f"{base_url}/public/buyer-qualification/{raw_token}"

    except Exception as exc:
        logger.warning(
            "Could not create form invitation for lead %s tenant %s: %s",
            lead_id, tenant_id, exc,
        )
        return f"{base_url}/public/buyer-qualification"

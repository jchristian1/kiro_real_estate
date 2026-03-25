"""
QualificationInviteService — specialized communications boundary for
qualification form invite sending.

Owns:
  - Active BUY FormVersion resolution
  - FormInvitation creation (raw token for URL)
  - Form URL construction
  - Template selection and rendering:
      1. AgentTemplate (brace-style) via TemplateRenderService — preferred
      2. MessageTemplate (double-brace) via TemplateRenderEngine — qualification fallback
  - Email delivery via EmailDeliveryService

Does NOT own:
  - Lead state mutation (lead.agent_current_state) — caller's responsibility
  - LeadInteraction recording — caller's responsibility
  - Activity/lifecycle emission — caller's responsibility
  - Pipeline rule evaluation
  - Scoring or form submission handling

Callers:
  - gmail_lead_sync/preapproval/handlers.py::on_buyer_lead_email_received
    (which retains state mutation, interaction logging, and activity emission)

Rendering boundary:
  - TemplateRenderService owns generic brace-style rendering (AdminTemplate,
    AgentTemplate). QualificationInviteService uses it for the AgentTemplate path.
  - TemplateRenderEngine is qualification-owned and handles MessageTemplateVersion
    double-brace syntax. QualificationInviteService uses it as an explicit
    qualification-scoped fallback when no AgentTemplate is configured.
  - This boundary is intentional and explicit — TemplateRenderEngine does NOT
    leak into unrelated code paths.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class InviteResult:
    """Result of a qualification invite send attempt.

    Attributes:
        sent:           True if the email was successfully delivered.
        invitation_id:  ID of the created FormInvitation (always set when a
                        form version exists, even if delivery failed).
        form_version_id: ID of the FormVersion used.
        rendered_subject: The rendered email subject (for LeadInteraction logging).
        skipped:        True if no active form version exists for the tenant.
    """
    sent: bool
    invitation_id: Optional[int] = None
    form_version_id: Optional[int] = None
    rendered_subject: Optional[str] = None
    skipped: bool = False


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class QualificationInviteService:
    """Sends a qualification form invite email for a given lead and tenant.

    Resolves the active form version, creates a FormInvitation, renders the
    invite email (AgentTemplate preferred, MessageTemplate fallback), and
    delivers via EmailDeliveryService.

    Returns an InviteResult so the caller can handle state mutation,
    interaction logging, and activity emission at the correct boundary.
    """

    def send_invite(
        self,
        db: Session,
        tenant_id: int,
        lead_id: int,
        parsed_metadata: dict,
    ) -> InviteResult:
        """Create a FormInvitation and send the qualification form email.

        Args:
            db:              Active SQLAlchemy session.
            tenant_id:       Company ID for the tenant.
            lead_id:         Lead to invite.
            parsed_metadata: Extra context passed to MessageTemplate rendering.

        Returns:
            InviteResult with sent status, invitation_id, and rendered_subject.
        """
        from gmail_lead_sync.models import Lead
        from gmail_lead_sync.preapproval.invitation_service import FormInvitationService
        from gmail_lead_sync.preapproval.models_preapproval import (
            FormTemplate,
            FormVersion,
            IntentType,
            MessageTemplate,
            MessageTemplateKey,
            MessageTemplateVersion,
        )

        # 1. Resolve active FormVersion
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
            logger.warning(
                "qualification_invite: no active BUY form for tenant %d (lead_id=%d) — skipping",
                tenant_id, lead_id,
            )
            return InviteResult(sent=False, skipped=True)

        # 2. Create FormInvitation
        invitation_svc = FormInvitationService()
        raw_token, invitation = invitation_svc.create_invitation(
            db,
            tenant_id=tenant_id,
            lead_id=lead_id,
            form_version_id=form_version.id,
        )

        # 3. Build form URL
        form_url = self._build_form_url(raw_token)

        # 4. Load lead + tenant context for rendering
        lead: Lead = db.get(Lead, lead_id)
        if lead is None:
            logger.error(
                "qualification_invite: lead %d not found — cannot render invite",
                lead_id,
            )
            return InviteResult(
                sent=False,
                invitation_id=invitation.id,
                form_version_id=form_version.id,
            )

        first_name = lead.name.split()[0] if lead.name else ""
        tenant_name = self._resolve_tenant_name(db, tenant_id)

        # 5. Render email — AgentTemplate preferred, MessageTemplate fallback
        rendered = self._render_invite_email(
            db=db,
            tenant_id=tenant_id,
            lead=lead,
            first_name=first_name,
            tenant_name=tenant_name,
            form_url=form_url,
            form_version=form_version,
            parsed_metadata=parsed_metadata,
        )
        if rendered is None:
            # No template configured — caller should log the error interaction
            return InviteResult(
                sent=False,
                invitation_id=invitation.id,
                form_version_id=form_version.id,
                rendered_subject=None,
            )

        rendered_subject, rendered_body = rendered

        # 6. Deliver via EmailDeliveryService
        from api.communications.email_delivery import EmailDeliveryService
        delivery = EmailDeliveryService()
        email_sent = delivery.send(
            db, tenant_id, lead.source_email, rendered_subject, rendered_body
        )
        if not email_sent:
            logger.error(
                "qualification_invite: delivery failed for tenant %d lead %d",
                tenant_id, lead_id,
            )

        # 7. Mark invitation sent_at
        invitation.sent_at = datetime.utcnow()
        db.commit()

        return InviteResult(
            sent=email_sent,
            invitation_id=invitation.id,
            form_version_id=form_version.id,
            rendered_subject=rendered_subject,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_form_url(raw_token: str) -> str:
        base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
        return f"{base}/public/buyer-qualification/{raw_token}"

    @staticmethod
    def _resolve_tenant_name(db: Session, tenant_id: int) -> str:
        from sqlalchemy import text as _text
        row = db.execute(
            _text("SELECT name FROM companies WHERE id = :tid"),
            {"tid": tenant_id},
        ).fetchone()
        return row[0] if row else ""

    def _render_invite_email(
        self,
        db: Session,
        tenant_id: int,
        lead,
        first_name: str,
        tenant_name: str,
        form_url: str,
        form_version,
        parsed_metadata: dict,
    ) -> Optional[tuple[str, str]]:
        """Render the invite email subject and body.

        Priority:
        1. AgentTemplate (brace-style) via TemplateRenderService.
        2. MessageTemplate (double-brace) via TemplateRenderEngine — qualification fallback.
        3. None if neither is configured.
        """
        from gmail_lead_sync.agent_models import AgentUser

        # Resolve agent context once for both rendering paths
        agent = db.query(AgentUser).filter(AgentUser.company_id == tenant_id).first()

        # Path 1: AgentTemplate via TemplateRenderService (brace-style)
        from api.communications.template_render import TemplateRenderService
        renderer = TemplateRenderService()
        agent_rendered = renderer.render_agent_template(
            db, tenant_id, "INITIAL_INVITE",
            {
                "lead_name": lead.name or first_name,
                "agent_name": (agent.full_name if agent else tenant_name) or "",
                "agent_phone": (agent.phone if agent else "") or "",
                "agent_email": (agent.email if agent else "") or "",
                "form_link": form_url,
            },
        )
        if agent_rendered is not None:
            return agent_rendered

        # Path 2: MessageTemplate via TemplateRenderEngine (qualification-scoped fallback)
        from gmail_lead_sync.preapproval.models_preapproval import (
            IntentType,
            MessageTemplate,
            MessageTemplateKey,
            MessageTemplateVersion,
        )
        from gmail_lead_sync.preapproval.template_engine import TemplateRenderEngine

        msg_version = (
            db.query(MessageTemplateVersion)
            .join(MessageTemplate, MessageTemplateVersion.template_id == MessageTemplate.id)
            .filter(
                MessageTemplate.tenant_id == tenant_id,
                MessageTemplate.intent_type == IntentType.BUY.value,
                MessageTemplate.key == MessageTemplateKey.INITIAL_INVITE_EMAIL.value,
                MessageTemplateVersion.is_active.is_(True),
            )
            .first()
        )
        if msg_version is None:
            logger.error(
                "qualification_invite: no active INITIAL_INVITE_EMAIL template "
                "for tenant %d — cannot render invite",
                tenant_id,
            )
            return None

        engine = TemplateRenderEngine()
        rendered_obj = engine.render(
            msg_version,
            {
                "lead.first_name": first_name,
                "lead.email": lead.source_email,
                "form.link": form_url,
                "tenant.name": tenant_name,
                **parsed_metadata,
            },
        )
        return rendered_obj.subject, rendered_obj.body

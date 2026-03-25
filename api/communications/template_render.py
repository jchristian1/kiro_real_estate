"""
TemplateRenderService — single boundary for brace-style template rendering.

Owns:
  - AdminTemplate rendering ({placeholder} syntax, from api/repositories)
  - AgentTemplate rendering ({placeholder} syntax, from gmail_lead_sync.agent_models)

Does NOT own:
  - MessageTemplate / double-brace rendering (→ TemplateRenderEngine in preapproval)
  - Email delivery (→ EmailDeliveryService)
  - Qualification invite creation (→ QualificationInviteService / handlers)
  - Pipeline rule evaluation

All callers that need to render AdminTemplate or AgentTemplate content
must call TemplateRenderService — not inline the placeholder logic themselves.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Brace-style placeholders shared by both template types.
_PLACEHOLDER_KEYS = (
    "{lead_name}",
    "{agent_name}",
    "{agent_phone}",
    "{agent_email}",
    "{form_link}",
)


def _apply_placeholders(subject: str, body: str, values: dict[str, str]) -> tuple[str, str]:
    """Replace every {key} token in subject/body with its value."""
    for key in _PLACEHOLDER_KEYS:
        v = values.get(key, "")
        subject = subject.replace(key, v)
        body = body.replace(key, v)
    return subject, body


class TemplateRenderService:
    """Renders AdminTemplate and AgentTemplate content with lead/agent placeholders."""

    # ------------------------------------------------------------------
    # AdminTemplate rendering
    # ------------------------------------------------------------------

    def render_admin_template(
        self,
        db: Session,
        template_id: int,
        lead,
        tenant_id: int,
    ) -> tuple[str, str]:
        """Render an AdminTemplate for the given lead and tenant.

        Handles {form_link} by delegating to the qualification module's public
        interface (get_or_create_form_link). This service does not create
        qualification invitations/tokens directly.

        Returns:
            (subject, body) tuple with all placeholders substituted.

        Raises:
            ValueError: if the AdminTemplate does not exist.
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

        values = {
            "{lead_name}": lead.name or "",
            "{agent_name}": (agent.full_name if agent else "") or "",
            "{agent_phone}": (agent.phone if agent else "") or "",
            "{agent_email}": (agent.email if agent else "") or "",
            "{form_link}": form_link,
        }
        return _apply_placeholders(tpl.subject, tpl.body, values)

    # ------------------------------------------------------------------
    # AgentTemplate rendering
    # ------------------------------------------------------------------

    def render_agent_template(
        self,
        db: Session,
        tenant_id: int,
        template_type: str,
        context: dict,
    ) -> Optional[tuple[str, str]]:
        """Resolve and render an AgentTemplate for the given tenant and type.

        Args:
            db:            Active SQLAlchemy session.
            tenant_id:     Company ID used to look up the AgentUser and template.
            template_type: Template type key (e.g. "INITIAL_INVITE").
            context:       Dict with keys: lead_name, agent_name, agent_phone,
                           agent_email, form_link.

        Returns:
            (subject, body) with placeholders substituted, or None if no active
            AgentTemplate exists for this tenant/type.
        """
        try:
            from gmail_lead_sync.agent_models import AgentTemplate, AgentUser

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

            values = {
                "{lead_name}": context.get("lead_name", ""),
                "{agent_name}": context.get("agent_name", ""),
                "{agent_phone}": context.get("agent_phone", ""),
                "{agent_email}": context.get("agent_email", ""),
                "{form_link}": context.get("form_link", ""),
            }
            return _apply_placeholders(row.subject, row.body, values)

        except Exception as exc:
            logger.warning(
                "template_render: could not render AgentTemplate "
                "tenant=%d type=%s: %s",
                tenant_id, template_type, exc,
            )
            return None

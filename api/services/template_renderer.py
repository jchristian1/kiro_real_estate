"""
Template renderer service.

Substitutes supported placeholders in email templates and enforces
subject safety (no newline characters).

Supported placeholders:
  {lead_name}    — lead.name
  {agent_name}   — agent_user.full_name
  {agent_phone}  — agent_user.phone
  {agent_email}  — agent_user.email
  {form_link}    — https://app.example.com/form/{lead.id}

Requirements: 14.5, 14.6, 14.7
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from gmail_lead_sync.agent_models import AgentTemplate, AgentUser
    from gmail_lead_sync.models import Lead

# ---------------------------------------------------------------------------
# Supported placeholder keys (without braces)
# ---------------------------------------------------------------------------
SUPPORTED_PLACEHOLDERS = {
    "lead_name",
    "agent_name",
    "agent_phone",
    "agent_email",
    "form_link",
}


def render_template_str(subject: str, body: str, context: dict) -> dict:
    """
    Substitute placeholders in *subject* and *body* using a plain context dict.

    Keys in *context* must match placeholder names without braces, e.g.
    ``{"lead_name": "Alex", "agent_name": "Sarah", ...}``.

    After substitution the subject has all newline characters stripped
    (Requirement 14.7).  The body is returned as-is (newlines preserved).

    Args:
        subject: Raw template subject string.
        body:    Raw template body string.
        context: Mapping of placeholder name → replacement value.

    Returns:
        ``{"subject": str, "body": str}``
    """
    for key, value in context.items():
        placeholder = "{" + key + "}"
        subject = subject.replace(placeholder, value)
        body = body.replace(placeholder, value)

    # Requirement 14.7 — strip ALL newline characters from subject only
    subject = subject.replace("\n", "").replace("\r", "")

    return {"subject": subject, "body": body}


def render_template(
    template: "AgentTemplate",
    lead: "Lead",
    agent_user_id: int,
    db: Session,
) -> dict:
    """
    Render an ``AgentTemplate`` by substituting all supported placeholders.

    Looks up the ``AgentUser`` identified by *agent_user_id* to resolve
    agent-specific placeholders.  Missing / ``None`` values are replaced
    with an empty string so that no unresolved ``{...}`` tokens remain for
    the supported placeholder set (Requirement 14.6).

    Args:
        template:      An ``AgentTemplate`` ORM object with ``.subject`` and
                       ``.body`` attributes.
        lead:          A ``Lead`` ORM object.
        agent_user_id: Integer PK of the ``AgentUser`` to look up.
        db:            Active SQLAlchemy ``Session``.

    Returns:
        ``{"subject": str, "body": str}`` with all placeholders substituted
        and the subject stripped of newline characters.
    """
    # Lazy import to avoid circular dependencies at module load time
    from gmail_lead_sync.agent_models import AgentUser  # noqa: PLC0415

    agent_user: AgentUser | None = db.get(AgentUser, agent_user_id)

    # Build form_link from lead id
    form_link = (
        f"https://app.example.com/form/{lead.id}"
        if getattr(lead, "id", None) is not None
        else ""
    )

    context = {
        "lead_name": lead.name or "" if lead.name is not None else "",
        "agent_name": (agent_user.full_name or "") if agent_user else "",
        "agent_phone": (agent_user.phone or "") if agent_user else "",
        "agent_email": (agent_user.email or "") if agent_user else "",
        "form_link": form_link,
    }

    return render_template_str(template.subject, template.body, context)

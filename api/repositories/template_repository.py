"""
Template repository — all SQLAlchemy queries for AgentTemplate and
BuyerAutomationConfig domains.

All methods are scoped to agent_user_id.

Requirements: 7.1, 7.2
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from gmail_lead_sync.agent_models import AgentPreferences, AgentTemplate, BuyerAutomationConfig


# ---------------------------------------------------------------------------
# Data transfer objects (no FastAPI imports — framework-agnostic)
# ---------------------------------------------------------------------------


class TemplateCreate(BaseModel):
    """Fields required to create a new AgentTemplate."""

    template_type: str
    name: str
    subject: str
    body: str
    tone: str = "PROFESSIONAL"
    is_active: bool = False


class TemplateUpdate(BaseModel):
    """Fields that may be updated on an existing AgentTemplate."""

    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    tone: Optional[str] = None


class AutomationConfigUpdate(BaseModel):
    """Fields that may be updated on a BuyerAutomationConfig."""

    hot_threshold: Optional[int] = None
    warm_threshold: Optional[int] = None
    enable_tour_question: Optional[bool] = None
    weight_timeline: Optional[int] = None
    weight_preapproval: Optional[int] = None
    weight_phone_provided: Optional[int] = None
    weight_tour_interest: Optional[int] = None
    weight_budget_match: Optional[int] = None
    sla_minutes_hot: Optional[int] = None


# ---------------------------------------------------------------------------
# Template Repository
# ---------------------------------------------------------------------------


class TemplateRepository:
    """Data-access layer for AgentTemplate records.

    All methods are scoped to ``agent_user_id``.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_agent(self, agent_id: int) -> list[AgentTemplate]:
        """Return all templates for *agent_id* ordered by type then created_at."""
        return (
            self._db.query(AgentTemplate)
            .filter(AgentTemplate.agent_user_id == agent_id)
            .order_by(AgentTemplate.template_type, AgentTemplate.created_at)
            .all()
        )

    def get_by_id(self, template_id: int, agent_id: int) -> Optional[AgentTemplate]:
        """Return the template only if it belongs to *agent_id*."""
        return (
            self._db.query(AgentTemplate)
            .filter(
                AgentTemplate.id == template_id,
                AgentTemplate.agent_user_id == agent_id,
            )
            .first()
        )

    def get_active_for_type(
        self, agent_id: int, template_type: str
    ) -> Optional[AgentTemplate]:
        """Return the active template for a given type and agent, or ``None``."""
        return (
            self._db.query(AgentTemplate)
            .filter(
                AgentTemplate.agent_user_id == agent_id,
                AgentTemplate.template_type == template_type,
                AgentTemplate.is_active == True,  # noqa: E712
            )
            .first()
        )

    def deactivate_type(self, agent_id: int, template_type: str) -> None:
        """Set is_active=False for all templates of *template_type* for *agent_id*."""
        self._db.query(AgentTemplate).filter(
            AgentTemplate.agent_user_id == agent_id,
            AgentTemplate.template_type == template_type,
            AgentTemplate.is_active == True,  # noqa: E712
        ).update({"is_active": False})

    def create(self, agent_id: int, data: TemplateCreate) -> AgentTemplate:
        """Create and persist a new template scoped to *agent_id*."""
        now = datetime.utcnow()
        tmpl = AgentTemplate(
            agent_user_id=agent_id,
            name=data.name,
            template_type=data.template_type,
            subject=data.subject,
            body=data.body,
            tone=data.tone,
            is_active=data.is_active,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._db.add(tmpl)
        self._db.commit()
        self._db.refresh(tmpl)
        return tmpl

    def update(
        self, template_id: int, agent_id: int, data: TemplateUpdate
    ) -> Optional[AgentTemplate]:
        """Update a template after verifying ownership.

        Returns the updated template, or ``None`` if not found / wrong agent.
        """
        tmpl = self.get_by_id(template_id, agent_id)
        if tmpl is None:
            return None

        now = datetime.utcnow()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(tmpl, field, value)
        tmpl.version += 1
        tmpl.updated_at = now

        self._db.commit()
        self._db.refresh(tmpl)
        return tmpl

    def activate(self, template_id: int, agent_id: int) -> Optional[AgentTemplate]:
        """Set *template_id* as active for its type (deactivates others first).

        Returns the activated template, or ``None`` if not found / wrong agent.
        """
        tmpl = self.get_by_id(template_id, agent_id)
        if tmpl is None:
            return None

        self.deactivate_type(agent_id, tmpl.template_type)
        tmpl.is_active = True
        self._db.commit()
        return tmpl

    def delete(self, template_id: int, agent_id: int) -> Optional[AgentTemplate]:
        """Delete a template after verifying ownership.

        Returns the deleted template (for post-delete logic), or ``None``.
        """
        tmpl = self.get_by_id(template_id, agent_id)
        if tmpl is None:
            return None

        self._db.delete(tmpl)
        self._db.commit()
        return tmpl

    def delete_by_type(self, agent_id: int, template_type: str) -> None:
        """Delete all templates of *template_type* for *agent_id*."""
        self._db.query(AgentTemplate).filter(
            AgentTemplate.agent_user_id == agent_id,
            AgentTemplate.template_type == template_type,
        ).delete()
        self._db.commit()

    def get_most_recent_for_type(
        self, agent_id: int, template_type: str
    ) -> Optional[AgentTemplate]:
        """Return the most recently created template for a type, or ``None``."""
        return (
            self._db.query(AgentTemplate)
            .filter(
                AgentTemplate.agent_user_id == agent_id,
                AgentTemplate.template_type == template_type,
            )
            .order_by(AgentTemplate.created_at.desc())
            .first()
        )


# ---------------------------------------------------------------------------
# Automation Config Repository
# ---------------------------------------------------------------------------


class AutomationConfigRepository:
    """Data-access layer for BuyerAutomationConfig records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, config_id: int) -> Optional[BuyerAutomationConfig]:
        """Return the config with the given primary key, or ``None``."""
        return (
            self._db.query(BuyerAutomationConfig)
            .filter(BuyerAutomationConfig.id == config_id)
            .first()
        )

    def get_for_agent_via_prefs(
        self, agent_id: int
    ) -> tuple[Optional[AgentPreferences], Optional[BuyerAutomationConfig]]:
        """Return (prefs, config) for *agent_id*.

        Either value may be ``None`` if not yet created.
        """
        prefs: Optional[AgentPreferences] = (
            self._db.query(AgentPreferences)
            .filter(AgentPreferences.agent_user_id == agent_id)
            .first()
        )
        config: Optional[BuyerAutomationConfig] = None
        if prefs and prefs.buyer_automation_config_id:
            config = self.get_by_id(prefs.buyer_automation_config_id)
        return prefs, config

    def upsert_for_agent(
        self,
        agent_id: int,
        data: AutomationConfigUpdate,
        platform_defaults: dict,
    ) -> tuple[AgentPreferences, BuyerAutomationConfig]:
        """Create or update the BuyerAutomationConfig for *agent_id*.

        Also syncs relevant fields onto AgentPreferences.
        Returns (prefs, config).
        """
        now = datetime.utcnow()

        # Load or create AgentPreferences
        prefs: Optional[AgentPreferences] = (
            self._db.query(AgentPreferences)
            .filter(AgentPreferences.agent_user_id == agent_id)
            .first()
        )
        if prefs is None:
            prefs = AgentPreferences(agent_user_id=agent_id, created_at=now)
            self._db.add(prefs)
            self._db.flush()

        # Load existing config if linked
        config: Optional[BuyerAutomationConfig] = None
        if prefs.buyer_automation_config_id:
            config = self.get_by_id(prefs.buyer_automation_config_id)

        if config is None:
            config = BuyerAutomationConfig(
                agent_user_id=agent_id,
                name=f"Agent {agent_id} Config",
                is_platform_default=False,
                hot_threshold=prefs.hot_threshold,
                warm_threshold=prefs.warm_threshold,
                weight_timeline=platform_defaults["weight_timeline"],
                weight_preapproval=platform_defaults["weight_preapproval"],
                weight_phone_provided=platform_defaults["weight_phone_provided"],
                weight_tour_interest=platform_defaults["weight_tour_interest"],
                weight_budget_match=platform_defaults["weight_budget_match"],
                enable_tour_question=prefs.enable_tour_question,
                created_at=now,
            )
            self._db.add(config)
            self._db.flush()
            prefs.buyer_automation_config_id = config.id

        # Apply updates to config
        config_fields = {
            "hot_threshold", "warm_threshold", "enable_tour_question",
            "weight_timeline", "weight_preapproval", "weight_phone_provided",
            "weight_tour_interest", "weight_budget_match",
        }
        for field, value in data.model_dump(exclude_unset=True).items():
            if field in config_fields and value is not None:
                setattr(config, field, value)
        config.updated_at = now

        # Sync relevant fields onto prefs
        if data.sla_minutes_hot is not None:
            prefs.sla_minutes_hot = data.sla_minutes_hot
        if data.enable_tour_question is not None:
            prefs.enable_tour_question = data.enable_tour_question
        if data.hot_threshold is not None:
            prefs.hot_threshold = data.hot_threshold
        if data.warm_threshold is not None:
            prefs.warm_threshold = data.warm_threshold
        prefs.updated_at = now

        self._db.commit()
        self._db.refresh(config)
        return prefs, config


# ---------------------------------------------------------------------------
# Admin Template Repository (for the admin_templates.py router)
# ---------------------------------------------------------------------------


class AdminTemplateRepository:
    """Data-access layer for the admin-facing Template and TemplateVersion records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, template_id: int):
        """Return the Template with the given primary key, or None."""
        from gmail_lead_sync.models import Template
        return self._db.query(Template).filter(Template.id == template_id).first()

    def get_by_name(self, name: str):
        """Return the Template with the given name, or None."""
        from gmail_lead_sync.models import Template
        return self._db.query(Template).filter(Template.name == name).first()

    def get_by_name_excluding(self, name: str, exclude_id: int):
        """Return a Template with *name* that is NOT *exclude_id*, or None."""
        from gmail_lead_sync.models import Template
        return (
            self._db.query(Template)
            .filter(Template.name == name, Template.id != exclude_id)
            .first()
        )

    def list_all(self) -> list:
        """Return all Templates ordered by created_at desc."""
        from gmail_lead_sync.models import Template
        return self._db.query(Template).order_by(Template.created_at.desc()).all()

    def create(self, name: str, subject: str, body: str):
        """Create and persist a new Template."""
        from gmail_lead_sync.models import Template
        template = Template(name=name, subject=subject, body=body)
        self._db.add(template)
        self._db.commit()
        self._db.refresh(template)
        return template

    def update(self, template_id: int, name=None, subject=None, body=None):
        """Update a Template. Returns the updated record, or None if not found."""
        template = self.get_by_id(template_id)
        if template is None:
            return None
        if name is not None:
            template.name = name
        if subject is not None:
            template.subject = subject
        if body is not None:
            template.body = body
        self._db.commit()
        self._db.refresh(template)
        return template

    def delete(self, template_id: int):
        """Delete a Template. Returns the deleted record, or None if not found."""
        template = self.get_by_id(template_id)
        if template is None:
            return None
        self._db.delete(template)
        self._db.commit()
        return template

    # TemplateVersion methods

    def get_latest_version(self, template_id: int):
        """Return the latest TemplateVersion for *template_id*, or None."""
        from api.models.web_ui_models import TemplateVersion
        return (
            self._db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.version.desc())
            .first()
        )

    def list_versions(self, template_id: int) -> list:
        """Return all TemplateVersion records for *template_id* ordered by version desc."""
        from api.models.web_ui_models import TemplateVersion
        return (
            self._db.query(TemplateVersion)
            .filter(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.version.desc())
            .all()
        )

    def get_version_by_number(self, template_id: int, version: int):
        """Return the TemplateVersion for *template_id* at *version*, or None."""
        from api.models.web_ui_models import TemplateVersion
        return (
            self._db.query(TemplateVersion)
            .filter(
                TemplateVersion.template_id == template_id,
                TemplateVersion.version == version,
            )
            .first()
        )

    def create_version(self, template, user_id: int) -> int:
        """Create a new TemplateVersion for *template*. Returns the new version number."""
        from api.models.web_ui_models import TemplateVersion
        latest = self.get_latest_version(template.id)
        new_version = (latest.version + 1) if latest else 1
        version_record = TemplateVersion(
            template_id=template.id,
            version=new_version,
            name=template.name,
            subject=template.subject,
            body=template.body,
            created_by=user_id,
        )
        self._db.add(version_record)
        self._db.commit()
        return new_version

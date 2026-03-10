"""
SQLAlchemy models for the Agent-Facing Web Application (agent-app).

Defines all new tables required for agent authentication, preferences,
automation configuration, email templates, and lead event auditing.

Also patches the existing Lead model with new agent-app columns.

Requirements: 1.1, 2.6, 7.1, 13.7, 20.1
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from gmail_lead_sync.models import Base, Lead


# ---------------------------------------------------------------------------
# AgentUser
# ---------------------------------------------------------------------------

class AgentUser(Base):
    """
    Agent-specific login accounts (separate from admin `users` table).

    Requirements: 1.1, 2.1
    """
    __tablename__ = "agent_users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    timezone = Column(String(100), nullable=False, default="UTC")
    service_area = Column(Text, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    credentials_id = Column(Integer, ForeignKey("credentials.id"), nullable=True)
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    onboarding_step = Column(Integer, nullable=False, default=0)
    role = Column(String(50), nullable=False, default="agent")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship(
        "AgentSession", back_populates="agent_user", cascade="all, delete-orphan"
    )
    preferences = relationship(
        "AgentPreferences",
        back_populates="agent_user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    buyer_automation_configs = relationship(
        "BuyerAutomationConfig", back_populates="agent_user"
    )
    templates = relationship(
        "AgentTemplate", back_populates="agent_user", cascade="all, delete-orphan"
    )
    lead_events = relationship("LeadEvent", back_populates="agent_user")
    leads = relationship(
        "Lead",
        back_populates="agent_user",
        foreign_keys="[Lead.agent_user_id]",
    )


# ---------------------------------------------------------------------------
# AgentSession
# ---------------------------------------------------------------------------

class AgentSession(Base):
    """
    Agent-specific session management using 64-byte secure random tokens.

    Requirements: 2.6
    """
    __tablename__ = "agent_sessions"
    __table_args__ = (
        Index("ix_agent_sessions_agent_user_id", "agent_user_id"),
        Index("ix_agent_sessions_expires_at", "expires_at"),
    )

    # 64-byte token stored as 128-char hex string
    id = Column(String(128), primary_key=True)
    agent_user_id = Column(Integer, ForeignKey("agent_users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    agent_user = relationship("AgentUser", back_populates="sessions")


# ---------------------------------------------------------------------------
# AgentPreferences
# ---------------------------------------------------------------------------

class AgentPreferences(Base):
    """
    Per-agent automation and notification preferences.

    Requirements: 7.1
    """
    __tablename__ = "agent_preferences"

    id = Column(Integer, primary_key=True)
    agent_user_id = Column(
        Integer, ForeignKey("agent_users.id"), nullable=False, unique=True
    )
    hot_threshold = Column(Integer, nullable=False, default=80)
    warm_threshold = Column(Integer, nullable=False, default=50)
    sla_minutes_hot = Column(Integer, nullable=False, default=5)
    quiet_hours_start = Column(Time, nullable=True)
    quiet_hours_end = Column(Time, nullable=True)
    working_days = Column(String(20), nullable=False, default="MON-SAT")
    enable_tour_question = Column(Boolean, nullable=False, default=True)
    # JSON array of lead_source IDs
    enabled_lead_source_ids = Column(Text, nullable=True)
    buyer_automation_config_id = Column(
        Integer, ForeignKey("buyer_automation_configs.id"), nullable=True
    )
    watcher_enabled = Column(Boolean, nullable=False, default=True)
    watcher_admin_override = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    agent_user = relationship("AgentUser", back_populates="preferences")
    buyer_automation_config = relationship(
        "BuyerAutomationConfig", foreign_keys=[buyer_automation_config_id]
    )


# ---------------------------------------------------------------------------
# BuyerAutomationConfig
# ---------------------------------------------------------------------------

class BuyerAutomationConfig(Base):
    """
    Buyer qualification template configuration (agent-scoped or platform default).

    NULL agent_user_id indicates a platform-wide default config.

    Requirements: 7.1, 13.1
    """
    __tablename__ = "buyer_automation_configs"

    id = Column(Integer, primary_key=True)
    # NULL = platform default
    agent_user_id = Column(Integer, ForeignKey("agent_users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    is_platform_default = Column(Boolean, nullable=False, default=False)
    hot_threshold = Column(Integer, nullable=False, default=80)
    warm_threshold = Column(Integer, nullable=False, default=50)
    # Scoring weights (sum should equal 100)
    weight_timeline = Column(Integer, nullable=False, default=25)
    weight_preapproval = Column(Integer, nullable=False, default=30)
    weight_phone_provided = Column(Integer, nullable=False, default=15)
    weight_tour_interest = Column(Integer, nullable=False, default=20)
    weight_budget_match = Column(Integer, nullable=False, default=10)
    enable_tour_question = Column(Boolean, nullable=False, default=True)
    form_link_template = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    agent_user = relationship("AgentUser", back_populates="buyer_automation_configs")


# ---------------------------------------------------------------------------
# AgentTemplate
# ---------------------------------------------------------------------------

class AgentTemplate(Base):
    """
    Agent-scoped email template overrides (cloned from platform defaults).

    Each agent may have at most one active template per template_type.

    Requirements: 8.4, 14.1, 14.2
    """
    __tablename__ = "agent_templates"
    __table_args__ = (
        UniqueConstraint(
            "agent_user_id", "template_type", name="uq_agent_templates_user_type"
        ),
    )

    id = Column(Integer, primary_key=True)
    agent_user_id = Column(Integer, ForeignKey("agent_users.id"), nullable=False)
    template_type = Column(
        Enum(
            "INITIAL_INVITE",
            "POST_HOT",
            "POST_WARM",
            "POST_NURTURE",
            name="agent_template_type_enum",
        ),
        nullable=False,
    )
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    tone = Column(
        Enum(
            "PROFESSIONAL",
            "FRIENDLY",
            "SHORT",
            name="agent_template_tone_enum",
        ),
        nullable=False,
        default="PROFESSIONAL",
    )
    is_active = Column(Boolean, nullable=False, default=True)
    # Platform default template this was cloned from
    parent_template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    agent_user = relationship("AgentUser", back_populates="templates")
    parent_template = relationship("Template", foreign_keys=[parent_template_id])


# ---------------------------------------------------------------------------
# LeadEvent
# ---------------------------------------------------------------------------

class LeadEvent(Base):
    """
    Immutable event log for full lead timeline and transparency.

    Records are never updated or deleted — append-only audit trail.

    Requirements: 20.1, 20.2
    """
    __tablename__ = "lead_events"
    __table_args__ = (
        Index("ix_lead_events_lead_id_created_at", "lead_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    agent_user_id = Column(Integer, ForeignKey("agent_users.id"), nullable=True)
    event_type = Column(
        Enum(
            "EMAIL_RECEIVED",
            "LEAD_PARSED",
            "INVITE_CREATED",
            "INVITE_SENT",
            "FORM_SUBMITTED",
            "LEAD_SCORED",
            "POST_EMAIL_SENT",
            "AGENT_CONTACTED",
            "APPOINTMENT_SET",
            "LEAD_LOST",
            "LEAD_CLOSED",
            "NOTE_ADDED",
            "STATUS_CHANGED",
            "WATCHER_TOGGLED",
            name="lead_event_type_enum",
        ),
        nullable=False,
    )
    # JSON payload: score breakdown, email content, note text, state transition, etc.
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="lead_events")
    agent_user = relationship("AgentUser", back_populates="lead_events")


# ---------------------------------------------------------------------------
# Patch existing Lead model with agent-app columns
# ---------------------------------------------------------------------------
# Only add columns if not already present (idempotent import).

if not hasattr(Lead, "property_address"):
    Lead.property_address = Column(String(500), nullable=True)

if not hasattr(Lead, "listing_url"):
    Lead.listing_url = Column(String(1000), nullable=True)

if not hasattr(Lead, "score"):
    Lead.score = Column(Integer, nullable=True)

if not hasattr(Lead, "score_bucket"):
    Lead.score_bucket = Column(
        Enum("HOT", "WARM", "NURTURE", name="lead_score_bucket_enum"),
        nullable=True,
    )

if not hasattr(Lead, "score_breakdown"):
    Lead.score_breakdown = Column(Text, nullable=True)  # JSON

# The existing `current_state` column is String(50) from the preapproval migration.
# The agent-app uses the same column with a defined set of string values.
# We add `agent_current_state` as a separate Enum column to avoid conflicts.
if not hasattr(Lead, "agent_current_state"):
    Lead.agent_current_state = Column(
        "agent_current_state",
        Enum(
            "NEW",
            "INVITE_SENT",
            "FORM_SUBMITTED",
            "SCORED",
            "CONTACTED",
            "APPOINTMENT_SET",
            "LOST",
            "CLOSED",
            name="lead_agent_state_enum",
        ),
        nullable=True,
        default="NEW",
    )

if not hasattr(Lead, "agent_user_id"):
    Lead.agent_user_id = Column(
        Integer, ForeignKey("agent_users.id"), nullable=True
    )

if not hasattr(Lead, "company_id"):
    Lead.company_id = Column(
        Integer, ForeignKey("companies.id"), nullable=True
    )

if not hasattr(Lead, "lead_source_name"):
    Lead.lead_source_name = Column(String(100), nullable=True)

if not hasattr(Lead, "last_agent_action_at"):
    Lead.last_agent_action_at = Column(DateTime, nullable=True)

# Patch relationships onto Lead (idempotent)
if not hasattr(Lead, "agent_user"):
    Lead.agent_user = relationship(
        "AgentUser",
        back_populates="leads",
        foreign_keys="[Lead.agent_user_id]",
    )

if not hasattr(Lead, "lead_events"):
    Lead.lead_events = relationship("LeadEvent", back_populates="lead")

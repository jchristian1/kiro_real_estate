"""
SQLAlchemy models and enums for the Buyer Lead Qualification pipeline.

Defines all enums, the 14 new model classes, and patches the existing Lead
model with `current_state` / `current_state_updated_at` columns.

Requirements: 1.4, 2.1, 3.1, 19.1
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from gmail_lead_sync.models import Base, Lead


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IntentType(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"   # reserved
    RENT = "RENT"   # reserved


class LeadState(str, Enum):
    NEW_EMAIL_RECEIVED         = "NEW_EMAIL_RECEIVED"
    FORM_INVITE_CREATED        = "FORM_INVITE_CREATED"
    FORM_INVITE_SENT           = "FORM_INVITE_SENT"
    FORM_SUBMITTED             = "FORM_SUBMITTED"
    SCORED                     = "SCORED"
    POST_SUBMISSION_EMAIL_SENT = "POST_SUBMISSION_EMAIL_SENT"


class Bucket(str, Enum):
    HOT     = "HOT"
    WARM    = "WARM"
    NURTURE = "NURTURE"


class ActorType(str, Enum):
    SYSTEM = "system"
    ADMIN  = "admin"


class Channel(str, Enum):
    EMAIL = "email"
    SMS   = "sms"    # reserved
    VOICE = "voice"  # reserved
    WEB   = "web"


class MessageTemplateKey(str, Enum):
    INITIAL_INVITE_EMAIL  = "INITIAL_INVITE_EMAIL"
    POST_SUBMISSION_EMAIL = "POST_SUBMISSION_EMAIL"


# ---------------------------------------------------------------------------
# Patch existing Lead model with preapproval columns
# ---------------------------------------------------------------------------

# Only add the columns if they haven't been added yet (idempotent import).
if not hasattr(Lead, "current_state"):
    Lead.current_state = Column(String(50), nullable=True)

if not hasattr(Lead, "current_state_updated_at"):
    Lead.current_state_updated_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Form System
# ---------------------------------------------------------------------------

class FormTemplate(Base):
    """Named, tenant-scoped container for versioned buyer qualification forms."""

    __tablename__ = "form_templates"

    id          = Column(Integer, primary_key=True)
    tenant_id   = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    intent_type = Column(String(10), nullable=False, default="BUY")
    name        = Column(String(255), nullable=False)
    status      = Column(String(20), nullable=False, default="draft")  # draft|active|archived
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    versions = relationship("FormVersion", back_populates="template")


class FormVersion(Base):
    """Immutable snapshot of a form's questions and logic rules."""

    __tablename__ = "form_versions"

    id             = Column(Integer, primary_key=True)
    template_id    = Column(Integer, ForeignKey("form_templates.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    schema_json    = Column(Text, nullable=False)   # full question list snapshot
    created_at     = Column(DateTime, default=datetime.utcnow)
    published_at   = Column(DateTime, nullable=True)
    is_active      = Column(Boolean, default=False)

    template    = relationship("FormTemplate", back_populates="versions")
    questions   = relationship("FormQuestion", back_populates="form_version")
    logic_rules = relationship("FormLogicRule", back_populates="form_version")


class FormQuestion(Base):
    """A single question within a FormVersion."""

    __tablename__ = "form_questions"

    id              = Column(Integer, primary_key=True)
    form_version_id = Column(Integer, ForeignKey("form_versions.id"), nullable=False, index=True)
    question_key    = Column(String(100), nullable=False)
    type            = Column(String(30), nullable=False)    # single_choice|multi_select|free_text|phone|email
    label           = Column(String(500), nullable=False)
    required        = Column(Boolean, default=True)
    options_json    = Column(Text, nullable=True)           # JSON array of {value, label}
    order           = Column(Integer, nullable=False)
    validation_json = Column(Text, nullable=True)

    form_version = relationship("FormVersion", back_populates="questions")


class FormLogicRule(Base):
    """Conditional visibility rule within a FormVersion."""

    __tablename__ = "form_logic_rules"

    id              = Column(Integer, primary_key=True)
    form_version_id = Column(Integer, ForeignKey("form_versions.id"), nullable=False, index=True)
    rule_json       = Column(Text, nullable=False)
    # rule_json shape: {"if": {"question_key": "agent", "answer": "Yes"}, "then": {"hide": ["tour"]}}

    form_version = relationship("FormVersion", back_populates="logic_rules")


# ---------------------------------------------------------------------------
# Scoring System
# ---------------------------------------------------------------------------

class ScoringConfig(Base):
    """Named, tenant-scoped container for versioned scoring rule sets."""

    __tablename__ = "scoring_configs"

    id          = Column(Integer, primary_key=True)
    tenant_id   = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    intent_type = Column(String(10), nullable=False, default="BUY")
    name        = Column(String(255), nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    versions = relationship("ScoringVersion", back_populates="config")


class ScoringVersion(Base):
    """Immutable snapshot of scoring rules and bucket thresholds."""

    __tablename__ = "scoring_versions"

    id                = Column(Integer, primary_key=True)
    scoring_config_id = Column(Integer, ForeignKey("scoring_configs.id"), nullable=False, index=True)
    version_number    = Column(Integer, nullable=False)
    rules_json        = Column(Text, nullable=False)
    # rules_json: list of {question_key, answer_value, points, reason}
    thresholds_json   = Column(Text, nullable=False)
    # thresholds_json: {"HOT": 80, "WARM": 50}
    created_at        = Column(DateTime, default=datetime.utcnow)
    published_at      = Column(DateTime, nullable=True)
    is_active         = Column(Boolean, default=False)

    config = relationship("ScoringConfig", back_populates="versions")


# ---------------------------------------------------------------------------
# Invitations & Submissions
# ---------------------------------------------------------------------------

class FormInvitation(Base):
    """Single-use, expiring, tokenized invitation sent to a lead."""

    __tablename__ = "form_invitations"

    id              = Column(Integer, primary_key=True)
    tenant_id       = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    lead_id         = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    intent_type     = Column(String(10), nullable=False, default="BUY")
    form_version_id = Column(Integer, ForeignKey("form_versions.id"), nullable=False)
    sent_at         = Column(DateTime, nullable=True)
    channel         = Column(String(20), nullable=False, default="email")
    token_hash      = Column(String(64), nullable=False, unique=True, index=True)
    expires_at      = Column(DateTime, nullable=False)
    used_at         = Column(DateTime, nullable=True)


class FormSubmission(Base):
    """A lead's completed response to a FormVersion."""

    __tablename__ = "form_submissions"

    id                     = Column(Integer, primary_key=True)
    tenant_id              = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    lead_id                = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    intent_type            = Column(String(10), nullable=False, default="BUY")
    form_version_id        = Column(Integer, ForeignKey("form_versions.id"), nullable=False)
    scoring_version_id     = Column(Integer, ForeignKey("scoring_versions.id"), nullable=True)
    invitation_id          = Column(Integer, ForeignKey("form_invitations.id"), nullable=True)
    submitted_at           = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_agent             = Column(String(500), nullable=True)
    device_type            = Column(String(50), nullable=True)
    time_to_submit_seconds = Column(Integer, nullable=True)
    lead_source            = Column(String(255), nullable=True)
    property_address       = Column(String(500), nullable=True)
    listing_url            = Column(String(1000), nullable=True)
    repeat_inquiry_count   = Column(Integer, default=0)
    raw_payload_json       = Column(Text, nullable=True)

    answers = relationship("SubmissionAnswer", back_populates="submission")
    score   = relationship("SubmissionScore", uselist=False, back_populates="submission")


class SubmissionAnswer(Base):
    """A single answer within a FormSubmission."""

    __tablename__ = "submission_answers"

    id                = Column(Integer, primary_key=True)
    submission_id     = Column(Integer, ForeignKey("form_submissions.id"), nullable=False, index=True)
    question_key      = Column(String(100), nullable=False)
    answer_value_json = Column(Text, nullable=False)

    submission = relationship("FormSubmission", back_populates="answers")


class SubmissionScore(Base):
    """Computed score record for a FormSubmission."""

    __tablename__ = "submission_scores"
    __table_args__ = (UniqueConstraint("submission_id", name="uq_submission_scores_submission_id"),)

    id               = Column(Integer, primary_key=True)
    submission_id    = Column(Integer, ForeignKey("form_submissions.id"), nullable=False, unique=True)
    total_score      = Column(Integer, nullable=False)
    bucket           = Column(String(20), nullable=False)   # HOT|WARM|NURTURE
    breakdown_json   = Column(Text, nullable=False)
    explanation_text = Column(Text, nullable=False)

    submission = relationship("FormSubmission", back_populates="score")


# ---------------------------------------------------------------------------
# Message Templates
# ---------------------------------------------------------------------------

class MessageTemplate(Base):
    """Named, tenant-scoped container for versioned email templates."""

    __tablename__ = "message_templates"

    id          = Column(Integer, primary_key=True)
    tenant_id   = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    intent_type = Column(String(10), nullable=False, default="BUY")
    key         = Column(String(50), nullable=False)   # MessageTemplateKey
    created_at  = Column(DateTime, default=datetime.utcnow)

    versions = relationship("MessageTemplateVersion", back_populates="template")


class MessageTemplateVersion(Base):
    """Immutable snapshot of an email template's subject, body, and optional bucket variants."""

    __tablename__ = "message_template_versions"

    id               = Column(Integer, primary_key=True)
    template_id      = Column(Integer, ForeignKey("message_templates.id"), nullable=False, index=True)
    version_number   = Column(Integer, nullable=False)
    subject_template = Column(String(500), nullable=False)
    body_template    = Column(Text, nullable=False)
    variants_json    = Column(Text, nullable=True)
    # variants_json for POST_SUBMISSION_EMAIL:
    # {"HOT": {"subject": "...", "body": "..."}, "WARM": {...}, "NURTURE": {...}}
    created_at       = Column(DateTime, default=datetime.utcnow)
    published_at     = Column(DateTime, nullable=True)
    is_active        = Column(Boolean, default=False)

    template = relationship("MessageTemplate", back_populates="versions")


# ---------------------------------------------------------------------------
# Lead State Machine
# ---------------------------------------------------------------------------

class LeadStateTransition(Base):
    """Immutable event-log row recording a state change for a lead."""

    __tablename__ = "lead_state_transitions"
    __table_args__ = (
        Index("idx_lead_state_transitions_lead_occurred", "lead_id", "occurred_at"),
    )

    id            = Column(Integer, primary_key=True)
    tenant_id     = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    lead_id       = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    intent_type   = Column(String(10), nullable=False, default="BUY")
    from_state    = Column(String(50), nullable=True)   # null for initial transition
    to_state      = Column(String(50), nullable=False)
    occurred_at   = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    metadata_json = Column(Text, nullable=True)
    actor_type    = Column(String(20), nullable=False, default="system")
    actor_id      = Column(Integer, nullable=True)


class LeadInteraction(Base):
    """Immutable record of an inbound or outbound communication with a lead."""

    __tablename__ = "lead_interactions"

    id            = Column(Integer, primary_key=True)
    tenant_id     = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    lead_id       = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    intent_type   = Column(String(10), nullable=False, default="BUY")
    channel       = Column(String(20), nullable=False, default="email")
    direction     = Column(String(10), nullable=False)   # inbound|outbound
    occurred_at   = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    metadata_json = Column(Text, nullable=True)
    content_text  = Column(Text, nullable=True)

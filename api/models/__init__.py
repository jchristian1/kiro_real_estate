"""
Database models for the Gmail Lead Sync Web UI & API Layer.

This package exports all SQLAlchemy models including:
- Existing CLI models (Lead, LeadSource, Template, Credentials, ProcessingLog)
- New Web UI models (User, Session, AuditLog, TemplateVersion, RegexProfileVersion, Setting)
"""

from gmail_lead_sync.models import Base, Lead, LeadSource, Template, Credentials, ProcessingLog
from api.models.web_ui_models import (
    User,
    Session,
    AuditLog,
    TemplateVersion,
    RegexProfileVersion,
    Setting
)

__all__ = [
    # Base
    'Base',
    # Existing CLI models
    'Lead',
    'LeadSource',
    'Template',
    'Credentials',
    'ProcessingLog',
    # New Web UI models
    'User',
    'Session',
    'AuditLog',
    'TemplateVersion',
    'RegexProfileVersion',
    'Setting',
]

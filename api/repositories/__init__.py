"""
Repository layer for data access.

All database queries are encapsulated here, keeping routers and services
free of direct SQLAlchemy calls.
"""

from api.repositories.lead_repository import LeadRepository, LeadEventRepository
from api.repositories.agent_repository import AgentRepository, AgentSessionRepository
from api.repositories.credential_repository import CredentialRepository
from api.repositories.watcher_repository import WatcherRepository, AgentPreferencesRepository
from api.repositories.lead_source_repository import (
    LeadSourceRepository,
    RegexProfileVersionRepository,
    TemplateExistenceRepository,
)
from api.repositories.template_repository import (
    TemplateRepository,
    AutomationConfigRepository,
    AdminTemplateRepository,
)
from api.repositories.audit_repository import AuditRepository
from api.repositories.company_repository import CompanyRepository, CompanyCreate, CompanyUpdate
from api.repositories.settings_repository import SettingsRepository
from api.repositories.buyer_leads_repository import (
    FormTemplateRepository,
    FormVersionRepository,
    ScoringConfigRepository,
    ScoringVersionRepository,
    MessageTemplateRepository,
    FormInvitationRepository,
    BuyerLeadsQueryRepository,
)

__all__ = [
    "LeadRepository",
    "LeadEventRepository",
    "AgentRepository",
    "AgentSessionRepository",
    "CredentialRepository",
    "WatcherRepository",
    "AgentPreferencesRepository",
    "LeadSourceRepository",
    "RegexProfileVersionRepository",
    "TemplateExistenceRepository",
    "TemplateRepository",
    "AutomationConfigRepository",
    "AdminTemplateRepository",
    "AuditRepository",
    "CompanyRepository",
    "CompanyCreate",
    "CompanyUpdate",
    "SettingsRepository",
    "FormTemplateRepository",
    "FormVersionRepository",
    "ScoringConfigRepository",
    "ScoringVersionRepository",
    "MessageTemplateRepository",
    "FormInvitationRepository",
    "BuyerLeadsQueryRepository",
]

"""
Repository layer for data access.

All database queries are encapsulated here, keeping routers and services
free of direct SQLAlchemy calls.
"""

from api.repositories.lead_repository import LeadRepository
from api.repositories.agent_repository import AgentRepository
from api.repositories.credential_repository import CredentialRepository
from api.repositories.watcher_repository import WatcherRepository
from api.repositories.lead_source_repository import LeadSourceRepository

__all__ = [
    "LeadRepository",
    "AgentRepository",
    "CredentialRepository",
    "WatcherRepository",
    "LeadSourceRepository",
]

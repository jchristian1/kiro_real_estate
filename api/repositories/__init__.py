"""
Repository layer for data access.

All database queries are encapsulated here, keeping routers and services
free of direct SQLAlchemy calls.
"""

from api.repositories.lead_repository import LeadRepository

__all__ = ["LeadRepository"]

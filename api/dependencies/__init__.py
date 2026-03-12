"""
api/dependencies — reusable FastAPI Depends functions.

Exports:
- get_db              — database session dependency
- get_current_agent   — agent session authentication
- get_current_admin   — admin session authentication
- require_role        — role-enforcement dependency factory
- get_pagination      — pagination query-parameter dependency
- PaginationParams    — pagination dataclass

Requirements: 7.4
"""

from api.dependencies.db import get_db
from api.dependencies.auth import get_current_agent, get_current_admin, require_role
from api.dependencies.pagination import get_pagination, PaginationParams

__all__ = [
    "get_db",
    "get_current_agent",
    "get_current_admin",
    "require_role",
    "get_pagination",
    "PaginationParams",
]

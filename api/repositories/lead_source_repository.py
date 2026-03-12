"""
Lead source repository — all SQLAlchemy queries for the LeadSource domain.

Lead sources are platform-level entities (not tenant-scoped): they define
email parsing rules shared across the platform.

Requirements: 7.1, 7.2
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from gmail_lead_sync.models import LeadSource


# ---------------------------------------------------------------------------
# Data transfer objects (no FastAPI imports — framework-agnostic)
# ---------------------------------------------------------------------------


class LeadSourceCreate(BaseModel):
    """Fields required to create a new lead source."""

    sender_email: str
    identifier_snippet: str
    name_regex: str
    phone_regex: str
    template_id: Optional[int] = None
    auto_respond_enabled: bool = False


class LeadSourceUpdate(BaseModel):
    """Fields that may be updated on an existing lead source."""

    sender_email: Optional[str] = None
    identifier_snippet: Optional[str] = None
    name_regex: Optional[str] = None
    phone_regex: Optional[str] = None
    template_id: Optional[int] = None
    auto_respond_enabled: Optional[bool] = None


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class LeadSourceRepository:
    """Data-access layer for LeadSource records.

    Lead sources are platform-level (not tenant-scoped).  The caller is
    responsible for ensuring the requesting user has the appropriate role
    before invoking write methods.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, source_id: int) -> Optional[LeadSource]:
        """Return the lead source with the given primary key, or ``None``."""
        return (
            self._db.query(LeadSource)
            .filter(LeadSource.id == source_id)
            .first()
        )

    def list_all(self, *, skip: int = 0, limit: int = 50) -> list[LeadSource]:
        """Return a paginated list of all lead sources."""
        return (
            self._db.query(LeadSource)
            .order_by(LeadSource.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, data: LeadSourceCreate) -> LeadSource:
        """Create and persist a new lead source."""
        source = LeadSource(
            sender_email=data.sender_email,
            identifier_snippet=data.identifier_snippet,
            name_regex=data.name_regex,
            phone_regex=data.phone_regex,
            template_id=data.template_id,
            auto_respond_enabled=data.auto_respond_enabled,
        )
        self._db.add(source)
        self._db.commit()
        self._db.refresh(source)
        return source

    def update(self, source_id: int, data: LeadSourceUpdate) -> Optional[LeadSource]:
        """Update a lead source.

        Returns the updated record, or ``None`` if not found.
        """
        source = self.get_by_id(source_id)
        if source is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(source, field, value)

        self._db.commit()
        self._db.refresh(source)
        return source

    def delete(self, source_id: int) -> bool:
        """Delete a lead source by ID.

        Returns ``True`` if deleted, ``False`` if not found.
        """
        source = self.get_by_id(source_id)
        if source is None:
            return False

        self._db.delete(source)
        self._db.commit()
        return True

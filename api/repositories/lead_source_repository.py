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


# ---------------------------------------------------------------------------
# Regex Profile Version Repository
# ---------------------------------------------------------------------------


class RegexProfileVersionRepository:
    """Data-access layer for RegexProfileVersion records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_latest_for_source(self, lead_source_id: int):
        """Return the latest RegexProfileVersion for *lead_source_id*, or None."""
        from api.models.web_ui_models import RegexProfileVersion
        return (
            self._db.query(RegexProfileVersion)
            .filter(RegexProfileVersion.lead_source_id == lead_source_id)
            .order_by(RegexProfileVersion.version.desc())
            .first()
        )

    def list_for_source(self, lead_source_id: int) -> list:
        """Return all RegexProfileVersion records for *lead_source_id* ordered by version desc."""
        from api.models.web_ui_models import RegexProfileVersion
        return (
            self._db.query(RegexProfileVersion)
            .filter(RegexProfileVersion.lead_source_id == lead_source_id)
            .order_by(RegexProfileVersion.version.desc())
            .all()
        )

    def get_by_version(self, lead_source_id: int, version: int):
        """Return the RegexProfileVersion for *lead_source_id* at *version*, or None."""
        from api.models.web_ui_models import RegexProfileVersion
        return (
            self._db.query(RegexProfileVersion)
            .filter(
                RegexProfileVersion.lead_source_id == lead_source_id,
                RegexProfileVersion.version == version,
            )
            .first()
        )

    def create(self, lead_source, user_id: int) -> int:
        """Create a new version record for *lead_source*. Returns the new version number."""
        from api.models.web_ui_models import RegexProfileVersion
        latest = self.get_latest_for_source(lead_source.id)
        new_version = (latest.version + 1) if latest else 1
        version_record = RegexProfileVersion(
            lead_source_id=lead_source.id,
            version=new_version,
            name_regex=lead_source.name_regex,
            phone_regex=lead_source.phone_regex,
            identifier_snippet=lead_source.identifier_snippet,
            created_by=user_id,
        )
        self._db.add(version_record)
        self._db.commit()
        return new_version


class TemplateExistenceRepository:
    """Minimal repository for checking Template existence (used by lead source router)."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def exists(self, template_id: int) -> bool:
        """Return True if a Template with *template_id* exists."""
        from gmail_lead_sync.models import Template
        return (
            self._db.query(Template).filter(Template.id == template_id).first()
        ) is not None

"""
Credential repository — all SQLAlchemy queries for the Credentials domain.

Every method is scoped to the owning agent_id.  Plaintext credentials are
never accepted or returned — callers must pass pre-encrypted blobs and
receive encrypted blobs back.  Decryption is the responsibility of the
CredentialEncryption service layer.

Requirements: 6.4, 7.1, 7.2
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from gmail_lead_sync.models import Credentials


# ---------------------------------------------------------------------------
# Data transfer objects (no FastAPI imports — framework-agnostic)
# ---------------------------------------------------------------------------


class CredentialCreate(BaseModel):
    """Encrypted credential blobs required to create a Credentials record.

    Callers MUST encrypt values before passing them here.
    """

    email_encrypted: str
    app_password_encrypted: str
    display_name: Optional[str] = None
    phone: Optional[str] = None
    company_id: Optional[int] = None


class CredentialUpdate(BaseModel):
    """Encrypted credential blobs that may be updated.

    Only fields explicitly set will be written.
    """

    email_encrypted: Optional[str] = None
    app_password_encrypted: Optional[str] = None
    display_name: Optional[str] = None
    phone: Optional[str] = None
    company_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class CredentialRepository:
    """Data-access layer for Credentials records.

    All methods are scoped to ``agent_id`` — it is impossible to read or
    modify credentials belonging to a different agent through this class.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_agent_id(self, agent_id: str) -> Optional[Credentials]:
        """Return the credentials record for *agent_id*, or ``None``.

        The query always filters by ``agent_id`` so a caller cannot retrieve
        another agent's credentials by supplying a different ID.
        """
        return (
            self._db.query(Credentials)
            .filter(Credentials.agent_id == agent_id)
            .first()
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, data: CredentialCreate, agent_id: str) -> Credentials:
        """Create a credentials record scoped to *agent_id*.

        The ``agent_id`` is always taken from the caller-supplied argument,
        never from ``data``, to prevent privilege escalation.
        """
        cred = Credentials(
            agent_id=agent_id,
            email_encrypted=data.email_encrypted,
            app_password_encrypted=data.app_password_encrypted,
            display_name=data.display_name,
            phone=data.phone,
            company_id=data.company_id,
        )
        self._db.add(cred)
        self._db.commit()
        self._db.refresh(cred)
        return cred

    def update(self, agent_id: str, data: CredentialUpdate) -> Optional[Credentials]:
        """Update the credentials record for *agent_id*.

        Returns the updated record, or ``None`` if no credentials exist for
        this agent.  The ``agent_id`` filter is applied inside the query so
        no cross-tenant data is ever loaded.
        """
        cred = self.get_by_agent_id(agent_id)
        if cred is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(cred, field, value)

        self._db.commit()
        self._db.refresh(cred)
        return cred

    def delete(self, agent_id: str) -> bool:
        """Delete the credentials record for *agent_id*.

        Returns ``True`` if a record was deleted, ``False`` if none existed.
        The ``agent_id`` filter ensures only the owning agent's record is
        affected.
        """
        cred = self.get_by_agent_id(agent_id)
        if cred is None:
            return False

        self._db.delete(cred)
        self._db.commit()
        return True

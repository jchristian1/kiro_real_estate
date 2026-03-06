"""
FormInvitationService — generates and validates single-use, expiring form tokens.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from gmail_lead_sync.preapproval.models_preapproval import FormInvitation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TokenNotFoundError(Exception):
    """Raised when no FormInvitation matches the provided token hash."""


class TokenUsedError(Exception):
    """Raised when the FormInvitation has already been used (used_at is set)."""


class TokenExpiredError(Exception):
    """Raised when the FormInvitation has passed its expires_at timestamp."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

def _sha256_hex(raw_token: str) -> str:
    """Return the hex-encoded SHA-256 digest of *raw_token*."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


class FormInvitationService:
    """
    Generates and validates single-use, expiring form invitation tokens.

    Security properties:
    - Raw token is NEVER persisted (Req 3.2, 17.4).
    - Only the SHA-256 hash is stored in form_invitations.token_hash.
    - Tokens are 32-byte cryptographically random URL-safe strings (Req 3.1, 3.6).
    """

    def create_invitation(
        self,
        db: Session,
        tenant_id: int,
        lead_id: int,
        form_version_id: int,
        ttl_hours: int = 72,
    ) -> tuple[str, FormInvitation]:
        """
        Generate a new form invitation token and persist the hashed record.

        Returns (raw_token, FormInvitation) — the raw token is returned to the
        caller exactly once so it can be embedded in the invite email URL.
        It is NEVER stored in the database (Req 3.2).

        Args:
            db: SQLAlchemy session.
            tenant_id: Owning tenant.
            lead_id: Target lead.
            form_version_id: Active FormVersion to link the invitation to.
            ttl_hours: Token lifetime in hours (default 72 — Req 3.3).

        Returns:
            Tuple of (raw_token, persisted FormInvitation record).
        """
        # Req 3.1 — cryptographically random 32-byte URL-safe token
        raw_token: str = secrets.token_urlsafe(32)

        # Req 3.2 — store only the SHA-256 hash
        token_hash: str = _sha256_hex(raw_token)

        # Req 3.3 — expiry = now + ttl_hours
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=ttl_hours)

        invitation = FormInvitation(
            tenant_id=tenant_id,
            lead_id=lead_id,
            form_version_id=form_version_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(invitation)
        db.commit()
        db.refresh(invitation)

        logger.info(
            "FormInvitation created: id=%d tenant=%d lead=%d expires_at=%s",
            invitation.id,
            tenant_id,
            lead_id,
            expires_at.isoformat(),
        )

        # Return raw token to caller — never logged, never stored (Req 3.2, 17.4)
        return raw_token, invitation

    def validate_token(
        self,
        db: Session,
        raw_token: str,
    ) -> FormInvitation:
        """
        Validate a raw token and return the matching FormInvitation.

        Raises:
            TokenNotFoundError: No invitation matches the token hash (Req 3.4).
            TokenUsedError: Invitation has already been used (Req 3.4).
            TokenExpiredError: Invitation has passed its expiry time (Req 3.4).

        Returns:
            The valid, unused, unexpired FormInvitation.
        """
        token_hash = _sha256_hex(raw_token)

        invitation: FormInvitation | None = (
            db.query(FormInvitation)
            .filter(FormInvitation.token_hash == token_hash)
            .one_or_none()
        )

        # Req 3.4 — not found
        if invitation is None:
            raise TokenNotFoundError(f"No invitation found for the provided token")

        # Req 3.4 — already used (check before expiry so callers get the most
        # specific error when a token is both used and expired)
        if invitation.used_at is not None:
            raise TokenUsedError(
                f"Invitation {invitation.id} has already been used at {invitation.used_at}"
            )

        # Req 3.4 — expired
        if invitation.expires_at < datetime.utcnow():
            raise TokenExpiredError(
                f"Invitation {invitation.id} expired at {invitation.expires_at}"
            )

        return invitation

    def mark_used(self, db: Session, invitation: FormInvitation) -> None:
        """
        Mark an invitation as used by setting used_at to now().

        After this call the token is permanently invalid for further
        submissions (Req 3.5).

        Args:
            db: SQLAlchemy session.
            invitation: The FormInvitation to consume.
        """
        invitation.used_at = datetime.utcnow()
        db.commit()

        logger.info(
            "FormInvitation %d marked used at %s",
            invitation.id,
            invitation.used_at.isoformat(),
        )

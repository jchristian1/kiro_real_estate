"""
EmailDeliveryService — single boundary for raw email delivery.

Owns:
  - Tenant SMTP credential resolution (from Credentials table, with optional
    encryption via EncryptedDBCredentialsStore)
  - Raw email sending via AutoResponder (Gmail SMTP / STARTTLS)

Does NOT own:
  - Template rendering (→ future TemplateRenderService)
  - Qualification invite creation (→ QualificationInviteService)
  - Pipeline rule evaluation
  - Activity/lifecycle emission

All pipeline handlers and qualification code that need to send email
must call EmailDeliveryService.send() — not AutoResponder directly.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CredentialResolutionError(Exception):
    """Raised when SMTP credentials cannot be resolved for a tenant."""


class EmailDeliveryService:
    """Resolves tenant SMTP credentials and delivers email via AutoResponder."""

    # ------------------------------------------------------------------
    # Credential resolution
    # ------------------------------------------------------------------

    def get_credentials(self, db: Session, tenant_id: int) -> tuple[str, str]:
        """Return (from_email, app_password) for *tenant_id*.

        Resolution order:
        1. Query Credentials table by company_id == tenant_id.
        2. If ENCRYPTION_KEY env var is set, decrypt via EncryptedDBCredentialsStore.
        3. Otherwise return raw (email_encrypted, app_password_encrypted) columns.

        Raises:
            CredentialResolutionError: if no Credentials row exists for the tenant.
        """
        from gmail_lead_sync.models import Credentials

        creds = db.query(Credentials).filter(Credentials.company_id == tenant_id).first()
        if creds is None:
            raise CredentialResolutionError(
                f"No SMTP credentials found for tenant {tenant_id}"
            )

        encryption_key = os.environ.get("ENCRYPTION_KEY")
        if encryption_key:
            from gmail_lead_sync.credentials import EncryptedDBCredentialsStore
            store = EncryptedDBCredentialsStore(db, encryption_key)
            return store.get_credentials(creds.agent_id)

        return creds.email_encrypted, creds.app_password_encrypted

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    def send(
        self,
        db: Session,
        tenant_id: int,
        to_address: str,
        subject: str,
        body: str,
    ) -> bool:
        """Resolve tenant credentials and send email via SMTP.

        Returns True on success, False if credentials are missing or SMTP fails.
        Never raises — callers should check the return value.

        Args:
            db:         Active SQLAlchemy session (for credential lookup).
            tenant_id:  Company ID used to resolve SMTP credentials.
            to_address: Recipient email address.
            subject:    Email subject line.
            body:       Email body (plain text).
        """
        try:
            from_address, app_password = self.get_credentials(db, tenant_id)
        except CredentialResolutionError as exc:
            logger.error(
                "email_delivery: cannot send to %s for tenant %s — %s",
                to_address, tenant_id, exc,
            )
            return False
        except Exception as exc:
            logger.error(
                "email_delivery: credential resolution failed for tenant %s: %s",
                tenant_id, exc, exc_info=True,
            )
            return False

        try:
            from gmail_lead_sync.responder import AutoResponder
            responder = object.__new__(AutoResponder)
            ok = responder.send_email(
                to_address=to_address,
                subject=subject,
                body=body,
                from_address=from_address,
                app_password=app_password,
            )
            if not ok:
                logger.error(
                    "email_delivery: AutoResponder returned False for %s (tenant %s)",
                    to_address, tenant_id,
                )
            return ok
        except Exception as exc:
            logger.error(
                "email_delivery: unexpected error sending to %s (tenant %s): %s",
                to_address, tenant_id, exc, exc_info=True,
            )
            return False

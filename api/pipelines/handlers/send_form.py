"""
send_qualification_form action handler.

Delegates to the qualification module's public interface
(on_buyer_lead_email_received). Does not implement form or email logic inline.

Config schema:
    {}  (no config required — tenant and lead are resolved from context/DB)
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from api.pipelines.handlers.base import ActionResult, resolve_lead_company_id
from gmail_lead_sync.preapproval.handlers import on_buyer_lead_email_received

logger = logging.getLogger(__name__)


class SendQualificationFormHandler:
    """Handles send_qualification_form actions.

    Calls the qualification module's public handler which creates a
    FormInvitation and sends the invite email. The pipeline engine does
    not need to know how that works.
    """

    def execute(
        self,
        db: Session,
        lead_id: int,
        config: dict,
        context: dict,
    ) -> ActionResult:
        try:
            tenant_id = resolve_lead_company_id(db, lead_id)
            if tenant_id is None:
                return ActionResult(
                    success=False,
                    error=f"Cannot resolve company_id for lead {lead_id}",
                )

            on_buyer_lead_email_received(
                db=db,
                tenant_id=tenant_id,
                lead_id=lead_id,
                parsed_metadata=context,
            )

            logger.info(
                "send_qualification_form: sent lead_id=%s tenant_id=%s",
                lead_id, tenant_id,
            )
            return ActionResult(
                success=True,
                metadata={"tenant_id": tenant_id},
            )

        except Exception as exc:
            return ActionResult(success=False, error=str(exc))

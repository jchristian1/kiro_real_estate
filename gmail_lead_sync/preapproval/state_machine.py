"""
LeadStateMachine — enforces valid state transitions, persists the immutable
event log, and updates leads.current_state atomically.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from api.exceptions import NotFoundException
from gmail_lead_sync.models import Lead
from gmail_lead_sync.preapproval.models_preapproval import (
    ActorType,
    IntentType,
    LeadState,
    LeadStateTransition,
)

logger = logging.getLogger(__name__)


class InvalidTransitionError(Exception):
    """Raised when a requested state transition is not in VALID_TRANSITIONS."""


class LeadStateMachine:
    """
    Enforces the buyer-lead qualification state machine.

    Valid transition map (Req 1.6):
        NULL                      → NEW_EMAIL_RECEIVED
        NEW_EMAIL_RECEIVED        → FORM_INVITE_CREATED
        FORM_INVITE_CREATED       → FORM_INVITE_SENT
        FORM_INVITE_SENT          → FORM_SUBMITTED
        FORM_SUBMITTED            → SCORED
        SCORED                    → POST_SUBMISSION_EMAIL_SENT
        POST_SUBMISSION_EMAIL_SENT → AGENT_ASSIGNED  (future)
    """

    VALID_TRANSITIONS: dict[str | None, list[str]] = {
        None:                           ["NEW_EMAIL_RECEIVED"],
        "NEW_EMAIL_RECEIVED":           ["FORM_INVITE_CREATED"],
        "FORM_INVITE_CREATED":          ["FORM_INVITE_SENT"],
        "FORM_INVITE_SENT":             ["FORM_SUBMITTED"],
        "FORM_SUBMITTED":               ["SCORED"],
        "SCORED":                       ["POST_SUBMISSION_EMAIL_SENT"],
        "POST_SUBMISSION_EMAIL_SENT":   ["AGENT_ASSIGNED"],  # future
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transition(
        self,
        db: Session,
        tenant_id: int,
        lead_id: int,
        intent_type: IntentType,
        to_state: LeadState,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: int | None = None,
        metadata: dict | None = None,
    ) -> LeadStateTransition:
        """
        Validate and apply a state transition for a lead.

        Steps:
        1. Load the lead (raises NotFoundException if missing — Req 1.8).
        2. Validate the transition is allowed (raises InvalidTransitionError — Req 1.2, 1.3).
        3. Check for existing transition within idempotency window (Req 8.5, 8.6).
        4. Insert an immutable LeadStateTransition row (Req 1.4, 1.7).
        5. Update leads.current_state + current_state_updated_at atomically (Req 1.5).
        6. Commit.

        Returns the newly created LeadStateTransition row (or existing row if idempotent).
        """
        lead = db.get(Lead, lead_id)
        if lead is None:
            raise NotFoundException(
                message=f"Lead {lead_id} not found",
                code="NOT_FOUND_RESOURCE",
            )

        from_state: str | None = lead.current_state
        to_state_value: str = to_state.value if isinstance(to_state, LeadState) else to_state

        # Validate transition (Req 1.2, 1.3)
        allowed = self.VALID_TRANSITIONS.get(from_state)
        if allowed is None or to_state_value not in allowed:
            raise InvalidTransitionError(
                f"{from_state!r} → {to_state_value!r} is not allowed"
            )

        now = datetime.utcnow()

        # Idempotency check: look for existing transition within last 5 seconds (Req 8.5, 8.6)
        idempotency_window = now - timedelta(seconds=5)
        existing_transition = (
            db.query(LeadStateTransition)
            .filter(
                LeadStateTransition.lead_id == lead_id,
                LeadStateTransition.from_state == from_state,
                LeadStateTransition.to_state == to_state_value,
                LeadStateTransition.occurred_at >= idempotency_window,
            )
            .order_by(LeadStateTransition.occurred_at.desc())
            .first()
        )

        if existing_transition is not None:
            logger.info(
                "Lead %d transition %s → %s already exists (id=%d, occurred_at=%s), returning existing row",
                lead_id,
                from_state,
                to_state_value,
                existing_transition.id,
                existing_transition.occurred_at,
            )
            return existing_transition

        # Immutable event log row (Req 1.4, 1.7)
        transition_row = LeadStateTransition(
            tenant_id=tenant_id,
            lead_id=lead_id,
            intent_type=intent_type.value if isinstance(intent_type, IntentType) else intent_type,
            from_state=from_state,
            to_state=to_state_value,
            occurred_at=now,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
            actor_type=actor_type.value if isinstance(actor_type, ActorType) else actor_type,
            actor_id=actor_id,
        )
        db.add(transition_row)

        # Atomic update of lead record (Req 1.5)
        lead.current_state = to_state_value
        lead.current_state_updated_at = now

        db.commit()
        db.refresh(transition_row)

        logger.info(
            "Lead %d transitioned %s → %s (tenant=%d, actor=%s/%s)",
            lead_id,
            from_state,
            to_state_value,
            tenant_id,
            actor_type,
            actor_id,
        )

        return transition_row

    def current_state(self, db: Session, lead_id: int) -> LeadState | None:
        """
        Return the current LeadState for a lead.

        Raises NotFoundException if the lead does not exist (Req 1.8).
        Returns None when the lead has no state yet (initial state).
        """
        lead = db.get(Lead, lead_id)
        if lead is None:
            raise NotFoundException(
                message=f"Lead {lead_id} not found",
                code="NOT_FOUND_RESOURCE",
            )

        raw = lead.current_state
        if raw is None:
            return None
        return LeadState(raw)

"""
Canonical location for LeadStateMachine and LeadState enum.

This module re-exports the state machine implementation from the gmail_lead_sync
module to provide a clean API-layer import path. All modules should import from
this location:

    from api.services.lead_state_machine import LeadState, LeadStateMachine

Requirements: 8.1, 8.2
"""

from gmail_lead_sync.preapproval.models_preapproval import LeadState
from gmail_lead_sync.preapproval.state_machine import (
    InvalidTransitionError,
    LeadStateMachine,
)

__all__ = [
    "LeadState",
    "LeadStateMachine",
    "InvalidTransitionError",
]

"""
Unit tests for LeadStateMachine idempotency behavior.

Tests that calling transition() twice with the same parameters within 5 seconds
returns the existing transition row without creating a duplicate.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base, Lead
from gmail_lead_sync.preapproval.models_preapproval import (
    LeadState,
    LeadStateTransition,
    IntentType,
    ActorType,
)
from gmail_lead_sync.preapproval.state_machine import LeadStateMachine


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_lead_source(db_session):
    """Create a sample lead source for testing."""
    from gmail_lead_sync.models import LeadSource
    
    lead_source = LeadSource(
        sender_email="test@example.com",
        identifier_snippet="test",
        name_regex=".*",
        phone_regex=".*",
    )
    db_session.add(lead_source)
    db_session.commit()
    db_session.refresh(lead_source)
    return lead_source


@pytest.fixture
def sample_lead(db_session, sample_lead_source):
    """Create a sample lead for testing."""
    lead = Lead(
        agent_id="test_agent",
        name="John Buyer",
        source_email="john@example.com",
        phone="555-1234",
        gmail_uid="test_uid_123",
        lead_source_id=sample_lead_source.id,
        current_state=None,
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


class TestLeadStateMachineIdempotency:
    """Test idempotency behavior of LeadStateMachine.transition()."""

    def test_duplicate_transition_within_5_seconds_returns_existing_row(
        self, db_session, sample_lead
    ):
        """
        Calling transition() twice with the same parameters within 5 seconds
        should return the existing transition row without creating a duplicate.
        
        Note: The idempotency check looks for existing transitions with the same
        (lead_id, from_state, to_state) tuple, regardless of the lead's current state.
        """
        state_machine = LeadStateMachine()
        tenant_id = 1

        # First transition: None → NEW_EMAIL_RECEIVED
        transition1 = state_machine.transition(
            db=db_session,
            tenant_id=tenant_id,
            lead_id=sample_lead.id,
            intent_type=IntentType.BUY,
            to_state=LeadState.NEW_EMAIL_RECEIVED,
            actor_type=ActorType.SYSTEM,
        )

        # Manually reset the lead's current_state back to None to allow the same transition
        # This simulates a retry scenario where the transition was recorded but we're
        # attempting it again (e.g., from a watcher retry)
        sample_lead.current_state = None
        db_session.commit()

        # Second transition with same parameters (within 5 seconds)
        # Should return the existing transition row due to idempotency check
        transition2 = state_machine.transition(
            db=db_session,
            tenant_id=tenant_id,
            lead_id=sample_lead.id,
            intent_type=IntentType.BUY,
            to_state=LeadState.NEW_EMAIL_RECEIVED,
            actor_type=ActorType.SYSTEM,
        )

        # Should return the same transition row
        assert transition1.id == transition2.id
        assert transition1.occurred_at == transition2.occurred_at

        # Verify only one transition row exists in the database
        all_transitions = (
            db_session.query(LeadStateTransition)
            .filter_by(lead_id=sample_lead.id)
            .all()
        )
        assert len(all_transitions) == 1

    def test_duplicate_transition_after_5_seconds_creates_new_row(
        self, db_session, sample_lead
    ):
        """
        Calling transition() twice with the same parameters after 5 seconds
        should create a new transition row (outside idempotency window).
        """
        state_machine = LeadStateMachine()
        tenant_id = 1

        # First transition: None → NEW_EMAIL_RECEIVED
        transition1 = state_machine.transition(
            db=db_session,
            tenant_id=tenant_id,
            lead_id=sample_lead.id,
            intent_type=IntentType.BUY,
            to_state=LeadState.NEW_EMAIL_RECEIVED,
            actor_type=ActorType.SYSTEM,
        )

        # Manually update the occurred_at timestamp to be 6 seconds ago
        # (outside the idempotency window)
        transition1.occurred_at = datetime.utcnow() - timedelta(seconds=6)
        db_session.commit()

        # Reset lead state to None to allow the same transition again
        sample_lead.current_state = None
        db_session.commit()

        # Second transition with same parameters (after 5 seconds)
        transition2 = state_machine.transition(
            db=db_session,
            tenant_id=tenant_id,
            lead_id=sample_lead.id,
            intent_type=IntentType.BUY,
            to_state=LeadState.NEW_EMAIL_RECEIVED,
            actor_type=ActorType.SYSTEM,
        )

        # Should create a new transition row
        assert transition1.id != transition2.id
        assert transition1.occurred_at != transition2.occurred_at

        # Verify two transition rows exist in the database
        all_transitions = (
            db_session.query(LeadStateTransition)
            .filter_by(lead_id=sample_lead.id)
            .all()
        )
        assert len(all_transitions) == 2

    def test_different_transitions_create_separate_rows(
        self, db_session, sample_lead
    ):
        """
        Different transitions (different from_state or to_state) should always
        create separate rows, even within 5 seconds.
        """
        state_machine = LeadStateMachine()
        tenant_id = 1

        # First transition: None → NEW_EMAIL_RECEIVED
        transition1 = state_machine.transition(
            db=db_session,
            tenant_id=tenant_id,
            lead_id=sample_lead.id,
            intent_type=IntentType.BUY,
            to_state=LeadState.NEW_EMAIL_RECEIVED,
            actor_type=ActorType.SYSTEM,
        )

        # Second transition: NEW_EMAIL_RECEIVED → FORM_INVITE_CREATED
        transition2 = state_machine.transition(
            db=db_session,
            tenant_id=tenant_id,
            lead_id=sample_lead.id,
            intent_type=IntentType.BUY,
            to_state=LeadState.FORM_INVITE_CREATED,
            actor_type=ActorType.SYSTEM,
        )

        # Should create separate transition rows
        assert transition1.id != transition2.id
        assert transition1.to_state != transition2.to_state

        # Verify two transition rows exist in the database
        all_transitions = (
            db_session.query(LeadStateTransition)
            .filter_by(lead_id=sample_lead.id)
            .all()
        )
        assert len(all_transitions) == 2

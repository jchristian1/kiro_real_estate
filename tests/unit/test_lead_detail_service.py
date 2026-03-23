"""
Unit tests for the unified lead detail assembler (Phase 3C).

Tests:
- assemble_lead_detail returns None for unknown lead
- core fields are populated from Lead ORM
- stage is None when lead has no current_stage_id
- stage is populated when PipelineStage exists
- qualification is None when no FormSubmission exists
- qualification is populated from SubmissionScore when available
- qualification falls back to Lead.score columns when submission unscored
- timeline uses LeadActivityRepository.get_timeline (not LeadEventWriteRepository)
- timeline entries carry actor_source and parsed metadata
- rendered_emails and notes are extractable from timeline in agent router
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from api.services.lead_detail_service import (
    assemble_lead_detail,
    _parse_breakdown,
    _parse_lead_score_breakdown,
    ScoreFactorDetail,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lead(
    id=1,
    name="Alice",
    phone="555-1234",
    source_email="alice@test.com",
    created_at=None,
    property_address="123 Main St",
    listing_url="https://example.com/listing",
    lead_source_name="Zillow",
    agent_current_state="NEW",
    last_agent_action_at=None,
    score=None,
    score_bucket=None,
    score_breakdown=None,
    current_stage_id=None,
    stage_entered_at=None,
    company_id=10,
    agent_user_id=5,
):
    return SimpleNamespace(
        id=id,
        name=name,
        phone=phone,
        source_email=source_email,
        created_at=created_at or datetime(2026, 1, 1),
        property_address=property_address,
        listing_url=listing_url,
        lead_source_name=lead_source_name,
        agent_current_state=agent_current_state,
        last_agent_action_at=last_agent_action_at,
        score=score,
        score_bucket=score_bucket,
        score_breakdown=score_breakdown,
        current_stage_id=current_stage_id,
        stage_entered_at=stage_entered_at,
        company_id=company_id,
        agent_user_id=agent_user_id,
    )


def _make_stage(id=1, name="New Lead", key="new_lead", color="#3B82F6", category="open"):
    cat = SimpleNamespace(value=category)
    return SimpleNamespace(id=id, name=name, key=key, color=color, category=cat)


def _make_submission(id=1, lead_id=1, submitted_at=None, invitation_id=None):
    return SimpleNamespace(
        id=id,
        lead_id=lead_id,
        submitted_at=submitted_at or datetime(2026, 1, 2),
        invitation_id=invitation_id,
    )


def _make_score(submission_id=1, total_score=85, bucket="HOT", breakdown_json=None, explanation_text="Strong buyer"):
    return SimpleNamespace(
        submission_id=submission_id,
        total_score=total_score,
        bucket=bucket,
        breakdown_json=breakdown_json or json.dumps([
            {"label": "Timeline", "points": 25, "met": True},
            {"label": "Pre-approval", "points": 30, "met": True},
        ]),
        explanation_text=explanation_text,
    )


def _make_event(id=1, lead_id=1, event_type="lead_created", actor_source="system", metadata_json=None, payload=None, created_at=None):
    return SimpleNamespace(
        id=id,
        lead_id=lead_id,
        event_type=event_type,
        actor_source=actor_source,
        metadata_json=metadata_json,
        payload=payload,
        created_at=created_at or datetime(2026, 1, 1, 12, 0),
    )


def _build_db(lead=None, stage=None, submission=None, score=None, invitation=None, events=None):
    """Build a mock db.query chain for the assembler."""
    db = MagicMock()

    def query_side_effect(model):
        mock_q = MagicMock()

        # Lead query
        from gmail_lead_sync.models import Lead as LeadModel
        from api.models.pipeline_models import PipelineStage
        from gmail_lead_sync.preapproval.models_preapproval import (
            FormSubmission, SubmissionScore, FormInvitation
        )

        if model is LeadModel:
            mock_q.filter.return_value.first.return_value = lead
        elif model is PipelineStage:
            mock_q.filter.return_value.first.return_value = stage
        elif model is FormSubmission:
            mock_q.filter.return_value.order_by.return_value.first.return_value = submission
        elif model is SubmissionScore:
            mock_q.filter.return_value.first.return_value = score
        elif model is FormInvitation:
            mock_q.filter.return_value.first.return_value = invitation
        else:
            mock_q.filter.return_value.first.return_value = None

        return mock_q

    db.query.side_effect = query_side_effect
    return db


# ---------------------------------------------------------------------------
# assemble_lead_detail — core
# ---------------------------------------------------------------------------

class TestAssembleLeadDetailCore:
    def test_returns_none_for_unknown_lead(self):
        db = _build_db(lead=None)
        result = assemble_lead_detail(db, lead_id=999)
        assert result is None

    def test_core_fields_populated(self):
        lead = _make_lead()
        db = _build_db(lead=lead)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1, company_id=10)

        assert result is not None
        assert result.core.id == 1
        assert result.core.name == "Alice"
        assert result.core.phone == "555-1234"
        assert result.core.source_email == "alice@test.com"
        assert result.core.property_address == "123 Main St"
        assert result.core.listing_url == "https://example.com/listing"
        assert result.core.lead_source_name == "Zillow"
        assert result.core.agent_current_state == "NEW"

    def test_core_name_defaults_to_empty_string_when_none(self):
        lead = _make_lead(name=None)
        db = _build_db(lead=lead)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.core.name == ""


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------

class TestAssembleLeadDetailStage:
    def test_stage_is_none_when_no_current_stage_id(self):
        lead = _make_lead(current_stage_id=None)
        db = _build_db(lead=lead)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.stage is None

    def test_stage_is_none_when_stage_not_found(self):
        lead = _make_lead(current_stage_id=99)
        db = _build_db(lead=lead, stage=None)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.stage is None

    def test_stage_populated_when_pipeline_stage_exists(self):
        lead = _make_lead(current_stage_id=3, stage_entered_at=datetime(2026, 1, 5))
        stage = _make_stage(id=3, name="Contacted", key="contacted", color="#10B981", category="in_progress")
        db = _build_db(lead=lead, stage=stage)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.stage is not None
        assert result.stage.stage_id == 3
        assert result.stage.stage_name == "Contacted"
        assert result.stage.stage_key == "contacted"
        assert result.stage.stage_color == "#10B981"
        assert result.stage.stage_category == "in_progress"
        assert result.stage.stage_entered_at == datetime(2026, 1, 5)


# ---------------------------------------------------------------------------
# Qualification
# ---------------------------------------------------------------------------

class TestAssembleLeadDetailQualification:
    def test_qualification_is_none_when_no_submission(self):
        lead = _make_lead()
        db = _build_db(lead=lead, submission=None)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.qualification is None

    def test_qualification_populated_from_submission_score(self):
        lead = _make_lead()
        submission = _make_submission()
        score = _make_score()
        db = _build_db(lead=lead, submission=submission, score=score)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.qualification is not None
        assert result.qualification.score == 85
        assert result.qualification.bucket == "HOT"
        assert result.qualification.explanation_text == "Strong buyer"
        assert len(result.qualification.breakdown) == 2
        assert result.qualification.breakdown[0].label == "Timeline"
        assert result.qualification.breakdown[0].met is True

    def test_qualification_submitted_at_from_submission(self):
        lead = _make_lead()
        submitted = datetime(2026, 2, 15)
        submission = _make_submission(submitted_at=submitted)
        score = _make_score()
        db = _build_db(lead=lead, submission=submission, score=score)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.qualification.submitted_at == submitted

    def test_qualification_invitation_sent_at_from_invitation(self):
        lead = _make_lead()
        submission = _make_submission(invitation_id=7)
        score = _make_score()
        inv = SimpleNamespace(id=7, sent_at=datetime(2026, 2, 10))
        db = _build_db(lead=lead, submission=submission, score=score, invitation=inv)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.qualification.invitation_sent_at == datetime(2026, 2, 10)

    def test_qualification_falls_back_to_lead_score_when_unscored(self):
        """When submission exists but no SubmissionScore, fall back to Lead.score columns."""
        lead = _make_lead(
            score=72,
            score_bucket="WARM",
            score_breakdown=json.dumps({"factors": [{"label": "Budget", "points": 10, "met": True}]}),
        )
        submission = _make_submission()
        db = _build_db(lead=lead, submission=submission, score=None)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.qualification is not None
        assert result.qualification.score == 72
        assert result.qualification.bucket == "WARM"
        assert len(result.qualification.breakdown) == 1

    def test_qualification_is_none_when_unscored_and_no_lead_score(self):
        """No submission score AND no Lead.score → qualification is None."""
        lead = _make_lead(score=None, score_bucket=None)
        submission = _make_submission()
        db = _build_db(lead=lead, submission=submission, score=None)

        with patch("api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline", return_value=[]):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.qualification is None


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class TestAssembleLeadDetailTimeline:
    def test_timeline_uses_lead_activity_repository(self):
        """Timeline must come from LeadActivityRepository, not LeadEventWriteRepository."""
        lead = _make_lead()
        db = _build_db(lead=lead)

        events = [
            _make_event(id=1, event_type="lead_created", actor_source="system"),
            _make_event(id=2, event_type="lead_stage_changed", actor_source="pipeline"),
        ]

        with patch(
            "api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline",
            return_value=events,
        ) as mock_timeline:
            result = assemble_lead_detail(db, lead_id=1, company_id=10)

        mock_timeline.assert_called_once_with(lead_id=1)
        assert len(result.timeline) == 2

    def test_timeline_entries_have_correct_fields(self):
        lead = _make_lead()
        db = _build_db(lead=lead)
        ts = datetime(2026, 3, 1, 10, 0)
        events = [
            _make_event(
                id=5,
                event_type="qualification_form_sent",
                actor_source="qualification",
                metadata_json=json.dumps({"form_version_id": 3}),
                created_at=ts,
            )
        ]

        with patch(
            "api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline",
            return_value=events,
        ):
            result = assemble_lead_detail(db, lead_id=1)

        entry = result.timeline[0]
        assert entry.id == 5
        assert entry.event_type == "qualification_form_sent"
        assert entry.actor_source == "qualification"
        assert entry.metadata == {"form_version_id": 3}
        assert entry.occurred_at == ts

    def test_timeline_empty_when_no_events(self):
        lead = _make_lead()
        db = _build_db(lead=lead)

        with patch(
            "api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline",
            return_value=[],
        ):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.timeline == []

    def test_timeline_metadata_falls_back_to_legacy_payload(self):
        """Events with no metadata_json but legacy payload should still parse."""
        lead = _make_lead()
        db = _build_db(lead=lead)
        events = [
            _make_event(
                id=3,
                event_type="INVITE_SENT",
                actor_source=None,
                metadata_json=None,
                payload=json.dumps({"subject": "Hello", "body": "World"}),
            )
        ]

        with patch(
            "api.repositories.lead_activity_repository.LeadActivityRepository.get_timeline",
            return_value=events,
        ):
            result = assemble_lead_detail(db, lead_id=1)

        assert result.timeline[0].metadata == {"subject": "Hello", "body": "World"}


# ---------------------------------------------------------------------------
# _parse_breakdown helpers
# ---------------------------------------------------------------------------

class TestParseBreakdown:
    def test_parses_list_format(self):
        raw = json.dumps([{"label": "A", "points": 10, "met": True}])
        result = _parse_breakdown(raw)
        assert len(result) == 1
        assert result[0].label == "A"
        assert result[0].points == 10
        assert result[0].met is True

    def test_parses_dict_with_factors_key(self):
        raw = json.dumps({"factors": [{"label": "B", "points": 5, "met": False}]})
        result = _parse_breakdown(raw)
        assert len(result) == 1
        assert result[0].label == "B"

    def test_returns_empty_on_invalid_json(self):
        result = _parse_breakdown("not-json")
        assert result == []

    def test_returns_empty_on_none(self):
        result = _parse_breakdown(None)
        assert result == []

    def test_skips_non_dict_entries(self):
        raw = json.dumps(["not", "a", "dict"])
        result = _parse_breakdown(raw)
        assert result == []


class TestParseLegacyBreakdown:
    def test_parses_factors_key(self):
        raw = json.dumps({"factors": [{"label": "X", "points": 20, "met": True}]})
        result = _parse_lead_score_breakdown(raw)
        assert len(result) == 1
        assert result[0].label == "X"

    def test_returns_empty_on_none(self):
        assert _parse_lead_score_breakdown(None) == []

    def test_returns_empty_on_invalid_json(self):
        assert _parse_lead_score_breakdown("{bad}") == []

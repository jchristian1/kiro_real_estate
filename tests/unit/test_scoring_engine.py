"""
Unit tests for api/services/scoring_engine.py

Tests cover:
- score_lead: all 5 factors met → HOT
- score_lead: no submission → only phone factor can be met
- score_lead: enable_tour_question=False → tour contributes 0 points
- score_lead: bucket assignment (HOT / WARM / NURTURE)
- score_lead: persists score, score_bucket, score_breakdown to lead
- score_lead: inserts LEAD_SCORED event with correct payload
- score_lead: raises ValueError for missing lead or config
- Helper functions: _parse_timeline_months, _is_preapproved, _wants_tour, _budget_in_range
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from api.services.scoring_engine import (
    _budget_in_range,
    _is_preapproved,
    _parse_timeline_months,
    _wants_tour,
    score_lead,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_config(
    hot_threshold=80,
    warm_threshold=50,
    weight_timeline=25,
    weight_preapproval=30,
    weight_phone_provided=15,
    weight_tour_interest=20,
    weight_budget_match=10,
    enable_tour_question=True,
):
    cfg = MagicMock()
    cfg.hot_threshold = hot_threshold
    cfg.warm_threshold = warm_threshold
    cfg.weight_timeline = weight_timeline
    cfg.weight_preapproval = weight_preapproval
    cfg.weight_phone_provided = weight_phone_provided
    cfg.weight_tour_interest = weight_tour_interest
    cfg.weight_budget_match = weight_budget_match
    cfg.enable_tour_question = enable_tour_question
    return cfg


def _make_lead(lead_id=1, phone="555-1234", agent_user_id=None):
    lead = MagicMock()
    lead.id = lead_id
    lead.phone = phone
    lead.agent_user_id = agent_user_id
    lead.score = None
    lead.score_bucket = None
    lead.score_breakdown = None
    return lead


def _make_db(lead=None, config=None):
    """Return a mock Session whose query().filter().first() returns the given objects."""
    db = MagicMock()

    def _query_side_effect(model):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        # Determine which object to return based on model name
        from gmail_lead_sync.models import Lead
        from gmail_lead_sync.agent_models import BuyerAutomationConfig
        if model is Lead:
            q.first.return_value = lead
        elif model is BuyerAutomationConfig:
            q.first.return_value = config
        else:
            q.first.return_value = None
        return q

    db.query.side_effect = _query_side_effect
    db.add = MagicMock()
    db.flush = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestParseTimelineMonths:
    def test_asap_returns_zero(self):
        assert _parse_timeline_months({"timeline": "asap"}) == 0

    def test_1_3_months_returns_2(self):
        assert _parse_timeline_months({"timeline": "1_3_months"}) == 2

    def test_3_6_months_returns_4(self):
        assert _parse_timeline_months({"timeline": "3_6_months"}) == 4

    def test_6_plus_months_returns_9(self):
        assert _parse_timeline_months({"timeline": "6_plus_months"}) == 9

    def test_not_sure_returns_none(self):
        assert _parse_timeline_months({"timeline": "not_sure"}) is None

    def test_missing_key_returns_none(self):
        assert _parse_timeline_months({}) is None


class TestIsPreapproved:
    def test_pre_approved_returns_true(self):
        assert _is_preapproved({"financing": "pre_approved"}) is True

    def test_cash_returns_true(self):
        assert _is_preapproved({"financing": "cash"}) is True

    def test_need_mortgage_returns_false(self):
        assert _is_preapproved({"financing": "need_mortgage"}) is False

    def test_not_sure_returns_false(self):
        assert _is_preapproved({"financing": "not_sure"}) is False

    def test_missing_key_returns_false(self):
        assert _is_preapproved({}) is False


class TestWantsTour:
    def test_yes_returns_true(self):
        assert _wants_tour({"wants_tour": "yes"}) is True

    def test_maybe_returns_false(self):
        assert _wants_tour({"wants_tour": "maybe"}) is False

    def test_no_returns_false(self):
        assert _wants_tour({"wants_tour": "no"}) is False

    def test_missing_key_returns_false(self):
        assert _wants_tour({}) is False


class TestBudgetInRange:
    def test_concrete_budget_returns_true(self):
        assert _budget_in_range({"budget": "500k_750k"}) is True

    def test_over_1m_returns_true(self):
        assert _budget_in_range({"budget": "over_1m"}) is True

    def test_not_sure_returns_false(self):
        assert _budget_in_range({"budget": "not_sure"}) is False

    def test_missing_key_returns_false(self):
        assert _budget_in_range({}) is False


# ---------------------------------------------------------------------------
# score_lead tests
# ---------------------------------------------------------------------------

class TestScoreLead:
    def _run(self, lead, config, answers=None):
        """Run score_lead with mocked DB and optional submission answers."""
        db = _make_db(lead=lead, config=config)
        with patch(
            "api.services.scoring_engine._get_submission_answers",
            return_value=answers,
        ):
            result = score_lead(db, lead.id, config.id)
        return result, db

    # --- All factors met → HOT ---

    def test_all_factors_met_hot(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config()  # defaults: hot=80, warm=50, weights sum to 100
        answers = {
            "timeline": "asap",        # 0 months → met
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        # All 5 factors met: 25+30+15+20+10 = 100
        assert result["score"] == 100
        assert result["bucket"] == "HOT"
        assert len(result["breakdown"]) == 5
        assert all(f["met"] for f in result["breakdown"])

    # --- No submission → only phone factor can be met ---

    def test_no_submission_only_phone_met(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config()
        result, _ = self._run(lead, config, answers=None)
        # Only phone provided (15 pts) → NURTURE (15 < 50)
        assert result["score"] == 15
        assert result["bucket"] == "NURTURE"
        phone_factor = next(f for f in result["breakdown"] if f["label"] == "Phone provided")
        assert phone_factor["met"] is True
        # All other factors unmet
        other_factors = [f for f in result["breakdown"] if f["label"] != "Phone provided"]
        assert all(not f["met"] for f in other_factors)

    def test_no_submission_no_phone_score_zero(self):
        lead = _make_lead(phone=None)
        config = _make_config()
        result, _ = self._run(lead, config, answers=None)
        assert result["score"] == 0
        assert result["bucket"] == "NURTURE"
        assert all(not f["met"] for f in result["breakdown"])

    # --- enable_tour_question = FALSE → tour contributes 0 (Req 13.8) ---

    def test_tour_disabled_contributes_zero(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config(enable_tour_question=False)
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",  # would normally add 20 pts
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        # Tour factor NOT met even though wants_tour=yes
        tour_factor = next(f for f in result["breakdown"] if f["label"] == "Wants tour")
        assert tour_factor["met"] is False
        # Score = 25+30+15+0+10 = 80 (still HOT at threshold 80)
        assert result["score"] == 80
        assert result["bucket"] == "HOT"

    def test_tour_disabled_score_excludes_tour_weight(self):
        """With tour disabled and all other factors met, score = sum of other weights."""
        lead = _make_lead(phone="555-1234")
        config = _make_config(
            weight_timeline=25,
            weight_preapproval=30,
            weight_phone_provided=15,
            weight_tour_interest=20,
            weight_budget_match=10,
            enable_tour_question=False,
            hot_threshold=90,
            warm_threshold=50,
        )
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        assert result["score"] == 80  # 25+30+15+10 (no tour)
        assert result["bucket"] == "WARM"  # 80 >= 50 but < 90

    # --- Bucket assignment ---

    def test_bucket_hot_at_threshold(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config(hot_threshold=80, warm_threshold=50)
        # Score exactly at hot_threshold
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        assert result["score"] == 100
        assert result["bucket"] == "HOT"

    def test_bucket_warm_between_thresholds(self):
        lead = _make_lead(phone=None)  # no phone
        config = _make_config(hot_threshold=80, warm_threshold=50)
        # Only timeline + preapproval + budget = 25+30+10 = 65 → WARM
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "no",
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        assert result["score"] == 65
        assert result["bucket"] == "WARM"

    def test_bucket_nurture_below_warm_threshold(self):
        lead = _make_lead(phone=None)
        config = _make_config(hot_threshold=80, warm_threshold=50)
        # Only budget = 10 → NURTURE
        answers = {
            "timeline": "6_plus_months",
            "financing": "need_mortgage",
            "wants_tour": "no",
            "budget": "300k_500k",
        }
        result, _ = self._run(lead, config, answers)
        assert result["score"] == 10
        assert result["bucket"] == "NURTURE"

    def test_bucket_warm_at_warm_threshold(self):
        lead = _make_lead(phone=None)
        config = _make_config(hot_threshold=80, warm_threshold=50)
        # timeline(25) + budget(10) + phone(15) = 50 → exactly WARM
        answers = {
            "timeline": "asap",
            "financing": "need_mortgage",
            "wants_tour": "no",
            "budget": "300k_500k",
        }
        lead.phone = "555-0000"
        result, _ = self._run(lead, config, answers)
        assert result["score"] == 50
        assert result["bucket"] == "WARM"

    # --- Breakdown structure ---

    def test_breakdown_has_five_factors(self):
        lead = _make_lead()
        config = _make_config()
        result, _ = self._run(lead, config, answers=None)
        assert len(result["breakdown"]) == 5

    def test_breakdown_labels(self):
        lead = _make_lead()
        config = _make_config()
        result, _ = self._run(lead, config, answers=None)
        labels = {f["label"] for f in result["breakdown"]}
        assert labels == {
            "Timeline < 3 months",
            "Pre-approved",
            "Phone provided",
            "Wants tour",
            "Budget in range",
        }

    def test_breakdown_points_match_config_weights(self):
        lead = _make_lead()
        config = _make_config(
            weight_timeline=25,
            weight_preapproval=30,
            weight_phone_provided=15,
            weight_tour_interest=20,
            weight_budget_match=10,
        )
        result, _ = self._run(lead, config, answers=None)
        weight_map = {
            "Timeline < 3 months": 25,
            "Pre-approved": 30,
            "Phone provided": 15,
            "Wants tour": 20,
            "Budget in range": 10,
        }
        for factor in result["breakdown"]:
            assert factor["points"] == weight_map[factor["label"]]

    # --- Persistence ---

    def test_persists_score_to_lead(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config()
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        assert lead.score == result["score"]

    def test_persists_bucket_to_lead(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config()
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        assert lead.score_bucket == result["bucket"]

    def test_persists_breakdown_json_to_lead(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config()
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        stored = json.loads(lead.score_breakdown)
        assert stored == result["breakdown"]

    # --- LEAD_SCORED event ---

    def test_inserts_lead_scored_event(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config()
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, db = self._run(lead, config, answers)
        # db.add should have been called with a LeadEvent
        db.add.assert_called_once()
        event_arg = db.add.call_args[0][0]
        from gmail_lead_sync.agent_models import LeadEvent
        assert isinstance(event_arg, LeadEvent)
        assert event_arg.event_type == "LEAD_SCORED"
        assert event_arg.lead_id == lead.id

    def test_lead_scored_event_payload(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config()
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, db = self._run(lead, config, answers)
        event_arg = db.add.call_args[0][0]
        payload = json.loads(event_arg.payload)
        assert payload["score"] == result["score"]
        assert payload["bucket"] == result["bucket"]
        assert payload["breakdown"] == result["breakdown"]

    def test_db_flush_called(self):
        lead = _make_lead()
        config = _make_config()
        _, db = self._run(lead, config, answers=None)
        db.flush.assert_called()

    # --- Error handling ---

    def test_raises_when_lead_not_found(self):
        db = _make_db(lead=None, config=_make_config())
        with patch("api.services.scoring_engine._get_submission_answers", return_value=None):
            with pytest.raises(ValueError, match="Lead 999 not found"):
                score_lead(db, 999, 1)

    def test_raises_when_config_not_found(self):
        lead = _make_lead()
        db = _make_db(lead=lead, config=None)
        with patch("api.services.scoring_engine._get_submission_answers", return_value=None):
            with pytest.raises(ValueError, match="BuyerAutomationConfig 999 not found"):
                score_lead(db, lead.id, 999)

    # --- Score bounds ---

    def test_score_is_zero_when_nothing_met(self):
        lead = _make_lead(phone=None)
        config = _make_config()
        result, _ = self._run(lead, config, answers=None)
        assert result["score"] == 0

    def test_score_is_100_when_all_met_with_default_weights(self):
        lead = _make_lead(phone="555-1234")
        config = _make_config()  # weights sum to 100
        answers = {
            "timeline": "asap",
            "financing": "pre_approved",
            "wants_tour": "yes",
            "budget": "500k_750k",
        }
        result, _ = self._run(lead, config, answers)
        assert result["score"] == 100

    # --- Phone edge cases ---

    def test_empty_phone_string_not_met(self):
        lead = _make_lead(phone="")
        config = _make_config()
        result, _ = self._run(lead, config, answers=None)
        phone_factor = next(f for f in result["breakdown"] if f["label"] == "Phone provided")
        assert phone_factor["met"] is False

    def test_whitespace_only_phone_not_met(self):
        lead = _make_lead(phone="   ")
        config = _make_config()
        result, _ = self._run(lead, config, answers=None)
        phone_factor = next(f for f in result["breakdown"] if f["label"] == "Phone provided")
        assert phone_factor["met"] is False

    # --- Timeline edge cases ---

    def test_timeline_exactly_3_months_is_met(self):
        """1_3_months maps to 2 months which is <= 3, so it's met."""
        lead = _make_lead(phone=None)
        config = _make_config()
        answers = {"timeline": "1_3_months"}
        result, _ = self._run(lead, config, answers)
        timeline_factor = next(f for f in result["breakdown"] if f["label"] == "Timeline < 3 months")
        assert timeline_factor["met"] is True

    def test_timeline_over_3_months_not_met(self):
        """3_6_months maps to 4 months which is > 3, so it's not met."""
        lead = _make_lead(phone=None)
        config = _make_config()
        answers = {"timeline": "3_6_months"}
        result, _ = self._run(lead, config, answers)
        timeline_factor = next(f for f in result["breakdown"] if f["label"] == "Timeline < 3 months")
        assert timeline_factor["met"] is False

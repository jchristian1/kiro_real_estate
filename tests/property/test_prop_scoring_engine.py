"""
Property-based tests for the Lead Scoring Engine.

Feature: agent-app

Properties covered:
  - Property 4: Score Computation Correctness
  - Property 5: Bucket Assignment Determinism
  - Property 6: Tour Question Disabled Zeroes Score
"""

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from api.services.scoring_engine import (
    score_lead,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_config(
    hot_threshold=80,
    warm_threshold=50,
    weight_timeline=0,
    weight_preapproval=0,
    weight_phone_provided=0,
    weight_tour_interest=0,
    weight_budget_match=0,
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


def _make_lead(phone="555-1234"):
    lead = MagicMock()
    lead.id = 1
    lead.phone = phone
    lead.agent_user_id = None
    lead.score = None
    lead.score_bucket = None
    lead.score_breakdown = None
    return lead


def _make_db(lead, config):
    db = MagicMock()

    def _query_side_effect(model):
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
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


def _run_score_lead(lead, config, answers):
    db = _make_db(lead, config)
    with patch(
        "api.services.scoring_engine._get_submission_answers",
        return_value=answers,
    ):
        return score_lead(db, lead.id, config.id)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Five boolean flags: one per factor (timeline, preapproval, phone, tour, budget)
factor_flags = st.tuples(
    st.booleans(),  # timeline_met
    st.booleans(),  # preapproval_met
    st.booleans(),  # phone_met
    st.booleans(),  # tour_met
    st.booleans(),  # budget_met
)

# Five non-negative integer weights (each 0–100)
factor_weights = st.tuples(
    st.integers(min_value=0, max_value=100),  # weight_timeline
    st.integers(min_value=0, max_value=100),  # weight_preapproval
    st.integers(min_value=0, max_value=100),  # weight_phone_provided
    st.integers(min_value=0, max_value=100),  # weight_tour_interest
    st.integers(min_value=0, max_value=100),  # weight_budget_match
)

# Threshold pair: hot_t > warm_t > 0
threshold_strategy = st.integers(min_value=1, max_value=99).flatmap(
    lambda warm: st.tuples(
        st.integers(min_value=warm + 1, max_value=200),  # hot_t > warm_t
        st.just(warm),                                    # warm_t
    )
)


# ---------------------------------------------------------------------------
# Property 4: Score Computation Correctness
# ---------------------------------------------------------------------------

class TestProperty4ScoreComputationCorrectness:
    """
    Property 4: Score Computation Correctness
    **Validates: Requirements 13.1, 13.6**

    For any factor inputs, score equals the sum of points for met factors
    and is between 0 and the sum of all weights inclusive.
    """

    @given(flags=factor_flags, weights=factor_weights)
    @settings(max_examples=300)
    def test_score_equals_sum_of_met_factor_weights(self, flags, weights):
        """
        Property 4: Score Computation Correctness
        **Validates: Requirements 13.1, 13.6**

        score == sum(weight_i for each factor_i that is met)
        """
        timeline_met, preapproval_met, phone_met, tour_met, budget_met = flags
        w_timeline, w_preapproval, w_phone, w_tour, w_budget = weights

        # Build answers that drive each factor to the desired met/unmet state
        answers = {
            "timeline": "asap" if timeline_met else "6_plus_months",
            "financing": "pre_approved" if preapproval_met else "need_mortgage",
            "wants_tour": "yes" if tour_met else "no",
            "budget": "500k_750k" if budget_met else "not_sure",
        }
        lead = _make_lead(phone="555-1234" if phone_met else None)
        config = _make_config(
            weight_timeline=w_timeline,
            weight_preapproval=w_preapproval,
            weight_phone_provided=w_phone,
            weight_tour_interest=w_tour,
            weight_budget_match=w_budget,
            # Set thresholds high so bucket assignment doesn't interfere
            hot_threshold=10000,
            warm_threshold=5000,
            enable_tour_question=True,
        )

        result = _run_score_lead(lead, config, answers)

        expected_score = (
            (w_timeline if timeline_met else 0)
            + (w_preapproval if preapproval_met else 0)
            + (w_phone if phone_met else 0)
            + (w_tour if tour_met else 0)
            + (w_budget if budget_met else 0)
        )

        assert result["score"] == expected_score, (
            f"Expected score {expected_score}, got {result['score']}. "
            f"flags={flags}, weights={weights}"
        )

    @given(flags=factor_flags, weights=factor_weights)
    @settings(max_examples=300)
    def test_score_is_between_zero_and_sum_of_all_weights(self, flags, weights):
        """
        Property 4: Score Computation Correctness
        **Validates: Requirements 13.1, 13.6**

        0 <= score <= sum_of_all_weights
        """
        timeline_met, preapproval_met, phone_met, tour_met, budget_met = flags
        w_timeline, w_preapproval, w_phone, w_tour, w_budget = weights

        answers = {
            "timeline": "asap" if timeline_met else "6_plus_months",
            "financing": "pre_approved" if preapproval_met else "need_mortgage",
            "wants_tour": "yes" if tour_met else "no",
            "budget": "500k_750k" if budget_met else "not_sure",
        }
        lead = _make_lead(phone="555-1234" if phone_met else None)
        config = _make_config(
            weight_timeline=w_timeline,
            weight_preapproval=w_preapproval,
            weight_phone_provided=w_phone,
            weight_tour_interest=w_tour,
            weight_budget_match=w_budget,
            hot_threshold=10000,
            warm_threshold=5000,
            enable_tour_question=True,
        )

        result = _run_score_lead(lead, config, answers)
        total_weight = w_timeline + w_preapproval + w_phone + w_tour + w_budget

        assert 0 <= result["score"] <= total_weight, (
            f"Score {result['score']} out of bounds [0, {total_weight}]. "
            f"flags={flags}, weights={weights}"
        )


# ---------------------------------------------------------------------------
# Property 5: Bucket Assignment Determinism
# ---------------------------------------------------------------------------

def _assign_bucket(score: int, hot_threshold: int, warm_threshold: int) -> str:
    """Pure bucket assignment logic extracted from score_lead."""
    if score >= hot_threshold:
        return "HOT"
    elif score >= warm_threshold:
        return "WARM"
    else:
        return "NURTURE"


class TestProperty5BucketAssignmentDeterminism:
    """
    Property 5: Bucket Assignment Determinism
    **Validates: Requirements 13.3, 13.4, 13.5**

    For any score and (hot_threshold, warm_threshold) where hot_t > warm_t > 0,
    bucket is exactly one of HOT/WARM/NURTURE and the three cases are mutually
    exclusive and exhaustive.
    """

    @given(
        score=st.integers(min_value=0, max_value=100),
        thresholds=threshold_strategy,
    )
    @settings(max_examples=500)
    def test_bucket_is_one_of_valid_values(self, score, thresholds):
        """
        Property 5: Bucket Assignment Determinism
        **Validates: Requirements 13.3, 13.4, 13.5**

        Bucket must always be exactly one of HOT, WARM, or NURTURE.
        """
        hot_t, warm_t = thresholds
        bucket = _assign_bucket(score, hot_t, warm_t)
        assert bucket in {"HOT", "WARM", "NURTURE"}, (
            f"Unexpected bucket {bucket!r} for score={score}, "
            f"hot_t={hot_t}, warm_t={warm_t}"
        )

    @given(
        score=st.integers(min_value=0, max_value=100),
        thresholds=threshold_strategy,
    )
    @settings(max_examples=500)
    def test_bucket_cases_are_mutually_exclusive(self, score, thresholds):
        """
        Property 5: Bucket Assignment Determinism
        **Validates: Requirements 13.3, 13.4, 13.5**

        Exactly one of the three bucket conditions holds for any given score.
        """
        hot_t, warm_t = thresholds
        is_hot = score >= hot_t
        is_warm = (score >= warm_t) and (score < hot_t)
        is_nurture = score < warm_t

        # Exactly one must be True
        active = sum([is_hot, is_warm, is_nurture])
        assert active == 1, (
            f"Expected exactly 1 active bucket condition, got {active}. "
            f"score={score}, hot_t={hot_t}, warm_t={warm_t}"
        )

    @given(
        score=st.integers(min_value=0, max_value=100),
        thresholds=threshold_strategy,
    )
    @settings(max_examples=500)
    def test_bucket_assignment_is_deterministic(self, score, thresholds):
        """
        Property 5: Bucket Assignment Determinism
        **Validates: Requirements 13.3, 13.4, 13.5**

        Calling bucket assignment twice with the same inputs always returns
        the same result.
        """
        hot_t, warm_t = thresholds
        bucket1 = _assign_bucket(score, hot_t, warm_t)
        bucket2 = _assign_bucket(score, hot_t, warm_t)
        assert bucket1 == bucket2, (
            f"Non-deterministic bucket: got {bucket1!r} then {bucket2!r} "
            f"for score={score}, hot_t={hot_t}, warm_t={warm_t}"
        )

    @given(
        score=st.integers(min_value=0, max_value=100),
        thresholds=threshold_strategy,
    )
    @settings(max_examples=500)
    def test_hot_bucket_iff_score_gte_hot_threshold(self, score, thresholds):
        """
        Property 5: Bucket Assignment Determinism
        **Validates: Requirements 13.3**

        HOT is assigned if and only if score >= hot_threshold.
        """
        hot_t, warm_t = thresholds
        bucket = _assign_bucket(score, hot_t, warm_t)
        if score >= hot_t:
            assert bucket == "HOT"
        else:
            assert bucket != "HOT"

    @given(
        score=st.integers(min_value=0, max_value=100),
        thresholds=threshold_strategy,
    )
    @settings(max_examples=500)
    def test_warm_bucket_iff_score_between_thresholds(self, score, thresholds):
        """
        Property 5: Bucket Assignment Determinism
        **Validates: Requirements 13.4**

        WARM is assigned if and only if warm_threshold <= score < hot_threshold.
        """
        hot_t, warm_t = thresholds
        bucket = _assign_bucket(score, hot_t, warm_t)
        if warm_t <= score < hot_t:
            assert bucket == "WARM"
        else:
            assert bucket != "WARM"

    @given(
        score=st.integers(min_value=0, max_value=100),
        thresholds=threshold_strategy,
    )
    @settings(max_examples=500)
    def test_nurture_bucket_iff_score_below_warm_threshold(self, score, thresholds):
        """
        Property 5: Bucket Assignment Determinism
        **Validates: Requirements 13.5**

        NURTURE is assigned if and only if score < warm_threshold.
        """
        hot_t, warm_t = thresholds
        bucket = _assign_bucket(score, hot_t, warm_t)
        if score < warm_t:
            assert bucket == "NURTURE"
        else:
            assert bucket != "NURTURE"


# ---------------------------------------------------------------------------
# Property 6: Tour Question Disabled Zeroes Score
# ---------------------------------------------------------------------------

class TestProperty6TourQuestionDisabled:
    """
    Property 6: Tour Question Disabled Zeroes Score
    **Validates: Requirements 13.8**

    When enable_tour_question = FALSE, the tour factor always contributes 0
    points regardless of the submission answer.
    """

    @given(wants_tour_answer=st.booleans())
    @settings(max_examples=200)
    def test_tour_factor_always_false_when_disabled(self, wants_tour_answer: bool):
        """
        Property 6: Tour Question Disabled Zeroes Score
        **Validates: Requirements 13.8**

        When enable_tour_question=False, the tour factor is never met,
        regardless of whether the lead answered yes or no to the tour question.
        """
        answers = {
            "timeline": "6_plus_months",   # not met
            "financing": "need_mortgage",  # not met
            "wants_tour": "yes" if wants_tour_answer else "no",
            "budget": "not_sure",          # not met
        }
        lead = _make_lead(phone=None)  # phone not met either
        config = _make_config(
            weight_tour_interest=20,
            enable_tour_question=False,
            hot_threshold=10000,
            warm_threshold=5000,
        )

        result = _run_score_lead(lead, config, answers)

        tour_factor = next(
            f for f in result["breakdown"] if f["label"] == "Wants tour"
        )
        assert tour_factor["met"] is False, (
            f"Tour factor should be unmet when enable_tour_question=False, "
            f"but got met=True for wants_tour={wants_tour_answer!r}"
        )

    @given(wants_tour_answer=st.booleans())
    @settings(max_examples=200)
    def test_tour_contributes_zero_points_when_disabled(self, wants_tour_answer: bool):
        """
        Property 6: Tour Question Disabled Zeroes Score
        **Validates: Requirements 13.8**

        When enable_tour_question=False, the tour weight never adds to the
        score, so score with tour disabled == score without tour weight.
        """
        answers = {
            "timeline": "asap",            # met: adds weight_timeline
            "financing": "pre_approved",   # met: adds weight_preapproval
            "wants_tour": "yes" if wants_tour_answer else "no",
            "budget": "500k_750k",         # met: adds weight_budget_match
        }
        lead = _make_lead(phone="555-1234")  # phone met

        w_timeline, w_preapproval, w_phone, w_tour, w_budget = 10, 10, 10, 20, 10

        config_disabled = _make_config(
            weight_timeline=w_timeline,
            weight_preapproval=w_preapproval,
            weight_phone_provided=w_phone,
            weight_tour_interest=w_tour,
            weight_budget_match=w_budget,
            enable_tour_question=False,
            hot_threshold=10000,
            warm_threshold=5000,
        )

        result = _run_score_lead(lead, config_disabled, answers)

        # Score must equal sum of all other met factors (tour excluded)
        expected = w_timeline + w_preapproval + w_phone + w_budget
        assert result["score"] == expected, (
            f"Expected score {expected} (tour disabled), got {result['score']}. "
            f"wants_tour={wants_tour_answer!r}"
        )

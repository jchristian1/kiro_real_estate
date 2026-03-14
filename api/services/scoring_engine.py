"""
Lead Scoring Engine for the Agent-Facing Web Application.

Evaluates five buyer qualification factors using a BuyerAutomationConfig's
weights, assigns a HOT/WARM/NURTURE bucket, persists results to the lead
record, and inserts a LEAD_SCORED event.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from gmail_lead_sync.agent_models import BuyerAutomationConfig, LeadEvent
from gmail_lead_sync.models import Lead


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_submission_answers(db: Session, lead_id: int) -> Optional[dict]:
    """
    Retrieve the most recent form submission answers for a lead as a flat dict.

    Returns a dict mapping question_key → answer_value (str), or None if no
    submission exists.

    The answers come from the preapproval system's form_submissions /
    submission_answers tables.  We import lazily to avoid circular imports.
    """
    try:
        from gmail_lead_sync.preapproval.models_preapproval import (
            FormSubmission,
        )
    except ImportError:
        return None

    submission = (
        db.query(FormSubmission)
        .filter(FormSubmission.lead_id == lead_id)
        .order_by(FormSubmission.submitted_at.desc())
        .first()
    )
    if submission is None:
        return None

    answers: dict[str, str] = {}
    for ans in submission.answers:
        try:
            # answer_value_json is a JSON-encoded string, e.g. '"yes"' or '"1_3_months"'
            answers[ans.question_key] = json.loads(ans.answer_value_json)
        except (json.JSONDecodeError, TypeError):
            answers[ans.question_key] = ans.answer_value_json
    return answers


def _parse_timeline_months(answers: dict) -> Optional[int]:
    """
    Convert the 'timeline' answer to an approximate number of months.

    Mapping:
      asap          → 0
      1_3_months    → 2
      3_6_months    → 4
      6_plus_months → 9
      not_sure      → None  (treated as no answer)
    """
    timeline_map = {
        "asap": 0,
        "1_3_months": 2,
        "3_6_months": 4,
        "6_plus_months": 9,
    }
    value = answers.get("timeline")
    return timeline_map.get(value)  # returns None for "not_sure" or missing


def _is_preapproved(answers: dict) -> bool:
    """Return True if the financing answer indicates pre-approval or cash."""
    financing = answers.get("financing", "")
    return financing in ("pre_approved", "cash")


def _wants_tour(answers: dict) -> bool:
    """Return True if the wants_tour answer is 'yes'."""
    return answers.get("wants_tour") == "yes"


def _budget_in_range(answers: dict) -> bool:
    """
    Return True if a budget answer was provided and is not 'not_sure'.

    The agent-app scoring model treats any concrete budget selection as
    'budget in range' — the agent's BuyerAutomationConfig does not store
    a specific budget threshold, so we treat any non-null, non-'not_sure'
    budget answer as meeting the factor.
    """
    budget = answers.get("budget")
    return budget is not None and budget != "not_sure"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_lead(db: Session, lead_id: int, buyer_config_id: int) -> dict:
    """
    Evaluate five buyer qualification factors, compute a score, assign a
    HOT/WARM/NURTURE bucket, persist results to the lead record, and insert
    a LEAD_SCORED event.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.
    lead_id:
        Primary key of the lead to score.
    buyer_config_id:
        Primary key of the BuyerAutomationConfig to use for weights and
        thresholds.

    Returns
    -------
    dict with keys:
        score     (int)   — total score, 0–100
        bucket    (str)   — "HOT", "WARM", or "NURTURE"
        breakdown (list)  — one dict per factor:
                            {label, points, met}

    Raises
    ------
    ValueError
        If the lead or config is not found.
    """
    # ------------------------------------------------------------------
    # 1. Load lead and config
    # ------------------------------------------------------------------
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")

    config = (
        db.query(BuyerAutomationConfig)
        .filter(BuyerAutomationConfig.id == buyer_config_id)
        .first()
    )
    if config is None:
        raise ValueError(f"BuyerAutomationConfig {buyer_config_id} not found")

    # ------------------------------------------------------------------
    # 2. Load form submission answers (may be None)
    # ------------------------------------------------------------------
    answers = _get_submission_answers(db, lead_id)

    # ------------------------------------------------------------------
    # 3. Evaluate factors
    # ------------------------------------------------------------------
    score = 0
    breakdown = []

    # Factor 1: Timeline urgency
    if answers is not None:
        months = _parse_timeline_months(answers)
        timeline_met = months is not None and months <= 3
    else:
        timeline_met = False

    if timeline_met:
        score += config.weight_timeline
        breakdown.append({
            "label": "Timeline < 3 months",
            "points": config.weight_timeline,
            "met": True,
        })
    else:
        breakdown.append({
            "label": "Timeline < 3 months",
            "points": config.weight_timeline,
            "met": False,
        })

    # Factor 2: Pre-approval status
    preapproval_met = answers is not None and _is_preapproved(answers)
    if preapproval_met:
        score += config.weight_preapproval
        breakdown.append({
            "label": "Pre-approved",
            "points": config.weight_preapproval,
            "met": True,
        })
    else:
        breakdown.append({
            "label": "Pre-approved",
            "points": config.weight_preapproval,
            "met": False,
        })

    # Factor 3: Phone provided (from lead record, not submission)
    phone_met = bool(lead.phone and len(lead.phone.strip()) > 0)
    if phone_met:
        score += config.weight_phone_provided
        breakdown.append({
            "label": "Phone provided",
            "points": config.weight_phone_provided,
            "met": True,
        })
    else:
        breakdown.append({
            "label": "Phone provided",
            "points": config.weight_phone_provided,
            "met": False,
        })

    # Factor 4: Tour interest
    # When enable_tour_question = FALSE, this factor always contributes 0 points
    # (Requirement 13.8)
    if config.enable_tour_question and answers is not None and _wants_tour(answers):
        score += config.weight_tour_interest
        breakdown.append({
            "label": "Wants tour",
            "points": config.weight_tour_interest,
            "met": True,
        })
    else:
        breakdown.append({
            "label": "Wants tour",
            "points": config.weight_tour_interest,
            "met": False,
        })

    # Factor 5: Budget match
    budget_met = answers is not None and _budget_in_range(answers)
    if budget_met:
        score += config.weight_budget_match
        breakdown.append({
            "label": "Budget in range",
            "points": config.weight_budget_match,
            "met": True,
        })
    else:
        breakdown.append({
            "label": "Budget in range",
            "points": config.weight_budget_match,
            "met": False,
        })

    # ------------------------------------------------------------------
    # 4. Determine bucket (Requirements 13.3, 13.4, 13.5)
    # ------------------------------------------------------------------
    if score >= config.hot_threshold:
        bucket = "HOT"
    elif score >= config.warm_threshold:
        bucket = "WARM"
    else:
        bucket = "NURTURE"

    # ------------------------------------------------------------------
    # 5. Persist to lead record (Requirement 13.7)
    # ------------------------------------------------------------------
    lead.score = score
    lead.score_bucket = bucket
    lead.score_breakdown = json.dumps(breakdown)

    # ------------------------------------------------------------------
    # 6. Insert LEAD_SCORED event (Requirements 13.7, 20.4)
    # ------------------------------------------------------------------
    event = LeadEvent(
        lead_id=lead_id,
        agent_user_id=getattr(lead, "agent_user_id", None),
        event_type="LEAD_SCORED",
        payload=json.dumps({"score": score, "bucket": bucket, "breakdown": breakdown}),
        created_at=datetime.utcnow(),
    )
    db.add(event)
    db.flush()

    return {"score": score, "bucket": bucket, "breakdown": breakdown}

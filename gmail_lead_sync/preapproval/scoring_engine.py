"""
ScoringEngine: applies versioned tenant scoring rules to a submission's answers
and returns a structured ScoreResult.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from gmail_lead_sync.preapproval.models_preapproval import Bucket, ScoringVersion

logger = logging.getLogger(__name__)

# Sentinel constants
_SENTINEL_ANY_RANGE = "__any_range__"
_SENTINEL_PRESENT = "__present__"


@dataclass
class ScoreBreakdownItem:
    """One matched rule entry in the score breakdown."""

    question_key: str
    answer: Any
    points: int
    reason: str


@dataclass
class ScoreResult:
    """Full result of a scoring computation."""

    total: int
    bucket: Bucket
    breakdown: list[ScoreBreakdownItem] = field(default_factory=list)
    explanation: str = ""


def _matches(actual: Any, answer_value: Any) -> bool:
    """
    Return True if *actual* satisfies *answer_value*.

    Sentinel rules:
    - ``__any_range__``: matches any value that is not ``"not_sure"`` and not None/empty.
    - ``__present__``:   matches any non-None, non-empty value (for metadata fields).
    - Otherwise:         exact equality.
    """
    if answer_value == _SENTINEL_ANY_RANGE:
        # Req 5.8: match any non-"not_sure" answer value
        if actual is None:
            return False
        if isinstance(actual, str) and (actual == "not_sure" or actual == ""):
            return False
        return True

    if answer_value == _SENTINEL_PRESENT:
        # Req 5.9: match any non-null, non-empty metadata value
        if actual is None:
            return False
        if isinstance(actual, str) and actual == "":
            return False
        if isinstance(actual, (list, dict)) and len(actual) == 0:
            return False
        return True

    # Exact match
    return actual == answer_value


def _build_explanation(bucket: Bucket, breakdown: list[ScoreBreakdownItem], total: int) -> str:
    """Produce a human-readable summary of the scoring result."""
    if not breakdown:
        return f"No scoring rules matched. Total score: {total}. Bucket: {bucket.value}."

    reasons = "; ".join(item.reason for item in breakdown)
    return (
        f"Total score: {total}. Bucket: {bucket.value}. "
        f"Matched {len(breakdown)} rule(s): {reasons}."
    )


class ScoringEngine:
    """
    Evaluates all rules in a ScoringVersion against submission answers and
    metadata, then assigns a HOT/WARM/NURTURE bucket based on thresholds.
    """

    def compute(
        self,
        answers: dict[str, Any],
        scoring_version: ScoringVersion,
        metadata: dict[str, Any],
    ) -> ScoreResult:
        """
        Compute a ScoreResult for the given answers and metadata.

        Args:
            answers:         Dict of question_key → answer value from the submission.
            scoring_version: Active ScoringVersion ORM object (rules_json, thresholds_json).
            metadata:        Extra lead metadata (lead_source, property_address, etc.).

        Returns:
            ScoreResult with total, bucket, breakdown, and explanation.

        Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10
        """
        rules: list[dict] = json.loads(scoring_version.rules_json)
        thresholds: dict[str, int] = json.loads(scoring_version.thresholds_json)

        total = 0
        breakdown: list[ScoreBreakdownItem] = []

        for rule in rules:
            source: str = rule.get("source", "answer")
            key: str = rule["key"]
            answer_value = rule["answer_value"]
            points: int = rule["points"]          # Req 5.10: may be negative
            reason: str = rule.get("reason", "")

            # Resolve actual value from the correct source
            if source == "answer":
                actual = answers.get(key)
            else:
                actual = metadata.get(key)

            if _matches(actual, answer_value):
                total += points                   # Req 5.2, 5.10
                breakdown.append(
                    ScoreBreakdownItem(
                        question_key=key,
                        answer=actual,
                        points=points,
                        reason=reason,
                    )
                )

        # Req 5.7: sum(breakdown.points) == total  (invariant maintained by construction)

        # Determine bucket — Req 5.3, 5.4, 5.5
        hot_threshold: int = thresholds["HOT"]
        warm_threshold: int = thresholds["WARM"]

        if total >= hot_threshold:
            bucket = Bucket.HOT
        elif total >= warm_threshold:
            bucket = Bucket.WARM
        else:
            bucket = Bucket.NURTURE

        explanation = _build_explanation(bucket, breakdown, total)

        return ScoreResult(
            total=total,
            bucket=bucket,
            breakdown=breakdown,
            explanation=explanation,
        )

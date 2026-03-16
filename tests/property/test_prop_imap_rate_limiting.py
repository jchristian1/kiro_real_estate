"""
Property-based tests for IMAP rate limiting.

Feature: agent-app

**Property 13: IMAP Rate Limiting** — for any agent, the 6th attempt within a
15-minute window always returns 429 with `error: "RATE_LIMITED"`.

**Validates: Requirements 5.7**
"""

import pytest
from hypothesis import given, settings, strategies as st

from api.services.imap_service import (
    IMAPRateLimitError,
    RATE_LIMIT_MAX_ATTEMPTS,
    check_and_record_imap_attempt,
    reset_imap_rate_limit,
)

# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------

agent_ids = st.integers(min_value=1, max_value=10000)


# ---------------------------------------------------------------------------
# Property 13: IMAP Rate Limiting
# ---------------------------------------------------------------------------


class TestProperty13IMAPRateLimiting:
    """
    Property 13: IMAP Rate Limiting
    **Validates: Requirements 5.7**
    """

    @given(agent_user_id=agent_ids)
    @settings(max_examples=50)
    def test_first_five_attempts_always_succeed(self, agent_user_id: int):
        """
        Property 13: IMAP Rate Limiting
        **Validates: Requirements 5.7**

        For any agent_user_id, the first 5 attempts within a 15-minute window
        must never raise an exception.
        """
        reset_imap_rate_limit(agent_user_id)
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            check_and_record_imap_attempt(agent_user_id)  # must not raise

    @given(agent_user_id=agent_ids)
    @settings(max_examples=50)
    def test_sixth_attempt_always_raises_rate_limit_error(self, agent_user_id: int):
        """
        Property 13: IMAP Rate Limiting
        **Validates: Requirements 5.7**

        For any agent_user_id, the 6th attempt within a 15-minute window must
        always raise IMAPRateLimitError.
        """
        reset_imap_rate_limit(agent_user_id)
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            check_and_record_imap_attempt(agent_user_id)

        with pytest.raises(IMAPRateLimitError):
            check_and_record_imap_attempt(agent_user_id)

    @given(agent_user_id=agent_ids)
    @settings(max_examples=50)
    def test_retry_after_seconds_always_positive(self, agent_user_id: int):
        """
        Property 13: IMAP Rate Limiting
        **Validates: Requirements 5.7**

        For any agent_user_id, the retry_after_seconds on the raised
        IMAPRateLimitError is always > 0.
        """
        reset_imap_rate_limit(agent_user_id)
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            check_and_record_imap_attempt(agent_user_id)

        try:
            check_and_record_imap_attempt(agent_user_id)
            pytest.fail("Expected IMAPRateLimitError was not raised")
        except IMAPRateLimitError as exc:
            assert exc.retry_after_seconds > 0, (
                f"retry_after_seconds must be > 0, got {exc.retry_after_seconds}"
            )

    @given(
        agent_a=agent_ids,
        agent_b=agent_ids,
    )
    @settings(max_examples=50)
    def test_different_agents_have_independent_windows(
        self, agent_a: int, agent_b: int
    ):
        """
        Property 13: IMAP Rate Limiting
        **Validates: Requirements 5.7**

        Different agent IDs have independent rate limit windows — exhausting
        agent A's limit must not affect agent B (when A != B).
        """
        # When both IDs are the same, skip — same agent, same window
        if agent_a == agent_b:
            return

        reset_imap_rate_limit(agent_a)
        reset_imap_rate_limit(agent_b)

        # Exhaust agent_a's limit
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            check_and_record_imap_attempt(agent_a)

        # agent_b's first attempt must still succeed
        check_and_record_imap_attempt(agent_b)  # must not raise

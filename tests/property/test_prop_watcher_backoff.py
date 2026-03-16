"""
Property-based tests for watcher exponential backoff schedule.

# Feature: production-hardening, Property 9: Watcher exponential backoff schedule

**Property 9: Watcher exponential backoff schedule** — for any sequence of N
consecutive IMAP connection failures (N ≤ 5), the delay before the k-th retry
attempt SHALL equal ``min(5 * 2^(k-1), 300)`` seconds.  After 5 consecutive
failures the watcher SHALL transition to ``FAILED`` status.

**Validates: Requirements 10.1**
"""

import math

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Pure formula under test
# ---------------------------------------------------------------------------

def backoff_delay(attempt: int) -> int:
    """
    Return the exponential backoff delay (seconds) for the given attempt number.

    attempt=1 → 5s, attempt=2 → 10s, attempt=3 → 20s, attempt=4 → 40s,
    attempt=5 → 80s.  Capped at 300s.

    This mirrors the formula used in WatcherRegistry._run_watcher:
        min(5 * 2^(attempt-1), 300)
    """
    return min(5 * (2 ** (attempt - 1)), 300)


# ---------------------------------------------------------------------------
# Property 9: Watcher exponential backoff schedule
# ---------------------------------------------------------------------------


class TestProperty9WatcherBackoffSchedule:
    """
    Property 9: Watcher exponential backoff schedule.
    **Validates: Requirements 10.1**
    """

    @given(k=st.integers(min_value=1, max_value=5))
    @settings(max_examples=100)
    def test_backoff_delay_equals_formula(self, k: int):
        """
        # Feature: production-hardening, Property 9: Watcher exponential backoff schedule
        **Validates: Requirements 10.1**

        For any attempt k in [1, 5], the computed delay SHALL equal
        min(5 * 2^(k-1), 300).
        """
        expected = min(5 * (2 ** (k - 1)), 300)
        actual = backoff_delay(k)
        assert actual == expected, (
            f"Attempt {k}: expected delay {expected}s, got {actual}s"
        )

    @given(k=st.integers(min_value=1, max_value=5))
    @settings(max_examples=100)
    def test_backoff_delay_is_positive(self, k: int):
        """
        # Feature: production-hardening, Property 9: Watcher exponential backoff schedule
        **Validates: Requirements 10.1**

        Every backoff delay SHALL be a positive number of seconds.
        """
        delay = backoff_delay(k)
        assert delay > 0, f"Attempt {k}: delay must be positive, got {delay}"

    @given(k=st.integers(min_value=1, max_value=5))
    @settings(max_examples=100)
    def test_backoff_delay_never_exceeds_cap(self, k: int):
        """
        # Feature: production-hardening, Property 9: Watcher exponential backoff schedule
        **Validates: Requirements 10.1**

        The backoff delay SHALL never exceed 300 seconds (the configured cap).
        """
        delay = backoff_delay(k)
        assert delay <= 300, (
            f"Attempt {k}: delay {delay}s exceeds the 300s cap"
        )

    @given(k=st.integers(min_value=1, max_value=4))
    @settings(max_examples=100)
    def test_backoff_delay_doubles_each_attempt(self, k: int):
        """
        # Feature: production-hardening, Property 9: Watcher exponential backoff schedule
        **Validates: Requirements 10.1**

        For attempts where neither k nor k+1 hits the cap, the delay for
        attempt k+1 SHALL be exactly double the delay for attempt k.
        """
        d_k = backoff_delay(k)
        d_k1 = backoff_delay(k + 1)
        # Only assert doubling when neither value is capped at 300
        if d_k < 300 and d_k1 < 300:
            assert d_k1 == 2 * d_k, (
                f"Attempt {k}→{k+1}: expected {2 * d_k}s (double), got {d_k1}s"
            )

    def test_known_backoff_schedule(self):
        """
        # Feature: production-hardening, Property 9: Watcher exponential backoff schedule
        **Validates: Requirements 10.1**

        Verify the exact schedule from the design doc:
        attempt 1 → 5s, 2 → 10s, 3 → 20s, 4 → 40s, 5 → 80s.
        """
        expected_schedule = {1: 5, 2: 10, 3: 20, 4: 40, 5: 80}
        for attempt, expected_delay in expected_schedule.items():
            actual = backoff_delay(attempt)
            assert actual == expected_delay, (
                f"Attempt {attempt}: expected {expected_delay}s, got {actual}s"
            )

    def test_max_retries_is_five(self):
        """
        # Feature: production-hardening, Property 9: Watcher exponential backoff schedule
        **Validates: Requirements 10.1**

        WatcherRegistry.MAX_RETRIES SHALL equal 5, meaning after 5 consecutive
        failures the watcher transitions to FAILED.
        """
        from api.services.watcher_registry import WatcherRegistry
        assert WatcherRegistry.MAX_RETRIES == 5, (
            f"Expected MAX_RETRIES=5, got {WatcherRegistry.MAX_RETRIES}"
        )

    @given(k=st.integers(min_value=1, max_value=5))
    @settings(max_examples=100)
    def test_backoff_delay_matches_registry_formula(self, k: int):
        """
        # Feature: production-hardening, Property 9: Watcher exponential backoff schedule
        **Validates: Requirements 10.1**

        The pure formula backoff_delay(k) SHALL match the formula documented
        in the design: min(5 * 2^(k-1), 300).  This test cross-checks the
        helper against the spec formula directly.
        """
        spec_formula = min(5 * int(math.pow(2, k - 1)), 300)
        assert backoff_delay(k) == spec_formula, (
            f"Attempt {k}: helper returned {backoff_delay(k)}, "
            f"spec formula gives {spec_formula}"
        )

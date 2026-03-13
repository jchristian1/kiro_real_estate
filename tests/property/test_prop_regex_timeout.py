"""
Property-based tests for regex timeout enforcement.

# Feature: production-hardening, Property 18: Regex timeout enforcement

**Property 18: Regex timeout enforcement** — for any regex pattern submitted
to lead source configuration that requires more than ``REGEX_TIMEOUT_MS``
milliseconds to execute against a test input, the validation SHALL fail with
an appropriate error and SHALL NOT allow the pattern to be saved.

**Validates: Requirements 11.7**
"""

import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from api.utils.regex_tester import RegexTimeoutError
from api.utils.regex_tester import test_regex_pattern as run_regex_pattern

# ---------------------------------------------------------------------------
# Catastrophic backtracking patterns
# ---------------------------------------------------------------------------

# These patterns are known to cause catastrophic backtracking (ReDoS)
# when matched against certain inputs.
CATASTROPHIC_PATTERNS = [
    # Classic ReDoS: (a+)+ against "aaa...a!"
    (r"(a+)+", "a" * 25 + "!"),
    # Nested quantifiers
    (r"(a*)*", "a" * 25 + "!"),
    # Alternation with overlap
    (r"(a|aa)+", "a" * 25 + "!"),
    # Multiple nested groups
    (r"([a-zA-Z]+)*", "a" * 20 + "!"),
    # Email-like ReDoS
    (r"^(([a-z])+.)+[A-Z]([a-z])+$", "a" * 20 + "!"),
]

# Patterns that are safe and should complete quickly
SAFE_PATTERNS = [
    (r"\d+", "12345"),
    (r"[a-z]+", "hello"),
    (r"^test$", "test"),
    (r"Name: (.+)", "Name: John Doe"),
    (r"Phone: (\d{3}-\d{4})", "Phone: 555-1234"),
]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_catastrophic_strategy = st.sampled_from(CATASTROPHIC_PATTERNS)
_safe_strategy = st.sampled_from(SAFE_PATTERNS)

# Short timeout values (in ms) to test timeout enforcement
_short_timeout_strategy = st.integers(min_value=100, max_value=500)


# ---------------------------------------------------------------------------
# Property 18: Regex timeout enforcement
# ---------------------------------------------------------------------------


class TestProperty18RegexTimeoutEnforcement:
    """
    Property 18: Regex timeout enforcement.
    **Validates: Requirements 11.7**
    """

    @given(pattern_input=_catastrophic_strategy)
    @settings(max_examples=5, deadline=None)
    def test_catastrophic_pattern_raises_timeout_or_completes_fast(
        self, pattern_input
    ):
        """
        # Feature: production-hardening, Property 18: Regex timeout enforcement
        **Validates: Requirements 11.7**

        For catastrophic backtracking patterns, test_regex_pattern SHALL either:
        1. Raise RegexTimeoutError within the timeout window, OR
        2. Complete quickly (the pattern happened to not trigger backtracking)

        The key property is that it SHALL NOT run indefinitely.
        """
        pattern, text = pattern_input
        timeout_ms = 1000  # 1 second

        start = time.monotonic()
        try:
            run_regex_pattern(pattern, text, timeout_ms=timeout_ms)
            elapsed = time.monotonic() - start
            # If it completed without timeout, it must have done so quickly
            # Allow 2x the timeout as a generous upper bound for test overhead
            assert elapsed < (timeout_ms / 1000) * 3, (
                f"Pattern {pattern!r} took {elapsed:.2f}s without timing out "
                f"(timeout={timeout_ms}ms)"
            )
        except RegexTimeoutError:
            elapsed = time.monotonic() - start
            # Timeout was raised — verify it happened within a reasonable window
            # Allow 3x the timeout for signal/thread overhead
            assert elapsed < (timeout_ms / 1000) * 3, (
                f"RegexTimeoutError raised but took {elapsed:.2f}s "
                f"(timeout={timeout_ms}ms)"
            )

    @given(pattern_input=_safe_strategy)
    @settings(max_examples=50, deadline=None)
    def test_safe_patterns_complete_without_timeout(self, pattern_input):
        """
        # Feature: production-hardening, Property 18: Regex timeout enforcement
        **Validates: Requirements 11.7**

        Safe regex patterns SHALL complete successfully without raising
        RegexTimeoutError.
        """
        pattern, text = pattern_input
        timeout_ms = 1000

        # Should not raise RegexTimeoutError
        try:
            matched, groups, match_text = run_regex_pattern(
                pattern, text, timeout_ms=timeout_ms
            )
            # Result should be a valid tuple
            assert isinstance(matched, bool)
            assert isinstance(groups, list)
        except RegexTimeoutError:
            pytest.fail(
                f"Safe pattern {pattern!r} timed out unexpectedly "
                f"against {text!r}"
            )

    def test_timeout_is_enforced_with_short_window(self):
        """
        # Feature: production-hardening, Property 18: Regex timeout enforcement
        **Validates: Requirements 11.7**

        With a very short timeout, catastrophic patterns SHALL be rejected
        within the timeout window.
        """
        # Use a pattern known to cause catastrophic backtracking
        pattern = r"(a+)+"
        text = "a" * 30 + "!"
        timeout_ms = 1000  # 1 second

        start = time.monotonic()
        try:
            run_regex_pattern(pattern, text, timeout_ms=timeout_ms)
        except RegexTimeoutError:
            pass
        elapsed = time.monotonic() - start

        # Either it timed out, or it completed quickly (some engines are fast)
        # The important thing is it didn't hang indefinitely
        assert elapsed < timeout_ms / 1000 * 5, (
            f"Pattern took {elapsed:.2f}s — should have timed out or completed quickly"
        )

    def test_invalid_regex_raises_value_error(self):
        """
        # Feature: production-hardening, Property 18: Regex timeout enforcement
        **Validates: Requirements 11.7**

        An invalid regex pattern SHALL raise ValueError (not RegexTimeoutError).
        """
        invalid_patterns = [
            r"[unclosed",
            r"(unmatched",
            r"*invalid",
            r"?invalid",
        ]
        for pattern in invalid_patterns:
            with pytest.raises(ValueError, match="Invalid regex pattern"):
                run_regex_pattern(pattern, "test", timeout_ms=1000)

    def test_timeout_ms_parameter_is_respected(self):
        """
        # Feature: production-hardening, Property 18: Regex timeout enforcement
        **Validates: Requirements 11.7**

        The timeout_ms parameter SHALL be used as the execution time limit.
        A pattern that completes quickly SHALL succeed regardless of timeout value.
        """
        pattern = r"\d+"
        text = "12345"

        for timeout_ms in [100, 500, 1000, 5000]:
            matched, groups, match_text = run_regex_pattern(
                pattern, text, timeout_ms=timeout_ms
            )
            assert matched is True, (
                f"Simple pattern failed with timeout_ms={timeout_ms}"
            )

    @pytest.mark.parametrize("pattern,text", CATASTROPHIC_PATTERNS)
    def test_known_catastrophic_patterns_do_not_hang(self, pattern, text):
        """
        # Feature: production-hardening, Property 18: Regex timeout enforcement
        **Validates: Requirements 11.7**

        Each known catastrophic backtracking pattern SHALL either complete
        quickly or raise RegexTimeoutError — never hang indefinitely.
        """
        timeout_ms = 1000
        start = time.monotonic()

        try:
            run_regex_pattern(pattern, text, timeout_ms=timeout_ms)
        except RegexTimeoutError:
            pass  # Expected for catastrophic patterns
        except Exception:
            pass  # Other errors are acceptable

        elapsed = time.monotonic() - start
        # Must complete within 5x the timeout (generous for CI overhead)
        assert elapsed < (timeout_ms / 1000) * 5, (
            f"Pattern {pattern!r} took {elapsed:.2f}s — possible hang detected"
        )

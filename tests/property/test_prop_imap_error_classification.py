"""
Property-based tests for IMAP error classification.

Feature: agent-app

**Property 14: IMAP Error Classification** — for any error message string,
`classify_imap_error()` returns a value from the fixed safe enumeration and
never returns the raw message.

**Validates: Requirements 5.3, 5.4, 5.5, 5.6**
"""

from hypothesis import given, settings, strategies as st

from api.services.imap_service import (
    classify_imap_error,
    ERROR_IMAP_DISABLED,
    ERROR_TWO_FACTOR_REQUIRED,
    ERROR_INVALID_PASSWORD,
    ERROR_RATE_LIMITED,
    ERROR_CONNECTION_FAILED,
)

# The complete fixed safe enumeration
VALID_ERROR_CODES = frozenset({
    ERROR_IMAP_DISABLED,
    ERROR_TWO_FACTOR_REQUIRED,
    ERROR_INVALID_PASSWORD,
    ERROR_RATE_LIMITED,
    ERROR_CONNECTION_FAILED,
})


class TestProperty14IMAPErrorClassification:
    """
    Property 14: IMAP Error Classification
    **Validates: Requirements 5.3, 5.4, 5.5, 5.6**
    """

    @given(raw_message=st.text())
    @settings(max_examples=500)
    def test_always_returns_valid_error_code(self, raw_message: str):
        """
        Property 14: IMAP Error Classification
        **Validates: Requirements 5.3, 5.4, 5.5, 5.6**

        For any arbitrary string input, `classify_imap_error()` must always
        return one of the 5 fixed error codes — never anything else.
        """
        result = classify_imap_error(raw_message)
        assert result in VALID_ERROR_CODES, (
            f"classify_imap_error({raw_message!r}) returned {result!r}, "
            f"which is not in the fixed safe enumeration {VALID_ERROR_CODES}"
        )

    @given(raw_message=st.text())
    @settings(max_examples=500)
    def test_never_returns_raw_message(self, raw_message: str):
        """
        Property 14: IMAP Error Classification
        **Validates: Requirements 5.3, 5.4, 5.5, 5.6**

        For any arbitrary string input, the return value must never equal the
        raw input message — the raw error is always replaced by a safe code.
        """
        result = classify_imap_error(raw_message)
        assert result != raw_message, (
            f"classify_imap_error({raw_message!r}) returned the raw message verbatim"
        )

    @given(raw_message=st.text())
    @settings(max_examples=500)
    def test_always_returns_non_empty_string(self, raw_message: str):
        """
        Property 14: IMAP Error Classification
        **Validates: Requirements 5.3, 5.4, 5.5, 5.6**

        For any arbitrary string input, the return value is always a non-empty
        string — the function never returns None, empty string, or a non-string.
        """
        result = classify_imap_error(raw_message)
        assert isinstance(result, str), (
            f"classify_imap_error({raw_message!r}) returned non-string: {result!r}"
        )
        assert len(result) > 0, (
            f"classify_imap_error({raw_message!r}) returned an empty string"
        )

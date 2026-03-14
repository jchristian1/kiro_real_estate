"""
Property-based tests for agent session token generation.

Feature: agent-app

**Property 22: Session Token Uniqueness** — any two generated session tokens
are different and are exactly 64 bytes (128 hex characters).

**Validates: Requirements 2.6**
"""

import re
import secrets

from hypothesis import given, settings, strategies as st

# Must match AGENT_SESSION_TOKEN_BYTES in api/routers/agent_auth.py
AGENT_SESSION_TOKEN_BYTES = 64


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_token() -> str:
    """Generate a session token using the same method as the auth router."""
    return secrets.token_hex(AGENT_SESSION_TOKEN_BYTES)


_HEX_PATTERN = re.compile(r"^[0-9a-f]+$")


# ── Property 22: Session Token Uniqueness ─────────────────────────────────────

class TestProperty22SessionTokenUniqueness:
    """
    Property 22: Session Token Uniqueness
    **Validates: Requirements 2.6**

    Any generated session token must be:
    1. Exactly 128 characters long (64 bytes hex-encoded)
    2. Composed entirely of valid hex characters (0-9, a-f)
    3. Unique — any two independently generated tokens are different
    """

    @given(n=st.integers(min_value=2, max_value=50))
    @settings(max_examples=100)
    def test_tokens_are_correct_length(self, n: int):
        """
        Property 22: Session Token Uniqueness
        **Validates: Requirements 2.6**

        Every token in a batch of n tokens must be exactly 128 characters
        (64 bytes represented as a hex string).
        """
        tokens = [_generate_token() for _ in range(n)]
        for token in tokens:
            assert len(token) == AGENT_SESSION_TOKEN_BYTES * 2, (
                f"Expected token length {AGENT_SESSION_TOKEN_BYTES * 2}, got {len(token)}"
            )

    @given(n=st.integers(min_value=2, max_value=50))
    @settings(max_examples=100)
    def test_tokens_are_valid_hex(self, n: int):
        """
        Property 22: Session Token Uniqueness
        **Validates: Requirements 2.6**

        Every token must consist only of lowercase hex characters (0-9, a-f).
        """
        tokens = [_generate_token() for _ in range(n)]
        for token in tokens:
            assert _HEX_PATTERN.match(token), (
                f"Token contains non-hex characters: {token!r}"
            )

    @given(n=st.integers(min_value=2, max_value=50))
    @settings(max_examples=100)
    def test_tokens_are_unique(self, n: int):
        """
        Property 22: Session Token Uniqueness
        **Validates: Requirements 2.6**

        Any batch of n independently generated tokens must all be distinct —
        no two tokens in the batch may be equal.
        """
        tokens = [_generate_token() for _ in range(n)]
        assert len(tokens) == len(set(tokens)), (
            f"Duplicate tokens found in batch of {n}"
        )

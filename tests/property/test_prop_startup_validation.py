"""
Property-based tests for startup secret validation.

Feature: production-hardening

# Feature: production-hardening, Property 1: Startup rejects short or absent secrets

**Property 1: Startup rejects short or absent secrets** — for any value of
`ENCRYPTION_KEY` or `SECRET_KEY` that is absent or shorter than 32 characters,
the configuration loader SHALL raise a `ValueError` and the application SHALL
NOT start successfully.

**Validates: Requirements 1.4, 4.4**
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from api.config import Config


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Short key: 0–31 characters (never reaches the 32-char minimum)
_SHORT_KEY = st.text(max_size=31)

# Valid key: exactly 32+ characters (used as the "good" counterpart)
_VALID_KEY = st.text(min_size=32, max_size=64)


# ---------------------------------------------------------------------------
# Property 1: Startup rejects short or absent secrets
# ---------------------------------------------------------------------------


class TestProperty1StartupRejectsShortOrAbsentSecrets:
    """
    Property 1: Config.__post_init__ raises ValueError whenever ENCRYPTION_KEY
    or SECRET_KEY is absent (empty string / None) or shorter than 32 characters.
    """

    @given(short_key=_SHORT_KEY, valid_key=_VALID_KEY)
    @settings(max_examples=100)
    def test_short_encryption_key_raises(self, short_key: str, valid_key: str):
        """
        For any ENCRYPTION_KEY shorter than 32 chars, Config raises ValueError.
        """
        # Feature: production-hardening, Property 1: Startup rejects short or absent secrets
        with pytest.raises(ValueError):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key=short_key,
                secret_key=valid_key,
            )

    @given(short_key=_SHORT_KEY, valid_key=_VALID_KEY)
    @settings(max_examples=100)
    def test_short_secret_key_raises(self, short_key: str, valid_key: str):
        """
        For any SECRET_KEY shorter than 32 chars, Config raises ValueError.
        """
        # Feature: production-hardening, Property 1: Startup rejects short or absent secrets
        with pytest.raises(ValueError):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key=valid_key,
                secret_key=short_key,
            )

    @given(valid_key=_VALID_KEY)
    @settings(max_examples=100)
    def test_absent_encryption_key_raises(self, valid_key: str):
        """
        When ENCRYPTION_KEY is empty (absent), Config raises ValueError.
        """
        # Feature: production-hardening, Property 1: Startup rejects short or absent secrets
        with pytest.raises(ValueError):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key="",
                secret_key=valid_key,
            )

    @given(valid_key=_VALID_KEY)
    @settings(max_examples=100)
    def test_absent_secret_key_raises(self, valid_key: str):
        """
        When SECRET_KEY is empty (absent), Config raises ValueError.
        """
        # Feature: production-hardening, Property 1: Startup rejects short or absent secrets
        with pytest.raises(ValueError):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key=valid_key,
                secret_key="",
            )

    @given(enc_key=_SHORT_KEY, sec_key=_SHORT_KEY)
    @settings(max_examples=100)
    def test_both_keys_short_raises(self, enc_key: str, sec_key: str):
        """
        When both keys are short, Config raises ValueError.
        """
        # Feature: production-hardening, Property 1: Startup rejects short or absent secrets
        with pytest.raises(ValueError):
            Config(
                database_url="sqlite:///./test.db",
                encryption_key=enc_key,
                secret_key=sec_key,
            )

    @given(valid_enc=_VALID_KEY, valid_sec=_VALID_KEY)
    @settings(max_examples=100)
    def test_valid_keys_do_not_raise(self, valid_enc: str, valid_sec: str):
        """
        When both keys are at least 32 chars, Config initialises without error.
        """
        # Feature: production-hardening, Property 1: Startup rejects short or absent secrets
        config = Config(
            database_url="sqlite:///./test.db",
            encryption_key=valid_enc,
            secret_key=valid_sec,
        )
        assert len(config.encryption_key) >= 32
        assert len(config.secret_key) >= 32

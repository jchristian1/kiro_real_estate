"""
Property-based tests for credential encryption service.

Feature: agent-app

**Property 3: Encryption Round-Trip** — for any non-empty string,
encrypt then decrypt returns the original value exactly.

**Validates: Requirements 19.5**
"""

import base64
import secrets

import pytest
from hypothesis import given, settings, strategies as st

from api.services.credential_encryption import (
    ENV_VAR_NAME,
    decrypt_app_password,
    encrypt_app_password,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_key() -> str:
    """Return a fresh valid base64-encoded 32-byte AES-256 key."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_encryption_key(monkeypatch):
    """Set a valid CREDENTIAL_ENCRYPTION_KEY for every test in this module."""
    monkeypatch.setenv(ENV_VAR_NAME, _make_key())


# ── Property 3: Encryption Round-Trip ────────────────────────────────────────

class TestProperty3EncryptionRoundTrip:
    """
    Property 3: Encryption Round-Trip
    **Validates: Requirements 19.5**

    For any non-empty string s, decrypt_app_password(encrypt_app_password(s)) == s.
    This must hold for arbitrary Unicode text, not just ASCII passwords.
    """

    @given(plaintext=st.text(min_size=1))
    @settings(max_examples=200)
    def test_round_trip_returns_original(self, plaintext):
        """
        Property 3: Encryption Round-Trip
        **Validates: Requirements 19.5**

        Encrypting then decrypting any non-empty string must return the
        original value exactly.
        """
        ciphertext = encrypt_app_password(plaintext)
        recovered = decrypt_app_password(ciphertext)
        assert recovered == plaintext

    @given(plaintext=st.text(min_size=1))
    @settings(max_examples=100)
    def test_nonce_uniqueness_different_ciphertexts(self, plaintext):
        """
        Nonce Uniqueness: encrypting the same plaintext twice must produce
        different ciphertexts (IND-CPA security via fresh random nonce).
        **Validates: Requirements 19.5**
        """
        ct1 = encrypt_app_password(plaintext)
        ct2 = encrypt_app_password(plaintext)
        assert ct1 != ct2

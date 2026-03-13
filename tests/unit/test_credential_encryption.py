"""
Unit tests for api/services/credential_encryption.py

Tests cover:
- encrypt_app_password / decrypt_app_password round-trip
- Error handling: missing env var, bad key, empty inputs, tampered ciphertext
- SecretStr usage in Pydantic models (no plaintext leakage)
- generate_key helper
"""

import base64
import secrets

import pytest
from pydantic import ValidationError

from api.services.credential_encryption import (
    ENV_VAR_NAME,
    decrypt_app_password,
    encrypt_app_password,
    generate_key,
    GmailConnectionRequest,
    GmailCredentialUpdateRequest,
    GmailConnectionResponse,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _valid_key() -> str:
    """Return a fresh valid base64-encoded 32-byte key."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    """Ensure the encryption key env var is unset before each test."""
    monkeypatch.delenv(ENV_VAR_NAME, raising=False)


@pytest.fixture()
def set_valid_key(monkeypatch):
    """Set a valid CREDENTIAL_ENCRYPTION_KEY and return its value."""
    key = _valid_key()
    monkeypatch.setenv(ENV_VAR_NAME, key)
    return key


# ── encrypt_app_password ──────────────────────────────────────────────────────

class TestEncryptAppPassword:
    def test_returns_non_empty_string(self, set_valid_key):
        result = encrypt_app_password("mysecretpassword")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_output_is_valid_base64(self, set_valid_key):
        result = encrypt_app_password("mysecretpassword")
        # Should not raise
        decoded = base64.b64decode(result)
        assert len(decoded) > 12  # nonce (12) + at least 1 byte ciphertext + 16 tag

    def test_same_plaintext_produces_different_ciphertexts(self, set_valid_key):
        """Each call uses a fresh nonce — ciphertexts must differ."""
        ct1 = encrypt_app_password("same_password")
        ct2 = encrypt_app_password("same_password")
        assert ct1 != ct2

    def test_raises_on_empty_plaintext(self, set_valid_key):
        with pytest.raises(ValueError, match="non-empty"):
            encrypt_app_password("")

    def test_raises_when_env_var_missing(self):
        with pytest.raises(EnvironmentError, match=ENV_VAR_NAME):
            encrypt_app_password("password")

    def test_raises_when_key_is_wrong_length(self, monkeypatch):
        # 16 bytes instead of 32
        short_key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        monkeypatch.setenv(ENV_VAR_NAME, short_key)
        with pytest.raises(EnvironmentError, match="32 bytes"):
            encrypt_app_password("password")

    def test_raises_when_key_is_not_base64(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR_NAME, "not-valid-base64!!!")
        with pytest.raises(EnvironmentError, match="not valid base64"):
            encrypt_app_password("password")

    def test_plaintext_not_in_ciphertext(self, set_valid_key):
        """The raw plaintext must not appear in the ciphertext string."""
        plaintext = "super_secret_app_password"
        ct = encrypt_app_password(plaintext)
        assert plaintext not in ct
        assert plaintext.encode() not in base64.b64decode(ct)


# ── decrypt_app_password ──────────────────────────────────────────────────────

class TestDecryptAppPassword:
    def test_round_trip(self, set_valid_key):
        original = "my_gmail_app_password_123"
        ct = encrypt_app_password(original)
        recovered = decrypt_app_password(ct)
        assert recovered == original

    def test_round_trip_unicode(self, set_valid_key):
        original = "pässwörd_with_ünïcödé"
        ct = encrypt_app_password(original)
        assert decrypt_app_password(ct) == original

    def test_raises_on_empty_ciphertext(self, set_valid_key):
        with pytest.raises(ValueError, match="non-empty"):
            decrypt_app_password("")

    def test_raises_on_tampered_ciphertext(self, set_valid_key):
        ct = encrypt_app_password("password")
        # Flip a byte in the middle of the blob
        blob = bytearray(base64.b64decode(ct))
        blob[15] ^= 0xFF
        tampered = base64.b64encode(bytes(blob)).decode("ascii")
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_app_password(tampered)

    def test_raises_on_wrong_key(self, monkeypatch):
        key1 = _valid_key()
        key2 = _valid_key()
        monkeypatch.setenv(ENV_VAR_NAME, key1)
        ct = encrypt_app_password("password")
        monkeypatch.setenv(ENV_VAR_NAME, key2)
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_app_password(ct)

    def test_raises_on_invalid_base64(self, set_valid_key):
        with pytest.raises(ValueError, match="not valid base64"):
            decrypt_app_password("!!!not-base64!!!")

    def test_raises_on_too_short_blob(self, set_valid_key):
        # Only 4 bytes — shorter than the 12-byte nonce
        short = base64.b64encode(b"tiny").decode("ascii")
        with pytest.raises(ValueError, match="too short"):
            decrypt_app_password(short)

    def test_raises_when_env_var_missing(self):
        with pytest.raises(EnvironmentError, match=ENV_VAR_NAME):
            decrypt_app_password("anyciphertext")


# ── generate_key ──────────────────────────────────────────────────────────────

class TestGenerateKey:
    def test_returns_valid_32_byte_key(self):
        key = generate_key()
        assert len(base64.b64decode(key)) == 32

    def test_keys_are_unique(self):
        keys = {generate_key() for _ in range(20)}
        assert len(keys) == 20  # all distinct


# ── Pydantic SecretStr models ─────────────────────────────────────────────────

class TestGmailConnectionRequest:
    def test_app_password_is_secret_str(self):
        req = GmailConnectionRequest(
            gmail_address="agent@gmail.com",
            app_password="secret_pass",
        )
        # SecretStr repr must not expose the value
        assert "secret_pass" not in repr(req)
        assert "secret_pass" not in str(req)

    def test_get_secret_value_returns_plaintext(self):
        req = GmailConnectionRequest(
            gmail_address="agent@gmail.com",
            app_password="secret_pass",
        )
        assert req.app_password.get_secret_value() == "secret_pass"

    def test_json_serialisation_hides_password(self):
        req = GmailConnectionRequest(
            gmail_address="agent@gmail.com",
            app_password="secret_pass",
        )
        json_str = req.model_dump_json()
        assert "secret_pass" not in json_str

    def test_default_imap_folder(self):
        req = GmailConnectionRequest(
            gmail_address="agent@gmail.com",
            app_password="pass",
        )
        assert req.imap_folder == "INBOX"

    def test_rejects_empty_password(self):
        with pytest.raises(ValidationError):
            GmailConnectionRequest(
                gmail_address="agent@gmail.com",
                app_password="",
            )


class TestGmailCredentialUpdateRequest:
    def test_app_password_is_secret_str(self):
        req = GmailCredentialUpdateRequest(
            gmail_address="agent@gmail.com",
            app_password="new_secret",
        )
        assert "new_secret" not in repr(req)
        assert req.app_password.get_secret_value() == "new_secret"


class TestGmailConnectionResponse:
    def test_no_password_field(self):
        resp = GmailConnectionResponse(connected=True, gmail_address="agent@gmail.com")
        data = resp.model_dump()
        assert "app_password" not in data
        assert "password" not in data

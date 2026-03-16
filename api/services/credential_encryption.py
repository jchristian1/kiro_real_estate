"""
Credential Encryption Service for Agent App Passwords.

Provides AES-256-GCM encryption/decryption for Gmail App Passwords.
The encryption key is sourced exclusively from the CREDENTIAL_ENCRYPTION_KEY
environment variable — never hardcoded.

Requirements: 19.1, 19.2, 19.3, 19.4
"""

import os
import base64
import secrets
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, SecretStr, Field


# ── Constants ────────────────────────────────────────────────────────────────

ENV_VAR_NAME = "CREDENTIAL_ENCRYPTION_KEY"
"""Name of the environment variable that holds the AES-256 key (32 raw bytes, base64-encoded)."""

_NONCE_BYTES = 12   # 96-bit nonce — standard for AES-GCM
_KEY_BYTES = 32     # 256-bit key


# ── Key loading ───────────────────────────────────────────────────────────────

def _load_key() -> bytes:
    """
    Load the AES-256 encryption key from the environment variable.

    Returns:
        32-byte key as raw bytes.

    Raises:
        EnvironmentError: If the env var is missing or the key is not valid
                          base64-encoded 32 bytes.
    """
    raw = os.environ.get(ENV_VAR_NAME)
    if not raw:
        raise EnvironmentError(
            f"Encryption key not found. Set the {ENV_VAR_NAME!r} environment "
            "variable to a base64-encoded 32-byte key. "
            "Generate one with: python -c \"import secrets, base64; "
            "print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )
    try:
        key_bytes = base64.b64decode(raw)
    except Exception as exc:
        raise EnvironmentError(
            f"{ENV_VAR_NAME!r} is not valid base64: {exc}"
        ) from exc

    if len(key_bytes) != _KEY_BYTES:
        raise EnvironmentError(
            f"{ENV_VAR_NAME!r} must decode to exactly {_KEY_BYTES} bytes "
            f"(got {len(key_bytes)} bytes). "
            "Generate a valid key with: python -c \"import secrets, base64; "
            "print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )
    return key_bytes


# ── Public API ────────────────────────────────────────────────────────────────

def encrypt_app_password(plaintext: str) -> str:
    """
    Encrypt a Gmail App Password using AES-256-GCM.

    A fresh random 96-bit nonce is generated for every call, so encrypting
    the same plaintext twice produces different ciphertexts (IND-CPA secure).

    The output format is:  base64( nonce || ciphertext_with_tag )
    This is a single URL-safe base64 string that can be stored in the DB.

    Args:
        plaintext: The App Password to encrypt (must be non-empty).

    Returns:
        A base64-encoded string containing the nonce and ciphertext.

    Raises:
        ValueError: If plaintext is empty.
        EnvironmentError: If CREDENTIAL_ENCRYPTION_KEY is missing or invalid.
    """
    if not plaintext:
        raise ValueError("plaintext must be a non-empty string")

    key = _load_key()
    nonce = secrets.token_bytes(_NONCE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Prepend nonce so decrypt can recover it
    blob = nonce + ciphertext
    return base64.b64encode(blob).decode("ascii")


def decrypt_app_password(ciphertext: str) -> str:
    """
    Decrypt a Gmail App Password that was encrypted with encrypt_app_password.

    Args:
        ciphertext: The base64-encoded string returned by encrypt_app_password.

    Returns:
        The original plaintext App Password.

    Raises:
        ValueError: If ciphertext is empty, malformed, or decryption fails
                    (wrong key, tampered data).
        EnvironmentError: If CREDENTIAL_ENCRYPTION_KEY is missing or invalid.
    """
    if not ciphertext:
        raise ValueError("ciphertext must be a non-empty string")

    key = _load_key()
    try:
        blob = base64.b64decode(ciphertext)
    except Exception as exc:
        raise ValueError(f"ciphertext is not valid base64: {exc}") from exc

    if len(blob) <= _NONCE_BYTES:
        raise ValueError(
            f"ciphertext too short: expected > {_NONCE_BYTES} bytes, got {len(blob)}"
        )

    nonce = blob[:_NONCE_BYTES]
    encrypted = blob[_NONCE_BYTES:]
    aesgcm = AESGCM(key)
    try:
        plaintext_bytes = aesgcm.decrypt(nonce, encrypted, None)
    except Exception as exc:
        raise ValueError(
            "Decryption failed — wrong key or tampered ciphertext."
        ) from exc

    return plaintext_bytes.decode("utf-8")


def generate_key() -> str:
    """
    Generate a new random AES-256 key suitable for CREDENTIAL_ENCRYPTION_KEY.

    Returns:
        A base64-encoded 32-byte key string.
    """
    return base64.b64encode(secrets.token_bytes(_KEY_BYTES)).decode("ascii")


# ── Pydantic models with SecretStr ────────────────────────────────────────────

class GmailConnectionRequest(BaseModel):
    """
    Request model for connecting a Gmail account during onboarding (Step 2).

    The app_password field uses SecretStr so that Pydantic never includes
    the plaintext value in repr(), str(), or JSON serialisation — satisfying
    Requirements 19.3 and 19.4.
    """

    gmail_address: str = Field(
        ...,
        description="Agent's Gmail address",
        examples=["agent@gmail.com"],
    )
    app_password: SecretStr = Field(
        ...,
        description="Gmail application-specific password (16-char, no spaces)",
        min_length=1,
    )
    imap_folder: Optional[str] = Field(
        default="INBOX",
        description="IMAP folder to monitor (default: INBOX)",
    )


class GmailCredentialUpdateRequest(BaseModel):
    """
    Request model for updating Gmail credentials in account settings.

    Uses SecretStr for app_password to prevent accidental logging.
    """

    gmail_address: str = Field(..., description="New Gmail address")
    app_password: SecretStr = Field(
        ...,
        description="New Gmail application-specific password",
        min_length=1,
    )


class GmailConnectionResponse(BaseModel):
    """
    Response model for a successful Gmail connection.

    NOTE: app_password is intentionally absent — plaintext is never returned.
    """

    connected: bool
    gmail_address: str
    last_sync: Optional[str] = None

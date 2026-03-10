"""
IMAP Connection Service for Gmail App Password validation.

Tests a live IMAP connection to imap.gmail.com:993 using imaplib.IMAP4_SSL.
Classifies IMAP errors into a fixed safe enumeration — the raw error message
and the app_password are NEVER included in logs, error messages, or responses.

Requirements: 5.1, 5.3, 5.4, 5.5, 5.6, 5.8, 19.4
"""

import imaplib
import logging
import socket
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_TIMEOUT_SECONDS = 10

# Fixed safe error code enumeration (Requirement 5.3–5.6)
ERROR_IMAP_DISABLED = "IMAP_DISABLED"
ERROR_TWO_FACTOR_REQUIRED = "TWO_FACTOR_REQUIRED"
ERROR_INVALID_PASSWORD = "INVALID_PASSWORD"
ERROR_RATE_LIMITED = "RATE_LIMITED"
ERROR_CONNECTION_FAILED = "CONNECTION_FAILED"

_SAFE_MESSAGES = {
    ERROR_IMAP_DISABLED: (
        "IMAP access is disabled for this Gmail account. "
        "Enable it in Gmail Settings → See All Settings → Forwarding and POP/IMAP."
    ),
    ERROR_TWO_FACTOR_REQUIRED: (
        "An application-specific password is required. "
        "Create one at myaccount.google.com/apppasswords."
    ),
    ERROR_INVALID_PASSWORD: (
        "The Gmail address or App Password is incorrect. "
        "Double-check your credentials and try again."
    ),
    ERROR_RATE_LIMITED: (
        "Too many login attempts. Please wait a few minutes before trying again."
    ),
    ERROR_CONNECTION_FAILED: (
        "Could not connect to Gmail. Check your internet connection and try again."
    ),
}


# ── Public API ────────────────────────────────────────────────────────────────

def test_imap_connection(gmail_address: str, app_password: str) -> dict:
    """
    Test a live IMAP connection to imap.gmail.com:993.

    Connects, logs in, selects INBOX, then logs out cleanly.
    On any failure the raw error is classified into a fixed safe error code;
    the app_password is NEVER included in any log output or returned value.

    Args:
        gmail_address: The agent's Gmail address.
        app_password:  The Gmail application-specific password.
                       NEVER logged or returned.

    Returns:
        On success: {"success": True, "last_sync": None}
        On failure: {"success": False, "error": <error_code>, "message": <safe_message>}
    """
    # Deliberately do NOT log app_password — Requirement 19.4
    logger.info("Testing IMAP connection for address: %s", gmail_address)

    conn: Optional[imaplib.IMAP4_SSL] = None
    try:
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        conn.socket().settimeout(IMAP_TIMEOUT_SECONDS)
        conn.login(gmail_address, app_password)
        conn.select("INBOX")
        conn.logout()
        logger.info("IMAP connection test succeeded for: %s", gmail_address)
        return {"success": True, "last_sync": None}

    except imaplib.IMAP4.error as exc:
        # Classify without leaking the raw message or the password
        raw = str(exc)
        error_code = classify_imap_error(raw)
        logger.warning(
            "IMAP connection test failed for %s — classified as: %s",
            gmail_address,
            error_code,
        )
        return {
            "success": False,
            "error": error_code,
            "message": _SAFE_MESSAGES[error_code],
        }

    except (socket.timeout, socket.gaierror, OSError, ConnectionError) as exc:
        # Network-level failures — log type only, never the exception message
        # (it could theoretically contain credential fragments in edge cases)
        logger.warning(
            "IMAP network error for %s — %s",
            gmail_address,
            type(exc).__name__,
        )
        return {
            "success": False,
            "error": ERROR_CONNECTION_FAILED,
            "message": _SAFE_MESSAGES[ERROR_CONNECTION_FAILED],
        }

    except Exception as exc:  # noqa: BLE001
        # Catch-all: log only the exception type, never the message
        logger.warning(
            "Unexpected IMAP error for %s — %s",
            gmail_address,
            type(exc).__name__,
        )
        return {
            "success": False,
            "error": ERROR_CONNECTION_FAILED,
            "message": _SAFE_MESSAGES[ERROR_CONNECTION_FAILED],
        }

    finally:
        # Best-effort cleanup — ignore errors during logout
        if conn is not None:
            try:
                conn.logout()
            except Exception:  # noqa: BLE001
                pass


def classify_imap_error(raw_message: str) -> str:
    """
    Map a raw IMAP error message to a fixed safe error code.

    The returned value is always one of the five constants defined in this
    module.  The raw_message is NEVER returned or logged by callers.

    Args:
        raw_message: The string representation of an imaplib.IMAP4.error.

    Returns:
        One of: IMAP_DISABLED, TWO_FACTOR_REQUIRED, INVALID_PASSWORD,
                RATE_LIMITED, CONNECTION_FAILED.
    """
    if "Application-specific password required" in raw_message:
        return ERROR_TWO_FACTOR_REQUIRED
    if "IMAP access is disabled" in raw_message:
        return ERROR_IMAP_DISABLED
    if "Invalid credentials" in raw_message:
        return ERROR_INVALID_PASSWORD
    if "Too many login attempts" in raw_message:
        return ERROR_RATE_LIMITED
    return ERROR_CONNECTION_FAILED

"""
IMAP Connection Service for Gmail App Password validation.

Tests a live IMAP connection to imap.gmail.com:993 using imaplib.IMAP4_SSL.
Classifies IMAP errors into a fixed safe enumeration — the raw error message
and the app_password are NEVER included in logs, error messages, or responses.

Also provides in-memory rate limiting: max 5 attempts per agent per 15-minute
sliding window (Requirement 5.7).

Requirements: 5.1, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 19.4
"""

import imaplib
import logging
import socket
import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_TIMEOUT_SECONDS = 10

# Rate limiting (Requirement 5.7)
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 15 * 60  # 15 minutes


# ── Rate Limiter ──────────────────────────────────────────────────────────────

class IMAPRateLimitError(Exception):
    """Raised when an agent exceeds the IMAP connection test rate limit."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded. Retry after {retry_after_seconds} seconds.")


# In-memory store: agent_user_id -> list of attempt timestamps (monotonic)
_attempt_timestamps: Dict[int, List[float]] = defaultdict(list)
_lock = Lock()


def check_and_record_imap_attempt(agent_user_id: int) -> None:
    """
    Check whether the agent is within the rate limit, then record the attempt.

    Uses a sliding window of RATE_LIMIT_WINDOW_SECONDS.  If the agent has
    already made RATE_LIMIT_MAX_ATTEMPTS within the current window, raises
    IMAPRateLimitError with the number of seconds until the oldest attempt
    falls outside the window.

    Args:
        agent_user_id: The authenticated agent's ID (rate-limit key).

    Raises:
        IMAPRateLimitError: When the agent has exceeded the allowed attempts.
    """
    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    with _lock:
        # Evict timestamps that have fallen outside the sliding window
        timestamps = _attempt_timestamps[agent_user_id]
        timestamps[:] = [t for t in timestamps if t > window_start]

        if len(timestamps) >= RATE_LIMIT_MAX_ATTEMPTS:
            # Oldest timestamp in the window determines when the slot frees up
            oldest = timestamps[0]
            retry_after = int(oldest + RATE_LIMIT_WINDOW_SECONDS - now) + 1
            raise IMAPRateLimitError(retry_after_seconds=max(retry_after, 1))

        # Record this attempt
        timestamps.append(now)


def reset_imap_rate_limit(agent_user_id: int) -> None:
    """
    Clear all recorded attempts for an agent.

    Intended for use in tests only — not called from production code.
    """
    with _lock:
        _attempt_timestamps[agent_user_id] = []

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

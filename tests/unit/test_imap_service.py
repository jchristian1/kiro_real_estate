"""
Unit tests for api/services/imap_service.py

All tests use mocks — no real IMAP connection is made.

Requirements: 5.1, 5.3, 5.4, 5.5, 5.6, 5.8, 19.4
"""

import imaplib
import socket
from unittest.mock import MagicMock, patch

import api.services.imap_service as imap_service
from api.services.imap_service import (
    ERROR_CONNECTION_FAILED,
    ERROR_IMAP_DISABLED,
    ERROR_INVALID_PASSWORD,
    ERROR_RATE_LIMITED,
    ERROR_TWO_FACTOR_REQUIRED,
    classify_imap_error,
)

# Alias to avoid pytest collecting the service function as a test fixture
check_imap = imap_service.test_imap_connection

GMAIL = "agent@gmail.com"
PASSWORD = "secret-app-password"


# ── classify_imap_error ───────────────────────────────────────────────────────

class TestClassifyImapError:
    def test_two_factor_required(self):
        assert classify_imap_error("Application-specific password required") == ERROR_TWO_FACTOR_REQUIRED

    def test_imap_disabled(self):
        assert classify_imap_error("IMAP access is disabled") == ERROR_IMAP_DISABLED

    def test_invalid_credentials(self):
        assert classify_imap_error("Invalid credentials (Failure)") == ERROR_INVALID_PASSWORD

    def test_rate_limited(self):
        assert classify_imap_error("Too many login attempts, please try again later.") == ERROR_RATE_LIMITED

    def test_unknown_falls_back_to_connection_failed(self):
        assert classify_imap_error("Some unexpected IMAP error") == ERROR_CONNECTION_FAILED

    def test_empty_string_falls_back_to_connection_failed(self):
        assert classify_imap_error("") == ERROR_CONNECTION_FAILED

    def test_returns_fixed_enum_value_not_raw_message(self):
        raw = "Application-specific password required — do not expose this"
        result = classify_imap_error(raw)
        assert result == ERROR_TWO_FACTOR_REQUIRED
        assert raw not in result  # raw message never returned


# ── IMAP connection — success path ────────────────────────────────────────────

class TestImapConnectionSuccess:
    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_returns_success_true_and_last_sync_none(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn

        result = check_imap(GMAIL, PASSWORD)

        assert result == {"success": True, "last_sync": None}

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_calls_login_with_correct_credentials(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn

        check_imap(GMAIL, PASSWORD)

        mock_conn.login.assert_called_once_with(GMAIL, PASSWORD)

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_selects_inbox(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn

        check_imap(GMAIL, PASSWORD)

        mock_conn.select.assert_called_once_with("INBOX")

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_connects_to_correct_host_and_port(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn

        check_imap(GMAIL, PASSWORD)

        mock_ssl_cls.assert_called_once_with("imap.gmail.com", 993)


# ── IMAP connection — IMAP error paths ───────────────────────────────────────

class TestImapConnectionImapErrors:
    def _make_imap_error(self, message: str) -> imaplib.IMAP4.error:
        return imaplib.IMAP4.error(message)

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_imap_disabled_error(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn
        mock_conn.login.side_effect = self._make_imap_error("IMAP access is disabled")

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_IMAP_DISABLED
        assert "message" in result

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_two_factor_required_error(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn
        mock_conn.login.side_effect = self._make_imap_error(
            "Application-specific password required"
        )

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_TWO_FACTOR_REQUIRED

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_invalid_password_error(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn
        mock_conn.login.side_effect = self._make_imap_error("Invalid credentials (Failure)")

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_INVALID_PASSWORD

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_rate_limited_error(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn
        mock_conn.login.side_effect = self._make_imap_error(
            "Too many login attempts, please try again later."
        )

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_RATE_LIMITED

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_unknown_imap_error_returns_connection_failed(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn
        mock_conn.login.side_effect = self._make_imap_error("Some unknown IMAP error")

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_CONNECTION_FAILED


# ── IMAP connection — network error paths ────────────────────────────────────

class TestImapConnectionNetworkErrors:
    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_socket_timeout_returns_connection_failed(self, mock_ssl_cls):
        mock_ssl_cls.side_effect = socket.timeout("timed out")

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_CONNECTION_FAILED

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_socket_gaierror_returns_connection_failed(self, mock_ssl_cls):
        mock_ssl_cls.side_effect = socket.gaierror("Name or service not known")

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_CONNECTION_FAILED

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_os_error_returns_connection_failed(self, mock_ssl_cls):
        mock_ssl_cls.side_effect = OSError("Connection refused")

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_CONNECTION_FAILED

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_unexpected_exception_returns_connection_failed(self, mock_ssl_cls):
        mock_ssl_cls.side_effect = RuntimeError("Unexpected failure")

        result = check_imap(GMAIL, PASSWORD)

        assert result["success"] is False
        assert result["error"] == ERROR_CONNECTION_FAILED


# ── Credential safety — app_password never in output ─────────────────────────

class TestCredentialSafety:
    """Requirement 19.4: app_password must never appear in any output."""

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_password_not_in_success_response(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn

        result = check_imap(GMAIL, PASSWORD)

        assert PASSWORD not in str(result)

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_password_not_in_error_response(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn
        mock_conn.login.side_effect = imaplib.IMAP4.error("Invalid credentials")

        result = check_imap(GMAIL, PASSWORD)

        assert PASSWORD not in str(result)
        assert PASSWORD not in result.get("message", "")
        assert PASSWORD not in result.get("error", "")

    @patch("api.services.imap_service.imaplib.IMAP4_SSL")
    def test_error_message_is_safe_user_facing_string(self, mock_ssl_cls):
        mock_conn = MagicMock()
        mock_ssl_cls.return_value = mock_conn
        mock_conn.login.side_effect = imaplib.IMAP4.error("IMAP access is disabled")

        result = check_imap(GMAIL, PASSWORD)

        # Message is a safe human-readable string, not the raw IMAP error verbatim
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0
        assert PASSWORD not in result["message"]

    def test_classify_never_returns_raw_message(self):
        raw = "Invalid credentials — secret-app-password exposed"
        result = classify_imap_error(raw)
        assert PASSWORD not in result
        assert raw not in result

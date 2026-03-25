"""
Unit tests for AutoResponder.send_email.

TemplateRenderer and AutoResponder.send_acknowledgment were removed in Task 15
as part of the legacy auto-email path cleanup. All email sending now goes
through the pipeline engine via SendEmailTemplateHandler.

These tests cover only the SMTP send primitive that the pipeline handler uses.
"""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from gmail_lead_sync.responder import AutoResponder


class TestAutoResponderSendEmail:
    """AutoResponder.send_email — the only public method on this class."""

    def _make_responder(self) -> AutoResponder:
        """Instantiate via object.__new__ as the pipeline handler does."""
        return object.__new__(AutoResponder)

    def test_success_returns_true(self):
        responder = self._make_responder()
        with patch("gmail_lead_sync.responder.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            result = responder.send_email(
                to_address="lead@example.com",
                subject="Hello",
                body="Body",
                from_address="agent@gmail.com",
                app_password="pw",
            )
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("agent@gmail.com", "pw")
        mock_server.send_message.assert_called_once()

    def test_uses_correct_smtp_server(self):
        responder = self._make_responder()
        with patch("gmail_lead_sync.responder.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            responder.send_email("a@b.com", "s", "b", "f@g.com", "pw")
        mock_smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)

    def test_retries_on_smtp_exception_then_succeeds(self):
        responder = self._make_responder()
        with patch("gmail_lead_sync.responder.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            mock_server.send_message.side_effect = [
                smtplib.SMTPException("fail"),
                smtplib.SMTPException("fail"),
                None,  # third attempt succeeds
            ]
            with patch("gmail_lead_sync.responder.time.sleep"):
                result = responder.send_email("a@b.com", "s", "b", "f@g.com", "pw")
        assert result is True
        assert mock_server.send_message.call_count == 3

    def test_returns_false_after_max_retries(self):
        responder = self._make_responder()
        with patch("gmail_lead_sync.responder.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            mock_server.send_message.side_effect = smtplib.SMTPException("permanent fail")
            with patch("gmail_lead_sync.responder.time.sleep"):
                result = responder.send_email(
                    "a@b.com", "s", "b", "f@g.com", "pw", max_attempts=3
                )
        assert result is False
        assert mock_server.send_message.call_count == 3

    def test_no_legacy_send_acknowledgment_method(self):
        """Confirm the legacy send_acknowledgment path no longer exists.

        This test acts as a regression guard — if someone re-adds the method,
        this test will fail and prompt a review.
        """
        responder = self._make_responder()
        assert not hasattr(responder, "send_acknowledgment"), (
            "send_acknowledgment was removed as part of legacy auto-email cleanup. "
            "All email sending must go through the pipeline engine."
        )

    def test_no_legacy_template_renderer(self):
        """Confirm TemplateRenderer no longer exists in the responder module."""
        import gmail_lead_sync.responder as responder_module
        assert not hasattr(responder_module, "TemplateRenderer"), (
            "TemplateRenderer was removed as part of legacy auto-email cleanup."
        )

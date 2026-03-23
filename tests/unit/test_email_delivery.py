"""
Unit tests for EmailDeliveryService.

Tests:
- get_credentials returns (email, password) from Credentials row
- get_credentials uses EncryptedDBCredentialsStore when ENCRYPTION_KEY is set
- get_credentials raises CredentialResolutionError when no row exists
- send returns True on successful delivery
- send returns False when credentials are missing
- send returns False when AutoResponder returns False
- send returns False on unexpected exception — never raises
- send delegates to AutoResponder.send_email with correct args
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from api.communications.email_delivery import EmailDeliveryService, CredentialResolutionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creds(email="agent@example.com", password="secret", company_id=5, agent_id="agent1"):
    return SimpleNamespace(
        company_id=company_id,
        agent_id=agent_id,
        email_encrypted=email,
        app_password_encrypted=password,
    )


def _make_db(creds_row=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = creds_row
    return db


# ---------------------------------------------------------------------------
# get_credentials
# ---------------------------------------------------------------------------

class TestGetCredentials:
    def test_returns_raw_columns_when_no_encryption_key(self):
        svc = EmailDeliveryService()
        db = _make_db(_make_creds(email="from@x.com", password="pw"))

        with patch.dict("os.environ", {}, clear=True):
            email, pw = svc.get_credentials(db, tenant_id=5)

        assert email == "from@x.com"
        assert pw == "pw"

    def test_uses_encrypted_store_when_key_present(self):
        svc = EmailDeliveryService()
        db = _make_db(_make_creds(agent_id="agent1"))

        mock_store = MagicMock()
        mock_store.get_credentials.return_value = ("decrypted@x.com", "decrypted_pw")

        with (
            patch.dict("os.environ", {"ENCRYPTION_KEY": "testkey"}),
            patch(
                "gmail_lead_sync.credentials.EncryptedDBCredentialsStore",
                return_value=mock_store,
            ),
        ):
            email, pw = svc.get_credentials(db, tenant_id=5)

        assert email == "decrypted@x.com"
        assert pw == "decrypted_pw"
        mock_store.get_credentials.assert_called_once_with("agent1")

    def test_raises_when_no_credentials_row(self):
        svc = EmailDeliveryService()
        db = _make_db(creds_row=None)

        with pytest.raises(CredentialResolutionError):
            svc.get_credentials(db, tenant_id=99)


# ---------------------------------------------------------------------------
# send
# ---------------------------------------------------------------------------

class TestSend:
    def _svc_with_creds(self, email="from@x.com", password="pw"):
        svc = EmailDeliveryService()
        svc.get_credentials = MagicMock(return_value=(email, password))
        return svc

    def test_returns_true_on_success(self):
        svc = self._svc_with_creds()
        db = MagicMock()

        with patch("gmail_lead_sync.responder.AutoResponder.send_email", return_value=True):
            result = svc.send(db, tenant_id=5, to_address="lead@x.com", subject="Hi", body="Body")

        assert result is True

    def test_delegates_correct_args_to_autoresponder(self):
        svc = self._svc_with_creds(email="from@x.com", password="pw")
        db = MagicMock()

        with patch("gmail_lead_sync.responder.AutoResponder.send_email", return_value=True) as mock_send:
            svc.send(db, tenant_id=5, to_address="lead@x.com", subject="Subj", body="Body text")

        mock_send.assert_called_once_with(
            to_address="lead@x.com",
            subject="Subj",
            body="Body text",
            from_address="from@x.com",
            app_password="pw",
        )

    def test_returns_false_when_autoresponder_returns_false(self):
        svc = self._svc_with_creds()
        db = MagicMock()

        with patch("gmail_lead_sync.responder.AutoResponder.send_email", return_value=False):
            result = svc.send(db, tenant_id=5, to_address="lead@x.com", subject="Hi", body="Body")

        assert result is False

    def test_returns_false_when_credentials_missing(self):
        svc = EmailDeliveryService()
        svc.get_credentials = MagicMock(side_effect=CredentialResolutionError("no creds"))
        db = MagicMock()

        result = svc.send(db, tenant_id=5, to_address="lead@x.com", subject="Hi", body="Body")

        assert result is False

    def test_never_raises_on_unexpected_exception(self):
        svc = self._svc_with_creds()
        db = MagicMock()

        with patch(
            "gmail_lead_sync.responder.AutoResponder.send_email",
            side_effect=RuntimeError("smtp exploded"),
        ):
            result = svc.send(db, tenant_id=5, to_address="lead@x.com", subject="Hi", body="Body")

        assert result is False

    def test_returns_false_on_credential_resolution_exception(self):
        svc = EmailDeliveryService()
        svc.get_credentials = MagicMock(side_effect=Exception("db down"))
        db = MagicMock()

        result = svc.send(db, tenant_id=5, to_address="lead@x.com", subject="Hi", body="Body")

        assert result is False


# ---------------------------------------------------------------------------
# Integration: send_email handler uses EmailDeliveryService
# ---------------------------------------------------------------------------

class TestSendEmailHandlerUsesDeliveryService:
    """Verify the pipeline handler delegates delivery to EmailDeliveryService."""

    def test_handler_calls_delivery_service_not_autoresponder_directly(self):
        from api.pipelines.handlers.send_email import SendEmailTemplateHandler
        from types import SimpleNamespace

        db = MagicMock()
        mock_lead = SimpleNamespace(id=1, source_email="lead@test.com", name="Test")

        with (
            patch("api.pipelines.handlers.send_email.resolve_lead_company_id", return_value=7),
            patch("api.pipelines.handlers.send_email._render_admin_template", return_value=("subj", "body")),
            patch("api.communications.email_delivery.EmailDeliveryService.send", return_value=True) as mock_send,
            patch("api.services.lead_activity.record_activity"),
        ):
            db.query.return_value.filter.return_value.first.return_value = mock_lead
            handler = SendEmailTemplateHandler()
            result = handler.execute(db, lead_id=1, config={"template_id": 5}, context={})

        assert result.success is True
        mock_send.assert_called_once_with(db, 7, "lead@test.com", "subj", "body")

    def test_handler_returns_failure_when_delivery_fails(self):
        from api.pipelines.handlers.send_email import SendEmailTemplateHandler
        from types import SimpleNamespace

        db = MagicMock()
        mock_lead = SimpleNamespace(id=1, source_email="lead@test.com", name="Test")

        with (
            patch("api.pipelines.handlers.send_email.resolve_lead_company_id", return_value=7),
            patch("api.pipelines.handlers.send_email._render_admin_template", return_value=("subj", "body")),
            patch("api.communications.email_delivery.EmailDeliveryService.send", return_value=False),
        ):
            db.query.return_value.filter.return_value.first.return_value = mock_lead
            handler = SendEmailTemplateHandler()
            result = handler.execute(db, lead_id=1, config={"template_id": 5}, context={})

        assert result.success is False
        assert "delivery failed" in result.error


# ---------------------------------------------------------------------------
# Integration: qualification handler uses EmailDeliveryService
# ---------------------------------------------------------------------------

class TestQualificationHandlerUsesDeliveryService:
    """Verify on_buyer_lead_email_received delegates delivery to EmailDeliveryService."""

    def test_qualification_handler_calls_delivery_service(self):
        import gmail_lead_sync.preapproval.handlers as handlers_module
        import inspect

        source = inspect.getsource(handlers_module.on_buyer_lead_email_received)
        # Must not contain the old direct credential/send helpers
        assert "_get_tenant_email_credentials" not in source
        assert "_send_email(" not in source
        # Must use the delivery service
        assert "_get_delivery" in source or "email_delivery" in source or "EmailDeliveryService" in source

    def test_old_credential_helpers_removed_from_handlers(self):
        import gmail_lead_sync.preapproval.handlers as handlers_module

        assert not hasattr(handlers_module, "_get_tenant_email_credentials"), \
            "_get_tenant_email_credentials must be removed — use EmailDeliveryService"
        assert not hasattr(handlers_module, "_send_email"), \
            "_send_email must be removed — use EmailDeliveryService"

    def test_old_credential_helpers_removed_from_send_email_handler(self):
        import api.pipelines.handlers.send_email as send_email_module

        assert not hasattr(send_email_module, "_get_smtp_credentials"), \
            "_get_smtp_credentials must be removed — use EmailDeliveryService"
        assert not hasattr(send_email_module, "_send_via_smtp"), \
            "_send_via_smtp must be removed — use EmailDeliveryService"

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
            patch("api.communications.template_render.TemplateRenderService.render_admin_template", return_value=("subj", "body")),
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
            patch("api.communications.template_render.TemplateRenderService.render_admin_template", return_value=("subj", "body")),
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
        # Must not contain old direct credential/send helpers
        assert "_get_tenant_email_credentials" not in source
        assert "_send_email(" not in source
        # Must delegate to QualificationInviteService (not inline delivery)
        assert "_get_invite_service" in source or "QualificationInviteService" in source

    def test_old_credential_helpers_removed_from_handlers(self):
        import gmail_lead_sync.preapproval.handlers as handlers_module

        assert not hasattr(handlers_module, "_get_tenant_email_credentials"), \
            "_get_tenant_email_credentials must be removed — use EmailDeliveryService"
        assert not hasattr(handlers_module, "_send_email"), \
            "_send_email must be removed — use EmailDeliveryService"
        assert not hasattr(handlers_module, "_resolve_agent_template"), \
            "_resolve_agent_template must be removed — use TemplateRenderService"
        assert not hasattr(handlers_module, "_render_agent_template"), \
            "_render_agent_template must be removed — use TemplateRenderService"

    def test_old_credential_helpers_removed_from_send_email_handler(self):
        import api.pipelines.handlers.send_email as send_email_module

        assert not hasattr(send_email_module, "_get_smtp_credentials"), \
            "_get_smtp_credentials must be removed — use EmailDeliveryService"
        assert not hasattr(send_email_module, "_send_via_smtp"), \
            "_send_via_smtp must be removed — use EmailDeliveryService"


# ---------------------------------------------------------------------------
# Phase 4C: TemplateRenderService
# ---------------------------------------------------------------------------

class TestTemplateRenderService:
    """Unit tests for TemplateRenderService."""

    # --- render_admin_template ---

    def test_render_admin_template_substitutes_placeholders(self):
        from api.communications.template_render import TemplateRenderService
        from types import SimpleNamespace

        svc = TemplateRenderService()
        db = MagicMock()
        lead = SimpleNamespace(id=1, name="Alice Smith", source_email="alice@x.com")
        mock_tpl = SimpleNamespace(subject="Hi {lead_name}", body="Call {agent_phone}")
        mock_agent = SimpleNamespace(full_name="Bob Agent", phone="555-1234", email="bob@x.com")

        with (
            patch("api.repositories.template_repository.AdminTemplateRepository") as MockRepo,
            patch("gmail_lead_sync.agent_models.AgentUser"),
        ):
            MockRepo.return_value.get_by_id.return_value = mock_tpl
            db.query.return_value.filter.return_value.first.return_value = mock_agent

            subject, body = svc.render_admin_template(db, template_id=1, lead=lead, tenant_id=5)

        assert subject == "Hi Alice Smith"
        assert "555-1234" in body

    def test_render_admin_template_raises_when_not_found(self):
        from api.communications.template_render import TemplateRenderService
        from types import SimpleNamespace

        svc = TemplateRenderService()
        db = MagicMock()
        lead = SimpleNamespace(id=1, name="Alice", source_email="a@x.com")

        with (
            patch("api.repositories.template_repository.AdminTemplateRepository") as MockRepo,
            patch("gmail_lead_sync.agent_models.AgentUser"),
        ):
            MockRepo.return_value.get_by_id.return_value = None
            db.query.return_value.filter.return_value.first.return_value = None

            with pytest.raises(ValueError, match="not found"):
                svc.render_admin_template(db, template_id=99, lead=lead, tenant_id=5)

    # --- render_agent_template ---

    def test_render_agent_template_returns_none_when_no_agent(self):
        from api.communications.template_render import TemplateRenderService

        svc = TemplateRenderService()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with patch("gmail_lead_sync.agent_models.AgentUser"):
            result = svc.render_agent_template(db, tenant_id=5, template_type="INITIAL_INVITE", context={})

        assert result is None

    def test_render_agent_template_returns_none_when_no_active_template(self):
        from api.communications.template_render import TemplateRenderService
        from types import SimpleNamespace

        svc = TemplateRenderService()
        db = MagicMock()
        mock_agent = SimpleNamespace(id=10)

        # First query (AgentUser) returns agent, second (AgentTemplate) returns None
        db.query.return_value.filter.return_value.first.side_effect = [mock_agent, None]

        with (
            patch("gmail_lead_sync.agent_models.AgentUser"),
            patch("gmail_lead_sync.agent_models.AgentTemplate"),
        ):
            result = svc.render_agent_template(db, tenant_id=5, template_type="INITIAL_INVITE", context={})

        assert result is None

    def test_render_agent_template_substitutes_placeholders(self):
        from api.communications.template_render import TemplateRenderService
        from types import SimpleNamespace

        svc = TemplateRenderService()
        db = MagicMock()
        mock_agent = SimpleNamespace(id=10)
        mock_row = SimpleNamespace(subject="Hello {lead_name}", body="Link: {form_link}")

        db.query.return_value.filter.return_value.first.side_effect = [mock_agent, mock_row]

        with (
            patch("gmail_lead_sync.agent_models.AgentUser"),
            patch("gmail_lead_sync.agent_models.AgentTemplate"),
        ):
            result = svc.render_agent_template(
                db, tenant_id=5, template_type="INITIAL_INVITE",
                context={"lead_name": "Jane", "form_link": "https://form.example.com"},
            )

        assert result is not None
        subject, body = result
        assert subject == "Hello Jane"
        assert "https://form.example.com" in body

    def test_render_agent_template_returns_none_on_exception(self):
        """render_agent_template must return None (not raise) on unexpected errors."""
        from api.communications.template_render import TemplateRenderService

        svc = TemplateRenderService()
        db = MagicMock()
        db.query.side_effect = RuntimeError("db exploded")

        result = svc.render_agent_template(db, tenant_id=5, template_type="INITIAL_INVITE", context={})

        assert result is None

    # --- send_email handler uses TemplateRenderService ---

    def test_send_email_handler_no_longer_has_render_admin_template(self):
        """_render_admin_template must not exist in send_email.py — rendering moved to TemplateRenderService."""
        import api.pipelines.handlers.send_email as send_email_module

        assert not hasattr(send_email_module, "_render_admin_template"), \
            "_render_admin_template must be removed from send_email.py — use TemplateRenderService"

    def test_qualification_handler_no_longer_has_agent_template_helpers(self):
        """_resolve_agent_template and _render_agent_template must not exist in handlers.py."""
        import gmail_lead_sync.preapproval.handlers as handlers_module

        assert not hasattr(handlers_module, "_resolve_agent_template"), \
            "_resolve_agent_template must be removed — use TemplateRenderService"
        assert not hasattr(handlers_module, "_render_agent_template"), \
            "_render_agent_template must be removed — use TemplateRenderService"


# ---------------------------------------------------------------------------
# Phase 4D: QualificationInviteService
# ---------------------------------------------------------------------------

class TestQualificationInviteService:
    """Unit tests for QualificationInviteService."""

    def _make_lead(self, lead_id=1, name="Alice Smith", email="alice@x.com"):
        from types import SimpleNamespace
        return SimpleNamespace(id=lead_id, name=name, source_email=email)

    def _make_form_version(self, fv_id=7):
        from types import SimpleNamespace
        return SimpleNamespace(id=fv_id)

    # --- skipped when no active form version ---

    def test_returns_skipped_when_no_active_form_version(self):
        from api.communications.qualification_invite import QualificationInviteService

        svc = QualificationInviteService()
        db = MagicMock()
        db.query.return_value.join.return_value.filter.return_value.first.return_value = None

        result = svc.send_invite(db, tenant_id=5, lead_id=1, parsed_metadata={})

        assert result.skipped is True
        assert result.sent is False

    # --- invitation created and sent_at marked ---

    def test_marks_invitation_sent_at_on_success(self):
        from api.communications.qualification_invite import QualificationInviteService
        from types import SimpleNamespace

        svc = QualificationInviteService()
        db = MagicMock()
        mock_fv = self._make_form_version()
        mock_lead = self._make_lead()
        mock_invitation = SimpleNamespace(id=99, sent_at=None)

        db.query.return_value.join.return_value.filter.return_value.first.return_value = mock_fv
        db.get.return_value = mock_lead

        with (
            patch("gmail_lead_sync.preapproval.invitation_service.FormInvitationService.create_invitation",
                  return_value=("tok123", mock_invitation)),
            patch.object(svc, "_render_invite_email", return_value=("Subj", "Body")),
            patch("api.communications.email_delivery.EmailDeliveryService.send", return_value=True),
        ):
            result = svc.send_invite(db, tenant_id=5, lead_id=1, parsed_metadata={})

        assert result.sent is True
        assert result.invitation_id == 99
        assert mock_invitation.sent_at is not None

    # --- returns sent=False when delivery fails ---

    def test_returns_sent_false_when_delivery_fails(self):
        from api.communications.qualification_invite import QualificationInviteService
        from types import SimpleNamespace

        svc = QualificationInviteService()
        db = MagicMock()
        mock_fv = self._make_form_version()
        mock_lead = self._make_lead()
        mock_invitation = SimpleNamespace(id=10, sent_at=None)

        db.query.return_value.join.return_value.filter.return_value.first.return_value = mock_fv
        db.get.return_value = mock_lead

        with (
            patch("gmail_lead_sync.preapproval.invitation_service.FormInvitationService.create_invitation",
                  return_value=("tok", mock_invitation)),
            patch.object(svc, "_render_invite_email", return_value=("S", "B")),
            patch("api.communications.email_delivery.EmailDeliveryService.send", return_value=False),
        ):
            result = svc.send_invite(db, tenant_id=5, lead_id=1, parsed_metadata={})

        assert result.sent is False
        assert result.invitation_id == 10

    # --- returns rendered_subject=None when no template ---

    def test_returns_none_rendered_subject_when_no_template(self):
        from api.communications.qualification_invite import QualificationInviteService
        from types import SimpleNamespace

        svc = QualificationInviteService()
        db = MagicMock()
        mock_fv = self._make_form_version()
        mock_lead = self._make_lead()
        mock_invitation = SimpleNamespace(id=5, sent_at=None)

        db.query.return_value.join.return_value.filter.return_value.first.return_value = mock_fv
        db.get.return_value = mock_lead

        with (
            patch("gmail_lead_sync.preapproval.invitation_service.FormInvitationService.create_invitation",
                  return_value=("tok", mock_invitation)),
            patch.object(svc, "_render_invite_email", return_value=None),
        ):
            result = svc.send_invite(db, tenant_id=5, lead_id=1, parsed_metadata={})

        assert result.rendered_subject is None
        assert result.sent is False

    # --- rendering boundary: AgentTemplate preferred over MessageTemplate ---

    def test_render_uses_agent_template_when_available(self):
        from api.communications.qualification_invite import QualificationInviteService
        from types import SimpleNamespace

        svc = QualificationInviteService()
        db = MagicMock()
        mock_fv = self._make_form_version()
        mock_lead = self._make_lead()

        with (
            patch("api.communications.template_render.TemplateRenderService.render_agent_template",
                  return_value=("AgentSubj", "AgentBody")) as mock_agent_render,
            patch("gmail_lead_sync.agent_models.AgentUser"),
        ):
            db.query.return_value.filter.return_value.first.return_value = None
            result = svc._render_invite_email(
                db=db, tenant_id=5, lead=mock_lead,
                first_name="Alice", tenant_name="Acme",
                form_url="https://form.example.com",
                form_version=mock_fv, parsed_metadata={},
            )

        assert result == ("AgentSubj", "AgentBody")
        mock_agent_render.assert_called_once()

    def test_render_falls_back_to_message_template_when_no_agent_template(self):
        from api.communications.qualification_invite import QualificationInviteService
        from types import SimpleNamespace

        svc = QualificationInviteService()
        db = MagicMock()
        mock_fv = self._make_form_version()
        mock_lead = self._make_lead()
        mock_msg_version = SimpleNamespace(
            id=3, subject_template="Hi {{lead.first_name}}", body_template="Link: {{form.link}}",
            variants_json=None,
        )

        with (
            patch("api.communications.template_render.TemplateRenderService.render_agent_template",
                  return_value=None),
            patch("gmail_lead_sync.agent_models.AgentUser"),
            patch("gmail_lead_sync.preapproval.template_engine.TemplateRenderEngine.render") as mock_engine,
        ):
            from types import SimpleNamespace as SN
            mock_engine.return_value = SN(subject="Hi Alice", body="Link: https://form.example.com")
            db.query.return_value.filter.return_value.first.return_value = None
            db.query.return_value.join.return_value.filter.return_value.first.return_value = mock_msg_version

            result = svc._render_invite_email(
                db=db, tenant_id=5, lead=mock_lead,
                first_name="Alice", tenant_name="Acme",
                form_url="https://form.example.com",
                form_version=mock_fv, parsed_metadata={},
            )

        assert result is not None
        mock_engine.assert_called_once()

    def test_render_returns_none_when_neither_template_configured(self):
        from api.communications.qualification_invite import QualificationInviteService

        svc = QualificationInviteService()
        db = MagicMock()
        mock_fv = self._make_form_version()
        mock_lead = self._make_lead()

        with (
            patch("api.communications.template_render.TemplateRenderService.render_agent_template",
                  return_value=None),
            patch("gmail_lead_sync.agent_models.AgentUser"),
        ):
            db.query.return_value.filter.return_value.first.return_value = None
            db.query.return_value.join.return_value.filter.return_value.first.return_value = None

            result = svc._render_invite_email(
                db=db, tenant_id=5, lead=mock_lead,
                first_name="Alice", tenant_name="Acme",
                form_url="https://form.example.com",
                form_version=mock_fv, parsed_metadata={},
            )

        assert result is None

    # --- structural: old mixed invite logic removed from handlers ---

    def test_handlers_no_longer_own_invite_rendering_or_delivery(self):
        """on_buyer_lead_email_received must not contain inline rendering or delivery logic."""
        import gmail_lead_sync.preapproval.handlers as handlers_module
        import inspect

        source = inspect.getsource(handlers_module.on_buyer_lead_email_received)
        # Must not contain inline rendering
        assert "render_agent_template" not in source
        assert "_template_engine" not in source
        assert "TemplateRenderEngine" not in source
        # Must not contain inline delivery
        assert "EmailDeliveryService" not in source
        assert "_get_delivery" not in source
        # Must delegate to QualificationInviteService
        assert "_get_invite_service" in source

    def test_qualification_invite_service_lives_in_communications(self):
        """QualificationInviteService must be importable from api.communications."""
        from api.communications.qualification_invite import QualificationInviteService
        assert QualificationInviteService is not None

    def test_invite_result_exposes_sent_and_invitation_id(self):
        from api.communications.qualification_invite import InviteResult
        r = InviteResult(sent=True, invitation_id=42, form_version_id=7, rendered_subject="Hi")
        assert r.sent is True
        assert r.invitation_id == 42
        assert r.skipped is False

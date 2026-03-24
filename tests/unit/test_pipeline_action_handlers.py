"""
Unit tests for pipeline action handlers and executor.

Tests:
- Config validation for each handler
- Ordered step execution via executor
- Safe failure: failed step does not halt remaining steps
- Unknown action type produces failed result, not exception
- move_to_stage returns new_stage_id in ActionResult
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from api.pipelines.handlers.base import ActionResult
from api.pipelines.handlers.move_stage import MoveToStageHandler
from api.pipelines.handlers.send_email import SendEmailTemplateHandler
from api.pipelines.handlers.send_form import SendQualificationFormHandler
from api.pipelines.executor import execute_step


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step(action_type: str, config: dict, step_id: int = 1, position: int = 1):
    """Build a minimal mock step object."""
    step = SimpleNamespace(
        id=step_id,
        action_type=SimpleNamespace(value=action_type),
        action_config_json=json.dumps(config),
        position=position,
    )
    return step


# ---------------------------------------------------------------------------
# MoveToStageHandler
# ---------------------------------------------------------------------------


class TestMoveToStageHandler:
    def test_missing_stage_id_returns_failure(self):
        handler = MoveToStageHandler()
        result = handler.execute(MagicMock(), lead_id=1, config={}, context={})
        assert result.success is False
        assert "stage_id" in result.error

    def test_invalid_stage_id_type_returns_failure(self):
        handler = MoveToStageHandler()
        result = handler.execute(MagicMock(), lead_id=1, config={"stage_id": "abc"}, context={})
        assert result.success is False
        assert "integer" in result.error

    def test_success_returns_new_stage_id(self):
        handler = MoveToStageHandler()
        db = MagicMock()
        with patch("api.pipelines.handlers.move_stage.move_stage") as mock_move:
            result = handler.execute(db, lead_id=1, config={"stage_id": 5}, context={})
        assert result.success is True
        assert result.new_stage_id == 5
        mock_move.assert_called_once()

    def test_move_stage_exception_returns_failure(self):
        handler = MoveToStageHandler()
        db = MagicMock()
        with patch("api.pipelines.handlers.move_stage.move_stage", side_effect=RuntimeError("db error")):
            result = handler.execute(db, lead_id=1, config={"stage_id": 5}, context={})
        assert result.success is False
        assert "db error" in result.error


# ---------------------------------------------------------------------------
# SendEmailTemplateHandler
# ---------------------------------------------------------------------------


class TestSendEmailTemplateHandler:
    def test_missing_template_id_returns_failure(self):
        handler = SendEmailTemplateHandler()
        result = handler.execute(MagicMock(), lead_id=1, config={}, context={})
        assert result.success is False
        assert "template_id" in result.error

    def test_invalid_template_id_type_returns_failure(self):
        handler = SendEmailTemplateHandler()
        result = handler.execute(MagicMock(), lead_id=1, config={"template_id": "bad"}, context={})
        assert result.success is False
        assert "integer" in result.error

    def test_lead_not_found_returns_failure(self):
        handler = SendEmailTemplateHandler()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = handler.execute(db, lead_id=99, config={"template_id": 1}, context={})
        assert result.success is False
        assert "not found" in result.error.lower()

    def test_success_returns_metadata(self):
        handler = SendEmailTemplateHandler()
        db = MagicMock()

        mock_lead = SimpleNamespace(id=1, name="Test", source_email="test@example.com", company_id=10)
        db.query.return_value.filter.return_value.first.return_value = mock_lead

        with (
            patch("api.pipelines.handlers.send_email.resolve_lead_company_id", return_value=10),
            patch("api.communications.template_render.TemplateRenderService.render_admin_template", return_value=("Subject", "Body")),
            patch("api.communications.email_delivery.EmailDeliveryService.send", return_value=True),
            patch("api.services.lead_activity.record_activity"),
        ):
            result = handler.execute(db, lead_id=1, config={"template_id": 3}, context={})

        assert result.success is True
        assert result.metadata["template_id"] == 3

    def test_smtp_failure_returns_failure(self):
        handler = SendEmailTemplateHandler()
        db = MagicMock()

        mock_lead = SimpleNamespace(id=1, name="Test", source_email="test@example.com", company_id=10)
        db.query.return_value.filter.return_value.first.return_value = mock_lead

        with (
            patch("api.pipelines.handlers.send_email.resolve_lead_company_id", return_value=10),
            patch("api.communications.template_render.TemplateRenderService.render_admin_template", return_value=("S", "B")),
            patch("api.communications.email_delivery.EmailDeliveryService.send", return_value=False),
        ):
            result = handler.execute(db, lead_id=1, config={"template_id": 3}, context={})

        assert result.success is False
        assert "delivery failed" in result.error


# ---------------------------------------------------------------------------
# SendQualificationFormHandler
# ---------------------------------------------------------------------------


class TestSendQualificationFormHandler:
    def test_unresolvable_company_returns_failure(self):
        handler = SendQualificationFormHandler()
        db = MagicMock()
        with patch("api.pipelines.handlers.send_form.resolve_lead_company_id", return_value=None):
            result = handler.execute(db, lead_id=1, config={}, context={})
        assert result.success is False
        assert "company_id" in result.error

    def test_success_calls_qualification_handler(self):
        handler = SendQualificationFormHandler()
        db = MagicMock()
        with (
            patch("api.pipelines.handlers.send_form.resolve_lead_company_id", return_value=5),
            patch("api.pipelines.handlers.send_form.on_buyer_lead_email_received") as mock_handler,
        ):
            result = handler.execute(db, lead_id=1, config={}, context={"key": "val"})

        assert result.success is True
        mock_handler.assert_called_once_with(
            db=db, tenant_id=5, lead_id=1, parsed_metadata={"key": "val"}
        )

    def test_qualification_exception_returns_failure(self):
        handler = SendQualificationFormHandler()
        db = MagicMock()
        with (
            patch("api.pipelines.handlers.send_form.resolve_lead_company_id", return_value=5),
            patch(
                "api.pipelines.handlers.send_form.on_buyer_lead_email_received",
                side_effect=RuntimeError("form error"),
            ),
        ):
            result = handler.execute(db, lead_id=1, config={}, context={})

        assert result.success is False
        assert "form error" in result.error


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class TestExecutor:
    def test_unknown_action_type_returns_failure(self):
        step = _make_step("send_sms_template", {})
        result = execute_step(MagicMock(), 1, 1, 1, step, {})
        assert result.success is False
        assert "Unknown action_type" in result.error

    def test_move_to_stage_dispatched_correctly(self):
        step = _make_step("move_to_stage", {"stage_id": 7})
        db = MagicMock()
        with patch("api.pipelines.handlers.move_stage.move_stage"):
            result = execute_step(db, lead_id=1, pipeline_id=1, rule_id=1, step=step, context={})
        assert result.success is True
        assert result.new_stage_id == 7

    def test_send_bucket_followup_email_uses_email_handler(self):
        """send_bucket_followup_email must route to the same handler as send_email_template."""
        step = _make_step("send_bucket_followup_email", {})
        result = execute_step(MagicMock(), 1, 1, 1, step, {})
        # No template_id → validation failure from SendEmailTemplateHandler
        assert result.success is False
        assert "template_id" in result.error

    def test_failed_step_returns_result_not_exception(self):
        """execute_step must never raise — errors are captured in ActionResult."""
        step = _make_step("move_to_stage", {"stage_id": 99})
        db = MagicMock()
        with patch(
            "api.pipelines.handlers.move_stage.move_stage",
            side_effect=Exception("unexpected"),
        ):
            result = execute_step(db, 1, 1, 1, step, {})
        assert result.success is False
        assert result.error is not None

    def test_ordered_execution_all_steps_attempted(self):
        """All steps must be attempted even if an earlier step fails."""
        executed = []

        def fake_move(db, lead_id, stage_id, change_source):
            executed.append(stage_id)

        steps = [
            _make_step("move_to_stage", {"stage_id": 2}, step_id=1, position=1),
            _make_step("send_email_template", {}, step_id=2, position=2),   # will fail (no template_id)
            _make_step("move_to_stage", {"stage_id": 3}, step_id=3, position=3),
        ]

        db = MagicMock()
        with patch("api.pipelines.handlers.move_stage.move_stage", side_effect=fake_move):
            results = [execute_step(db, 1, 1, 1, step, {}) for step in steps]

        assert results[0].success is True
        assert results[1].success is False   # missing template_id
        assert results[2].success is True
        assert executed == [2, 3], f"Expected both moves to execute, got {executed}"


# ---------------------------------------------------------------------------
# on_stage_enter chaining via new_stage_id
# ---------------------------------------------------------------------------


class TestStageEnterChaining:
    """Verify that new_stage_id propagates correctly from move_to_stage results.

    The engine uses ActionResult.new_stage_id to queue on_stage_enter rule
    evaluation. This test confirms the executor surfaces it correctly so the
    engine can chain.
    """

    def test_move_to_stage_new_stage_id_propagates(self):
        """new_stage_id must equal the configured stage_id on success."""
        step = _make_step("move_to_stage", {"stage_id": 42})
        db = MagicMock()
        with patch("api.pipelines.handlers.move_stage.move_stage"):
            result = execute_step(db, lead_id=1, pipeline_id=1, rule_id=1, step=step, context={})
        assert result.success is True
        assert result.new_stage_id == 42

    def test_non_move_actions_have_no_new_stage_id(self):
        """send_email_template must not set new_stage_id (only move_to_stage does)."""
        step = _make_step("send_email_template", {})
        # Missing template_id → validation failure, but new_stage_id must still be None
        result = execute_step(MagicMock(), 1, 1, 1, step, {})
        assert result.new_stage_id is None

    def test_failed_move_does_not_set_new_stage_id(self):
        """A failed move_to_stage must not propagate new_stage_id."""
        step = _make_step("move_to_stage", {"stage_id": 10})
        db = MagicMock()
        with patch(
            "api.pipelines.handlers.move_stage.move_stage",
            side_effect=RuntimeError("stage locked"),
        ):
            result = execute_step(db, 1, 1, 1, step, {})
        assert result.success is False
        assert result.new_stage_id is None


# ---------------------------------------------------------------------------
# {form_link} boundary — qualification module owns token creation
# ---------------------------------------------------------------------------


class TestFormLinkBoundary:
    """Verify that TemplateRenderService.render_admin_template delegates {form_link}
    to the qualification module and does not create invitations inline.
    """

    def _make_mock_template(self, subject: str, body: str):
        return SimpleNamespace(subject=subject, body=body)

    def test_form_link_delegates_to_qualification_module(self):
        """{form_link} in template must call get_or_create_form_link, not FormInvitationService directly."""
        from api.communications.template_render import TemplateRenderService

        svc = TemplateRenderService()
        db = MagicMock()
        lead = SimpleNamespace(id=1, name="Alice", company_id=10)
        mock_tpl = SimpleNamespace(subject="Hi {lead_name}", body="Click {form_link}")

        with (
            patch("api.repositories.template_repository.AdminTemplateRepository") as MockRepo,
            patch("gmail_lead_sync.agent_models.AgentUser"),
            patch(
                "gmail_lead_sync.preapproval.handlers.get_or_create_form_link",
                return_value="https://example.com/form/abc123",
            ) as mock_get_link,
        ):
            MockRepo.return_value.get_by_id.return_value = mock_tpl
            db.query.return_value.filter.return_value.first.return_value = None

            subject, body = svc.render_admin_template(db, template_id=1, lead=lead, tenant_id=10)

        mock_get_link.assert_called_once_with(db, 10, 1)
        assert "https://example.com/form/abc123" in body

    def test_no_form_link_placeholder_skips_qualification_call(self):
        """Templates without {form_link} must not call get_or_create_form_link at all."""
        from api.communications.template_render import TemplateRenderService

        svc = TemplateRenderService()
        db = MagicMock()
        lead = SimpleNamespace(id=1, name="Bob", company_id=10)
        mock_tpl = SimpleNamespace(subject="Hello {lead_name}", body="No form link here.")

        with (
            patch("api.repositories.template_repository.AdminTemplateRepository") as MockRepo,
            patch("gmail_lead_sync.agent_models.AgentUser"),
            patch(
                "gmail_lead_sync.preapproval.handlers.get_or_create_form_link"
            ) as mock_get_link,
        ):
            MockRepo.return_value.get_by_id.return_value = mock_tpl
            db.query.return_value.filter.return_value.first.return_value = None

            svc.render_admin_template(db, template_id=1, lead=lead, tenant_id=10)

        mock_get_link.assert_not_called()

    def test_get_or_create_form_link_returns_fallback_when_no_active_form(self):
        """get_or_create_form_link must return fallback URL when no active form version exists."""
        from gmail_lead_sync.preapproval.handlers import get_or_create_form_link

        db = MagicMock()
        with patch(
            "gmail_lead_sync.preapproval.handlers.resolve_active_form_version",
            return_value=None,
        ):
            result = get_or_create_form_link(db, tenant_id=5, lead_id=1)

        assert result.endswith("/public/buyer-qualification")
        assert "/" in result

    def test_get_or_create_form_link_returns_token_url_when_form_exists(self):
        """get_or_create_form_link must return a token URL when an active form version exists."""
        from gmail_lead_sync.preapproval.handlers import get_or_create_form_link
        from types import SimpleNamespace as SN

        db = MagicMock()
        mock_version = SN(id=7)

        with (
            patch(
                "gmail_lead_sync.preapproval.handlers.resolve_active_form_version",
                return_value=mock_version,
            ),
            patch(
                "gmail_lead_sync.preapproval.handlers._invitation_service.create_invitation",
                return_value=("tok123", SN(id=99)),
            ),
        ):
            result = get_or_create_form_link(db, tenant_id=5, lead_id=1)

        assert "tok123" in result

    def test_get_or_create_form_link_falls_back_on_invitation_error(self):
        """get_or_create_form_link must return fallback URL if invitation creation fails."""
        from gmail_lead_sync.preapproval.handlers import get_or_create_form_link
        from types import SimpleNamespace as SN

        db = MagicMock()
        mock_version = SN(id=7)

        with (
            patch(
                "gmail_lead_sync.preapproval.handlers.resolve_active_form_version",
                return_value=mock_version,
            ),
            patch(
                "gmail_lead_sync.preapproval.handlers._invitation_service.create_invitation",
                side_effect=RuntimeError("db locked"),
            ),
        ):
            result = get_or_create_form_link(db, tenant_id=5, lead_id=1)

        assert result.endswith("/public/buyer-qualification")

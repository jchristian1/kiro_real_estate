"""
Unit tests for api/services/template_renderer.py

Tests cover:
- render_template_str: all placeholders substituted
- render_template_str: missing context keys leave placeholder as-is
- render_template_str: subject newlines stripped, body newlines preserved
- render_template_str: empty context leaves text unchanged (except newline strip)
- render_template: all placeholders resolved via DB lookup
- render_template: None fields fall back to empty string
- render_template: unknown agent_user_id → all agent fields empty
- render_template: lead with no id → form_link is empty string
"""

from unittest.mock import MagicMock


from api.services.template_renderer import render_template, render_template_str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lead(id=42, name="Alex Johnson"):
    lead = MagicMock()
    lead.id = id
    lead.name = name
    return lead


def _make_agent(full_name="Sarah Chen", phone="555-1234", email="sarah@example.com"):
    agent = MagicMock()
    agent.full_name = full_name
    agent.phone = phone
    agent.email = email
    return agent


def _make_template(subject, body):
    tmpl = MagicMock()
    tmpl.subject = subject
    tmpl.body = body
    return tmpl


def _make_db(agent_user=None):
    db = MagicMock()
    db.get.return_value = agent_user
    return db


# ---------------------------------------------------------------------------
# render_template_str tests
# ---------------------------------------------------------------------------

class TestRenderTemplateStr:
    def test_all_placeholders_substituted(self):
        context = {
            "lead_name": "Alex",
            "agent_name": "Sarah",
            "agent_phone": "555-1234",
            "agent_email": "sarah@example.com",
            "form_link": "https://app.example.com/form/42",
        }
        result = render_template_str(
            subject="Hi {lead_name}, I'm {agent_name}",
            body="Call me at {agent_phone} or email {agent_email}. Form: {form_link}",
            context=context,
        )
        assert result["subject"] == "Hi Alex, I'm Sarah"
        assert result["body"] == "Call me at 555-1234 or email sarah@example.com. Form: https://app.example.com/form/42"

    def test_subject_newlines_stripped(self):
        result = render_template_str(
            subject="Hello\nWorld\r\nTest",
            body="Body\nwith\nnewlines",
            context={},
        )
        assert "\n" not in result["subject"]
        assert "\r" not in result["subject"]
        assert result["subject"] == "HelloWorldTest"

    def test_body_newlines_preserved(self):
        body = "Line 1\nLine 2\r\nLine 3"
        result = render_template_str(subject="Subject", body=body, context={})
        assert result["body"] == body

    def test_empty_context_leaves_placeholders(self):
        result = render_template_str(
            subject="{lead_name}",
            body="{agent_name}",
            context={},
        )
        assert result["subject"] == "{lead_name}"
        assert result["body"] == "{agent_name}"

    def test_partial_context_substitutes_only_provided(self):
        result = render_template_str(
            subject="{lead_name} — {agent_name}",
            body="",
            context={"lead_name": "Alex"},
        )
        assert result["subject"] == "Alex — {agent_name}"

    def test_empty_value_replaces_placeholder(self):
        result = render_template_str(
            subject="Hi {lead_name}!",
            body="",
            context={"lead_name": ""},
        )
        assert result["subject"] == "Hi !"

    def test_returns_dict_with_subject_and_body_keys(self):
        result = render_template_str("s", "b", {})
        assert set(result.keys()) == {"subject", "body"}


# ---------------------------------------------------------------------------
# render_template tests
# ---------------------------------------------------------------------------

class TestRenderTemplate:
    def test_all_placeholders_resolved(self):
        agent = _make_agent(full_name="Sarah Chen", phone="555-1234", email="sarah@example.com")
        lead = _make_lead(id=42, name="Alex Johnson")
        db = _make_db(agent_user=agent)
        tmpl = _make_template(
            subject="Hi {lead_name}, I'm {agent_name}",
            body="Phone: {agent_phone} Email: {agent_email} Form: {form_link}",
        )

        result = render_template(tmpl, lead, agent_user_id=1, db=db)

        assert result["subject"] == "Hi Alex Johnson, I'm Sarah Chen"
        assert "555-1234" in result["body"]
        assert "sarah@example.com" in result["body"]
        assert "https://app.example.com/form/42" in result["body"]

    def test_form_link_uses_lead_id(self):
        agent = _make_agent()
        lead = _make_lead(id=99)
        db = _make_db(agent_user=agent)
        tmpl = _make_template(subject="", body="{form_link}")

        result = render_template(tmpl, lead, agent_user_id=1, db=db)

        assert result["body"] == "https://app.example.com/form/99"

    def test_lead_name_none_becomes_empty_string(self):
        agent = _make_agent()
        lead = _make_lead(name=None)
        db = _make_db(agent_user=agent)
        tmpl = _make_template(subject="Hi {lead_name}", body="")

        result = render_template(tmpl, lead, agent_user_id=1, db=db)

        assert result["subject"] == "Hi "

    def test_agent_not_found_fields_empty(self):
        lead = _make_lead()
        db = _make_db(agent_user=None)
        tmpl = _make_template(
            subject="{agent_name}",
            body="{agent_phone} {agent_email}",
        )

        result = render_template(tmpl, lead, agent_user_id=999, db=db)

        assert result["subject"] == ""
        assert result["body"] == " "

    def test_agent_phone_none_becomes_empty_string(self):
        agent = _make_agent(phone=None)
        lead = _make_lead()
        db = _make_db(agent_user=agent)
        tmpl = _make_template(subject="", body="Phone: {agent_phone}")

        result = render_template(tmpl, lead, agent_user_id=1, db=db)

        assert result["body"] == "Phone: "

    def test_lead_with_no_id_form_link_empty(self):
        agent = _make_agent()
        lead = MagicMock()
        lead.id = None
        lead.name = "Alex"
        db = _make_db(agent_user=agent)
        tmpl = _make_template(subject="", body="{form_link}")

        result = render_template(tmpl, lead, agent_user_id=1, db=db)

        assert result["body"] == ""

    def test_subject_newlines_stripped(self):
        agent = _make_agent()
        lead = _make_lead()
        db = _make_db(agent_user=agent)
        tmpl = _make_template(subject="Hello\nWorld", body="Body\ntext")

        result = render_template(tmpl, lead, agent_user_id=1, db=db)

        assert "\n" not in result["subject"]
        assert "\n" in result["body"]

    def test_db_get_called_with_correct_agent_user_id(self):
        from gmail_lead_sync.agent_models import AgentUser

        agent = _make_agent()
        lead = _make_lead()
        db = _make_db(agent_user=agent)
        tmpl = _make_template(subject="", body="")

        render_template(tmpl, lead, agent_user_id=7, db=db)

        db.get.assert_called_once_with(AgentUser, 7)

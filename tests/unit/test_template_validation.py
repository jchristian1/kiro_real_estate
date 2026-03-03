"""
Comprehensive tests for template validation requirements.

This test file specifically validates Task 8.2 requirements:
- Email header injection patterns (newlines in subject)
- Placeholder validation: {lead_name}, {agent_name}, {agent_phone}, {agent_email}
- Validation errors for unsupported placeholders

Requirements:
- 3.2: Validate against email header injection patterns
- 3.4: Validate that all placeholders in templates are supported
- 3.5: Display available placeholders for template creation
- 10.2: Validate Template against email header injection patterns
- 13.4: Validate that Template placeholders match supported fields
- 13.5: Return validation errors listing invalid placeholders
"""

import pytest
from pydantic import ValidationError

from api.models.template_models import (
    TemplateCreateRequest,
    TemplateUpdateRequest,
    SUPPORTED_PLACEHOLDERS
)


class TestHeaderInjectionValidation:
    """Tests for email header injection validation in subject lines."""
    
    def test_subject_with_carriage_return_newline_fails(self):
        """Test that subject with \\r\\n (CRLF) fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Bad Template",
                subject="Subject\r\nBcc: attacker@evil.com",
                body="Body"
            )
        
        error_msg = str(exc_info.value).lower()
        assert "header injection" in error_msg or "newline" in error_msg
    
    def test_subject_with_newline_fails(self):
        """Test that subject with \\n fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Bad Template",
                subject="Subject\nBcc: attacker@evil.com",
                body="Body"
            )
        
        error_msg = str(exc_info.value).lower()
        assert "header injection" in error_msg or "newline" in error_msg
    
    def test_subject_with_carriage_return_fails(self):
        """Test that subject with \\r fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Bad Template",
                subject="Subject\rBcc: attacker@evil.com",
                body="Body"
            )
        
        error_msg = str(exc_info.value).lower()
        assert "header injection" in error_msg or "newline" in error_msg
    
    def test_subject_without_newlines_succeeds(self):
        """Test that subject without newlines passes validation."""
        template = TemplateCreateRequest(
            name="Good Template",
            subject="This is a valid subject line",
            body="Body"
        )
        
        assert template.subject == "This is a valid subject line"
    
    def test_update_subject_with_newline_fails(self):
        """Test that updating subject with newline fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateUpdateRequest(
                subject="Subject\nBcc: attacker@evil.com"
            )
        
        error_msg = str(exc_info.value).lower()
        assert "header injection" in error_msg or "newline" in error_msg


class TestPlaceholderValidation:
    """Tests for placeholder validation in template body."""
    
    def test_all_supported_placeholders_succeed(self):
        """Test that all supported placeholders pass validation."""
        template = TemplateCreateRequest(
            name="Full Template",
            subject="Hello {lead_name}",
            body=(
                "Hi {lead_name},\n\n"
                "I'm {agent_name} and I'll be happy to assist you.\n\n"
                "You can reach me at {agent_phone} or {agent_email}.\n\n"
                "Best regards,\n{agent_name}"
            )
        )
        
        # Verify all placeholders are present
        assert "{lead_name}" in template.body
        assert "{agent_name}" in template.body
        assert "{agent_phone}" in template.body
        assert "{agent_email}" in template.body
    
    def test_lead_name_placeholder_succeeds(self):
        """Test that {lead_name} placeholder is valid."""
        template = TemplateCreateRequest(
            name="Template",
            subject="Subject",
            body="Hi {lead_name}, welcome!"
        )
        
        assert "{lead_name}" in template.body
    
    def test_agent_name_placeholder_succeeds(self):
        """Test that {agent_name} placeholder is valid."""
        template = TemplateCreateRequest(
            name="Template",
            subject="Subject",
            body="I'm {agent_name}, your agent."
        )
        
        assert "{agent_name}" in template.body
    
    def test_agent_phone_placeholder_succeeds(self):
        """Test that {agent_phone} placeholder is valid."""
        template = TemplateCreateRequest(
            name="Template",
            subject="Subject",
            body="Call me at {agent_phone}."
        )
        
        assert "{agent_phone}" in template.body
    
    def test_agent_email_placeholder_succeeds(self):
        """Test that {agent_email} placeholder is valid."""
        template = TemplateCreateRequest(
            name="Template",
            subject="Subject",
            body="Email me at {agent_email}."
        )
        
        assert "{agent_email}" in template.body
    
    def test_invalid_placeholder_fails(self):
        """Test that unsupported placeholder fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Bad Template",
                subject="Subject",
                body="Hi {lead_name}, your {invalid_placeholder} is ready."
            )
        
        error_msg = str(exc_info.value).lower()
        assert "invalid_placeholder" in error_msg or "invalid placeholder" in error_msg
    
    def test_multiple_invalid_placeholders_fail(self):
        """Test that multiple unsupported placeholders fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Bad Template",
                subject="Subject",
                body="Hi {lead_name}, your {bad_one} and {bad_two} are ready."
            )
        
        error_msg = str(exc_info.value).lower()
        # Should mention at least one invalid placeholder
        assert "bad_one" in error_msg or "bad_two" in error_msg or "invalid placeholder" in error_msg
    
    def test_validation_error_lists_supported_placeholders(self):
        """Test that validation error lists supported placeholders."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Bad Template",
                subject="Subject",
                body="Hi {invalid_placeholder}."
            )
        
        error_msg = str(exc_info.value)
        # Should mention supported placeholders
        assert "supported" in error_msg.lower() or "valid" in error_msg.lower()
    
    def test_no_placeholders_succeeds(self):
        """Test that template without placeholders passes validation."""
        template = TemplateCreateRequest(
            name="Simple Template",
            subject="Subject",
            body="This is a simple body without any placeholders."
        )
        
        assert template.body == "This is a simple body without any placeholders."
    
    def test_update_body_with_invalid_placeholder_fails(self):
        """Test that updating body with invalid placeholder fails."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateUpdateRequest(
                body="Body with {invalid_placeholder}"
            )
        
        error_msg = str(exc_info.value).lower()
        assert "invalid_placeholder" in error_msg or "invalid placeholder" in error_msg


class TestSupportedPlaceholders:
    """Tests for the SUPPORTED_PLACEHOLDERS constant."""
    
    def test_supported_placeholders_constant_exists(self):
        """Test that SUPPORTED_PLACEHOLDERS constant is defined."""
        assert SUPPORTED_PLACEHOLDERS is not None
        assert isinstance(SUPPORTED_PLACEHOLDERS, set)
    
    def test_supported_placeholders_contains_required_fields(self):
        """Test that SUPPORTED_PLACEHOLDERS contains all required fields."""
        required = {'{lead_name}', '{agent_name}', '{agent_phone}', '{agent_email}'}
        assert required == SUPPORTED_PLACEHOLDERS
    
    def test_supported_placeholders_count(self):
        """Test that there are exactly 4 supported placeholders."""
        assert len(SUPPORTED_PLACEHOLDERS) == 4


class TestCombinedValidation:
    """Tests for combined validation scenarios."""
    
    def test_header_injection_and_invalid_placeholder_both_fail(self):
        """Test that both header injection and invalid placeholder are caught."""
        # Header injection should be caught first (subject validation)
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Bad Template",
                subject="Subject\nBcc: attacker@evil.com",
                body="Body with {invalid_placeholder}"
            )
        
        error_msg = str(exc_info.value).lower()
        # Should catch header injection in subject
        assert "header injection" in error_msg or "newline" in error_msg
    
    def test_valid_subject_with_invalid_placeholder_fails_on_body(self):
        """Test that valid subject but invalid placeholder fails on body validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Template",
                subject="Valid Subject",
                body="Body with {invalid_placeholder}"
            )
        
        error_msg = str(exc_info.value).lower()
        # Should catch invalid placeholder in body
        assert "invalid_placeholder" in error_msg or "invalid placeholder" in error_msg
    
    def test_valid_template_with_all_features_succeeds(self):
        """Test that a fully valid template with all features passes."""
        template = TemplateCreateRequest(
            name="Complete Template",
            subject="Thank you {lead_name}",
            body=(
                "Dear {lead_name},\n\n"
                "Thank you for your inquiry. I'm {agent_name}, "
                "and I'll be your dedicated agent.\n\n"
                "You can reach me at:\n"
                "Phone: {agent_phone}\n"
                "Email: {agent_email}\n\n"
                "I look forward to working with you!\n\n"
                "Best regards,\n"
                "{agent_name}"
            )
        )
        
        # Verify all fields are set correctly
        assert template.name == "Complete Template"
        assert "{lead_name}" in template.subject
        assert all(p in template.body for p in [
            "{lead_name}", "{agent_name}", "{agent_phone}", "{agent_email}"
        ])


class TestEdgeCases:
    """Tests for edge cases in template validation."""
    
    def test_placeholder_in_subject_is_allowed(self):
        """Test that placeholders in subject line are allowed."""
        template = TemplateCreateRequest(
            name="Template",
            subject="Hello {lead_name}",
            body="Body"
        )
        
        assert "{lead_name}" in template.subject
    
    def test_empty_braces_not_treated_as_placeholder(self):
        """Test that empty braces {} are not treated as invalid placeholder."""
        # Empty braces don't match the placeholder regex pattern \{[^}]+\}
        # so they're ignored (acceptable behavior)
        template = TemplateCreateRequest(
            name="Template",
            subject="Subject",
            body="Body with {} empty braces"
        )
        
        # Should succeed because {} doesn't match placeholder pattern
        assert template.body == "Body with {} empty braces"
    
    def test_malformed_placeholder_ignored(self):
        """Test that malformed placeholders are ignored (acceptable behavior)."""
        # Malformed placeholders (missing closing brace) don't match the regex
        # pattern \{[^}]+\}, so they're treated as literal text
        template = TemplateCreateRequest(
            name="Template",
            subject="Subject",
            body="Body with {malformed_placeholder"
        )
        
        # Should succeed because incomplete braces don't match placeholder pattern
        assert "{malformed_placeholder" in template.body
    
    def test_case_sensitive_placeholder_validation(self):
        """Test that placeholder validation is case-sensitive."""
        # {Lead_Name} should fail because it's not exactly {lead_name}
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Template",
                subject="Subject",
                body="Hi {Lead_Name}"
            )
        
        error_msg = str(exc_info.value).lower()
        assert "lead_name" in error_msg or "invalid" in error_msg
    
    def test_placeholder_with_spaces_fails(self):
        """Test that placeholders with spaces fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateCreateRequest(
                name="Template",
                subject="Subject",
                body="Hi { lead_name }"
            )
        
        error_msg = str(exc_info.value).lower()
        assert "invalid" in error_msg or "supported" in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

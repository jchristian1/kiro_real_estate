"""
Unit tests for API input validation and sanitization.

Tests the validation utilities to ensure proper input sanitization,
length enforcement, and security hardening for agent management endpoints.

Requirements:
- 10.1: Sanitize all user input before processing
- 10.4: Enforce maximum length limits on all text fields
- 10.5: Validate email addresses against RFC 5322 format
- 24.6: Include tests for input sanitization functions
"""

import pytest
from pydantic import ValidationError

from api.utils.validation import (
    sanitize_string,
    sanitize_agent_id,
    sanitize_email,
    sanitize_password,
    MAX_AGENT_ID_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH
)
from api.models.agent_models import AgentCreateRequest, AgentUpdateRequest


class TestSanitizeString:
    """Tests for general string sanitization."""
    
    def test_removes_null_bytes(self):
        """Test that null bytes are removed from strings."""
        value = "Hello\x00World\x00Test"
        sanitized = sanitize_string(value)
        assert '\x00' not in sanitized
        assert sanitized == "HelloWorldTest"
    
    def test_removes_control_characters(self):
        """Test that control characters are removed (except newlines and tabs)."""
        value = "Hello\x01\x02World\x1fTest"
        sanitized = sanitize_string(value)
        assert '\x01' not in sanitized
        assert '\x02' not in sanitized
        assert '\x1f' not in sanitized
        assert sanitized == "HelloWorldTest"
    
    def test_preserves_newlines_and_tabs(self):
        """Test that newlines and tabs are preserved."""
        value = "Hello\nWorld\tTest"
        sanitized = sanitize_string(value)
        assert '\n' in sanitized
        assert '\t' in sanitized
        assert sanitized == "Hello\nWorld\tTest"
    
    def test_strips_whitespace(self):
        """Test that leading and trailing whitespace is stripped."""
        value = "  Hello World  "
        sanitized = sanitize_string(value)
        assert sanitized == "Hello World"
    
    def test_enforces_max_length(self):
        """Test that maximum length is enforced."""
        value = "A" * 100
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_string(value, max_length=50)
    
    def test_allows_within_max_length(self):
        """Test that strings within max length are allowed."""
        value = "A" * 50
        sanitized = sanitize_string(value, max_length=50)
        assert sanitized == value
    
    def test_handles_empty_string(self):
        """Test that empty strings are handled correctly."""
        sanitized = sanitize_string("")
        assert sanitized == ""
    
    def test_handles_unicode(self):
        """Test that unicode content is preserved."""
        value = "Hello 世界 🌍 Émojis"
        sanitized = sanitize_string(value)
        assert sanitized == value
    
    def test_rejects_non_string(self):
        """Test that non-string values are rejected."""
        with pytest.raises(ValueError, match="must be a string"):
            sanitize_string(123)


class TestSanitizeAgentId:
    """Tests for agent ID sanitization and validation."""
    
    def test_valid_alphanumeric(self):
        """Test that valid alphanumeric agent IDs are accepted."""
        agent_id = "agent123"
        sanitized = sanitize_agent_id(agent_id)
        assert sanitized == agent_id
    
    def test_valid_with_hyphens(self):
        """Test that agent IDs with hyphens are accepted."""
        agent_id = "agent-123"
        sanitized = sanitize_agent_id(agent_id)
        assert sanitized == agent_id
    
    def test_valid_with_underscores(self):
        """Test that agent IDs with underscores are accepted."""
        agent_id = "agent_123"
        sanitized = sanitize_agent_id(agent_id)
        assert sanitized == agent_id
    
    def test_valid_with_dots(self):
        """Test that agent IDs with dots are accepted."""
        agent_id = "agent.123"
        sanitized = sanitize_agent_id(agent_id)
        assert sanitized == agent_id
    
    def test_rejects_special_characters(self):
        """Test that agent IDs with special characters are rejected."""
        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            sanitize_agent_id("agent@123")
        
        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            sanitize_agent_id("agent#123")
        
        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            sanitize_agent_id("agent 123")  # Space
    
    def test_rejects_empty_after_sanitization(self):
        """Test that empty agent IDs are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_agent_id("   ")  # Only whitespace
    
    def test_enforces_max_length(self):
        """Test that maximum length is enforced."""
        long_id = "a" * (MAX_AGENT_ID_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_agent_id(long_id)
    
    def test_removes_null_bytes(self):
        """Test that null bytes are removed."""
        agent_id = "agent\x00123"
        sanitized = sanitize_agent_id(agent_id)
        assert '\x00' not in sanitized
        assert sanitized == "agent123"


class TestSanitizeEmail:
    """Tests for email sanitization."""
    
    def test_valid_email(self):
        """Test that valid emails are accepted."""
        email = "user@example.com"
        sanitized = sanitize_email(email)
        assert sanitized == email
    
    def test_removes_null_bytes(self):
        """Test that null bytes are removed."""
        email = "user\x00@example.com"
        sanitized = sanitize_email(email)
        assert '\x00' not in sanitized
        assert sanitized == "user@example.com"
    
    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        email = "  user@example.com  "
        sanitized = sanitize_email(email)
        assert sanitized == "user@example.com"
    
    def test_enforces_max_length(self):
        """Test that maximum length is enforced."""
        long_email = "a" * (MAX_EMAIL_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_email(long_email)
    
    def test_rejects_empty(self):
        """Test that empty emails are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_email("   ")


class TestSanitizePassword:
    """Tests for password sanitization."""
    
    def test_valid_password(self):
        """Test that valid passwords are accepted."""
        password = "my-secure-password-123"
        sanitized = sanitize_password(password)
        assert sanitized == password
    
    def test_removes_null_bytes(self):
        """Test that null bytes are removed."""
        password = "pass\x00word"
        sanitized = sanitize_password(password)
        assert '\x00' not in sanitized
        assert sanitized == "password"
    
    def test_preserves_special_characters(self):
        """Test that special characters in passwords are preserved."""
        password = "p@ssw0rd!#$%"
        sanitized = sanitize_password(password)
        assert sanitized == password
    
    def test_preserves_whitespace(self):
        """Test that whitespace in passwords is preserved (might be intentional)."""
        password = "pass word"
        sanitized = sanitize_password(password)
        assert sanitized == password
    
    def test_enforces_max_length(self):
        """Test that maximum length is enforced."""
        long_password = "a" * (MAX_PASSWORD_LENGTH + 1)
        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_password(long_password)
    
    def test_rejects_empty(self):
        """Test that empty passwords are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            sanitize_password("")
    
    def test_rejects_non_string(self):
        """Test that non-string passwords are rejected."""
        with pytest.raises(ValueError, match="must be a string"):
            sanitize_password(123)


class TestAgentCreateRequestValidation:
    """Tests for AgentCreateRequest model validation."""
    
    def test_valid_request(self):
        """Test that valid agent creation requests are accepted."""
        request = AgentCreateRequest(
            agent_id="agent1",
            email="agent1@example.com",
            app_password="secure-password"
        )
        assert request.agent_id == "agent1"
        assert request.email == "agent1@example.com"
        assert request.app_password == "secure-password"
    
    def test_sanitizes_agent_id(self):
        """Test that agent_id is sanitized."""
        request = AgentCreateRequest(
            agent_id="  agent1  ",
            email="agent1@example.com",
            app_password="secure-password"
        )
        assert request.agent_id == "agent1"  # Whitespace stripped
    
    def test_sanitizes_email(self):
        """Test that email is sanitized."""
        request = AgentCreateRequest(
            agent_id="agent1",
            email="  agent1@example.com  ",
            app_password="secure-password"
        )
        assert request.email == "agent1@example.com"  # Whitespace stripped
    
    def test_sanitizes_password(self):
        """Test that password is sanitized (null bytes removed)."""
        request = AgentCreateRequest(
            agent_id="agent1",
            email="agent1@example.com",
            app_password="pass\x00word"
        )
        assert '\x00' not in request.app_password
        assert request.app_password == "password"
    
    def test_rejects_invalid_email_format(self):
        """Test that invalid email formats are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCreateRequest(
                agent_id="agent1",
                email="not-an-email",
                app_password="secure-password"
            )
        assert "email" in str(exc_info.value).lower()
    
    def test_rejects_invalid_agent_id_format(self):
        """Test that invalid agent_id formats are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCreateRequest(
                agent_id="agent@123",  # @ not allowed
                email="agent1@example.com",
                app_password="secure-password"
            )
        assert "agent_id" in str(exc_info.value).lower()
    
    def test_rejects_empty_agent_id(self):
        """Test that empty agent_id is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCreateRequest(
                agent_id="",
                email="agent1@example.com",
                app_password="secure-password"
            )
        assert "agent_id" in str(exc_info.value).lower()
    
    def test_rejects_empty_password(self):
        """Test that empty password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCreateRequest(
                agent_id="agent1",
                email="agent1@example.com",
                app_password=""
            )
        assert "app_password" in str(exc_info.value).lower()
    
    def test_rejects_too_long_agent_id(self):
        """Test that agent_id exceeding max length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCreateRequest(
                agent_id="a" * (MAX_AGENT_ID_LENGTH + 1),
                email="agent1@example.com",
                app_password="secure-password"
            )
        assert "agent_id" in str(exc_info.value).lower()
    
    def test_rejects_too_long_email(self):
        """Test that email exceeding max length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCreateRequest(
                agent_id="agent1",
                email="a" * (MAX_EMAIL_LENGTH + 1),
                app_password="secure-password"
            )
        assert "email" in str(exc_info.value).lower()
    
    def test_rejects_too_long_password(self):
        """Test that password exceeding max length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCreateRequest(
                agent_id="agent1",
                email="agent1@example.com",
                app_password="a" * (MAX_PASSWORD_LENGTH + 1)
            )
        assert "app_password" in str(exc_info.value).lower()


class TestAgentUpdateRequestValidation:
    """Tests for AgentUpdateRequest model validation."""
    
    def test_valid_request_with_email(self):
        """Test that valid update requests with email are accepted."""
        request = AgentUpdateRequest(email="newemail@example.com")
        assert request.email == "newemail@example.com"
        assert request.app_password is None
    
    def test_valid_request_with_password(self):
        """Test that valid update requests with password are accepted."""
        request = AgentUpdateRequest(app_password="new-password")
        assert request.app_password == "new-password"
        assert request.email is None
    
    def test_valid_request_with_both(self):
        """Test that valid update requests with both fields are accepted."""
        request = AgentUpdateRequest(
            email="newemail@example.com",
            app_password="new-password"
        )
        assert request.email == "newemail@example.com"
        assert request.app_password == "new-password"
    
    def test_valid_request_with_neither(self):
        """Test that update requests with no fields are accepted (validation happens in endpoint)."""
        request = AgentUpdateRequest()
        assert request.email is None
        assert request.app_password is None
    
    def test_sanitizes_email(self):
        """Test that email is sanitized."""
        request = AgentUpdateRequest(email="  newemail@example.com  ")
        assert request.email == "newemail@example.com"
    
    def test_sanitizes_password(self):
        """Test that password is sanitized."""
        request = AgentUpdateRequest(app_password="pass\x00word")
        assert '\x00' not in request.app_password
        assert request.app_password == "password"
    
    def test_rejects_invalid_email_format(self):
        """Test that invalid email formats are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentUpdateRequest(email="not-an-email")
        assert "email" in str(exc_info.value).lower()
    
    def test_rejects_empty_password(self):
        """Test that empty password is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentUpdateRequest(app_password="")
        assert "app_password" in str(exc_info.value).lower()
    
    def test_rejects_too_long_email(self):
        """Test that email exceeding max length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentUpdateRequest(email="a" * (MAX_EMAIL_LENGTH + 1))
        assert "email" in str(exc_info.value).lower()
    
    def test_rejects_too_long_password(self):
        """Test that password exceeding max length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentUpdateRequest(app_password="a" * (MAX_PASSWORD_LENGTH + 1))
        assert "app_password" in str(exc_info.value).lower()


class TestRFC5322EmailValidation:
    """Tests for RFC 5322 email validation compliance."""
    
    def test_accepts_standard_email(self):
        """Test that standard email formats are accepted."""
        request = AgentCreateRequest(
            agent_id="agent1",
            email="user@example.com",
            app_password="password"
        )
        assert request.email == "user@example.com"
    
    def test_accepts_email_with_plus(self):
        """Test that emails with + are accepted (RFC 5322 compliant)."""
        request = AgentCreateRequest(
            agent_id="agent1",
            email="user+tag@example.com",
            app_password="password"
        )
        assert request.email == "user+tag@example.com"
    
    def test_accepts_email_with_dots(self):
        """Test that emails with dots are accepted."""
        request = AgentCreateRequest(
            agent_id="agent1",
            email="first.last@example.com",
            app_password="password"
        )
        assert request.email == "first.last@example.com"
    
    def test_accepts_email_with_subdomain(self):
        """Test that emails with subdomains are accepted."""
        request = AgentCreateRequest(
            agent_id="agent1",
            email="user@mail.example.com",
            app_password="password"
        )
        assert request.email == "user@mail.example.com"
    
    def test_rejects_email_without_at(self):
        """Test that emails without @ are rejected."""
        with pytest.raises(ValidationError):
            AgentCreateRequest(
                agent_id="agent1",
                email="userexample.com",
                app_password="password"
            )
    
    def test_rejects_email_without_domain(self):
        """Test that emails without domain are rejected."""
        with pytest.raises(ValidationError):
            AgentCreateRequest(
                agent_id="agent1",
                email="user@",
                app_password="password"
            )
    
    def test_rejects_email_without_local_part(self):
        """Test that emails without local part are rejected."""
        with pytest.raises(ValidationError):
            AgentCreateRequest(
                agent_id="agent1",
                email="@example.com",
                app_password="password"
            )

"""
Unit tests for the TemplateRenderer class.

Tests template rendering with placeholder replacement and validation.
"""

import pytest
from gmail_lead_sync.responder import TemplateRenderer
from gmail_lead_sync.models import Template, Lead


class TestTemplateRenderer:
    """Test suite for TemplateRenderer class."""
    
    def test_render_template_with_all_placeholders(self):
        """Test successful template rendering with all placeholders."""
        # Create template with all supported placeholders
        template = Template(
            id=1,
            name="Test Template",
            subject="Welcome {lead_name}",
            body="Hi {lead_name},\n\nThank you for your interest. "
                 "I'm {agent_name} and you can reach me at {agent_phone} or {agent_email}.\n\n"
                 "Best regards,\n{agent_name}"
        )
        
        # Create lead
        lead = Lead(
            id=1,
            name="John Doe",
            phone="555-1234",
            source_email="leads@example.com",
            lead_source_id=1,
            gmail_uid="12345"
        )
        
        # Agent info
        agent_info = {
            'agent_name': 'Jane Smith',
            'agent_phone': '555-9876',
            'agent_email': 'jane@realestate.com'
        }
        
        # Render template
        renderer = TemplateRenderer()
        result = renderer.render_template(template, lead, agent_info)
        
        # Verify all placeholders are replaced
        assert '{lead_name}' not in result
        assert '{agent_name}' not in result
        assert '{agent_phone}' not in result
        assert '{agent_email}' not in result
        
        # Verify actual values are present
        assert 'John Doe' in result
        assert 'Jane Smith' in result
        assert '555-9876' in result
        assert 'jane@realestate.com' in result
    
    def test_render_template_with_partial_placeholders(self):
        """Test template rendering with only some placeholders."""
        template = Template(
            id=1,
            name="Simple Template",
            subject="Hello",
            body="Hi {lead_name}, contact me at {agent_email}."
        )
        
        lead = Lead(
            id=1,
            name="Alice Johnson",
            phone="555-0000",
            source_email="leads@example.com",
            lead_source_id=1,
            gmail_uid="67890"
        )
        
        agent_info = {
            'agent_name': 'Bob Agent',
            'agent_phone': '555-1111',
            'agent_email': 'bob@realestate.com'
        }
        
        renderer = TemplateRenderer()
        result = renderer.render_template(template, lead, agent_info)
        
        # Verify used placeholders are replaced
        assert 'Alice Johnson' in result
        assert 'bob@realestate.com' in result
        assert '{lead_name}' not in result
        assert '{agent_email}' not in result
    
    def test_render_template_with_missing_agent_info(self):
        """Test template rendering when agent info is incomplete."""
        template = Template(
            id=1,
            name="Test Template",
            subject="Hello",
            body="Hi {lead_name}, call {agent_phone}."
        )
        
        lead = Lead(
            id=1,
            name="Test Lead",
            phone="555-0000",
            source_email="leads@example.com",
            lead_source_id=1,
            gmail_uid="11111"
        )
        
        # Missing agent_phone in agent_info
        agent_info = {
            'agent_name': 'Agent Name',
            'agent_email': 'agent@example.com'
        }
        
        renderer = TemplateRenderer()
        result = renderer.render_template(template, lead, agent_info)
        
        # Should replace with empty string when key is missing
        assert 'Test Lead' in result
        assert '{lead_name}' not in result
        # agent_phone should be replaced with empty string
        assert 'call .' in result
    
    def test_render_template_validation_fails_with_unsupported_placeholder(self):
        """Test that validation fails when unsupported placeholders remain."""
        template = Template(
            id=1,
            name="Invalid Template",
            subject="Hello",
            body="Hi {lead_name}, your property is {property_address}."
        )
        
        lead = Lead(
            id=1,
            name="Test Lead",
            phone="555-0000",
            source_email="leads@example.com",
            lead_source_id=1,
            gmail_uid="22222"
        )
        
        agent_info = {
            'agent_name': 'Agent',
            'agent_phone': '555-1234',
            'agent_email': 'agent@example.com'
        }
        
        renderer = TemplateRenderer()
        
        # Should raise ValueError because {property_address} is not supported
        with pytest.raises(ValueError) as exc_info:
            renderer.render_template(template, lead, agent_info)
        
        assert 'Unreplaced placeholders' in str(exc_info.value)
        assert '{property_address}' in str(exc_info.value)
    
    def test_render_template_with_no_placeholders(self):
        """Test template rendering with no placeholders."""
        template = Template(
            id=1,
            name="Static Template",
            subject="Hello",
            body="This is a static message with no placeholders."
        )
        
        lead = Lead(
            id=1,
            name="Test Lead",
            phone="555-0000",
            source_email="leads@example.com",
            lead_source_id=1,
            gmail_uid="33333"
        )
        
        agent_info = {
            'agent_name': 'Agent',
            'agent_phone': '555-1234',
            'agent_email': 'agent@example.com'
        }
        
        renderer = TemplateRenderer()
        result = renderer.render_template(template, lead, agent_info)
        
        # Should return the body unchanged
        assert result == "This is a static message with no placeholders."
    
    def test_render_template_with_multiple_occurrences(self):
        """Test that all occurrences of a placeholder are replaced."""
        template = Template(
            id=1,
            name="Repetitive Template",
            subject="Hello",
            body="Hi {lead_name}, welcome {lead_name}! We're glad to have you, {lead_name}."
        )
        
        lead = Lead(
            id=1,
            name="Sarah Connor",
            phone="555-0000",
            source_email="leads@example.com",
            lead_source_id=1,
            gmail_uid="44444"
        )
        
        agent_info = {
            'agent_name': 'Agent',
            'agent_phone': '555-1234',
            'agent_email': 'agent@example.com'
        }
        
        renderer = TemplateRenderer()
        result = renderer.render_template(template, lead, agent_info)
        
        # All three occurrences should be replaced
        assert result.count('Sarah Connor') == 3
        assert '{lead_name}' not in result



class TestAutoResponder:
    """Test suite for AutoResponder class."""
    
    @pytest.fixture
    def mock_credentials_store(self):
        """Mock credentials store for testing."""
        from unittest.mock import Mock
        store = Mock()
        store.get_credentials.return_value = ('test@gmail.com', 'test_app_password')
        return store
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session for testing."""
        from unittest.mock import Mock
        session = Mock()
        return session
    
    @pytest.fixture
    def sample_lead(self):
        """Create a sample lead for testing."""
        return Lead(
            id=1,
            name="John Doe",
            phone="555-1234",
            source_email="john@example.com",
            lead_source_id=1,
            gmail_uid="12345",
            response_sent=False,
            response_status=None
        )
    
    @pytest.fixture
    def sample_template(self):
        """Create a sample template for testing."""
        return Template(
            id=1,
            name="Test Template",
            subject="Thank you {lead_name}",
            body="Hi {lead_name}, thank you for your interest. Contact me at {agent_email}."
        )
    
    @pytest.fixture
    def sample_lead_source_with_template(self, sample_template):
        """Create a lead source with auto-response enabled and template."""
        from gmail_lead_sync.models import LeadSource
        lead_source = LeadSource(
            id=1,
            sender_email="leads@example.com",
            identifier_snippet="New Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            template_id=1,
            auto_respond_enabled=True
        )
        lead_source.template = sample_template
        return lead_source
    
    @pytest.fixture
    def sample_lead_source_disabled(self):
        """Create a lead source with auto-response disabled."""
        from gmail_lead_sync.models import LeadSource
        return LeadSource(
            id=2,
            sender_email="leads@example.com",
            identifier_snippet="New Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            template_id=None,
            auto_respond_enabled=False
        )
    
    def test_send_acknowledgment_disabled(self, mock_credentials_store, mock_db_session,
                                         sample_lead, sample_lead_source_disabled):
        """Test that no email is sent when auto_respond_enabled is False."""
        from gmail_lead_sync.responder import AutoResponder
        
        responder = AutoResponder(mock_credentials_store, mock_db_session)
        result = responder.send_acknowledgment(sample_lead, sample_lead_source_disabled)
        
        assert result is False
        # Credentials should not be retrieved
        mock_credentials_store.get_credentials.assert_not_called()
    
    def test_send_acknowledgment_no_template(self, mock_credentials_store, mock_db_session,
                                            sample_lead):
        """Test that no email is sent when template is not configured."""
        from gmail_lead_sync.models import LeadSource
        
        lead_source = LeadSource(
            id=3,
            sender_email="leads@example.com",
            identifier_snippet="New Lead",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)",
            template_id=None,
            auto_respond_enabled=True
        )
        lead_source.template = None
        
        from gmail_lead_sync.responder import AutoResponder
        responder = AutoResponder(mock_credentials_store, mock_db_session)
        result = responder.send_acknowledgment(sample_lead, lead_source)
        
        assert result is False
        assert sample_lead.response_status == 'no_template'
        mock_db_session.commit.assert_called()
    
    def test_send_acknowledgment_success(self, mock_credentials_store, mock_db_session,
                                        sample_lead, sample_lead_source_with_template):
        """Test successful email sending."""
        from unittest.mock import patch, MagicMock
        from gmail_lead_sync.responder import AutoResponder
        
        responder = AutoResponder(mock_credentials_store, mock_db_session)
        
        # Mock the send_email method to return success
        with patch.object(responder, 'send_email', return_value=True):
            result = responder.send_acknowledgment(
                sample_lead,
                sample_lead_source_with_template,
                agent_info={'agent_name': 'Agent', 'agent_phone': '555-9999', 
                           'agent_email': 'agent@example.com'}
            )
        
        assert result is True
        assert sample_lead.response_sent is True
        assert sample_lead.response_status == 'sent'
        mock_db_session.commit.assert_called()
    
    def test_send_acknowledgment_failure(self, mock_credentials_store, mock_db_session,
                                        sample_lead, sample_lead_source_with_template):
        """Test email sending failure."""
        from unittest.mock import patch
        from gmail_lead_sync.responder import AutoResponder
        
        responder = AutoResponder(mock_credentials_store, mock_db_session)
        
        # Mock the send_email method to return failure
        with patch.object(responder, 'send_email', return_value=False):
            result = responder.send_acknowledgment(
                sample_lead,
                sample_lead_source_with_template,
                agent_info={'agent_name': 'Agent', 'agent_phone': '555-9999',
                           'agent_email': 'agent@example.com'}
            )
        
        assert result is False
        assert sample_lead.response_sent is False
        assert sample_lead.response_status == 'failed'
        mock_db_session.commit.assert_called()
    
    def test_send_email_success(self, mock_credentials_store, mock_db_session):
        """Test successful SMTP email sending."""
        from unittest.mock import patch, MagicMock
        from gmail_lead_sync.responder import AutoResponder
        
        responder = AutoResponder(mock_credentials_store, mock_db_session)
        
        # Mock SMTP
        with patch('gmail_lead_sync.responder.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            result = responder.send_email(
                to_address='recipient@example.com',
                subject='Test Subject',
                body='Test Body',
                from_address='sender@gmail.com',
                app_password='test_password'
            )
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('sender@gmail.com', 'test_password')
        mock_server.send_message.assert_called_once()
    
    def test_send_email_retry_on_smtp_exception(self, mock_credentials_store, mock_db_session):
        """Test retry logic on SMTP exception."""
        from unittest.mock import patch, MagicMock
        import smtplib
        from gmail_lead_sync.responder import AutoResponder
        
        responder = AutoResponder(mock_credentials_store, mock_db_session)
        
        # Mock SMTP to fail twice then succeed
        with patch('gmail_lead_sync.responder.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            # First two attempts fail, third succeeds
            mock_server.send_message.side_effect = [
                smtplib.SMTPException("Temporary failure"),
                smtplib.SMTPException("Temporary failure"),
                None  # Success
            ]
            
            # Mock time.sleep to speed up test
            with patch('gmail_lead_sync.responder.time.sleep'):
                result = responder.send_email(
                    to_address='recipient@example.com',
                    subject='Test Subject',
                    body='Test Body',
                    from_address='sender@gmail.com',
                    app_password='test_password'
                )
        
        assert result is True
        assert mock_server.send_message.call_count == 3
    
    def test_send_email_max_retries_exceeded(self, mock_credentials_store, mock_db_session):
        """Test that email sending fails after max retries."""
        from unittest.mock import patch, MagicMock
        import smtplib
        from gmail_lead_sync.responder import AutoResponder
        
        responder = AutoResponder(mock_credentials_store, mock_db_session)
        
        # Mock SMTP to always fail
        with patch('gmail_lead_sync.responder.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            mock_server.send_message.side_effect = smtplib.SMTPException("Permanent failure")
            
            # Mock time.sleep to speed up test
            with patch('gmail_lead_sync.responder.time.sleep'):
                result = responder.send_email(
                    to_address='recipient@example.com',
                    subject='Test Subject',
                    body='Test Body',
                    from_address='sender@gmail.com',
                    app_password='test_password',
                    max_attempts=3
                )
        
        assert result is False
        assert mock_server.send_message.call_count == 3
    
    def test_send_email_with_tls(self, mock_credentials_store, mock_db_session):
        """Test that TLS/STARTTLS is enabled."""
        from unittest.mock import patch, MagicMock
        from gmail_lead_sync.responder import AutoResponder
        
        responder = AutoResponder(mock_credentials_store, mock_db_session)
        
        with patch('gmail_lead_sync.responder.smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            responder.send_email(
                to_address='recipient@example.com',
                subject='Test Subject',
                body='Test Body',
                from_address='sender@gmail.com',
                app_password='test_password'
            )
        
        # Verify STARTTLS was called
        mock_server.starttls.assert_called_once()
        
        # Verify connection to correct SMTP server
        mock_smtp.assert_called_once_with('smtp.gmail.com', 587, timeout=30)

"""
Unit tests for LeadParser component.

Tests the parser's ability to:
- Match emails to Lead_Source configurations
- Extract lead information using regex patterns
- Validate data with Pydantic models
- Create Lead records in the database
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gmail_lead_sync.models import Base, Lead, LeadSource, ProcessingLog
from gmail_lead_sync.parser import LeadParser


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_lead_source(db_session):
    """Create a sample LeadSource configuration."""
    lead_source = LeadSource(
        sender_email='leads@example.com',
        identifier_snippet='New Lead Notification',
        name_regex=r'Name:\s*(.+?)(?:\n|$)',
        phone_regex=r'Phone:\s*([\d\-\(\)\s\+]+?)(?:\n|$)',
        auto_respond_enabled=False
    )
    db_session.add(lead_source)
    db_session.commit()
    return lead_source


@pytest.fixture
def parser(db_session):
    """Create a LeadParser instance."""
    return LeadParser(db_session)


class TestGetLeadSource:
    """Tests for get_lead_source method."""
    
    def test_matching_sender_and_identifier(self, parser, sample_lead_source):
        """Test successful match with sender email and identifier snippet."""
        email_body = """
        New Lead Notification
        
        Name: John Doe
        Phone: 555-1234
        """
        
        result = parser.get_lead_source('leads@example.com', email_body)
        
        assert result is not None
        assert result.id == sample_lead_source.id
        assert result.sender_email == 'leads@example.com'
    
    def test_no_matching_sender(self, parser, sample_lead_source):
        """Test no match when sender email doesn't exist in database."""
        email_body = "New Lead Notification"
        
        result = parser.get_lead_source('unknown@example.com', email_body)
        
        assert result is None
    
    def test_matching_sender_but_no_identifier(self, parser, sample_lead_source):
        """Test no match when sender matches but identifier snippet is missing."""
        email_body = """
        Some other email content
        Name: John Doe
        Phone: 555-1234
        """
        
        result = parser.get_lead_source('leads@example.com', email_body)
        
        assert result is None


class TestExtractLead:
    """Tests for extract_lead method."""
    
    def test_successful_extraction(self, parser, sample_lead_source):
        """Test successful lead extraction with valid email content."""
        email_body = """
        New Lead Notification
        
        Name: John Doe
        Phone: 555-1234
        Email: john@example.com
        """
        
        lead_data = parser.extract_lead(email_body, sample_lead_source)
        
        assert lead_data is not None
        assert lead_data.name == 'John Doe'
        assert lead_data.phone == '555-1234'
        assert lead_data.source_email == 'leads@example.com'
    
    def test_name_regex_no_match(self, parser, sample_lead_source):
        """Test extraction failure when name regex doesn't match."""
        email_body = """
        New Lead Notification
        
        Phone: 555-1234
        """
        
        lead_data = parser.extract_lead(email_body, sample_lead_source)
        
        assert lead_data is None
    
    def test_phone_regex_no_match(self, parser, sample_lead_source):
        """Test extraction failure when phone regex doesn't match."""
        email_body = """
        New Lead Notification
        
        Name: John Doe
        """
        
        lead_data = parser.extract_lead(email_body, sample_lead_source)
        
        assert lead_data is None
    
    def test_extraction_with_various_phone_formats(self, parser, sample_lead_source):
        """Test extraction with different phone number formats."""
        test_cases = [
            ('555-1234', '555-1234'),
            ('(555) 123-4567', '(555) 123-4567'),
            ('555 123 4567', '555 123 4567'),
            ('+1 555-123-4567', '+1 555-123-4567'),
        ]
        
        for phone_in_email, expected_phone in test_cases:
            email_body = f"""
            New Lead Notification
            
            Name: John Doe
            Phone: {phone_in_email}
            """
            
            lead_data = parser.extract_lead(email_body, sample_lead_source)
            
            assert lead_data is not None, f"Failed to extract phone: {phone_in_email}"
            assert lead_data.phone == expected_phone


class TestValidateAndCreateLead:
    """Tests for validate_and_create_lead method."""
    
    def test_successful_lead_creation(self, parser, sample_lead_source, db_session):
        """Test successful Lead record creation."""
        from gmail_lead_sync.validation import LeadData
        
        lead_data = LeadData(
            name='John Doe',
            phone='555-1234',
            source_email='leads@example.com'
        )
        
        lead = parser.validate_and_create_lead(
            lead_data,
            gmail_uid='12345',
            lead_source_id=sample_lead_source.id
        )
        
        assert lead is not None
        assert lead.id is not None
        assert lead.name == 'John Doe'
        assert lead.phone == '555-1234'
        assert lead.gmail_uid == '12345'
        assert lead.lead_source_id == sample_lead_source.id
        
        # Verify it's in the database
        db_lead = db_session.query(Lead).filter_by(gmail_uid='12345').first()
        assert db_lead is not None
        assert db_lead.name == 'John Doe'


class TestParseEmail:
    """Tests for the complete parse_email workflow."""
    
    def test_complete_successful_parsing(self, parser, sample_lead_source, db_session):
        """Test complete email parsing workflow from start to finish."""
        email_body = """
        New Lead Notification
        
        Name: Jane Smith
        Phone: (555) 987-6543
        Email: jane@example.com
        """
        
        lead = parser.parse_email(
            sender_email='leads@example.com',
            email_body=email_body,
            gmail_uid='test-uid-001'
        )
        
        assert lead is not None
        assert lead.name == 'Jane Smith'
        assert lead.phone == '(555) 987-6543'
        assert lead.gmail_uid == 'test-uid-001'
        
        # Verify ProcessingLog was created with success status
        log = db_session.query(ProcessingLog).filter_by(gmail_uid='test-uid-001').first()
        assert log is not None
        assert log.status == 'success'
        assert log.lead_id == lead.id
    
    def test_parsing_failure_logs_error(self, parser, sample_lead_source, db_session):
        """Test that parsing failures are logged to ProcessingLog."""
        email_body = """
        New Lead Notification
        
        Name: Jane Smith
        (missing phone number)
        """
        
        lead = parser.parse_email(
            sender_email='leads@example.com',
            email_body=email_body,
            gmail_uid='test-uid-002'
        )
        
        assert lead is None
        
        # Verify ProcessingLog was created with failure status
        log = db_session.query(ProcessingLog).filter_by(gmail_uid='test-uid-002').first()
        assert log is not None
        assert log.status == 'parsing_failed'
        assert log.lead_id is None
        assert 'extraction_failed' in log.error_details
    
    def test_no_matching_lead_source_logs_error(self, parser, db_session):
        """Test that missing Lead_Source is logged."""
        email_body = """
        Some email content
        Name: John Doe
        Phone: 555-1234
        """
        
        lead = parser.parse_email(
            sender_email='unknown@example.com',
            email_body=email_body,
            gmail_uid='test-uid-003'
        )
        
        assert lead is None
        
        # Verify ProcessingLog was created
        log = db_session.query(ProcessingLog).filter_by(gmail_uid='test-uid-003').first()
        assert log is not None
        assert log.status == 'parsing_failed'
        assert 'no_matching_lead_source' in log.error_details

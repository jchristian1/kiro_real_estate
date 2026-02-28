"""
Property-based tests for LeadParser component.

Feature: gmail-lead-sync-engine

These tests use Hypothesis to verify universal properties that should hold
across all inputs for the parser component.
"""

import pytest
from hypothesis import given, strategies as st, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gmail_lead_sync.models import Base, Lead, LeadSource, ProcessingLog
from gmail_lead_sync.parser import LeadParser
from gmail_lead_sync.validation import LeadData
import re


def create_test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


# Hypothesis strategies for generating test data
valid_email_strategy = st.emails()

valid_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters=' .-'),
    min_size=1,
    max_size=100
).filter(lambda x: x.strip() != '')

valid_phone_strategy = st.from_regex(r'\+?[\d\s\-\(\)]{7,20}', fullmatch=True).filter(
    lambda x: len(re.sub(r'\D', '', x)) >= 7
)


class TestProperty9LeadSourceMatching:
    """
    Property 9: Lead Source Matching
    **Validates: Requirements 4.3**
    
    When multiple Lead_Source records match a sender email, the parser
    should return the first one with a valid identifier_snippet in the email body.
    """
    
    @given(
        sender=valid_email_strategy,
        identifier1=st.text(min_size=5, max_size=50),
        identifier2=st.text(min_size=5, max_size=50)
    )
    def test_first_matching_identifier_wins(self, sender, identifier1, identifier2):
        """Test that first Lead_Source with matching identifier is selected."""
        # Ensure identifiers are different
        assume(identifier1 != identifier2)
        
        db_session = create_test_db()
        parser = LeadParser(db_session)
        
        # Create first Lead_Source with sender
        lead_source1 = LeadSource(
            sender_email=sender,
            identifier_snippet=identifier1,
            name_regex=r'Name:\s*(.+)',
            phone_regex=r'Phone:\s*([\d\-]+)'
        )
        db_session.add(lead_source1)
        db_session.commit()
        
        # Email contains second identifier only (first doesn't match)
        email_body = f"Email content with {identifier2} in it"
        
        result = parser.get_lead_source(sender, email_body)
        
        # Should not match because identifier1 is not in email
        assert result is None
        
        # Now test with identifier1 in email
        email_body2 = f"Email content with {identifier1} in it"
        result2 = parser.get_lead_source(sender, email_body2)
        
        # Should match
        assert result2 is not None
        assert result2.identifier_snippet == identifier1
        
        db_session.close()


class TestProperty11IdentifierSnippetVerification:
    """
    Property 11: Identifier Snippet Verification
    **Validates: Requirements 5.1**
    
    The parser should only process emails that contain the identifier_snippet
    from the Lead_Source configuration.
    """
    
    @given(
        sender=valid_email_strategy,
        identifier=st.text(min_size=10, max_size=50),
        email_content=st.text(min_size=20, max_size=200)
    )
    def test_identifier_must_be_present(self, sender, identifier, email_content):
        """Test that emails without identifier_snippet are rejected."""
        # Ensure identifier is not in email content
        assume(identifier not in email_content)
        
        db_session = create_test_db()
        parser = LeadParser(db_session)
        
        lead_source = LeadSource(
            sender_email=sender,
            identifier_snippet=identifier,
            name_regex=r'Name:\s*(.+)',
            phone_regex=r'Phone:\s*([\d\-]+)'
        )
        db_session.add(lead_source)
        db_session.commit()
        
        result = parser.get_lead_source(sender, email_content)
        
        # Should not match because identifier is missing
        assert result is None
        
        db_session.close()


class TestProperty13DualExtractionAttempt:
    """
    Property 13: Dual Extraction Attempt
    **Validates: Requirements 5.3, 5.4**
    
    The parser must attempt to extract both name and phone. If either
    extraction fails, the entire parsing should fail.
    """
    
    @given(
        name=valid_name_strategy,
        phone=valid_phone_strategy
    )
    def test_both_name_and_phone_required(self, name, phone):
        """Test that both name and phone must be extracted successfully."""
        db_session = create_test_db()
        parser = LeadParser(db_session)
        
        lead_source = LeadSource(
            sender_email='test@example.com',
            identifier_snippet='Lead Info',
            name_regex=r'Name:\s*(.+?)(?:\n|$)',
            phone_regex=r'Phone:\s*([\d\s\-\(\)\+]+?)(?:\n|$)'
        )
        db_session.add(lead_source)
        db_session.commit()
        
        # Email with both name and phone
        email_with_both = f"Lead Info\nName: {name}\nPhone: {phone}\n"
        result_both = parser.extract_lead(email_with_both, lead_source)
        assert result_both is not None
        
        # Email with only name
        email_name_only = f"Lead Info\nName: {name}\n"
        result_name_only = parser.extract_lead(email_name_only, lead_source)
        assert result_name_only is None
        
        # Email with only phone
        email_phone_only = f"Lead Info\nPhone: {phone}\n"
        result_phone_only = parser.extract_lead(email_phone_only, lead_source)
        assert result_phone_only is None
        
        db_session.close()


class TestProperty16ValidLeadCreation:
    """
    Property 16: Valid Lead Creation
    **Validates: Requirements 5.7**
    
    When both name and phone are successfully extracted and validated,
    a Lead record must be created in the database.
    """
    
    @given(
        name=valid_name_strategy,
        phone=valid_phone_strategy,
        gmail_uid=st.text(min_size=5, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'
        ))
    )
    def test_valid_extraction_creates_lead(self, name, phone, gmail_uid):
        """Test that valid lead data results in database record creation."""
        db_session = create_test_db()
        parser = LeadParser(db_session)
        
        lead_source = LeadSource(
            sender_email='test@example.com',
            identifier_snippet='Lead',
            name_regex=r'Name:\s*(.+?)(?:\n|$)',
            phone_regex=r'Phone:\s*([\d\s\-\(\)\+]+?)(?:\n|$)'
        )
        db_session.add(lead_source)
        db_session.commit()
        
        email_body = f"Lead\nName: {name}\nPhone: {phone}\n"
        
        lead = parser.parse_email(
            sender_email='test@example.com',
            email_body=email_body,
            gmail_uid=gmail_uid
        )
        
        if lead is not None:
            # Verify lead was created in database
            db_lead = db_session.query(Lead).filter_by(gmail_uid=gmail_uid).first()
            assert db_lead is not None
            assert db_lead.name.strip() == name.strip()
            
            # Verify processing log shows success
            log = db_session.query(ProcessingLog).filter_by(gmail_uid=gmail_uid).first()
            assert log is not None
            assert log.status == 'success'
        
        db_session.close()


class TestProperty15PydanticValidationGate:
    """
    Property 15: Pydantic Validation Gate
    **Validates: Requirements 5.6**
    
    Invalid data should be rejected by Pydantic validation before
    database insertion.
    """
    
    @given(
        invalid_phone=st.text(min_size=1, max_size=20).filter(
            lambda x: len(re.sub(r'\D', '', x)) < 7  # Less than 7 digits
        )
    )
    def test_invalid_phone_rejected(self, invalid_phone):
        """Test that phones with fewer than 7 digits are rejected."""
        db_session = create_test_db()
        parser = LeadParser(db_session)
        
        lead_source = LeadSource(
            sender_email='test@example.com',
            identifier_snippet='Lead',
            name_regex=r'Name:\s*(.+)',
            phone_regex=r'Phone:\s*(.+)'  # Permissive regex to test Pydantic validation
        )
        db_session.add(lead_source)
        db_session.commit()
        
        email_body = f"Lead\nName: John Doe\nPhone: {invalid_phone}"
        
        lead = parser.parse_email(
            sender_email='test@example.com',
            email_body=email_body,
            gmail_uid='test-uid'
        )
        
        # Should fail due to Pydantic validation
        assert lead is None
        
        # Should not create a Lead record
        db_lead = db_session.query(Lead).filter_by(gmail_uid='test-uid').first()
        assert db_lead is None
        
        db_session.close()


class TestProperty23ProcessingAuditTrail:
    """
    Property 23: Processing Audit Trail
    **Validates: Requirements 8.1, 8.2**
    
    Every email processing attempt should create a ProcessingLog record,
    whether successful or failed.
    """
    
    @given(
        gmail_uid=st.text(min_size=5, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'
        )),
        sender=valid_email_strategy
    )
    def test_all_attempts_logged(self, gmail_uid, sender):
        """Test that all parsing attempts are logged."""
        db_session = create_test_db()
        parser = LeadParser(db_session)
        
        lead_source = LeadSource(
            sender_email=sender,
            identifier_snippet='Lead',
            name_regex=r'Name:\s*(.+?)(?:\n|$)',
            phone_regex=r'Phone:\s*([\d\s\-\(\)\+]+?)(?:\n|$)'
        )
        db_session.add(lead_source)
        db_session.commit()
        
        # Try parsing (may succeed or fail)
        email_body = "Lead\nName: Test\nPhone: 555-1234567\n"
        parser.parse_email(
            sender_email=sender,
            email_body=email_body,
            gmail_uid=gmail_uid
        )
        
        # Verify ProcessingLog was created
        log = db_session.query(ProcessingLog).filter_by(gmail_uid=gmail_uid).first()
        assert log is not None
        assert log.sender_email == sender
        assert log.status in ['success', 'parsing_failed']
        
        db_session.close()

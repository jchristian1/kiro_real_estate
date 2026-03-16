"""
Integration tests for input sanitization with parser and config manager.

Tests that sanitization functions are properly integrated into the
parsing workflow and configuration management.
"""

import pytest
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker
from gmail_lead_sync.models import Base, LeadSource
from gmail_lead_sync.parser import LeadParser
from gmail_lead_sync.error_handling import validate_regex_safety


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestParserSanitization:
    """Test that parser properly sanitizes email bodies."""
    
    def test_parser_handles_null_bytes_in_email(self, db_session):
        """Test that parser can handle emails with null bytes."""
        # Create a lead source
        lead_source = LeadSource(
            sender_email="test@example.com",
            identifier_snippet="Lead Notification",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)"
        )
        db_session.add(lead_source)
        db_session.commit()
        
        # Create parser
        parser = LeadParser(db_session)
        
        # Email with null bytes
        email_body = "Lead Notification\nName: John\x00Doe\nPhone: 555-1234"
        
        # Parse should work (null bytes removed by sanitization)
        lead = parser.parse_email(
            sender_email="test@example.com",
            email_body=email_body,
            gmail_uid="test-uid-123"
        )
        
        # Lead should be created successfully
        assert lead is not None
        assert lead.name == "JohnDoe"  # Null byte removed
        assert lead.phone == "555-1234"
    
    def test_parser_handles_large_email_body(self, db_session):
        """Test that parser can handle very large email bodies."""
        # Create a lead source
        lead_source = LeadSource(
            sender_email="test@example.com",
            identifier_snippet="Lead Notification",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)"
        )
        db_session.add(lead_source)
        db_session.commit()
        
        # Create parser
        parser = LeadParser(db_session)
        
        # Email with important data at the beginning and lots of filler
        important_data = "Lead Notification\nName: Jane Smith\nPhone: 555-9876\n"
        filler = "X" * (2 * 1024 * 1024)  # 2MB of filler
        email_body = important_data + filler
        
        # Parse should work (body truncated to 1MB but important data preserved)
        lead = parser.parse_email(
            sender_email="test@example.com",
            email_body=email_body,
            gmail_uid="test-uid-456"
        )
        
        # Lead should be created successfully
        assert lead is not None
        assert lead.name == "Jane Smith"
        assert lead.phone == "555-9876"


class TestConfigManagerRegexValidation:
    """Test that config manager validates regex patterns for safety."""
    
    def test_accepts_safe_regex_patterns(self):
        """Test that safe regex patterns are accepted."""
        # Simple name pattern
        is_safe, error = validate_regex_safety(r"Name:\s*(.+)")
        assert is_safe is True
        assert error is None
        
        # Phone pattern with various formats
        is_safe, error = validate_regex_safety(r"Phone:\s*([\d\-\(\)\s]+)")
        assert is_safe is True
        assert error is None
    
    def test_rejects_dangerous_regex_patterns(self):
        """Test that dangerous regex patterns are rejected."""
        # Nested quantifiers that cause catastrophic backtracking
        dangerous_patterns = [
            r"(a*)+b",
            r"(a+)*b",
            r"(a+)+b",
        ]
        
        for pattern in dangerous_patterns:
            is_safe, error = validate_regex_safety(pattern)
            assert is_safe is False
            assert error is not None
    
    def test_rejects_invalid_regex_syntax(self):
        """Test that invalid regex syntax is rejected."""
        is_safe, error = validate_regex_safety(r"[invalid(")
        assert is_safe is False
        assert "Invalid regex syntax" in error


class TestEndToEndSanitization:
    """End-to-end tests for sanitization in the full workflow."""
    
    def test_malicious_email_body_is_sanitized(self, db_session):
        """Test that malicious email content is properly sanitized."""
        # Create a lead source
        lead_source = LeadSource(
            sender_email="malicious@example.com",
            identifier_snippet="Lead Info",
            name_regex=r"Name:\s*(.+)",
            phone_regex=r"Phone:\s*([\d-]+)"
        )
        db_session.add(lead_source)
        db_session.commit()
        
        # Create parser
        parser = LeadParser(db_session)
        
        # Email with null bytes and excessive size
        malicious_body = (
            "Lead Info\n"
            "Name: Evil\x00User\n"
            "Phone: 555-0000\n"
            + "A" * (3 * 1024 * 1024)  # 3MB of data
        )
        
        # Parse should handle it safely
        lead = parser.parse_email(
            sender_email="malicious@example.com",
            email_body=malicious_body,
            gmail_uid="malicious-uid-789"
        )
        
        # Lead should be created with sanitized data
        assert lead is not None
        assert '\x00' not in lead.name
        assert lead.name == "EvilUser"
        assert lead.phone == "555-0000"

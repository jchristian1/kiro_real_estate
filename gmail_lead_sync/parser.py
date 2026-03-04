"""
Lead parser for Gmail Lead Sync Engine.

This module provides the LeadParser class for extracting lead information
from email bodies using configurable regex patterns. The parser:
- Matches emails to Lead_Source configurations
- Verifies identifier snippets
- Extracts name and phone using regex patterns
- Validates data with Pydantic models
- Creates Lead records in the database
"""

import re
import logging
from typing import Optional
from sqlalchemy.orm import Session
from pydantic import ValidationError

from gmail_lead_sync.models import Lead, LeadSource, ProcessingLog
from gmail_lead_sync.validation import LeadData
from gmail_lead_sync.error_handling import sanitize_email_body


# Configure logger
logger = logging.getLogger(__name__)


class LeadParser:
    """
    Parser for extracting lead information from emails.
    
    The parser uses Lead_Source configurations to identify relevant emails
    and extract lead data using regex patterns. All extracted data is
    validated with Pydantic before database insertion.
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize the lead parser.
        
        Args:
            db_session: SQLAlchemy database session for queries and inserts
        """
        self.db_session = db_session
    
    def get_lead_source(self, sender_email: str, email_body: str) -> Optional[LeadSource]:
        """
        Find matching Lead_Source configuration for an email.
        
        Matches the sender email against Lead_Source records and verifies
        that the identifier_snippet exists in the email body. If multiple
        Lead_Source records match the sender, returns the first one with
        a valid identifier_snippet.
        
        Args:
            sender_email: Email address of the sender
            email_body: Full text content of the email
            
        Returns:
            Matching LeadSource object, or None if no match found
        """
        # Query all Lead_Source records matching the sender email
        lead_sources = self.db_session.query(LeadSource)\
            .filter(LeadSource.sender_email == sender_email)\
            .all()
        
        if not lead_sources:
            logger.warning(f"No Lead_Source configuration found for sender: {sender_email}")
            return None
        
        # Find first Lead_Source with identifier_snippet in email body
        for lead_source in lead_sources:
            if lead_source.identifier_snippet in email_body:
                logger.info(
                    f"Matched Lead_Source ID {lead_source.id} for sender {sender_email} "
                    f"with identifier: '{lead_source.identifier_snippet[:50]}...'"
                )
                return lead_source
        
        # No Lead_Source had matching identifier_snippet
        logger.warning(
            f"Lead_Source found for {sender_email} but identifier_snippet not in email body"
        )
        return None
    
    def extract_lead(self, email_body: str, lead_source: LeadSource) -> Optional[LeadData]:
        """
        Extract lead information from email body using regex patterns.
        
        Applies the name_regex and phone_regex from the Lead_Source configuration
        to extract lead data. Uses the first capture group from each regex match.
        
        Args:
            email_body: Full text content of the email
            lead_source: LeadSource configuration with regex patterns
            
        Returns:
            LeadData object with extracted information, or None if extraction fails
        """
        # Extract name using name_regex
        name_match = re.search(lead_source.name_regex, email_body)
        if not name_match:
            logger.warning(
                f"Name regex did not match for Lead_Source ID {lead_source.id}. "
                f"Pattern: {lead_source.name_regex}"
            )
            return None
        
        # Get first capture group for name
        try:
            name = name_match.group(1)
        except IndexError:
            logger.error(
                f"Name regex matched but no capture group found. "
                f"Pattern: {lead_source.name_regex}"
            )
            return None
        
        # Extract phone using phone_regex
        phone_match = re.search(lead_source.phone_regex, email_body)
        if not phone_match:
            logger.warning(
                f"Phone regex did not match for Lead_Source ID {lead_source.id}. "
                f"Pattern: {lead_source.phone_regex}"
            )
            return None
        
        # Get first capture group for phone
        try:
            phone = phone_match.group(1)
        except IndexError:
            logger.error(
                f"Phone regex matched but no capture group found. "
                f"Pattern: {lead_source.phone_regex}"
            )
            return None
        
        # Create LeadData object for validation
        try:
            lead_data = LeadData(
                name=name,
                phone=phone,
                source_email=lead_source.sender_email
            )
            logger.info(
                f"Successfully extracted lead: name='{lead_data.name}', "
                f"phone='{lead_data.phone}'"
            )
            return lead_data
        except ValidationError as e:
            logger.error(
                f"Pydantic validation failed for extracted lead data. "
                f"Name: '{name}', Phone: '{phone}', Errors: {e}"
            )
            return None
    
    def validate_and_create_lead(
        self,
        lead_data: LeadData,
        gmail_uid: str,
        lead_source_id: int,
        agent_id: str = None
    ) -> Optional[Lead]:
        """
        Validate lead data and create Lead record in database.
        """
        try:
            lead = Lead(
                name=lead_data.name,
                phone=lead_data.phone,
                source_email=lead_data.source_email,
                gmail_uid=gmail_uid,
                lead_source_id=lead_source_id,
                agent_id=agent_id
            )
            
            self.db_session.add(lead)
            self.db_session.flush()
            
            logger.info(
                f"Created Lead ID {lead.id} from Gmail UID {gmail_uid}: "
                f"{lead.name} - {lead.phone}"
            )
            
            return lead
            
        except Exception as e:
            logger.error(
                f"Failed to create Lead record for Gmail UID {gmail_uid}: {e}",
                exc_info=True
            )
            self.db_session.rollback()
            return None
    
    def parse_email(
        self,
        sender_email: str,
        email_body: str,
        gmail_uid: str,
        agent_id: str = None
    ) -> Optional[Lead]:
        """Complete email parsing workflow."""
        email_body = sanitize_email_body(email_body)
        email_snippet = email_body[:500] if len(email_body) > 500 else email_body
        
        try:
            lead_source = self.get_lead_source(sender_email, email_body)
            if not lead_source:
                self._log_parsing_failure(
                    gmail_uid=gmail_uid,
                    sender_email=sender_email,
                    reason="no_matching_lead_source",
                    details=f"No Lead_Source found or identifier_snippet not in email. "
                            f"Email snippet: {email_snippet}"
                )
                return None
            
            lead_data = self.extract_lead(email_body, lead_source)
            if not lead_data:
                self._log_parsing_failure(
                    gmail_uid=gmail_uid,
                    sender_email=sender_email,
                    reason="extraction_failed",
                    details=f"Name regex: {lead_source.name_regex}, "
                            f"Phone regex: {lead_source.phone_regex}. "
                            f"Email snippet: {email_snippet}"
                )
                return None
            
            lead = self.validate_and_create_lead(lead_data, gmail_uid, lead_source.id, agent_id=agent_id)
            if not lead:
                self._log_parsing_failure(
                    gmail_uid=gmail_uid,
                    sender_email=sender_email,
                    reason="database_insertion_failed",
                    details=f"Failed to create Lead record. Email snippet: {email_snippet}"
                )
                return None
            
            self._log_parsing_success(
                gmail_uid=gmail_uid,
                sender_email=sender_email,
                lead_id=lead.id
            )
            
            return lead
            
        except Exception as e:
            logger.error(
                f"Unexpected error parsing email {gmail_uid} from {sender_email}: {e}",
                exc_info=True
            )
            self._log_parsing_failure(
                gmail_uid=gmail_uid,
                sender_email=sender_email,
                reason="unexpected_error",
                details=f"Exception: {str(e)}. Email snippet: {email_snippet}"
            )
            return None
    
    def _log_parsing_failure(
        self,
        gmail_uid: str,
        sender_email: str,
        reason: str,
        details: str
    ) -> None:
        """
        Log parsing failure to ProcessingLog table.
        
        Args:
            gmail_uid: Unique Gmail identifier for the email
            sender_email: Email address of the sender
            reason: Short reason code for the failure
            details: Detailed error information including patterns and email snippet
        """
        try:
            log_entry = ProcessingLog(
                gmail_uid=gmail_uid,
                sender_email=sender_email,
                status='parsing_failed',
                error_details=f"Reason: {reason}. Details: {details}"
            )
            self.db_session.add(log_entry)
            self.db_session.commit()
            
            logger.info(f"Logged parsing failure for Gmail UID {gmail_uid}")
            
        except Exception as e:
            logger.error(
                f"Failed to log parsing failure for Gmail UID {gmail_uid}: {e}",
                exc_info=True
            )
            self.db_session.rollback()
    
    def _log_parsing_success(
        self,
        gmail_uid: str,
        sender_email: str,
        lead_id: int
    ) -> None:
        """
        Log successful parsing to ProcessingLog table.
        
        Args:
            gmail_uid: Unique Gmail identifier for the email
            sender_email: Email address of the sender
            lead_id: ID of the created Lead record
        """
        try:
            log_entry = ProcessingLog(
                gmail_uid=gmail_uid,
                sender_email=sender_email,
                status='success',
                lead_id=lead_id
            )
            self.db_session.add(log_entry)
            self.db_session.commit()
            
            logger.info(f"Logged parsing success for Gmail UID {gmail_uid}")
            
        except Exception as e:
            logger.error(
                f"Failed to log parsing success for Gmail UID {gmail_uid}: {e}",
                exc_info=True
            )
            self.db_session.rollback()
